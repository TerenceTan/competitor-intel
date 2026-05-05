"""
scrapers/apify_social.py
------------------------
Apify-driven social scraper for Facebook + Instagram + X across all
competitors in scrapers/config.py.

Phase 1 shipped this for ic-markets / FB only (D-05). Phase 2 cutover
extends it to all 11 competitors and adds IG + X actors so the broken
Thunderbit / ScraperAPI paths in social_scraper.py can be removed.

Per platform:
  - Facebook:  apify/facebook-pages-scraper (page metadata: followers, likes)
             + apify/facebook-posts-scraper (5 posts/page for posts_last_7d
                                              and engagement metrics)
  - Instagram: apify/instagram-profile-scraper (profile + follower count)
             + apify/instagram-post-scraper (5 posts/handle for posts_last_7d)
  - X/Twitter: kaitoeasyapi cheapest tweet scraper, ~10 tweets/handle so we
               can derive both follower count (from author object) AND
               posts_last_7d (from tweet timestamps).

Outputs per competitor × platform:
  1. ``social_snapshots`` row on success — followers, posts_last_7d,
     engagement_rate (FB only), extraction_confidence (D-18)
  2. ``change_events`` row of ``scraper_zero_results`` when no data returned
  3. ``apify_run_logs`` row ALWAYS (success / empty / failure) for diagnostics

Cost (free-tier-safe at weekly cadence):
  IG profile (1 call, 11 profiles):     ~$0.029
  IG posts   (1 call, ~55 posts):       ~$0.094
  X          (1 call, ~110 tweets):     ~$0.028
  FB pages   (1 call, 11 pages):        ~$0.055
  FB posts   (1 call, 11 × 5 posts):    ~$0.281
  ----------------------------------------------------
  Total per run: ~$0.49  |  Weekly:    ~$1.96/mo

Run from project root::

    APIFY_API_TOKEN=apify_api_xxx .venv/bin/python scrapers/apify_social.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal

from dotenv import load_dotenv

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

# Install secret redaction BEFORE importing apify_client (D-12 / INFRA-03 /
# April 2026 EC2 incident). apify_client SDK debug-logs HTTP requests
# including Authorization headers; SecretRedactionFilter strips them.
from log_redaction import install_redaction  # noqa: E402
install_redaction()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from apify_client import ApifyClient  # noqa: E402
from config import COMPETITORS  # noqa: E402
from db_utils import get_db, log_scraper_run, update_scraper_run  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRAPER_NAME = "apify_social"  # MUST match dbName in src/lib/constants.ts SCRAPERS

# Actor IDs — keep in sync with src/lib/constants.ts ACTOR_TO_SCRAPER map.
FB_ACTOR_ID = "apify/facebook-posts-scraper"
FB_ACTOR_BUILD = "0.0.293"   # verified 2026-05-04 — see APIFY_BUILD_VERIFIED.txt
FB_PAGES_ACTOR_ID = "apify/facebook-pages-scraper"  # page metadata (followers, likes)
IG_ACTOR_ID = "apify/instagram-profile-scraper"
IG_POSTS_ACTOR_ID = "apify/instagram-post-scraper"  # for posts_last_7d
X_ACTOR_ID  = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"

# Per-actor cost caps. Belt-and-braces against runaway scrolls. Free tier is $5/mo.
FB_COST_CAP_USD = Decimal("1.00")  # 11 pages × 5 posts measured ~$0.28
FB_PAGES_COST_CAP_USD = Decimal("0.30")  # 11 pages metadata measured ~$0.055
IG_COST_CAP_USD = Decimal("0.50")  # 11 profiles measured ~$0.029
IG_POSTS_COST_CAP_USD = Decimal("0.50")  # 11 × 5 posts measured ~$0.094
X_COST_CAP_USD  = Decimal("0.50")  # 11 batched searchTerms × ~10 tweets ~$0.028
FB_RESULTS_LIMIT_PER_PAGE = 5      # was 50 in Phase 1 — reduced for Phase 2 cost
IG_POSTS_LIMIT_PER_HANDLE = 5      # enough to compute posts_last_7d
X_TWEETS_PER_HANDLE = 10           # bumped from 1 — needed for posts_last_7d
PER_RUN_TIMEOUT_SECS = 900         # 15 min (subprocess gives 30 min outer cap)

DEFAULT_MARKET_CODE = "global"


# ---------------------------------------------------------------------------
# Per-platform extractors
# ---------------------------------------------------------------------------
def _is_within_7d(timestamp_str: str | None) -> bool:
    if not timestamp_str:
        return False
    try:
        ts = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() <= 7 * 86400
    except Exception:
        return False


def _normalize_slug(s: str | None) -> str:
    return (s or "").lower().strip().lstrip("@").rstrip("/")


def _is_x_tweet_within_7d(timestamp: str | int | float | None) -> bool:
    """X / Twitter tweets carry timestamps in two formats:
      - legacy Twitter: 'Tue Dec 08 10:40:14 +0000 2009'
      - ISO 8601: '2026-05-04T17:09:40.274Z'
    Returns True if timestamp is within 7 days of now."""
    if not timestamp:
        return False
    if isinstance(timestamp, (int, float)):
        try:
            ts = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            return (datetime.now(timezone.utc) - ts).total_seconds() <= 7 * 86400
        except Exception:
            return False
    s = str(timestamp)
    # Try ISO first
    if _is_within_7d(s):
        return True
    # Try legacy Twitter format
    try:
        ts = datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
        return (datetime.now(timezone.utc) - ts).total_seconds() <= 7 * 86400
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Facebook (apify/facebook-pages-scraper for metadata + posts-scraper for activity)
# ---------------------------------------------------------------------------
def _fetch_fb_page_metadata(client: ApifyClient, slugs: list[str]) -> dict[str, dict]:
    """Call apify/facebook-pages-scraper for batched page metadata. Returns
    {slug_lower: {followers, likes}} keyed by slug. Empty dict on failure
    (the FB posts scraper still runs and writes a snapshot row with null
    follower count)."""
    if not slugs:
        return {}
    try:
        logger.info("FB pages: calling %s for %d pages", FB_PAGES_ACTOR_ID, len(slugs))
        run = client.actor(FB_PAGES_ACTOR_ID).call(
            run_input={
                "startUrls": [{"url": f"https://www.facebook.com/{s}"} for s in slugs],
            },
            max_total_charge_usd=FB_PAGES_COST_CAP_USD,
            timeout_secs=PER_RUN_TIMEOUT_SECS,
        ) or {}
        items = list(client.dataset(run.get("defaultDatasetId")).iterate_items())
        logger.info("FB pages: returned %d items, status=%s", len(items), run.get("status"))
    except Exception as e:
        logger.exception("FB pages actor call failed: %s", e)
        return {}

    out: dict[str, dict] = {}
    for it in items:
        url = (it.get("pageUrl") or it.get("url") or it.get("facebookUrl") or "").lower()
        for s in slugs:
            sl = s.lower()
            if f"/{sl}" in url or f"facebook.com/{sl}" in url:
                followers = it.get("followers") or it.get("followersCount")
                likes = it.get("likes") or it.get("likesCount")
                out[sl] = {
                    "followers": int(followers) if isinstance(followers, (int, float)) and followers > 0 else None,
                    "likes": int(likes) if isinstance(likes, (int, float)) and likes > 0 else None,
                }
                break
    return out


def _fb_compute_engagement(page_items: list[dict], follower_count: int | None) -> float | None:
    """Average (likes + comments + shares) per post / followers. Returns
    None if we can't compute (no followers or no posts with engagement)."""
    if not page_items or not follower_count or follower_count <= 0:
        return None
    samples: list[int] = []
    for post in page_items:
        likes = post.get("likesCount") or post.get("likes") or 0
        comments = post.get("commentsCount") or post.get("comments") or 0
        shares = post.get("sharesCount") or post.get("shares") or 0
        if isinstance(likes, dict):  # some actors return reaction breakdowns
            likes = likes.get("total") or sum(v for v in likes.values() if isinstance(v, int))
        try:
            samples.append(int(likes) + int(comments) + int(shares))
        except (TypeError, ValueError):
            continue
    if not samples:
        return None
    avg_engagement = sum(samples) / len(samples)
    return round(avg_engagement / follower_count, 6)


def _fb_group_by_slug(items: list[dict], slugs: list[str]) -> dict[str, list[dict]]:
    """Group posts by which page they came from. Match on the page slug
    appearing in pageUrl / url / facebookUrl."""
    out: dict[str, list[dict]] = {s.lower(): [] for s in slugs}
    for post in items:
        url = (post.get("pageUrl") or post.get("url") or post.get("facebookUrl") or "").lower()
        for s in slugs:
            sl = s.lower()
            if f"/{sl}" in url or f"facebook.com/{sl}" in url:
                out[sl].append(post)
                break
    return out


def run_facebook(client: ApifyClient, conn, run_id: int, snapshot_date: str,
                 targets: list[tuple[str, str]]) -> tuple[int, list[str]]:
    """Returns (records_written, error_messages).

    Two batched actor calls per run:
      1. apify/facebook-pages-scraper → followers + page likes per page
      2. apify/facebook-posts-scraper → recent posts for posts_last_7d +
         engagement metrics (likes/comments/shares per post averaged ÷ followers)
    """
    if not targets:
        return 0, []
    slugs = [t[1] for t in targets]
    by_competitor = {t[1].lower(): t[0] for t in targets}
    errors: list[str] = []
    written = 0
    apify_run_obj: dict = {}
    items: list[dict] = []
    err_msg: str | None = None

    # Step 1: batched page metadata (followers, likes)
    pages_meta = _fetch_fb_page_metadata(client, slugs)

    # Step 2: batched recent posts (for posts_last_7d + engagement)
    try:
        logger.info("FB: calling %s for %d pages", FB_ACTOR_ID, len(slugs))
        apify_run_obj = client.actor(FB_ACTOR_ID).call(
            run_input={
                "startUrls": [{"url": f"https://www.facebook.com/{s}"} for s in slugs],
                "resultsLimit": FB_RESULTS_LIMIT_PER_PAGE,
            },
            build=FB_ACTOR_BUILD,
            max_total_charge_usd=FB_COST_CAP_USD,
            timeout_secs=PER_RUN_TIMEOUT_SECS,
        ) or {}
        items = list(client.dataset(apify_run_obj.get("defaultDatasetId")).iterate_items())
        logger.info("FB: actor returned %d items, status=%s", len(items), apify_run_obj.get("status"))
    except Exception as e:
        err_msg = str(e)
        errors.append(f"fb_actor_call: {e}")
        logger.exception("FB actor call failed")

    grouped = _fb_group_by_slug(items, slugs)

    for slug in slugs:
        slug_l = slug.lower()
        cid = by_competitor[slug_l]
        page_items = grouped.get(slug_l, [])
        page_meta = pages_meta.get(slug_l, {})
        # Pages scraper is the authoritative source for followers; fall back
        # to whatever the posts scraper happened to embed if pages call failed.
        follower_count = page_meta.get("followers")
        platform_status = "success" if (page_items or follower_count) else "empty"

        if page_items or follower_count:
            posts_last_7d = sum(
                1 for it in page_items
                if _is_within_7d(it.get("time") or it.get("timestamp") or it.get("createdAt"))
            )
            engagement_rate = _fb_compute_engagement(page_items, follower_count)
            confidence = "high" if (follower_count and posts_last_7d > 0) else "medium"
            try:
                conn.execute(
                    "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? "
                    "AND market_code=? AND snapshot_date=?",
                    (cid, "facebook", DEFAULT_MARKET_CODE, snapshot_date),
                )
                conn.execute(
                    """
                    INSERT INTO social_snapshots
                      (competitor_id, platform, snapshot_date, followers,
                       posts_last_7d, engagement_rate, latest_post_url,
                       market_code, extraction_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "facebook", snapshot_date, follower_count, posts_last_7d,
                     engagement_rate,
                     (page_items[0].get("url") or page_items[0].get("postUrl")) if page_items else None,
                     DEFAULT_MARKET_CODE, confidence),
                )
                written += 1
            except Exception as e:
                errors.append(f"fb_db_write[{cid}]: {e}")
                logger.exception("FB DB write failed for %s", cid)
        else:
            # Zero-result silent-success guard
            try:
                conn.execute(
                    """
                    INSERT INTO change_events
                      (competitor_id, domain, field_name, old_value, new_value,
                       severity, detected_at, market_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "social_facebook", "scraper_zero_results", None,
                     json.dumps({"actor_id": FB_ACTOR_ID, "platform": "facebook",
                                 "apify_run_id": apify_run_obj.get("id")}),
                     "medium", datetime.now(timezone.utc).isoformat(), DEFAULT_MARKET_CODE),
                )
            except Exception as e:
                errors.append(f"fb_zero_event[{cid}]: {e}")

        # apify_run_logs row per competitor (shared apify_run_id)
        try:
            conn.execute(
                """
                INSERT INTO apify_run_logs
                  (scraper_run_id, apify_run_id, actor_id, actor_version,
                   competitor_id, platform, market_code, status, dataset_count,
                   cost_usd, error_message, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, apify_run_obj.get("id"), FB_ACTOR_ID, FB_ACTOR_BUILD,
                 cid, "facebook", DEFAULT_MARKET_CODE,
                 "failed" if err_msg else platform_status,
                 len(page_items), None, err_msg,
                 apify_run_obj.get("startedAt") or datetime.now(timezone.utc).isoformat(),
                 apify_run_obj.get("finishedAt")),
            )
        except Exception as e:
            errors.append(f"fb_log_row[{cid}]: {e}")

    conn.commit()
    return written, errors


# ---------------------------------------------------------------------------
# Instagram (profile scraper for metadata + post scraper for posts_last_7d)
# ---------------------------------------------------------------------------
def _fetch_ig_posts_per_handle(client: ApifyClient, handles: list[str]) -> dict[str, int]:
    """Call apify/instagram-post-scraper for batched recent posts. Returns
    {handle_lower: posts_last_7d}. Empty dict on failure (snapshot still
    writes with posts_last_7d=None)."""
    if not handles:
        return {}
    try:
        logger.info("IG posts: calling %s for %d handles", IG_POSTS_ACTOR_ID, len(handles))
        run = client.actor(IG_POSTS_ACTOR_ID).call(
            run_input={
                "directUrls": [f"https://www.instagram.com/{h}/" for h in handles],
                "resultsLimit": IG_POSTS_LIMIT_PER_HANDLE,
            },
            max_total_charge_usd=IG_POSTS_COST_CAP_USD,
            timeout_secs=PER_RUN_TIMEOUT_SECS,
        ) or {}
        items = list(client.dataset(run.get("defaultDatasetId")).iterate_items())
        logger.info("IG posts: returned %d items, status=%s", len(items), run.get("status"))
    except Exception as e:
        logger.exception("IG posts actor call failed: %s", e)
        return {}

    counts: dict[str, int] = {}
    for post in items:
        owner = post.get("ownerUsername") or post.get("username") or ""
        h = _normalize_slug(owner)
        if not h:
            continue
        ts = post.get("timestamp") or post.get("takenAtTimestamp") or post.get("createdAt")
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        if _is_within_7d(ts):
            counts[h] = counts.get(h, 0) + 1
    return counts


def run_instagram(client: ApifyClient, conn, run_id: int, snapshot_date: str,
                  targets: list[tuple[str, str]]) -> tuple[int, list[str]]:
    if not targets:
        return 0, []
    handles = [t[1] for t in targets]
    by_handle = {_normalize_slug(t[1]): t[0] for t in targets}
    errors: list[str] = []
    written = 0
    apify_run_obj: dict = {}
    items: list[dict] = []
    err_msg: str | None = None

    # Step 1: batched profile data (followers)
    try:
        logger.info("IG: calling %s for %d handles", IG_ACTOR_ID, len(handles))
        apify_run_obj = client.actor(IG_ACTOR_ID).call(
            run_input={"usernames": handles},
            max_total_charge_usd=IG_COST_CAP_USD,
            timeout_secs=PER_RUN_TIMEOUT_SECS,
        ) or {}
        items = list(client.dataset(apify_run_obj.get("defaultDatasetId")).iterate_items())
        logger.info("IG: returned %d items, status=%s", len(items), apify_run_obj.get("status"))
    except Exception as e:
        err_msg = str(e)
        errors.append(f"ig_actor_call: {e}")
        logger.exception("IG actor call failed")

    # Step 2: batched recent posts (for posts_last_7d)
    posts_per_handle = _fetch_ig_posts_per_handle(client, handles)

    # Index by username — the actor returns one item per username.
    by_user = {_normalize_slug(it.get("username")): it for it in items if it.get("username")}

    for handle in handles:
        h = _normalize_slug(handle)
        cid = by_handle[h]
        item = by_user.get(h)
        if item and isinstance(item.get("followersCount"), int):
            try:
                followers = item["followersCount"]
                posts_last_7d = posts_per_handle.get(h, 0)
                confidence = "high" if (followers > 0 and posts_last_7d > 0) else "medium"
                conn.execute(
                    "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? "
                    "AND market_code=? AND snapshot_date=?",
                    (cid, "instagram", DEFAULT_MARKET_CODE, snapshot_date),
                )
                conn.execute(
                    """
                    INSERT INTO social_snapshots
                      (competitor_id, platform, snapshot_date, followers,
                       posts_last_7d, latest_post_url, market_code, extraction_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "instagram", snapshot_date, followers, posts_last_7d,
                     f"https://www.instagram.com/{handle}/", DEFAULT_MARKET_CODE, confidence),
                )
                written += 1
                platform_status = "success"
                dataset_count = 1
            except Exception as e:
                errors.append(f"ig_db_write[{cid}]: {e}")
                platform_status = "failed"
                dataset_count = 0
        else:
            try:
                conn.execute(
                    """
                    INSERT INTO change_events
                      (competitor_id, domain, field_name, old_value, new_value,
                       severity, detected_at, market_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "social_instagram", "scraper_zero_results", None,
                     json.dumps({"actor_id": IG_ACTOR_ID, "platform": "instagram",
                                 "apify_run_id": apify_run_obj.get("id")}),
                     "medium", datetime.now(timezone.utc).isoformat(), DEFAULT_MARKET_CODE),
                )
            except Exception as e:
                errors.append(f"ig_zero_event[{cid}]: {e}")
            platform_status = "empty"
            dataset_count = 0

        try:
            conn.execute(
                """
                INSERT INTO apify_run_logs
                  (scraper_run_id, apify_run_id, actor_id, actor_version,
                   competitor_id, platform, market_code, status, dataset_count,
                   cost_usd, error_message, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, apify_run_obj.get("id"), IG_ACTOR_ID, None, cid, "instagram",
                 DEFAULT_MARKET_CODE, "failed" if err_msg else platform_status,
                 dataset_count, None, err_msg,
                 apify_run_obj.get("startedAt") or datetime.now(timezone.utc).isoformat(),
                 apify_run_obj.get("finishedAt")),
            )
        except Exception as e:
            errors.append(f"ig_log_row[{cid}]: {e}")

    conn.commit()
    return written, errors


# ---------------------------------------------------------------------------
# X / Twitter (kaitoeasyapi cheapest tweet scraper)
# ---------------------------------------------------------------------------
def run_x(client: ApifyClient, conn, run_id: int, snapshot_date: str,
          targets: list[tuple[str, str]]) -> tuple[int, list[str]]:
    if not targets:
        return 0, []
    handles = [t[1] for t in targets]
    by_handle = {_normalize_slug(t[1]): t[0] for t in targets}
    errors: list[str] = []
    written = 0
    apify_run_obj: dict = {}
    items: list[dict] = []
    err_msg: str | None = None

    try:
        logger.info("X: calling %s for %d handles (×%d tweets each)",
                    X_ACTOR_ID, len(handles), X_TWEETS_PER_HANDLE)
        apify_run_obj = client.actor(X_ACTOR_ID).call(
            run_input={
                "searchTerms": [f"from:{h}" for h in handles],
                # bumped from 1: need ~10 tweets per handle to count posts_last_7d.
                # actor minimum batch is 20/searchTerm so we get plenty either way.
                "maxItems": len(handles) * X_TWEETS_PER_HANDLE,
            },
            max_total_charge_usd=X_COST_CAP_USD,
            timeout_secs=PER_RUN_TIMEOUT_SECS,
        ) or {}
        items = list(client.dataset(apify_run_obj.get("defaultDatasetId")).iterate_items())
        logger.info("X: returned %d items, status=%s", len(items), apify_run_obj.get("status"))
    except Exception as e:
        err_msg = str(e)
        errors.append(f"x_actor_call: {e}")
        logger.exception("X actor call failed")

    # Tweets carry the author object. Index FIRST tweet per user as the
    # author-info source; also count tweets per user inside 7-day window.
    by_user: dict[str, dict] = {}
    posts_last_7d_per_user: dict[str, int] = {}
    mock_count = 0
    for tweet in items:
        if tweet.get("type") == "mock_tweet":
            mock_count += 1
            continue
        author = tweet.get("author") or {}
        u = _normalize_slug(author.get("userName"))
        if not u:
            continue
        if u not in by_user:
            by_user[u] = author
        # Count this tweet against posts_last_7d if its createdAt is within 7d.
        # createdAt format: "Tue Dec 08 10:40:14 +0000 2009" (legacy Twitter)
        # or ISO. Try both.
        created = tweet.get("createdAt") or tweet.get("created_at")
        if _is_x_tweet_within_7d(created):
            posts_last_7d_per_user[u] = posts_last_7d_per_user.get(u, 0) + 1
    if mock_count:
        logger.warning("X: %d mock placeholders (handles that 404'd) — billed but ignored", mock_count)

    for handle in handles:
        h = _normalize_slug(handle)
        cid = by_handle[h]
        author = by_user.get(h)
        if author and isinstance(author.get("followers"), int):
            try:
                followers = author["followers"]
                posts_last_7d = posts_last_7d_per_user.get(h, 0)
                confidence = "high" if (followers > 0 and posts_last_7d > 0) else "medium"
                conn.execute(
                    "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? "
                    "AND market_code=? AND snapshot_date=?",
                    (cid, "x", DEFAULT_MARKET_CODE, snapshot_date),
                )
                conn.execute(
                    """
                    INSERT INTO social_snapshots
                      (competitor_id, platform, snapshot_date, followers,
                       posts_last_7d, latest_post_url, market_code, extraction_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "x", snapshot_date, followers, posts_last_7d,
                     f"https://x.com/{handle}", DEFAULT_MARKET_CODE, confidence),
                )
                written += 1
                platform_status = "success"
                dataset_count = 1
            except Exception as e:
                errors.append(f"x_db_write[{cid}]: {e}")
                platform_status = "failed"
                dataset_count = 0
        else:
            try:
                conn.execute(
                    """
                    INSERT INTO change_events
                      (competitor_id, domain, field_name, old_value, new_value,
                       severity, detected_at, market_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "social_x", "scraper_zero_results", None,
                     json.dumps({"actor_id": X_ACTOR_ID, "platform": "x",
                                 "apify_run_id": apify_run_obj.get("id"),
                                 "mock_count": mock_count}),
                     "medium", datetime.now(timezone.utc).isoformat(), DEFAULT_MARKET_CODE),
                )
            except Exception as e:
                errors.append(f"x_zero_event[{cid}]: {e}")
            platform_status = "empty"
            dataset_count = 0

        try:
            conn.execute(
                """
                INSERT INTO apify_run_logs
                  (scraper_run_id, apify_run_id, actor_id, actor_version,
                   competitor_id, platform, market_code, status, dataset_count,
                   cost_usd, error_message, started_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, apify_run_obj.get("id"), X_ACTOR_ID, None, cid, "x",
                 DEFAULT_MARKET_CODE, "failed" if err_msg else platform_status,
                 dataset_count, None, err_msg,
                 apify_run_obj.get("startedAt") or datetime.now(timezone.utc).isoformat(),
                 apify_run_obj.get("finishedAt")),
            )
        except Exception as e:
            errors.append(f"x_log_row[{cid}]: {e}")

    conn.commit()
    return written, errors


# ---------------------------------------------------------------------------
# Main entry — orchestrate all 3 platforms
# ---------------------------------------------------------------------------
def run():
    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        logger.error("APIFY_API_TOKEN not set — aborting")
        sys.exit(1)

    run_id = log_scraper_run(SCRAPER_NAME, "running")
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    client = ApifyClient(api_token)

    fb_targets = [(c["id"], c["facebook_slug"])    for c in COMPETITORS if c.get("facebook_slug")]
    ig_targets = [(c["id"], c["instagram_handle"]) for c in COMPETITORS if c.get("instagram_handle")]
    x_targets  = [(c["id"], c["x_handle"])         for c in COMPETITORS if c.get("x_handle")]

    logger.info("Targets — FB: %d, IG: %d, X: %d competitors",
                len(fb_targets), len(ig_targets), len(x_targets))

    total_written = 0
    all_errors: list[str] = []

    with closing(get_db()) as conn:
        n, errs = run_facebook(client, conn, run_id, snapshot_date, fb_targets)
        total_written += n
        all_errors.extend(errs)

        n, errs = run_instagram(client, conn, run_id, snapshot_date, ig_targets)
        total_written += n
        all_errors.extend(errs)

        n, errs = run_x(client, conn, run_id, snapshot_date, x_targets)
        total_written += n
        all_errors.extend(errs)

    status = "success" if not all_errors else "partial"
    update_scraper_run(run_id, status, total_written, "; ".join(all_errors[:5]) or None)
    logger.info("DONE. wrote=%d errors=%d status=%s", total_written, len(all_errors), status)


if __name__ == "__main__":
    run()

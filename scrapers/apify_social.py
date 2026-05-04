"""
scrapers/apify_social.py
------------------------
Apify-driven social scraper for Facebook + Instagram + X across all
competitors in scrapers/config.py.

Phase 1 shipped this for ic-markets / FB only (D-05). Phase 2 cutover
extends it to all 11 competitors and adds IG + X actors so the broken
Thunderbit / ScraperAPI paths in social_scraper.py can be removed.

Per platform:
  - Facebook: apify/facebook-posts-scraper (5 posts/page, batched)
  - Instagram: apify/instagram-profile-scraper (batched)
  - X / Twitter: kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest
                 (batched via searchTerms with from: operator; mock-data detection)

Outputs per competitor × platform:
  1. ``social_snapshots`` row on success (extraction_confidence per D-18)
  2. ``change_events`` row of ``scraper_zero_results`` when no data returned
  3. ``apify_run_logs`` row ALWAYS (success / empty / failure) for diagnostics

Cost (free-tier-safe at weekly cadence):
  IG (1 actor call, 11 profiles):                   ~$0.029
  X  (1 actor call, ~220 tweets w/ batched terms):  ~$0.055
  FB (1 actor call, 11 pages × 5 posts):            ~$0.281
  ----------------------------------------------------------
  Total per run: ~$0.36   |   Weekly: ~$1.44/mo

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
IG_ACTOR_ID = "apify/instagram-profile-scraper"
X_ACTOR_ID  = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"

# Per-actor cost caps. Belt-and-braces against runaway scrolls. Free tier is $5/mo.
FB_COST_CAP_USD = Decimal("1.00")  # 11 pages × 5 posts measured ~$0.28; cap at 1.00
IG_COST_CAP_USD = Decimal("0.50")  # 11 profiles measured ~$0.029; generous cap
X_COST_CAP_USD  = Decimal("0.50")  # 11 batched searchTerms measured ~$0.055
FB_RESULTS_LIMIT_PER_PAGE = 5      # was 50 in Phase 1 — reduced for Phase 2 cost
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


# ---------------------------------------------------------------------------
# Facebook (apify/facebook-posts-scraper)
# ---------------------------------------------------------------------------
def _fb_extract_followers(items_for_page: list[dict]) -> int | None:
    """FB posts-scraper sometimes embeds page metadata on each post; try
    several known shapes defensively. Returns None when none of the
    candidates are present or positive (PHASE 2 NOTE: this actor is
    post-focused; consider apify/facebook-pages-scraper for cleaner page
    metadata in a future plan)."""
    for it in items_for_page or []:
        candidates = [
            it.get("followers"),
            (it.get("page") or {}).get("followers"),
            (it.get("page") or {}).get("followersCount"),
            it.get("pageFollowers"),
            it.get("pageLikes"),  # FB pages often expose likes as proxy
        ]
        for c in candidates:
            if isinstance(c, (int, float)) and c > 0:
                return int(c)
    return None


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
    """Returns (records_written, error_messages)."""
    if not targets:
        return 0, []
    slugs = [t[1] for t in targets]
    by_competitor = {t[1].lower(): t[0] for t in targets}
    errors: list[str] = []
    written = 0
    apify_run_obj: dict = {}
    items: list[dict] = []
    err_msg: str | None = None

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
        platform_status = "success" if page_items else "empty"

        if page_items:
            follower_count = _fb_extract_followers(page_items)
            posts_last_7d = sum(
                1 for it in page_items
                if _is_within_7d(it.get("time") or it.get("timestamp") or it.get("createdAt"))
            )
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
                       posts_last_7d, latest_post_url, market_code, extraction_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, "facebook", snapshot_date, follower_count, posts_last_7d,
                     page_items[0].get("url") or page_items[0].get("postUrl"),
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
# Instagram (apify/instagram-profile-scraper)
# ---------------------------------------------------------------------------
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

    # Index by username — the actor returns one item per username.
    by_user = {_normalize_slug(it.get("username")): it for it in items if it.get("username")}

    for handle in handles:
        h = _normalize_slug(handle)
        cid = by_handle[h]
        item = by_user.get(h)
        if item and isinstance(item.get("followersCount"), int):
            try:
                followers = item["followersCount"]
                posts_count = item.get("postsCount") or 0
                # IG profile actor doesn't return per-post timestamps; use postsCount as
                # a proxy "has activity" signal. Real posts_last_7d would need a separate call.
                confidence = "high" if followers > 0 else "medium"
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
                    (cid, "instagram", snapshot_date, followers, None,
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
        logger.info("X: calling %s for %d handles", X_ACTOR_ID, len(handles))
        apify_run_obj = client.actor(X_ACTOR_ID).call(
            run_input={
                "searchTerms": [f"from:{h}" for h in handles],
                "maxItems": len(handles),
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

    # Tweets carry the author object; index by author.userName. Skip mocks.
    by_user: dict[str, dict] = {}
    mock_count = 0
    for tweet in items:
        if tweet.get("type") == "mock_tweet":
            mock_count += 1
            continue
        author = tweet.get("author") or {}
        u = _normalize_slug(author.get("userName"))
        if u and u not in by_user:
            by_user[u] = author
    if mock_count:
        logger.warning("X: %d mock placeholders (handles that 404'd) — billed but ignored", mock_count)

    for handle in handles:
        h = _normalize_slug(handle)
        cid = by_handle[h]
        author = by_user.get(h)
        if author and isinstance(author.get("followers"), int):
            try:
                followers = author["followers"]
                statuses = author.get("statusesCount") or 0
                confidence = "high" if followers > 0 else "medium"
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
                    (cid, "x", snapshot_date, followers, None,
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

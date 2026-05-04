"""
social_scraper.py
-----------------
Social media scraper for competitor follower counts:
  - YouTube: YouTube Data API v3 (channel search + subscriber count + recent videos)
  - Instagram, X: Thunderbit AI extraction (primary), ScraperAPI regex (fallback)

Phase 1 (D-01): Facebook moved to scrapers/apify_social.py — runs as a
separate subprocess via scrapers/run_all.py SCRIPTS list. The Thunderbit
FB code path was removed from this file. Instagram and X stay here until
Phase 2 owns the IG/X cutover.

Requires environment variables:
  YOUTUBE_API_KEY      – for YouTube Data API
  THUNDERBIT_API_KEY   – for AI-powered social extraction (Instagram, X)
  SCRAPERAPI_KEY       – fallback for Instagram, X scraping

Run from the project root:
    python scrapers/social_scraper.py
    python scrapers/social_scraper.py --broker ic-markets   # single broker test
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.parse import quote_plus, urlencode
from urllib.error import URLError

import requests

from dotenv import load_dotenv

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import DELAY_BETWEEN_REQUESTS, SCRAPER_UA
from db_utils import get_all_brokers
COMPETITORS = get_all_brokers()
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change

SCRAPER_NAME = "social_scraper"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
THUNDERBIT_API_URL = "https://openapi.thunderbit.com/openapi/v1/extract"

# --- Thunderbit schemas for each platform ---
# Thunderbit uses simple {field_name: description} format, not JSON Schema.
# Phase 1: Facebook moved to scrapers/apify_social.py — _FB_SCHEMA removed.
_IG_SCHEMA = {
    "followers": "Total number of followers, as a number",
    "posts_count": "Total number of posts, as a number",
    "is_verified": "Whether the account is verified, true or false",
}

_X_SCHEMA = {
    "followers": "Total number of followers, as a number",
    "posts_count": "Total number of posts or tweets, as a number",
    "is_verified": "Whether the account is verified, true or false",
}

_THUNDERBIT_MAX_RETRIES = 2
_THUNDERBIT_RETRY_DELAY = 5  # seconds

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fetch_via_scraperapi(url: str, api_key: str, render: bool = True, premium: bool = False, country_code: str | None = None) -> str | None:
    """Fetch a URL through ScraperAPI. Returns HTML string or None on failure."""
    api_url = (
        f"http://api.scraperapi.com"
        f"?api_key={api_key}"
        f"&url={url}"
        f"&render={'true' if render else 'false'}"
    )
    if country_code:
        api_url += f"&country_code={country_code}"
    if premium:
        api_url += "&premium=true"
    try:
        resp = requests.get(api_url, timeout=90)
        if resp.status_code != 200:
            print(f"    [ScraperAPI] HTTP {resp.status_code} for {url}")
            return None
        if len(resp.text) < 500 or "access denied" in resp.text.lower():
            print(f"    [ScraperAPI] Blocked/empty for {url}")
            return None
        return resp.text
    except Exception as e:
        print(f"    [ScraperAPI] Error for {url}: {e}")
        return None


def _parse_abbreviated_number(text: str) -> int | None:
    """
    Convert abbreviated number strings to integers.
    Examples: "1.2M" → 1200000, "450K" → 450000, "3,200" → 3200, "1.5B" → 1500000000
    """
    if not text:
        return None
    text = text.strip().replace(",", "").replace(" ", "")
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    m = re.match(r'^([\d.]+)\s*([KMBkmb])?$', text)
    if not m:
        return None
    num = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    if suffix in multipliers:
        num *= multipliers[suffix]
    return int(num)


# ---------------------------------------------------------------------------
# Thunderbit AI extraction
# ---------------------------------------------------------------------------

def _thunderbit_extract(url: str, schema: dict, api_key: str) -> dict | None:
    """
    Extract structured data from a URL using Thunderbit AI extraction.
    Retries up to _THUNDERBIT_MAX_RETRIES times with backoff on failure.
    Returns the extracted data dict or None.
    """
    payload = {
        "url": url,
        "schema": schema,
    }

    for attempt in range(1, _THUNDERBIT_MAX_RETRIES + 1):
        try:
            resp = requests.post(
                THUNDERBIT_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=90,
            )

            if resp.status_code != 200:
                body = resp.text[:300] if resp.text else "(empty)"
                print(f"    [Thunderbit] Attempt {attempt}/{_THUNDERBIT_MAX_RETRIES} HTTP {resp.status_code} for {url}: {body}")
                if attempt < _THUNDERBIT_MAX_RETRIES:
                    time.sleep(_THUNDERBIT_RETRY_DELAY)
                continue

            result = resp.json()
            if result.get("success"):
                data = result.get("data", {}).get("extract")
                if data:
                    return data
                print(f"    [Thunderbit] Empty extract for {url}")
                return None

            print(f"    [Thunderbit] API returned success=false for {url}: {result.get('error', 'unknown')}")
            return None

        except Exception as e:
            print(f"    [Thunderbit] Attempt {attempt}/{_THUNDERBIT_MAX_RETRIES} failed for {url}: {e}")
            if attempt < _THUNDERBIT_MAX_RETRIES:
                time.sleep(_THUNDERBIT_RETRY_DELAY)

    return None


# ---------------------------------------------------------------------------
# YouTube helpers
# ---------------------------------------------------------------------------

def _yt_get(endpoint: str, params: dict, api_key: str) -> dict:
    """Make a GET request to the YouTube Data API and return parsed JSON."""
    params["key"] = api_key
    url = f"{YOUTUBE_API_BASE}/{endpoint}?{urlencode(params)}"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_youtube_stats(competitor_name: str, query: str, api_key: str) -> dict | None:
    """
    Search for the competitor's YouTube channel and return subscriber count + recent videos.
    """
    try:
        search_data = _yt_get(
            "search",
            {"part": "snippet", "q": query, "type": "channel", "maxResults": 3},
            api_key,
        )
        items = search_data.get("items", [])
        if not items:
            return None

        channel_id = None
        channel_title = None
        for item in items:
            snippet = item.get("snippet", {})
            title = snippet.get("channelTitle", "")
            ch_id = item.get("id", {}).get("channelId")
            if not ch_id:
                continue
            if competitor_name.lower().split()[0] in title.lower():
                channel_id = ch_id
                channel_title = title
                break
        if not channel_id:
            ch = items[0]
            channel_id = ch.get("id", {}).get("channelId")
            channel_title = ch.get("snippet", {}).get("channelTitle", "")

        if not channel_id:
            return None

        stats_data = _yt_get(
            "channels",
            {"part": "statistics,snippet", "id": channel_id},
            api_key,
        )
        stat_items = stats_data.get("items", [])
        if not stat_items:
            return None

        stats = stat_items[0].get("statistics", {})
        subscribers = int(stats.get("subscriberCount", 0) or 0)

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        videos_data = _yt_get(
            "search",
            {
                "part": "snippet",
                "channelId": channel_id,
                "type": "video",
                "order": "date",
                "publishedAfter": cutoff,
                "maxResults": 50,
            },
            api_key,
        )
        video_items = videos_data.get("items", [])
        videos_last_7d = len(video_items)

        latest_video_url = None
        if video_items:
            vid_id = video_items[0].get("id", {}).get("videoId")
            if vid_id:
                latest_video_url = f"https://www.youtube.com/watch?v={vid_id}"

        return {
            "subscribers": subscribers,
            "videos_last_7d": videos_last_7d,
            "latest_video_url": latest_video_url,
        }

    except URLError as e:
        print(f"    [YouTube] Network error for {competitor_name}: {e}")
    except Exception as e:
        print(f"    [YouTube] Error for {competitor_name}: {e}")
    return None


# ---------------------------------------------------------------------------
# Facebook
# ---------------------------------------------------------------------------
# Phase 1: Facebook moved to scrapers/apify_social.py (D-01).
# That scraper runs as its own subprocess via scrapers/run_all.py SCRIPTS list.
# DO NOT re-add Thunderbit FB calls here — apify_social.py is the single
# authoritative writer for facebook_* social_snapshots rows.


# ---------------------------------------------------------------------------
# Instagram — legacy (ScraperAPI + regex fallback)
# ---------------------------------------------------------------------------

def _fetch_instagram_legacy(handle: str, api_key: str) -> dict | None:
    """Scrape Instagram profile follower count via ScraperAPI regex. Legacy fallback."""
    url = f"https://www.instagram.com/{handle}/"
    html = _fetch_via_scraperapi(url, api_key, render=True, premium=True)
    if not html:
        return None

    followers = None
    m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:description"', html, re.IGNORECASE)
    if m:
        desc = m.group(1)
        fm = re.search(r'([\d,.]+[KMB]?)\s+Followers', desc, re.IGNORECASE)
        if fm:
            followers = _parse_abbreviated_number(fm.group(1))
    if not followers:
        m = re.search(r'"userInteractionCount"\s*:\s*"?(\d+)"?', html)
        if m:
            followers = int(m.group(1))
    if not followers:
        m = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)\}', html)
        if m:
            followers = int(m.group(1))
    if not followers:
        return None
    return {"followers": followers}


def fetch_instagram_stats(handle: str, scraperapi_key: str | None, thunderbit_key: str | None) -> dict | None:
    """Fetch Instagram stats. Tries Thunderbit AI extraction first, falls back to ScraperAPI regex."""
    if thunderbit_key:
        url = f"https://www.instagram.com/{handle}/"
        result = _thunderbit_extract(url, _IG_SCHEMA, thunderbit_key)
        if result and result.get("followers"):
            followers = int(result["followers"])
            data = {"followers": followers}
            if result.get("posts_count") is not None:
                data["posts_count"] = int(result["posts_count"])
            if result.get("is_verified") is not None:
                data["is_verified"] = result["is_verified"]
            print(f"    [Thunderbit] Instagram OK")
            return data

        print(f"    [Thunderbit] Instagram failed, trying ScraperAPI fallback...")

    if scraperapi_key:
        return _fetch_instagram_legacy(handle, scraperapi_key)
    return None


# ---------------------------------------------------------------------------
# X (Twitter) — legacy (ScraperAPI + regex fallback)
# ---------------------------------------------------------------------------

def _fetch_x_legacy(handle: str, api_key: str) -> dict | None:
    """Get X/Twitter follower count via ScraperAPI regex. Legacy fallback."""
    url = f"https://x.com/{handle}"
    html = _fetch_via_scraperapi(url, api_key, render=True, premium=True)
    if not html:
        return None

    followers = None
    m = re.search(r'([\d,.]+[KMB]?)\s+Followers', html, re.IGNORECASE)
    if m:
        followers = _parse_abbreviated_number(m.group(1))
    if not followers:
        m = re.search(r'"followers_count"\s*:\s*(\d+)', html)
        if m:
            followers = int(m.group(1))
    if not followers:
        return None
    return {"followers": followers}


def fetch_x_stats(handle: str, scraperapi_key: str | None, thunderbit_key: str | None) -> dict | None:
    """Fetch X/Twitter stats. Tries Thunderbit AI extraction first, falls back to ScraperAPI regex."""
    if thunderbit_key:
        url = f"https://x.com/{handle}"
        result = _thunderbit_extract(url, _X_SCHEMA, thunderbit_key)
        if result and result.get("followers"):
            followers = int(result["followers"])
            data = {"followers": followers}
            if result.get("posts_count") is not None:
                data["posts_count"] = int(result["posts_count"])
            if result.get("is_verified") is not None:
                data["is_verified"] = result["is_verified"]
            print(f"    [Thunderbit] X OK")
            return data

        print(f"    [Thunderbit] X failed, trying ScraperAPI fallback...")

    if scraperapi_key:
        return _fetch_x_legacy(handle, scraperapi_key)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _upsert_social(conn, cid: str, platform: str, snapshot_date: str,
                    followers: int, posts_last_7d: int | None = None,
                    engagement_rate: float | None = None, latest_post_url: str | None = None,
                    market_code: str = "global"):
    """Delete + insert a social snapshot row and trigger change detection."""
    conn.execute(
        "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? AND market_code=? AND snapshot_date=?",
        (cid, platform, market_code, snapshot_date),
    )
    conn.execute(
        """
        INSERT INTO social_snapshots
            (competitor_id, platform, snapshot_date, followers,
             posts_last_7d, engagement_rate, latest_post_url, market_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cid, platform, snapshot_date, followers, posts_last_7d, engagement_rate, latest_post_url, market_code),
    )
    conn.commit()
    # Per-market change detection — fold market into the field name so SG vs global
    # follower swings stay distinct in the change feed.
    field_suffix = "" if market_code == "global" else f"_{market_code}"
    detect_change(conn, cid, f"social_{platform}", f"followers{field_suffix}", str(followers), "low")


def get_market_social_handles(competitor: dict) -> dict[str, dict]:
    """
    Returns {market_code: {handle_key: value}} for every market that has a
    social handle override that differs from the competitor's global handle.
    Always includes a "global" entry with the default handles.

    A competitor with no overrides returns just {"global": {...}}.
    """
    from market_config import PRIORITY_MARKETS

    global_handles = {
        "facebook_slug": competitor.get("facebook_slug"),
        "instagram_handle": competitor.get("instagram_handle"),
        "x_handle": competitor.get("x_handle"),
        "youtube_query": competitor.get("youtube_query"),
    }
    out: dict[str, dict] = {"global": global_handles}

    market_config = competitor.get("market_config") or {}
    if isinstance(market_config, str):
        try:
            market_config = json.loads(market_config)
        except Exception:
            market_config = {}

    for market in PRIORITY_MARKETS:
        cfg = market_config.get(market) or {}
        per_market: dict[str, str] = {}
        for key in ("facebook_slug", "instagram_handle", "x_handle", "youtube_query"):
            override = cfg.get(key)
            if override and override != global_handles.get(key):
                per_market[key] = override
        if per_market:
            out[market] = per_market

    return out


async def scrape_all():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    scraperapi_key = os.environ.get("SCRAPERAPI_KEY")
    thunderbit_key = os.environ.get("THUNDERBIT_API_KEY")

    if not api_key:
        print("WARNING: YOUTUBE_API_KEY not set. YouTube scraping will be skipped.")
    if thunderbit_key:
        print("Thunderbit API key found — will use AI extraction for FB/IG/X.")
    else:
        print("WARNING: THUNDERBIT_API_KEY not set. Will use ScraperAPI regex only.")
    if not scraperapi_key:
        print("WARNING: SCRAPERAPI_KEY not set. Facebook/Instagram/X scraping will be limited.")

    # Filter to single broker if --broker flag provided
    brokers = COMPETITORS
    if "--broker" in sys.argv:
        idx = sys.argv.index("--broker")
        if idx + 1 < len(sys.argv):
            broker_id = sys.argv[idx + 1]
            brokers = [c for c in COMPETITORS if c["id"] == broker_id]
            if not brokers:
                print(f"ERROR: Broker '{broker_id}' not found in config.")
                return

    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    conn = get_db()
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for competitor in brokers:
        cid = competitor["id"]
        name = competitor["name"]

        # Build per-market handle map. Always has a "global" entry; only adds per-market
        # entries when an override differs from global, so we don't duplicate-scrape.
        markets_handles = get_market_social_handles(competitor)

        print(f"\nProcessing {name} ({len(markets_handles)} market{'s' if len(markets_handles) != 1 else ''})...")

        for market_code, handles in markets_handles.items():
            yt_query = handles.get("youtube_query") or f"{name} trading"
            fb_slug = handles.get("facebook_slug")
            ig_handle = handles.get("instagram_handle")
            x_handle = handles.get("x_handle")

            market_label = "" if market_code == "global" else f" [{market_code}]"

            # --- YouTube ---
            if api_key and yt_query:
                try:
                    yt = fetch_youtube_stats(name, yt_query, api_key)
                    if yt:
                        _upsert_social(
                            conn, cid, "youtube", snapshot_date,
                            yt["subscribers"],
                            posts_last_7d=yt["videos_last_7d"],
                            latest_post_url=yt["latest_video_url"],
                            market_code=market_code,
                        )
                        total_records += 1
                        print(f"  ✓ YouTube{market_label}: {yt['subscribers']:,} subs | {yt['videos_last_7d']} videos last 7d")
                    else:
                        print(f"  ✗ YouTube{market_label}: no channel found")
                except Exception as e:
                    msg = f"{name} youtube{market_label}: {e}"
                    print(f"  ✗ YouTube{market_label}: {e}")
                    error_summary.append(msg)

                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

            # --- Facebook ---
            # Phase 1: Facebook moved to scrapers/apify_social.py (D-01).
            # That scraper runs as its own subprocess via scrapers/run_all.py SCRIPTS list.
            # This branch intentionally left empty — DO NOT re-add Thunderbit FB calls here.
            _ = fb_slug  # keep the unpack above honest (variable still derived for IG/X siblings)

            # --- Instagram ---
            if ig_handle and (thunderbit_key or scraperapi_key):
                try:
                    ig = fetch_instagram_stats(ig_handle, scraperapi_key, thunderbit_key)
                    if ig:
                        _upsert_social(conn, cid, "instagram", snapshot_date,
                                       ig["followers"], posts_last_7d=ig.get("posts_count"),
                                       market_code=market_code)
                        total_records += 1
                        extra = f" | {ig['posts_count']} posts" if ig.get("posts_count") is not None else ""
                        print(f"  ✓ Instagram{market_label}: {ig['followers']:,} followers{extra}")
                    else:
                        print(f"  ✗ Instagram{market_label}: could not extract follower count")
                except Exception as e:
                    msg = f"{name} instagram{market_label}: {e}"
                    print(f"  ✗ Instagram{market_label}: {e}")
                    error_summary.append(msg)

                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

            # --- X (Twitter) ---
            if x_handle and (thunderbit_key or scraperapi_key):
                try:
                    x = fetch_x_stats(x_handle, scraperapi_key, thunderbit_key)
                    if x:
                        _upsert_social(conn, cid, "x", snapshot_date,
                                       x["followers"], posts_last_7d=x.get("posts_count"),
                                       market_code=market_code)
                        total_records += 1
                        extra = f" | {x['posts_count']} posts" if x.get("posts_count") is not None else ""
                        print(f"  ✓ X{market_label}: {x['followers']:,} followers{extra}")
                    else:
                        print(f"  ✗ X{market_label}: could not extract follower count")
                except Exception as e:
                    msg = f"{name} x{market_label}: {e}"
                    print(f"  ✗ X{market_label}: {e}")
                    error_summary.append(msg)

                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    conn.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records written: {total_records}. Status: {status}")


if __name__ == "__main__":
    asyncio.run(scrape_all())

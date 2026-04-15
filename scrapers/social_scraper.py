"""
social_scraper.py
-----------------
Social media scraper for competitor follower counts:
  - YouTube: YouTube Data API v3 (channel search + subscriber count + recent videos)
  - Facebook, Instagram, X: Thunderbit AI extraction (primary), ScraperAPI regex (fallback)

Requires environment variables:
  YOUTUBE_API_KEY      – for YouTube Data API
  THUNDERBIT_API_KEY   – for AI-powered social extraction (Facebook, Instagram, X)
  SCRAPERAPI_KEY       – fallback for Facebook, Instagram, X scraping

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

# --- Thunderbit JSON schemas for each platform ---
_FB_SCHEMA = {
    "type": "object",
    "properties": {
        "followers": {"type": "number", "description": "Total number of followers or people who follow this page"},
        "likes": {"type": "number", "description": "Total number of page likes"},
        "posts_last_7d": {"type": "number", "description": "Number of posts visible on the page published in the last 7 days"},
    },
}

_IG_SCHEMA = {
    "type": "object",
    "properties": {
        "followers": {"type": "number", "description": "Total number of followers"},
        "following": {"type": "number", "description": "Number of accounts this profile follows"},
        "posts_count": {"type": "number", "description": "Total number of posts"},
        "is_verified": {"type": "boolean", "description": "Whether the account is verified"},
    },
}

_X_SCHEMA = {
    "type": "object",
    "properties": {
        "followers": {"type": "number", "description": "Total number of followers"},
        "following": {"type": "number", "description": "Number of accounts this profile follows"},
        "posts_count": {"type": "number", "description": "Total number of posts or tweets"},
        "is_verified": {"type": "boolean", "description": "Whether the account is verified"},
    },
}

_THUNDERBIT_MAX_RETRIES = 2
_THUNDERBIT_RETRY_DELAY = 5  # seconds

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fetch_via_scraperapi(url: str, api_key: str, render: bool = True, premium: bool = False) -> str | None:
    """Fetch a URL through ScraperAPI. Returns HTML string or None on failure."""
    api_url = (
        f"http://api.scraperapi.com"
        f"?api_key={api_key}"
        f"&url={url}"
        f"&render={'true' if render else 'false'}"
        f"&country_code=my"
    )
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
        "timeout": 45000,
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
# Facebook — legacy (ScraperAPI + regex fallback)
# ---------------------------------------------------------------------------

def _fetch_facebook_legacy(page_slug: str, api_key: str) -> dict | None:
    """Scrape Facebook page follower count via ScraperAPI regex. Legacy fallback."""
    url = f"https://www.facebook.com/{page_slug}"
    html = _fetch_via_scraperapi(url, api_key, render=True, premium=True)
    if not html:
        return None

    followers = None
    m = re.search(r'([\d,.\s]+[KMB]?)\s+(?:people\s+)?follow', html, re.IGNORECASE)
    if m:
        followers = _parse_abbreviated_number(m.group(1))
    if not followers:
        m = re.search(r'"follower_count"\s*:\s*(\d+)', html)
        if m:
            followers = int(m.group(1))
    if not followers:
        m = re.search(r'([\d,.\s]+[KMB]?)\s+(?:people\s+)?like', html, re.IGNORECASE)
        if m:
            followers = _parse_abbreviated_number(m.group(1))
    if not followers:
        return None
    return {"followers": followers}


def fetch_facebook_stats(page_slug: str, scraperapi_key: str | None, thunderbit_key: str | None) -> dict | None:
    """Fetch Facebook stats. Tries Thunderbit AI extraction first, falls back to ScraperAPI regex."""
    if thunderbit_key:
        url = f"https://www.facebook.com/{page_slug}"
        result = _thunderbit_extract(url, _FB_SCHEMA, thunderbit_key)
        if result and result.get("followers"):
            followers = int(result["followers"])
            data = {"followers": followers}
            if result.get("likes"):
                data["likes"] = int(result["likes"])
            if result.get("posts_last_7d") is not None:
                data["posts_last_7d"] = int(result["posts_last_7d"])
            print(f"    [Thunderbit] Facebook OK")
            return data

        print(f"    [Thunderbit] Facebook failed, trying ScraperAPI fallback...")

    if scraperapi_key:
        return _fetch_facebook_legacy(page_slug, scraperapi_key)
    return None


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
                    engagement_rate: float | None = None, latest_post_url: str | None = None):
    """Delete + insert a social snapshot row and trigger change detection."""
    conn.execute(
        "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? AND snapshot_date=?",
        (cid, platform, snapshot_date),
    )
    conn.execute(
        """
        INSERT INTO social_snapshots
            (competitor_id, platform, snapshot_date, followers,
             posts_last_7d, engagement_rate, latest_post_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (cid, platform, snapshot_date, followers, posts_last_7d, engagement_rate, latest_post_url),
    )
    conn.commit()
    detect_change(conn, cid, f"social_{platform}", "followers", str(followers), "low")


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
        yt_query = competitor.get("youtube_query", f"{name} trading")
        fb_slug = competitor.get("facebook_slug")
        ig_handle = competitor.get("instagram_handle")
        x_handle = competitor.get("x_handle")

        print(f"\nProcessing {name}...")

        # --- YouTube ---
        if api_key:
            try:
                yt = fetch_youtube_stats(name, yt_query, api_key)
                if yt:
                    conn.execute(
                        "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? AND snapshot_date=?",
                        (cid, "youtube", snapshot_date),
                    )
                    conn.execute(
                        """
                        INSERT INTO social_snapshots
                            (competitor_id, platform, snapshot_date, followers,
                             posts_last_7d, engagement_rate, latest_post_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (cid, "youtube", snapshot_date, yt["subscribers"],
                         yt["videos_last_7d"], None, yt["latest_video_url"]),
                    )
                    conn.commit()
                    total_records += 1
                    detect_change(conn, cid, "social_youtube", "subscribers", str(yt["subscribers"]), "low")
                    print(f"  ✓ YouTube: {yt['subscribers']:,} subs | {yt['videos_last_7d']} videos last 7d")
                else:
                    print(f"  ✗ YouTube: no channel found")
            except Exception as e:
                msg = f"{name} youtube: {e}"
                print(f"  ✗ YouTube: {e}")
                error_summary.append(msg)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        # --- Facebook ---
        if fb_slug and (thunderbit_key or scraperapi_key):
            try:
                fb = fetch_facebook_stats(fb_slug, scraperapi_key, thunderbit_key)
                if fb:
                    _upsert_social(conn, cid, "facebook", snapshot_date,
                                   fb["followers"], posts_last_7d=fb.get("posts_last_7d"))
                    total_records += 1
                    extra = f" | {fb['posts_last_7d']} posts/7d" if fb.get("posts_last_7d") is not None else ""
                    print(f"  ✓ Facebook: {fb['followers']:,} followers{extra}")
                else:
                    print(f"  ✗ Facebook: could not extract follower count")
            except Exception as e:
                msg = f"{name} facebook: {e}"
                print(f"  ✗ Facebook: {e}")
                error_summary.append(msg)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        # --- Instagram ---
        if ig_handle and (thunderbit_key or scraperapi_key):
            try:
                ig = fetch_instagram_stats(ig_handle, scraperapi_key, thunderbit_key)
                if ig:
                    _upsert_social(conn, cid, "instagram", snapshot_date,
                                   ig["followers"], posts_last_7d=ig.get("posts_count"))
                    total_records += 1
                    extra = f" | {ig['posts_count']} posts" if ig.get("posts_count") is not None else ""
                    print(f"  ✓ Instagram: {ig['followers']:,} followers{extra}")
                else:
                    print(f"  ✗ Instagram: could not extract follower count")
            except Exception as e:
                msg = f"{name} instagram: {e}"
                print(f"  ✗ Instagram: {e}")
                error_summary.append(msg)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        # --- X (Twitter) ---
        if x_handle and (thunderbit_key or scraperapi_key):
            try:
                x = fetch_x_stats(x_handle, scraperapi_key, thunderbit_key)
                if x:
                    _upsert_social(conn, cid, "x", snapshot_date,
                                   x["followers"], posts_last_7d=x.get("posts_count"))
                    total_records += 1
                    extra = f" | {x['posts_count']} posts" if x.get("posts_count") is not None else ""
                    print(f"  ✓ X: {x['followers']:,} followers{extra}")
                else:
                    print(f"  ✗ X: could not extract follower count")
            except Exception as e:
                msg = f"{name} x: {e}"
                print(f"  ✗ X: {e}")
                error_summary.append(msg)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    conn.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records written: {total_records}. Status: {status}")


if __name__ == "__main__":
    asyncio.run(scrape_all())

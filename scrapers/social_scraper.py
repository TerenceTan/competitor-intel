"""
social_scraper.py
-----------------
Social media scraper for competitor follower counts:
  - YouTube: YouTube Data API v3 (channel search + subscriber count + recent videos)
  - Facebook: ScraperAPI render=true (public page follower count)
  - Instagram: ScraperAPI render=true (profile follower count from og:description)
  - X (Twitter): ScraperAPI render=true

Requires environment variables:
  YOUTUBE_API_KEY   – for YouTube Data API
  SCRAPERAPI_KEY    – for Facebook, Instagram, X scraping

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

def fetch_facebook_stats(page_slug: str, api_key: str) -> dict | None:
    """
    Scrape Facebook page follower count via ScraperAPI render=true.
    Returns {"followers": int} or None.
    """
    url = f"https://www.facebook.com/{page_slug}"
    html = _fetch_via_scraperapi(url, api_key, render=True, premium=True)
    if not html:
        return None

    followers = None

    # Pattern 1: "X people follow this" or "X followers"
    m = re.search(r'([\d,.\s]+[KMB]?)\s+(?:people\s+)?follow', html, re.IGNORECASE)
    if m:
        followers = _parse_abbreviated_number(m.group(1))

    # Pattern 2: JSON "follower_count": 12345
    if not followers:
        m = re.search(r'"follower_count"\s*:\s*(\d+)', html)
        if m:
            followers = int(m.group(1))

    # Pattern 3: "X likes" as fallback (page likes ≈ followers)
    if not followers:
        m = re.search(r'([\d,.\s]+[KMB]?)\s+(?:people\s+)?like', html, re.IGNORECASE)
        if m:
            followers = _parse_abbreviated_number(m.group(1))

    if not followers:
        return None

    return {"followers": followers}


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------

def fetch_instagram_stats(handle: str, api_key: str) -> dict | None:
    """
    Scrape Instagram profile follower count via ScraperAPI render=true.
    Returns {"followers": int} or None.
    """
    url = f"https://www.instagram.com/{handle}/"
    html = _fetch_via_scraperapi(url, api_key, render=True, premium=True)
    if not html:
        return None

    followers = None

    # Pattern 1: og:description meta — "123K Followers, 500 Following, 200 Posts"
    m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html, re.IGNORECASE)
    if not m:
        m = re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:description"', html, re.IGNORECASE)
    if m:
        desc = m.group(1)
        fm = re.search(r'([\d,.]+[KMB]?)\s+Followers', desc, re.IGNORECASE)
        if fm:
            followers = _parse_abbreviated_number(fm.group(1))

    # Pattern 2: JSON interactionStatistic
    if not followers:
        m = re.search(r'"userInteractionCount"\s*:\s*"?(\d+)"?', html)
        if m:
            followers = int(m.group(1))

    # Pattern 3: edge_followed_by count
    if not followers:
        m = re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)\}', html)
        if m:
            followers = int(m.group(1))

    if not followers:
        return None

    return {"followers": followers}


# ---------------------------------------------------------------------------
# X (Twitter) — ScraperAPI render=true
# ---------------------------------------------------------------------------

def fetch_x_stats(handle: str, api_key: str | None) -> dict | None:
    """
    Get X/Twitter follower count via ScraperAPI render=true.
    Returns {"followers": int} or None.
    """
    if not api_key:
        return None
    url = f"https://x.com/{handle}"
    html = _fetch_via_scraperapi(url, api_key, render=True, premium=True)
    if not html:
        return None

    followers = None

    # Pattern 1: "X Followers" text
    m = re.search(r'([\d,.]+[KMB]?)\s+Followers', html, re.IGNORECASE)
    if m:
        followers = _parse_abbreviated_number(m.group(1))

    # Pattern 2: JSON data
    if not followers:
        m = re.search(r'"followers_count"\s*:\s*(\d+)', html)
        if m:
            followers = int(m.group(1))

    if not followers:
        return None

    return {"followers": followers}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _upsert_social(conn, cid: str, platform: str, snapshot_date: str, followers: int):
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
        (cid, platform, snapshot_date, followers, None, None, None),
    )
    conn.commit()
    detect_change(conn, cid, f"social_{platform}", "followers", str(followers), "low")


async def scrape_all():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    scraperapi_key = os.environ.get("SCRAPERAPI_KEY")

    if not api_key:
        print("WARNING: YOUTUBE_API_KEY not set. YouTube scraping will be skipped.")
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
        if fb_slug and scraperapi_key:
            try:
                fb = fetch_facebook_stats(fb_slug, scraperapi_key)
                if fb:
                    _upsert_social(conn, cid, "facebook", snapshot_date, fb["followers"])
                    total_records += 1
                    print(f"  ✓ Facebook: {fb['followers']:,} followers")
                else:
                    print(f"  ✗ Facebook: could not extract follower count")
            except Exception as e:
                msg = f"{name} facebook: {e}"
                print(f"  ✗ Facebook: {e}")
                error_summary.append(msg)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        # --- Instagram ---
        if ig_handle and scraperapi_key:
            try:
                ig = fetch_instagram_stats(ig_handle, scraperapi_key)
                if ig:
                    _upsert_social(conn, cid, "instagram", snapshot_date, ig["followers"])
                    total_records += 1
                    print(f"  ✓ Instagram: {ig['followers']:,} followers")
                else:
                    print(f"  ✗ Instagram: could not extract follower count")
            except Exception as e:
                msg = f"{name} instagram: {e}"
                print(f"  ✗ Instagram: {e}")
                error_summary.append(msg)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        # --- X (Twitter) ---
        if x_handle:
            try:
                x = fetch_x_stats(x_handle, scraperapi_key)
                if x:
                    _upsert_social(conn, cid, "x", snapshot_date, x["followers"])
                    total_records += 1
                    print(f"  ✓ X: {x['followers']:,} followers")
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

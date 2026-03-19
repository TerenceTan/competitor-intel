"""
social_scraper.py
-----------------
Lightweight social media scraper:
  - YouTube: uses YouTube Data API v3 to find competitor channels and
    fetch subscriber count + latest video count (last 7 days).
  - Telegram: uses Playwright to scrape public channel pages at t.me/s/<handle>
    if a handle is configured.

Requires environment variable: YOUTUBE_API_KEY

Run from the project root:
    YOUTUBE_API_KEY=your_key python scrapers/social_scraper.py
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

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from dotenv import load_dotenv

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import ALL_BROKERS as COMPETITORS, DELAY_BETWEEN_REQUESTS, SCRAPER_UA
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change

SCRAPER_NAME = "social_scraper"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


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
    Search for the competitor's YouTube channel and return a dict with:
      channel_id, channel_title, subscribers, videos_last_7d,
      latest_video_url, engagement_rate (None – not available without OAuth)
    Returns None on failure.
    """
    try:
        # Step 1: Search for channel
        search_data = _yt_get(
            "search",
            {
                "part": "snippet",
                "q": query,
                "type": "channel",
                "maxResults": 3,
            },
            api_key,
        )
        items = search_data.get("items", [])
        if not items:
            return None

        # Pick the best match: prefer exact name match
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
            # Fall back to first result
            ch = items[0]
            channel_id = ch.get("id", {}).get("channelId")
            channel_title = ch.get("snippet", {}).get("channelTitle", "")

        if not channel_id:
            return None

        # Step 2: Get channel statistics
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

        # Step 3: Count videos uploaded in last 7 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
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
            "channel_id": channel_id,
            "channel_title": channel_title,
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
# Telegram helpers
# ---------------------------------------------------------------------------

async def fetch_telegram_stats(page, handle: str) -> dict | None:
    """
    Scrape a public Telegram channel at t.me/s/<handle>.
    Returns dict with followers (members), posts_last_7d, latest_post_url.
    """
    url = f"https://t.me/s/{handle}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await asyncio.sleep(2)

        html = await page.content()

        # Member count: often in .tgme_page_extra or similar
        followers = None
        m = re.search(r'([\d\s,]+)\s+(?:members?|subscribers?)', html, re.IGNORECASE)
        if m:
            followers = int(re.sub(r'[^\d]', '', m.group(1)))

        # Count posts in last 7 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        # Posts often have datetime attributes
        dates = re.findall(r'datetime="([^"]+)"', html)
        posts_last_7d = 0
        latest_post_url = None
        for d in dates:
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
                if dt >= cutoff:
                    posts_last_7d += 1
            except ValueError:
                continue

        # Latest post URL
        post_links = re.findall(rf't\.me/{re.escape(handle)}/(\d+)', html)
        if post_links:
            latest_num = max(int(n) for n in post_links)
            latest_post_url = f"https://t.me/{handle}/{latest_num}"

        return {
            "followers": followers,
            "posts_last_7d": posts_last_7d,
            "latest_post_url": latest_post_url,
        }

    except PlaywrightTimeout:
        print(f"    [Telegram] Timeout for {handle}")
    except Exception as e:
        print(f"    [Telegram] Error for {handle}: {e}")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def scrape_all():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("WARNING: YOUTUBE_API_KEY not set. YouTube scraping will be skipped.")

    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=SCRAPER_UA,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        conn = get_db()
        snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for competitor in COMPETITORS:
            cid = competitor["id"]
            name = competitor["name"]
            yt_query = competitor.get("youtube_query", f"{name} trading")
            tg_handle = competitor.get("telegram_handle")

            print(f"Processing {name}...")

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
                            (
                                cid, "youtube", snapshot_date,
                                yt["subscribers"],
                                yt["videos_last_7d"],
                                None,  # engagement_rate not available without OAuth
                                yt["latest_video_url"],
                            ),
                        )
                        conn.commit()
                        total_records += 1
                        detect_change(
                            conn, cid, "social_youtube", "subscribers",
                            str(yt["subscribers"]), "low"
                        )
                        print(
                            f"    YouTube: {yt['subscribers']:,} subs | "
                            f"{yt['videos_last_7d']} videos last 7d"
                        )
                    else:
                        print(f"    YouTube: no channel found")
                except Exception as e:
                    msg = f"{name} youtube: {e}"
                    print(f"    [YouTube] Error: {e}")
                    error_summary.append(msg)

                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

            # --- Telegram ---
            if tg_handle:
                try:
                    tg = await fetch_telegram_stats(page, tg_handle)
                    if tg:
                        conn.execute(
                            "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? AND snapshot_date=?",
                            (cid, "telegram", snapshot_date),
                        )
                        conn.execute(
                            """
                            INSERT INTO social_snapshots
                                (competitor_id, platform, snapshot_date, followers,
                                 posts_last_7d, engagement_rate, latest_post_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                cid, "telegram", snapshot_date,
                                tg["followers"],
                                tg["posts_last_7d"],
                                None,
                                tg["latest_post_url"],
                            ),
                        )
                        conn.commit()
                        total_records += 1
                        if tg["followers"]:
                            detect_change(
                                conn, cid, "social_telegram", "followers",
                                str(tg["followers"]), "low"
                            )
                        print(
                            f"    Telegram: {tg['followers']} members | "
                            f"{tg['posts_last_7d']} posts last 7d"
                        )
                    else:
                        print(f"    Telegram: no data")
                except Exception as e:
                    msg = f"{name} telegram: {e}"
                    print(f"    [Telegram] Error: {e}")
                    error_summary.append(msg)

                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        conn.close()
        await browser.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records written: {total_records}. Status: {status}")


if __name__ == "__main__":
    asyncio.run(scrape_all())

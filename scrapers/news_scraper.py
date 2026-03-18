"""
news_scraper.py
---------------
Fetches Google News RSS for each competitor, parses items, runs sentiment
detection, and stores results in news_items (deduped by URL).

Run from the project root:
    python scrapers/news_scraper.py
"""

from __future__ import annotations

import os
import sys
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
from urllib.error import URLError
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import COMPETITORS, DELAY_BETWEEN_REQUESTS
from db_utils import get_db, log_scraper_run, update_scraper_run

SCRAPER_NAME = "news_scraper"

POSITIVE_KEYWORDS = [
    "launched", "launch", "record", "expands", "expansion", "growth",
    "award", "achieves", "achievement", "partnership", "wins", "winner",
    "milestone", "innovation", "approved", "license", "profit", "revenue",
    "new product", "collaboration", "deal", "agreement",
]

NEGATIVE_KEYWORDS = [
    "fine", "fined", "penalty", "penalised", "lawsuit", "sued", "suspended",
    "suspension", "fraud", "investigation", "warning", "regulatory action",
    "scam", "ban", "banned", "banning", "revoked", "revocation", "violation",
    "crackdown", "misconduct", "illegal", "complaint", "breach", "failure",
    "loss", "hack", "breach",
]


def detect_sentiment(text: str) -> str:
    lower = text.lower()
    pos_hits = sum(1 for kw in POSITIVE_KEYWORDS if kw in lower)
    neg_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in lower)
    if neg_hits > pos_hits:
        return "negative"
    elif pos_hits > neg_hits:
        return "positive"
    return "neutral"


def parse_rss_date(date_str: str) -> datetime | None:
    """Parse RFC 2822 date used in RSS feeds. Returns UTC-aware datetime or None."""
    if not date_str:
        return None
    # Try multiple formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    # Fallback: strip timezone name and try
    cleaned = re.sub(r'\s+[A-Z]{2,5}$', '', date_str.strip())
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt.replace(" %z", "").replace(" %Z", ""))
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def fetch_rss(competitor_name: str) -> list[dict]:
    """
    Fetch Google News RSS for competitor_name and return list of article dicts.
    Each dict: {title, url, source, published_at (ISO str), sentiment}
    Only returns articles from the last 7 days.
    """
    query = quote_plus(f"{competitor_name} forex")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; CompetitorIntelBot/1.0; "
            "+https://techaway.online)"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    articles = []

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=20) as resp:
            content = resp.read()

        root = ET.fromstring(content)
        channel = root.find("channel")
        if channel is None:
            return []

        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            source_el = item.find("source")

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            pub_text = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
            source = (
                source_el.text.strip()
                if source_el is not None and source_el.text
                else "Unknown"
            )

            # Google News links are redirect URLs; extract original if possible
            # (the raw link is sufficient for dedup)
            pub_dt = parse_rss_date(pub_text)
            if pub_dt and pub_dt < cutoff:
                continue  # Too old

            pub_iso = pub_dt.isoformat() if pub_dt else datetime.now(timezone.utc).isoformat()
            sentiment = detect_sentiment(title)

            articles.append(
                {
                    "title": title,
                    "url": link,
                    "source": source,
                    "published_at": pub_iso,
                    "sentiment": sentiment,
                }
            )

    except URLError as e:
        print(f"    [RSS] Network error for {competitor_name}: {e}")
    except ET.ParseError as e:
        print(f"    [RSS] XML parse error for {competitor_name}: {e}")
    except Exception as e:
        print(f"    [RSS] Unexpected error for {competitor_name}: {e}")

    return articles


def save_articles(conn, competitor_id: str, articles: list[dict]) -> int:
    """Insert articles that are not already in news_items. Returns count inserted."""
    inserted = 0
    for art in articles:
        if not art["url"]:
            continue
        existing = conn.execute(
            "SELECT 1 FROM news_items WHERE url = ?", (art["url"],)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """
            INSERT INTO news_items (competitor_id, title, url, source, published_at, sentiment)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                competitor_id,
                art["title"],
                art["url"],
                art["source"],
                art["published_at"],
                art["sentiment"],
            ),
        )
        inserted += 1
    conn.commit()
    return inserted


def run():
    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    conn = get_db()

    for competitor in COMPETITORS:
        cid = competitor["id"]
        name = competitor["name"]
        print(f"Processing {name}...")

        try:
            articles = fetch_rss(name)
            inserted = save_articles(conn, cid, articles)
            total_records += inserted
            print(f"    Found {len(articles)} articles, inserted {inserted} new.")
        except Exception as e:
            msg = f"{name}: {e}"
            print(f"    Error: {msg}")
            error_summary.append(msg)

        time.sleep(DELAY_BETWEEN_REQUESTS)

    conn.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records inserted: {total_records}. Status: {status}")


if __name__ == "__main__":
    run()

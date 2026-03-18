"""
wikifx_scraper.py
-----------------
Scrapes WikiFX broker profiles using curl-cffi (mimics Chrome TLS fingerprint
to bypass Sucuri/Cloudflare WAF that blocks headless Playwright).

Extracts: WikiFX score, account types table, marketing strategy, biz area tags.
Skips competitors where wikifx_id is None.

Run from the project root:
    python3 scrapers/wikifx_scraper.py

Requires:
    pip install curl-cffi
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import COMPETITORS, DELAY_BETWEEN_REQUESTS
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change

SCRAPER_NAME = "wikifx_scraper"

try:
    from curl_cffi import requests as curl_requests
    _CURL_AVAILABLE = True
except ImportError:
    _CURL_AVAILABLE = False
    import requests as std_requests
    print("WARNING: curl-cffi not installed. Falling back to requests (may be blocked by WAF).")
    print("         Install with: pip install curl-cffi")


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 30) -> tuple[int, str]:
    """
    Fetch a URL with Chrome-impersonation TLS fingerprint.
    Returns (status_code, html).
    """
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.wikifx.com/en/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Upgrade-Insecure-Requests": "1",
    }
    if _CURL_AVAILABLE:
        resp = curl_requests.get(
            url,
            headers=headers,
            impersonate="chrome120",  # mimics Chrome 120 TLS fingerprint
            timeout=timeout,
            allow_redirects=True,
        )
        return resp.status_code, resp.text
    else:
        resp = std_requests.get(url, headers=headers, timeout=timeout)
        return resp.status_code, resp.text


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_wikifx_score(html: str) -> float | None:
    """Try multiple patterns to extract the WikiFX numeric score."""
    # Pattern 1: JSON key variants
    for key in ("wikifxScore", "wikifx_score", "WikiFXScore", "score", "Score"):
        m = re.search(rf'"{key}"\s*:\s*"?(\d{{1,2}}(?:\.\d+)?)"?', html)
        if m:
            val = float(m.group(1))
            if 0 < val <= 10:
                return val

    # Pattern 2: standalone decimal in plausible score range near score keywords
    for m in re.finditer(r'(\d{1,2}\.\d{2})', html):
        val = float(m.group(1))
        if 5.0 <= val <= 10.0:
            ctx = html[max(0, m.start() - 300): m.start() + 100].lower()
            if any(kw in ctx for kw in ("score", "rating", "wikifx", "dealer", "regulatory")):
                return val

    return None


def _extract_biz_area(html: str) -> list[str]:
    """Extract business area tag text."""
    areas: list[str] = []
    m = re.search(
        r'(?:Business Area|Biz Area)[^<]{0,600}'
        r'((?:<(?:span|div|li|a|td)[^>]*>[^<]{2,40}</(?:span|div|li|a|td)>\s*){1,20})',
        html, re.IGNORECASE | re.DOTALL,
    )
    if m:
        for tag_text in re.findall(r'>([A-Za-z][A-Za-z0-9\s&/()\-]{1,35})</', m.group(1)):
            t = tag_text.strip()
            if t and t not in areas:
                areas.append(t)
    return areas


def _extract_marketing_strategy(html: str) -> list[dict]:
    """Extract marketing strategy list items."""
    items: list[dict] = []
    m = re.search(
        r'Marketing Strategy([\s\S]{0,5000}?)'
        r'(?:WikiFX Score|Regulatory|Account Type|<section|</section|Biz Area|</div>\s*</div>)',
        html, re.IGNORECASE,
    )
    if not m:
        return items
    section = m.group(1)
    entries = re.findall(r'<li[^>]*>([\s\S]*?)</li>', section, re.IGNORECASE)
    if not entries:
        entries = re.findall(r'<p[^>]*>([\s\S]*?)</p>', section, re.IGNORECASE)
    for entry in entries:
        text = re.sub(r'<[^>]+>', '', entry).strip()
        text = re.sub(r'\s+', ' ', text)
        if 5 < len(text) < 500:
            items.append({"title": text, "description": ""})
    return items


def _extract_accounts_from_html(html: str) -> list[dict]:
    """Parse account table rows from raw HTML."""
    accounts: list[dict] = []
    # Find all <table> blocks
    for table_match in re.finditer(r'<table[^>]*>([\s\S]*?)</table>', html, re.IGNORECASE):
        table_html = table_match.group(1)
        rows = re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', table_html, re.IGNORECASE)
        if len(rows) < 2:
            continue
        # Extract cell text per row
        parsed = []
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>([\s\S]*?)</t[dh]>', row, re.IGNORECASE)
            cell_texts = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if cell_texts:
                parsed.append(cell_texts)

        if not parsed or len(parsed) < 2:
            continue

        header = [h.lower() for h in parsed[0]]
        # Only process if header looks like an account table
        account_keywords = ('account', 'spread', 'leverage', 'deposit', 'name')
        if not any(kw in ' '.join(header) for kw in account_keywords):
            continue

        col_map: dict[str, int] = {}
        for idx, h in enumerate(header):
            if 'account' in h or ('name' in h and 'account' in ' '.join(header)):
                col_map.setdefault('name', idx)
            elif 'spread' in h:
                col_map.setdefault('spread_from', idx)
            elif 'leverage' in h:
                col_map.setdefault('max_leverage', idx)
            elif 'deposit' in h:
                col_map.setdefault('min_deposit', idx)
            elif 'currency' in h:
                col_map.setdefault('currency', idx)
            elif 'instrument' in h or 'product' in h:
                col_map.setdefault('instruments', idx)

        for row in parsed[1:]:
            if not row or all(c == '' for c in row):
                continue
            acc: dict = {}
            for field, idx in col_map.items():
                if idx < len(row) and row[idx]:
                    acc[field] = row[idx]
            if acc:
                accounts.append(acc)

        if accounts:
            break  # use the first matching table

    return accounts


# ---------------------------------------------------------------------------
# Per-competitor scrape
# ---------------------------------------------------------------------------

def scrape_wikifx(competitor: dict) -> dict:
    """Fetch and parse one WikiFX dealer page. Returns extracted data dict."""
    wikifx_id = competitor.get("wikifx_id")
    name = competitor["name"]

    if not wikifx_id:
        print(f"  [{name}] wikifx_id is None — skipping")
        return {}

    url = f"https://www.wikifx.com/en/dealer/{wikifx_id}.html"
    print(f"  [{name}] Fetching {url}")

    try:
        status, html = _fetch(url)
    except Exception as e:
        print(f"  [{name}] Fetch error: {e}")
        return {}

    print(f"  [{name}] HTTP {status} | HTML length: {len(html)}")

    if status != 200:
        print(f"  [{name}] Non-200 response — skipping")
        return {}

    if "access denied" in html.lower() or len(html) < 1000:
        print(f"  [{name}] Access denied or empty page")
        # Show snippet for diagnosis
        print(f"  [{name}] Response: {html[:200]!r}")
        return {}

    # Debug: show a snippet near score-related keywords
    for kw in ("wikifxScore", "score", "Score"):
        idx = html.find(kw)
        if idx != -1:
            snippet = html[max(0, idx - 50): idx + 120].replace("\n", " ")
            print(f"  [{name}] Snippet near '{kw}': ...{snippet}...")
            break

    wikifx_score = _extract_wikifx_score(html)
    accounts = _extract_accounts_from_html(html)
    marketing_strategy = _extract_marketing_strategy(html)
    biz_area = _extract_biz_area(html)

    print(f"  [{name}] score={wikifx_score} | accounts={len(accounts)} | strategy={len(marketing_strategy)} | biz={biz_area}")

    return {
        "wikifx_score": wikifx_score,
        "accounts": accounts,
        "marketing_strategy": marketing_strategy,
        "biz_area": biz_area,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def scrape_all():
    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    conn = get_db()
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for competitor in COMPETITORS:
        cid = competitor["id"]
        name = competitor["name"]
        print(f"\nProcessing {name}...")

        if not competitor.get("wikifx_id"):
            print(f"  [{name}] No wikifx_id — skipping")
            continue

        try:
            data = scrape_wikifx(competitor)
        except Exception as e:
            msg = f"{name}: {e}"
            print(f"  Error: {msg}")
            error_summary.append(msg)
            data = {}

        if not data:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        wikifx_score = data.get("wikifx_score")
        accounts = data.get("accounts", [])
        marketing_strategy = data.get("marketing_strategy", [])
        biz_area = data.get("biz_area", [])

        has_data = (
            wikifx_score is not None
            or len(accounts) > 0
            or len(marketing_strategy) > 0
            or len(biz_area) > 0
        )

        if not has_data:
            print(f"  [{name}] No data extracted — skipping DB write")
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        try:
            conn.execute(
                "DELETE FROM wikifx_snapshots WHERE competitor_id=? AND snapshot_date=?",
                (cid, snapshot_date),
            )
            conn.execute(
                """
                INSERT INTO wikifx_snapshots
                    (competitor_id, snapshot_date, wikifx_score, accounts_json,
                     marketing_strategy_json, biz_area_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    snapshot_date,
                    wikifx_score,
                    json.dumps(accounts) if accounts else None,
                    json.dumps(marketing_strategy) if marketing_strategy else None,
                    json.dumps(biz_area) if biz_area else None,
                ),
            )
            conn.commit()
            total_records += 1
            print(f"  [{name}] Saved to DB ✓")

            detect_change(conn, cid, "wikifx", "wikifx_score", wikifx_score, "medium")

        except Exception as e:
            msg = f"{name} db: {e}"
            print(f"  DB Error: {msg}")
            error_summary.append(msg)

        time.sleep(DELAY_BETWEEN_REQUESTS)

    conn.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records written: {total_records}. Status: {status}")
    if error_summary:
        print(f"Errors: {error_msg}")


if __name__ == "__main__":
    scrape_all()

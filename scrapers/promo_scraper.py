"""
promo_scraper.py
----------------
Uses Playwright + Claude API to extract promotions for all competitors.

Flow:
  Step A — Pre-fetch MyFXBook promotions page once (Playwright + Claude API)
  Step B — Per-competitor: scrape promo page with Playwright, extract with Claude API
  Step C — Merge MyFXBook promos, deduplicate by title overlap, store result

Requires environment variable: ANTHROPIC_API_KEY

Run from the project root:
    python scrapers/promo_scraper.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

# Load .env.local for ANTHROPIC_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
except ImportError:
    pass

from config import ALL_BROKERS as COMPETITORS, DELAY_BETWEEN_REQUESTS, SCRAPER_UA
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change

SCRAPER_NAME = "promo_scraper"

MYFXBOOK_URL = "https://www.myfxbook.com/forex-broker-promotions"


# ---------------------------------------------------------------------------
# Claude API helper
# ---------------------------------------------------------------------------

def _get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=api_key)
    except ImportError:
        print("WARNING: anthropic package not installed. Run: pip install anthropic")
        return None


def _call_claude(client, prompt: str, system: str | None = None) -> str | None:
    """Call Claude API and return the text response, or None on failure."""
    try:
        kwargs = {
            "model": "claude-haiku-4-5-20251001",  # Fast + cheap for extraction tasks
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = client.messages.create(**kwargs)
        return response.content[0].text if response.content else None
    except Exception as e:
        print(f"    [Claude] API error: {e}")
        return None


def _parse_json_from_response(text: str) -> list | dict | None:
    """Extract and parse JSON from a Claude response (may be wrapped in markdown code block)."""
    if not text:
        return None
    # Try to find JSON array or object in the response
    text = text.strip()
    # Remove markdown code fences if present
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first JSON array or object
        m = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Step A — MyFXBook pre-fetch
# ---------------------------------------------------------------------------

async def fetch_myfxbook_promos(page, client) -> dict[str, list[dict]]:
    """
    Scrape MyFXBook broker promotions page and extract per-broker promos via Claude.
    Returns dict keyed by normalized broker name (lowercase).
    """
    if client is None:
        return {}

    print("  Pre-fetching MyFXBook promotions...")
    try:
        await page.goto(MYFXBOOK_URL, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(3)
        page_text = await page.inner_text("body")
        # Truncate to avoid hitting token limits
        page_text = page_text[:12000]
    except Exception as e:
        print(f"  [MyFXBook] Error loading page: {e}")
        return {}

    prompt = f"""From this MyFXBook forex broker promotions page, extract all broker promotions grouped by broker name.

Page content:
{page_text}

Return a JSON object where keys are broker names and values are arrays of promotion objects:
{{"broker_name": [{{"title": "...", "description": "...", "offer_value": "...", "expiry": "...", "source_url": "{MYFXBOOK_URL}"}}]}}

Only include genuine financial promotions (deposit bonuses, cashback, rebates, trading contests, referral rewards).
Return an empty object {{}} if no promotions are found."""

    response_text = _call_claude(client, prompt)
    result = _parse_json_from_response(response_text)

    if not isinstance(result, dict):
        print("  [MyFXBook] Could not parse Claude response as dict")
        return {}

    # Normalize keys to lowercase for matching
    normalized = {k.lower().strip(): v for k, v in result.items() if isinstance(v, list)}
    print(f"  [MyFXBook] Extracted promos for {len(normalized)} broker(s)")
    return normalized


# ---------------------------------------------------------------------------
# Step B — Per-competitor Claude extraction
# ---------------------------------------------------------------------------

async def extract_promos_with_claude(page, competitor: dict, client) -> list[dict]:
    """
    Navigate to competitor promo page, extract text, call Claude to identify real promotions.
    """
    promo_url = competitor["promo_url"]
    name = competitor["name"]

    try:
        await page.goto(promo_url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(3)
        page_text = await page.inner_text("body")
        # Truncate to avoid token limits
        page_text = page_text[:10000]
    except PlaywrightTimeout:
        print(f"    [Promo] Timeout loading {promo_url}")
        return []
    except Exception as e:
        print(f"    [Promo] Error loading {promo_url}: {e}")
        return []

    if client is None:
        # Fallback: return empty if no Claude API
        return []

    prompt = f"""You are extracting promotions from a forex broker's website. From the following page text,
extract ONLY genuine financial promotions (deposit bonuses, cashback, rebates, trading contests,
referral rewards). Do NOT include generic product features, platform descriptions, or
'why trade with us' content.

Broker: {name}
Page URL: {promo_url}

Page content:
{page_text}

Return a JSON array:
[{{"title": "...", "description": "...", "offer_value": "...", "expiry": "...", "url": "..."}}]

For the "url" field: include the specific href/link for this promotion if one exists on the page,
otherwise set it to null.

Return [] if no real promotions are found."""

    response_text = _call_claude(client, prompt)
    result = _parse_json_from_response(response_text)

    if not isinstance(result, list):
        return []

    # Add source_url to each promo: use Claude-extracted url if present, else fall back to promo_url
    promos = []
    for item in result:
        if isinstance(item, dict) and item.get("title"):
            extracted_url = item.pop("url", None)
            item["source_url"] = extracted_url if extracted_url else promo_url
            promos.append(item)

    return promos


# ---------------------------------------------------------------------------
# Step C — Merge and deduplicate
# ---------------------------------------------------------------------------

def _title_words(title: str) -> set[str]:
    """Return set of meaningful words in a title (lowercase, strip punctuation)."""
    words = re.findall(r'\b[a-z]{3,}\b', title.lower())
    return set(words)


def _is_duplicate(new_title: str, existing_promos: list[dict], threshold: float = 0.8) -> bool:
    """Return True if new_title has >threshold word overlap with any existing promo title."""
    new_words = _title_words(new_title)
    if not new_words:
        return False
    for existing in existing_promos:
        existing_words = _title_words(existing.get("title", ""))
        if not existing_words:
            continue
        overlap = len(new_words & existing_words) / max(len(new_words), len(existing_words))
        if overlap >= threshold:
            return True
    return False


def merge_promos(
    competitor_promos: list[dict],
    myfxbook_promos: dict[str, list[dict]],
    broker_name: str,
) -> list[dict]:
    """
    Merge competitor-scraped promos with MyFXBook promos, deduplicating by title overlap.
    """
    merged = list(competitor_promos)

    # Find matching MyFXBook entry by normalized name
    broker_lower = broker_name.lower()
    myfxbook_matches: list[dict] = []

    # Try exact match first, then partial
    if broker_lower in myfxbook_promos:
        myfxbook_matches = myfxbook_promos[broker_lower]
    else:
        for key, promos in myfxbook_promos.items():
            broker_parts = broker_lower.split()
            if any(part in key for part in broker_parts if len(part) > 3):
                myfxbook_matches = promos
                break

    for promo in myfxbook_matches:
        title = promo.get("title", "")
        if title and not _is_duplicate(title, merged):
            merged.append(promo)

    return merged


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def scrape_all():
    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    client = _get_anthropic_client()
    if client is None:
        print("WARNING: ANTHROPIC_API_KEY not set or anthropic not installed.")
        print("         Promo extraction will return empty results.")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=SCRAPER_UA,
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,mp4,webp}",
            lambda r: r.abort(),
        )

        conn = get_db()
        snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # --- Step A: Pre-fetch MyFXBook ---
        myfxbook_promos = await fetch_myfxbook_promos(page, client)
        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        for competitor in COMPETITORS:
            cid = competitor["id"]
            name = competitor["name"]
            promo_url = competitor["promo_url"]
            print(f"Processing {name}...")

            promos: list[dict] = []
            try:
                # --- Step B: Extract with Claude ---
                promos = await extract_promos_with_claude(page, competitor, client)
                print(f"    Claude extracted {len(promos)} promotion(s).")

                # --- Step C: Merge with MyFXBook ---
                promos = merge_promos(promos, myfxbook_promos, name)
                print(f"    After MyFXBook merge: {len(promos)} promotion(s).")

            except Exception as e:
                msg = f"{name}: {e}"
                print(f"    Error: {msg}")
                error_summary.append(msg)

            # Always write (even if empty) to record the snapshot
            try:
                promos_json = json.dumps(promos)
                conn.execute(
                    "DELETE FROM promo_snapshots WHERE competitor_id=? AND snapshot_date=?",
                    (cid, snapshot_date),
                )
                conn.execute(
                    """
                    INSERT INTO promo_snapshots (competitor_id, snapshot_date, promotions_json)
                    VALUES (?, ?, ?)
                    """,
                    (cid, snapshot_date, promos_json),
                )
                conn.commit()
                total_records += 1

                # Change detection: track count and titles
                detect_change(
                    conn, cid, "promos", "promo_count",
                    str(len(promos)), "medium"
                )
                titles = json.dumps(sorted(p["title"] for p in promos if p.get("title")))
                detect_change(conn, cid, "promos", "promo_titles", titles, "medium")

            except Exception as e:
                msg = f"{name} db: {e}"
                print(f"    DB Error: {msg}")
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

"""
pricing_scraper.py
------------------
Uses Playwright to scrape pricing / account-type pages for all competitors.
Extracts via Claude API:
  - Account types (list of objects with name, min_deposit, spread_from, max_leverage, currency)
  - Minimum deposit (USD)
  - Leverage ratios (list of strings like "1:500")
  - Number of instruments/assets
  - Funding methods

Stores results in pricing_snapshots and runs change detection.
Guards against overwriting existing data when extraction returns empty.

Run from the project root:
    python scrapers/pricing_scraper.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout  # type: ignore[import]

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

# Load .env.local so ANTHROPIC_API_KEY and other secrets are available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
except ImportError:
    pass

from config import ALL_BROKERS as COMPETITORS, DELAY_BETWEEN_REQUESTS, SCRAPER_UA  # type: ignore[import]
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change  # type: ignore[import]
from wikifx_scraper import _fetch, _extract_accounts_from_html  # type: ignore[import]

SCRAPER_NAME = "pricing_scraper"

# ---------------------------------------------------------------------------
# Claude API extraction
# ---------------------------------------------------------------------------

def _extract_with_claude(combined_text: str, broker_name: str) -> dict:
    """
    Call Claude API to extract all structured pricing data from page text.
    Returns dict with accounts, min_deposit_usd, leverage, instruments_count,
    funding_methods.
    """
    try:
        import anthropic  # type: ignore[import]
    except ImportError:
        print("    [Claude] anthropic package not installed — skipping AI extraction")
        return {}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("    [Claude] ANTHROPIC_API_KEY not set — skipping AI extraction")
        return {}

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are extracting structured data from a forex broker's account types and pricing page.

Broker: {broker_name}

Page text:
{combined_text[:15000]}

Return ONLY a valid JSON object with this exact structure:
{{
  "accounts": [
    {{
      "name": "account type name e.g. Standard, Razor, Raw, ECN",
      "min_deposit": "raw text e.g. $200 or No minimum or null",
      "spread_from": "e.g. From 0.0 pips or null",
      "max_leverage": "e.g. 1:500 or null",
      "currency": "e.g. USD or null"
    }}
  ],
  "min_deposit_usd": 200.0,
  "max_leverage": "1:500",
  "instruments_count": 1000,
  "funding_methods": ["Visa", "Mastercard", "Bank Transfer"]
}}

Rules:
- accounts: only include account types clearly described on the page; empty array if none found
- min_deposit_usd: the lowest numeric USD deposit across all accounts (null if unclear or not mentioned)
- max_leverage: the highest leverage ratio offered (string like "1:500", null if not found)
- instruments_count: total number of tradable instruments/assets/pairs (integer, null if not mentioned)
- funding_methods: list of payment method names found (e.g. Visa, Mastercard, PayPal, Bank Transfer, Bitcoin); empty array if none found
- Return only JSON, no explanation or markdown"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Extract JSON object robustly — handles markdown fences, leading/trailing text
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        raise ValueError(f"No JSON object found in Claude response: {raw[:200]}")

    return json.loads(json_match.group(0))


# ---------------------------------------------------------------------------
# WikiFX enrichment
# ---------------------------------------------------------------------------

def _parse_leverage_value(raw: str) -> str | None:
    """
    Parse a leverage value from various formats into canonical '1:NNN' form.
    Handles: '1:500', '500:1', '500', 'x500', '500x', 'up to 500'.
    Returns None if no plausible leverage found.
    """
    # Standard 1:NNN
    m = re.search(r'1\s*:\s*(\d+)', raw)
    if m:
        return f"1:{m.group(1)}"
    # Reversed NNN:1
    m = re.search(r'(\d+)\s*:\s*1\b', raw)
    if m:
        return f"1:{m.group(1)}"
    # Plain number or x-prefixed/suffixed: only if in typical leverage range
    m = re.search(r'[xX]?\s*(\d+)\s*[xX]?', raw)
    if m:
        val = int(m.group(1))
        if 10 <= val <= 3000:
            return f"1:{val}"
    return None


def _enrich_from_wikifx(competitor: dict, result: dict) -> dict:
    """
    Fetch the WikiFX broker page and use its structured account table to:
      - Populate spread_json (always, as it's not captured by direct scraping)
      - Fill account_types if Claude returned nothing
      - Fill min_deposit_usd if still None after Claude extraction
      - Fill leverage if still empty after Claude extraction
    """
    wikifx_id = competitor.get("wikifx_id")
    name = competitor["name"]
    if not wikifx_id:
        return result

    url = f"https://www.wikifx.com/en/dealer/{wikifx_id}.html"
    try:
        status: int
        html: str
        status, html = _fetch(url)
    except Exception as e:
        print(f"    [WikiFX fallback] Fetch error for {name}: {e}")
        return result

    if status != 200 or len(html) < 1000:
        print(f"    [WikiFX fallback] HTTP {status} or empty page for {name}")
        return result

    accounts = _extract_accounts_from_html(html)
    if not accounts:
        print(f"    [WikiFX fallback] No accounts extracted for {name} — trying text scan")

    # Build spread_json from account table rows
    if accounts:
        spread_json = []
        for acc in accounts:
            if acc.get("spread_from"):
                spread_json.append({
                    "account_type": acc.get("name", ""),
                    "spread_from": acc["spread_from"],
                })
        result["spread_json"] = spread_json

        # Fallback: account_types from WikiFX when Claude returned nothing
        if not result["account_types"]:
            wikifx_names = [a["name"] for a in accounts if a.get("name")]
            if wikifx_names:
                result["account_types"] = wikifx_names
                print(f"    [WikiFX fallback] account_types filled: {wikifx_names}")

        # Fallback: min_deposit from WikiFX accounts (smallest parseable value)
        if result["min_deposit_usd"] is None:
            deposits = []
            for acc in accounts:
                raw = acc.get("min_deposit", "")
                digits = re.sub(r"[^\d.]", "", str(raw))
                if digits:
                    try:
                        val = float(digits)
                        if 0 < val <= 100_000:
                            deposits.append(val)
                    except ValueError:
                        pass
            if deposits:
                result["min_deposit_usd"] = min(deposits)
                print(f"    [WikiFX fallback] min_deposit filled: {result['min_deposit_usd']}")

    # Fallback: leverage — first try account table, then full page text scan
    if not result["leverage"]:
        leverages = []
        seen: set[str] = set()
        for acc in accounts:
            raw = str(acc.get("max_leverage", ""))
            key = _parse_leverage_value(raw)
            if key and key not in seen:
                seen.add(key)
                leverages.append(key)
        # Scan the raw HTML for any leverage mentions (catches non-table layouts)
        if not leverages:
            for m in re.finditer(r'(?:max(?:imum)?\s+)?leverage[^<\n]{0,80}', html, re.IGNORECASE):
                key = _parse_leverage_value(m.group(0))
                if key and key not in seen:
                    seen.add(key)
                    leverages.append(key)
        if leverages:
            result["leverage"] = leverages
            print(f"    [WikiFX fallback] leverage filled: {leverages}")
        else:
            print(f"    [WikiFX fallback] leverage not found for {name}")

    return result


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def scrape_pricing(page, competitor: dict) -> dict:
    """Scrape account/pricing pages and return extracted fields via Claude API."""
    account_urls = competitor.get("account_urls") or [competitor["pricing_url"]]
    result: dict[str, object] = {
        "min_deposit_usd": None,
        "leverage": [],
        "account_types": [],
        "instruments_count": None,
        "funding_methods": [],
        "spread_json": [],
    }

    combined_text = ""
    for url in account_urls:
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)

            # Optional per-competitor wait selector for slow-rendering pages
            wait_selector = competitor.get("pricing_wait_selector")
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    pass  # Best-effort; continue with what's loaded

            combined_text += "\n\n" + await page.inner_text("body")
        except PlaywrightTimeout:
            print(f"    [Pricing] Timeout loading {url}")
        except Exception as e:
            print(f"    [Pricing] Error loading {url} for {competitor['name']}: {e}")

    # Claude extraction for all fields
    if combined_text.strip():
        try:
            claude_result = _extract_with_claude(combined_text, competitor["name"])
            if claude_result:
                accounts = claude_result.get("accounts") or []
                result["account_types"] = [a["name"] for a in accounts if a.get("name")]
                result["min_deposit_usd"] = claude_result.get("min_deposit_usd")
                result["instruments_count"] = claude_result.get("instruments_count")
                result["funding_methods"] = claude_result.get("funding_methods") or []

                # Parse leverage from Claude's string (e.g. "1:500") into list
                raw_lev = claude_result.get("max_leverage")
                if raw_lev:
                    parsed = _parse_leverage_value(str(raw_lev))
                    if parsed:
                        result["leverage"] = [parsed]
        except Exception as e:
            print(f"    [Claude] Extraction failed for {competitor['name']}: {e}")

    print(
        f"    min_deposit={result['min_deposit_usd']} | "
        f"leverage={result['leverage']} | "
        f"accounts={result['account_types']} | "
        f"instruments={result['instruments_count']} | "
        f"funding={result['funding_methods']}"
    )

    # Enrich with WikiFX data: adds spread_json, fills any remaining gaps
    result = _enrich_from_wikifx(competitor, result)

    # Apply known authoritative values from config — always override everything
    if competitor.get("known_leverage"):
        result["leverage"] = competitor["known_leverage"]
        print(f"    [config override] leverage: {result['leverage']}")
    if competitor.get("known_account_types"):
        result["account_types"] = competitor["known_account_types"]
        print(f"    [config override] account_types: {result['account_types']}")
    if competitor.get("known_min_deposit_usd") is not None:
        result["min_deposit_usd"] = competitor["known_min_deposit_usd"]
        print(f"    [config override] min_deposit_usd: {result['min_deposit_usd']}")

    return result


async def scrape_all():
    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

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

        for competitor in COMPETITORS:
            cid = competitor["id"]
            name = competitor["name"]
            print(f"Processing {name}...")

            try:
                data = await scrape_pricing(page, competitor)

                # Guard: skip upsert if extraction returned nothing useful
                has_data = (
                    data.get("min_deposit_usd") is not None
                    or bool(data.get("leverage"))
                    or bool(data.get("account_types"))
                    or data.get("instruments_count") is not None
                    or bool(data.get("spread_json"))
                )
                if not has_data:
                    print(f"  ⚠ {name}: no pricing data extracted — preserving existing record")
                    error_summary.append(f"{name}: extraction empty, skipped upsert")
                    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                    continue

                leverage_json = json.dumps(data["leverage"])
                account_types_json = json.dumps(data["account_types"])
                funding_methods_json = json.dumps(data["funding_methods"])
                spread_json = json.dumps(data["spread_json"]) if data.get("spread_json") else None

                conn.execute(
                    "DELETE FROM pricing_snapshots WHERE competitor_id=? AND snapshot_date=?",
                    (cid, snapshot_date),
                )
                conn.execute(
                    """
                    INSERT INTO pricing_snapshots
                        (competitor_id, snapshot_date, leverage_json, account_types_json,
                         min_deposit_usd, instruments_count, funding_methods_json, spread_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        snapshot_date,
                        leverage_json,
                        account_types_json,
                        data["min_deposit_usd"],
                        data["instruments_count"],
                        funding_methods_json,
                        spread_json,
                    ),
                )
                conn.commit()
                total_records += 1

                # Change detection
                if data["min_deposit_usd"] is not None:
                    detect_change(
                        conn, cid, "pricing", "min_deposit_usd",
                        str(data["min_deposit_usd"]), "high"
                    )
                if data["leverage"]:
                    try:
                        lev_vals = [
                            int(lev.split(":")[1])
                            for lev in data["leverage"]
                            if ":" in lev and lev.split(":")[1].isdigit()
                        ]
                        max_lev = max(lev_vals) if lev_vals else None
                        if max_lev:
                            detect_change(conn, cid, "pricing", "max_leverage", str(max_lev), "high")
                    except Exception as lev_err:
                        print(f"    [Change detection] Leverage parse error for {name}: {lev_err}")
                if data.get("spread_json"):
                    detect_change(conn, cid, "pricing", "spread_json", json.dumps(data["spread_json"]), "medium")

            except Exception as e:
                msg = f"{name}: {e}"
                print(f"    Error: {msg}")
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

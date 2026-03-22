"""
pricing_scraper.py
------------------
Uses Playwright to scrape pricing / account-type pages for all competitors.
Extracts:
  - Minimum deposit (USD)
  - Leverage ratios (list of strings like "1:500")
  - Account types (list of strings)
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
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import ALL_BROKERS as COMPETITORS, DELAY_BETWEEN_REQUESTS, SCRAPER_UA  # type: ignore[import]
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change  # type: ignore[import]
from wikifx_scraper import _fetch, _extract_accounts_from_html  # type: ignore[import]

SCRAPER_NAME = "pricing_scraper"

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_min_deposit(text: str) -> float | None:
    """
    Look for patterns like "$100", "USD 100", "minimum deposit $50",
    "min deposit: 200", etc. Returns the smallest plausible deposit found.
    """
    deposits = []

    for m in re.finditer(
        r'(?i)(?:minimum\s+)?deposit[^$\d]{0,30}?(?:usd\s*)?\$?\s*([\d,]+(?:\.\d+)?)',
        text,
    ):
        val = float(m.group(1).replace(",", ""))
        if 0 < val <= 100_000:
            deposits.append(val)

    for m in re.finditer(r'\$\s*([\d,]+(?:\.\d+)?)', text):
        val = float(m.group(1).replace(",", ""))
        if 0 < val <= 10_000:
            deposits.append(val)

    if not deposits:
        return None
    candidates = [d for d in deposits if d >= 0]
    return min(candidates) if candidates else None


def _extract_leverage(text: str) -> list[str]:
    """Return list of leverage strings like ['1:200', '1:500', '1:1000']."""
    found = re.findall(r'1\s*:\s*(\d+)', text)
    seen = set()
    result = []
    for f in found:
        key = f"1:{f}"
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _extract_account_types(text: str) -> list[str]:
    """
    Heuristically extract account type names.
    Common patterns: "Standard", "Raw", "ECN", "Pro", "VIP", "Islamic", etc.
    """
    known = [
        "Standard", "Standard+", "Raw", "Raw+", "ECN", "ECN+", "Pro", "Elite",
        "VIP", "Islamic", "Swap-Free", "Swap Free", "Zero", "Ultra Low",
        "Micro", "Nano", "Mini", "Classic", "Premier", "Advantage", "Advantage+",
        "Direct", "Sharp", "Cent", "PAMM", "MAM",
        "Razor", "Razor+",
    ]
    found = []
    for acc in known:
        if re.search(re.escape(acc), text, re.IGNORECASE):
            found.append(acc)
    return found


def _extract_instruments_count(text: str) -> int | None:
    """
    Look for patterns like "500+ instruments", "1000 assets", "250 trading pairs".
    Returns the largest plausible count found.
    """
    counts = []
    for m in re.finditer(
        r'(\d[\d,]*)\s*\+?\s*(?:instruments?|assets?|(?:currency\s+)?pairs?|CFDs?|products?)',
        text,
        re.IGNORECASE,
    ):
        val = int(m.group(1).replace(",", ""))
        if 10 <= val <= 50_000:
            counts.append(val)
    return max(counts) if counts else None


def _extract_funding_methods(text: str) -> list[str]:
    """Return list of payment method names found in the page."""
    methods = [
        "Visa", "Mastercard", "American Express", "Amex",
        "PayPal", "Skrill", "Neteller", "UnionPay",
        "Bank Transfer", "Wire Transfer", "BPAY",
        "Bitcoin", "Crypto", "USDT", "ETH",
        "Fasapay", "Perfect Money", "WebMoney",
        "POLi", "Dragonpay", "GrabPay", "Alipay",
        "WeChat Pay", "Paytm",
    ]
    found = []
    for method in methods:
        if re.search(re.escape(method), text, re.IGNORECASE):
            found.append(method)
    return found


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
      - Fill min_deposit_usd if still None after direct scraping
      - Fill leverage if still empty after direct scraping
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
    """Scrape the pricing/account page and return extracted fields."""
    url = competitor["pricing_url"]
    result: dict[str, object] = {
        "min_deposit_usd": None,
        "leverage": [],
        "account_types": [],
        "instruments_count": None,
        "funding_methods": [],
        "spread_json": [],
    }

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

        # Grab all visible text
        text = await page.inner_text("body")

        result["min_deposit_usd"] = _extract_min_deposit(text)
        result["leverage"] = _extract_leverage(text)
        result["account_types"] = _extract_account_types(text)
        result["instruments_count"] = _extract_instruments_count(text)
        result["funding_methods"] = _extract_funding_methods(text)

        print(
            f"    min_deposit={result['min_deposit_usd']} | "
            f"leverage={result['leverage']} | "
            f"accounts={result['account_types']} | "
            f"instruments={result['instruments_count']} | "
            f"funding={result['funding_methods']}"
        )

    except PlaywrightTimeout:
        print(f"    [Pricing] Timeout loading {url}")
    except Exception as e:
        print(f"    [Pricing] Error for {competitor['name']}: {e}")

    # Enrich with WikiFX data: adds spread_json, fills min_deposit/leverage gaps
    result = _enrich_from_wikifx(competitor, result)

    # Apply known authoritative values from config — always override scraping
    # so stale or incorrectly extracted data is never persisted.
    if competitor.get("known_leverage"):
        result["leverage"] = competitor["known_leverage"]
        print(f"    [config override] leverage: {result['leverage']}")
    if competitor.get("known_account_types"):
        result["account_types"] = competitor["known_account_types"]
        print(f"    [config override] account_types: {result['account_types']}")

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
                    max_lev = max(
                        int(lev.split(":")[1]) for lev in data["leverage"]
                    ) if data["leverage"] else None
                    if max_lev:
                        detect_change(conn, cid, "pricing", "max_leverage", str(max_lev), "high")
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

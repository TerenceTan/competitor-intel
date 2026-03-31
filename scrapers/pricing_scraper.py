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
    Note: leverage is now handled separately by _collect_leverage_from_wikifx.
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
        print(f"    [WikiFX] Fetch error for {name}: {e}")
        return result

    if status != 200 or len(html) < 1000:
        print(f"    [WikiFX] HTTP {status} or empty page for {name}")
        return result

    accounts = _extract_accounts_from_html(html)
    if not accounts:
        print(f"    [WikiFX] No accounts extracted for {name}")

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

    return result


# ---------------------------------------------------------------------------
# Standalone leverage collectors — each returns list[str] without side effects
# ---------------------------------------------------------------------------

def _collect_leverage_from_claude(combined_text: str, broker_name: str) -> list[str]:
    """Extract leverage from official broker page text via Claude AI."""
    if not combined_text.strip():
        return []
    try:
        claude_result = _extract_with_claude(combined_text, broker_name)
        if claude_result:
            raw_lev = claude_result.get("max_leverage")
            if raw_lev:
                parsed = _parse_leverage_value(str(raw_lev))
                if parsed:
                    return [parsed]
    except Exception as e:
        print(f"    [Claude leverage] Extraction failed for {broker_name}: {e}")
    return []


def _fetch_cached(url: str, cache: dict[str, str | None], label: str) -> str | None:
    """Fetch a URL, caching the HTML result. Returns HTML or None on failure."""
    if url in cache:
        return cache[url]
    try:
        status, html = _fetch(url)
        if status == 200 and len(html) >= 1000:
            cache[url] = html
            return html
        print(f"    [{label}] HTTP {status} or empty page")
    except Exception as e:
        print(f"    [{label}] Fetch error: {e}")
    cache[url] = None
    return None


def _collect_leverage_from_wikifx(competitor: dict, cache: dict[str, str | None] | None = None) -> list[str]:
    """Extract leverage from WikiFX broker page (account table + text scan)."""
    wikifx_id = competitor.get("wikifx_id")
    if not wikifx_id:
        return []

    url = f"https://www.wikifx.com/en/dealer/{wikifx_id}.html"
    html = _fetch_cached(url, cache if cache is not None else {}, "WikiFX leverage")
    if not html:
        return []

    leverages: list[str] = []
    seen: set[str] = set()

    accounts = _extract_accounts_from_html(html)
    for acc in (accounts or []):
        raw = str(acc.get("max_leverage", ""))
        key = _parse_leverage_value(raw)
        if key and key not in seen:
            seen.add(key)
            leverages.append(key)

    # Scan raw HTML for leverage mentions (catches non-table layouts)
    if not leverages:
        for m in re.finditer(r'(?:max(?:imum)?\s+)?leverage[^<\n]{0,80}', html, re.IGNORECASE):
            key = _parse_leverage_value(m.group(0))
            if key and key not in seen:
                seen.add(key)
                leverages.append(key)

    return leverages


def _collect_leverage_from_tradingfinder(competitor: dict, cache: dict[str, str | None] | None = None) -> list[str]:
    """Extract leverage from TradingFinder broker review page."""
    slug = competitor.get("tradingfinder_slug")
    if not slug:
        return []

    url = f"https://tradingfinder.com/brokers/{slug}/"
    html = _fetch_cached(url, cache if cache is not None else {}, "TradingFinder leverage")
    if not html:
        return []

    leverages: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r'(?:max(?:imum)?\s+)?leverage[^<\n]{0,80}', html, re.IGNORECASE):
        key = _parse_leverage_value(m.group(0))
        if key and key not in seen:
            seen.add(key)
            leverages.append(key)
    return leverages


def _collect_leverage_from_dailyforex(competitor: dict, cache: dict[str, str | None] | None = None) -> list[str]:
    """Extract leverage from DailyForex broker review page."""
    slug = competitor.get("dailyforex_slug")
    if not slug:
        return []

    url = f"https://www.dailyforex.com/forex-brokers/{slug}-review"
    html = _fetch_cached(url, cache if cache is not None else {}, "DailyForex leverage")
    if not html:
        return []

    leverages: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r'(?:max(?:imum)?\s+)?leverage[^<\n]{0,80}', html, re.IGNORECASE):
        key = _parse_leverage_value(m.group(0))
        if key and key not in seen:
            seen.add(key)
            leverages.append(key)
    return leverages


# ---------------------------------------------------------------------------
# Standalone min-deposit collectors — each returns float | None
# ---------------------------------------------------------------------------

def _parse_min_deposit(raw: str) -> float | None:
    """Parse a min deposit string like '$200', 'USD 50', '0', 'No minimum' into a float."""
    if not raw:
        return None
    s = str(raw).lower().strip()
    if any(kw in s for kw in ("no minimum", "no min", "none", "n/a")):
        return 0.0
    digits = re.sub(r"[^\d.]", "", s)
    if digits:
        try:
            val = float(digits)
            if 0 <= val <= 100_000:
                return val
        except ValueError:
            pass
    return None


def _collect_min_deposit_from_wikifx(competitor: dict, cache: dict[str, str | None] | None = None) -> float | None:
    """Extract min deposit from WikiFX broker page account table."""
    wikifx_id = competitor.get("wikifx_id")
    if not wikifx_id:
        return None

    url = f"https://www.wikifx.com/en/dealer/{wikifx_id}.html"
    html = _fetch_cached(url, cache if cache is not None else {}, "WikiFX min_deposit")
    if not html:
        return None

    accounts = _extract_accounts_from_html(html)
    deposits: list[float] = []
    for acc in (accounts or []):
        val = _parse_min_deposit(acc.get("min_deposit", ""))
        if val is not None:
            deposits.append(val)
    return min(deposits) if deposits else None


def _collect_min_deposit_from_tradingfinder(competitor: dict, cache: dict[str, str | None] | None = None) -> float | None:
    """Extract min deposit from TradingFinder broker review page."""
    slug = competitor.get("tradingfinder_slug")
    if not slug:
        return None

    url = f"https://tradingfinder.com/brokers/{slug}/"
    html = _fetch_cached(url, cache if cache is not None else {}, "TradingFinder min_deposit")
    if not html:
        return None

    # Look for patterns like "Min Deposit: $20", "Minimum Deposit: USD 50"
    for m in re.finditer(
        r'(?:min(?:imum)?\s+)?deposit[^<\n]{0,60}',
        html,
        re.IGNORECASE,
    ):
        val = _parse_min_deposit(m.group(0))
        if val is not None:
            return val
    return None


def _collect_min_deposit_from_dailyforex(competitor: dict, cache: dict[str, str | None] | None = None) -> float | None:
    """Extract min deposit from DailyForex broker review page."""
    slug = competitor.get("dailyforex_slug")
    if not slug:
        return None

    url = f"https://www.dailyforex.com/forex-brokers/{slug}-review"
    html = _fetch_cached(url, cache if cache is not None else {}, "DailyForex min_deposit")
    if not html:
        return None

    for m in re.finditer(
        r'(?:min(?:imum)?\s+)?deposit[^<\n]{0,60}',
        html,
        re.IGNORECASE,
    ):
        val = _parse_min_deposit(m.group(0))
        if val is not None:
            return val
    return None


# ---------------------------------------------------------------------------
# Min-deposit reconciliation
# ---------------------------------------------------------------------------

def _reconcile_min_deposit(
    sources: dict[str, float | None], broker_name: str
) -> tuple[float | None, str, dict]:
    """
    Compare min deposit values from multiple sources and reconcile.
    Returns (final_value, confidence, reconciliation_info).
    """
    non_empty = {k: v for k, v in sources.items() if v is not None}

    if not non_empty:
        return None, "low", {"method": "no_data"}

    source_names = list(non_empty.keys())
    source_values = list(non_empty.values())

    if len(non_empty) == 1:
        src = source_names[0]
        return source_values[0], "low", {"method": "single_source", "source": src}

    # All agree (exact match)
    unique_vals = set(source_values)
    if len(unique_vals) == 1:
        return source_values[0], "high", {
            "method": "auto_agree",
            "agreed_value": source_values[0],
            "sources": source_names,
        }

    # Close enough — within $10 tolerance (brokers often show $0 vs $1, or $50 vs $45)
    min_val = min(source_values)
    max_val = max(source_values)
    if max_val - min_val <= 10:
        # Use the lowest (most conservative/favorable) value
        return min_val, "high", {
            "method": "auto_agree_within_tolerance",
            "chosen_value": min_val,
            "range": [min_val, max_val],
            "sources": source_names,
        }

    # Majority agree (3+ sources)
    if len(non_empty) >= 3:
        from collections import Counter
        counts = Counter(source_values)
        most_common_val, most_common_count = counts.most_common(1)[0]
        if most_common_count >= 2 and most_common_count > len(non_empty) / 2:
            majority_sources = [s for s, v in non_empty.items() if v == most_common_val]
            outliers = {s: v for s, v in non_empty.items() if v != most_common_val}
            return most_common_val, "medium", {
                "method": "majority_agree",
                "agreed_value": most_common_val,
                "majority_sources": majority_sources,
                "outliers": outliers,
            }

    # Genuine disagreement — call Claude
    print(f"    [Min deposit reconciliation] Sources disagree for {broker_name}: {non_empty} — calling Claude")
    try:
        import anthropic  # type: ignore[import]
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            for preferred in ("claude", "wikifx", "tradingfinder", "dailyforex"):
                if preferred in non_empty:
                    return non_empty[preferred], "low", {
                        "method": "fallback_no_api_key",
                        "source": preferred,
                        "disagreement": non_empty,
                    }

        client = anthropic.Anthropic(api_key=api_key)
        source_lines = "\n".join(
            f"- {src}: ${val}" for src, val in non_empty.items()
        )
        prompt = f"""You are validating minimum deposit data for the forex broker "{broker_name}".
Multiple sources report different minimum deposit amounts (USD):

{source_lines}

Which minimum deposit value is most likely correct? Consider:
1. "claude" source (official broker website) is most authoritative when available
2. "wikifx" is a regulated broker database and generally reliable
3. "tradingfinder" and "dailyforex" are review sites that may have outdated info
4. $0 means "no minimum deposit" — this is a real value, not missing data

Return ONLY a JSON object:
{{
  "min_deposit_usd": NNN.0,
  "confidence": "high" | "medium" | "low",
  "reasoning": "brief explanation (1-2 sentences)"
}}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            reconciled = json.loads(json_match.group(0))
            final_val = reconciled.get("min_deposit_usd")
            confidence = reconciled.get("confidence", "medium")
            if final_val is not None:
                print(f"    [Min deposit reconciliation] Claude chose ${final_val} ({confidence}): {reconciled.get('reasoning', '')}")
                return float(final_val), confidence, {
                    "method": "claude_reconciled",
                    "reasoning": reconciled.get("reasoning", ""),
                    "disagreement": non_empty,
                }
    except Exception as e:
        print(f"    [Min deposit reconciliation] Claude call failed for {broker_name}: {e}")

    # Final fallback: prefer official site, then WikiFX
    for preferred in ("claude", "wikifx", "tradingfinder", "dailyforex"):
        if preferred in non_empty:
            return non_empty[preferred], "low", {
                "method": "fallback_reconciliation_failed",
                "source": preferred,
                "disagreement": non_empty,
            }

    return None, "low", {"method": "no_data"}


# ---------------------------------------------------------------------------
# Leverage reconciliation
# ---------------------------------------------------------------------------

def _max_leverage_int(values: list[str]) -> int | None:
    """Extract the highest leverage integer from a list like ['1:200', '1:500']."""
    nums = []
    for v in values:
        if ":" in v:
            try:
                nums.append(int(v.split(":")[1]))
            except (ValueError, IndexError):
                pass
    return max(nums) if nums else None


def _reconcile_leverage(sources: dict[str, list[str]], broker_name: str) -> tuple[list[str], str, dict]:
    """
    Compare leverage values from multiple sources and reconcile.
    Returns (final_leverage_list, confidence, reconciliation_info).

    Logic:
    1. No data → low confidence
    2. Single source → low confidence
    3. All sources agree → high confidence (no Claude call)
    4. Majority agree → medium confidence (no Claude call)
    5. Genuine disagreement → call Claude Haiku to reconcile
    """
    non_empty = {k: v for k, v in sources.items() if v}

    if not non_empty:
        return [], "low", {"method": "no_data"}

    source_names = list(non_empty.keys())
    source_values = list(non_empty.values())

    if len(non_empty) == 1:
        src = source_names[0]
        return source_values[0], "low", {"method": "single_source", "source": src}

    # Compare max leverage integers across sources
    max_per_source: dict[str, int] = {}
    for src, vals in non_empty.items():
        mx = _max_leverage_int(vals)
        if mx is not None:
            max_per_source[src] = mx

    if not max_per_source:
        # All sources had values but none parseable
        first_vals = source_values[0]
        return first_vals, "low", {"method": "unparseable", "sources": source_names}

    unique_maxes = set(max_per_source.values())

    # All agree
    if len(unique_maxes) == 1:
        agreed_val = unique_maxes.pop()
        # Use the richest value list (most entries) from any agreeing source
        best_vals = max(source_values, key=len)
        return best_vals, "high", {
            "method": "auto_agree",
            "agreed_value": f"1:{agreed_val}",
            "sources": source_names,
        }

    # Majority agree (3+ sources provided data)
    if len(max_per_source) >= 3:
        from collections import Counter
        counts = Counter(max_per_source.values())
        most_common_val, most_common_count = counts.most_common(1)[0]
        if most_common_count >= 2 and most_common_count > len(max_per_source) / 2:
            majority_sources = [s for s, v in max_per_source.items() if v == most_common_val]
            outlier_sources = {s: f"1:{v}" for s, v in max_per_source.items() if v != most_common_val}
            # Use values from a majority source
            best_vals = non_empty[majority_sources[0]]
            return best_vals, "medium", {
                "method": "majority_agree",
                "agreed_value": f"1:{most_common_val}",
                "majority_sources": majority_sources,
                "outliers": outlier_sources,
            }

    # Genuine disagreement — call Claude to reconcile
    print(f"    [Reconciliation] Sources disagree for {broker_name}: {max_per_source} — calling Claude")
    try:
        import anthropic  # type: ignore[import]
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            # Can't call Claude — fall back to official site or highest-authority source
            for preferred in ("claude", "wikifx", "tradingfinder", "dailyforex"):
                if preferred in non_empty:
                    return non_empty[preferred], "low", {
                        "method": "fallback_no_api_key",
                        "source": preferred,
                        "disagreement": {s: f"1:{v}" for s, v in max_per_source.items()},
                    }

        client = anthropic.Anthropic(api_key=api_key)
        source_lines = "\n".join(
            f"- {src}: {vals}" for src, vals in non_empty.items()
        )
        prompt = f"""You are validating leverage data for the forex broker "{broker_name}".
Multiple sources report different maximum leverage values:

{source_lines}

Which maximum leverage value is most likely correct? Consider:
1. "claude" source (official broker website) is most authoritative when available
2. "wikifx" is a regulated broker database and generally reliable
3. "tradingfinder" and "dailyforex" are review sites that may have outdated info
4. Differences may reflect different jurisdictions (e.g., EU 1:30 vs global 1:500) — prefer the global/international max

Return ONLY a JSON object:
{{
  "max_leverage": "1:NNN",
  "confidence": "high" | "medium" | "low",
  "reasoning": "brief explanation (1-2 sentences)"
}}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            reconciled = json.loads(json_match.group(0))
            final_lev = reconciled.get("max_leverage")
            parsed = _parse_leverage_value(str(final_lev)) if final_lev else None
            confidence = reconciled.get("confidence", "medium")
            if parsed:
                print(f"    [Reconciliation] Claude chose {parsed} ({confidence}): {reconciled.get('reasoning', '')}")
                return [parsed], confidence, {
                    "method": "claude_reconciled",
                    "reasoning": reconciled.get("reasoning", ""),
                    "disagreement": {s: f"1:{v}" for s, v in max_per_source.items()},
                }
    except Exception as e:
        print(f"    [Reconciliation] Claude call failed for {broker_name}: {e}")

    # Final fallback: prefer official site, then WikiFX, then others
    for preferred in ("claude", "wikifx", "tradingfinder", "dailyforex"):
        if preferred in non_empty:
            return non_empty[preferred], "low", {
                "method": "fallback_reconciliation_failed",
                "source": preferred,
                "disagreement": {s: f"1:{v}" for s, v in max_per_source.items()},
            }

    return [], "low", {"method": "no_data"}


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def scrape_pricing(page, competitor: dict) -> dict:
    """Scrape account/pricing pages and return extracted fields via Claude API."""
    account_urls = competitor.get("account_urls") or [competitor["pricing_url"]]
    name = competitor["name"]
    result: dict[str, object] = {
        "min_deposit_usd": None,
        "leverage": [],
        "account_types": competitor.get("known_account_types", []),
        "instruments_count": None,
        "funding_methods": [],
        "spread_json": [],
        "leverage_sources": {},
        "leverage_confidence": None,
        "leverage_reconciliation": {},
        "min_deposit_sources": {},
        "min_deposit_confidence": None,
        "min_deposit_reconciliation": {},
    }

    # Log config overrides applied up front
    if competitor.get("known_account_types"):
        print(f"    [config override] account_types: {result['account_types']}")

    # If known_leverage is set, skip all leverage scraping entirely
    if competitor.get("known_leverage"):
        result["leverage"] = competitor["known_leverage"]
        result["leverage_sources"] = {"config_override": competitor["known_leverage"]}
        result["leverage_confidence"] = "high"
        result["leverage_reconciliation"] = {"method": "config_override"}
        print(f"    [config override] leverage: {result['leverage']}")

    # If known_min_deposit_usd is set, skip all min deposit scraping entirely
    if competitor.get("known_min_deposit_usd") is not None:
        result["min_deposit_usd"] = competitor["known_min_deposit_usd"]
        result["min_deposit_sources"] = {"config_override": competitor["known_min_deposit_usd"]}
        result["min_deposit_confidence"] = "high"
        result["min_deposit_reconciliation"] = {"method": "config_override"}
        print(f"    [config override] min_deposit_usd: {result['min_deposit_usd']}")

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
            print(f"    [Pricing] Error loading {url} for {name}: {e}")

    # Claude extraction for non-leverage/non-deposit fields (+ raw result for cross-source)
    claude_result: dict = {}
    if combined_text.strip():
        try:
            claude_result = _extract_with_claude(combined_text, name) or {}
            if claude_result:
                accounts = claude_result.get("accounts") or []
                if not result["account_types"]:
                    result["account_types"] = [a["name"] for a in accounts if a.get("name")]
                result["instruments_count"] = claude_result.get("instruments_count")
                result["funding_methods"] = claude_result.get("funding_methods") or []
        except Exception as e:
            print(f"    [Claude] Extraction failed for {name}: {e}")

    # Enrich with WikiFX data: adds spread_json, fills account_types/min_deposit gaps
    result = _enrich_from_wikifx(competitor, result)

    # Shared HTML cache for cross-source collection — each URL is fetched at most once
    html_cache: dict[str, str | None] = {}

    # Cross-source leverage collection and reconciliation (skip if config override)
    if not competitor.get("known_leverage"):
        print(f"    [Leverage] Collecting from all sources for {name}...")

        # Source 1: Claude (already extracted above)
        claude_leverages = _collect_leverage_from_claude(combined_text, name) if not claude_result else []
        if claude_result:
            raw_lev = claude_result.get("max_leverage")
            if raw_lev:
                parsed = _parse_leverage_value(str(raw_lev))
                claude_leverages = [parsed] if parsed else []

        # Source 2: WikiFX
        await asyncio.sleep(1)
        wikifx_leverages = _collect_leverage_from_wikifx(competitor, html_cache)

        # Source 3: TradingFinder
        await asyncio.sleep(1)
        tf_leverages = _collect_leverage_from_tradingfinder(competitor, html_cache)

        # Source 4: DailyForex
        await asyncio.sleep(1)
        df_leverages = _collect_leverage_from_dailyforex(competitor, html_cache)

        sources = {
            "claude": claude_leverages,
            "wikifx": wikifx_leverages,
            "tradingfinder": tf_leverages,
            "dailyforex": df_leverages,
        }
        print(f"    [Leverage] Sources: {sources}")

        final_leverage, confidence, reconciliation = _reconcile_leverage(sources, name)
        result["leverage"] = final_leverage
        result["leverage_sources"] = sources
        result["leverage_confidence"] = confidence
        result["leverage_reconciliation"] = reconciliation
        print(f"    [Leverage] Final: {final_leverage} (confidence: {confidence}, method: {reconciliation.get('method')})")

    # Cross-source min deposit collection and reconciliation (skip if config override)
    if competitor.get("known_min_deposit_usd") is None:
        print(f"    [Min deposit] Collecting from all sources for {name}...")

        # Source 1: Claude (already extracted above)
        claude_min_dep = claude_result.get("min_deposit_usd") if claude_result else None

        # Source 2: WikiFX (reuses cached HTML from leverage collection)
        wikifx_min_dep = _collect_min_deposit_from_wikifx(competitor, html_cache)

        # Source 3: TradingFinder (reuses cached HTML)
        tf_min_dep = _collect_min_deposit_from_tradingfinder(competitor, html_cache)

        # Source 4: DailyForex (reuses cached HTML)
        df_min_dep = _collect_min_deposit_from_dailyforex(competitor, html_cache)

        dep_sources = {
            "claude": claude_min_dep,
            "wikifx": wikifx_min_dep,
            "tradingfinder": tf_min_dep,
            "dailyforex": df_min_dep,
        }
        print(f"    [Min deposit] Sources: {dep_sources}")

        final_deposit, dep_confidence, dep_reconciliation = _reconcile_min_deposit(dep_sources, name)
        result["min_deposit_usd"] = final_deposit
        result["min_deposit_sources"] = dep_sources
        result["min_deposit_confidence"] = dep_confidence
        result["min_deposit_reconciliation"] = dep_reconciliation
        print(f"    [Min deposit] Final: ${final_deposit} (confidence: {dep_confidence}, method: {dep_reconciliation.get('method')})")

    print(
        f"    min_deposit={result['min_deposit_usd']} | "
        f"leverage={result['leverage']} | "
        f"accounts={result['account_types']} | "
        f"instruments={result['instruments_count']} | "
        f"funding={result['funding_methods']}"
    )

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
                leverage_sources_json = json.dumps(data.get("leverage_sources", {}))
                leverage_confidence = data.get("leverage_confidence")
                leverage_reconciliation_json = json.dumps(data.get("leverage_reconciliation", {}))
                min_deposit_sources_json = json.dumps(data.get("min_deposit_sources", {}))
                min_deposit_confidence = data.get("min_deposit_confidence")
                min_deposit_reconciliation_json = json.dumps(data.get("min_deposit_reconciliation", {}))

                conn.execute(
                    "DELETE FROM pricing_snapshots WHERE competitor_id=? AND snapshot_date=?",
                    (cid, snapshot_date),
                )
                conn.execute(
                    """
                    INSERT INTO pricing_snapshots
                        (competitor_id, snapshot_date, leverage_json, account_types_json,
                         min_deposit_usd, instruments_count, funding_methods_json, spread_json,
                         leverage_sources_json, leverage_confidence, leverage_reconciliation_json,
                         min_deposit_sources_json, min_deposit_confidence, min_deposit_reconciliation_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        leverage_sources_json,
                        leverage_confidence,
                        leverage_reconciliation_json,
                        min_deposit_sources_json,
                        min_deposit_confidence,
                        min_deposit_reconciliation_json,
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

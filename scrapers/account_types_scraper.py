"""
account_types_scraper.py
------------------------
Dedicated scraper for detailed account type specifications from CFD/Forex brokers.
Uses a 3-layer extraction strategy with cross-source reconciliation:

  Layer 1: Official broker account pages (Playwright + Claude AI) — primary
  Layer 2: Help centre / FAQ pages (plain HTTP) — supplement for missing fields
  Layer 3: Aggregator cross-check (TradingFinder, DailyForex) — validation

When sources disagree on key fields (spreads, commission, min deposit, leverage),
the reconciliation engine compares values and calls Claude Haiku to resolve.

Stores results in account_type_snapshots table.
Runs change detection for new/removed accounts and field changes.

Run from the project root:
    python scrapers/account_types_scraper.py
    python scrapers/account_types_scraper.py --broker ic-markets
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

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
except ImportError:
    pass

from config import DELAY_BETWEEN_REQUESTS, SCRAPER_UA, SCRAPER_HEADERS
from db_utils import get_all_brokers
ALL_BROKERS = get_all_brokers()
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change
from market_config import PRIORITY_MARKETS, get_market_urls

SCRAPER_NAME = "account_types_scraper"

# Account category normalisation mapping
CATEGORY_KEYWORDS = {
    "standard": "standard",
    "classic": "standard",
    "stp": "standard",
    "raw": "ecn_raw",
    "ecn": "ecn_raw",
    "razor": "ecn_raw",
    "edge": "ecn_raw",
    "raw+": "ecn_raw",
    "zero": "zero_spread",
    "zero spread": "zero_spread",
    "pro": "pro",
    "professional": "pro",
    "pro plus": "pro",
    "elite": "pro",
    "premium": "pro",
    "cent": "cent",
    "micro": "cent",
    "shares": "shares",
    "copy": "copy_trading",
    "social": "copy_trading",
    "bonus": "bonus",
    "top-up bonus": "bonus",
    "islamic": "islamic",
    "swap-free": "islamic",
    "swap free": "islamic",
    "demo": "demo",
}


def _classify_account_category(account_name: str) -> str:
    """Map an account name to a standardised category."""
    name_lower = account_name.lower().strip()
    for keyword in sorted(CATEGORY_KEYWORDS, key=len, reverse=True):
        if keyword in name_lower:
            return CATEGORY_KEYWORDS[keyword]
    return "standard"


# Patterns that indicate "no real data" — Claude sometimes generates these instead of null
_JUNK_PATTERNS = re.compile(
    r"^("
    r"unable to (?:determine|find|extract|verify)"
    r"|not (?:available|specified|mentioned|found|provided|disclosed|stated|listed|applicable)"
    r"|n/?a"
    r"|unknown"
    r"|none"
    r"|varies"
    r"|see (?:website|page|broker)"
    r"|contact (?:broker|support)"
    r"|check (?:website|broker)"
    r"|no (?:data|info|information)"
    r"|--+"
    r"|—+"
    r"|-"
    r")$",
    re.IGNORECASE,
)

# Fields that should contain actual data values, not descriptions
_DATA_FIELDS = {
    "min_deposit", "spread_from", "spread_type", "commission",
    "commission_structure", "max_leverage", "execution_type",
    "min_lot_size", "max_lot_size", "margin_call_pct", "stop_out_pct",
    "instruments_count",
}


def _sanitize_account(acc: dict) -> dict:
    """
    Clean up an account dict: convert junk/verbose strings to None so the
    frontend displays a clean '—' instead of confusing text.
    """
    cleaned = dict(acc)
    for field in _DATA_FIELDS:
        val = cleaned.get(field)
        if val is None:
            continue
        val_str = str(val).strip()
        # Empty or whitespace-only
        if not val_str:
            cleaned[field] = None
            continue
        # Matches a known junk pattern
        if _JUNK_PATTERNS.match(val_str):
            cleaned[field] = None
            continue
        # Too long to be a real value — likely a sentence/explanation
        if len(val_str) > 80 and field != "instruments_count":
            cleaned[field] = None
            continue
    # Also sanitize list fields: empty lists → None
    for list_field in ("platforms", "base_currencies"):
        val = cleaned.get(list_field)
        if isinstance(val, list) and not val:
            cleaned[list_field] = None
    return cleaned


# ---------------------------------------------------------------------------
# HTTP fetch (plain requests, no browser needed for Layer 2/3)
# ---------------------------------------------------------------------------

def _fetch_html(url: str, timeout: int = 20) -> str | None:
    """Fetch a URL and return HTML text, or None on failure."""
    try:
        try:
            from curl_cffi import requests as curl_requests
            resp = curl_requests.get(
                url, headers=SCRAPER_HEADERS,
                impersonate="chrome120", timeout=timeout, allow_redirects=True,
            )
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text
        except ImportError:
            import requests as std_requests
            resp = std_requests.get(url, headers=SCRAPER_HEADERS, timeout=timeout)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text
    except Exception as e:
        print(f"    [fetch] Error fetching {url}: {e}")
    return None


# ---------------------------------------------------------------------------
# Claude AI extraction (shared by all layers)
# ---------------------------------------------------------------------------

def _get_claude_client():
    """Return (client, True) or (None, False) if unavailable."""
    try:
        import anthropic
    except ImportError:
        return None, False
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, False
    return anthropic.Anthropic(api_key=api_key), True


def _extract_account_types_with_claude(
    combined_text: str,
    broker_name: str,
    expected_accounts: list[str] | None = None,
    source_label: str = "official website",
) -> list[dict]:
    """
    Call Claude API to extract detailed account type specifications from page text.
    Returns list of account objects with 15+ fields each.
    """
    client, ok = _get_claude_client()
    if not ok:
        print(f"    [Claude] Not available -- skipping AI extraction for {source_label}")
        return []

    expected_hint = ""
    if expected_accounts:
        expected_hint = f"\nExpected account types for this broker: {', '.join(expected_accounts)}. Make sure to extract all of these if they appear on the page.\n"

    prompt = f"""You are extracting detailed account type specifications from a forex/CFD broker's {source_label}.

Broker: {broker_name}
{expected_hint}
Page text:
{combined_text[:20000]}

Return ONLY a valid JSON array. Each element represents one account type with this structure:
[
  {{
    "account_name": "e.g. Standard, Razor, Raw Spread, Pro",
    "min_deposit": "raw text e.g. $200 or No minimum or null",
    "spread_from": "e.g. 0.0 pips or From 1.0 pips or null",
    "spread_type": "variable or fixed or null",
    "commission": "e.g. $0 or $3.50 per lot per side or None or null",
    "commission_structure": "spread_only or commission_based or hybrid or null",
    "max_leverage": "e.g. 1:500 or Up to 1:2000 or null",
    "execution_type": "market or instant or null",
    "min_lot_size": "e.g. 0.01 or null",
    "max_lot_size": "e.g. 100 or 200 or null",
    "platforms": ["MT4", "MT5", "cTrader"],
    "base_currencies": ["USD", "EUR", "GBP"],
    "margin_call_pct": "e.g. 80% or null",
    "stop_out_pct": "e.g. 50% or null",
    "swap_free_available": true,
    "negative_balance_protection": true,
    "instruments_count": "e.g. 1200+ or null",
    "target_audience": "e.g. Beginners, Professional traders, or null",
    "notes": "any footnotes, asterisks, or additional context"
  }}
]

Rules:
- Extract ALL account types visible on the page — do not skip any
- CRITICAL: Use JSON null for any field not clearly stated on the page. NEVER use phrases like "Unable to determine", "Not available", "N/A", "Not specified", "Unknown", "Varies", "Contact broker", or "See website". If the data is not on the page, the value MUST be null.
- For commission_structure: "spread_only" = no commission (spreads include markup), "commission_based" = raw/tight spreads + per-lot commission, "hybrid" = both
- Capture exact text including symbols like $, pips, % — do not normalise
- Include footnotes or asterisks in the notes field
- If the page shows different values per platform (e.g. MT4 vs cTrader commission), note that in the notes field
- Return ONLY the JSON array, no explanation or markdown fences"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    json_match = re.search(r'\[[\s\S]*\]', raw)
    if not json_match:
        raise ValueError(f"No JSON array found in Claude response: {raw[:200]}")

    accounts = json.loads(json_match.group(0))
    if not isinstance(accounts, list):
        raise ValueError(f"Expected JSON array, got {type(accounts)}")

    return accounts


# ---------------------------------------------------------------------------
# Expected account types from config (for validation)
# ---------------------------------------------------------------------------

EXPECTED_ACCOUNTS: dict[str, list[str]] = {
    "ic-markets": ["Standard", "Raw Spread"],
    "exness": ["Standard", "Standard Cent", "Pro", "Raw Spread", "Zero"],
    "vantage": ["Standard STP", "Raw ECN", "Pro ECN"],
    "xm": ["Micro", "Standard", "Ultra Low Standard", "Ultra Low Micro", "Shares"],
    "hfm": ["Cent", "Zero", "Pro", "Pro Plus", "Premium", "Top-Up Bonus"],
    "fbs": ["Standard", "Cent", "ECN", "Zero Spread"],
    "iux": ["Standard", "Raw", "Pro"],
    "fxpro": ["Standard", "Raw+", "Elite"],
    "mitrade": ["Live"],
    "tmgm": ["Classic", "Edge"],
    "pepperstone": ["Standard", "Razor"],
}

# Layer 2: Help centre URLs for supplementary data
HELP_CENTRE_URLS: dict[str, list[str]] = {
    "exness": ["https://get.exness.help/hc/en-us/articles/360013782240-Trading-account-types"],
    "xm": ["https://www.xm.com/faq/account-types"],
    "hfm": ["https://www.hfm.com/int/en/trading/account-types/"],
    "ic-markets": ["https://www.icmarkets.com/global/en/help-centre"],
    "pepperstone": ["https://pepperstone.com/en/support"],
    "fxpro": ["https://www.fxpro.com/help-section/faq/accounts/what-account-types-do-you-offer"],
}

# Layer 3: Aggregator URLs for cross-check validation
AGGREGATOR_SLUGS: dict[str, dict[str, str]] = {
    "ic-markets": {"tradingfinder": "ic-markets", "dailyforex": "ic-markets"},
    "exness": {"tradingfinder": "exness", "dailyforex": "exness"},
    "vantage": {"tradingfinder": "vantage", "dailyforex": "vantage-fx"},
    "xm": {"tradingfinder": "xm", "dailyforex": "xm"},
    "hfm": {"tradingfinder": "hfm", "dailyforex": "hotforex"},
    "fbs": {"tradingfinder": "fbs", "dailyforex": "fbs"},
    "iux": {"tradingfinder": "iux", "dailyforex": "iux"},
    "fxpro": {"tradingfinder": "fxpro", "dailyforex": "fxpro"},
    "mitrade": {"tradingfinder": "mitrade", "dailyforex": "mitrade"},
    "tmgm": {"tradingfinder": "tmgm", "dailyforex": "tmgm"},
    "pepperstone": {"tradingfinder": "pepperstone", "dailyforex": "pepperstone"},
}


# ---------------------------------------------------------------------------
# Layer 1: Official broker pages (Playwright + Claude)
# ---------------------------------------------------------------------------

async def _scrape_layer1(page, competitor: dict) -> list[dict]:
    """Layer 1: Scrape official broker account pages via Playwright + Claude AI."""
    account_urls = competitor.get("account_urls") or [competitor.get("pricing_url", "")]
    name = competitor["name"]
    cid = competitor["id"]

    # Filter to account-type-relevant URLs
    relevant_urls = []
    for url in account_urls:
        url_lower = url.lower()
        if any(kw in url_lower for kw in ("account", "pricing", "trade/pricing")):
            relevant_urls.append(url)

    if not relevant_urls:
        relevant_urls = [account_urls[0]]
        if competitor.get("pricing_url") and competitor["pricing_url"] not in relevant_urls:
            relevant_urls.append(competitor["pricing_url"])

    print(f"    [L1 Official] Scraping {len(relevant_urls)} URL(s)")

    combined_text = ""
    for url in relevant_urls:
        try:
            await page.goto(url, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)

            # Dismiss common popups/disclaimers
            for selector in [
                'button:has-text("Accept")',
                'button:has-text("I understand")',
                'button:has-text("OK")',
                'button:has-text("Got it")',
                '[class*="cookie"] button',
                '[class*="consent"] button',
            ]:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass

            text = await page.inner_text("body")
            if text.strip():
                combined_text += f"\n\n--- Page: {url} ---\n\n{text}"
        except PlaywrightTimeout:
            print(f"    [L1 Official] Timeout loading {url}")
        except Exception as e:
            print(f"    [L1 Official] Error loading {url}: {e}")

    if not combined_text.strip():
        print(f"    [L1 Official] No text extracted for {name}")
        return []

    expected = EXPECTED_ACCOUNTS.get(cid, [])
    try:
        accounts = _extract_account_types_with_claude(combined_text, name, expected, "official website")
        print(f"    [L1 Official] Extracted {len(accounts)} account(s): {[a.get('account_name') for a in accounts]}")
        return accounts
    except Exception as e:
        print(f"    [L1 Official] Claude extraction failed for {name}: {e}")
        return []


# ---------------------------------------------------------------------------
# Layer 2: Help centre / FAQ (plain HTTP + Claude)
# ---------------------------------------------------------------------------

def _scrape_layer2(competitor: dict) -> list[dict]:
    """Layer 2: Scrape help centre / FAQ pages for supplementary account specs."""
    cid = competitor["id"]
    name = competitor["name"]
    urls = HELP_CENTRE_URLS.get(cid, [])

    if not urls:
        return []

    print(f"    [L2 Help] Fetching {len(urls)} help centre URL(s)")
    combined_text = ""
    for url in urls:
        html = _fetch_html(url)
        if html:
            # Strip HTML tags for cleaner text
            text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html)
            text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 200:
                combined_text += f"\n\n--- Help page: {url} ---\n\n{text}"

    if not combined_text.strip():
        print(f"    [L2 Help] No usable text from help centre for {name}")
        return []

    expected = EXPECTED_ACCOUNTS.get(cid, [])
    try:
        accounts = _extract_account_types_with_claude(combined_text, name, expected, "help centre / FAQ")
        print(f"    [L2 Help] Extracted {len(accounts)} account(s): {[a.get('account_name') for a in accounts]}")
        return accounts
    except Exception as e:
        print(f"    [L2 Help] Extraction failed for {name}: {e}")
        return []


# ---------------------------------------------------------------------------
# Layer 3: Aggregator cross-check (TradingFinder / DailyForex)
# ---------------------------------------------------------------------------

def _scrape_layer3_tradingfinder(competitor: dict) -> list[dict]:
    """Layer 3a: Scrape TradingFinder broker page for account type validation."""
    cid = competitor["id"]
    name = competitor["name"]
    slugs = AGGREGATOR_SLUGS.get(cid, {})
    slug = slugs.get("tradingfinder")
    if not slug:
        return []

    url = f"https://tradingfinder.com/brokers/{slug}/"
    print(f"    [L3 TradingFinder] Fetching {url}")
    html = _fetch_html(url)
    if not html:
        return []

    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html)
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) < 500:
        return []

    try:
        accounts = _extract_account_types_with_claude(text, name, source_label="TradingFinder aggregator review")
        print(f"    [L3 TradingFinder] Extracted {len(accounts)} account(s): {[a.get('account_name') for a in accounts]}")
        return accounts
    except Exception as e:
        print(f"    [L3 TradingFinder] Extraction failed for {name}: {e}")
        return []


def _scrape_layer3_dailyforex(competitor: dict) -> list[dict]:
    """Layer 3b: Scrape DailyForex broker page for account type validation."""
    cid = competitor["id"]
    name = competitor["name"]
    slugs = AGGREGATOR_SLUGS.get(cid, {})
    slug = slugs.get("dailyforex")
    if not slug:
        return []

    url = f"https://www.dailyforex.com/forex-brokers/{slug}-review"
    print(f"    [L3 DailyForex] Fetching {url}")
    html = _fetch_html(url)
    if not html:
        return []

    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html)
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) < 500:
        return []

    try:
        accounts = _extract_account_types_with_claude(text, name, source_label="DailyForex aggregator review")
        print(f"    [L3 DailyForex] Extracted {len(accounts)} account(s): {[a.get('account_name') for a in accounts]}")
        return accounts
    except Exception as e:
        print(f"    [L3 DailyForex] Extraction failed for {name}: {e}")
        return []


# ---------------------------------------------------------------------------
# Cross-source reconciliation
# ---------------------------------------------------------------------------

# Fields that are comparable across sources
RECONCILE_FIELDS = {
    "min_deposit": "high",
    "spread_from": "high",
    "commission": "high",
    "max_leverage": "high",
    "stop_out_pct": "medium",
    "margin_call_pct": "medium",
}


def _match_account_name(name: str, candidates: dict[str, dict]) -> dict | None:
    """Fuzzy-match an account name against a dict keyed by lowered names."""
    name_lower = name.lower().strip()
    # Exact match
    if name_lower in candidates:
        return candidates[name_lower]
    # Substring match (e.g. "Standard STP" matches "Standard")
    for key, val in candidates.items():
        if name_lower in key or key in name_lower:
            return val
    return None


def _reconcile_field(
    field: str,
    account_name: str,
    broker_name: str,
    values_by_source: dict[str, str | None],
) -> tuple[str | None, str, dict]:
    """
    Reconcile a single field across multiple sources.
    Returns (final_value, confidence, reconciliation_info).
    """
    non_empty = {k: v for k, v in values_by_source.items() if v is not None and str(v).strip()}

    if not non_empty:
        return None, "low", {"method": "no_data"}

    if len(non_empty) == 1:
        src = list(non_empty.keys())[0]
        return list(non_empty.values())[0], "low", {"method": "single_source", "source": src}

    # Normalise for comparison (strip whitespace, lowercase)
    normalised = {k: re.sub(r'\s+', ' ', str(v).strip().lower()) for k, v in non_empty.items()}
    unique_vals = set(normalised.values())

    # All agree
    if len(unique_vals) == 1:
        # Prefer Layer 1 (official) text since it has best formatting
        best_src = "layer1" if "layer1" in non_empty else list(non_empty.keys())[0]
        return non_empty[best_src], "high", {
            "method": "all_agree",
            "sources": list(non_empty.keys()),
        }

    # Majority agree (3+ sources)
    if len(normalised) >= 3:
        from collections import Counter
        counts = Counter(normalised.values())
        most_common_val, most_common_count = counts.most_common(1)[0]
        if most_common_count >= 2:
            majority_sources = [s for s, v in normalised.items() if v == most_common_val]
            outliers = {s: non_empty[s] for s in non_empty if s not in majority_sources}
            best_src = "layer1" if "layer1" in majority_sources else majority_sources[0]
            return non_empty[best_src], "medium", {
                "method": "majority_agree",
                "majority_sources": majority_sources,
                "outliers": outliers,
            }

    # Genuine disagreement — call Claude to reconcile
    print(f"    [Reconcile] {account_name}.{field} disagrees: {non_empty}")
    client, ok = _get_claude_client()
    if not ok:
        # Fallback to Layer 1 (official)
        for preferred in ("layer1", "layer2_help", "layer3_tradingfinder", "layer3_dailyforex"):
            if preferred in non_empty:
                return non_empty[preferred], "low", {
                    "method": "fallback_no_api_key",
                    "source": preferred,
                    "disagreement": non_empty,
                }

    try:
        source_lines = "\n".join(
            f"- {src}: {val}" for src, val in non_empty.items()
        )
        prompt = f"""You are validating account type data for the forex broker "{broker_name}".

For the "{account_name}" account, multiple sources report different values for "{field}":

{source_lines}

Source reliability order:
1. "layer1" = official broker website (most authoritative)
2. "layer2_help" = broker's own help centre / FAQ (authoritative but may be outdated)
3. "layer3_tradingfinder" = TradingFinder aggregator (generally reliable but may lag behind)
4. "layer3_dailyforex" = DailyForex aggregator (review site, may have stale data)

Which value is most likely correct? Consider that official sources may show different values for different jurisdictions/entities.

Return ONLY a JSON object:
{{
  "value": "the most likely correct value (use exact text from the most authoritative source)",
  "confidence": "high" | "medium" | "low",
  "reasoning": "1-2 sentence explanation"
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
            final_val = reconciled.get("value")
            confidence = reconciled.get("confidence", "medium")
            if final_val is not None:
                print(f"    [Reconcile] Claude chose '{final_val}' ({confidence}): {reconciled.get('reasoning', '')}")
                return str(final_val), confidence, {
                    "method": "claude_reconciled",
                    "reasoning": reconciled.get("reasoning", ""),
                    "disagreement": non_empty,
                }
    except Exception as e:
        print(f"    [Reconcile] Claude call failed for {account_name}.{field}: {e}")

    # Final fallback: prefer official sources
    for preferred in ("layer1", "layer2_help", "layer3_tradingfinder", "layer3_dailyforex"):
        if preferred in non_empty:
            return non_empty[preferred], "low", {
                "method": "fallback_reconciliation_failed",
                "source": preferred,
                "disagreement": non_empty,
            }

    return None, "low", {"method": "no_data"}


def _reconcile_accounts(
    layer1: list[dict],
    layer2: list[dict],
    layer3_tf: list[dict],
    layer3_df: list[dict],
    broker_name: str,
) -> tuple[list[dict], dict]:
    """
    Merge and reconcile account data from all layers.

    Strategy:
    - Layer 1 is the base (account names, structure, most fields)
    - Layer 2 fills in null fields from help centre
    - Layer 3 validates key fields; disagreements trigger reconciliation
    - If Layer 1 is empty, fall back to Layer 2, then Layer 3

    Returns (final_accounts, reconciliation_summary).
    """
    reconciliation_summary: dict = {
        "sources_used": [],
        "field_reconciliations": [],
        "fallback_used": None,
    }

    # Choose base accounts (Layer 1 preferred)
    if layer1:
        base_accounts = layer1
        reconciliation_summary["sources_used"].append("layer1")
    elif layer2:
        base_accounts = layer2
        reconciliation_summary["sources_used"].append("layer2_help")
        reconciliation_summary["fallback_used"] = "layer2_help"
        print(f"    [Reconcile] Layer 1 empty — falling back to Layer 2 (help centre)")
    elif layer3_tf:
        base_accounts = layer3_tf
        reconciliation_summary["sources_used"].append("layer3_tradingfinder")
        reconciliation_summary["fallback_used"] = "layer3_tradingfinder"
        print(f"    [Reconcile] Layers 1+2 empty — falling back to TradingFinder")
    elif layer3_df:
        base_accounts = layer3_df
        reconciliation_summary["sources_used"].append("layer3_dailyforex")
        reconciliation_summary["fallback_used"] = "layer3_dailyforex"
        print(f"    [Reconcile] Layers 1+2+3a empty — falling back to DailyForex")
    else:
        return [], {"sources_used": [], "error": "all_layers_empty"}

    # Index other layers by account name for lookup
    l2_map = {a.get("account_name", "").lower(): a for a in layer2} if layer2 else {}
    l3_tf_map = {a.get("account_name", "").lower(): a for a in layer3_tf} if layer3_tf else {}
    l3_df_map = {a.get("account_name", "").lower(): a for a in layer3_df} if layer3_df else {}

    if l2_map:
        reconciliation_summary["sources_used"].append("layer2_help")
    if l3_tf_map:
        reconciliation_summary["sources_used"].append("layer3_tradingfinder")
    if l3_df_map:
        reconciliation_summary["sources_used"].append("layer3_dailyforex")

    final_accounts = []

    for acc in base_accounts:
        acc_name = acc.get("account_name", "Unknown")
        merged = dict(acc)  # Start with base (Layer 1) values

        # Find matching accounts in other layers
        l2_acc = _match_account_name(acc_name, l2_map)
        l3_tf_acc = _match_account_name(acc_name, l3_tf_map)
        l3_df_acc = _match_account_name(acc_name, l3_df_map)

        # Step 1: Fill null fields from Layer 2 (supplement)
        if l2_acc:
            for field in merged:
                if merged[field] is None and l2_acc.get(field) is not None:
                    merged[field] = l2_acc[field]
                    print(f"    [Supplement] {acc_name}.{field} filled from help centre: {l2_acc[field]}")

        # Step 2: Cross-check reconcilable fields
        has_cross_source = l2_acc or l3_tf_acc or l3_df_acc
        if has_cross_source:
            for field, severity in RECONCILE_FIELDS.items():
                values_by_source: dict[str, str | None] = {"layer1": acc.get(field)}

                if l2_acc:
                    values_by_source["layer2_help"] = l2_acc.get(field)
                if l3_tf_acc:
                    values_by_source["layer3_tradingfinder"] = l3_tf_acc.get(field)
                if l3_df_acc:
                    values_by_source["layer3_dailyforex"] = l3_df_acc.get(field)

                # Only reconcile if we have 2+ non-null values that differ
                non_null = {k: v for k, v in values_by_source.items() if v is not None and str(v).strip()}
                if len(non_null) < 2:
                    continue

                # Check if they actually disagree
                normalised_vals = {re.sub(r'\s+', ' ', str(v).strip().lower()) for v in non_null.values()}
                if len(normalised_vals) <= 1:
                    continue  # All agree — no reconciliation needed

                # Disagree — reconcile
                final_val, confidence, recon_info = _reconcile_field(
                    field, acc_name, broker_name, non_null,
                )
                if final_val is not None:
                    merged[field] = final_val
                    reconciliation_summary["field_reconciliations"].append({
                        "account": acc_name,
                        "field": field,
                        "confidence": confidence,
                        "method": recon_info.get("method"),
                        "values": non_null,
                    })

        final_accounts.append(merged)

    return final_accounts, reconciliation_summary


# ---------------------------------------------------------------------------
# Main scraper (orchestrates all layers)
# ---------------------------------------------------------------------------

async def scrape_account_types(page, competitor: dict) -> dict:
    """Scrape all layers and reconcile account type data for one broker."""
    name = competitor["name"]
    cid = competitor["id"]

    # Layer 1: Official broker pages (Playwright)
    layer1 = await _scrape_layer1(page, competitor)

    # Layer 2: Help centre (plain HTTP) — run even if Layer 1 succeeds (for supplementing)
    await asyncio.sleep(1)
    layer2 = _scrape_layer2(competitor)

    # Layer 3: Aggregator cross-check (plain HTTP)
    await asyncio.sleep(1)
    layer3_tf = _scrape_layer3_tradingfinder(competitor)
    await asyncio.sleep(1)
    layer3_df = _scrape_layer3_dailyforex(competitor)

    # Log source summary
    src_counts = {
        "L1 Official": len(layer1),
        "L2 Help": len(layer2),
        "L3 TradingFinder": len(layer3_tf),
        "L3 DailyForex": len(layer3_df),
    }
    print(f"    [Sources] {name}: {src_counts}")

    # Reconcile across all layers
    accounts, reconciliation = _reconcile_accounts(layer1, layer2, layer3_tf, layer3_df, name)

    # Post-process: sanitize junk values and add category classification
    accounts = [_sanitize_account(acc) for acc in accounts]
    for acc in accounts:
        acc_name = acc.get("account_name", "")
        acc["account_category"] = _classify_account_category(acc_name)

    # Validate against expected accounts
    expected = EXPECTED_ACCOUNTS.get(cid, [])
    if expected:
        extracted_names = {a.get("account_name", "").lower() for a in accounts}
        for exp_name in expected:
            if not any(exp_name.lower() in en for en in extracted_names):
                print(f"    [Validate] WARNING: Expected account '{exp_name}' not found for {name}")

    source_urls = []
    if layer1:
        account_urls = competitor.get("account_urls") or [competitor.get("pricing_url", "")]
        source_urls.extend([u for u in account_urls if any(kw in u.lower() for kw in ("account", "pricing"))])
    source_urls.extend(HELP_CENTRE_URLS.get(cid, []))

    method = "multi_layer_reconciled" if len(reconciliation.get("sources_used", [])) > 1 else "single_layer"
    if reconciliation.get("fallback_used"):
        method = f"fallback_{reconciliation['fallback_used']}"

    print(f"    [Result] {len(accounts)} account(s) for {name} | method={method} | reconciliations={len(reconciliation.get('field_reconciliations', []))}")

    return {
        "accounts": accounts,
        "source_urls": source_urls,
        "method": method,
        "reconciliation": reconciliation,
    }


# ---------------------------------------------------------------------------
# Change detection for account types
# ---------------------------------------------------------------------------

def _detect_account_changes(conn, competitor_id: str, new_accounts: list[dict], broker_name: str, market_code: str = "global"):
    """
    Compare new account types against previous snapshot and detect changes.
    Flags: new_account, removed_account, field_changed.
    """
    row = conn.execute(
        """
        SELECT accounts_detailed_json FROM account_type_snapshots
        WHERE competitor_id = ? AND market_code = ?
        ORDER BY snapshot_date DESC
        LIMIT 1
        """,
        (competitor_id, market_code),
    ).fetchone()

    if not row or not row["accounts_detailed_json"]:
        return

    try:
        old_accounts = json.loads(row["accounts_detailed_json"])
    except (json.JSONDecodeError, TypeError):
        return

    old_names = {a.get("account_name", "").lower(): a for a in old_accounts}
    new_names = {a.get("account_name", "").lower(): a for a in new_accounts}

    # Detect new accounts
    for name_lower, acc in new_names.items():
        if name_lower not in old_names:
            acc_name = acc.get("account_name", name_lower)
            detect_change(conn, competitor_id, "account_types", "new_account", acc_name, "high", market_code=market_code)
            print(f"    [Change] New account type detected: {acc_name}")

    # Detect removed accounts
    for name_lower, acc in old_names.items():
        if name_lower not in new_names:
            acc_name = acc.get("account_name", name_lower)
            detect_change(conn, competitor_id, "account_types", "removed_account", f"REMOVED: {acc_name}", "high", market_code=market_code)
            print(f"    [Change] Account type removed: {acc_name}")

    # Detect field changes for matching accounts
    HIGH_PRIORITY_FIELDS = {"spread_from", "commission", "min_deposit", "max_leverage"}
    MEDIUM_PRIORITY_FIELDS = {"stop_out_pct", "margin_call_pct", "instruments_count"}

    for name_lower in set(old_names) & set(new_names):
        old_acc = old_names[name_lower]
        new_acc = new_names[name_lower]
        acc_name = new_acc.get("account_name", name_lower)

        for field in HIGH_PRIORITY_FIELDS | MEDIUM_PRIORITY_FIELDS:
            old_val = str(old_acc.get(field, "")) if old_acc.get(field) is not None else ""
            new_val = str(new_acc.get(field, "")) if new_acc.get(field) is not None else ""
            if old_val != new_val and (old_val or new_val):
                severity = "high" if field in HIGH_PRIORITY_FIELDS else "medium"
                detect_change(
                    conn, competitor_id, "account_types",
                    f"{acc_name}.{field}",
                    f"{old_val} -> {new_val}",
                    severity,
                    market_code=market_code,
                )
                print(f"    [Change] {acc_name}.{field}: '{old_val}' -> '{new_val}'")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _store_account_snapshot(
    conn, cid: str, snapshot_date: str, data: dict, market_code: str = "global",
    error_summary: list | None = None,
) -> int:
    """
    Guard, DELETE+INSERT an account_type_snapshot row, run change detection,
    and backfill pricing_snapshots. Returns 1 on success, 0 if skipped/error.
    """
    accounts = data.get("accounts", [])
    if not accounts:
        print(f"  WARNING: {cid}: no account types extracted — preserving existing record (market={market_code})")
        if error_summary is not None:
            error_summary.append(f"{cid}[{market_code}]: all layers empty, skipped upsert")
        return 0

    # Change detection before overwriting
    _detect_account_changes(conn, cid, accounts, cid, market_code=market_code)

    # Upsert snapshot
    conn.execute(
        "DELETE FROM account_type_snapshots WHERE competitor_id=? AND snapshot_date=? AND market_code=?",
        (cid, snapshot_date, market_code),
    )
    conn.execute(
        """
        INSERT INTO account_type_snapshots
            (competitor_id, snapshot_date, accounts_detailed_json, source_urls, extraction_method, reconciliation_json, market_code)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cid,
            snapshot_date,
            json.dumps(accounts, ensure_ascii=False),
            json.dumps(data.get("source_urls", [])),
            data.get("method", "unknown"),
            json.dumps(data.get("reconciliation", {})),
            market_code,
        ),
    )
    conn.commit()

    # Also update the simpler account_types_json in pricing_snapshots for backward compat
    account_names = [a.get("account_name") for a in accounts if a.get("account_name")]
    if account_names:
        conn.execute(
            """
            UPDATE pricing_snapshots
            SET account_types_json = ?
            WHERE competitor_id = ? AND market_code = ? AND snapshot_date = (
                SELECT MAX(snapshot_date) FROM pricing_snapshots WHERE competitor_id = ? AND market_code = ?
            )
            """,
            (json.dumps(account_names), cid, market_code, cid, market_code),
        )
        conn.commit()

    return 1


async def scrape_all(broker_filter: str | None = None, market_code: str = "global"):
    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    brokers = ALL_BROKERS
    if broker_filter:
        brokers = [b for b in ALL_BROKERS if b["id"] == broker_filter]
        if not brokers:
            print(f"ERROR: Broker '{broker_filter}' not found in config")
            update_scraper_run(run_id, "failed", 0, f"Broker '{broker_filter}' not found")
            return

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

        for competitor in brokers:
            cid = competitor["id"]
            name = competitor["name"]
            print(f"\n{'='*50}\nProcessing {name} [{market_code}]...\n{'='*50}")

            try:
                if market_code == "global":
                    data = await scrape_account_types(page, competitor)
                else:
                    # Market-specific: override account_urls if market config provides them
                    market_urls = get_market_urls(cid, market_code)
                    if market_urls and market_urls.get("method") == "url":
                        pricing_url = market_urls.get("pricing_url")
                        market_comp = {**competitor}
                        if "account_urls" in market_urls:
                            market_comp["account_urls"] = market_urls["account_urls"]
                        elif pricing_url:
                            market_comp["account_urls"] = [pricing_url]
                        print(f"    [Market {market_code}] Direct URL: {market_comp.get('account_urls', [])}")
                        data = await scrape_account_types(page, market_comp)
                    else:
                        print(f"    [Market {market_code}] Geo-proxy not supported for account types — skipping")
                        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
                        continue

                if _store_account_snapshot(conn, cid, snapshot_date, data, market_code, error_summary):
                    total_records += 1

            except Exception as e:
                msg = f"{name}[{market_code}]: {e}"
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
    import argparse
    parser = argparse.ArgumentParser(description="Account types scraper with market localisation")
    parser.add_argument("--broker", type=str, help="Single broker ID (e.g. ic-markets)")
    parser.add_argument("--market", type=str, help="Single market code (e.g. sg)")
    parser.add_argument("--markets", action="store_true", help="All priority APAC markets after global")
    args = parser.parse_args()

    if args.market:
        asyncio.run(scrape_all(args.broker, market_code=args.market))
    elif args.markets:
        async def _run_all_markets():
            markets = ["global"] + list(PRIORITY_MARKETS)
            for mc in markets:
                print(f"\n{'='*60}\n  Market: {mc.upper()}\n{'='*60}")
                await scrape_all(args.broker, market_code=mc)
        asyncio.run(_run_all_markets())
    else:
        asyncio.run(scrape_all(args.broker))

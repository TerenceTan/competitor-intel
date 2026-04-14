"""
promo_scraper.py
----------------
Multi-source promotions scraper for CFD/Forex broker competitor intelligence.

Architecture (two layers):
  Layer 1 — Official broker promo pages (Playwright + Claude AI extraction)
  Layer 2 — Aggregator sites (server-rendered HTML, parsed directly):
            • BrokersOfForex.com  (primary — well-structured, categorised)
            • BestForexBonus.com  (secondary — large table with all promos)

Flow:
  1. Scrape aggregator sites (no browser needed, fast HTTP)
  2. Per-competitor: scrape official promo page with Playwright + Claude
  3. Merge all sources, deduplicate by hash(broker + title + type)
  4. Store normalised result

Requires: ANTHROPIC_API_KEY env var, curl-cffi (pip install curl-cffi)

Run from the project root:
    python scrapers/promo_scraper.py
"""
from __future__ import annotations

import asyncio
import hashlib
import html as html_module
import json
import os
import re
import sys
import time
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

from config import DELAY_BETWEEN_REQUESTS, SCRAPER_UA, SCRAPER_HEADERS
from db_utils import get_all_brokers
COMPETITORS = get_all_brokers()
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change
from market_config import PRIORITY_MARKETS, get_market_urls

SCRAPER_NAME = "promo_scraper"

# Try curl-cffi first (WAF bypass), fall back to requests
try:
    from curl_cffi import requests as curl_requests
    _CURL_AVAILABLE = True
except ImportError:
    _CURL_AVAILABLE = False
    import requests as std_requests
    print("WARNING: curl-cffi not installed. Falling back to requests.")

# ---------------------------------------------------------------------------
# Promo type enum (from brief)
# ---------------------------------------------------------------------------
PROMO_TYPES = {
    "deposit_bonus", "no_deposit_bonus", "cashback", "contest_live",
    "contest_demo", "refer_a_friend", "loyalty", "lucky_draw",
    "vps", "free_subscription", "loss_protection", "other",
}

# ---------------------------------------------------------------------------
# Broker name normalisation — map aggregator names → config IDs
# ---------------------------------------------------------------------------
_BROKER_ALIASES: dict[str, str] = {}


def _build_broker_aliases():
    """Build lookup from various name forms → competitor id."""
    global _BROKER_ALIASES
    if _BROKER_ALIASES:
        return
    for comp in COMPETITORS:
        cid = comp["id"]
        name_lower = comp["name"].lower().strip()
        _BROKER_ALIASES[name_lower] = cid
        _BROKER_ALIASES[cid] = cid
        # Common variations
        website = comp.get("website", "").replace(".com", "").replace("www.", "").strip()
        if website:
            _BROKER_ALIASES[website.lower()] = cid
    # Manual aliases for aggregator naming quirks
    extra = {
        "xm": "xm", "xm group": "xm", "xmgroup": "xm", "xm.com": "xm",
        "hfm": "hfm", "hf markets": "hfm", "hotforex": "hfm", "hfmarkets": "hfm",
        "ic markets": "ic-markets", "icmarkets": "ic-markets",
        "vantage": "vantage", "vantage fx": "vantage", "vantagefx": "vantage",
        "vantage markets": "vantage",
        "fbs": "fbs",
        "exness": "exness",
        "fxpro": "fxpro", "fx pro": "fxpro",
        "iux": "iux", "iux markets": "iux",
        "mitrade": "mitrade",
        "tmgm": "tmgm",
        "pepperstone": "pepperstone",
    }
    _BROKER_ALIASES.update(extra)


def _resolve_broker_id(name: str) -> str | None:
    """Map an aggregator broker name to our config id. Returns None if not a target broker."""
    _build_broker_aliases()
    key = name.lower().strip()
    if key in _BROKER_ALIASES:
        return _BROKER_ALIASES[key]
    # Fuzzy: check if any alias is a substring
    for alias, cid in _BROKER_ALIASES.items():
        if len(alias) > 2 and (alias in key or key in alias):
            return cid
    return None


# ---------------------------------------------------------------------------
# HTTP fetch (for aggregator sites — server-rendered HTML)
# ---------------------------------------------------------------------------

def _fetch_html(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL and return HTML text, or None on failure."""
    try:
        if _CURL_AVAILABLE:
            resp = curl_requests.get(
                url, headers=SCRAPER_HEADERS,
                impersonate="chrome120", timeout=timeout, allow_redirects=True,
            )
        else:
            resp = std_requests.get(url, headers=SCRAPER_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        print(f"    [HTTP] {url} → {resp.status_code}")
    except Exception as e:
        print(f"    [HTTP] {url} error: {e}")
    return None


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------

def _normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for dedup comparison."""
    t = re.sub(r'[^a-z0-9\s]', '', title.lower())
    return re.sub(r'\s+', ' ', t).strip()


def _promo_hash(broker_id: str, title: str, promo_type: str = "other") -> str:
    """Generate a dedup key from broker + normalised title + type."""
    key = f"{broker_id}|{_normalise_title(title)}|{promo_type}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def _title_overlap(a: str, b: str) -> float:
    """Word-overlap ratio between two titles."""
    wa = set(re.findall(r'\b[a-z]{3,}\b', a.lower()))
    wb = set(re.findall(r'\b[a-z]{3,}\b', b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


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
    try:
        kwargs = {
            "model": "claude-haiku-4-5-20251001",
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
    if not text:
        return None
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Layer 2A — BrokersOfForex aggregator
# ---------------------------------------------------------------------------

BROKERSOFFOREX_CATEGORIES = {
    "deposit_bonus": "/promo/deposit-bonus/",
    "no_deposit_bonus": "/promo/no-deposit-bonus/",
    "contest_live": "/promo/live-contest/",
    "contest_demo": "/promo/demo-contest/",
    "loyalty": "/promo/loyalty/",
    "lucky_draw": "/promo/draw/",
    "other": "/promo/event/",
}


def _parse_bof_featured_cards(html: str, promo_type: str, base_url: str) -> list[dict]:
    """Parse <ul class="promo-list"> featured cards from BrokersOfForex."""
    promos = []
    # Find all <li class="promo-list-bonus"> or <li class="promo-list-item">
    for li_match in re.finditer(
        r'<li\s+class="promo-list-(?:bonus|item|event)"[^>]*>([\s\S]*?)</li>',
        html, re.IGNORECASE,
    ):
        block = li_match.group(1)

        # Title from <div class="promo-list-title"><h4><a href="...">Title</a></h4>
        title_m = re.search(
            r'class="promo-list-title"[^>]*>[\s\S]*?<a\s+href="([^"]*)"[^>]*>([\s\S]*?)</a>',
            block, re.IGNORECASE,
        )
        if not title_m:
            continue
        detail_url = title_m.group(1).strip()
        raw_title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
        if not raw_title:
            continue

        # Description
        desc_m = re.search(
            r'class="promo-list-description"[^>]*>[\s\S]*?<p[^>]*>([\s\S]*?)</p>',
            block, re.IGNORECASE,
        )
        description = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ""

        # Bonus size (promo-list-pool > promo-list-sepc)
        pool_m = re.search(
            r'class="promo-list-pool"[\s\S]*?class="promo-list-sepc"[^>]*>([\s\S]*?)</div>',
            block, re.IGNORECASE,
        )
        bonus_value = re.sub(r'<[^>]+>', '', pool_m.group(1)).strip() if pool_m else None

        # Dates / availability (promo-list-dates > promo-list-sepc)
        dates_m = re.search(
            r'class="promo-list-dates"[\s\S]*?class="promo-list-sepc"[^>]*>([\s\S]*?)</div>',
            block, re.IGNORECASE,
        )
        expiry = re.sub(r'<[^>]+>', '', dates_m.group(1)).strip() if dates_m else None

        # Try to extract broker name from title (usually "BrokerName PromoTitle")
        broker_name = _extract_broker_from_title(raw_title)

        promos.append({
            "broker_name_raw": broker_name or raw_title.split()[0],
            "title": raw_title,
            "description": description,
            "promo_type": promo_type,
            "bonus_value": bonus_value,
            "expiry": expiry,
            "source": "brokersofforex",
            "source_url": detail_url if detail_url.startswith("http") else f"https://en.brokersofforex.com{detail_url}",
        })

    return promos


def _parse_bof_table(html: str, promo_type: str) -> list[dict]:
    """Parse TablePress tables from BrokersOfForex category pages."""
    promos = []
    # Find tablepress tables
    for table_match in re.finditer(
        r'<table[^>]*class="[^"]*tablepress[^"]*"[^>]*>([\s\S]*?)</table>',
        html, re.IGNORECASE,
    ):
        table_html = table_match.group(1)
        # Skip header row, parse data rows
        for row_match in re.finditer(r'<tr[^>]*class="row-(\d+)"[^>]*>([\s\S]*?)</tr>', table_html, re.IGNORECASE):
            row_num = int(row_match.group(1))
            if row_num <= 1:  # Skip header
                continue
            row_html = row_match.group(2)

            # Extract cells
            cells = re.findall(r'<td[^>]*class="[^"]*column-(\d+)[^"]*"[^>]*>([\s\S]*?)</td>', row_html, re.IGNORECASE)
            cell_map = {}
            for col_num, cell_content in cells:
                cell_map[int(col_num)] = re.sub(r'<[^>]+>', ' ', cell_content).strip()

            # Column 1 = broker name (may have link)
            broker_name = cell_map.get(1, "").strip()
            # Extract link from column 1
            link_m = re.search(r'<a\s+href="([^"]*)"', cells[0][1] if cells else "")
            detail_url = link_m.group(1) if link_m else None

            # Column 2 = bonus/contest name
            bonus_name = cell_map.get(2, "").strip()
            # Column 3 = bonus size (deposit pages) or empty
            bonus_value = cell_map.get(3, "").strip() or None
            # Column 4 = min deposit (some pages)
            # Column 5 = max bonus (some pages)

            if not broker_name or not bonus_name:
                continue

            title = f"{broker_name} {bonus_name}" if broker_name.lower() not in bonus_name.lower() else bonus_name

            promos.append({
                "broker_name_raw": broker_name,
                "title": title,
                "description": "",
                "promo_type": promo_type,
                "bonus_value": bonus_value,
                "expiry": None,
                "source": "brokersofforex",
                "source_url": detail_url if detail_url and detail_url.startswith("http") else None,
            })

    return promos


def _extract_broker_from_title(title: str) -> str | None:
    """Try to extract the broker name prefix from a promo title like 'XM Group Deposit Bonus'."""
    _build_broker_aliases()
    title_lower = title.lower().strip()
    # Try matching known broker names at the start of the title
    best_match = None
    best_len = 0
    for alias in _BROKER_ALIASES:
        if title_lower.startswith(alias) and len(alias) > best_len:
            best_match = alias
            best_len = len(alias)
    if best_match:
        # Return the original-case version from the title
        return title[:best_len].strip()
    return None


def scrape_brokersofforex() -> list[dict]:
    """Scrape all BrokersOfForex category pages. Returns list of raw promo dicts."""
    print("\n--- Layer 2A: BrokersOfForex ---")
    all_promos = []

    for promo_type, path in BROKERSOFFOREX_CATEGORIES.items():
        url = f"https://en.brokersofforex.com{path}"
        print(f"  Fetching {promo_type}: {url}")
        html = _fetch_html(url)
        if not html:
            continue

        # Parse both featured cards and table rows
        featured = _parse_bof_featured_cards(html, promo_type, url)
        table = _parse_bof_table(html, promo_type)

        # Merge (featured cards are richer, table may have extras)
        combined = list(featured)
        for tp in table:
            # Skip if already in featured (by title overlap)
            if not any(_title_overlap(tp["title"], f["title"]) > 0.7 for f in featured):
                combined.append(tp)

        print(f"    → {len(combined)} promos ({len(featured)} featured + {len(table) - (len(combined) - len(featured))} unique table)")
        all_promos.extend(combined)
        time.sleep(1.5)  # Rate limit

    print(f"  BrokersOfForex total: {len(all_promos)} raw promos")
    return all_promos


# ---------------------------------------------------------------------------
# Layer 2B — BestForexBonus aggregator
# ---------------------------------------------------------------------------

def _is_noise_promo(title: str, url_path: str) -> bool:
    """Filter out non-promo content (education, news, tools, job listings)."""
    noise_keywords = (
        "education", "webinar", "course", "lesson", "tutorial", "article",
        "analysis", "forecast", "news", "guidebook", "video lesson",
        "officer", "specialist", "dealer", "junior", "senior",  # Job titles
        "analyst", "manager", "lead risk",  # More job titles
        "overview", "basics", "academy", "school",
        "podcast", "watch and learn", "trading signal", "insight",
        "ebook", "e-book", "web tv", "market sentiment",
        "technical summar", "research",
    )
    combined = (title + " " + url_path).lower()
    return any(kw in combined for kw in noise_keywords)


def scrape_bestforexbonus() -> list[dict]:
    """Scrape BestForexBonus /all page. Returns list of raw promo dicts."""
    print("\n--- Layer 2B: BestForexBonus ---")
    url = "https://www.bestforexbonus.com/all"
    html = _fetch_html(url, timeout=30)
    if not html:
        print("  Failed to fetch BestForexBonus")
        return []

    promos = []
    skipped_noise = 0
    # Parse table rows: <tr class="even|odd"> with views-field-title and views-field-created
    for row_match in re.finditer(
        r'<tr\s+class="(?:even|odd)"[^>]*>([\s\S]*?)</tr>',
        html, re.IGNORECASE,
    ):
        row_html = row_match.group(1)

        # Title cell: <td class="views-field views-field-title"><a href="...">BrokerName | Promo Title</a>
        title_m = re.search(
            r'views-field-title[^>]*>[\s\S]*?<a\s+href="([^"]*)"[^>]*>([\s\S]*?)</a>',
            row_html, re.IGNORECASE,
        )
        if not title_m:
            continue
        detail_path = title_m.group(1).strip()
        full_text = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()

        # Decode HTML entities
        full_text = html_module.unescape(full_text)

        # Split on " | " to get broker and promo name
        if " | " in full_text:
            broker_name, promo_title = full_text.split(" | ", 1)
        else:
            broker_name = full_text.split()[0] if full_text else ""
            promo_title = full_text

        # Filter out non-promo content
        if _is_noise_promo(promo_title, detail_path):
            skipped_noise += 1
            continue

        # Date cell: <td class="views-field views-field-created">
        date_m = re.search(
            r'views-field-created[^>]*>([\s\S]*?)</td>',
            row_html, re.IGNORECASE,
        )
        expiry = re.sub(r'<[^>]+>', '', date_m.group(1)).strip() if date_m else None

        # Infer promo_type from URL path or title keywords
        promo_type = _infer_promo_type(detail_path + " " + promo_title)

        source_url = f"https://www.bestforexbonus.com{detail_path}" if not detail_path.startswith("http") else detail_path

        promos.append({
            "broker_name_raw": broker_name.strip(),
            "title": promo_title.strip(),
            "description": "",
            "promo_type": promo_type,
            "bonus_value": None,
            "expiry": expiry,
            "source": "bestforexbonus",
            "source_url": source_url,
        })

    print(f"  BestForexBonus total: {len(promos)} promos ({skipped_noise} noise entries filtered)")
    return promos


def _infer_promo_type(text: str) -> str:
    """Infer promo type from keywords in text/URL."""
    t = text.lower()
    if "no-deposit" in t or "no deposit" in t or "nodeposit" in t or "free bonus" in t:
        return "no_deposit_bonus"
    if "deposit" in t and "bonus" in t:
        return "deposit_bonus"
    if "cashback" in t or "rebate" in t:
        return "cashback"
    if "demo" in t and "contest" in t:
        return "contest_demo"
    if "contest" in t or "competition" in t or "tournament" in t:
        return "contest_live"
    if "refer" in t or "referral" in t:
        return "refer_a_friend"
    if "loyalty" in t or "reward" in t:
        return "loyalty"
    if "draw" in t or "raffle" in t or "lucky" in t:
        return "lucky_draw"
    if "vps" in t:
        return "vps"
    if "tradingview" in t or "subscription" in t:
        return "free_subscription"
    if "shield" in t or "insurance" in t or "protection" in t:
        return "loss_protection"
    return "other"


# ---------------------------------------------------------------------------
# Layer 1 — Official broker promo pages (Playwright + Claude)
# ---------------------------------------------------------------------------

async def extract_promos_with_claude(page, competitor: dict, client) -> list[dict]:
    """Navigate to competitor promo page, extract with Claude for structured data."""
    promo_url = competitor.get("promo_url")
    name = competitor["name"]

    if not promo_url:
        print(f"    [{name}] No promo_url — skipping official page")
        return []

    try:
        await page.goto(promo_url, wait_until="networkidle", timeout=45000)
        await asyncio.sleep(3)

        # Handle Vantage geo-gate popup
        if "vantage" in name.lower():
            try:
                confirm_btn = page.locator("text=I CONFIRM MY INTENTION TO PROCEED")
                if await confirm_btn.is_visible(timeout=3000):
                    await confirm_btn.click()
                    await asyncio.sleep(2)
            except Exception:
                pass

        page_text = await page.inner_text("body")
        page_text = page_text[:12000]  # Truncate for token limits
    except PlaywrightTimeout:
        print(f"    [{name}] Timeout loading {promo_url}")
        return []
    except Exception as e:
        print(f"    [{name}] Error loading {promo_url}: {e}")
        return []

    if client is None:
        return []

    prompt = f"""Extract all active promotions from this forex broker's website page.
Only include genuine financial promotions. Do NOT include generic product features,
platform descriptions, or 'why trade with us' content.

Broker: {name}
Page URL: {promo_url}

Page content:
{page_text}

Return a JSON array where each item has:
{{
  "title": "promotion title/headline",
  "description": "brief description",
  "promo_type": "one of: deposit_bonus, no_deposit_bonus, cashback, contest_live, contest_demo, refer_a_friend, loyalty, lucky_draw, vps, free_subscription, loss_protection, other",
  "bonus_value": "e.g. '100%', '$30', 'up to $52,500' or null",
  "min_deposit": "e.g. '$5', '$100' or null",
  "expiry": "end date if shown, or null",
  "url": "specific promo link if available, or null"
}}

Return [] if no real promotions are found."""

    response_text = _call_claude(client, prompt)
    result = _parse_json_from_response(response_text)

    if not isinstance(result, list):
        return []

    promos = []
    for item in result:
        if isinstance(item, dict) and item.get("title"):
            extracted_url = item.pop("url", None)
            item["source"] = "official"
            item["source_url"] = extracted_url if extracted_url else promo_url
            item["broker_name_raw"] = name
            # Validate promo_type
            if item.get("promo_type") not in PROMO_TYPES:
                item["promo_type"] = _infer_promo_type(item.get("title", "") + " " + item.get("description", ""))
            promos.append(item)

    return promos


# ---------------------------------------------------------------------------
# Merge & Dedup across all sources
# ---------------------------------------------------------------------------

def merge_all_sources(
    official_promos: dict[str, list[dict]],
    aggregator_promos: list[dict],
) -> dict[str, list[dict]]:
    """
    Merge official and aggregator promos per broker, deduplicating.
    Official data always wins — aggregator data only fills gaps.
    Returns dict keyed by competitor_id → list of merged promos.
    """
    # Track which brokers had official data scraped
    brokers_with_official = set(official_promos.keys())

    # Index: competitor_id → list of promos (with dedup tracking)
    merged: dict[str, list[dict]] = {}

    # First, add official promos (highest priority — these are the source of truth)
    for cid, promos in official_promos.items():
        merged.setdefault(cid, [])
        for p in promos:
            p["_dedup_title"] = _normalise_title(p.get("title", ""))
            p["verified_official"] = True
            merged[cid].append(p)

    # Then, add aggregator promos (skip duplicates, never overwrite official data)
    for raw_promo in aggregator_promos:
        broker_raw = raw_promo.get("broker_name_raw", "")
        cid = _resolve_broker_id(broker_raw)
        if not cid:
            continue  # Not one of our target brokers

        merged.setdefault(cid, [])
        new_title = raw_promo.get("title", "")

        # Check for duplicates against existing promos for this broker
        is_dup = False
        for existing in merged[cid]:
            if _title_overlap(new_title, existing.get("title", "")) > 0.6:
                # Merge source info into existing promo
                existing.setdefault("additional_sources", [])
                existing["additional_sources"].append({
                    "source": raw_promo.get("source"),
                    "source_url": raw_promo.get("source_url"),
                })
                # Only fill in fields where official data is missing — never overwrite
                for field in ("bonus_value", "expiry", "description", "promo_type"):
                    if not existing.get(field) and raw_promo.get(field):
                        existing[field] = raw_promo[field]
                    elif existing.get(field) and raw_promo.get(field):
                        # Log discrepancy if aggregator disagrees with official
                        if (existing.get("verified_official")
                                and field in ("bonus_value", "promo_type")
                                and existing[field] != raw_promo[field]):
                            print(f"    [Validation] {cid}: aggregator {raw_promo.get('source')} "
                                  f"has {field}={raw_promo[field]!r} vs official={existing[field]!r} "
                                  f"— keeping official")
                is_dup = True
                break

        if not is_dup:
            # Mark as unverified if this broker had official data but this promo wasn't on it
            if cid in brokers_with_official:
                raw_promo["verified_official"] = False
            raw_promo["_dedup_title"] = _normalise_title(new_title)
            merged[cid].append(raw_promo)

    # Clean up internal fields before returning
    for cid in merged:
        for p in merged[cid]:
            p.pop("_dedup_title", None)
            p.pop("broker_name_raw", None)

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
        print("         Official page extraction will return empty results.")

    # --- Layer 2: Aggregator scraping (no browser needed) ---
    aggregator_promos: list[dict] = []
    try:
        bof_promos = scrape_brokersofforex()
        aggregator_promos.extend(bof_promos)
    except Exception as e:
        print(f"  BrokersOfForex error: {e}")
        error_summary.append(f"BrokersOfForex: {e}")

    try:
        bfb_promos = scrape_bestforexbonus()
        aggregator_promos.extend(bfb_promos)
    except Exception as e:
        print(f"  BestForexBonus error: {e}")
        error_summary.append(f"BestForexBonus: {e}")

    print(f"\nAggregator total: {len(aggregator_promos)} raw promos across all brokers")

    # --- Layer 1: Official page scraping (Playwright + Claude) ---
    official_promos: dict[str, list[dict]] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=SCRAPER_UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,mp4,webp}",
            lambda r: r.abort(),
        )

        for competitor in COMPETITORS:
            cid = competitor["id"]
            name = competitor["name"]

            promo_url = competitor.get("promo_url")
            if not promo_url:
                print(f"\n[{name}] No promo URL — aggregator-only")
                continue

            print(f"\n[{name}] Scraping official: {promo_url}")
            try:
                promos = await extract_promos_with_claude(page, competitor, client)
                print(f"  → {len(promos)} promo(s) extracted")
                if promos:
                    official_promos[cid] = promos
            except Exception as e:
                msg = f"{name}: {e}"
                print(f"  Error: {msg}")
                error_summary.append(msg)

            await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        await browser.close()

    # --- Merge & Dedup ---
    print("\n--- Merging and deduplicating ---")
    merged = merge_all_sources(official_promos, aggregator_promos)

    # Count target brokers with promos
    target_ids = {c["id"] for c in COMPETITORS}
    brokers_with_promos = sum(1 for cid in merged if cid in target_ids and merged[cid])
    total_promos = sum(len(v) for cid, v in merged.items() if cid in target_ids)
    print(f"  {total_promos} unique promos across {brokers_with_promos} broker(s)")

    # --- Store results (global) ---
    conn = get_db()
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for competitor in COMPETITORS:
        cid = competitor["id"]
        promos = merged.get(cid, [])
        total_records += _store_promo_snapshot(conn, cid, snapshot_date, promos, "global", error_summary)

    conn.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records: {total_records}. Status: {status}")
    if error_summary:
        print(f"Errors: {error_msg}")


def _store_promo_snapshot(
    conn, cid: str, snapshot_date: str, promos: list[dict], market_code: str = "global",
    error_summary: list | None = None,
) -> int:
    """Store a promo snapshot row and run change detection. Returns 1 on success, 0 on error."""
    try:
        promos_json = json.dumps(promos)
        conn.execute(
            "DELETE FROM promo_snapshots WHERE competitor_id=? AND snapshot_date=? AND market_code=?",
            (cid, snapshot_date, market_code),
        )
        conn.execute(
            """
            INSERT INTO promo_snapshots (competitor_id, snapshot_date, promotions_json, market_code)
            VALUES (?, ?, ?, ?)
            """,
            (cid, snapshot_date, promos_json, market_code),
        )
        conn.commit()

        # Change detection
        detect_change(conn, cid, "promos", "promo_count", str(len(promos)), "medium", market_code=market_code)
        titles = json.dumps(sorted(p.get("title", "") for p in promos if p.get("title")))
        detect_change(conn, cid, "promos", "promo_titles", titles, "medium", market_code=market_code)

        return 1
    except Exception as e:
        msg = f"{cid}[{market_code}] db: {e}"
        print(f"  DB Error: {msg}")
        if error_summary is not None:
            error_summary.append(msg)
        return 0


async def scrape_markets():
    """Scrape market-specific promo pages (Layer 1 only — aggregators are global)."""
    import argparse
    parser = argparse.ArgumentParser(description="Promo scraper — market-specific mode")
    parser.add_argument("--broker", type=str, help="Single broker ID")
    parser.add_argument("--market", type=str, help="Single market code (e.g. sg)")
    parser.add_argument("--markets", action="store_true", help="All priority APAC markets")
    args = parser.parse_args()

    brokers = list(COMPETITORS)
    if args.broker:
        brokers = [c for c in brokers if c["id"] == args.broker]
        if not brokers:
            print(f"Unknown broker: {args.broker}")
            return

    markets_to_scrape = []
    if args.market:
        markets_to_scrape = [args.market]
    elif args.markets:
        markets_to_scrape = list(PRIORITY_MARKETS)
    else:
        # No market flags — run the global scrape
        await scrape_all()
        return

    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    client = _get_anthropic_client()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=SCRAPER_UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()
        await page.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,mp4,webp}",
            lambda r: r.abort(),
        )

        conn = get_db()
        snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for market_code in markets_to_scrape:
            print(f"\n{'='*60}")
            print(f"  Market: {market_code.upper()}")
            print(f"{'='*60}")

            for competitor in brokers:
                cid = competitor["id"]
                name = competitor["name"]
                promo_url = competitor.get("promo_url")

                # Check for market-specific promo URL override
                market_urls = get_market_urls(cid, market_code)
                if market_urls and market_urls.get("promo_url"):
                    promo_url = market_urls["promo_url"]

                if not promo_url:
                    continue

                print(f"\n[{name}][{market_code}] Scraping: {promo_url}")
                try:
                    market_comp = {**competitor, "promo_url": promo_url}
                    promos = await extract_promos_with_claude(page, market_comp, client)
                    print(f"  → {len(promos)} promo(s) extracted")
                    total_records += _store_promo_snapshot(conn, cid, snapshot_date, promos, market_code, error_summary)
                except Exception as e:
                    msg = f"{name}[{market_code}]: {e}"
                    print(f"  Error: {msg}")
                    error_summary.append(msg)

                await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

        conn.close()
        await browser.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records: {total_records}. Status: {status}")


if __name__ == "__main__":
    # If --market or --markets flag is present, run market-specific mode
    if "--market" in sys.argv or "--markets" in sys.argv:
        asyncio.run(scrape_markets())
    else:
        asyncio.run(scrape_all())

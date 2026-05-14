"""One-shot SERP research for per-market competitor list curation.

For a given market code (e.g. 'sg', 'vn'), runs a curated query set through
apify/google-search-scraper with country-localized params, then scores each
known competitor on SERP visibility AND surfaces unknown domains that may
indicate competitors not yet in scrapers/config.py.

Usage:
    cd /home/ubuntu/app
    source .venv/bin/activate
    python scrapers/admin/serp_market_research.py sg
    python scrapers/admin/serp_market_research.py vn

Cost:
    apify/google-search-scraper @ ~$1.5/1000 results
    15 queries × 20 results = 300 results ≈ $0.45/market

Output:
    1. Markdown table to stdout (paste-into-doc-friendly)
    2. CSV at logs/serp_research_<market>.csv (sheet-friendly)

Does NOT write to the production DB. Read-only research.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from urllib.parse import urlparse

from dotenv import load_dotenv

_SCRAPERS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
sys.path.insert(0, _SCRAPERS_DIR)

from apify_client import ApifyClient  # noqa: E402
from config import COMPETITORS  # noqa: E402

ACTOR_ID = "apify/google-search-scraper"
COST_CAP_USD = Decimal("1.00")  # belt-and-braces; expected ~$0.45/market

# Curated query sets per market. Each set has 15 queries split:
#   5 generic intent | 5 spec/feature | 5 branded
QUERY_SETS: dict[str, list[str]] = {
    "sg": [
        # Generic intent (8 — bumped from 5 after the first SG run showed too
        # many known competitors had zero organic visibility because branded
        # queries dominated the set)
        "forex broker singapore",
        "best cfd broker singapore",
        "mt4 broker singapore",
        "mt5 broker singapore",
        "cfd trading platform singapore",
        "online trading platform singapore",
        "forex trading account singapore",
        "leveraged trading singapore",
        # Spec / feature (5)
        "lowest spread forex singapore",
        "ecn forex broker singapore",
        "islamic forex account singapore",
        "forex broker mas regulated singapore",
        "demo account forex broker singapore",
        # Branded (2 — reduced from 5; score now filters own-brand hits)
        "ic markets singapore",
        "xm broker singapore",
    ],
    "vn": [
        # Generic intent (8) — mixed Vietnamese + English. VN audience uses both
        # for financial content; English-language queries catch SEO-optimized
        # foreign brokers, Vietnamese queries catch local-language landing pages.
        "sàn forex việt nam",
        "forex broker vietnam",
        "sàn cfd việt nam",
        "mt4 broker vietnam",
        "giao dịch ngoại hối việt nam",
        "best forex broker vietnam",
        "sàn giao dịch chứng khoán quốc tế",  # international stock exchange
        "đầu tư forex việt nam",                # forex investment
        # Spec / feature (5)
        "sàn forex spread thấp việt nam",
        "sàn ecn việt nam",
        "sàn forex uy tín nhất việt nam",       # most trustworthy
        "demo forex việt nam",
        "tài khoản forex việt nam",             # forex account
        # Branded (2)
        "exness vietnam",
        "ic markets vietnam",
    ],
    # hk / tw / my / th / ph / id query sets to be added once SG + VN validate
}

# Per-competitor brand tokens for own-brand filtering. Each token is matched
# against the lowercase query with word boundaries. False-positives on
# 2-char ids (e.g. "xm") are avoided by using the full "name" from config.py
# when the id is too short.
_BRAND_TOKENS_OVERRIDE: dict[str, list[str]] = {
    "ic-markets": ["ic markets", "icmarkets"],
    "vantage": ["vantage markets", "vantage"],
    "xm": ["xm broker", "xm trading", "xm group"],  # avoid bare "xm" — too short
    "fxpro": ["fxpro", "fx pro"],
    "exness": ["exness"],
    "fbs": ["fbs"],
    "hfm": ["hfm", "hf markets", "hotforex"],
    "iux": ["iux"],
    "mitrade": ["mitrade"],
    "tmgm": ["tmgm"],
    "pepperstone": ["pepperstone"],
}

# Per-competitor domain PATTERNS for matching SERP URLs to a competitor.
# Most brokers operate multiple regional domains (exness.com, exness.eu,
# exness.com.vn, ...); config.py only stores ONE website per competitor so
# exact-domain matching missed regional variants. The first SG+VN run made
# this obvious: Exness — reportedly dominant in VN — only matched 1 own-
# brand hit because their VN landing is on exness.com.vn or exness.eu, not
# exness.com.
#
# Two pattern types:
#   - "label" patterns match if ANY dot-separated domain label CONTAINS the
#     pattern as a substring. Use for brand roots that are unique enough to
#     not false-positive (e.g. "icmarkets", "exness", "phillipnova").
#   - "exact" patterns are matched against the full domain. Use for brand
#     roots too short or ambiguous to label-match safely (e.g. "xm" matches
#     "xm.com" but should also catch "xmglobal.com" → exact list both).
_BRAND_DOMAIN_PATTERNS: dict[str, dict[str, list[str]]] = {
    "ic-markets": {"label": ["icmarkets"]},
    "exness": {"label": ["exness"]},
    "vantage": {"label": ["vantagemarkets", "vantagefx"]},
    "xm": {"exact": ["xm.com", "xmglobal.com", "xmtrading.com", "xm.co"]},
    "fxpro": {"label": ["fxpro"]},
    "fbs": {"exact": ["fbs.com", "fbs.eu", "fbs.io"]},  # bare "fbs" too short for label match
    "hfm": {"label": ["hfm", "hotforex", "hfmarkets"]},
    "iux": {"exact": ["iux.com", "iuxmarkets.com"]},
    "mitrade": {"label": ["mitrade"]},
    "tmgm": {"label": ["tmgm"]},
    "pepperstone": {"label": ["pepperstone"]},
    # ─── added 2026-05-14 from Phase 2.1 SERP market research ───
    # "ig" is 2 chars — too short for label match — use prefix (matches
    # ig.com + ig.com.sg + ig.com.au + ig.com.hk + ig.com.my + ig.com.de etc.)
    "ig": {"prefix": ["ig.com"]},
    "oanda": {"label": ["oanda"]},
    "phillip-nova": {"label": ["phillipnova"]},
    "fp-markets": {"label": ["fpmarkets"]},
    "litefinance": {"label": ["litefinance"]},
}

# Localization params for the Apify google-search-scraper actor
MARKET_PARAMS: dict[str, dict[str, str]] = {
    "sg": {"countryCode": "sg", "languageCode": "en"},
    "hk": {"countryCode": "hk", "languageCode": "en"},
    "tw": {"countryCode": "tw", "languageCode": "zh-TW"},
    "my": {"countryCode": "my", "languageCode": "en"},
    "th": {"countryCode": "th", "languageCode": "th"},
    "ph": {"countryCode": "ph", "languageCode": "en"},
    "id": {"countryCode": "id", "languageCode": "id"},
    "vn": {"countryCode": "vn", "languageCode": "vi"},
}


def _domain(url: str) -> str:
    """Extract registrable domain from a URL. Strips www. for matching."""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _match_competitor(domain: str) -> str | None:
    """Return competitor_id whose domain pattern matches `domain`, or None.

    Pattern resolution order:
      1. Exact patterns (full-domain equality)
      2. Prefix patterns (domain starts with pattern then '.' or end)
      3. Label patterns (substring within ANY dot-separated label)

    Falls back to None — surfaces the domain as "unknown" for review.
    """
    if not domain:
        return None
    labels = domain.split(".")
    for cid, patterns in _BRAND_DOMAIN_PATTERNS.items():
        for exact in patterns.get("exact", []):
            if domain == exact:
                return cid
        for prefix in patterns.get("prefix", []):
            # Match 'ig.com' AND 'ig.com.sg' AND 'ig.com.au' but NOT 'igsomething.com'
            if domain == prefix or domain.startswith(prefix + "."):
                return cid
        for label_pat in patterns.get("label", []):
            for lbl in labels:
                if label_pat in lbl:
                    return cid
    return None


def _known_competitor_ids() -> set[str]:
    """For the 'zero-presence' report — competitors in config.py NOT in
    _BRAND_DOMAIN_PATTERNS are still tracked so we know what we missed."""
    return {c["id"] for c in COMPETITORS if c.get("id")}


def run_serp(client: ApifyClient, market: str) -> list[dict]:
    """Call apify/google-search-scraper with the market's query set."""
    if market not in QUERY_SETS:
        raise SystemExit(f"ERROR: no query set defined for market '{market}'. Available: {list(QUERY_SETS)}")
    if market not in MARKET_PARAMS:
        raise SystemExit(f"ERROR: no localization params for market '{market}'.")

    queries = QUERY_SETS[market]
    params = MARKET_PARAMS[market]
    print(f"=== SERP run for market={market} ===")
    print(f"  Actor: {ACTOR_ID}")
    print(f"  Queries: {len(queries)} (top 20 results each)")
    print(f"  Localization: countryCode={params['countryCode']} languageCode={params['languageCode']}")
    print(f"  Cost cap: ${COST_CAP_USD}")

    run_input = {
        "queries": "\n".join(queries),  # actor accepts newline-separated query list
        "resultsPerPage": 20,
        "maxPagesPerQuery": 1,
        "mobileResults": False,
        "saveHtml": False,
        "saveHtmlToKeyValueStore": False,
        **params,
    }

    run = client.actor(ACTOR_ID).call(
        run_input=run_input,
        max_total_charge_usd=COST_CAP_USD,
    )
    if run is None:
        raise SystemExit("ERROR: actor.call returned None (cost cap or failure)")

    print(f"  Status: {run.get('status')}  cost: {run.get('usageTotalUsd', '(see run page)')}")
    items = list(client.dataset(run.get("defaultDatasetId")).iterate_items())
    print(f"  Dataset items: {len(items)}")
    return items


def _is_own_brand_query(query: str, competitor_id: str) -> bool:
    """A competitor ranking #1 for its own branded query ('ic markets singapore'
    for ic-markets) is trivially expected and tells us nothing about
    actual market activity. Filter those out of the score so the rule
    measures organic / cross-query visibility, not name recognition.

    Uses _BRAND_TOKENS_OVERRIDE for known competitors; falls back to the
    competitor_id (hyphen-normalized) for unknowns.
    """
    q_lower = query.lower()
    tokens = _BRAND_TOKENS_OVERRIDE.get(
        competitor_id,
        [competitor_id.replace("-", " ").lower(), competitor_id.replace("-", "").lower()],
    )
    return any(tok in q_lower for tok in tokens)


def score(items: list[dict]) -> tuple[dict, Counter]:
    """Returns ({competitor_id: stats}, Counter of unknown domains).

    Stats per competitor:
      - queries_appeared: set of query strings where they appeared (excl. own-brand)
      - ranks: list of (query, position) tuples (excl. own-brand)
      - own_brand_hits: count of own-brand appearances (informational only)
    """
    stats: dict[str, dict] = defaultdict(
        lambda: {"queries_appeared": set(), "ranks": [], "own_brand_hits": 0}
    )
    unknown_domains: Counter = Counter()

    for item in items:
        query = item.get("searchQuery", {}).get("term") or item.get("query") or ""
        # Apify google-search-scraper structure: { "searchQuery": {...},
        #                                           "organicResults": [ {url, position, ...}, ... ] }
        results = item.get("organicResults") or item.get("results") or []
        for res in results:
            url = res.get("url") or ""
            position = res.get("position") or res.get("rank") or 0
            if not url or not position:
                continue
            d = _domain(url)
            if not d:
                continue
            cid = _match_competitor(d)
            if cid:
                if _is_own_brand_query(query, cid):
                    # Trivial self-ranking; count for visibility but exclude from score
                    stats[cid]["own_brand_hits"] += 1
                else:
                    stats[cid]["queries_appeared"].add(query)
                    stats[cid]["ranks"].append((query, position))
            else:
                # Skip Google internal domains and well-known non-broker domains
                if any(skip in d for skip in (
                    "google.", "youtube.", "wikipedia.", "wikimedia.",
                    "facebook.com", "twitter.com", "x.com", "linkedin.",
                    "reddit.", "investopedia.", "forexbrokers.", "wikifx.",
                    "trustpilot.", "tradingview.", "myfxbook.",
                )):
                    continue
                unknown_domains[d] += 1

    return stats, unknown_domains


def render(stats: dict, unknown: Counter, market: str, csv_path: str) -> None:
    """Print markdown table to stdout AND write CSV."""
    rows: list[dict] = []
    for cid, s in stats.items():
        ranks = [r for _, r in s["ranks"]]
        rows.append({
            "competitor_id": cid,
            "queries_appeared": len(s["queries_appeared"]),
            "total_appearances": len(s["ranks"]),
            "best_rank": min(ranks) if ranks else None,
            "avg_rank": round(sum(ranks) / len(ranks), 1) if ranks else None,
            "own_brand_hits": s["own_brand_hits"],
        })
    rows.sort(key=lambda r: (-r["queries_appeared"], r["best_rank"] or 99))

    print(f"\n=== Per-competitor SERP visibility — market={market} ===")
    print(f"  Scoring excludes own-brand queries (e.g. 'ic markets singapore' for ic-markets)")
    print(f"  to measure organic / cross-query visibility rather than name recognition.")
    print()
    print(f"| {'competitor':14s} | queries | total | best | avg  | own-brand | confidence |")
    print(f"|{'-'*16}|---------|-------|------|------|-----------|------------|")
    for r in rows:
        # Confidence rule (post own-brand filter):
        #   strong = appeared in >=2 organic queries AND best_rank<=10
        #            (relaxed from 3 because most brokers don't dominate >2 queries
        #             after own-brand removal — empirically validated against SG run 1)
        #   medium = appeared in >=1 organic query
        #   weak   = no organic appearances (may still have own-brand hits)
        if r["queries_appeared"] >= 2 and (r["best_rank"] or 99) <= 10:
            conf = "STRONG"
        elif r["queries_appeared"] >= 1:
            conf = "medium"
        else:
            conf = "weak"
        print(f"| {r['competitor_id']:14s} | {r['queries_appeared']:>7d} | "
              f"{r['total_appearances']:>5d} | {(r['best_rank'] or '-'):>4} | "
              f"{(r['avg_rank'] or '-'):>4} | {r['own_brand_hits']:>9d} | {conf:10s} |")

    # Competitors in config.py that didn't appear at all
    all_cids = _known_competitor_ids()
    appeared = set(stats.keys())
    no_show = sorted(all_cids - appeared)
    if no_show:
        print(f"\n=== Known competitors with ZERO SERP presence in {market} ===")
        for cid in no_show:
            print(f"  {cid}")

    print(f"\n=== Top 15 UNKNOWN domains (potential new competitors) ===")
    print(f"  Domains seen in SERPs that aren't in config.py.")
    print(f"  Filter for actual broker domains; ignore portals / aggregators / forums.")
    for dom, count in unknown.most_common(15):
        print(f"  {count:>3d}× {dom}")

    # Write CSV
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w") as f:
        w = csv.DictWriter(f, fieldnames=[
            "competitor_id", "queries_appeared", "total_appearances",
            "best_rank", "avg_rank", "own_brand_hits",
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nCSV: {csv_path}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scrapers/admin/serp_market_research.py <market_code>", file=sys.stderr)
        return 1
    market = sys.argv[1].lower()
    if not os.environ.get("APIFY_API_TOKEN"):
        print("ERROR: APIFY_API_TOKEN not set in .env.local", file=sys.stderr)
        return 1
    client = ApifyClient(os.environ["APIFY_API_TOKEN"])
    print(f"Pattern-matching against {len(_BRAND_DOMAIN_PATTERNS)} known competitor brand(s)")
    items = run_serp(client, market)
    stats, unknown = score(items)
    csv_path = os.path.join(_PROJECT_ROOT, "logs", f"serp_research_{market}.csv")
    render(stats, unknown, market, csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

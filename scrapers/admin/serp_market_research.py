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
        # Generic intent
        "forex broker singapore",
        "best cfd broker singapore",
        "mt4 broker singapore",
        "mt5 broker singapore",
        "cfd trading platform singapore",
        # Spec / feature
        "lowest spread forex singapore",
        "ecn forex broker singapore",
        "islamic forex account singapore",
        "forex broker mas regulated singapore",
        "demo account forex broker singapore",
        # Branded — verifies our existing 11 + reveals unknowns via co-occurrence
        "ic markets singapore",
        "exness singapore",
        "vantage markets singapore",
        "fxpro singapore",
        "xm broker singapore",
    ],
    # vn / hk / tw / my / th / ph / id query sets to be added once SG is validated
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


def _build_competitor_domain_map() -> dict[str, str]:
    """Returns {domain: competitor_id} for every competitor in config.py.

    Multi-domain competitors (entities with .com + .co.za etc.) all map to
    the same competitor_id."""
    out: dict[str, str] = {}
    for c in COMPETITORS:
        cid = c.get("id")
        if not cid:
            continue
        if c.get("website"):
            out[_domain("https://" + c["website"]) if "://" not in c["website"] else _domain(c["website"])] = cid
        # Pull from any account_urls / pricing_url / promo_url to catch
        # market-specific subdomains like icmarkets.com vs icmarkets.com.au
        for url_field in ("pricing_url", "promo_url"):
            u = c.get(url_field)
            if u:
                d = _domain(u)
                if d:
                    out.setdefault(d, cid)
        for u in c.get("account_urls", []) or []:
            d = _domain(u)
            if d:
                out.setdefault(d, cid)
    return out


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


def score(items: list[dict], known: dict[str, str]) -> tuple[dict, Counter]:
    """Returns ({competitor_id: stats}, Counter of unknown domains).

    Stats per competitor:
      - queries_appeared: set of query strings where they appeared
      - ranks: list of (query, position) tuples
    """
    stats: dict[str, dict] = defaultdict(
        lambda: {"queries_appeared": set(), "ranks": []}
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
            cid = known.get(d)
            if cid:
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
        })
    rows.sort(key=lambda r: (-r["queries_appeared"], r["best_rank"] or 99))

    print(f"\n=== Per-competitor SERP visibility — market={market} ===")
    print(f"| {'competitor':14s} | queries | total | best | avg  | confidence |")
    print(f"|{'-'*16}|---------|-------|------|------|------------|")
    for r in rows:
        # Confidence rule:
        #   strong = appeared in >=3 queries AND best_rank<=10
        #   medium = appeared in >=1 query
        #   weak   = no appearances
        if r["queries_appeared"] >= 3 and (r["best_rank"] or 99) <= 10:
            conf = "STRONG"
        elif r["queries_appeared"] >= 1:
            conf = "medium"
        else:
            conf = "weak"
        print(f"| {r['competitor_id']:14s} | {r['queries_appeared']:>7d} | "
              f"{r['total_appearances']:>5d} | {(r['best_rank'] or '-'):>4} | "
              f"{(r['avg_rank'] or '-'):>4} | {conf:10s} |")

    # Competitors in config.py that didn't appear at all
    all_cids = {c["id"] for c in COMPETITORS}
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
            "best_rank", "avg_rank",
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
    known = _build_competitor_domain_map()
    print(f"Loaded {len(known)} known competitor domain(s) from config.py")
    items = run_serp(client, market)
    stats, unknown = score(items, known)
    csv_path = os.path.join(_PROJECT_ROOT, "logs", f"serp_research_{market}.csv")
    render(stats, unknown, market, csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

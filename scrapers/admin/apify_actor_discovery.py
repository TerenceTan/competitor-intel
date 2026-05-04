"""One-shot operator script: query Apify Store for IG / X profile scrapers
that return follower counts, and rank by pricing model + popularity.

Usage:
    cd /home/ubuntu/app
    .venv/bin/python scrapers/admin/apify_actor_discovery.py

Output: top candidates per platform with pricing summary, so the operator can
pick a cheap pay-per-result actor before running a smoke test against the
free-tier Apify account ($5/mo ceiling).
"""
import json
import sys
from urllib import request, parse


def fmt_pricing(actor: dict) -> str:
    """Boil the nested pricingInfos array down to a one-liner."""
    infos = actor.get("currentPricingInfo") or {}
    model = infos.get("pricingModel", "?")
    if model == "FLAT_PRICE_PER_MONTH":
        usd = infos.get("pricePerUnitUsd", "?")
        return f"FLAT ${usd}/mo"
    if model == "PAY_PER_EVENT":
        events = (infos.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
        # Take the FREE-tier price for the primary event (usually 'actor-start' or 'item')
        bits = []
        for ev_name, ev_info in list(events.items())[:3]:
            tiered = ev_info.get("eventTieredPricingUsd", {}).get("FREE", {})
            usd = tiered.get("tieredEventPriceUsd", "?")
            bits.append(f"{ev_name}=${usd}")
        return f"PAY_PER_EVENT [{', '.join(bits)}]"
    if model == "PAY_PER_RESULT":
        usd = infos.get("pricePerUnitUsd", "?")
        return f"PAY_PER_RESULT ${usd}/result"
    if model == "FREE":
        return "FREE"
    return f"{model} (raw: {json.dumps(infos)[:80]})"


def search(term: str, limit: int = 8) -> list[dict]:
    qs = parse.urlencode({"search": term, "limit": str(limit)})
    url = f"https://api.apify.com/v2/store?{qs}"
    with request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read().decode())
    return data.get("data", {}).get("items", [])


def show(term: str, items: list[dict]) -> None:
    print(f"\n=== Top results for: '{term}' ===")
    print(f"{'#':>2}  {'username/name':50s}  {'totalRuns':>10s}  {'rating':>6s}  pricing")
    print("-" * 140)
    for i, a in enumerate(items[:6], 1):
        ident = f"{a.get('username','?')}/{a.get('name','?')}"
        stats = a.get("stats", {})
        runs = stats.get("totalRuns", 0)
        rating = stats.get("actorReviewRating") or 0
        pricing = fmt_pricing(a)
        title = (a.get("title") or "")[:60]
        print(f"{i:>2}  {ident[:50]:50s}  {runs:>10,}  {rating:>5.2f}  {pricing}")
        if title:
            print(f"      {title}")


def main() -> int:
    # If a search term is passed as argv[1], use it as the only query.
    # Otherwise run the default IG + X sweep.
    if len(sys.argv) > 1:
        term = " ".join(sys.argv[1:])
        try:
            show(term, search(term, limit=10))
        except Exception as e:
            print(f"  !! search failed: {type(e).__name__}: {e}")
            return 1
        return 0

    queries = [
        ("instagram scraper", "Instagram (broad)"),
        ("twitter scraper", "X / Twitter (broad — for follower count)"),
        ("x twitter user profile", "X / Twitter (profile-focused)"),
    ]
    for term, label in queries:
        print(f"\n>>> {label}")
        try:
            show(term, search(term))
        except Exception as e:
            print(f"  !! search failed: {type(e).__name__}: {e}")
    print()
    print("# Look for: PAY_PER_RESULT or low PAY_PER_EVENT cost, high totalRuns,")
    print("# rating >= 4.0. Avoid FLAT_PRICE_PER_MONTH (subscription) for smoke tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

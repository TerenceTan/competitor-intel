"""One-shot smoke test: fetch X (Twitter) follower count for vantage via
kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest.

Strategy: pull 1 tweet from @vantagemkts, read follower count from the
embedded author object. Cost: $0.00025 per tweet (= $0.25/1K).

Why this actor:
  - LIMITED_PERMISSIONS (no scary "full account access" prompt like apidojo)
  - 36M runs, 4.41 rating
  - Cheapest pay-per-result X actor in the discovery list

Why not the others tried:
  - scrape.badger/twitter-user-scraper: 'Get User by ID' mode error, no
    public input schema
  - apidojo/tweet-scraper: requires full account access (security concern)

Input shape isn't publicly documented for this actor (exampleRunInput is
a placeholder), so we try several common shapes and use the first that
the actor accepts.

Usage:
    cd /home/ubuntu/app
    source .venv/bin/activate
    python scrapers/admin/apify_smoke_x.py
"""
import json
import os
import sys
from decimal import Decimal

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.local"))

from apify_client import ApifyClient  # noqa: E402

ACTOR_ID = "kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest"
# IC_Markets has no real X presence; using Vantage Markets (@vantagemkts).
HANDLE = "vantagemkts"
PER_CALL_COST_CAP_USD = Decimal("0.50")


def main() -> int:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("ERROR: APIFY_API_TOKEN not set in .env.local", file=sys.stderr)
        return 1

    print(f"=== Apify X smoke: {ACTOR_ID} → @{HANDLE} ===")
    client = ApifyClient(token)

    # Try multiple input shapes — first that the actor accepts wins.
    # All include maxItems=1 to keep cost at $0.00025/attempt.
    candidates = [
        ({"twitterHandles": [HANDLE], "maxItems": 1}, "twitterHandles"),
        ({"searchTerms": [f"from:{HANDLE}"], "maxItems": 1}, "searchTerms (from:)"),
        ({"queries": [f"from:{HANDLE}"], "maxItems": 1}, "queries"),
        ({"query": f"from:{HANDLE}", "maxItems": 1}, "query (singular)"),
        ({"startUrls": [{"url": f"https://x.com/{HANDLE}"}], "maxItems": 1}, "startUrls"),
        ({"urls": [f"https://x.com/{HANDLE}"], "maxItems": 1}, "urls"),
    ]
    run = None
    for run_input, label in candidates:
        print(f"\n--- attempt: {label} → {run_input} ---")
        try:
            run = client.actor(ACTOR_ID).call(
                run_input=run_input,
                max_total_charge_usd=PER_CALL_COST_CAP_USD,
            )
        except Exception as e:
            print(f"  !! {type(e).__name__}: {str(e)[:200]}")
            continue
        if run is None:
            print("  !! actor.call returned None")
            continue
        if run.get("status") == "FAILED":
            # Some actors return a FAILED status object instead of raising
            print(f"  !! actor FAILED: {run.get('statusMessage', '')[:200]}")
            run = None
            continue
        # Got a non-failed run — use it
        break

    if run is None:
        print("\nERROR: every input shape failed. Inspect actor docs:", file=sys.stderr)
        print(f"  https://apify.com/{ACTOR_ID}", file=sys.stderr)
        return 2

    print(f"\nrun status: {run.get('status')}")
    print(f"run id: {run.get('id')}")
    cost = run.get("usageTotalUsd") or (run.get("usage") or {}).get("totalUsd") or "(see run page)"
    print(f"cost: {cost}")

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        print("ERROR: no dataset id", file=sys.stderr)
        return 3

    items = list(client.dataset(dataset_id).iterate_items())
    print(f"dataset items: {len(items)}")
    if not items:
        print("WARNING: zero tweets returned — handle may be incorrect or X blocked the actor")
        return 4

    tweet = items[0]
    # Print top-level keys so we know the schema
    print(f"\n=== Tweet object keys ({len(tweet)} total) ===")
    print("  " + ", ".join(sorted(tweet.keys())[:30]))

    # Author info is typically nested under 'author' or 'user'
    author = tweet.get("author") or tweet.get("user") or {}
    if not author:
        # Some actors flatten author fields onto the tweet itself
        author = {k: v for k, v in tweet.items() if "follow" in k.lower() or "user" in k.lower()}

    print("\n=== Author / user object ===")
    if isinstance(author, dict):
        for k in sorted(author.keys()):
            v = author[k]
            if isinstance(v, str) and len(v) > 80:
                v = v[:80] + "..."
            elif isinstance(v, (dict, list)):
                v = f"<{type(v).__name__} len={len(v)}>"
            print(f"  {k:30s} {v}")
    else:
        print(f"  (unexpected shape: {type(author).__name__})")

    # Hunt for follower count under common key names
    follower_keys = (
        "followers", "followersCount", "followers_count",
        "publicMetrics", "public_metrics",
        "userFollowers", "userFollowersCount",
    )
    fc = None
    matched_path = None

    def _look(obj, path=""):
        if not isinstance(obj, dict):
            return None
        for k in follower_keys:
            if k in obj:
                v = obj[k]
                if isinstance(v, int):
                    return v, f"{path}.{k}".lstrip(".")
                if isinstance(v, dict) and "followers_count" in v:
                    return v["followers_count"], f"{path}.{k}.followers_count".lstrip(".")
                if isinstance(v, dict) and "followers" in v:
                    return v["followers"], f"{path}.{k}.followers".lstrip(".")
        return None

    for obj, path in [(author, "author"), (tweet, "")]:
        result = _look(obj, path)
        if result:
            fc, matched_path = result
            break

    if fc is None:
        print("\n!! Follower count not found in expected keys.")
        print("Full tweet object (first 2000 chars):")
        print(json.dumps(tweet, indent=2, default=str)[:2000])
        return 5

    print(f"\n✓ Follower count for @{HANDLE} (path '{matched_path}'): {fc:,}")
    print("\nIG + X both proven via Apify. Phase 2 paid-Apify upgrade is justified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

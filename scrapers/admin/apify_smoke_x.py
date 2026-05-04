"""One-shot smoke test: fetch X (Twitter) follower count for ic-markets via
apidojo/tweet-scraper.

Strategy: pull 1 tweet from @IC_Markets, then read follower count from the
embedded author object. Tweet-scrapers always include author metadata, so
this works as a profile-info smoke even though the actor is technically
tweet-focused.

Why not scrape.badger/twitter-user-scraper: that actor failed input
validation with an obscure 'Get User by ID' mode error and exposes no
input schema publicly. apidojo/tweet-scraper has 140M runs and a stable
documented input shape.

Usage:
    cd /home/ubuntu/app
    source .venv/bin/activate
    python scrapers/admin/apify_smoke_x.py

Cost: ~$0.04 (1 dataset item × $0.04). Cost-capped at $0.50.
"""
import json
import os
import sys
from decimal import Decimal

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.local"))

from apify_client import ApifyClient  # noqa: E402

ACTOR_ID = "apidojo/tweet-scraper"
HANDLE = "IC_Markets"
PER_CALL_COST_CAP_USD = Decimal("0.50")


def main() -> int:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("ERROR: APIFY_API_TOKEN not set in .env.local", file=sys.stderr)
        return 1

    print(f"=== Apify X smoke: {ACTOR_ID} → @{HANDLE} ===")
    client = ApifyClient(token)

    run_input = {
        "twitterHandles": [HANDLE],
        "maxItems": 1,           # one tweet is enough — author metadata is embedded
        "sort": "Latest",
    }
    print(f"run_input: {run_input}")

    run = client.actor(ACTOR_ID).call(
        run_input=run_input,
        max_total_charge_usd=PER_CALL_COST_CAP_USD,
    )
    if run is None:
        print("ERROR: actor.call returned None", file=sys.stderr)
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

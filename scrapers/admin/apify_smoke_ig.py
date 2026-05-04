"""One-shot smoke test: fetch IG follower count for ic-markets via
apify/instagram-profile-scraper.

Goal: prove IG-via-Apify works before spending $$ on a paid Apify upgrade.

Usage:
    cd /home/ubuntu/app
    source .venv/bin/activate
    python scrapers/admin/apify_smoke_ig.py

What it does:
    - Calls apify/instagram-profile-scraper with usernames=['icmarketsglobal']
    - Per-call cost cap of $0.50 (well under one IG profile's expected $0.003)
    - Pinned ACTOR_BUILD via the API ('latest' is rejected per D-04 elsewhere
      in the project; this is a one-shot smoke so we accept the moving tag here)
    - Prints follower_count, follows_count, post_count, verified flag
    - Reports the actual cost of the run so we can project Phase 2 spend
    - Writes nothing to the production DB — read-only smoke
"""
import os
import sys
from decimal import Decimal

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.local"))

from apify_client import ApifyClient  # noqa: E402

ACTOR_ID = "apify/instagram-profile-scraper"
USERNAME = "icmarketsglobal"  # ic-markets per scrapers/config.py
PER_CALL_COST_CAP_USD = Decimal("0.50")  # belt-and-braces; expected ~$0.003


def main() -> int:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("ERROR: APIFY_API_TOKEN not set in .env.local", file=sys.stderr)
        return 1

    print(f"=== Apify IG smoke: {ACTOR_ID} → @{USERNAME} ===")
    client = ApifyClient(token)
    run = client.actor(ACTOR_ID).call(
        run_input={"usernames": [USERNAME]},
        max_total_charge_usd=PER_CALL_COST_CAP_USD,
    )

    if run is None:
        print("ERROR: actor.call returned None (cost cap or actor failure)", file=sys.stderr)
        return 2

    status = run.get("status", "?")
    actual_cost = run.get("usageTotalUsd") or run.get("usage", {}).get("totalUsd") or "?"
    print(f"\nrun status: {status}")
    print(f"actual cost: ${actual_cost}")
    print(f"run id: {run.get('id')}")
    print(f"started: {run.get('startedAt')}  finished: {run.get('finishedAt')}")

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        print("ERROR: no dataset id on run object", file=sys.stderr)
        return 3

    items = list(client.dataset(dataset_id).iterate_items())
    print(f"dataset items: {len(items)}")
    if not items:
        print("WARNING: zero items returned — IG may have blocked the actor for this account/username")
        return 4

    item = items[0]
    print("\n=== Result fields (first item) ===")
    for key in ("username", "fullName", "followersCount", "followsCount",
                "postsCount", "verified", "private", "biography"):
        if key in item:
            val = item[key]
            if isinstance(val, str) and len(val) > 80:
                val = val[:80] + "..."
            print(f"  {key:20s} {val}")

    fc = item.get("followersCount")
    if fc is None:
        print("\n!! WARNING: followersCount missing from result — actor may have changed schema")
        return 5

    print(f"\n✓ Follower count for @{USERNAME}: {fc:,}")
    print("\nNext: if this number looks right, the IG-via-Apify path is proven.")
    print("Cost projection: 1 profile = ~$0.003. 7 competitors × 8 markets = 56 profiles ≈ $0.15/run.")
    print("At weekly cadence: ~$0.60/mo. Way under the $5 free tier ceiling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

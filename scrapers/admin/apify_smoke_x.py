"""One-shot smoke test: fetch X (Twitter) follower count for ic-markets via
scrape.badger/twitter-user-scraper.

Goal: prove X-via-Apify works before spending $$ on a paid Apify upgrade.

Usage:
    cd /home/ubuntu/app
    source .venv/bin/activate
    python scrapers/admin/apify_smoke_x.py

Notes:
    - Actor: scrape.badger/twitter-user-scraper (148K runs, 4.85 rating).
      Title says "Metadata, Followers, Followings & More". Pricing was
      not exposed in the Apify Store JSON — capped at $0.50 to abort
      safely if the actor charges more than expected.
    - Input shape uncertain across X user actors. Trying common keys in
      order: 'startUrls', then 'usernames', then 'twitterHandles'. The
      first that the actor accepts is the one we use.
    - Reads APIFY_API_TOKEN from .env.local. Writes nothing to DB.
"""
import os
import sys
from decimal import Decimal

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env.local"))

from apify_client import ApifyClient  # noqa: E402

ACTOR_ID = "scrape.badger/twitter-user-scraper"
HANDLE = "IC_Markets"  # ic-markets per scrapers/config.py
PROFILE_URL = f"https://x.com/{HANDLE}"
PER_CALL_COST_CAP_USD = Decimal("0.50")


def _try_call(client: ApifyClient, run_input: dict, label: str):
    print(f"\n--- attempt: {label} ---")
    print(f"  run_input: {run_input}")
    try:
        return client.actor(ACTOR_ID).call(
            run_input=run_input,
            max_total_charge_usd=PER_CALL_COST_CAP_USD,
        )
    except Exception as e:
        print(f"  !! {type(e).__name__}: {str(e)[:160]}")
        return None


def main() -> int:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("ERROR: APIFY_API_TOKEN not set in .env.local", file=sys.stderr)
        return 1

    print(f"=== Apify X smoke: {ACTOR_ID} → @{HANDLE} ===")
    client = ApifyClient(token)

    # Try multiple common input shapes — first that doesn't 400 wins
    candidates = [
        ({"startUrls": [{"url": PROFILE_URL}]}, "startUrls (object)"),
        ({"startUrls": [PROFILE_URL]}, "startUrls (string)"),
        ({"usernames": [HANDLE]}, "usernames"),
        ({"twitterHandles": [HANDLE]}, "twitterHandles"),
        ({"handles": [HANDLE]}, "handles"),
    ]

    run = None
    for run_input, label in candidates:
        run = _try_call(client, run_input, label)
        if run is not None:
            break

    if run is None:
        print("\nERROR: all input shapes rejected. Inspect the actor's input schema:", file=sys.stderr)
        print(f"  https://apify.com/{ACTOR_ID}", file=sys.stderr)
        return 2

    status = run.get("status", "?")
    actual_cost = run.get("usageTotalUsd")
    if actual_cost is None:
        actual_cost = (run.get("usage") or {}).get("totalUsd")
    if actual_cost is None:
        actual_cost = run.get("chargedEventCounts") or "(see run page)"
    print(f"\nrun status: {status}")
    print(f"actual cost: {actual_cost}")
    print(f"run id: {run.get('id')}")

    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        print("ERROR: no dataset id on run object", file=sys.stderr)
        return 3

    items = list(client.dataset(dataset_id).iterate_items())
    print(f"dataset items: {len(items)}")
    if not items:
        print("WARNING: zero items returned — X may have blocked, or actor needs different input")
        return 4

    item = items[0]
    print(f"\n=== Result fields (first item — {len(item)} keys total) ===")
    for key in sorted(item.keys()):
        val = item[key]
        if isinstance(val, str) and len(val) > 80:
            val = val[:80] + "..."
        elif isinstance(val, (dict, list)):
            val = f"<{type(val).__name__} len={len(val)}>"
        print(f"  {key:30s} {val}")

    # Hunt for follower count under common key names
    follower_keys = (
        "followersCount", "followers_count", "followers",
        "followerCount", "followerNumber", "publicFollowers",
    )
    fc = None
    matched = None
    for k in follower_keys:
        if k in item and isinstance(item[k], int):
            fc = item[k]
            matched = k
            break

    if fc is None:
        print("\n!! WARNING: no follower-count field found. Look at the keys above and pick the right one.")
        return 5

    print(f"\n✓ Follower count for @{HANDLE} (field '{matched}'): {fc:,}")
    print("\nNext: if this number looks right, X-via-Apify is proven.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
One-time backfill: write scraper_config and market_config JSON from
hardcoded config.py / market_config.py into the competitors DB table.

Usage:
    python3 scrapers/backfill_config_to_db.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_utils import get_db
from config import ALL_BROKERS
from market_config import MARKET_URLS

# Fields that live in the competitors table directly (not in scraper_config JSON)
BASE_FIELDS = {"id", "name", "tier", "website", "is_self"}


def build_scraper_config(broker: dict) -> dict:
    """Extract scraper-specific fields from a broker config dict."""
    return {k: v for k, v in broker.items() if k not in BASE_FIELDS}


def main():
    conn = get_db()
    updated = 0

    for broker in ALL_BROKERS:
        bid = broker["id"]
        scraper_config = build_scraper_config(broker)
        market_config = MARKET_URLS.get(bid)

        scraper_json = json.dumps(scraper_config, ensure_ascii=False)
        market_json = json.dumps(market_config, ensure_ascii=False) if market_config else None

        conn.execute(
            "UPDATE competitors SET scraper_config = ?, market_config = ? WHERE id = ?",
            (scraper_json, market_json, bid),
        )
        updated += 1
        print(f"  [{bid}] scraper_config={len(scraper_json)}B, market_config={len(market_json or '')}B")

    conn.commit()
    conn.close()
    print(f"\nBackfilled {updated} competitors.")


if __name__ == "__main__":
    main()

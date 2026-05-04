"""
scrapers/apify_social.py
------------------------
Apify Facebook scraper for Phase 1 — replaces the broken Thunderbit FB code path
(D-01). Calls the pinned ``apify/facebook-posts-scraper`` actor for ONE
competitor (``ic-markets``, D-05) on FB only, in the ``global`` market.

Outputs (mutually exclusive — exactly one of the first two branches runs):
  1. ``social_snapshots`` row with ``extraction_confidence`` (D-18) on success
  2. ``change_events`` row of ``field_name = "scraper_zero_results"`` and SKIP
     the snapshot insert when len(items) == 0 (D-07 / SOCIAL-04 silent-success
     guard)

ALWAYS:
  3. ``apify_run_logs`` row inserted in the ``finally`` block (success/empty/
     failure) for diagnostics — surfaced on the Plan 05 Data Health page
     (SOCIAL-05 / D-08).

Threat model (per CLAUDE.md Comments rules)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- T-01-03-01 Information Disclosure: ``install_redaction()`` is called BEFORE
  ``from apify_client import ApifyClient`` so any SDK debug logging is filtered
  through ``SecretRedactionFilter`` before reaching stdout/log files. Per the
  April 2026 EC2 incident (MEMORY.md project_ec2_compromise.md) leaked logs
  must not expose API tokens.
- T-01-03-02 DoS (financial): per-call ``max_total_charge_usd=1.00`` cap is
  belt-and-braces with the account-level $100/mo cap configured in Apify
  Console (D-06). Plus ``timeout_secs=900`` and ``resultsLimit=50``.
- T-01-03-03 Tampering (schema drift): ``ACTOR_BUILD`` is pinned to a specific
  version (D-04). Never ``:latest`` — caught by negative grep in the plan
  acceptance criteria.
- T-01-03-04 Tampering (silent-success / fake fresh data): zero-items branch
  writes a ``change_events`` row of type ``scraper_zero_results`` and SKIPS
  the snapshot insert so a stale snapshot doesn't masquerade as fresh data.
- T-01-03-06 db_utils bypass: all writes go through ``get_db()`` (WAL +
  foreign keys + parameterized SQL). No direct ``sqlite3.connect`` calls in
  this module.

Run from the project root::

    APIFY_API_TOKEN=apify_api_xxx python3 scrapers/apify_social.py
"""
from __future__ import annotations

import os
import sys
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging

from dotenv import load_dotenv

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

# CRITICAL: install log redaction BEFORE importing apify_client or any other
# library that may log secret-bearing requests. Per D-12 / INFRA-03 / the
# April 2026 EC2 incident.
from log_redaction import install_redaction  # noqa: E402
install_redaction()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

from apify_client import ApifyClient  # noqa: E402
from config import COMPETITORS  # noqa: E402  — module-level list of dicts (see scrapers/config.py)
from db_utils import get_db, log_scraper_run, update_scraper_run  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRAPER_NAME = "apify_social"  # MUST match dbName in src/lib/constants.ts SCRAPERS entry

ACTOR_ID = "apify/facebook-posts-scraper"

# ACTOR_BUILD pinned per D-04. The verified tag is recorded in
# `.planning/phases/01-foundation-apify-scaffolding-trust-schema/APIFY_BUILD_VERIFIED.txt`
# (Plan 03 Task 0 marker file). NEVER use 'latest'. If the operator updates
# the marker file with a newer stable build, this constant MUST be updated to
# match in the same commit.
ACTOR_BUILD = "0.0.293"

# Per-call cost cap belt-and-braces with the account-level $100/mo cap (D-06).
# 50 posts at $0.002 = $0.10 per call; cap at $1.00 to guard against runaway
# scrolls. Account-level cap is the primary defense — set in Apify Console.
PER_CALL_COST_CAP_USD = Decimal("1.00")
PER_RUN_TIMEOUT_SECS = 900  # 15 min (subprocess gives 30 min outer cap per INFRA-02)

PHASE_1_COMPETITOR_ID = "ic-markets"  # D-05
PHASE_1_PLATFORM = "facebook"
PHASE_1_MARKET_CODE = "global"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_followers(item: dict) -> int | None:
    """
    Apify FB actor returns followers on page metadata; field path varies by
    build. Try several known shapes defensively. Returns None when none of the
    candidates are present or positive.
    """
    if not item:
        return None
    candidates = [
        item.get("followers"),
        (item.get("page") or {}).get("followers"),
        (item.get("page") or {}).get("followersCount"),
        item.get("likesCount"),  # FB pages often expose likes as a follower proxy
    ]
    for c in candidates:
        if isinstance(c, (int, float)) and c > 0:
            return int(c)
    return None


def _is_within_7d(timestamp_str: str | None) -> bool:
    """Return True iff the timestamp string parses to a UTC time within 7 days of now."""
    if not timestamp_str:
        return False
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() <= 7 * 86400
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------
def run():
    """Phase 1: scrape ic-markets FB via Apify, write to social_snapshots OR change_events."""
    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        logger.error("APIFY_API_TOKEN not set — aborting")
        sys.exit(1)

    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary: list[str] = []
    apify_run_obj: dict = {}
    items: list[dict] = []
    apify_status = "failed"
    err_msg: str | None = None

    try:
        client = ApifyClient(api_token)
        snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # D-05: derive the FB URL from scrapers/config.py — do NOT hardcode the slug.
        # COMPETITORS is the existing source of truth for competitor handles.
        competitor = next(c for c in COMPETITORS if c["id"] == PHASE_1_COMPETITOR_ID)
        fb_url = f"https://www.facebook.com/{competitor['facebook_slug']}"

        # D-03 (synchronous .call() — no webhooks/async polling) + D-04 (pinned
        # build) + RESEARCH.md Pattern 1.
        run_input = {
            "startUrls": [{"url": fb_url}],
            "resultsLimit": 50,
        }
        logger.info("Calling actor %s build=%s", ACTOR_ID, ACTOR_BUILD)
        apify_run_obj = client.actor(ACTOR_ID).call(
            run_input=run_input,
            build=ACTOR_BUILD,                           # D-04 — never 'latest'
            max_total_charge_usd=PER_CALL_COST_CAP_USD,  # D-06 belt-and-braces
            timeout_secs=PER_RUN_TIMEOUT_SECS,
        )
        # apify_run_obj fields: id, defaultDatasetId, status, usageTotalUsd,
        # startedAt, finishedAt.

        items = client.dataset(apify_run_obj["defaultDatasetId"]).list_items().items
        logger.info(
            "Actor returned %d items, status=%s",
            len(items),
            apify_run_obj.get("status"),
        )

        with closing(get_db()) as conn:
            if len(items) == 0:
                # D-07 / SOCIAL-04: zero-result silent-success guard.
                # Write change_events row, SKIP social_snapshots insert.
                conn.execute(
                    """
                    INSERT INTO change_events
                      (competitor_id, domain, field_name, old_value, new_value,
                       severity, detected_at, market_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        PHASE_1_COMPETITOR_ID,
                        f"social_{PHASE_1_PLATFORM}",
                        "scraper_zero_results",
                        None,
                        json.dumps(
                            {
                                "actor_id": ACTOR_ID,
                                "actor_version": ACTOR_BUILD,
                                "apify_run_id": apify_run_obj.get("id"),
                                "platform": PHASE_1_PLATFORM,
                            }
                        ),
                        "medium",
                        datetime.now(timezone.utc).isoformat(),
                        PHASE_1_MARKET_CODE,
                    ),
                )
                conn.commit()
                apify_status = "empty"
                logger.warning(
                    "Zero-result run: wrote change_events row (no snapshot insert)"
                )
            else:
                # D-18: extraction_confidence — "high" when both followers and
                # posts_last_7d are derivable from the dataset; "medium" otherwise.
                follower_count = _extract_followers(items[0])
                posts_last_7d = sum(
                    1 for it in items if _is_within_7d(it.get("time") or it.get("timestamp"))
                )
                # WR-04 fix: sum() always returns int >=0, never None — the previous "is not None" check
                # was always True, so the rule was effectively "high if follower_count else medium"
                # (docstring above promised the harder condition). Real rule per the contract:
                # "high" requires BOTH a follower count AND at least one parseable post in the last 7d.
                # A run that returns 50 items but every timestamp fails to parse will now correctly
                # report confidence="medium" instead of falsely reporting "high".
                confidence = "high" if (follower_count and posts_last_7d > 0) else "medium"

                # Insert social_snapshots row directly (column count requires
                # explicit SQL; mirror _upsert_social shape from social_scraper.py).
                conn.execute(
                    "DELETE FROM social_snapshots "
                    "WHERE competitor_id=? AND platform=? AND market_code=? AND snapshot_date=?",
                    (
                        PHASE_1_COMPETITOR_ID,
                        PHASE_1_PLATFORM,
                        PHASE_1_MARKET_CODE,
                        snapshot_date,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO social_snapshots
                      (competitor_id, platform, snapshot_date, followers,
                       posts_last_7d, latest_post_url, market_code, extraction_confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        PHASE_1_COMPETITOR_ID,
                        PHASE_1_PLATFORM,
                        snapshot_date,
                        follower_count,
                        posts_last_7d,
                        items[0].get("url") or items[0].get("postUrl"),
                        PHASE_1_MARKET_CODE,
                        confidence,
                    ),
                )
                conn.commit()
                total_records = 1
                apify_status = "success"
                logger.info(
                    "Wrote social_snapshots row: followers=%s posts_last_7d=%s confidence=%s",
                    follower_count,
                    posts_last_7d,
                    confidence,
                )

    except Exception as e:
        err_msg = str(e)
        apify_status = "failed"
        error_summary.append(f"apify_social: {e}")
        logger.exception("Apify scraper failed")

    finally:
        # SOCIAL-05 / D-08 / RESEARCH.md Pattern 3: ALWAYS write apify_run_logs row.
        try:
            with closing(get_db()) as conn:
                conn.execute(
                    """
                    INSERT INTO apify_run_logs
                      (scraper_run_id, apify_run_id, actor_id, actor_version,
                       competitor_id, platform, market_code, status,
                       dataset_count, cost_usd, error_message,
                       started_at, finished_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        apify_run_obj.get("id"),
                        ACTOR_ID,
                        ACTOR_BUILD,
                        PHASE_1_COMPETITOR_ID,
                        PHASE_1_PLATFORM,
                        PHASE_1_MARKET_CODE,
                        apify_status,
                        len(items) if items else 0,
                        float(apify_run_obj.get("usageTotalUsd") or 0.0),
                        err_msg,
                        apify_run_obj.get("startedAt") or datetime.now(timezone.utc).isoformat(),
                        apify_run_obj.get("finishedAt"),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.exception("Failed to insert apify_run_logs row: %s", e)

        status = "success" if not error_summary else "partial"
        update_scraper_run(run_id, status, total_records, "; ".join(error_summary) or None)


if __name__ == "__main__":
    run()

import sqlite3
import json
import os
from datetime import datetime, timezone

# Resolve DB path relative to project root (one level up from this file's directory)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Import DB_PATH from config, but resolve it against project root
try:
    from config import DB_PATH as _DB_PATH_RAW
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import DB_PATH as _DB_PATH_RAW

# Noise-floor thresholds for change detection (see change_thresholds.py).
try:
    from change_thresholds import should_register_change
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from change_thresholds import should_register_change

# Module-level counters for the noise-floor metric.
# log_scraper_run() resets these at the start of each run; update_scraper_run()
# persists them to scraper_runs at the end. Scrapers run sequentially via cron,
# so a single global counter is safe (not thread-safe, but not needed).
_noise_counters = {"raw_deltas": 0, "registered_events": 0}

# DB_PATH = os.path.join(_PROJECT_ROOT, _DB_PATH_RAW.lstrip("./"))
DB_PATH = _DB_PATH_RAW if os.path.isabs(_DB_PATH_RAW) else os.path.join(_PROJECT_ROOT, _DB_PATH_RAW.lstrip("./"))


def get_db() -> sqlite3.Connection:
    """Return a WAL-mode SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Additive migration: is_self flag (safe to run repeatedly)
    try:
        conn.execute("ALTER TABLE competitors ADD COLUMN is_self INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Additive migration: spread data from WikiFX
    try:
        conn.execute("ALTER TABLE pricing_snapshots ADD COLUMN spread_json TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Additive migration: cross-source leverage validation columns
    for col in (
        "leverage_sources_json", "leverage_confidence", "leverage_reconciliation_json",
        "min_deposit_sources_json", "min_deposit_confidence", "min_deposit_reconciliation_json",
    ):
        try:
            conn.execute(f"ALTER TABLE pricing_snapshots ADD COLUMN {col} TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists

    # Additive migration: account_type_snapshots table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_type_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competitor_id TEXT NOT NULL REFERENCES competitors(id),
            snapshot_date TEXT NOT NULL,
            accounts_detailed_json TEXT,
            source_urls TEXT,
            extraction_method TEXT,
            reconciliation_json TEXT
        )
    """)
    conn.commit()

    # Additive migration: reconciliation_json column (for existing tables)
    try:
        conn.execute("ALTER TABLE account_type_snapshots ADD COLUMN reconciliation_json TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists

    # Additive migration: market_code column for market-level localisation
    for table in ("pricing_snapshots", "promo_snapshots", "account_type_snapshots", "change_events"):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN market_code TEXT NOT NULL DEFAULT 'global'")
            conn.commit()
        except Exception:
            pass  # column already exists

    # Additive migration: scraper_config + market_config columns for DB-driven competitor config
    for col in ("scraper_config", "market_config"):
        try:
            conn.execute(f"ALTER TABLE competitors ADD COLUMN {col} TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists

    # Additive migration: noise-floor metric columns on scraper_runs
    # raw_deltas_count         = # of diffs detected before threshold filtering
    # registered_events_count  = # of diffs that actually became change_events rows
    # Healthy signal-to-noise ratio: registered << raw
    for col in ("raw_deltas_count", "registered_events_count"):
        try:
            conn.execute(f"ALTER TABLE scraper_runs ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
            conn.commit()
        except Exception:
            pass  # column already exists

    # Ensure Pepperstone exists as the self-benchmark row
    conn.execute(
        """
        INSERT OR IGNORE INTO competitors (id, name, tier, website, is_self)
        VALUES ('pepperstone', 'Pepperstone', 1, 'pepperstone.com', 1)
        """
    )
    conn.commit()

    return conn


def log_scraper_run(scraper_name: str, status: str, records: int = 0, error: str = None) -> int:
    """
    Insert a new row into scraper_runs and return its rowid (run_id).
    status is typically 'running' when called at the start.

    Also resets the noise-floor counters for this run so that the
    raw_deltas_count / registered_events_count written by update_scraper_run()
    reflect only the work done by the scraper that just started.
    """
    _noise_counters["raw_deltas"] = 0
    _noise_counters["registered_events"] = 0

    conn = get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO scraper_runs (scraper_name, started_at, status, records_processed, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scraper_name, datetime.now(timezone.utc).isoformat(), status, records, error),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_scraper_run(run_id: int, status: str, records: int = 0, error: str = None):
    """
    Update an existing scraper_run row to reflect completion.
    Sets finished_at to now and persists the noise-floor counters accumulated
    by detect_change() during this run.
    """
    conn = get_db()
    try:
        conn.execute(
            """
            UPDATE scraper_runs
            SET finished_at = ?,
                status = ?,
                records_processed = ?,
                error_message = ?,
                raw_deltas_count = ?,
                registered_events_count = ?
            WHERE rowid = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                status,
                records,
                error,
                _noise_counters["raw_deltas"],
                _noise_counters["registered_events"],
                run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def detect_change(
    conn: sqlite3.Connection,
    competitor_id: str,
    domain: str,
    field: str,
    new_value,
    severity: str,
    market_code: str = "global",
) -> bool:
    """
    Look up the most recent change_event for (competitor_id, domain, field, market_code).
    If new_value differs from old new_value AND the delta clears the noise floor
    configured in change_thresholds.py, write a new change_event row and return True.
    Otherwise return False.

    new_value is stored/compared as a string so JSON blobs and numbers are
    handled uniformly.

    The noise-floor filter lives in should_register_change() — see
    change_thresholds.py for the rationale and the per-field thresholds.
    First-time values (no prior change_event row) always register, so the
    filter only applies to actual diffs.
    """
    if new_value is None:
        print(f"  [detect_change] Skipping {competitor_id}/{domain}/{field} — new_value is None")
        return False

    new_str = json.dumps(new_value) if not isinstance(new_value, str) else new_value

    # Fetch the most recent recorded value for this field + market
    row = conn.execute(
        """
        SELECT new_value FROM change_events
        WHERE competitor_id = ? AND domain = ? AND field_name = ? AND market_code = ?
        ORDER BY detected_at DESC
        LIMIT 1
        """,
        (competitor_id, domain, field, market_code),
    ).fetchone()

    old_str = row["new_value"] if row else None

    if old_str == new_str:
        return False  # No delta at all — not even counted as a raw delta.

    # We have a genuine diff. Count it before applying the noise filter so
    # the noise-floor metric reflects how much the thresholds are suppressing.
    _noise_counters["raw_deltas"] += 1

    # First-time values (no prior row) always register — nothing to compare
    # against, and the user wants to see the initial baseline in the feed.
    if old_str is not None:
        should_register, effective_severity = should_register_change(
            domain, field, old_str, new_str, severity
        )
        if not should_register:
            # Below the noise floor — skip the insert. Caller sees this as
            # "no meaningful change", same as if the value had been unchanged.
            return False
    else:
        effective_severity = severity

    conn.execute(
        """
        INSERT INTO change_events (competitor_id, domain, field_name, old_value, new_value, severity, detected_at, market_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            competitor_id,
            domain,
            field,
            old_str,
            new_str,
            effective_severity,
            datetime.now(timezone.utc).isoformat(),
            market_code,
        ),
    )
    conn.commit()
    _noise_counters["registered_events"] += 1
    return True


def upsert_competitor(conn: sqlite3.Connection, competitor: dict):
    """Insert or replace a competitor record."""
    conn.execute(
        """
        INSERT OR REPLACE INTO competitors (id, name, tier, website, is_self)
        VALUES (:id, :name, :tier, :website, :is_self)
        """,
        {
            "id": competitor["id"],
            "name": competitor["name"],
            "tier": competitor["tier"],
            "website": competitor["website"],
            "is_self": 1 if competitor.get("is_self") else 0,
        },
    )
    conn.commit()


def get_all_brokers() -> list:
    """
    Read all competitors from DB with their scraper_config JSON merged in.
    Returns same dict shape as config.py ALL_BROKERS for backward compatibility.
    Falls back to hardcoded config.py if scraper_config is empty.
    """
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM competitors ORDER BY tier, name").fetchall()
        brokers = []
        for row in rows:
            raw_config = row["scraper_config"]
            if not raw_config:
                # No DB config yet — skip (fallback handled by caller)
                continue
            config = json.loads(raw_config)
            broker = {
                "id": row["id"],
                "name": row["name"],
                "tier": row["tier"],
                "website": row["website"],
                "is_self": bool(row["is_self"]),
                **config,
            }
            brokers.append(broker)
        return brokers
    finally:
        conn.close()


def get_market_urls_from_db(competitor_id: str, market_code: str):
    """
    Read market-specific URL config for a competitor from the DB.
    Returns dict with "method" key, or None if not configured.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT market_config FROM competitors WHERE id = ?",
            (competitor_id,),
        ).fetchone()
        if not row or not row["market_config"]:
            return None
        market_config = json.loads(row["market_config"])
        return market_config.get(market_code)
    finally:
        conn.close()

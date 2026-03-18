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

#DB_PATH = os.path.join(_PROJECT_ROOT, _DB_PATH_RAW.lstrip("./"))
DB_PATH = _DB_PATH_RAW if os.path.isabs(_DB_PATH_RAW) else os.path.join(_PROJECT_ROOT, _DB_PATH_RAW.lstrip("./"))


def get_db() -> sqlite3.Connection:
    """Return a WAL-mode SQLite connection with row_factory set."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def log_scraper_run(scraper_name: str, status: str, records: int = 0, error: str = None) -> int:
    """
    Insert a new row into scraper_runs and return its rowid (run_id).
    status is typically 'running' when called at the start.
    """
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
    Sets finished_at to now.
    """
    conn = get_db()
    try:
        conn.execute(
            """
            UPDATE scraper_runs
            SET finished_at = ?,
                status = ?,
                records_processed = ?,
                error_message = ?
            WHERE rowid = ?
            """,
            (datetime.now(timezone.utc).isoformat(), status, records, error, run_id),
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
) -> bool:
    """
    Look up the most recent change_event for (competitor_id, domain, field).
    If new_value differs from old new_value (or no prior record exists), write
    a new change_event row and return True.  Otherwise return False.

    new_value is stored/compared as a string so that JSON blobs and numbers
    are handled uniformly.
    """
    if new_value is None:
        # Nothing to compare; skip recording a change.
        return False

    new_str = json.dumps(new_value) if not isinstance(new_value, str) else new_value

    # Fetch the most recent recorded value for this field
    row = conn.execute(
        """
        SELECT new_value FROM change_events
        WHERE competitor_id = ? AND domain = ? AND field_name = ?
        ORDER BY detected_at DESC
        LIMIT 1
        """,
        (competitor_id, domain, field),
    ).fetchone()

    old_str = row["new_value"] if row else None

    if old_str == new_str:
        return False  # No change

    conn.execute(
        """
        INSERT INTO change_events (competitor_id, domain, field_name, old_value, new_value, severity, detected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            competitor_id,
            domain,
            field,
            old_str,
            new_str,
            severity,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return True


def upsert_competitor(conn: sqlite3.Connection, competitor: dict):
    """Insert or replace a competitor record."""
    conn.execute(
        """
        INSERT OR REPLACE INTO competitors (id, name, tier, website)
        VALUES (:id, :name, :tier, :website)
        """,
        competitor,
    )
    conn.commit()

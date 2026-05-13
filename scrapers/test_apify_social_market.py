"""
scrapers/test_apify_social_market.py
------------------------------------
Phase 2 tests for the per-market social fanout — exercises (a) the Wave 0
parse_target_markets + APAC_V1_MARKETS surface from plan 02-02, and (b) the
plan 02-03 _proxy_config helper plus mock-Apify integration tests for the
per-market loop (snapshot writes, change_events scraper_zero_results,
apify_run_logs market_code).

Run from project root:
    python3 -m unittest scrapers.test_apify_social_market
    python3 -m unittest scrapers.test_apify_social_market -v
    python3 scrapers/test_apify_social_market.py

Discoverable via:
    python3 -m unittest discover scrapers/

Uses stdlib unittest only (no pytest dependency) so the suite runs on a bare
EC2 Python install without any pip installs — matches Phase 1 D-22 convention
established by scrapers/test_log_redaction.py and scrapers/test_run_all_smoke.py.

Integration tests (TestRunFacebookMarketLoop) monkeypatch ApifyClient to
avoid burning Apify budget — they exercise the real INSERT SQL against an
in-memory sqlite database, with the relevant CREATE TABLE statements copied
verbatim from src/db/schema.ts / scrapers/db_utils.py so they remain
faithful to the production schema.
"""
import os
import sqlite3
import sys
import unittest
from unittest.mock import MagicMock, patch

# Make scrapers/ importable so we can `from market_config import ...` whether
# invoked via `python3 -m unittest scrapers.test_apify_social_market` (package
# import) or directly via `python3 scrapers/test_apify_social_market.py`.
# Same pattern as scrapers/test_log_redaction.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from market_config import (  # noqa: E402  — sys.path tweak must run first
    APAC_V1_MARKETS,
    PRIORITY_MARKETS,
    parse_target_markets,
)

# apify_social import is guarded — local dev environments without
# `apify-client` installed (e.g. CI without the SDK) can still run the
# parse_target_markets tests. The proxy/integration suites are skipped via
# unittest.skipIf when the import fails.
try:
    # Stub apify_client BEFORE importing apify_social so the SDK isn't required
    # locally. The integration tests monkeypatch apify_social.ApifyClient
    # anyway, so the real SDK is never called from this test module.
    if "apify_client" not in sys.modules:
        _stub = type(sys)("apify_client")
        _stub.ApifyClient = MagicMock  # type: ignore[attr-defined]
        sys.modules["apify_client"] = _stub
    import apify_social  # noqa: E402
    from apify_social import _proxy_config, run_facebook  # noqa: E402

    APIFY_SOCIAL_IMPORTABLE = True
    APIFY_SOCIAL_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover — only fires when import wiring breaks
    APIFY_SOCIAL_IMPORTABLE = False
    APIFY_SOCIAL_IMPORT_ERROR = repr(e)


class TestParseTargetMarkets(unittest.TestCase):
    """Behavior contract for parse_target_markets(env_value)."""

    def test_none_returns_global(self):
        self.assertEqual(parse_target_markets(None), ["global"])

    def test_empty_string_returns_global(self):
        self.assertEqual(parse_target_markets(""), ["global"])

    def test_whitespace_only_returns_global(self):
        self.assertEqual(parse_target_markets("   "), ["global"])

    def test_global_token_passes_through(self):
        self.assertEqual(parse_target_markets("global"), ["global"])

    def test_single_market(self):
        self.assertEqual(parse_target_markets("sg"), ["sg"])

    def test_multiple_markets_preserves_order(self):
        self.assertEqual(
            parse_target_markets("sg,my,th"), ["sg", "my", "th"]
        )

    def test_case_and_whitespace_normalised(self):
        # Uppercase, mixed case, and stray whitespace all collapse to the
        # lowercase canonical form.
        cases = [
            ("SG, MY ", ["sg", "my"]),
            ("  sg ,  my  ", ["sg", "my"]),
            ("Sg,mY", ["sg", "my"]),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(parse_target_markets(raw), expected)

    def test_unknown_codes_silently_dropped(self):
        # 'xx' is not in APAC_V1_MARKETS; should be skipped, not raise.
        self.assertEqual(parse_target_markets("sg,xx,my"), ["sg", "my"])

    def test_only_commas_returns_global_fallback(self):
        # Degenerate input — all tokens empty after split — must still
        # fall back to ['global'] rather than returning [].
        self.assertEqual(parse_target_markets(",,,"), ["global"])

    def test_global_alongside_market_codes(self):
        # 'global' is a valid token and can coexist with market codes.
        self.assertEqual(
            parse_target_markets("global,sg"), ["global", "sg"]
        )

    def test_only_unknown_codes_returns_global_fallback(self):
        # Belt-and-braces: if EVERY token is unknown, we must still return
        # ['global'] (free-tier-safe default) rather than [].
        self.assertEqual(parse_target_markets("xx,yy,zz"), ["global"])


class TestApacV1Markets(unittest.TestCase):
    """Invariants for the canonical APAC_V1_MARKETS list (D2-01)."""

    def test_apac_v1_markets_length_is_8(self):
        self.assertEqual(len(APAC_V1_MARKETS), 8)

    def test_apac_v1_markets_contains_all_8_codes(self):
        self.assertEqual(
            set(APAC_V1_MARKETS),
            {"sg", "hk", "tw", "my", "th", "ph", "id", "vn"},
        )

    def test_apac_v1_markets_excludes_out_of_scope_codes(self):
        # cn + mn are out of scope per ROADMAP Out-of-Scope table.
        self.assertNotIn("cn", APAC_V1_MARKETS)
        self.assertNotIn("mn", APAC_V1_MARKETS)

    def test_priority_markets_mirrors_apac_v1(self):
        # Catches future drift if a hand-edit re-introduces cn/mn or drops ph.
        self.assertEqual(list(PRIORITY_MARKETS), list(APAC_V1_MARKETS))


# ---------------------------------------------------------------------------
# Plan 02-03: _proxy_config helper unit tests
# ---------------------------------------------------------------------------
@unittest.skipIf(not APIFY_SOCIAL_IMPORTABLE,
                 f"apify_social not importable: {APIFY_SOCIAL_IMPORT_ERROR}")
class TestProxyConfig(unittest.TestCase):
    """Contract for apify_social._proxy_config(market_code) — RESEARCH §1
    Pattern 1 + Pitfall 1 (lowercase MarketCode must be uppercased before
    being passed to Apify's apifyProxyCountry, which validates against the
    regex ^[A-Z]{2}$)."""

    def test_proxy_config_global(self):
        # 'global' explicitly returns {useApifyProxy: True} with NO
        # apifyProxyCountry key — preserves Phase 1 datacenter-anywhere
        # routing.
        result = _proxy_config("global")
        self.assertEqual(result, {"useApifyProxy": True})
        self.assertNotIn("apifyProxyCountry", result)

    def test_proxy_config_sg(self):
        # Lowercase 'sg' must round-trip to uppercase 'SG' per Apify regex.
        self.assertEqual(
            _proxy_config("sg"),
            {"useApifyProxy": True, "apifyProxyCountry": "SG"},
        )

    def test_proxy_config_all_8_apac_markets(self):
        # Every APAC v1 code uppercases correctly. Belt-and-braces against
        # silently dropping a market when the canonical list grows.
        for code in APAC_V1_MARKETS:
            with self.subTest(code=code):
                result = _proxy_config(code)
                self.assertTrue(result["useApifyProxy"])
                self.assertEqual(result["apifyProxyCountry"], code.upper())
                # Apify regex check: 2 uppercase ASCII letters.
                self.assertRegex(result["apifyProxyCountry"], r"^[A-Z]{2}$")


# ---------------------------------------------------------------------------
# Plan 02-03: Mock-Apify integration tests for run_facebook market threading
# ---------------------------------------------------------------------------

# CREATE TABLE statements copied from src/db/schema.ts and scrapers/db_utils.py
# so the in-memory sqlite mirrors the production schema. Drop the FK
# constraints in social_snapshots / apify_run_logs / change_events because the
# test does not seed the competitors table.
_TEST_SCHEMA_SQL = [
    """
    CREATE TABLE scraper_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scraper_name TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        error_message TEXT,
        records_processed INTEGER DEFAULT 0,
        raw_deltas_count INTEGER NOT NULL DEFAULT 0,
        registered_events_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE social_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competitor_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        followers INTEGER,
        posts_last_7d INTEGER,
        engagement_rate REAL,
        latest_post_url TEXT,
        market_code TEXT NOT NULL DEFAULT 'global',
        extraction_confidence TEXT
    )
    """,
    """
    CREATE TABLE change_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competitor_id TEXT NOT NULL,
        domain TEXT NOT NULL,
        field_name TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        severity TEXT NOT NULL,
        detected_at TEXT NOT NULL,
        market_code TEXT NOT NULL DEFAULT 'global'
    )
    """,
    """
    CREATE TABLE apify_run_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scraper_run_id INTEGER,
        apify_run_id TEXT,
        actor_id TEXT NOT NULL,
        actor_version TEXT,
        competitor_id TEXT NOT NULL,
        platform TEXT NOT NULL,
        market_code TEXT NOT NULL DEFAULT 'global',
        status TEXT NOT NULL,
        dataset_count INTEGER DEFAULT 0,
        cost_usd REAL,
        error_message TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT
    )
    """,
]


def _build_fake_apify_client(pages_items, posts_items):
    """Construct a MagicMock ApifyClient whose .actor(actor_id).call(...) and
    .dataset(dataset_id).iterate_items() return deterministic fixtures.

    Two actors are exercised by run_facebook:
      - FB_PAGES_ACTOR_ID -> pages_items dataset
      - FB_ACTOR_ID       -> posts_items dataset
    """
    fake_pages_run = {
        "id": "fake-pages-run-id",
        "defaultDatasetId": "pages-dataset",
        "status": "SUCCEEDED",
        "startedAt": "2026-05-13T00:00:00Z",
        "finishedAt": "2026-05-13T00:01:00Z",
    }
    fake_posts_run = {
        "id": "fake-posts-run-id",
        "defaultDatasetId": "posts-dataset",
        "status": "SUCCEEDED",
        "startedAt": "2026-05-13T00:01:30Z",
        "finishedAt": "2026-05-13T00:02:30Z",
    }

    pages_actor = MagicMock()
    pages_actor.call.return_value = fake_pages_run
    posts_actor = MagicMock()
    posts_actor.call.return_value = fake_posts_run

    pages_dataset = MagicMock()
    pages_dataset.iterate_items.return_value = iter(pages_items)
    posts_dataset = MagicMock()
    posts_dataset.iterate_items.return_value = iter(posts_items)

    def _actor_router(actor_id):
        if actor_id == apify_social.FB_PAGES_ACTOR_ID:
            return pages_actor
        if actor_id == apify_social.FB_ACTOR_ID:
            return posts_actor
        raise AssertionError(f"unexpected actor_id in test: {actor_id!r}")

    def _dataset_router(dataset_id):
        if dataset_id == "pages-dataset":
            return pages_dataset
        if dataset_id == "posts-dataset":
            return posts_dataset
        raise AssertionError(f"unexpected dataset_id in test: {dataset_id!r}")

    client = MagicMock()
    client.actor.side_effect = _actor_router
    client.dataset.side_effect = _dataset_router
    return client


@unittest.skipIf(not APIFY_SOCIAL_IMPORTABLE,
                 f"apify_social not importable: {APIFY_SOCIAL_IMPORT_ERROR}")
class TestRunFacebookMarketLoop(unittest.TestCase):
    """Mock-Apify integration tests proving market_code threads end-to-end
    from run_facebook's positional arg into the actual INSERT SQL for
    social_snapshots, change_events, and apify_run_logs (per RESEARCH §1
    Pattern 2 + D2-04 / Pitfall 5)."""

    SNAPSHOT_DATE = "2026-05-13"
    TARGETS = [("comp-a", "testpage")]

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        for stmt in _TEST_SCHEMA_SQL:
            self.conn.execute(stmt)
        self.conn.commit()
        # Seed a scraper_runs row so the FK-less integer reference is realistic.
        cur = self.conn.execute(
            "INSERT INTO scraper_runs (scraper_name, started_at, status) "
            "VALUES (?, ?, ?)",
            ("apify_social", "2026-05-13T00:00:00Z", "running"),
        )
        self.run_id = cur.lastrowid
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_market_code_threaded_into_social_snapshots(self):
        """run_facebook(..., market_code='my') writes a social_snapshots row
        with market_code='my' (not the DEFAULT_MARKET_CODE='global')."""
        pages_items = [{
            "pageUrl": "https://www.facebook.com/testpage",
            "followers": 12000,
            "likes": 9500,
        }]
        posts_items = [{
            "pageUrl": "https://www.facebook.com/testpage",
            "url": "https://www.facebook.com/testpage/posts/abc123",
            # 'time' is checked by _is_within_7d — leave None so we hit the
            # 'no posts within 7d' path. Followers > 0 still satisfies the
            # 'page_items or follower_count' write branch.
            "likesCount": 42,
            "commentsCount": 7,
            "sharesCount": 3,
        }]
        client = _build_fake_apify_client(pages_items, posts_items)

        written, errors = run_facebook(
            client, self.conn, self.run_id, self.SNAPSHOT_DATE,
            self.TARGETS, market_code="my",
        )

        self.assertEqual(errors, [], f"unexpected errors: {errors}")
        self.assertEqual(written, 1)

        rows = self.conn.execute(
            "SELECT competitor_id, platform, market_code, followers "
            "FROM social_snapshots"
        ).fetchall()
        self.assertEqual(len(rows), 1, "expected exactly one social_snapshots row")
        self.assertEqual(rows[0]["competitor_id"], "comp-a")
        self.assertEqual(rows[0]["platform"], "facebook")
        self.assertEqual(rows[0]["market_code"], "my")
        self.assertEqual(rows[0]["followers"], 12000)
        # The confidence rule from D2-15: high IFF followers > 0 AND
        # posts_last_7d > 0. Our fixture has posts_last_7d == 0 (no 'time'
        # field on the post), so it should land 'medium'.
        confidence = self.conn.execute(
            "SELECT extraction_confidence FROM social_snapshots"
        ).fetchone()["extraction_confidence"]
        self.assertEqual(confidence, "medium")

    def test_zero_result_writes_change_event_with_market_code(self):
        """When both FB actors return zero items, run_facebook should write
        a change_events scraper_zero_results row tagged with market_code='my'
        and NOT write a social_snapshots row (SOCIAL-04 zero-result guard)."""
        client = _build_fake_apify_client(pages_items=[], posts_items=[])

        written, errors = run_facebook(
            client, self.conn, self.run_id, self.SNAPSHOT_DATE,
            self.TARGETS, market_code="my",
        )

        self.assertEqual(errors, [], f"unexpected errors: {errors}")
        self.assertEqual(written, 0)

        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM social_snapshots").fetchone()[0],
            0,
            "zero-result path must NOT write a social_snapshots row",
        )
        change_rows = self.conn.execute(
            "SELECT competitor_id, domain, field_name, severity, market_code "
            "FROM change_events"
        ).fetchall()
        self.assertEqual(len(change_rows), 1)
        self.assertEqual(change_rows[0]["competitor_id"], "comp-a")
        self.assertEqual(change_rows[0]["domain"], "social_facebook")
        self.assertEqual(change_rows[0]["field_name"], "scraper_zero_results")
        self.assertEqual(change_rows[0]["market_code"], "my")
        self.assertEqual(change_rows[0]["severity"], "medium")

    def test_apify_run_logs_records_market_code(self):
        """apify_run_logs row written on every iteration carries the loop's
        market_code (D2-04 / Pitfall 5: forgetting to pass market_code here
        silently records 'global' for per-market runs)."""
        pages_items = [{
            "pageUrl": "https://www.facebook.com/testpage",
            "followers": 12000,
            "likes": 9500,
        }]
        posts_items = [{
            "pageUrl": "https://www.facebook.com/testpage",
            "url": "https://www.facebook.com/testpage/posts/abc123",
            "likesCount": 42, "commentsCount": 7, "sharesCount": 3,
        }]
        client = _build_fake_apify_client(pages_items, posts_items)

        run_facebook(
            client, self.conn, self.run_id, self.SNAPSHOT_DATE,
            self.TARGETS, market_code="my",
        )

        rows = self.conn.execute(
            "SELECT competitor_id, platform, market_code, actor_id, status "
            "FROM apify_run_logs"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["competitor_id"], "comp-a")
        self.assertEqual(rows[0]["platform"], "facebook")
        self.assertEqual(rows[0]["market_code"], "my")
        self.assertEqual(rows[0]["actor_id"], apify_social.FB_ACTOR_ID)
        self.assertEqual(rows[0]["status"], "success")


if __name__ == "__main__":
    unittest.main()

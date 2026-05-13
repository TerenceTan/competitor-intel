"""
scrapers/test_apify_social_market.py
------------------------------------
Wave 0 tests for Phase 2 plan 02-02 — exercises parse_target_markets and the
APAC_V1_MARKETS constant in scrapers/market_config.py BEFORE Plan 02-03 lands
the apify_social.py refactor that consumes them.

Plan 02-03 will extend this file with mock-Apify integration tests for the
per-market loop (snapshot writes, apify_run_logs market_code, _proxy_config
helper).

Run from project root:
    python3 -m unittest scrapers.test_apify_social_market
    python3 -m unittest scrapers.test_apify_social_market -v
    python3 scrapers/test_apify_social_market.py

Discoverable via:
    python3 -m unittest discover scrapers/

Uses stdlib unittest only (no pytest dependency) so the suite runs on a bare
EC2 Python install without any pip installs — matches Phase 1 D-22 convention
established by scrapers/test_log_redaction.py and scrapers/test_run_all_smoke.py.

Test coverage maps 1:1 to plan 02-02 Task 2 behaviors plus the locked
D2-01 8-market list and the PRIORITY_MARKETS-mirrors-APAC_V1_MARKETS
invariant (catches future drift if a hand-edit re-introduces cn/mn).
"""
import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()

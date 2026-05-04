"""Smoke tests for scrapers/run_all.py — timeout handling + healthcheck no-op behavior.

Plan 01-04 Task 2 — these tests exercise the new behavior in isolation:
  - No real Apify calls, no real subprocess, no real network.
  - Mock requests.get to verify _ping_healthcheck shape (URL + 5s timeout).
  - Verify the PER_SCRAPER_TIMEOUT_SECS = 1800 constant (D-11 hard cap).
  - Verify apify_social.py registered in SCRIPTS list (Plan 03 wiring intact).

The timeout behavior of subprocess.run(timeout=) is documented Python stdlib;
we deliberately do NOT mock subprocess at this layer (RESEARCH.md Pattern 4
"Don't Hand-Roll" — trust the stdlib).

Run with:  python3 -m unittest scrapers.test_run_all_smoke
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class RunAllSmokeTests(unittest.TestCase):

    def setUp(self):
        # Ensure HC URL is unset for the no-op test
        self._saved_hc = os.environ.pop("HEALTHCHECK_URL_APIFY_SOCIAL", None)

    def tearDown(self):
        if self._saved_hc is not None:
            os.environ["HEALTHCHECK_URL_APIFY_SOCIAL"] = self._saved_hc
        else:
            # Belt-and-braces: ensure no test pollution leaks the env var
            os.environ.pop("HEALTHCHECK_URL_APIFY_SOCIAL", None)

    def test_ping_healthcheck_no_op_when_env_var_missing(self):
        """No HEALTHCHECK_URL_* env var → silent no-op, no requests.get call."""
        import run_all
        with patch("run_all.requests.get") as mock_get:
            run_all._ping_healthcheck("apify_social.py")
            mock_get.assert_not_called()

    def test_ping_healthcheck_pings_when_env_var_set(self):
        """HEALTHCHECK_URL_* env var present → requests.get called with that URL and 5s timeout."""
        os.environ["HEALTHCHECK_URL_APIFY_SOCIAL"] = "https://hc-ping.com/test-uuid-not-real"
        try:
            import run_all
            with patch("run_all.requests.get") as mock_get:
                mock_get.return_value = MagicMock(status_code=200)
                run_all._ping_healthcheck("apify_social.py")
                mock_get.assert_called_once()
                args, kwargs = mock_get.call_args
                self.assertEqual(args[0], "https://hc-ping.com/test-uuid-not-real")
                self.assertEqual(kwargs.get("timeout"), 5)
        finally:
            del os.environ["HEALTHCHECK_URL_APIFY_SOCIAL"]

    def test_ping_healthcheck_silent_on_network_error(self):
        """requests.get raises → ping returns silently (HC.io missed-ping alarm catches it)."""
        os.environ["HEALTHCHECK_URL_APIFY_SOCIAL"] = "https://hc-ping.com/test-uuid-not-real"
        try:
            import run_all
            with patch("run_all.requests.get", side_effect=ConnectionError("boom")):
                # Should NOT raise
                run_all._ping_healthcheck("apify_social.py")
        finally:
            del os.environ["HEALTHCHECK_URL_APIFY_SOCIAL"]

    def test_per_scraper_timeout_constant_is_1800(self):
        """D-11: 30-min hard cap."""
        import run_all
        self.assertEqual(run_all.PER_SCRAPER_TIMEOUT_SECS, 1800)

    def test_apify_social_in_scripts_list(self):
        """Plan 03 scraper registered in SCRIPTS."""
        import run_all
        self.assertIn("apify_social.py", run_all.SCRIPTS)


if __name__ == "__main__":
    unittest.main()

"""
scrapers/test_log_redaction.py
------------------------------
Unit tests for scrapers/log_redaction.py — verifies secret redaction works
on real token-shaped inputs.

Run from project root:
    python3 -m unittest scrapers.test_log_redaction
    python3 scrapers/test_log_redaction.py

Uses stdlib unittest only (no pytest dependency) so the suite runs on a
bare EC2 Python install without any pip installs.

Test coverage maps 1:1 to plan 01-02 Task 2 behaviors:
  1. test_redacts_apify_token_from_env       — env var value redaction
  2. test_redacts_bearer_token_pattern       — Bearer regex
  3. test_redacts_apify_api_pattern          — apify_api_ regex
  4. test_redacts_anthropic_pattern          — sk-ant- regex
  5. test_passes_innocent_message_unchanged  — no false positives
  6. test_install_redaction_idempotent       — no double-attach
  7. test_redacts_healthcheck_url_value      — HEALTHCHECK_URL_* env value
"""
import logging
import os
import sys
import unittest

# Make scrapers/ importable so we can `from log_redaction import ...`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class SecretRedactionFilterTests(unittest.TestCase):

    # Env vars this suite mutates; tearDown pops them so tests don't pollute
    # each other or the developer environment.
    _MANAGED_ENV_VARS = (
        "APIFY_API_TOKEN",
        "HEALTHCHECK_URL_APIFY_SOCIAL",
    )

    def _make_record(self, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def setUp(self):
        # Reset root logger filters between tests so idempotency tests start
        # from a clean state.
        root = logging.getLogger()
        for f in list(root.filters):
            root.removeFilter(f)

    def tearDown(self):
        # Remove any filters this test may have installed.
        root = logging.getLogger()
        for f in list(root.filters):
            root.removeFilter(f)
        # Pop any env vars we set so we don't leak into the next test or
        # the developer's shell.
        for name in self._MANAGED_ENV_VARS:
            os.environ.pop(name, None)

    def test_redacts_apify_token_from_env(self):
        os.environ["APIFY_API_TOKEN"] = "apify_api_TESTKEYabcd1234"
        from log_redaction import SecretRedactionFilter
        f = SecretRedactionFilter()
        record = self._make_record(
            "Calling Apify with token=apify_api_TESTKEYabcd1234"
        )
        f.filter(record)
        self.assertIn("[REDACTED]", record.getMessage())
        self.assertNotIn("apify_api_TESTKEYabcd1234", record.getMessage())

    def test_redacts_bearer_token_pattern(self):
        from log_redaction import SecretRedactionFilter
        f = SecretRedactionFilter()
        record = self._make_record(
            "Authorization: Bearer abc123_xyz-456-very-long-token"
        )
        f.filter(record)
        msg = record.getMessage()
        self.assertIn("[REDACTED]", msg)
        self.assertNotIn("abc123_xyz-456-very-long-token", msg)

    def test_redacts_apify_api_pattern(self):
        from log_redaction import SecretRedactionFilter
        f = SecretRedactionFilter()
        record = self._make_record("token=apify_api_aBcDeFgHiJkLmNoPqRsTuV")
        f.filter(record)
        msg = record.getMessage()
        self.assertIn("[REDACTED]", msg)
        self.assertNotIn("apify_api_aBcDeFgHiJkLmNoPqRsTuV", msg)

    def test_redacts_anthropic_pattern(self):
        from log_redaction import SecretRedactionFilter
        f = SecretRedactionFilter()
        record = self._make_record("key=sk-ant-abcdefghijklmnopqrstuvwx")
        f.filter(record)
        msg = record.getMessage()
        self.assertIn("[REDACTED]", msg)
        self.assertNotIn("sk-ant-abcdefghijklmnopqrstuvwx", msg)

    def test_passes_innocent_message_unchanged(self):
        from log_redaction import SecretRedactionFilter
        f = SecretRedactionFilter()
        innocent = "Scraper completed successfully"
        record = self._make_record(innocent)
        f.filter(record)
        self.assertEqual(record.getMessage(), innocent)

    def test_install_redaction_idempotent(self):
        from log_redaction import SecretRedactionFilter, install_redaction
        install_redaction()
        install_redaction()
        matching = [
            f for f in logging.getLogger().filters
            if isinstance(f, SecretRedactionFilter)
        ]
        self.assertEqual(
            len(matching), 1,
            "install_redaction should attach exactly one SecretRedactionFilter "
            "to the root logger even when called multiple times",
        )

    def test_redacts_healthcheck_url_value(self):
        os.environ["HEALTHCHECK_URL_APIFY_SOCIAL"] = (
            "https://hc-ping.com/uuid-not-real-but-long-enough"
        )
        from log_redaction import SecretRedactionFilter
        f = SecretRedactionFilter()
        record = self._make_record(
            "Pinging healthcheck at https://hc-ping.com/uuid-not-real-but-long-enough"
        )
        f.filter(record)
        msg = record.getMessage()
        self.assertIn("[REDACTED]", msg)
        self.assertNotIn(
            "https://hc-ping.com/uuid-not-real-but-long-enough", msg
        )


if __name__ == "__main__":
    unittest.main()

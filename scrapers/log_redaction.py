"""
scrapers/log_redaction.py
-------------------------
Root-logger filter that strips known secret values + common token patterns
from every log record before any handler writes. Per CLAUDE.md error-handling
rules and the April 2026 EC2 security incident history (MEMORY.md
``project_ec2_compromise.md``), no API key or credential should ever appear in
scraper stdout or log files.

Threat model
~~~~~~~~~~~~
A leaked log file (committed accidentally to git, attached to a Jira/Slack
ticket, or read by a compromised process on the EC2 host) must not expose
secrets. The April 2026 EC2 compromise is the canonical reason this module
exists: had the box's logs contained API tokens at the time of the breach,
the blast radius would have widened beyond a single rebuild.

Defenses applied per log record:

1. Replace VALUES of known secret-bearing env vars (``APIFY_API_TOKEN``,
   ``ANTHROPIC_API_KEY``, ``HEALTHCHECK_URL_*``, etc.) with ``[REDACTED]``.
2. Apply regex patterns for common token shapes (Bearer tokens,
   ``apify_api_*``, ``sk-ant-*``, 40+ char hex blobs) to catch tokens that
   are not in the env var list (defense in depth).

Install at the top of every scraper entry-point BEFORE any other logging::

    from log_redaction import install_redaction
    install_redaction()

This module is greenfield: no in-repo analog. Existing scrapers use
``print()`` exclusively; the filter is a no-op on ``print`` output. New
scrapers (apify_social.py — Plan 03; calibration/validate_extraction.py —
Plan 01-06) use ``logging`` and benefit from this filter.
"""
from __future__ import annotations

import logging
import os
import re

# Env vars whose VALUES must be redacted from log output (not just the keys).
# UPPER_SNAKE_CASE per CLAUDE.md naming convention; leading underscore marks
# this as module-private.
_SECRET_ENV_VARS = (
    "APIFY_API_TOKEN",
    "ANTHROPIC_API_KEY",
    "YOUTUBE_API_KEY",
    "THUNDERBIT_API_KEY",     # legacy — still in env until cutover validated
    "SCRAPERAPI_KEY",         # legacy
    "DASHBOARD_PASSWORD",
    "GOOGLE_APPLICATION_CREDENTIALS",  # path, but redact in case path leaks UUID-y dir
)

# Healthcheck URLs are also secret: anyone with the URL can spoof a success
# ping and silence the missed-ping alarm. Treat any env var starting with
# this prefix as a secret value.
_SECRET_ENV_PREFIX = "HEALTHCHECK_URL_"

# Generic token patterns — defense in depth for tokens that aren't in env
# (e.g., a token pasted into an error message from an external API response).
# Pre-compiled at module load for sub-microsecond per-record cost.
_TOKEN_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"apify_api_[A-Za-z0-9]+"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),       # Anthropic tokens
    re.compile(r"\b[A-Fa-f0-9]{40,}\b"),         # generic hex tokens (40+ chars)
]

# Minimum length for an env-var value to be treated as a secret. Avoids
# redacting trivially short values (e.g., DASHBOARD_PASSWORD="x" in tests)
# that would over-match innocent log content.
_MIN_SECRET_LEN = 6


class SecretRedactionFilter(logging.Filter):
    """
    logging.Filter subclass that replaces secret values with ``[REDACTED]``
    in every log record's message before it reaches any handler.

    Snapshots env-var values at construction (NOT at filter() call time) so
    the filter is stable even if the environment is mutated mid-run. This
    means rotated secrets only take effect on the next ``install_redaction()``
    call — acceptable trade-off because scraper processes are short-lived
    cron invocations.
    """

    def __init__(self) -> None:
        super().__init__()
        self._secrets: list[str] = []

        # Pick up known secret-bearing env vars by exact name.
        for name in _SECRET_ENV_VARS:
            val = os.environ.get(name)
            if val and len(val) >= _MIN_SECRET_LEN:
                self._secrets.append(val)

        # Pick up any env var matching the HEALTHCHECK_URL_ prefix (one per
        # scheduled scraper per Plan 04 / D-10).
        for name, val in os.environ.items():
            if name.startswith(_SECRET_ENV_PREFIX) and val and len(val) >= _MIN_SECRET_LEN:
                self._secrets.append(val)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Redact secrets in ``record.msg`` (and clear ``record.args``) when a
        replacement happened. Always returns True — this is a redactor, not
        a dropper; we never want a log call to silently disappear because
        of a redaction error.
        """
        try:
            msg = record.getMessage()
        except Exception:
            # If formatting blows up (bad %-args, etc.), don't try to redact
            # — just let the original record through and let the handler's
            # error path deal with it.
            return True

        redacted = msg

        # Pass 1: literal env-var values.
        for secret in self._secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, "[REDACTED]")

        # Pass 2: regex token patterns (defense in depth).
        for pattern in _TOKEN_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)

        if redacted != msg:
            # Replace msg with the redacted string and clear args so the
            # logging machinery doesn't try to re-format and double-apply
            # %-substitution against a string that no longer contains the
            # original placeholders.
            record.msg = redacted
            record.args = ()

        return True


def install_redaction() -> None:
    """
    Attach a ``SecretRedactionFilter`` to the root logger so every handler
    downstream (StreamHandler, FileHandler, etc.) sees redacted records.

    Idempotent: if the root logger already has a ``SecretRedactionFilter``
    attached, this is a no-op. Safe to call from multiple scraper entry-points
    that may run in the same process.

    Performance note: filter cost is sub-microsecond per log call (literal
    ``str.replace`` plus pre-compiled regex on a typical sub-1KB log line).
    Negligible compared to subprocess + network IO that dominates scraper
    runtime.
    """
    root = logging.getLogger()
    if not any(isinstance(f, SecretRedactionFilter) for f in root.filters):
        root.addFilter(SecretRedactionFilter())

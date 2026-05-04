"""
run_all.py
----------
Runs all scraper scripts in sequence and reports overall status.
Output is printed to stdout AND written to logs/<scraper-name>.log

Run from the project root:
    python scrapers/run_all.py

Optional environment variables:
    YOUTUBE_API_KEY    - required for social_scraper.py
    ANTHROPIC_API_KEY  - required for ai_analyzer.py
"""

import subprocess
import sys
import os
import time
from datetime import datetime

import requests

# Always run from the project root so relative DB paths work correctly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRAPERS_DIR = os.path.join(PROJECT_ROOT, "scrapers")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# CRITICAL: install log redaction at orchestrator startup (D-12 / INFRA-03).
# Threat model anchor: April 2026 EC2 incident (see scrapers/log_redaction.py
# module docstring) — leaked logs MUST NOT contain API tokens, healthcheck URLs,
# or other secret-bearing values.
#
# Coverage map (current Phase 1 reality — code review WR-05 / Plan 01-10):
#   - run_all.py itself: PROTECTED. install_redaction() below attaches the
#     SecretRedactionFilter to the root logger so any logging.* call this
#     orchestrator makes is filtered. Note: run_all.py's existing print()
#     statements (header banner + status lines + log_path writes) bypass the
#     filter by design — print() writes to sys.stdout directly and is not
#     interceptable by a logging.Filter. Acceptable because run_all.py prints
#     only its own static control-flow strings; it never echoes scraper
#     output OR env-var values to stdout.
#   - Child subprocesses that USE the filter (2 of 9):
#       * scrapers/apify_social.py — calls install_redaction() before
#         `from apify_client import ApifyClient` (the SDK debug-logs HTTP
#         requests including Authorization headers; the filter strips them).
#       * scrapers/calibration/validate_extraction.py — calls install_redaction()
#         before importing promo_scraper (Anthropic SDK debug-logs requests).
#   - Child subprocesses that DO NOT use the filter (7 of 9, residual risk):
#       pricing_scraper.py, account_types_scraper.py, promo_scraper.py,
#       social_scraper.py, reputation_scraper.py, wikifx_scraper.py,
#       news_scraper.py, ai_analyzer.py. These use print() exclusively;
#       print() bypasses logging filters by design, so wrapping them in
#       install_redaction() would NOT protect them. The migration path is
#       to move each scraper's print() calls to logging.info() incrementally
#       as Phase 2-5 touches them — Phase 2 will already touch social_scraper.py
#       for IG/X fanout, that is the right moment to migrate it.
#   - Operator hygiene compensating control: SCRAPERAPI_KEY / THUNDERBIT_API_KEY /
#     ANTHROPIC_API_KEY / YOUTUBE_API_KEY values are never echoed to stdout by the
#     7 print()-using scrapers under their current code paths (audited at Plan 01-02
#     time; no f-string or %-format includes a secret env var as a positional argument).
#
# Net trust posture: Phase 1 protects the new Apify code path (where the worst
# secret leak risk lives — fresh SDK with verbose default logging) and accepts
# documented residual risk on the legacy print()-using scrapers, with a named
# migration path tied to phases that will already be touching those files.
if SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, SCRAPERS_DIR)
from log_redaction import install_redaction
install_redaction()

SCRIPTS = [
    "pricing_scraper.py",
    "account_types_scraper.py",
    "promo_scraper.py",
    "social_scraper.py",
    "apify_social.py",          # Phase 1 — Apify FB cutover (Plan 03)
    "reputation_scraper.py",
    "wikifx_scraper.py",
    "news_scraper.py",
    "ai_analyzer.py",
]

# Per-scraper subprocess timeout (D-11 / INFRA-02). 30 minutes hard cap so one
# hung scraper cannot block the entire pipeline; subprocess.run handles
# kill+wait+pipe-drain internally on TimeoutExpired (no Popen hand-rolling).
PER_SCRAPER_TIMEOUT_SECS = 1800  # 30 min hard cap per D-11 / INFRA-02
HEALTHCHECK_PING_TIMEOUT_SECS = 5  # never block scraper completion on HC.io being slow


def _log_name(script_name: str) -> str:
    """Convert e.g. 'pricing_scraper.py' → 'pricing-scraper'."""
    return script_name.replace("_", "-").replace(".py", "")


def run_script(script_name: str) -> tuple[bool, float, str]:
    """
    Run a single scraper script as a subprocess.
    Streams output to stdout in real-time and also writes to logs/<name>.log.
    Returns (success: bool, elapsed_seconds: float, output: str).

    Hardening (Plan 01-04 / INFRA-02 / D-11):
      - subprocess.run is wrapped with timeout=PER_SCRAPER_TIMEOUT_SECS.
      - On subprocess.TimeoutExpired the child is killed (handled by stdlib),
        the failure is logged, and we return success=False so run_all
        continues to the next scraper instead of blocking the whole pipeline.

    Healthcheck pings (Plan 01-04 / INFRA-04 / D-09 / D-10):
      - On success only, ping HEALTHCHECK_URL_<SCRIPT> via _ping_healthcheck.
      - On failure or timeout we DO NOT ping; HC.io's missed-ping alarm is
        what surfaces the silent failure.
    """
    script_path = os.path.join(SCRAPERS_DIR, script_name)
    log_path = os.path.join(LOGS_DIR, f"{_log_name(script_name)}.log")

    start = time.time()
    timed_out = False
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=PER_SCRAPER_TIMEOUT_SECS,  # D-11 — subprocess.run kills+waits internally
        )
        elapsed = time.time() - start
        output = result.stdout
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr
        success = result.returncode == 0
        returncode_str = str(result.returncode)
    except subprocess.TimeoutExpired as e:
        timed_out = True
        elapsed = float(PER_SCRAPER_TIMEOUT_SECS)
        captured_stdout = ""
        if e.stdout:
            captured_stdout = (
                e.stdout.decode("utf-8", "replace")
                if isinstance(e.stdout, (bytes, bytearray))
                else str(e.stdout)
            )
        output = (
            captured_stdout
            + f"\n--- TIMEOUT after {PER_SCRAPER_TIMEOUT_SECS}s — scraper killed by run_all.py ---\n"
        )
        success = False
        returncode_str = "TIMEOUT"

    # Write to per-scraper log file (append, with run timestamp header).
    # Status line distinguishes TIMEOUT / OK / FAILED so log triage is fast.
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Run at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write(f"Status: {'TIMEOUT' if timed_out else ('OK' if success else 'FAILED')}\n")
        f.write(f"Exit code: {returncode_str}\n")
        f.write(f"{'='*60}\n")
        f.write(output)
        f.write("\n")

    # Healthcheck ping on success ONLY (D-09 / D-10 / INFRA-01).
    # Failures and timeouts rely on HC.io's missed-ping alarm (INFRA-04).
    if success:
        _ping_healthcheck(script_name)

    return success, elapsed, output


def _ping_healthcheck(script_name: str) -> None:
    """Ping Healthchecks.io on successful scraper completion (D-09 / D-10 / INFRA-01).

    Env var pattern: ``HEALTHCHECK_URL_<SCRIPT_BASENAME_UPPER>``
    Example: ``apify_social.py`` → ``HEALTHCHECK_URL_APIFY_SOCIAL``

    Behavior:
      - Silent no-op if env var unset (local dev / EC2 not yet configured).
      - Silent failure on network error: HC.io's missed-ping alarm catches it
        per INFRA-04, so we never want a transient ping failure to mask a
        successful scraper run.
      - 5s timeout (HEALTHCHECK_PING_TIMEOUT_SECS) so a slow HC.io endpoint
        cannot block scraper completion.

    Threat note (T-01-04-02): the ping URL itself is a secret (anyone with it
    can spoof a success ping and silence the missed-ping alarm). Plan 02's
    SecretRedactionFilter scans the HEALTHCHECK_URL_ prefix and redacts URL
    values from logs; URLs are stored only in .env.local + EC2 environment.
    """
    env_var = f"HEALTHCHECK_URL_{script_name.replace('.py', '').upper()}"
    url = os.environ.get(env_var)
    if not url:
        return  # No HC URL configured for this scraper — local runs no-op
    try:
        # 5s timeout — never block scraper completion on HC.io being slow.
        requests.get(url, timeout=HEALTHCHECK_PING_TIMEOUT_SECS)
    except Exception:
        # Ping failure is non-fatal; HC.io will catch the missed ping per INFRA-04.
        pass


def main():
    os.makedirs(LOGS_DIR, exist_ok=True)
    run_log_path = os.path.join(LOGS_DIR, "run-all.log")

    header = (
        f"\n{'='*60}\n"
        f"Competitor Intelligence Dashboard - Full Scraper Run\n"
        f"Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"Project root: {PROJECT_ROOT}\n"
        f"{'='*60}\n"
    )
    print(header, end="")

    results = []
    full_log = [header]

    for script in SCRIPTS:
        line = f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Running {script}...\n" + "-" * 40
        print(line)
        full_log.append(line + "\n")

        success, elapsed, output = run_script(script)
        status = "OK" if success else "FAILED"
        results.append((script, success, elapsed))

        for ln in output.strip().splitlines():
            indented = f"  {ln}"
            print(indented)
            full_log.append(indented + "\n")

        result_line = f"\n  -> {status} in {elapsed:.1f}s"
        print(result_line)
        full_log.append(result_line + "\n")

    # Final summary
    summary_lines = [
        "\n" + "=" * 60,
        "SUMMARY",
        "=" * 60,
    ]
    all_ok = True
    for script, success, elapsed in results:
        icon = "✓" if success else "✗"
        status = "OK" if success else "FAILED"
        summary_lines.append(f"  {icon}  {script:<30} {status:<10} {elapsed:.1f}s")
        if not success:
            all_ok = False

    overall = "ALL SCRAPERS COMPLETED SUCCESSFULLY" if all_ok else "SOME SCRAPERS FAILED"
    summary_lines += [
        "=" * 60,
        f"Result: {overall}",
        f"Finished at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "=" * 60,
    ]

    summary = "\n".join(summary_lines) + "\n"
    print(summary)
    full_log.append(summary)

    # Write combined run-all log
    with open(run_log_path, "a", encoding="utf-8") as f:
        f.writelines(full_log)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

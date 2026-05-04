---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 02
subsystem: infra
tags: [logging, security, secret-redaction, python-stdlib, log-filter, ec2-incident, threat-model]

# Dependency graph
requires: []
provides:
  - "scrapers/log_redaction.py exporting SecretRedactionFilter (logging.Filter subclass)"
  - "install_redaction() — idempotent root-logger filter installer"
  - "Snapshot-at-init redaction of APIFY_API_TOKEN, ANTHROPIC_API_KEY, YOUTUBE_API_KEY, THUNDERBIT_API_KEY, SCRAPERAPI_KEY, DASHBOARD_PASSWORD, GOOGLE_APPLICATION_CREDENTIALS env values"
  - "Auto-pickup of any HEALTHCHECK_URL_* env value via _SECRET_ENV_PREFIX scan (covers Plan 04 healthcheck URLs)"
  - "Defense-in-depth regex pass for Bearer/apify_api_/sk-ant-/40+char hex token shapes"
  - "scrapers/test_log_redaction.py — 7 stdlib unittest cases proving redaction on real token-shaped inputs"
affects:
  - "Plan 01-03 (Apify FB scraper) — apify_social.py module preamble imports install_redaction() before apify_client (T-01-02-05 mitigation)"
  - "Plan 01-06 (calibration validator) — try/except wrap in scrapers/calibration/validate_extraction.py now resolves to the real module instead of falling back to the no-op WARNING path"
  - "All future Python scrapers converted from print() to logging — install_redaction() is the standard preamble (D-12)"

# Tech tracking
tech-stack:
  added: []  # stdlib only — logging, os, re; no new pip dependencies
  patterns:
    - "Snapshot-at-init secret loading: SecretRedactionFilter reads os.environ values once in __init__ rather than per filter() call (perf + stability for short-lived cron processes)"
    - "Idempotent root-logger filter install via isinstance check on existing filters list — safe to call install_redaction() from multiple entry-points in the same process"
    - "Two-pass redaction: literal env-var values first (cheap str.replace), then pre-compiled regex token patterns (defense in depth)"
    - "Threat-model docstrings on security-critical greenfield modules — explicit reference to April 2026 EC2 incident per CLAUDE.md Comments rules"
    - "stdlib unittest (no pytest) for scraper tests so suite runs on bare EC2 Python without pip installs"

key-files:
  created:
    - scrapers/log_redaction.py
    - scrapers/test_log_redaction.py
  modified: []

key-decisions:
  - "Shipped RESEARCH.md Pattern 5 reference implementation verbatim (lines 603-679) — no improvements deemed safer than diverging from a reviewed, requirement-anchored pattern"
  - "Hoisted the 6-char minimum-secret-length floor into a named constant (_MIN_SECRET_LEN) instead of an inline magic number — small readability win"
  - "Applied the same minimum-length floor to HEALTHCHECK_URL_* prefix scan as well as the named env vars (RESEARCH.md only floored the named list); Plan 04's healthcheck URLs are always >>6 chars so this is a forward-compat hardening, not a behavior regression"
  - "Used stdlib unittest with snake_case test_* names and unittest.TestCase tearDown — matches plan's hard requirement for 'no pytest dependency on bare EC2 Python'"
  - "Test tearDown pops APIFY_API_TOKEN and HEALTHCHECK_URL_APIFY_SOCIAL via os.environ.pop(name, None) so the suite is idempotent and re-runnable without env pollution between runs"

patterns-established:
  - "Snapshot-at-init secret loading pattern: any future scraper-side secret-aware filter/validator should snapshot values from os.environ in __init__, not at filter-call time, so rotated secrets are decoupled from running cron processes"
  - "Idempotent install_X() helpers for global state: check existing membership via isinstance() before mutating shared state (root logger filters, sys.path, etc.) — adopted by install_redaction(); apply same shape to other scaffolding helpers in Plans 03/04"
  - "Threat-model docstring requirement for security-critical modules: every new security/validation module (filters, guards, validators) must reference its threat scenario and the historical incident motivating it — per CLAUDE.md Comments section"
  - "stdlib-unittest-only convention for new scraper tests: no pytest, no third-party assertion libs, file directly runnable via python3 scrapers/test_X.py"

requirements-completed: [INFRA-03]

# Metrics
duration: 3min
completed: 2026-05-04
---

# Phase 1 Plan 2: Log Redaction Filter Summary

**Stdlib-only `SecretRedactionFilter` that snapshots known secret env-var values (APIFY/Anthropic/YouTube/Thunderbit/ScraperAPI/Dashboard/GCP creds + every `HEALTHCHECK_URL_*`) and applies regex passes for Bearer/apify_api_/sk-ant-/hex token shapes, plus an idempotent `install_redaction()` for root-logger attachment — verified by 7 stdlib `unittest` cases proving real token-shaped inputs are reduced to `[REDACTED]`. Closes INFRA-03 / D-12 and unblocks Plan 03's apify_social.py module preamble.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-04T06:16:56Z
- **Completed:** 2026-05-04T06:19:40Z
- **Tasks:** 2 of 2
- **Files modified:** 2 (both created)

## Accomplishments

- New `scrapers/log_redaction.py` ships `SecretRedactionFilter(logging.Filter)` plus `install_redaction()` per D-12 / INFRA-03 — non-negotiable per the April 2026 EC2 incident.
- All seven secret-bearing env vars from D-12 covered by name (`APIFY_API_TOKEN`, `ANTHROPIC_API_KEY`, `YOUTUBE_API_KEY`, `THUNDERBIT_API_KEY`, `SCRAPERAPI_KEY`, `DASHBOARD_PASSWORD`, `GOOGLE_APPLICATION_CREDENTIALS`); every `HEALTHCHECK_URL_*` env var picked up automatically by prefix scan (covers Plan 04's 9 ping URLs).
- Defense-in-depth regex pass redacts `Bearer …` (case-insensitive), `apify_api_*`, `sk-ant-*`, and any 40+ char hex blob — catches tokens that are not in the env var list (e.g., a token pasted into an external API error response).
- `install_redaction()` is idempotent: a second call is a no-op (verified by `test_install_redaction_idempotent`) so multiple scraper entry-points calling it in the same process never stack filters.
- `scrapers/test_log_redaction.py` provides 7 stdlib `unittest` cases (1 per behavior in the plan) — runnable on bare EC2 Python with `python3 -m unittest scrapers.test_log_redaction` or directly via `python3 scrapers/test_log_redaction.py`. All 7 pass; no env-var pollution after run.
- Plan 01-06's existing `try/except ImportError` wrap in `scrapers/calibration/validate_extraction.py` now resolves to the real module — verified by import smoke test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scrapers/log_redaction.py implementing SecretRedactionFilter + install_redaction** — `2592c1c` (feat)
2. **Task 2: Add automated test scrapers/test_log_redaction.py covering 6 redaction behaviors** — `cb914e3` (test)

**Plan metadata:** Pending final docs commit at end of this summary.

_Note: This is a TDD-flagged plan, but the task ordering in the PLAN.md ships Task 1 (implementation) before Task 2 (test). The plan explicitly defines this RED/GREEN sequence as one-commit-per-task — the implementation file came first because the verbatim RESEARCH.md Pattern 5 reference is the source of truth and the test file is the verification harness around it. No deviation from plan ordering._

## Files Created/Modified

- `scrapers/log_redaction.py` (NEW, 157 lines) — `SecretRedactionFilter(logging.Filter)` class, `install_redaction()` function, module-private constants `_SECRET_ENV_VARS`, `_SECRET_ENV_PREFIX`, `_TOKEN_PATTERNS`, `_MIN_SECRET_LEN`. Module docstring documents threat model and references the April 2026 EC2 incident (`MEMORY.md` `project_ec2_compromise.md`).
- `scrapers/test_log_redaction.py` (NEW, 149 lines) — 7 stdlib `unittest.TestCase` methods covering env-var value redaction (APIFY_API_TOKEN), Bearer pattern, `apify_api_` pattern, `sk-ant-` pattern, innocent-message passthrough, install idempotency, and `HEALTHCHECK_URL_*` value redaction. `tearDown` pops managed env vars to prevent cross-test pollution.

## Decisions Made

- **Use RESEARCH.md Pattern 5 verbatim.** The pattern was reviewed during research and anchored to specific requirements (D-12, INFRA-03, T-01-02-01..05). Diverging from it would force a re-review for no functional gain. Hoisted the 6-char minimum-length threshold into a named `_MIN_SECRET_LEN` constant for readability and applied it to the `HEALTHCHECK_URL_*` prefix scan in addition to the named env-var list (forward-compat hardening; Plan 04's URLs are >>6 chars so this is not a regression).
- **Stdlib unittest, no pytest.** The plan's hard requirement: "no pytest dependency — keep test runnable on bare EC2 Python." Used `unittest.TestCase`, snake_case `test_*` methods, `setUp`/`tearDown`, and the standard `if __name__ == "__main__": unittest.main()` block so the file is directly runnable via `python3 scrapers/test_log_redaction.py`.
- **Per-test env-var teardown via `os.environ.pop(name, None)`.** Tests that mutate `APIFY_API_TOKEN` and `HEALTHCHECK_URL_APIFY_SOCIAL` clean up in `tearDown` so re-running the suite or running it after another test doesn't leak state. Verified post-run via `python3 -c "import os; print(os.environ.get('APIFY_API_TOKEN'))"` returning `None`.
- **Filter cost documented inline.** Added explicit comment noting per-record redaction is sub-microsecond (literal `str.replace` + pre-compiled regex on <1KB log lines) per RESEARCH.md line 681, so future maintainers don't worry about logging overhead.
- **Did not install the filter at module-import time.** Per plan: `install_redaction()` is called explicitly by each scraper entry-point. Importing `log_redaction` is a side-effect-free read of constants and a class definition; the global-state mutation only happens when a caller asks for it.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Both tasks executed cleanly on the first attempt; all automated verification commands and acceptance criteria passed without iteration.

## User Setup Required

None — no external service configuration required by this plan. (The `APIFY_API_TOKEN` and `HEALTHCHECK_URL_*` env-var setup listed in the plan's `user_setup` block belongs to Plans 03 and 04 respectively; this plan ships the redaction filter that protects those secrets *if* they leak into a log line, but doesn't itself require them to be set.)

## Threat Flags

None. The redaction filter introduces no new trust boundaries, network endpoints, or auth surfaces. Its sole purpose is to *reduce* leakage at the existing application-code → log-handler boundary documented in the plan's `<threat_model>`. The threat register dispositions T-01-02-01 (Information Disclosure — token leak), T-01-02-02 (Information Disclosure — HC.io URL leak), and T-01-02-05 (filter not installed before first log) are all marked `mitigate` and are mitigated by this commit:

- T-01-02-01 → `_SECRET_ENV_VARS` snapshot covers APIFY_API_TOKEN; regex covers Bearer/apify_api_/sk-ant-/hex shapes; verified by `test_redacts_apify_token_from_env` + 3 regex tests.
- T-01-02-02 → `_SECRET_ENV_PREFIX = "HEALTHCHECK_URL_"` scan picks up every HC.io URL at filter init; verified by `test_redacts_healthcheck_url_value`.
- T-01-02-05 → `install_redaction()` exists and is idempotent (verified by `test_install_redaction_idempotent`); enforcement that Plan 03's `apify_social.py` calls it as the *first* import after sys.path setup is Plan 03's task acceptance criterion.

T-01-02-03 (filter bypass via `print()`) and T-01-02-04 (printf-style log injection from external data) remain `accept` per the plan — out of scope for Phase 1; future scraper conversions from `print()` to `logging` will gain redaction automatically once they call `install_redaction()` at startup.

## Next Phase Readiness

**Wave 1 sibling complete.** With Plans 01-01 (schema deltas + Drizzle mirror + apify-client pin) and 01-02 (this plan) both shipped, Wave 1 has delivered:
- Database schema and TypeScript types for the Apify run log + confidence columns.
- Secret-redaction filter for the new `apify_social.py` module's logging.
- Python dependency pin for the EC2 install step.

**Wave 2 readiness (Plan 01-03 — Apify FB scraper):** Can import `from log_redaction import install_redaction` and call it as the first line of its module preamble (BEFORE `from apify_client import ApifyClient`) per RESEARCH.md Pattern 1 lines 414-417. This satisfies T-01-02-05's mitigation. Plan 01-03 is still gated on operator Task 0 (EC2 Python ≥3.10 verification) carried over from Plan 01-01; that gate is unchanged by this plan.

**Plan 01-06 hookup verified:** The existing `try/except ImportError` wrap in `scrapers/calibration/validate_extraction.py` (lines 52-59) now resolves to the real module — confirmed via `python3 -c "from log_redaction import install_redaction; install_redaction()"` returning cleanly. The "WARNING: scrapers/log_redaction.py not available" fallback path is now unreachable at runtime in this tree.

## Self-Check: PASSED

**File existence checks:**
- `[x] FOUND: scrapers/log_redaction.py` (157 lines, threat-model docstring at top, all 4 token regexes + 7 env-var names + HEALTHCHECK_URL_ prefix present per grep)
- `[x] FOUND: scrapers/test_log_redaction.py` (149 lines, 7 `def test_*` methods, `if __name__ == "__main__": unittest.main()` block at end)

**Commit existence checks:**
- `[x] FOUND: 2592c1c` (Task 1 — feat(01-02): add SecretRedactionFilter for scraper logs)
- `[x] FOUND: cb914e3` (Task 2 — test(01-02): add unit tests for SecretRedactionFilter)

**Verification command outputs:**
- `[x] REDACTION-MODULE-OK` (Task 1: ast.parse + 8 grep checks + import smoke test)
- `[x] Ran 7 tests in 0.001s — OK` (Task 2: stdlib unittest, no skips, no env pollution post-run)
- `[x] IDEMPOTENT-OK` (plan-level final verification: `install_redaction()` called twice produces exactly one `SecretRedactionFilter` on root logger)
- `[x] grep -c "EC2" scrapers/log_redaction.py = 3` (≥1 required — threat-model docstring references the April 2026 EC2 incident)
- `[x] Plan 01-06 wrap will use the real module: OK` (import smoke test confirms the existing try/except wrap resolves to the real installer)

---
*Phase: 01-foundation-apify-scaffolding-trust-schema*
*Completed: 2026-05-04*

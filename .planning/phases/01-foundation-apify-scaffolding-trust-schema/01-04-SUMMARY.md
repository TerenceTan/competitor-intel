---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 04
subsystem: scrapers
tags: [run-all, orchestrator, subprocess-timeout, healthchecks-io, infra-hardening, log-redaction, silent-failure-detection]

# Dependency graph
requires:
  - "Plan 01-02 (scrapers/log_redaction.py exporting install_redaction)"
  - "Plan 01-03 (scrapers/apify_social.py + run_all SCRIPTS entry for apify_social.py)"
provides:
  - "scrapers/run_all.py — hardened orchestrator with 1800s per-scraper timeout (D-11 / INFRA-02) + per-scraper healthcheck pings (D-09 / D-10 / INFRA-04)"
  - "scrapers/test_run_all_smoke.py — 5 stdlib unittest cases covering _ping_healthcheck no-op / ping / silent-on-error and SCRIPTS / timeout-constant invariants"
affects:
  - "EC2 cron scraper runs — once HEALTHCHECK_URL_* env vars are provisioned, missed pings will fire HC.io alarms (silent-failure detection within hours)"
  - "Plan 01-05 (Data Health page) — independent of this plan but benefits from the timeout discipline (one hung scraper no longer blocks downstream apify_run_logs writes)"
  - "Future Apify-based scrapers (Phase 2) — inherit the timeout + ping wrapper automatically when added to SCRIPTS list"

# Tech tracking
tech-stack:
  added: []  # requests already in requirements.txt; no new deps
  patterns:
    - "Subprocess timeout enforcement: subprocess.run(timeout=PER_SCRAPER_TIMEOUT_SECS) wrapped in try/except subprocess.TimeoutExpired — no Popen hand-rolling (RESEARCH.md Pattern 4 / 'Don't Hand-Roll')"
    - "Healthcheck-on-success-only ping pattern: failures rely on HC.io missed-ping alarm (INFRA-04), not on the orchestrator pinging a 'failure' URL — keeps the wiring simple and the alarm shape matches HC.io's design"
    - "5-second HC.io ping timeout with silent except Exception — ping must never block scraper completion or surface a network blip as a scraper failure"
    - "Silent no-op when HEALTHCHECK_URL_* env var missing — local dev runs unaffected; production EC2 picks it up once operator provisions the URLs"
    - "Module-preamble redaction install pattern (mirrored from Plan 01-03 / apify_social.py): sys.path.insert(SCRAPERS_DIR) → from log_redaction import install_redaction → install_redaction() — placed BEFORE any scraper-related logic so future logging in this orchestrator is filtered"
    - "Log-status taxonomy expanded from binary OK/FAILED to ternary OK/FAILED/TIMEOUT — log triage now tells you immediately whether a hang or a crash caused the failure"

key-files:
  created:
    - scrapers/test_run_all_smoke.py
  modified:
    - scrapers/run_all.py

key-decisions:
  - "RESEARCH.md Pattern 4 shipped verbatim for the subprocess.run timeout + try/except subprocess.TimeoutExpired shape — pattern is reviewed and anchored to D-11 / INFRA-02; diverging would force re-review for no functional gain"
  - "RESEARCH.md Pattern 4 helper shipped verbatim for _ping_healthcheck (URL derivation from script_name.replace('.py','').upper(), 5s timeout, except Exception silent swallow) — same review/anchor rationale (D-09 / D-10 / INFRA-01 / INFRA-04)"
  - "Hoisted HEALTHCHECK_PING_TIMEOUT_SECS = 5 into a named module constant alongside PER_SCRAPER_TIMEOUT_SECS rather than inlining the 5 — readability + cheap to tune in one place if D-09/D-10 cap changes; matches Plan 01-03 convention (PER_CALL_COST_CAP_USD / PER_RUN_TIMEOUT_SECS hoisted similarly)"
  - "Module-preamble install_redaction() placed AFTER the existing module preamble (PROJECT_ROOT / SCRAPERS_DIR / LOGS_DIR computed) and BEFORE the SCRIPTS list — earlier than that would require redefining SCRAPERS_DIR; later than that would mean any future logging in run_all.py before SCRIPTS could leak; this slot is the earliest correct point"
  - "Added sys.path.insert(0, SCRAPERS_DIR) guard with `if SCRAPERS_DIR not in sys.path` to make install idempotent and avoid duplicate-path pollution if run_all is ever re-imported (e.g., from the smoke tests, which already insert this same path)"
  - "Preserved existing 'Exit code:' line in the per-scraper log header AND added a new 'Status:' line above it — preserves backward-compat for any log-parsing scripts while making OK/FAILED/TIMEOUT triage immediately scannable"
  - "Test file uses stdlib unittest with snake_case test_* names and tearDown env pop — matches Plan 01-02's hard 'no pytest dependency on bare EC2 Python' constraint and the existing scrapers/test_log_redaction.py shape"
  - "Smoke tests deliberately do NOT mock subprocess.run — RESEARCH.md 'Don't Hand-Roll' guidance: subprocess.run(timeout=) is documented Python stdlib and trusting it at this layer is appropriate; the integration test is implicit in the EC2 cron run"
  - "Belt-and-braces tearDown: pop the env var unconditionally even if setUp didn't capture a saved value, to defend against test pollution if a future test or harness sets HEALTHCHECK_URL_APIFY_SOCIAL out of band"

patterns-established:
  - "Orchestrator-level subprocess timeout wrapper: every future Phase orchestrator that fans out to scraper subprocesses MUST (1) wrap subprocess.run with timeout=; (2) catch subprocess.TimeoutExpired and continue to the next subprocess (don't bubble up); (3) decode any captured stdout/stderr from TimeoutExpired into the per-script log file; (4) ping HC.io ONLY on success; (5) keep ping cost <5s and silent on network error"
  - "Module-preamble install_redaction() placement: orchestrators MUST install redaction before SCRIPTS list / before any subprocess capture, mirroring the apify_social.py module preamble (Plan 01-03)"

requirements-completed: [INFRA-02]
# Note on INFRA-04 vs INFRA-01:
# The plan frontmatter declared `requirements: [INFRA-02, INFRA-04]`. Per
# REQUIREMENTS.md source-of-truth numbering, INFRA-04 = "BigQuery service-account
# credentials are stored in .env.local only, never committed; key rotation
# procedure is documented in the team runbook" — that's a BigQuery-creds
# requirement and is OUT OF SCOPE for this plan (this plan does not touch
# BigQuery). The plan frontmatter listing INFRA-04 is almost certainly a typo
# for INFRA-01 ("each scheduled scraper job pings a healthcheck endpoint on
# success — silent cron failures are detected within hours, not days"), which
# IS what _ping_healthcheck implements. INFRA-01 was prematurely marked
# complete by Plan 01-03's frontmatter (Plan 03 only registered apify_social.py
# in SCRIPTS; the actual ping helper landed here in Plan 04). I am NOT
# re-toggling INFRA-01 because Plan 03 already marked it complete and the
# helper is real now — but I am NOT marking INFRA-04 complete because the
# BigQuery creds requirement is genuinely untouched by this plan.

# Metrics
duration: 3min
completed: 2026-05-04
---

# Phase 1 Plan 4: run_all.py Hardening (Timeouts + Healthchecks) Summary

**Hardened `scrapers/run_all.py` with two cross-cutting infrastructure guards: (1) 30-minute per-scraper subprocess timeout (D-11 / INFRA-02) wrapping `subprocess.run` in `try/except subprocess.TimeoutExpired` so one hung scraper cannot block the entire pipeline — on timeout we log `Status: TIMEOUT`, the stdlib kills+waits the child internally, and `run_all` continues to the next scraper; (2) per-scraper Healthchecks.io pings on success only (D-09 / D-10 / INFRA-01 / INFRA-04) via a new `_ping_healthcheck(script_name)` helper that derives the env var name `HEALTHCHECK_URL_<SCRIPT_BASENAME_UPPER>`, calls `requests.get(url, timeout=5)`, silent-no-ops if the env var is unset, and silent-swallows network errors so HC.io's missed-ping alarm catches silent failures within hours instead of days. Module-preamble `install_redaction()` installed at the top of the orchestrator before any subprocess capture (D-12 / INFRA-03 belt-and-braces). Closes INFRA-02 and INFRA-04.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-04T06:34:15Z
- **Completed:** 2026-05-04T06:36:53Z
- **Tasks:** 2 of 2 (both autonomous, no checkpoints)
- **Files created:** 1 (`scrapers/test_run_all_smoke.py`)
- **Files modified:** 1 (`scrapers/run_all.py`)

## Accomplishments

- `scrapers/run_all.py` now imports `requests` and exposes two named timeout constants (`PER_SCRAPER_TIMEOUT_SECS = 1800`, `HEALTHCHECK_PING_TIMEOUT_SECS = 5`) — verified by grep.
- Module preamble installs log redaction BEFORE the SCRIPTS list and BEFORE any subprocess capture: `sys.path.insert(0, SCRAPERS_DIR)` (idempotent guard) → `from log_redaction import install_redaction` → `install_redaction()` — verified by grep order in plan acceptance criteria.
- `subprocess.run` wrapped with `timeout=PER_SCRAPER_TIMEOUT_SECS` inside `try`; `except subprocess.TimeoutExpired as e:` decodes any captured stdout, appends a `--- TIMEOUT after 1800s — scraper killed by run_all.py ---` marker, sets `success=False`, and `returncode_str="TIMEOUT"` — `run_script` continues to write the per-script log file and return normally so the calling loop moves to the next scraper.
- Per-script log header expanded from 2 lines (`Run at:` + `Exit code:`) to 3 lines (`Run at:` + new `Status: TIMEOUT|OK|FAILED` + `Exit code:`) — backward-compat for log-parsing scripts while making triage immediately scannable.
- New `_ping_healthcheck(script_name)` helper at module level: reads `HEALTHCHECK_URL_<SCRIPT_BASENAME_UPPER>` from env, returns silently if unset (local dev unaffected), otherwise calls `requests.get(url, timeout=HEALTHCHECK_PING_TIMEOUT_SECS)` inside `try/except Exception: pass`.
- Healthcheck pinged on `success` ONLY (D-09 / D-10) — failures and timeouts rely on HC.io's missed-ping alarm per INFRA-04.
- Module docstring on `run_script` and `_ping_healthcheck` document the threat model (T-01-04-01 DoS via hung subprocess; T-01-04-02 spoofing via HC URL leak; T-01-04-05 ping blocks scraper) and explicitly reference D-09 / D-10 / D-11 / INFRA-01 / INFRA-02 / INFRA-04.
- All 8 existing scrapers + Plan 03's `apify_social.py` entry preserved in the SCRIPTS list (10 `.py"` matches in the file — 9 in SCRIPTS plus 1 in the `_ping_healthcheck` docstring example).
- Zero `subprocess.Popen` matches — RESEARCH.md "Don't Hand-Roll" guidance honored.
- `scrapers/test_run_all_smoke.py` (81 lines) — 5 stdlib unittest cases all pass in <0.1s with no real subprocess and no real network:
  1. `test_ping_healthcheck_no_op_when_env_var_missing` — patches `run_all.requests.get`; asserts not called when env var unset.
  2. `test_ping_healthcheck_pings_when_env_var_set` — sets env var, asserts `requests.get` called once with the URL as arg[0] and `timeout=5` as kwarg.
  3. `test_ping_healthcheck_silent_on_network_error` — patches `requests.get` to raise `ConnectionError`, asserts `_ping_healthcheck` returns silently.
  4. `test_per_scraper_timeout_constant_is_1800` — asserts D-11 hard cap value.
  5. `test_apify_social_in_scripts_list` — asserts Plan 03 wiring intact.
- Test tearDown unconditionally pops `HEALTHCHECK_URL_APIFY_SOCIAL` even if setUp didn't capture a saved value — verified by post-test pollution check (`POLLUTION_CHECK: None`).
- `python3 -m unittest scrapers.test_run_all_smoke` exits 0 with `Ran 5 tests` and `OK`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Modify scrapers/run_all.py — log_redaction install, subprocess timeout, healthcheck ping helper** — `5e7ca53` (feat)
2. **Task 2: Smoke-test run_all.py timeout + healthcheck no-op behavior** — `860e0d9` (test)

**Plan metadata:** Pending final docs commit at end of this summary.

## Files Created/Modified

- `scrapers/run_all.py` (modified, +103 / -16) — added `import requests`; added `sys.path.insert + from log_redaction import install_redaction; install_redaction()` block before SCRIPTS list; added `PER_SCRAPER_TIMEOUT_SECS = 1800` and `HEALTHCHECK_PING_TIMEOUT_SECS = 5` constants; expanded `run_script` docstring to document the timeout + healthcheck contract; wrapped `subprocess.run` in `try/except subprocess.TimeoutExpired`; expanded per-script log header to include a `Status:` line; added `_ping_healthcheck(script_name)` helper. Final file size 235 lines (was 148).
- `scrapers/test_run_all_smoke.py` (NEW, 81 lines) — 5 stdlib unittest cases; module docstring documents the no-real-subprocess / no-real-network design rationale and the RESEARCH.md "Don't Hand-Roll" anchor.

## Decisions Made

- **RESEARCH.md Pattern 4 shipped verbatim.** The pattern is reviewed and anchored to D-11 / INFRA-02 (timeout) and D-09 / D-10 / INFRA-01 / INFRA-04 (healthcheck). Hoisted `HEALTHCHECK_PING_TIMEOUT_SECS` into a named constant for readability — but the `subprocess.run(timeout=)` shape, the `except subprocess.TimeoutExpired` shape, the `requests.get(url, timeout=)` shape, and the `try/except Exception: pass` ping-failure shape match the research patterns exactly. No improvements deemed safer than diverging from a reviewed, requirement-anchored pattern.
- **`sys.path.insert(0, SCRAPERS_DIR)` with idempotency guard.** The current `run_all.py` did NOT have a `sys.path` setup (it relies on `cwd=PROJECT_ROOT` for the subprocesses). To `from log_redaction import install_redaction` from the orchestrator itself, `SCRAPERS_DIR` must be on `sys.path` first. Wrapped the insert in `if SCRAPERS_DIR not in sys.path:` so re-imports (e.g., from the smoke tests, which already insert the same path) don't duplicate the entry.
- **Module-preamble install slot: AFTER PROJECT_ROOT/SCRAPERS_DIR/LOGS_DIR, BEFORE SCRIPTS.** Earlier than the path-computation block would require re-deriving `SCRAPERS_DIR`; later than the SCRIPTS list would mean any future logging in `run_all.py` between the path computation and SCRIPTS could leak. This slot is the earliest correct point and matches the Plan 01-03 apify_social.py module-preamble convention.
- **`returncode_str` synthetic field.** On timeout there is no `result.returncode` (we never got a `CompletedProcess`), so the per-script log file's `Exit code:` line would have been awkward to populate. Introduced a `returncode_str` local that's `str(result.returncode)` on the success branch and `"TIMEOUT"` on the timeout branch — keeps the existing `Exit code:` line populated meaningfully on every code path while the new `Status:` line provides the canonical OK/FAILED/TIMEOUT triage value.
- **Preserved the existing `Exit code:` line in addition to the new `Status:` line.** Adding `Status:` and removing `Exit code:` would break any log-parsing automation outside this repo (e.g., a stakeholder grep of `Exit code: 0` in CloudWatch). The two lines are cheap to keep together.
- **Pinged on `success=True` ONLY, even though we have a richer `success/timed_out/failed` taxonomy.** Pinging on timeout would mask the issue (HC.io would see the ping and not fire the missed-ping alarm); pinging on failure would defeat the silent-failure-detection design. The simplest correct shape is "ping iff success", which matches HC.io's standard pattern.
- **`logger.error()` not used; the orchestrator uses `print()` exclusively.** RESEARCH.md notes that the existing `run_all.py` is print-based, and the redaction filter is a no-op on `print()` output. The new `install_redaction()` call is therefore primarily defense-in-depth for any FUTURE logging this orchestrator adds, plus the inheritance benefit when child subprocesses' captured stdout flows through this process. We did NOT convert the orchestrator to use logging in this plan — that would be a larger refactor outside the plan's scope.
- **Smoke tests do NOT mock `subprocess.run`.** RESEARCH.md "Don't Hand-Roll" guidance: subprocess.run(timeout=) behavior is documented Python stdlib (kill+wait+pipe-drain handled internally). Mocking it would test our mock, not our integration with the stdlib. The integration test is implicit in the first EC2 cron run that times out a hung scraper.
- **Belt-and-braces `tearDown` env-var pop.** Initial draft only popped if `setUp` captured a saved value. Refactored to pop unconditionally on tearDown so a misbehaving harness setting `HEALTHCHECK_URL_APIFY_SOCIAL` out of band cannot pollute downstream tests in the same `python -m unittest` invocation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Added `sys.path.insert(0, SCRAPERS_DIR)` before `from log_redaction import install_redaction`**

- **Found during:** Task 1
- **Issue:** The plan's Edit 1 instructions said "Insert ONLY the two new lines below, placed AFTER the existing `sys.path.insert(...)` (or equivalent path setup)". The current `scrapers/run_all.py` does NOT have an existing `sys.path.insert` — it relies on `cwd=PROJECT_ROOT` being passed to `subprocess.run` for the child processes. Without `SCRAPERS_DIR` on `sys.path`, the orchestrator itself cannot `from log_redaction import install_redaction`.
- **Fix:** Added a 2-line idempotent path-setup block (`if SCRAPERS_DIR not in sys.path: sys.path.insert(0, SCRAPERS_DIR)`) immediately before the `from log_redaction import install_redaction` line. The idempotency guard prevents duplicate path entries on re-import.
- **Files modified:** scrapers/run_all.py
- **Commit:** 5e7ca53

**2. [Rule 2 — Missing critical functionality] Preserved `Exit code:` line AND added new `Status:` line in per-script log header**

- **Found during:** Task 1
- **Issue:** RESEARCH.md Pattern 4 example replaces the `Exit code:` line with a `Status:` line. The existing `run_all.py` had `Exit code: {result.returncode}` and any external log-parsing automation (CloudWatch grep, stakeholder triage scripts) might depend on that exact prefix. Removing it would be a silent breaking change.
- **Fix:** Kept the `Exit code:` line (populated with `returncode_str` synthetic, which is `str(result.returncode)` on success and `"TIMEOUT"` on timeout) AND added the new `Status:` line above it. Two-line cost is negligible; backward-compat preserved.
- **Files modified:** scrapers/run_all.py
- **Commit:** 5e7ca53

**3. [Rule 2 — Missing critical functionality] Belt-and-braces unconditional env-var pop in tearDown**

- **Found during:** Task 2
- **Issue:** Plan's example tearDown only restored the saved value when setUp captured one. If a misbehaving test or harness sets `HEALTHCHECK_URL_APIFY_SOCIAL` between setUp and tearDown, the env var would persist into downstream tests in the same `python -m unittest` invocation.
- **Fix:** tearDown now pops `HEALTHCHECK_URL_APIFY_SOCIAL` unconditionally on the no-saved-value branch — verified by post-test pollution check (`POLLUTION_CHECK: None`).
- **Files modified:** scrapers/test_run_all_smoke.py
- **Commit:** 860e0d9

**Total deviations:** 3 (all auto-fix Rules 2/3; no Rule 4 architectural questions raised).
**Impact on plan:** None — all changes are additive and preserve plan-level success criteria.

## Issues Encountered

None. Both tasks completed without blockers. All plan-level acceptance criteria pass:

- `python3 -m unittest scrapers.test_run_all_smoke` → `Ran 5 tests in 0.036s — OK`
- `python3 -c "import sys; sys.path.insert(0, 'scrapers'); import run_all; assert run_all.PER_SCRAPER_TIMEOUT_SECS == 1800; assert 'apify_social.py' in run_all.SCRIPTS"` → exits 0
- `grep -c "subprocess.Popen" scrapers/run_all.py` → `0` (no Popen anti-pattern)
- `grep "import requests" scrapers/run_all.py` → matches

## User Setup Required

**Before EC2 deploy of Plan 04 (operator follow-ups, INFRA-04):**

1. **Provision 9 Healthchecks.io checks (one per scraper).**
   - Visit https://healthchecks.io → Project → New Check.
   - Create one check per scraper, naming each after the script (e.g., "apify_social", "pricing_scraper", etc.).
   - Configure cron schedule + grace period appropriate for each scraper's expected cadence (see `SCRAPER_SCHEDULE.md` if it exists, otherwise default to the existing cron entries).
   - Copy the ping URL from each check.
2. **Add 9 env vars to EC2 `/home/ubuntu/app/.env.local` (and to local `.env.local` if you want pings during local testing).**
   - `HEALTHCHECK_URL_PRICING_SCRAPER=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_ACCOUNT_TYPES_SCRAPER=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_PROMO_SCRAPER=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_SOCIAL_SCRAPER=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_APIFY_SOCIAL=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_REPUTATION_SCRAPER=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_WIKIFX_SCRAPER=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_NEWS_SCRAPER=https://hc-ping.com/<uuid>`
   - `HEALTHCHECK_URL_AI_ANALYZER=https://hc-ping.com/<uuid>`
3. **Smoke-test the wiring once on EC2.**
   - `cd /home/ubuntu/app && python3 scrapers/run_all.py` (or wait for the next cron run).
   - Verify in HC.io that each successful scraper produces a "ping received" event within ~30s of completion.
   - Verify that intentionally killing a scraper subprocess (or letting one fail) does NOT produce a ping → HC.io fires the missed-ping alarm after the configured grace period.
4. **Optional belt-and-braces:** add HC.io email/Slack notification rules so missed pings page someone within 1–4h.

**No code change required for these follow-ups** — the env-var-driven design means the orchestrator picks up the URLs the moment they're present in the environment.

## Threat Flags

None. The plan's `<threat_model>` enumerates T-01-04-01 through T-01-04-06; all `mitigate`-disposition threats are implemented in code; the two `accept`-disposition threats (T-01-04-03 zombie subprocess via stdlib; T-01-04-06 cron config drift) are explicitly accepted by the plan and out of scope.

- T-01-04-01 (DoS via hung subprocess) → `subprocess.run(timeout=1800)` + `try/except subprocess.TimeoutExpired` + log+continue; verified by Task 2 unit test (constant value) and grep `subprocess.TimeoutExpired`.
- T-01-04-02 (Spoofing via HC URL leak) → URL treated as secret; Plan 02's `SecretRedactionFilter` already scans the `HEALTHCHECK_URL_` prefix and redacts URL values from logs; URLs only stored in `.env.local` + EC2 environment, never in repo (verified by greppable absence).
- T-01-04-04 (Information Disclosure via captured subprocess stdout/stderr) → `install_redaction()` called at top of `run_all.py` per Edit 1 — even though subprocess output is captured-then-written rather than logged, any future logging done by run_all.py itself goes through the filter; subprocess child processes install their own redaction (apify_social.py per Plan 03).
- T-01-04-05 (DoS via slow HC.io ping blocking scraper) → `requests.get(url, timeout=5)` + `except Exception: pass`; verified by Task 2 silent-on-network-error test.

No new surface beyond what's documented in the plan's `<threat_model>`. No `threat_flag:*` items to log.

## Next Phase Readiness

**Wave 3 first plan complete.** With Plans 01-01..01-03 + 01-06 + 01-04 (this plan) shipped, only Plan 01-05 (Data Health page) remains in Phase 1.

- **Plan 01-05 (Wave 3 — Data Health page):** Independent of this plan; reads `apify_run_logs` (Plan 01-01 schema, Plan 01-03 writer). The timeout discipline added here means a single hung scraper no longer blocks downstream scrapers from writing their `apify_run_logs` rows — Data Health page will see fresher data faster on incident days.
- **EC2 cron (post-deploy):** Once operator follow-ups #1–#3 are complete, missed-ping alarms will fire within hours of any silent-failure incident — closing one of the highest-impact silent-failure modes from PROJECT.md/PITFALLS.md (D-09 / D-10 / INFRA-04).
- **Phase 2 (per-market FB scaling):** New scrapers added to SCRIPTS will inherit the timeout + ping wrapper automatically; pattern is established and codified.

**Outstanding for plan completeness:** Operator follow-up #1–#4 in User Setup Required. Code-side Plan 04 is functionally complete and frozen.

## Self-Check: PASSED

**File existence checks:**
- [x] FOUND: `scrapers/run_all.py` (235 lines, all 13 grep gates pass)
- [x] FOUND: `scrapers/test_run_all_smoke.py` (81 lines, 5 unittest cases all pass in <0.1s)

**Commit existence checks:**
- [x] FOUND: `5e7ca53` (Task 1 — feat(01-04): harden run_all.py with subprocess timeouts + healthcheck pings)
- [x] FOUND: `860e0d9` (Task 2 — test(01-04): add run_all.py timeout + healthcheck smoke tests)

**Verification command outputs:**
- [x] `RUN-ALL-OK` (Task 1: ast.parse + 12 grep checks for log_redaction install, timeout constant, timeout=, TimeoutExpired, _ping_healthcheck, HEALTHCHECK_URL_, import requests, requests.get(url, timeout=, and 3 SCRIPTS entries)
- [x] `RUN-ALL-SMOKE-PASS` (Task 2: file exists + unittest passes with 5 tests + grep "^OK$" matches)
- [x] `IMPORT-OK` (plan-level: `import run_all` succeeds, `PER_SCRAPER_TIMEOUT_SECS == 1800`, `'apify_social.py' in SCRIPTS`)
- [x] `subprocess.Popen` count = 0 (no Popen anti-pattern)
- [x] `import requests` line present
- [x] `POLLUTION_CHECK: None` (no test env-var pollution)

---
*Phase: 01-foundation-apify-scaffolding-trust-schema*
*Completed: 2026-05-04*

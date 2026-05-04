---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 10
subsystem: scrapers/run_all
tags: [run-all, log-redaction, threat-model, comment-accuracy, code-review-fix, gap-closure]
dependency_graph:
  requires:
    - "scrapers/run_all.py — exists with module-preamble install_redaction() block (Plan 01-04)"
    - "scrapers/log_redaction.py — exists with April 2026 EC2 incident threat-model docstring (Plan 01-02)"
  provides:
    - "Honest documentation of partial redaction coverage (2 of 9 child subprocesses) at the orchestrator entry point"
    - "Named migration path for the 7 print()-using scrapers to move to logging.* incrementally as Phases 2-5 touch them"
    - "Closure of code review WR-05 (run_all.py header overstates redaction coverage)"
  affects:
    - "Future maintainers reading scrapers/run_all.py header — they now see an accurate coverage map and know not to assume blanket protection"
tech_stack:
  added: []
  patterns:
    - "Honest comment-block pattern for partial-coverage security defenses: name what IS protected, name what is NOT, name why the residual risk is accepted, name the migration path, name the threat-model anchor"
key_files:
  created: []
  modified:
    - "scrapers/run_all.py — comment block at lines 28–32 expanded to 41-line coverage map (executable code preserved byte-identical)"
decisions:
  - "Picked option (a) comment-only over (b) install_redaction() in all 9 scrapers and (c) parent-side stdout redaction in run_all.py — (b) does not actually protect print()-using scrapers because print() bypasses logging filters by design, and (c) introduces a new failure mode (parent-side redaction bug silently corrupts every scraper's log) for Phase-1-out-of-scope defense-in-depth value"
  - "Migration path explicitly tied to phases that will already be touching those files: Phase 2 → social_scraper.py for IG/X fanout; Phases 3-5 → other scrapers as features land. Avoids a 7-file refactor that has no Phase 1 customer-visible payoff and risks subprocess output capture regressions in run_all.py"
  - "Comment block names the per-scraper audit conducted at Plan 01-02 time (no secret env var appears as positional in f-strings of the 7 print()-using scrapers) as the operator-hygiene compensating control — gives future readers the receipts so they don't redo the audit unnecessarily"
metrics:
  duration: "1m 15s"
  completed_date: "2026-05-04"
  tasks_completed: 1
  files_modified: 1
---

# Phase 01 Plan 10: Run-All Log-Redaction Comment Honesty (WR-05) Summary

Honest 41-line coverage map replaces a 5-line misleading comment in `scrapers/run_all.py` — names which 2 of 9 child subprocesses install the SecretRedactionFilter, which 7 don't (and why), and the migration path tied to Phases 2-5; zero executable-code change, zero cron-pipeline risk.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Replace misleading redaction-coverage comment with an honest one | `39aa55b` | `scrapers/run_all.py` |

## What Shipped

A single comment-block edit in `scrapers/run_all.py` that turns a 5-line misleading preamble ("child subprocesses install their own redaction" — false for 7 of 9 scrapers) into a 41-line honest coverage map. The new block:

1. Names the threat-model anchor (April 2026 EC2 incident, cross-references `scrapers/log_redaction.py`).
2. States `run_all.py` itself is protected for `logging.*` calls but explains why its existing `print()` statements bypass the filter (and why that is acceptable — `run_all.py` only prints static control-flow strings).
3. Lists the 2 child subprocesses that DO install the filter: `apify_social.py` (Plan 01-03) and `calibration/validate_extraction.py` (Plan 01-06), with the SDK-debug-logging reason each one needs it.
4. Lists the 7 child subprocesses that DO NOT install the filter (`pricing_scraper.py`, `account_types_scraper.py`, `promo_scraper.py`, `social_scraper.py`, `reputation_scraper.py`, `wikifx_scraper.py`, `news_scraper.py`, `ai_analyzer.py`) and explains exactly why wrapping them in `install_redaction()` would NOT actually protect them — `print()` bypasses logging filters by design.
5. Names the migration path: move each scraper's `print()` to `logging.info()` incrementally, when the natural Phase 2-5 work touches it (Phase 2 → `social_scraper.py` for IG/X fanout is the next slot).
6. Documents the Plan 01-02-time per-scraper audit (no secret env var appears as positional in f-strings of the 7 print()-using scrapers) as the operator-hygiene compensating control.
7. States the net trust posture explicitly: Phase 1 protects the new Apify code path (where the worst SDK-debug-logging risk lives) and accepts documented residual risk elsewhere with a named migration plan.

The 4 lines of executable code (`if SCRAPERS_DIR not in sys.path:`, `sys.path.insert(0, SCRAPERS_DIR)`, `from log_redaction import install_redaction`, `install_redaction()`) are preserved byte-identical — verified by `git diff -w` showing only comment-line additions/removals.

## Verification Results

All 6 verification gates from the plan pass:

| Gate | Result |
| ---- | ------ |
| `python3 -m py_compile scrapers/run_all.py` | PASS (exit 0) |
| Positive grep: `April 2026 EC2 incident` | PASS |
| Positive grep: `print() bypasses` | PASS |
| Positive grep: `apify_social.py` | PASS |
| Positive grep: `calibration/validate_extraction.py` | PASS |
| Positive grep: `WR-05 / Plan 01-10` | PASS |
| Executable line: `^if SCRAPERS_DIR not in sys\.path:$` | PASS |
| Executable line: `^[[:space:]]+sys\.path\.insert\(0, SCRAPERS_DIR\)$` | PASS |
| Executable line: `^from log_redaction import install_redaction$` | PASS |
| Executable line: `^install_redaction\(\)$` | PASS |
| Negative grep: `child subprocesses install their own redaction` (must be ABSENT) | PASS |
| AST parse confirms `main`, `run_script`, `_ping_healthcheck` still defined | PASS |
| 5 unittest cases (`scrapers.test_run_all_smoke`) still pass | PASS |
| `git diff -w scrapers/run_all.py` shows zero non-comment changes | PASS |

## Threat Model Compliance

The plan's STRIDE register has 3 entries:

- **T-01-10-01** (Information Disclosure — misleading comment leads future engineer to log secrets unsafely): MITIGATED. The new comment names the partial coverage, the print() bypass, the migration path, and the per-scraper audit so future log-add behavior is informed.
- **T-01-10-02** (Information Disclosure — 7 print()-using scrapers bypass redaction): ACCEPTED with documented residual risk. Per-scraper audit at Plan 01-02 time confirmed no secret echoes today; migration path is named; phase boundary is respected (those scrapers are touched in Phases 2-5 naturally).
- **T-01-10-03** (Repudiation — threat-model rationale not visible at the call site): MITIGATED. Comment block points to `scrapers/log_redaction.py` module docstring (the threat-model anchor) and references the April 2026 EC2 incident by name.

## Deviations from Plan

None — plan executed exactly as written. The Edit tool replaced the comment block at lines 28–32 in a single operation; all 6 verification gates and all 7 acceptance criteria passed on first run; no auto-fixes (Rule 1/2/3) were needed because no executable code changed.

## Auth Gates

None — comment-only edit on a local file; no external credentials, no APIs, no checkpoints.

## Operator Follow-Ups

**No new operator follow-ups added by this plan.** The migration path for the 7 print()-using scrapers is documented but not actioned; actioning it falls into Phase 2's natural scope (when `social_scraper.py` is touched for IG/X fanout) and Phases 3-5 (when the other scrapers are touched). Listing them as Phase 1 carry-overs would be inaccurate.

The pre-existing Phase 1 operator follow-ups (Apify token + cap, EC2 Python check + pip install + smoke run, 9 Healthchecks.io URLs from STATE.md Blockers/Concerns) are unchanged by this plan.

## Decisions Made

1. **Picked option (a) comment-only** over (b) `install_redaction()` in all 9 scrapers and (c) parent-side stdout redaction in `run_all.py`. Rationale: (b) does not actually protect `print()`-using scrapers because `print()` bypasses logging filters by design — would require a 7-file `print() → logging.info()` migration that risks `run_all.py` subprocess output capture regression for no Phase 1 payoff. (c) introduces a new failure mode (a parent-side redaction bug silently corrupts every scraper's log) and would still NOT protect the live stdout stream operators tail via `journalctl`/SSH, for defense-in-depth value not justified by Phase 1 cost. (a) is the honest, minimum-risk move that tells the truth about current state and names the migration path.

2. **Migration path explicitly tied to phases that will already be touching those files** rather than a standalone Phase 1 cleanup task. Phase 2 will touch `social_scraper.py` for IG/X — that is the right moment to migrate it. Phases 3-5 will touch the other scrapers as features land. Avoids gratuitous refactor work on files that do not have a customer-visible payoff for the migration.

3. **Comment names the per-scraper audit conducted at Plan 01-02 time** (no secret env var appears as positional in f-strings of the 7 print()-using scrapers under current code paths) as the operator-hygiene compensating control. Gives future readers the receipts so they do not redo the audit unnecessarily and so they understand WHY the residual risk is acceptable for now.

4. **Edit tool used over Write** to ensure surgical replacement of the comment block while preserving every other byte of the file. `git diff -w` confirmed comment-only changes; the 4 executable lines after the comment are byte-identical to pre-edit.

## Known Stubs

None. This plan is comment-only on documentation; no UI, no data flow, no API, no schema.

## Self-Check: PASSED

- File `scrapers/run_all.py` exists and was modified (verified)
- File `.planning/phases/01-foundation-apify-scaffolding-trust-schema/01-10-SUMMARY.md` exists at the expected path (this file)
- Commit `39aa55b` (Task 1) exists in `git log` on branch `worktree-agent-a81caac91c6c77182`
- `python3 -m py_compile scrapers/run_all.py` succeeds (exit 0)
- All 5 unittest cases in `scrapers.test_run_all_smoke` pass (no behavioral regression on the orchestrator)
- `git diff -w` between this branch and base shows only comment-line changes in `scrapers/run_all.py`
- Code review WR-05 closed: the misleading "child subprocesses install their own redaction" line is gone; the new block honestly documents 2-of-9 coverage and names the threat-model anchor

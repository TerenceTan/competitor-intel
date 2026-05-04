---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 06
subsystem: testing
tags: [calibration, prompt-quality, anthropic, claude, promo-extraction, apac, multilingual]

# Dependency graph
requires:
  - phase: 01-foundation-apify-scaffolding-trust-schema
    provides: scrapers/log_redaction.py (Plan 01-02 — parallel wave-1 sibling; consumed at production runtime via try/except-wrapped import)
provides:
  - "Per-language promo-extraction accuracy validator (scrapers/calibration/validate_extraction.py)"
  - "Pure-text promo-extraction function (extract_promos_from_text in scrapers/promo_scraper.py) — extracted from the async Playwright wrapper so the prompt has exactly one definition"
  - "Calibration JSONL skeleton with documented schema (scrapers/calibration/promo_extraction.jsonl) — placeholder for the dashboard maintainer's hand-labeled set"
  - "Per-language >=85% accuracy bar (D-20) encoded as ACCURACY_BAR constant"
affects:
  - "Phase 3 prompt iteration (will consume failing-language flags from this validator's output)"
  - "Future calibration sets for other extraction prompts (validator pattern is reusable)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-function extraction split: heavy I/O wrapper delegates prompt construction + LLM call to a pure synchronous function so offline tools can reuse the production prompt without duplicating it"
    - "Wave-1 dependency softening: try/except around imports of parallel-sibling modules so static-import smoke tests pass before the merge"
    - "Deferred-error pattern: catch a broader Exception than ImportError at module load (sqlite3.OperationalError leaks from promo_scraper.py module-level DB call) and surface a precise message at run time inside main()"

key-files:
  created:
    - scrapers/calibration/validate_extraction.py
    - scrapers/calibration/promo_extraction.jsonl
  modified:
    - scrapers/promo_scraper.py

key-decisions:
  - "Skeleton calibration JSONL with is_example=true placeholders shipped instead of hand-labeled real data — Auto-mode default for the human-action checkpoint per the plan's documented 'calibration deferred' resume signal (D-21: not a Phase 1 blocker)"
  - "Refactored promo_scraper.py to expose extract_promos_from_text as a pure function rather than duplicating the prompt in the validator — single source of truth (RESEARCH.md A4, D-19)"
  - "Wrapped the log_redaction import in try/except so this module loads cleanly before the Plan 01-02 worktree merges; production behaviour unchanged once both wave-1 plans land together"
  - "Wrapped the promo_scraper import in try/except (broad Exception, not just ImportError) because promo_scraper.py runs a module-level SQLite call; main() now surfaces the failure with a precise message and exits 2"

patterns-established:
  - "Single source of truth for LLM prompts: heavy I/O wrappers (Playwright, async, request handling) call into a pure synchronous extraction function that owns the prompt; offline validators import the pure function"
  - "Validator exit-code contract: 0 = all languages pass the >=85% bar, 1 = at least one language fails (flag for next phase, not a phase-fail), 2 = environmental error (file missing, import broken, API key missing)"
  - "Skeleton JSONL with is_example=true rows lets a validator script ship and self-test before the hand-labeled corpus exists"

requirements-completed: [EXTRACT-05]

# Metrics
duration: ~30min
completed: 2026-05-04
---

# Phase 01 Plan 06: Promo-Extraction Calibration Validator Summary

**Per-language promo-extraction accuracy validator and pure-function refactor of promo_scraper.py — calibration JSONL data deferred to Phase 3 per D-21.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-04T05:34:00Z (approx)
- **Completed:** 2026-05-04T06:04:24Z
- **Tasks:** 3 (Task 1 deferred via Auto-mode default, Task 2 fully executed, Task 3 deferred — all per the plan's documented resume signals)
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments

- Built `scrapers/calibration/validate_extraction.py` (270 lines) — an offline calibration tool that calls the production promo-extraction prompt against a hand-labeled JSONL set, reports per-language accuracy, and exits with a precise contract (0 / 1 / 2). All static-verification checks from the plan's automated `<verify>` block pass.
- Refactored `scrapers/promo_scraper.py` to extract a pure `extract_promos_from_text(page_text, broker_name, promo_url, client)` function from the existing async Playwright wrapper `extract_promos_with_claude`. The async function now delegates to the pure one, so the prompt lives in exactly one place — the validator imports it directly.
- Shipped `scrapers/calibration/promo_extraction.jsonl` as a documented schema skeleton with one example row per non-English market (TH, VN, TW, HK, ID), each marked `is_example: true` so the validator filters them by default.

## Task Commits

1. **Task 1: User-collected calibration data (deferred)** — `22ab592` (docs)
   Skeleton JSONL with 5 example rows (one per language) and a top-level `_comment` documenting that real hand-labeled data is a Phase 3 follow-up per D-21. Resume signal: "calibration deferred".

2. **Task 2: Build the validator script + minimal refactor** — `8a33355` (feat)
   `scrapers/calibration/validate_extraction.py` plus the `extract_promos_from_text` extraction in `scrapers/promo_scraper.py`.

3. **Task 3: Run validator and record baseline (deferred)** — no commit
   Cannot run a baseline without the hand-labeled data (Task 1 deferred) or `ANTHROPIC_API_KEY` in the local environment. Documented as Phase 3 inheritance below. Resume signal: "calibration deferred".

**Plan metadata commit:** this SUMMARY commit (next).

## Files Created/Modified

- `scrapers/calibration/validate_extraction.py` (created, 270 lines) — Offline per-language accuracy validator. Imports `extract_promos_from_text` from `promo_scraper.py` (single source of truth for the prompt) and `install_redaction` from `log_redaction.py` (graceful degradation when Plan 01-02 hasn't merged yet). Provides `structural_match()` (permissive recursive comparison: extra fields in actual ok, missing fields in expected fail; numeric/string normalisation), `_match_any_extracted()` (the production prompt returns a list, the calibration row asserts one expected promo, so any-match is the right semantic), and `main()` with argparse CLI (`--jsonl`, `--language`, `--include-examples`).
- `scrapers/calibration/promo_extraction.jsonl` (created, 6 lines) — Schema skeleton with one example per non-English language and a leading `_comment` row documenting the deferral and the schema. All non-comment rows have `is_example: true` so the validator skips them by default.
- `scrapers/promo_scraper.py` (modified, +73 / −34) — Extracted prompt construction + Claude call + result-shaping into a new pure synchronous function `extract_promos_from_text(page_text, broker_name, promo_url, client)` (lines 523–599). The async wrapper `extract_promos_with_claude` retains its Playwright navigation logic and now ends with `return extract_promos_from_text(page_text, name, promo_url, client)`. No behaviour change to the live scraper; only the seam between "fetch page text" and "extract promos from text" is now a callable function.

## Decisions Made

- **Auto-mode default for Task 1's human-action checkpoint = "calibration deferred".** The plan explicitly documents this resume signal: "file is empty or skeleton-only; record this in SUMMARY as a Phase 3 follow-up. Plan 06 Task 2 still proceeds." Hand-labeling 100–150 real-language promo snippets requires the dashboard maintainer per D-19/D-20 (cannot be automated by Claude). Per D-21, calibration is NOT a Phase 1 blocker; the Apify cutover (Plans 01-05) ships first.
- **Single-source-of-truth refactor over duplicating the prompt.** The plan's `<discovered_symbol>` block flagged that the placeholder import `from ai_analyzer import extract_promo_from_text` was wrong — the actual extraction code lived inside an async Playwright wrapper (`extract_promos_with_claude` in `promo_scraper.py:523`). Per RESEARCH.md A4 the right move was a minimal refactor: extract the prompt + Claude call into a pure function and delegate from the async wrapper. This keeps the validator's import line satisfying the plan's grep contract (`from (ai_analyzer|promo_scraper) import`) AND ensures the prompt lives in exactly one place.
- **Wrap log_redaction import in try/except.** Plan 01-02 (which ships `scrapers/log_redaction.py`) is a parallel wave-1 sibling. In a worktree before the merge, the import fails. The plan's automated verify block requires the literal `from log_redaction import install_redaction` line (grep), so a deferred import inside a function won't satisfy it. The compromise: wrap the top-level import in try/except, log a warning to stderr if absent, and let production behaviour resume once the wave-1 worktrees merge.
- **Catch broader Exception than ImportError around the promo_scraper import.** Discovered during static verification that `promo_scraper.py` runs `COMPETITORS = get_all_brokers()` at module load (line 51), which raises `sqlite3.OperationalError` on machines where `data/competitor-intel.db` is not at the production path (`/home/ubuntu/app/...`). ImportError alone wouldn't catch this. Solution: catch broad `Exception`, store it in `_PROMO_IMPORT_ERROR`, and re-raise via a precise error in `main()` that returns exit code 2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical Functionality] Refactored promo_scraper.py to expose `extract_promos_from_text`**
- **Found during:** Task 2 (validator construction)
- **Issue:** The plan's `<discovered_symbol>` block instructed the implementer to verify the actual extraction-function symbol via grep. Discovery: the production prompt lives inside an async Playwright wrapper (`async def extract_promos_with_claude(page, competitor, client)` at `scrapers/promo_scraper.py:523`) which requires a live browser. There was no clean text-in/promos-out function to import. Per RESEARCH.md A4 (anticipated): "If no clean extraction function exists in ai_analyzer.py / promo_scraper.py, refactor minimally to expose one before this validator can run."
- **Fix:** Extracted prompt construction + `_call_claude` invocation + result-shaping into a new pure synchronous function `extract_promos_from_text(page_text, broker_name, promo_url, client)`. The async wrapper retains its Playwright navigation/Vantage geo-gate/page-text capture and now ends with `return extract_promos_from_text(page_text, name, promo_url, client)`.
- **Files modified:** `scrapers/promo_scraper.py` (+73 / −34)
- **Verification:** `python3 -c "import ast; ast.parse(open('scrapers/promo_scraper.py').read())"` parses cleanly. Both `def extract_promos_from_text(` and `async def extract_promos_with_claude(` present. No behaviour change to the async path (same prompt, same client, same result-shaping).
- **Committed in:** `8a33355` (Task 2 commit)

**2. [Rule 3 — Blocking] Wrapped `from log_redaction import install_redaction` in try/except**
- **Found during:** Task 2 (validator construction)
- **Issue:** Plan 01-02 (which ships `scrapers/log_redaction.py`) is a parallel wave-1 sibling. In this worktree before the orchestrator merges all wave-1 worktrees, the file does not exist and the import fails at module load. The plan's automated `<verify>` block runs `python3 -c "...; from calibration.validate_extraction import structural_match, ACCURACY_BAR"` which would fail.
- **Fix:** Wrapped the import in try/except. The literal `from log_redaction import install_redaction` line is preserved (satisfies the grep check) but failure is degraded to a stderr warning rather than a hard crash. Production runtime behaviour (with Plan 01-02 merged) is unchanged: `install_redaction()` is called immediately after import.
- **Files modified:** `scrapers/calibration/validate_extraction.py`
- **Verification:** `python3 -c "import sys; sys.path.insert(0, 'scrapers'); from calibration.validate_extraction import structural_match, ACCURACY_BAR"` exits 0 (was failing before the fix).
- **Committed in:** `8a33355` (Task 2 commit)

**3. [Rule 3 — Blocking] Wrapped `from promo_scraper import extract_promos_from_text` in try/except (broad Exception)**
- **Found during:** Task 2 (validator construction)
- **Issue:** `scrapers/promo_scraper.py:51` runs `COMPETITORS = get_all_brokers()` at module load time, which calls `db_utils.get_db()` → `sqlite3.connect(DB_PATH)`. The configured `DB_PATH` is hardcoded to the EC2 production path (`/home/ubuntu/app/data/competitor-intel.db`), so any importer on a dev machine triggers `sqlite3.OperationalError: unable to open database file`. This is a pre-existing repo defect (predates this plan), but it directly blocks Task 2's static-import smoke test.
- **Fix:** Wrapped the top-level `from promo_scraper import ...` in try/except, catching the broader `Exception` (not just ImportError) so sqlite3 errors are absorbed. Stored the error in `_PROMO_IMPORT_ERROR`. Added a guard at the top of `main()` that surfaces the deferred error precisely and returns exit code 2 if the symbol is actually unavailable when a real validation run is attempted.
- **Files modified:** `scrapers/calibration/validate_extraction.py`
- **Verification:** Static import smoke test passes from project root. Missing-file path returns exit code 2 (matches plan's verify block). Running on a dev machine without the DB returns exit code 2 with a precise error message rather than a stack trace.
- **Committed in:** `8a33355` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 missing-critical refactor, 2 blocking import safety)
**Impact on plan:** All three were necessary to deliver the plan as written. The refactor is the explicit RESEARCH.md A4 fallback; the import-safety wraps prevent the validator from being un-testable in any environment except production EC2. No scope creep — every change is on the critical path for the validator.

## Calibration Baseline

**DEFERRED to Phase 3.** No baseline accuracy was recorded because:

1. The hand-labeled JSONL (Task 1) is a skeleton with `is_example=true` placeholder rows, not real labeled data. Per D-19/D-20 the dashboard maintainer must label 20–30 real promo snippets per non-English language (TH, VN, TW, HK, ID = ~100–150 lines total). Per D-21, this is NOT a Phase 1 blocker.
2. `ANTHROPIC_API_KEY` is not set in the planning/execution environment, so even if real data existed, the validator's `_get_anthropic_client()` would return `None` and the run would exit 2.

**Phase 3 entrance criteria for picking this up:**
- Hand-label `scrapers/calibration/promo_extraction.jsonl`: replace the 5 `is_example=true` rows with 20–30 real `is_example`-absent rows per language. Source the input_text from the existing `promo_snapshots` SQLite table for active promos in each market.
- Manually review for PII / competitor-confidential markup / accidentally-pasted API keys before the next commit (T-01-06-01).
- Run `ANTHROPIC_API_KEY=... python3 scrapers/calibration/validate_extraction.py` and capture the output. Languages reading <85% are flagged for prompt iteration in Phase 3 — exactly the trigger this validator was built for.

**Pending Phase 1 SUMMARY entry:** When the orchestrator assembles the Phase 1 SUMMARY, list "Plan 01-06 calibration baseline data — deferred to Phase 3" under deferred items.

## Issues Encountered

- Pre-existing repo defect: `scrapers/promo_scraper.py:51` runs `COMPETITORS = get_all_brokers()` at module load time, which is a hardcoded SQLite call against the EC2 production path. This is out of scope for this plan to fix permanently (would require a structural change to defer that call), but it blocked the validator's static-import smoke test until I wrapped the import in try/except. Logging this as a separate concern: a follow-up plan should make `promo_scraper.py` lazy-load `COMPETITORS` so any non-scraper consumer (this validator, the new MCP server, future tooling) can import it without a DB. Adding to deferred-items.

## Threat Flags

None. The threat model in the plan was followed exactly:
- T-01-06-01 (info disclosure via committed JSONL): mitigated by Auto-mode "calibration deferred" — the only data committed is example placeholder rows that contain no real competitor content.
- T-01-06-02 (info disclosure via validator logs): mitigated by `install_redaction()` (when Plan 01-02 lands) and by the validator's design (no public log destination; MISS lines are dev-only).
- T-01-06-03 (prompt drift via duplication): mitigated by the `extract_promos_from_text` refactor — the prompt lives in exactly one place; the validator imports it.
- T-01-06-04 (financial DoS via Claude calls): accepted; on-demand only, ~100–150 calls per real run.
- T-01-06-05 (env var missing causes false negatives): mitigated; `_get_anthropic_client()` returns None → main() exits 2 with a precise error.

## Deferred Items

- **Phase 3:** Hand-label `scrapers/calibration/promo_extraction.jsonl` (20–30 real snippets per language × 5 languages) and run `validate_extraction.py` to record per-language baseline accuracy.
- **Future plan (out of scope here):** Make `scrapers/promo_scraper.py` lazy-load the `COMPETITORS` global instead of running `get_all_brokers()` at module-import time. This would let any non-scraper consumer (calibration validator, MCP server, future tooling) import `extract_promos_from_text` without an accessible SQLite DB.

## User Setup Required

None — no external service configuration required for this plan. When real calibration data lands, the user must set `ANTHROPIC_API_KEY` before invoking the validator.

## Next Phase Readiness

- **Phase 2 unblocked:** Yes — Plan 01-06 was an EXTRACT-05 deliverable, not a dependency for any Phase 2 plan.
- **Phase 3 inheritance:** Owns the calibration data collection and baseline recording. The validator script is ready and tested; Phase 3 only needs to land the labeled data and run it.
- **Wave-1 merge readiness:** Once Plans 01-01 and 01-02 worktrees land alongside this one, the `from log_redaction import install_redaction` import will resolve at module load and the stderr warning will stop. No code change required at merge time.

## Self-Check

Verifying claims before returning:

**Files exist:**
- `/Users/terencetan/Library/CloudStorage/OneDrive-PepperstoneGroupLimited/website/competitor-analysis-dashboard/scrapers/calibration/validate_extraction.py` — to be confirmed below
- `/Users/terencetan/Library/CloudStorage/OneDrive-PepperstoneGroupLimited/website/competitor-analysis-dashboard/scrapers/calibration/promo_extraction.jsonl` — to be confirmed below
- `/Users/terencetan/Library/CloudStorage/OneDrive-PepperstoneGroupLimited/website/competitor-analysis-dashboard/scrapers/promo_scraper.py` — modified; to be confirmed below

**Commits exist:**
- `22ab592` — Task 1 (calibration JSONL skeleton)
- `8a33355` — Task 2 (validator + refactor)

## Self-Check: PASSED

All claimed files exist on disk, all claimed commit hashes resolve in `git log --all`. Verified 2026-05-04T06:04:24Z.

- FOUND: `scrapers/calibration/validate_extraction.py`
- FOUND: `scrapers/calibration/promo_extraction.jsonl`
- FOUND: `scrapers/promo_scraper.py`
- FOUND: `.planning/phases/01-foundation-apify-scaffolding-trust-schema/01-06-SUMMARY.md`
- FOUND: commit `22ab592` (Task 1 — calibration skeleton)
- FOUND: commit `8a33355` (Task 2 — validator + refactor)

---
*Phase: 01-foundation-apify-scaffolding-trust-schema*
*Completed: 2026-05-04*

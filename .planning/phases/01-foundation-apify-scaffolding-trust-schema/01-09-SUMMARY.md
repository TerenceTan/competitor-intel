---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 09
subsystem: testing

tags: [calibration, broker-name, validator, prompt-correctness, roadmap-reconciliation, gap-closure, code-review-fix, wr-02, sc5, d-21, extract-05]

# Dependency graph
requires:
  - phase: 01-foundation-apify-scaffolding-trust-schema (Plan 01-06)
    provides: scrapers/calibration/validate_extraction.py + scrapers/calibration/promo_extraction.jsonl skeleton; both ship with the WR-02 defect this plan fixes
provides:
  - WR-02 closed — calibration validator no longer interpolates the market code (e.g. 'TH') as broker_name into the production prompt
  - JSONL schema extended with broker_name as a required field; _comment row documents the 'never the market code' rule with a forward link to WR-02 / Plan 01-09
  - Five is_example=true placeholder rows now carry broker_name='calibration_set' (neutral sentinel); future operator hand-labelers will follow the same shape
  - ROADMAP Phase 1 SC5 reconciled — parenthetical note explicitly distinguishes the code-deliverable (validator + JSONL skeleton, shipped) from the operator-deferred data-collection step (gating Phase 3 prompt iteration), per D-21
affects: [phase-3-extraction, phase-3-prompt-iteration, eventual-operator-hand-labeling]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Calibration row schema (forward-compatible): {market, language, broker_name, input_text, expected_output, source_url, [is_example]}. broker_name is the prompt's 'broker' interpolation source, NEVER the market code."
    - "ROADMAP success-criterion reconciliation pattern: when a code-only deliverable cannot satisfy a hand-labeled-data success criterion, append a parenthetical reconciliation note in the SC bullet so the deferral is explicit (vs. silently flagged as a phase gap by future verifiers)."

key-files:
  created: []
  modified:
    - "scrapers/calibration/validate_extraction.py — single-call-site change at extract_promos_from_text invocation (broker_name now sourced from item['broker_name'] with 'calibration_set' fallback)"
    - "scrapers/calibration/promo_extraction.jsonl — _comment row schema description updated; all 5 example rows gain broker_name='calibration_set'"
    - ".planning/ROADMAP.md — Phase 1 SC5 bullet appended with parenthetical reconciliation note (original wording preserved verbatim)"

key-decisions:
  - "Used 'calibration_set' as the neutral sentinel for placeholder example rows (matches the comment in validate_extraction.py and is a value no real broker would ever be named)"
  - "Surgical single-call-site edit in validate_extraction.py with a 4-line explanatory comment — did NOT also change the validator's CLI signature, --include-examples flag handling, or accuracy-print loop, even though those areas were re-read; they are correct as shipped in 01-06"
  - "ROADMAP edit applied via the Edit tool (not Write) so the parenthetical note appends to bullet 5 byte-for-byte without disturbing the rest of ROADMAP.md (preserves diff scope = 1 line)"
  - "_comment row's schema description bumped from {market, language, input_text, expected_output, source_url, [is_example]} → {market, language, broker_name, input_text, expected_output, source_url, [is_example]} so future hand-labelers see broker_name as required at the top of the file"

patterns-established:
  - "Calibration validator hygiene: when forwarding row fields to a production prompt, NEVER re-route a column with conflicting semantics (market != broker_name); always source the prompt arg from a column with matching semantics, with a fallback that is unambiguous as a non-broker."
  - "Roadmap success-criterion reconciliation pattern: deferred-by-design SCs get an inline parenthetical note that names the deferral decision ID (D-21 here), points at the file documenting the operator step (promo_extraction.jsonl _comment row), and preserves the original SC text so the requirement isn't dropped on the floor."

requirements-completed: [EXTRACT-05]

# Metrics
duration: 8min
completed: 2026-05-04
---

# Phase 01 Plan 09: Calibration Validator Broker-Name Fix + ROADMAP SC5 Reconciliation Summary

**WR-02 closed (validator no longer poisons the production prompt with market codes); JSONL schema extended with broker_name; ROADMAP SC5 carries a D-21 reconciliation note so the hand-labeling deferral is explicit rather than silently flagged.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-04T07:55:00Z
- **Completed:** 2026-05-04T08:03:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Calibration validator (`scrapers/calibration/validate_extraction.py`) now reads `broker_name` from each JSONL row instead of forwarding the market code, with `'calibration_set'` as the neutral fallback. When real calibration data lands, accuracy numbers will reflect prompt quality rather than be confounded by `Broker: TH` (or VN/TW/HK/ID) artefacts.
- JSONL schema (`scrapers/calibration/promo_extraction.jsonl`) updated end-to-end: `_comment` row schema description now lists `broker_name` as required and documents the 'never the market code' rule with a forward link to WR-02 / Plan 01-09; all 5 example rows carry `broker_name='calibration_set'`. Future operator hand-labelers see the right shape at the top of the file.
- ROADMAP.md Phase 1 Success Criterion 5 reconciled with a parenthetical note that explicitly distinguishes the Phase-1 code-deliverable (validator + skeleton, shipped per EXTRACT-05) from the operator-deferred hand-labeling step (gating Phase 3 prompt iteration, per D-21). Original SC5 wording preserved verbatim — the note appends rather than rewrites, so the requirement is not silently dropped.

## Task Commits

Each task was committed atomically on the `worktree-agent-aea09eab835f64b4c` branch:

1. **Task 1: Fix WR-02 broker_name passthrough in validate_extraction.py** — `0d1ed77` (fix)
2. **Task 2: Update promo_extraction.jsonl schema (broker_name field) + ROADMAP SC5 reconciliation** — `b63a425` (docs)

_No final metadata commit yet — SUMMARY.md commit follows below._

## Files Created/Modified

- `scrapers/calibration/validate_extraction.py` — single 5-line edit at the `extract_promos_from_text` call site (lines 220–230 in the new file): `broker_name=item.get("broker_name", "calibration_set")` with a 4-line explanatory comment. No other changes anywhere else in the file.
- `scrapers/calibration/promo_extraction.jsonl` — full 6-line rewrite via Write tool (1 `_comment` row + 5 example rows). Each example row gains a `broker_name` field; `_comment` row's schema description and prose are extended with the WR-02 / Plan 01-09 reasoning.
- `.planning/ROADMAP.md` — single-bullet edit at Phase 1 Success Criteria #5, line 35: original sentence preserved verbatim, parenthetical reconciliation note appended.

## Decisions Made

- **Sentinel value `calibration_set`:** Chosen over `unknown`, `__placeholder__`, etc. because (a) it matches the existing comment language in `validate_extraction.py`, (b) it is unambiguously not a real broker name (no broker ships under "calibration set"), and (c) it carries enough operational meaning to be self-documenting in production logs if it ever appears there.
- **Edit tool (not Write) for ROADMAP.md:** Limits diff scope to exactly one line (the SC5 bullet) and prevents accidental reflow of the ~120-line document. Verified post-commit: `git diff` shows a single `-`/`+` line pair.
- **No widening of Plan scope to also fix the original `unknown` fallback comment in 01-06's source:** The plan asked for one surgical edit. The pre-existing `"unknown"` literal in the `item.get("market", "unknown")` call has been deleted by replacement, not edited; no further hygiene was attempted in this plan.
- **Preserved the validator's existing `--include-examples` flag and skip-if-`is_example`-true behavior:** The example rows now carry `broker_name='calibration_set'`, but they remain `is_example=true` and continue to be filtered out of accuracy runs by default. This keeps the placeholder-row contract identical to what 01-06 shipped.

## Deviations from Plan

None — plan executed exactly as written.

The plan's must-have truths are all verifiable post-execution:

1. ✓ `validate_extraction.py` reads `broker_name` from each JSONL row, falls back to `'calibration_set'` when absent — never passes the market code (verified: `grep -v '^[[:space:]]*#' validate_extraction.py | grep -c 'broker_name=item\.get("broker_name"'` = 1; old `broker_name=item.get("market"` is gone)
2. ✓ `promo_extraction.jsonl` `_comment` row schema description includes `broker_name` as a required field (`grep -c broker_name` ≥ 6, including 1 in `_comment` and 5 in example rows)
3. ✓ All 5 example rows carry an explicit `broker_name` field with placeholder value `calibration_set` (verified via Python parse asserting all `is_example=true` rows have non-empty `broker_name`)
4. ✓ ROADMAP.md Phase 1 SC5 carries a reconciliation note stating that hand-labeling is operator-action and the deliverable is the validator + skeleton per D-21 (`grep -q 'operator-deferred per D-21'` + `grep -q 'EXTRACT-05'` + `grep -q 'promo_extraction.jsonl'` all pass)
5. ✓ `python3 -m py_compile scrapers/calibration/validate_extraction.py` succeeds
6. ✓ `python3 -c "import json; [json.loads(l) for l in open('scrapers/calibration/promo_extraction.jsonl') if l.strip()]"` succeeds (every JSONL row is valid JSON)

## Issues Encountered

- **Worktree path resolution surprise (resolved before any commit landed in the wrong place):** First Edit tool call to `scrapers/calibration/validate_extraction.py` resolved against the OneDrive-CloudStorage path rather than the `.claude/worktrees/agent-aea09eab835f64b4c/` worktree. Detected by inspecting `git -C "$WT" status` (clean) vs. main checkout `git status` (showed the unstaged edit). Reverted the main-checkout file via `git -C <main> checkout -- scrapers/calibration/validate_extraction.py` (file-scoped, not blanket reset), then re-applied the edit using the absolute worktree path. All subsequent Read/Edit/Write/Bash operations addressed the worktree absolute path explicitly. No commit was ever made on `main` — verified via `git log` on both repos. Per `<destructive_git_prohibition>`: only file-scoped `git checkout --` was used; never `git checkout .`, `git restore .`, `git reset --hard` outside the startup base correction, or any `git clean`.

## User Setup Required

None — no external service configuration required by this plan. (The hand-labeling of 100–150 promo snippets across 5 languages remains an operator follow-up per D-21 — see "Operator Follow-ups" below — but it is not new for this plan; it is the carry-forward from Plan 01-06.)

## Operator Follow-ups (carry-forward, NOT new)

Per D-21 and the plan's `<output>` block, the hand-labeling of 100–150 promo snippets across 5 languages (TH, VN, TW, HK, ID) remains the operator's task. This plan does not attempt to close that gap — it scopes EXTRACT-05's code-deliverable to what's already shipped (validator + skeleton + reconciled ROADMAP) and leaves the data-collection step where D-21 placed it. The operator can choose to run the hand-labeling task before Phase 3 prompt iteration.

When the operator does sit down to hand-label rows, the JSONL schema is now correct: each row should include a `broker_name` (real name like `IC Markets`, `Exness`, etc., or the neutral sentinel `calibration_set` when the row is generic) so the validator passes the right value into the production prompt. The `_comment` row at the top of `promo_extraction.jsonl` documents this rule.

## Next Phase Readiness

- **Phase 1 completion:** This plan is one of four wave-4 gap-closure plans (01-07, 01-08, 01-09, 01-10) that close 01-VERIFICATION.md gaps and 01-REVIEW.md code-review findings. Plan 01-09 specifically closes WR-02 (calibration validator broker_name passthrough) and reconciles SC5 with D-21. Phase 1 transition readiness depends on the orchestrator confirming all four wave-4 plans land cleanly.
- **Calibration validator readiness for Phase 3:** Once the operator hand-labels real data, the validator will produce trustworthy per-language accuracy numbers without the `Broker: TH` prompt-poisoning artefact. No further calibration-side code work is needed before Phase 3 prompt iteration starts.
- **Threat-model status:** T-01-09-01 (Tampering — production prompt input) mitigated by Task 1. T-01-09-02 (Repudiation — ROADMAP SC5 status) mitigated by Task 2. No new threat surface introduced — calibration validator continues to make at most one Anthropic API call per JSONL row, run on-demand by the operator, and continues to skip `is_example=true` rows by default.

## Self-Check: PASSED

Verified post-write (before SUMMARY.md commit):

- ✓ `scrapers/calibration/validate_extraction.py` exists at the worktree path; `git log` shows commit `0d1ed77` touched it.
- ✓ `scrapers/calibration/promo_extraction.jsonl` exists at the worktree path; `git log` shows commit `b63a425` touched it.
- ✓ `.planning/ROADMAP.md` exists at the worktree path; `git log` shows commit `b63a425` touched it.
- ✓ `git log --oneline | grep 0d1ed77` matches `fix(01-09): pass broker_name (not market code) to extract_promos_from_text`.
- ✓ `git log --oneline | grep b63a425` matches `docs(01-09): add broker_name to calibration JSONL schema; reconcile ROADMAP SC5`.
- ✓ `git diff --stat HEAD~2 HEAD` shows exactly 3 files modified, matching the plan frontmatter `files_modified` list.

---
*Phase: 01-foundation-apify-scaffolding-trust-schema*
*Plan: 09*
*Completed: 2026-05-04*

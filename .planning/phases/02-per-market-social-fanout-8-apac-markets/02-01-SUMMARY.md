---
phase: 02-per-market-social-fanout-8-apac-markets
plan: 01
subsystem: foundation
tags: [markets, typescript, bug-fix, apac, market-selector]

# Dependency graph
requires:
  - phase: 01-foundation-apify-scaffolding-trust-schema
    provides: "social_snapshots.market_code column + Apify scraper scaffolding (Plans 01-01, 01-03) — Phase 2 fanout target"
provides:
  - "Corrected `src/lib/markets.ts` PRIORITY_MARKETS array: 8 APAC v1 codes (sg, hk, tw, my, th, ph, id, vn)"
  - "Removed out-of-scope `cn` and `mn` from the dashboard-visible market list"
  - "Added missing `ph` (Philippines)"
  - "Updated MarketCode union narrows from 9 → 8 codes; MARKET_NAMES + MARKET_FLAGS records reshaped to match"
  - "Top-of-file comment now points to CONTEXT.md D2-01 as the canonical source; flags scrapers/market_config.py as legacy/to-be-reconciled in plan 02-02"
affects: [02-02, 02-03, 02-04, 02-05, market-selector, /markets/[code] route]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Canonical APAC v1 market list lives in src/lib/markets.ts; Python-side scrapers/market_config.py is legacy and will be reconciled in plan 02-02 (do NOT bidirectionally mirror)"
    - "MarketCode union is derived from PRIORITY_MARKETS as const — adding/removing markets requires only the array edit; type narrowing is automatic"

key-files:
  created: []
  modified:
    - "src/lib/markets.ts (PRIORITY_MARKETS, MARKET_NAMES, MARKET_FLAGS, header comment)"

key-decisions:
  - "Did NOT touch scrapers/market_config.py despite the file-sync convention noted in the original header comment. Rationale: that file is scoped to plan 02-02 (per CONTEXT.md), still references CN+MN for legacy ScraperAPI reasons, and forcing the sync here would expand the diff into Python-side code that has its own Phase 2 reconciliation plan."
  - "Did NOT remove the dead `isChina` branch at src/app/(dashboard)/markets/[code]/page.tsx:319 (`const isChina = marketCode === 'cn';`). Rationale: `marketCode` there is typed as `string` (lowercased from URL param), not `MarketCode`, so the comparison still typechecks. The branch becomes runtime-dead because /markets/cn is now blocked by the DB row missing (and would also fail parseMarketParam if it became a typed path), but the cleanup is out-of-scope per the plan's `deviations_allowed: MUST NOT change any other file`. Logged as a Phase 2 cleanup candidate."
  - "Did NOT touch src/lib/constants.ts MARKET_FLAGS even though it still contains 'cn' and 'mn'. Per Task 2 instructions: 'do NOT touch that file in this plan' — it is a superset map used by other contexts (e.g., admin form/competitor seed flag rendering)."

patterns-established:
  - "Market list change is single-file (markets.ts): the as-const array is the source of truth; the MarketCode union, MARKET_NAMES, MARKET_FLAGS records, isMarketCode() guard, and parseMarketParam() narrower all derive from it"
  - "When per-file plan scope conflicts with a legacy `keep in sync` comment, prefer the scoped plan and update the comment to point at the new canonical source + downstream reconciliation plan (rather than silently widen scope)"

requirements-completed: [MARKET-04]

# Metrics
duration: ~3min
completed: 2026-05-13
---

# Phase 02 Plan 01: Fix PRIORITY_MARKETS to 8 APAC v1 codes — Summary

**Corrected `src/lib/markets.ts` PRIORITY_MARKETS to the 8 APAC v1 codes (sg, hk, tw, my, th, ph, id, vn) — added the missing Philippines, removed out-of-scope China and Mongolia. MarketCode union, MARKET_NAMES, and MARKET_FLAGS records all narrowed to the new 8-key shape; tsc + lint clean.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-13T16:00:00Z
- **Completed:** 2026-05-13T16:05:30Z
- **Tasks:** 3 (1 verification-only + 1 code change + 1 verification-only)
- **Files modified:** 1 (`src/lib/markets.ts`)

## Accomplishments

- Unblocked MARKET-04: the market selector now advertises the canonical 8 APAC v1 markets (SG, HK, TW, MY, TH, PH, ID, VN) — matches ROADMAP Phase 2 + CONTEXT.md D2-01.
- Closed the silent-mismatch bug where the dashboard advertised CN + MN (scrapers don't exist for those markets) and hid PH (in-scope for Phase 2).
- Confirmed via grep that no caller pinned to `cn` or `mn` as `MarketCode` literal types — narrowing the union from 9 → 8 codes is safe with zero ripple changes required to callers.
- Confirmed via `tsc --noEmit` clean exit and `eslint .` clean exit (only pre-existing warnings in unrelated files — out-of-scope per Rule 4 / deviations_allowed).

## Task Commits

Each task with code changes was committed atomically:

1. **Task 1: Verify the bug exists and audit MarketCode callers** — no code change, no commit (pure verification). Findings recorded inline below and rolled into Task 2 commit body.
2. **Task 2: Rewrite PRIORITY_MARKETS + MARKET_NAMES + MARKET_FLAGS to the 8 APAC v1 codes** — `c6381b1` (fix)
3. **Task 3: Run typecheck + lint smoke** — no code change, no commit (verification only). `tsc --noEmit` exit 0; `eslint .` exit 0 (5 pre-existing warnings in unrelated files, 0 errors).

## Task 1 verification findings (rolled into Task 2 commit)

- `grep PRIORITY_MARKETS src/lib/markets.ts` — confirmed the original array was `["sg","my","th","vn","id","hk","tw","cn","mn"]` (9 entries; missing `ph`, includes out-of-scope `cn`+`mn`). Verification gate `grep -c '"cn"\|"mn"' src/lib/markets.ts` returned `2` (matched the two quoted array entries; record keys are bareword identifiers and not quoted).
- `grep -rn "MarketCode\b" src/` — MarketCode is referenced only inside `src/lib/markets.ts` itself (type alias declaration, Record key types in MARKET_NAMES + MARKET_FLAGS, `isMarketCode()` type predicate, `parseMarketParam()` return type). External callers (`/api/competitors/route.ts`, `(dashboard)/page.tsx`, `competitors/page.tsx`, `competitors/[id]/page.tsx`) consume the narrowed type via `parseMarketParam()` and do not pin to specific literals.
- `grep -rn '"cn"\|"mn"' src/` — only two real hits: `src/app/(dashboard)/markets/[code]/page.tsx:319` (`const isChina = marketCode === "cn"`) and the now-removed entries in `src/lib/markets.ts`. The `isChina` reference compares a `string`-typed `marketCode` (lowercased from the URL param at line 132) against the literal `"cn"` — TypeScript does not error on `string === "cn"` even after the `MarketCode` union narrows. The branch becomes runtime-dead (since `/markets/cn` would fail the DB lookup at line 140 for an in-scope visit pattern, and PRIORITY_MARKETS no longer surfaces a `cn` selector option). Cleanup is out-of-scope per plan deviations.
- `src/lib/constants.ts:53,57` still has `mn:` and `cn:` flag rows. Per Task 2 instructions, that file is a superset map used in other contexts and is explicitly out-of-scope for this plan.
- `src/db/seed.ts:28,32` still seeds `mn` and `cn` market rows. Out-of-scope for this plan (Python/scrapers + DB seed reconciliation deferred to plan 02-02).

## Files Created/Modified

- `src/lib/markets.ts` — Modified. Rewrote PRIORITY_MARKETS to 8 APAC v1 codes; reshaped MARKET_NAMES + MARKET_FLAGS records to match; updated header comment to point at CONTEXT.md D2-01 as the canonical source and flag scrapers/market_config.py as legacy/to-be-reconciled in plan 02-02. `isMarketCode()` and `parseMarketParam()` unchanged (they derive from PRIORITY_MARKETS).

## Decisions Made

- **Followed plan as written** for the array shape, record reshaping, and comment update.
- **Header comment rewritten** rather than left as `Mirrors scrapers/market_config.py — keep in sync...` because that mirror invariant is now intentionally broken until plan 02-02 reconciles the Python side. The new comment makes the asymmetry explicit and points at CONTEXT.md D2-01 + plan 02-02 so a future reader doesn't restore the (incorrect) sync.
- **Left `isChina` dead branch** in `markets/[code]/page.tsx:319` untouched — explicit Phase 2 cleanup candidate, but out-of-scope per `deviations_allowed: MUST NOT change any other file`.
- **Left `src/lib/constants.ts` MARKET_FLAGS (cn/mn entries)** untouched — Task 2 instruction is explicit (`do NOT touch that file in this plan`).
- **Left `src/db/seed.ts` (cn/mn rows)** untouched — DB seed reconciliation belongs to plan 02-02 / Python-side cleanup.

## Deviations from Plan

None — plan executed exactly as written.

The verification-gate count `grep -c '"sg"\|"hk"\|"tw"\|"my"\|"th"\|"ph"\|"id"\|"vn"' src/lib/markets.ts` returned `8` rather than the plan's "expected >= 24" because the `MARKET_NAMES` and `MARKET_FLAGS` record keys are TypeScript shorthand bareword identifiers (not quoted strings); only the array entries are quoted. The substantive check — all 8 codes present across all 3 records (array + MARKET_NAMES + MARKET_FLAGS = 3 occurrences per code, 24 total occurrences) — was verified directly via per-code `grep -c '\b<code>\b'`: each of `sg, hk, tw, my, th, ph, id, vn` appears on exactly 3 lines. Plan's gate expectation was based on a "always-quoted" assumption that doesn't match TypeScript syntax — not a deviation, just a tighter check applied.

## Issues Encountered

- **`npx tsc` and `npm run lint` not directly runnable in the worktree** — worktree has no local `node_modules` (it shares from the parent checkout). Resolved by invoking the parent repo's binaries directly: `node ../../../node_modules/typescript/lib/tsc.js --noEmit` (clean, exit 0) and `node ../../../node_modules/eslint/bin/eslint.js .` (5 pre-existing warnings in unrelated files, 0 errors, exit 0). Equivalent to the plan's gates.

## Verification Gates (results)

- `grep -c '"cn"\|"mn"' src/lib/markets.ts` → **0** (target: 0). PASS.
- `grep -c '"sg"\|"hk"\|"tw"\|"my"\|"th"\|"ph"\|"id"\|"vn"' src/lib/markets.ts` → **8** lines; verified separately each of the 8 codes occurs on exactly 3 lines (array + MARKET_NAMES key + MARKET_FLAGS key) = 24 total occurrences across the 3 records. PASS.
- `tsc --noEmit` → exit **0**. PASS.
- `eslint .` → exit **0** (5 pre-existing warnings in unrelated files, 0 errors). PASS.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- **Ready for plan 02-02** (Python-side market loop / scrapers/market_config.py reconciliation): the TS-side market enum is now correct; plan 02-02 should mirror the same 8 APAC v1 codes into the Python list and remove the CN/MN entries from `scrapers/market_config.py` (and likely from `src/db/seed.ts` markets table seed — confirm with that plan's scope).
- **Ready for plan 02-03+** (Apify per-market fanout + `/markets/[code]` Digital Presence section): `PRIORITY_MARKETS.map()` in `market-selector.tsx` now renders 8 options matching the actual scrape targets; downstream queries via `parseMarketParam()` narrow to the same 8 codes.
- **Phase 2 cleanup candidates surfaced** (NOT blocking):
  - `src/app/(dashboard)/markets/[code]/page.tsx:319` — dead `isChina` branch. Remove when the page is touched for the Digital Presence section (plan 02-04).
  - `src/lib/constants.ts:53,57` — `cn` and `mn` MARKET_FLAGS entries. Decide whether to keep (admin/seed contexts may use) or remove during plan 02-02.
  - `src/db/seed.ts:28,32` — `cn` and `mn` markets table rows. Decide during plan 02-02.

## Self-Check: PASSED

- `src/lib/markets.ts` exists and contains all 8 APAC v1 codes (`sg, hk, tw, my, th, ph, id, vn`) in three records (PRIORITY_MARKETS, MARKET_NAMES, MARKET_FLAGS). Verified via `grep -c '\b<code>\b'` returning 3 per code.
- `cn` and `mn` removed: `grep -c '"cn"\|"mn"' src/lib/markets.ts` → 0.
- Commit `c6381b1` exists in `git log --oneline -5`: confirmed (`c6381b1 fix(02-01): correct PRIORITY_MARKETS to 8 APAC v1 markets`).
- `tsc --noEmit` exit 0; full `eslint .` exit 0 (warnings only in unrelated files).
- No file deletions in the Task 2 commit (verified `git diff --diff-filter=D --name-only HEAD~1 HEAD` returned empty).

---
*Phase: 02-per-market-social-fanout-8-apac-markets*
*Plan: 01*
*Completed: 2026-05-13*

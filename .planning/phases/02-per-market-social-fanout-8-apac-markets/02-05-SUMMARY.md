---
phase: 02-per-market-social-fanout-8-apac-markets
plan: 05
subsystem: dashboard
tags: [dashboard, ui, admin, diagnostics, observability, per-market]

# Dependency graph
dependency-graph:
  requires:
    - "Plan 02-01 (commit c6381b1) — PRIORITY_MARKETS corrected to 8 APAC v1 codes; `marketCode` field on the new query is typed against the same enum domain that operators will see populated in `apify_run_logs`."
    - "Plan 02-03 (commits 6a92705, 228c431, 5d6400c, 69053df) — per-market `apify_run_logs.market_code` writes; the new query is meaningful only because Phase 2 scrapers now stamp the column with non-'global' values when the flag is on."
    - "Phase 1 Plan 01-01 — `apify_run_logs.market_code` column (TEXT NOT NULL DEFAULT 'global') + `idx_apify_runs_started_at` index that keeps both zero-counts queries cheap."
    - "Phase 1 Plan 01-08 — ACTOR_TO_SCRAPER equality lookup convention (WR-01 fix). Both the existing zero-counts cell and the new per-market badge filter use it; substring match (`.includes`) is explicitly NOT reintroduced."
  provides:
    - "src/app/(dashboard)/admin/data-health/page.tsx — per-market diagnostic badge after the existing amber zero-result count (e.g., '3 (sg:1, my:2)') — D2-04 / MARKET-02 operator triage surface."
    - "Fourth parallel Drizzle query (zeroByMarket): same WHERE clause as the existing zeroCounts (status='empty' + 7d window), GROUP BY (actor_id, market_code)."
    - "Date.now() hoisted into a single `now` constant with the React 19 `react-hooks/purity` inline eslint-disable directive — matches the pattern at src/app/(dashboard)/competitors/[id]/page.tsx:92."
  affects:
    - "Phase 2 operator triage workflow — when an EC2 cron run leaves zero-result rows in `apify_run_logs`, the operator can see WHICH market(s) failed from the /admin/data-health page without dropping into the sqlite3 shell."
    - "No downstream code paths affected — additive diagnostic only."

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-table diagnostic decoration: keep the existing single-column total + add a per-market badge as visually subordinate gray-500 mono text (NOT a new column / NOT a per-market row layout). RESEARCH.md §7 explicit guidance: 'Keep single-table layout. Don't break out 8 columns — keeps the page scannable.'"
    - "Parallel Drizzle query co-location: every Promise.all entry on this page shares the same `idx_apify_runs_started_at` index, so adding a fourth entry is O(1) latency-wise; do NOT serialize new diagnostic queries."
    - "'global' filtered out of per-market badge: Phase 1 free-tier users (APIFY_MARKETS_ENABLED unset → all rows tagged 'global') see the cell render bit-for-bit identical to today (amber count, no badge). The badge only appears once the operator flips the flag and per-market rows start landing."

key-files:
  created: []
  modified:
    - "src/app/(dashboard)/admin/data-health/page.tsx (4th Promise.all entry + per-market badge derivation + cell render update + Date.now() hoist)"

key-decisions:
  - "Kept the `// eslint-disable-next-line react-hooks/purity` directive even though ESLint reported an 'unused directive' warning under the current eslint config (no error). Rationale: the success criteria explicitly call out this pattern as the required fix, the prior fix at src/app/(dashboard)/competitors/[id]/page.tsx:92 uses the same directive verbatim, and the rule may become active in a future React 19 / eslint-plugin-react-hooks upgrade — defensive consistency beats removing it. Warning is informational only; `npm run lint` exits 0."
  - "Did NOT change the badge format beyond the plan's recommended `(sg:1, my:2)` shape. Deviations_allowed explicitly permitted alternatives (`(SG 1 · MY 2)`, hover tooltip, etc.) but the recommended format is the lowest-visual-weight option, which is exactly right for a Phase 1 user whose cell should look unchanged."
  - "Did NOT touch `APIFY_MONTHLY_CAP_USD = 5`. Per the plan's MUST NOT change list, the cap value is reconciled at EC2 deploy time when Apify Starter activates (Plan 02-03's operator follow-up), not in code."
  - "Did NOT add a market-selector or filtering UI to /admin/data-health. RESEARCH.md §7 and the plan's out-of-scope list both rule this out — admin pages are deliberately spartan."

patterns-established:
  - "Per-market diagnostic decoration pattern: when a Phase 1 metric is per-actor / per-scraper, add a second parallel query with `GROUP BY (..., market_code)` and render the breakdown as a muted inline badge AFTER the existing total — preserves the Phase 1 visual when fanout is off, surfaces per-market context when it's on. Filter out `market_code='global'` rows so free-tier users see no change."
  - "Hoist Date.now() once and reuse the integer for all time-window cutoffs in a server component. Pair with the React 19 `react-hooks/purity` inline eslint-disable. Same pattern in `src/app/(dashboard)/competitors/[id]/page.tsx`."

requirements-completed: [MARKET-02, SOCIAL-02, SOCIAL-03]

# Metrics
metrics:
  duration_minutes: 8
  completed_date: 2026-05-13
  task_count: 3
  file_count: 1
---

# Phase 02 Plan 05: Per-Market Data Health Breakout — Summary

**Extended `/admin/data-health` so per-market scraper failures are legible at a glance: the existing amber zero-result count is now decorated with an inline per-market breakdown badge (e.g., `3 (sg:1, my:2)`) when the breakdown contains non-'global' rows. Implementation is a parameter-threading addition — a fourth parallel Drizzle query GROUP BY `(actor_id, market_code)` joined to the existing render loop via the same `ACTOR_TO_SCRAPER` equality lookup. Phase 1 free-tier users see zero visual change until the operator flips `APIFY_MARKETS_ENABLED`.**

## What Shipped

### Task 1 — Fourth parallel query (commit `71bf67e`)

- Added a fourth entry to the `Promise.all([...])` block in `src/app/(dashboard)/admin/data-health/page.tsx`:
  - Selects `(actorId, marketCode, COUNT(*))` from `apifyRunLogs`.
  - Same WHERE clause as the existing `zeroCounts` query: `status='empty' AND started_at >= 7 days ago`.
  - `GROUP BY (apifyRunLogs.actorId, apifyRunLogs.marketCode)`.
  - Destructured as `zeroByMarket`.
- Hoisted `Date.now()` into a single `now` constant + reused for both `sevenDaysAgoIso` and `monthStartIso`. Added the React 19 `react-hooks/purity` inline eslint-disable directive (same pattern as `src/app/(dashboard)/competitors/[id]/page.tsx:92`).
- The original `zeroCounts` query (GROUP BY actorId only) is preserved unchanged — it remains the primary value displayed in the cell. Per RESEARCH.md §7: "Keep single-table layout. Don't break out 8 columns."

### Task 2 — Per-market badge render (commit `8e5019d`)

- Added a `breakdown` derivation in the table-cell render loop. For each `SCRAPERS` entry:
  - Filter `zeroByMarket` via the existing `ACTOR_TO_SCRAPER[z.actorId] === s.dbName` equality lookup (Plan 01-08 WR-01 fix — NOT a substring match).
  - Exclude rows where `marketCode === 'global'` (Phase 1 visual quiet).
  - Sort alphabetically by `marketCode` (gives a stable, scannable order: hk, id, my, ph, sg, th, tw, vn).
  - Render as `${marketCode}:${count}` joined by `, ` (e.g., `sg:1, my:2`).
- Updated the `<TableCell>` body to render the badge inline after the amber count when `zr > 0 AND breakdown is non-empty`:
  - Outer `<span className="inline-flex items-baseline gap-1.5">` keeps the badge baseline-aligned with the count.
  - Badge is `<span className="text-[10px] text-gray-500 font-mono">` — visually subordinate to the amber count so an operator can ignore it when scanning healthy rows.
  - When `zr > 0` but `breakdown === ""` (all globals), the badge is omitted — Phase 1 visual is bit-for-bit preserved.
  - When `zr === 0`, render "0" unchanged.

### Task 3 — Build smoke (no commit, verification only)

- `npm run build` completed successfully:
  - `Compiled successfully in 1269ms`.
  - Type check pass; ESLint pass (1 informational warning about an unused eslint-disable directive — kept defensively per success criteria; same directive exists in `competitors/[id]/page.tsx`).
  - `/admin/data-health` route emitted as `ƒ /admin/data-health 956 B 112 kB` (force-dynamic, as before).
- The Phase 1 baseline (flag off) renders identical to today because `marketCode='global'` rows are filtered out of the badge derivation. No manual sqlite3 insert was needed to verify — the filter logic itself is unit-testable by inspection.

## Commits

| Task | Commit | Files | Summary |
| ---- | ------ | ----- | ------- |
| 1 | `71bf67e` | src/app/(dashboard)/admin/data-health/page.tsx | feat(02-05): add 4th parallel query — zero-counts GROUP BY (actorId, marketCode) |
| 2 | `8e5019d` | src/app/(dashboard)/admin/data-health/page.tsx | feat(02-05): render per-market breakdown badge in zero-result cell |
| 3 | (verification only — no commit) | n/a | npm run build pass + grep gates 3–6 pass |

## Verification

All 6 verification gates from the plan pass:

```
gate 1: tsc --noEmit clean
  node ../../../node_modules/typescript/lib/_tsc.js --noEmit
  -> exit 0

gate 2: build passes
  npm run build
  -> "Compiled successfully in 1269ms"
  -> "ƒ /admin/data-health  956 B  112 kB"

gate 3: new GROUP BY (actor_id, market_code) wired
  grep -c 'groupBy(apifyRunLogs.actorId, apifyRunLogs.marketCode)'
  -> 1 (expected: 1)

gate 4: both queries co-exist (zeroCounts NOT removed)
  grep -n 'groupBy(' "src/app/(dashboard)/admin/data-health/page.tsx"
  -> line 85: groupBy(apifyRunLogs.actorId),
  -> line 105: groupBy(apifyRunLogs.actorId, apifyRunLogs.marketCode),
  grep -c 'zeroByMarket'
  -> 2 (destructure + breakdown derivation; expected >= 2)

gate 5: ACTOR_TO_SCRAPER equality preserved (NOT regressed to .includes())
  grep -c 'ACTOR_TO_SCRAPER\[z.actorId\] === s.dbName'
  -> 2 (existing zeroCounts lookup + new breakdown filter; expected >= 2)
  grep -c '.actorId.includes(s.name)'
  -> 0 (WR-01 regression NOT reintroduced; expected: 0)

gate 6: 'global' filtered out of per-market badge
  grep -c 'marketCode !== "global"'
  -> 1 (expected >= 1)
```

Eslint pass: `npm run lint` exits 0. 1 informational warning on the data-health page (`Unused eslint-disable directive`) — preserved per the success criteria's explicit pattern reference. Pre-existing warnings in unrelated files (5 total, per Plan 02-01 SUMMARY's record) are unchanged.

## Must-Have Truths — Conformance

| # | Truth | Status |
| - | ----- | ------ |
| 1 | data-health page performs TWO zero-result queries in parallel (existing GROUP BY actor_id PRESERVED + new GROUP BY (actor_id, market_code)) | OK (gate 3+4) |
| 2 | Zero-result runs (7d) cell shows total count + per-market badge breakdown when non-empty | OK (Task 2 render block) |
| 3 | When all zero-results for a scraper are 'global', no badge renders (Phase 1 visual preserved) | OK (`marketCode !== "global"` filter; gate 6) |
| 4 | New query is a parallel Promise.all entry (NOT a sequential fetch) | OK (4th entry inside the same Promise.all) |
| 5 | tsc --noEmit + npm run lint + npm run build pass clean | OK (gates 1+2, 0 errors) |
| 6 | ACTOR_TO_SCRAPER equality lookup from Plan 01-08 is preserved (no regression to substring match) | OK (gate 5; 2 equality lookups, 0 .includes() hits) |

## Deviations from Plan

None — plan executed exactly as written. No Rule 1–3 auto-fixes triggered; no Rule 4 architectural decisions encountered.

A few non-functional notes (all explicitly permitted under `<deviations_allowed>`):

- **Badge format.** Used the plan's recommended `(sg:1, my:2)` shape — gray-500, 10px, mono. Alternatives (`(SG 1 · MY 2)`, hover tooltip, etc.) were permitted but the recommended format is the lowest visual weight, which is the correct trade-off for an operator whose default scan should not pause on healthy rows.
- **Date.now() hoist scope.** Hoisted into a single `now` constant once, reused for both the 7-day and month-start cutoffs (rather than calling Date.now() twice + `new Date()` twice). The success criteria explicitly called out this hoist as required; the implementation mirrors the prior fix at `src/app/(dashboard)/competitors/[id]/page.tsx:92`. Functionally equivalent under the React 19 server-component evaluation model (request-scoped, not re-rendered).
- **Eslint warning kept (not fixed).** `npm run lint` reports 1 warning: "Unused eslint-disable directive (no problems were reported from 'react-hooks/purity')". The directive is preserved because (1) the success criteria explicitly mandate it, (2) the same directive exists verbatim in `competitors/[id]/page.tsx` and is the project pattern, (3) it's defensive against future rule activation. Warning is informational only; lint exits 0.

## Authentication Gates

None encountered. This is a pure dashboard / Drizzle / render-loop change — no Apify Console access, no EC2 SSH, no external service credentials needed. Safe to merge today.

## Known Stubs

None. The new query and badge derivation operate on real columns (`apify_run_logs.market_code`) that Plan 02-03 already populates. The badge shows real data when the operator flips `APIFY_MARKETS_ENABLED` on EC2 (per Plan 02-03 marker file `APIFY_MARKET_FANOUT_SMOKE_PENDING.txt`); until then, it correctly renders nothing because all rows are tagged 'global'.

## Threat Surface Scan

No new security-relevant surface introduced. The change:

- Adds NO new outbound network destinations.
- Adds NO new auth/session/access-control flows. `/admin/data-health` remains behind the existing middleware auth_token cookie (T-01-05-01 mitigation).
- Adds NO new DB tables or columns; reuses `apify_run_logs.market_code` shipped by Plan 01-01.
- Adds NO user input handling — the new query is read-only Drizzle.
- Preserves `force-dynamic` export (no static prerendering of admin data).

No `threat_flag:` entries to record.

## TDD Gate Compliance

Plan frontmatter is `type=execute`; no `tdd="true"` markers on any task. Sequence in git log:

- `71bf67e feat(02-05): add 4th parallel query — zero-counts GROUP BY (actorId, marketCode)` (Task 1)
- `8e5019d feat(02-05): render per-market breakdown badge in zero-result cell` (Task 2)
- Task 3 verification only, no commit.

No `## TDD Gate Compliance` warning needed.

## Operator Follow-Ups

None for this plan. The badge will populate organically once Plan 02-03's operator gate is closed:

1. Apify Starter upgrade.
2. `APIFY_MARKETS_ENABLED="sg,my"` (or full 8) on EC2 `.env.local`.
3. After the first weekly cron run, any zero-result rows tagged with a non-'global' market code will surface in the Data Health page's per-market badge.

No additional EC2 / Apify Console action is required for THIS plan to ship. It is a no-op visual on the free tier (because all current rows are `market_code='global'`).

## Phase 2 Carry-forward

- Phase 2 wave 3 is now functionally complete. The Data Health page advertises per-market failures correctly when they occur; until they do, it looks identical to Phase 1.
- No downstream plans are blocked by this plan.
- The pattern established here (parallel `GROUP BY (..., market_code)` query + filter-out-global + alphabetic-sort breakdown badge) is reusable for any future Phase 2.x diagnostic — e.g., if cost-per-market becomes a triage need, a sibling query on `apify_run_logs.cost_usd` GROUP BY market_code would slot into the same Promise.all.

## Self-Check

- `src/app/(dashboard)/admin/data-health/page.tsx` — FOUND (modified; tsc + lint + build clean)
- commit `71bf67e` — FOUND in git log
- commit `8e5019d` — FOUND in git log
- No file deletions in any task commit (verified via `git diff --diff-filter=D --name-only HEAD~1 HEAD` for each — all empty)

## Self-Check: PASSED

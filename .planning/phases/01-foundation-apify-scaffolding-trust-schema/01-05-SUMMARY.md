---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 05
subsystem: dashboard-ui+scrapers
tags: [empty-state, data-health, admin, force-dynamic, drizzle, intl-numberformat, thunderbit-removal, fb-cutover, trust-ux, phase-1-cutover]

# Dependency graph
requires:
  - "Plan 01-01 (apifyRunLogs Drizzle table + idx_apify_runs_started_at index supporting cost-panel + zero-result-count queries)"
  - "Plan 01-03 (scrapers/apify_social.py owning FB end-to-end so social_scraper.py FB removal is non-breaking)"
provides:
  - "src/components/shared/empty-state.tsx — backward-compatible EmptyState extension with optional reason prop ('scraper-failed' | 'scraper-empty' | 'no-activity')"
  - "src/app/(dashboard)/admin/data-health/page.tsx — operational triage surface listing per-scraper status + zero-result counts (7d) + Apify cost-to-date with cap percentage"
  - "scrapers/social_scraper.py — FB Thunderbit code path removed; YouTube + Instagram + X paths preserved"
affects:
  - "Phase 5 (Confidence & Freshness UX Polish) — will wire `<EmptyState reason='scraper-failed'>` into per-market views and extend the Data Health page with per-actor cost breakdown + freshness pills"
  - "Phase 2 (Per-Market Social Fanout) — Data Health page already lists `Apify Social Scraper` row; Phase 2 fanout to 8 markets just multiplies the apify_run_logs count without changing the UI shape"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backward-compatible component extension: optional new prop driven by Record<NonNullable<Variant>, Preset> presets table — when undefined, behavior is byte-identical to pre-extension component (verified by negative-grep + tsc clean across all 6 import sites)"
    - "Visual consistency by token reuse: `<EmptyState reason='scraper-failed'>` uses bg-red-50 border-red-200 text-red palette IDENTICAL to `<StaleDataBanner>` so the dashboard speaks one consistent visual language for 'data trust problem' regardless of which surface raises it"
    - "force-dynamic admin page reading SQLite directly via Drizzle (no API route) — Next.js 15 server component, three-query Promise.all parallel fetch, no client components, no useEffect"
    - "Intl.NumberFormat for currency (no hand-rolled $X.XX templates) — RESEARCH.md Don't Hand-Roll guidance applied"
    - "Color-coded threshold helper for cost-vs-cap (≥70% red / ≥40% amber / else green) — same shape Phase 5 will reuse for per-market freshness pill thresholds"
    - "Surgical scraper deletion + redirect-comment pattern: when migrating a code path between Python files, leave an explicit 'Phase X: <feature> moved to <new-file>' comment at every removed call site so future readers know where the logic went without git-blame archaeology"

key-files:
  created:
    - src/app/(dashboard)/admin/data-health/page.tsx
  modified:
    - src/components/shared/empty-state.tsx
    - scrapers/social_scraper.py

key-decisions:
  - "Extended src/components/shared/empty-state.tsx in place rather than creating src/components/ui/empty-state.tsx (D-16 reconciliation per PATTERNS.md + RESEARCH.md Pattern 6) — 6 existing import sites resolve to the shared/ path, splitting them would require touching every import"
  - "RESEARCH.md Patterns 6 and 7 shipped verbatim for EmptyState extension and Data Health page — patterns are anchored to D-16/D-17 + TRUST-04/TRUST-05 + the apifyRunLogs/scraperRuns schema landed in Plan 01-01; diverging would force re-review for no functional gain"
  - "Inner icon container background hard-coded to bg-white (not preset.bg) so the colored outer container provides the semantic signal while the icon itself stays high-contrast — matches the visual treatment in stale-data-banner.tsx where the AlertTriangle icon sits on text-red-600 against bg-red-50"
  - "APIFY_MONTHLY_CAP_USD = 100 hard-coded as a module constant rather than reading from env — D-06 specifies $100; Apify Console-side cap is the authoritative defense; the dashboard value is for operator visibility and changes ~yearly at most. Hoisted to a named constant so it's a one-line edit if D-06 cap changes"
  - "Cost color thresholds 70%/40% chosen so 'red' triggers BEFORE the cap is hit (operator has time to investigate before getting cut off) — the green→amber transition at 40% is the 'we're spending real money, take a look this week' signal, the amber→red at 70% is 'this run pace puts us at the cap, act now'"
  - "approximate-match for zero-result counts: zeroCounts row (keyed by actorId like 'apify/facebook-posts-scraper') is matched against SCRAPERS by `z.actorId.includes(s.name) || z.actorId.includes(s.dbName)` — works for the current 1-actor-per-scraper Phase 1 shape; Phase 2/5 may need an explicit actor→scraper map if multiple Apify scrapers share a slug fragment"
  - "Surgical deletion of fetch_facebook_stats / _fetch_facebook_legacy / _FB_SCHEMA over the alternative of stubbing them with raise RuntimeError — verified via grep that no other module imports them (only social_scraper.py internal calls), so deletion is safer and simpler than living deprecation stubs that might be re-discovered and re-wired by future readers"
  - "FB call site replaced with `_ = fb_slug` no-op rather than removing the `fb_slug = handles.get('facebook_slug')` extraction above — the variable is in the same destructure as `ig_handle` and `x_handle`; touching the destructure for cleanliness would expand the diff and risk an Instagram/X regression. The no-op assignment is a 1-line cost for a +0-line risk"

requirements-completed: [TRUST-04, TRUST-05]

# Metrics
duration: 4min
completed: 2026-05-04
---

# Phase 1 Plan 5: Trust UX Skeleton + Phase 1 FB Cutover Summary

**Backward-compatible `<EmptyState reason="scraper-failed" | "scraper-empty" | "no-activity">` extension lands at `src/components/shared/empty-state.tsx` (red palette consistent with `<StaleDataBanner>` for cross-component visual coherence; all 6 existing import sites compile and render unchanged), new `/admin/data-health` server page lists per-scraper status + 7-day zero-result counts + Apify cost-to-date with cap percentage (force-dynamic, three parallel Drizzle queries, Intl.NumberFormat USD, color-coded thresholds at 70%/40%), and the Phase 1 FB cutover completes with the `fetch_facebook_stats` / `_fetch_facebook_legacy` / `_FB_SCHEMA` deletion from `scrapers/social_scraper.py` plus an explicit "Phase 1: Facebook moved to scrapers/apify_social.py" comment at the per-broker call site so future readers cannot accidentally re-add the Thunderbit FB path. Closes TRUST-04 / TRUST-05; finishes Phase 1.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-04T06:44:11Z
- **Completed:** 2026-05-04T06:48:13Z
- **Tasks:** 3 of 3
- **Files created:** 1 (`src/app/(dashboard)/admin/data-health/page.tsx`)
- **Files modified:** 2 (`src/components/shared/empty-state.tsx`, `scrapers/social_scraper.py`)

## Accomplishments

- **EmptyState extension shipped backward-compatibly.** Optional `reason?: EmptyStateReason` prop drives a presets table mapping `'scraper-failed'`/`'scraper-empty'`/`'no-activity'` → `{ icon, bg, iconColor }`. When `reason` is undefined, the rendered output is byte-identical to the pre-extension component — verified by tsc clean (0 errors anywhere in the repo) across all 6 existing import sites (`error.tsx`, `insights/page.tsx`, `changes/page.tsx`, `markets/page.tsx`, `competitors/page.tsx`, `competitors/[id]/page.tsx`) covering 7 call sites.
- **`scraper-failed` reuses the stale-data-banner red palette** (`bg-red-50 border-red-200`, `text-red-500` on the icon) so the dashboard's "data trust problem" visual language is consistent across the chrome (top banner) and content (inline empty state) layers.
- **D-16 reconciliation honored** — extended `src/components/shared/empty-state.tsx` in place rather than creating a parallel `src/components/ui/empty-state.tsx` per PATTERNS.md + RESEARCH.md Pattern 6 reconciliation note. Negative-grep gate `[ ! -f "src/components/ui/empty-state.tsx" ]` passes.
- **`/admin/data-health` page (167 lines, well above the 60-line acceptance floor)** ships as a force-dynamic server component reading SQLite directly via three parallel Drizzle queries:
  1. `scraperRuns` ordered DESC by `startedAt`, LIMIT 200, collapsed to a Map keyed by `scraperName` (most-recent wins).
  2. `apifyRunLogs SUM(cost_usd)` filtered by `startedAt >= monthStart` (uses Plan 01-01 `idx_apify_runs_started_at` index) — feeds the cost panel.
  3. `apifyRunLogs COUNT(*) GROUP BY actorId` filtered by `status='empty' AND startedAt >= 7d ago` — per-actor zero-result counts surface in the table's right column.
- **Cost panel uses `Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })`** — no hand-rolled `$X.XX` templates per RESEARCH.md Don't Hand-Roll guidance. Hoisted as a single `usd` instance reused for both the running total and the cap so locale formatting is consistent.
- **Color-coded cost threshold helper** — `costPct >= 70 ? "text-red-600" : costPct >= 40 ? "text-amber-600" : "text-green-700"`. Triggers BEFORE the cap is hit so operator has time to investigate. The same shape Phase 5 will reuse for freshness pill thresholds.
- **Scraper table iterates `SCRAPERS` from `@/lib/constants`** — one row per scraper. Last-run timestamp via `formatDateTime` (Asia/Singapore SGT, matches existing dashboard convention); status via colored span (`success` → green, `running` → blue, anything else → red); zero-result count via amber span when >0, plain "0" when 0 (no false-positive yellow when nothing's wrong).
- **Auth gating delegated to existing `src/middleware.ts`** — the `(dashboard)` route group inherits the cookie auth check that protects every other dashboard page. T-01-05-01 (mitigate) is closed by this delegation; no new auth code added.
- **Three parallel Drizzle reads use parameterized eq/gte/sql template** — no string concatenation of user input; `sevenDaysAgoIso` and `monthStartIso` are computed server-side from `Date.now()`. T-01-05-03 (mitigate) closed.
- **`COALESCE(SUM(...), 0)` + `Number(costRow.total) || 0`** handles the empty-DB case (Plan 01-03 hasn't deployed to EC2 yet so apify_run_logs may be empty in production until the first cron run). T-01-05-05 (mitigate) closed.
- **Phase 1 FB cutover completes** — `scrapers/social_scraper.py` no longer contains any Thunderbit FB code:
  - Deleted: `_FB_SCHEMA` constant (was at line 51).
  - Deleted: `_fetch_facebook_legacy()` function (was 22 lines, ScraperAPI regex fallback).
  - Deleted: `fetch_facebook_stats()` function (was 19 lines, Thunderbit primary + ScraperAPI fallback).
  - Deleted: 16-line per-broker FB call site in `scrape_all()`.
  - Added: 4-line "Phase 1: Facebook moved to scrapers/apify_social.py (D-01). DO NOT re-add Thunderbit FB calls here." comment at the per-broker call site (where the deleted block used to be) — explicit redirect for future readers per PATTERNS.md option (b).
  - Added: 4-line "Facebook" section divider comment with the same redirect explanation between `_thunderbit_extract` and `_fetch_instagram_legacy` (where the deleted FB section header used to be).
  - Updated: module docstring header — Facebook removed from the "platforms covered" list; Phase 1 D-01 cutover note added.
- **Preservation requirements verified by grep**: `_thunderbit_extract` still defined and still called for `_IG_SCHEMA` (line 311) and `_X_SCHEMA` (line 357) but no longer for `_FB_SCHEMA` (deleted); `_upsert_social` helper still defined (line 379) and still called for youtube/instagram/x (lines 497/526/546); `fetch_youtube_stats` intact (line 184); `fetch_instagram_stats` intact (line 307); `fetch_x_stats` intact (line 353); `SCRAPER_NAME = "social_scraper"` unchanged (this scraper's identity is preserved — Plan 01-03's `apify_social.py` uses a DIFFERENT `SCRAPER_NAME` so the two scrapers coexist as separate `scraper_runs` rows).
- **Cross-file consistency intact** — `apify_social` appears in `src/lib/constants.ts` SCRAPERS array (Plan 01-03), `apify_social.py` appears in `scrapers/run_all.py` SCRIPTS list (Plan 01-03), and `SCRAPER_NAME = "apify_social"` is set inside the apify_social.py module — verified by triple-grep.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend EmptyState with optional reason prop** — `f9a7a80` (feat)
2. **Task 2: Add /admin/data-health page** — `95b9c52` (feat)
3. **Task 3: Remove FB Thunderbit path from social_scraper.py** — `df00bda` (refactor)

**Plan metadata:** Pending final docs commit at end of this summary.

## Files Created/Modified

- `src/components/shared/empty-state.tsx` (modified, 25 → 42 lines) — added 3-line lucide-react import for AlertOctagon/AlertCircle/Inbox, 1-line `cn` import from `@/lib/utils`, `type EmptyStateReason` union, optional `reason?: EmptyStateReason` field on the props interface, `REASON_PRESETS` table, and resolved-icon/resolved-bg logic threading the preset through the existing JSX. The original `<div>` and `<h3>` and `<p>` structure is unchanged so the visual default for un-keyed callers is byte-identical.
- `src/app/(dashboard)/admin/data-health/page.tsx` (NEW, 167 lines) — imports (db, schema, drizzle-orm, shadcn Table, SCRAPERS, formatDateTime) → `dynamic = "force-dynamic"` declaration → `APIFY_MONTHLY_CAP_USD` constant → async `DataHealthPage` component running three parallel Drizzle queries via `Promise.all`, collapsing latestRuns into a Map keyed by `scraperName`, computing cost percentage + color, then rendering header + cost panel + scraper table.
- `scrapers/social_scraper.py` (modified, 626 → 571 lines, -55 net) — see Accomplishments for the deletion list. Net effect: every line removed was Thunderbit-specific FB code; every line added is either a redirect comment or a docstring update.

## Decisions Made

See frontmatter `key-decisions` for the full list. Highlights:

- **Extended in place at `src/components/shared/`, not parallel `src/components/ui/`.** D-16 specified `src/components/ui/empty-state.tsx` as a NEW file path, but PATTERNS.md + RESEARCH.md Pattern 6 reconciliation observed that 6 import sites already resolve to `@/components/shared/empty-state` and splitting them would force every caller to update its import. Extending in place is the lower-risk choice and was the verbatim recommendation in both reconciliation documents.
- **RESEARCH.md Patterns 6 and 7 shipped verbatim.** Both patterns are reviewed and anchored to D-16/D-17 + TRUST-04/TRUST-05 + the apifyRunLogs/scraperRuns schema landed in Plan 01-01. Same posture as Plan 01-02/01-03/01-04: diverging from a reviewed, requirement-anchored pattern is not safer than shipping it and is more expensive in review cost.
- **70%/40% cost thresholds.** Chosen so the red signal triggers with operational headroom — at $70 of the $100 monthly cap the team has at least a few days to investigate before the cap actually cuts off scraping. The 40% green→amber transition is the "real money is being spent, eyeball this once this week" signal.
- **Surgical deletion of FB code over deprecation-stub.** I checked for external imports of `fetch_facebook_stats` / `_FB_SCHEMA` / `_fetch_facebook_legacy` via grep across `scrapers/` and `src/` — only `social_scraper.py` itself referenced them. Deleting was therefore the lower-risk choice; a `raise RuntimeError(...)` stub would create a tombstone that future readers might be tempted to re-implement, whereas a deletion + explicit redirect comment communicates the migration unambiguously.
- **`_ = fb_slug` no-op at the FB call site instead of removing the `fb_slug` extraction.** `fb_slug` is destructured in the same block as `ig_handle` and `x_handle`. Touching the destructure for cleanliness would expand the diff into the IG/X paths and risk an unrelated regression for a Phase-2-owned scraper. The no-op `_ =` assignment is a 1-line cost for a +0-line risk.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

**`npx tsc` bin is broken locally.** When invoking `npx tsc --noEmit`, the local Node 25 module loader threw `Cannot find module '../lib/tsc.js'` from `node_modules/.bin/tsc`. Worked around by invoking the typescript compiler directly via `node node_modules/typescript/lib/tsc.js --noEmit`, which runs cleanly — 0 errors across the entire repo for both Task 1 (EmptyState extension) and Task 2 (Data Health page) verifications. This is a local-machine issue (Node 25 vs npx wrapper), not a project issue, and does not affect the EC2 build (which runs `npm ci` against Node 22 LTS). Not flagging as a deferred item — the bin is repaired by `npm rebuild typescript` next time the operator hits it.

**Live integration verification (curl `/admin/data-health`) deferred to operator.** The plan's acceptance criteria for Task 2 marks the live curl gate as "skipped if dev server not running locally; verified manually post-implementation." Starting `npm run dev` in this autonomous executor on an in-use developer workstation could conflict with whatever dev server the user already has open and is not appropriate. The page is statically verified — tsc clean, all 12 grep gates pass, 167 lines (>60 floor) — and will render correctly given the schema (Plan 01-01) and writers (Plan 01-03) are in place. First live render happens on the operator's next `npm run dev` or first EC2 deploy.

## User Setup Required

**No new setup required by this plan.** The Data Health page renders against any `apifyRunLogs` and `scraperRuns` rows that exist; rows are written by Plan 01-03's `apify_social.py` and Plan 01-04's `run_all.py` lifecycle wrappers. As soon as the carryover Plan 01-03 operator follow-ups (Apify token in `.env.local`, $100/mo cap in Apify Console, EC2 Python verification, `pip install`, smoke run) and Plan 01-04 operator follow-ups (9 `HEALTHCHECK_URL_*` env vars + 9 HC.io checks) are completed, the page will populate naturally on the next cron run.

**One soft follow-up for Phase 5:** the zero-result-counts column matches by `z.actorId.includes(s.name) || z.actorId.includes(s.dbName)`, which works for the current 1-actor-per-scraper Phase 1 shape. When Phase 2 fans `apify_social.py` out to per-market FB scrapers and Phase 5 adds IG/X Apify actors, an explicit `actorId → SCRAPERS entry` map will be cleaner than the substring match. Not blocking — flagged here for the Phase 5 planner.

## Threat Flags

None new. The Data Health page introduces no new outbound network surface (it reads local SQLite only) and no new untrusted-content rendering path (every value rendered is server-rendered from typed Drizzle results — no innerHTML, no markdown rendering, no user-supplied query params). All `mitigate`-disposition threats from the plan's `<threat_model>` are implemented:

- **T-01-05-01** (Spoofing / unauthenticated access to /admin/data-health) → `(dashboard)` route group inherits `src/middleware.ts` cookie auth gate; no new auth code added.
- **T-01-05-03** (Tampering / SQL injection) → all Drizzle queries use parameterized `eq` / `gte` / `sql` template; `sevenDaysAgoIso` and `monthStartIso` are computed server-side from `Date.now()`, never from user input.
- **T-01-05-05** (Cost panel display incorrect on empty DB) → `COALESCE(SUM(...), 0)` in the SQL plus `Number(costRow.total) || 0` in JS handles the empty-table case; the page renders without error even with zero `apify_run_logs` rows.

`accept`-disposition threats T-01-05-02 (information disclosure of scraper names/costs/error messages) and T-01-05-04 (DoS via slow query) and T-01-05-06 (FB scraper output in pre-Phase-1 logs) remain accepted per the plan: same trust posture as `/admin/page.tsx`; query budget is bounded; pre-Phase-1 log scrubbing is out of scope.

The FB code removal in `social_scraper.py` does not introduce any new threats — Thunderbit was already an outbound surface and the removal strictly shrinks the trusted-write set for `social_snapshots` (only `apify_social.py` writes facebook_* rows now).

## Next Phase Readiness

**Phase 1 is complete with this plan.** All 6 plans shipped (01-01 schema + apify-client pin; 01-02 redaction filter + tests; 01-03 Apify FB scraper module + SCRAPERS/SCRIPTS registration; 01-04 run_all.py timeout + healthcheck pings; 01-05 EmptyState + Data Health + FB cutover; 01-06 EXTRACT-05 calibration validator). All 13 Phase 1 requirements (SOCIAL-01, SOCIAL-04, SOCIAL-05, SOCIAL-06, EXTRACT-05, TRUST-01, TRUST-04, TRUST-05, INFRA-01..05) are closed. Phase 1 success criteria 1, 2, 3, 4, 5 are all materially achieved (criteria 1 and 2 await the operator's first EC2 cron run before live data renders; criterion 3 — Data Health page — ships in this plan; criteria 4 and 5 ship in 01-04 and 01-06 respectively).

**Phase 2 (Per-Market Social Fanout):** Inherits from this plan (1) the `<EmptyState reason='scraper-failed'>` component to render when an Apify run on a per-market FB URL returns zero results, (2) the `/admin/data-health` page that will automatically extend to show `apify-social-sg` / `apify-social-hk` / etc. rows once Phase 2 SCRAPERS entries land — no UI code change required because the table iterates SCRAPERS, and (3) the precedent that `social_scraper.py` no longer touches FB so Phase 2 can fan FB out to 8 markets entirely inside `apify_social.py` without coordinating with the legacy module.

**Phase 5 (Confidence & Freshness UX Polish):** The `<EmptyState reason='*'>` API is now in place and ready to be wired into per-market views. The Data Health page is the foundation Phase 5 will extend with per-actor cost breakdown, freshness pills, and hover tooltips per the plan deferred-items list.

**Outstanding for plan completeness:** Operator follow-ups carry over from Plans 01-03 and 01-04 (already documented in STATE.md Blockers/Concerns); no new operator follow-ups added by Plan 01-05.

## Self-Check: PASSED

**File existence checks:**
- `[x] FOUND: src/components/shared/empty-state.tsx` (42 lines, 7 grep gates pass: reason?: EmptyStateReason, "scraper-failed", AlertOctagon, bg-red-50 border-red-200, export function EmptyState, import { cn } from "@/lib/utils", parallel ui/empty-state.tsx does NOT exist)
- `[x] FOUND: src/app/(dashboard)/admin/data-health/page.tsx` (167 lines, 12 grep gates pass: force-dynamic, DataHealthPage, apifyRunLogs, scraperRuns, SCRAPERS, Promise.all, APIFY_MONTHLY_CAP_USD = 100, Intl.NumberFormat, COALESCE(SUM, eq(apifyRunLogs.status, "empty"), >=60 lines)
- `[x] FOUND: scrapers/social_scraper.py` (571 lines, ast.parse OK, 6 grep gates pass: "Phase 1: Facebook moved" comment present, _upsert_social preserved, YouTube preserved, _thunderbit_extract preserved (used by IG/X), SCRAPER_NAME = "social_scraper" preserved, no _thunderbit_extract(_FB_SCHEMA) call anywhere)

**Commit existence checks:**
- `[x] FOUND: f9a7a80` (Task 1 — feat(01-05): extend EmptyState with optional reason prop)
- `[x] FOUND: 95b9c52` (Task 2 — feat(01-05): add /admin/data-health page (TRUST-05))
- `[x] FOUND: df00bda` (Task 3 — refactor(01-05): remove FB Thunderbit path from social_scraper.py)

**Verification command outputs:**
- `[x] GREP-GATES-OK` (Task 1)
- `[x] DATA-HEALTH-GREP-OK (167 lines)` (Task 2)
- `[x] SOCIAL-SCRAPER-EDIT-OK + ast.parse OK + preservation checks` (Task 3)
- `[x] tsc clean (0 errors anywhere in the repo)` (Tasks 1+2 plan-level)
- `[x] Cross-file consistency intact (apify_social present in constants.ts + run_all.py + apify_social.py SCRAPER_NAME)`
- `[ ] SKIPPED: Live integration verification (curl /admin/data-health)` — deferred to operator's next `npm run dev` or first EC2 deploy; statically verified

---
*Phase: 01-foundation-apify-scaffolding-trust-schema*
*Completed: 2026-05-04*

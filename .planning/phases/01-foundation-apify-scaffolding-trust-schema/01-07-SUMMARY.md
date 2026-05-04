---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 07
subsystem: ui
tags: [empty-state, scraper-failed, social-view, change-events, trust-ux, gap-closure, drizzle, nextjs, react]

# Dependency graph
requires:
  - phase: 01-foundation-apify-scaffolding-trust-schema/01-03
    provides: "scrapers/apify_social.py writes change_events row of fieldName='scraper_zero_results' with domain='social_{platform}' on zero-result Apify runs"
  - phase: 01-foundation-apify-scaffolding-trust-schema/01-05
    provides: "<EmptyState reason='scraper-failed'> variant in src/components/shared/empty-state.tsx — bg-red-50 + AlertOctagon"
provides:
  - "Per-platform Digital Presence card now branches 3-way: snapshot → scraper-failed EmptyState → plain N/A"
  - "Live consumer for the dormant <EmptyState reason='scraper-failed'> variant shipped in 01-05"
  - "Narrow Drizzle query (fieldName='scraper_zero_results' + competitorId + 7d window) added to existing parallel fetch in competitor detail page"
  - "Failure-vs-quiet distinction honored: snapshot wins over failure; plain N/A preserved as genuine-no-data"
affects: [02-per-market-social-fanout, future trust-ux phases, future EmptyState consumers, /admin/data-health phase 5+ wiring]

# Tech tracking
tech-stack:
  added: []  # No new dependencies — uses existing drizzle-orm gte() and existing EmptyState component
  patterns:
    - "Narrow time-bounded change_events lookups for trust UX: separate Drizzle query (1 fieldName + 1 competitorId + 7d window) instead of in-memory filtering of the existing LIMIT-50 changes feed (which would silently miss recent rows)"
    - "Snapshot-wins-over-failure-event ordering: when both data and a failure event exist, the data row trumps — failure wiring never overwrites real data"
    - "Build a Set<string> from query results before render rather than calling .find() inside .map() — O(N+M) over O(N*M) and a clear semantic boundary"

key-files:
  created: []
  modified:
    - "src/app/(dashboard)/competitors/[id]/page.tsx"

key-decisions:
  - "Used a SEPARATE Drizzle query for scraper_zero_results events (not in-memory filter of the existing changes query) because the existing query is LIMIT 50 ORDER BY detectedAt and would silently miss a recent failure row if 50 newer events exist"
  - "7-day window for the failure lookup — long enough to catch a missed daily/weekly cron, short enough that a one-off failure from a month ago doesn't permanently flag the card"
  - "3-way render branch ordered (snap | failure | plain N/A) so that a fresh data row always trumps a stale failure event (must-have #4)"
  - "Plain 'N/A — Data unavailable' copy preserved verbatim — failure-vs-quiet distinction honored, not collapsed; we ship a third state, not a replacement for the second"
  - "Built Set<string> outside the render loop so the PLATFORMS.map pass stays O(1) per platform"
  - "EmptyState description text 'Triage on /admin/data-health' chosen to direct operators to the admin page shipped in 01-05 — keeps the same tactile loop the AI Overview tab already uses (operator-facing, no PII)"

patterns-established:
  - "Pattern: trust-UX renders that need 'did the source go silent vs. fail' branch on the existence of a recent change_events row of a known fieldName, NOT on the absence of a snapshot alone — three-state UI not two"
  - "Pattern: domain-prefix slicing — change_events.domain values like 'social_facebook' map to platform names via slice('social_'.length); centralizing this in a Set keeps it simple"
  - "Pattern: parallel-fetch addition — when adding to an existing Promise.all, append to BOTH the destructure tuple and the array (last position) and pick a narrow query so it adds <1ms"

requirements-completed: [TRUST-04, SOCIAL-04]

# Metrics
duration: 2min
completed: 2026-05-04
---

# Phase 01 Plan 07: Wire scraper-failed EmptyState into Digital Presence per-platform card Summary

**3-way branched per-platform social card on the competitor detail page now renders the red AlertOctagon scraper-failed EmptyState when a recent `change_events` row of `scraper_zero_results` exists for that competitor+platform, instead of silently collapsing to plain "N/A — Data unavailable" — closes gap SC2 from 01-VERIFICATION.md.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-04T07:59:30Z
- **Completed:** 2026-05-04T08:01:21Z
- **Tasks:** 1 / 1
- **Files modified:** 1

## Accomplishments

- Added `gte` to the existing `drizzle-orm` import (no new package dependency — `gte` was already exported by the installed Drizzle version)
- Added a narrow Drizzle query inside the existing `Promise.all` block: selects `change_events.domain` and `change_events.detectedAt` filtered by `competitorId=id`, `fieldName='scraper_zero_results'`, and `detectedAt >= 7 days ago` (ISO 8601 string comparison)
- Built `socialScraperFailedPlatforms: Set<string>` once after the data fetch by slicing `domain` strings of the form `social_{platform}` → `{platform}`
- Replaced the existing 2-way `(!snap ? <p>N/A</p> : <div>data</div>)` ternary with a 3-way `(snap ? data : failedSet.has(platform) ? <EmptyState/> : <p>N/A</p>)` branch
- Preserved the plain `"N/A — Data unavailable"` copy and class verbatim — failure-vs-quiet distinction is honored, not collapsed
- Snapshot wins over scraper-failed: when both exist, the snapshot branch is taken first, so the failure wiring cannot overwrite real data (must-have truth #4)
- Reused the existing `EmptyState` import (line 29) — no duplicate import added
- Wires `<EmptyState reason="scraper-failed">` shipped dormant in 01-05 to its first real consumer

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire scraper-failed EmptyState into the per-platform social card** — `1efd975` (feat)

**Plan metadata:** _to be added by metadata commit step below_

## Files Created/Modified

- `src/app/(dashboard)/competitors/[id]/page.tsx` — Added `gte` import; appended new `change_events` query to the existing `Promise.all` and to the destructure tuple; built `socialScraperFailedPlatforms` Set after the social-map block; replaced the 2-way per-platform render with a 3-way branch (snapshot → scraper-failed EmptyState → plain N/A)

## Decisions Made

- **Separate query instead of in-memory filter of `changes`** — the existing `changes` query at lines ~144–149 is `LIMIT 50 ORDER BY detectedAt DESC` and is NOT filtered by `fieldName`. If 50 newer non-failure events exist between now and the most recent failure, the failure row would silently fall off the end and the wiring would miss it. A separate narrow query (1 competitorId + 1 fieldName + 7d window) is correct and adds <1ms to the parallel fetch (the table is small + indexed by competitor).
- **7-day window** — chosen so a missed daily or weekly cron run is still visible on the card, but a stale failure from a month ago does not permanently flag a competitor that has since recovered. Same window shape Phase 5 will reuse for freshness pills.
- **3-way branch ordered (snap → failure → plain)** — snap-first ordering enforces "snapshot wins over scraper-failed" without an explicit precedence flag; the type check is just JavaScript ternary precedence. Plain N/A as the fallthrough preserves the genuine-no-data state untouched.
- **EmptyState copy** — `title="Scraper returned zero results"` + `description="The most recent run for this platform produced no data. Triage on /admin/data-health."` directs operators to the admin page shipped in 01-05 (the same loop the AI Overview tab already uses). Hardcoded operator-facing strings — no PII or secrets, same posture as existing EmptyState calls on this page.

## Deviations from Plan

None - plan executed exactly as written.

The plan provided exact code blocks for all three edits and they shipped verbatim. No bugs found, no missing critical functionality discovered, no architectural changes needed. tsc clean on first run, all 6 grep gates passed on first run, single-file diff scope as expected.

---

**Total deviations:** 0
**Impact on plan:** Plan was small and surgical; the explicit code-block-with-rationale shape made it a clean ship.

## Issues Encountered

None.

**Note on tsc invocation:** The verify block specifies `node node_modules/typescript/lib/tsc.js --noEmit`. The worktree does not have its own `node_modules/`, so the parent repo's typescript binary was used at the absolute path `/Users/.../competitor-analysis-dashboard/node_modules/typescript/lib/tsc.js`. Output was empty (clean compile), satisfying the must-have truth "tsc --noEmit produces zero new errors anywhere in the repo". Not a deviation — same Node + TS stack, just resolved via the parent repo's node_modules per worktree convention.

## Threat Flags

None — the change uses parameterized Drizzle `eq`/`gte` over the existing typed schema; no new untrusted input crosses any boundary; EmptyState renders hardcoded operator-facing strings only. All threat-register entries from the plan's `<threat_model>` are addressed (T-01-07-01 mitigated by Drizzle parameterization; T-01-07-02 and T-01-07-03 accepted as documented).

## User Setup Required

None — no external service configuration required for THIS plan.

**Operator follow-ups for live verification (carry-over from 01-03/01-05/STATE.md, not blocking this plan):**

1. **For real `scraper_zero_results` events to land:** Phase 1 operator follow-ups must be done — Apify token in EC2 `.env.local`, Apify Console monthly $100 cap (D-06), EC2 Python ≥3.10 verification + `pip install -r scrapers/requirements.txt`, one-time smoke run `python3 scrapers/apify_social.py`. Until these land, the wiring is testable only via DB seed (option 2).
2. **For local DB-seed smoke test of THIS wiring (optional, doesn't block deploy):**
   ```bash
   sqlite3 data/competitor-intel.db "INSERT INTO change_events (competitor_id, domain, field_name, old_value, new_value, severity, detected_at, market_code) VALUES ('ic-markets', 'social_facebook', 'scraper_zero_results', NULL, '{\"actor_id\":\"apify/facebook-posts-scraper\",\"actor_version\":\"1.16.0\",\"platform\":\"facebook\"}', 'medium', strftime('%Y-%m-%dT%H:%M:%fZ','now'), 'global');"
   # Visit /competitors/ic-markets, click "Digital Presence" tab — Facebook card should render the red AlertOctagon EmptyState (description: "Triage on /admin/data-health.")
   # Cleanup:
   sqlite3 data/competitor-intel.db "DELETE FROM change_events WHERE field_name='scraper_zero_results' AND competitor_id='ic-markets' AND detected_at >= datetime('now', '-1 hour');"
   ```

## Next Phase Readiness

- **Phase 2 (Per-Market Social Fanout) readiness:** This plan only touches the global per-platform card — `socialScraperFailedPlatforms` is built off `domain.startsWith("social_")` so when Phase 2 starts writing per-market `change_events` rows for Apify failures, the wiring picks them up automatically (the failure Set will include those platforms regardless of `marketCode`). If Phase 2 wants per-market failure granularity (e.g., FB-SG failed but FB-MY didn't), the Set will need to be widened to a `Map<platform, Set<marketCode>>` or a `Set<"platform:market">`; flagging here for Phase 2 planning.
- **Gap SC2 from `01-VERIFICATION.md` is closed at the code wiring level.** A future zero-result Apify run on EC2 will surface as the red EmptyState on the Digital Presence tab without any further code change — the data → UI path is now end-to-end.
- **No new blockers introduced.** Operator follow-ups carried over from 01-03/01-05/STATE.md remain unchanged.

## Self-Check

- File `src/app/(dashboard)/competitors/[id]/page.tsx` exists: FOUND
- Commit `1efd975` exists in git log: FOUND
- All 6 grep gates passed: PASSED (1 / 1 / 3 / 1 / found / 1)
- tsc --noEmit clean: PASSED (no output)
- git diff --stat: 1 file changed (within scope)

## Self-Check: PASSED

---
*Phase: 01-foundation-apify-scaffolding-trust-schema*
*Plan: 07*
*Completed: 2026-05-04*

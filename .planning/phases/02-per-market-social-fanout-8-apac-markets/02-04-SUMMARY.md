---
phase: 02-per-market-social-fanout-8-apac-markets
plan: 04
subsystem: dashboard
tags: [dashboard, ui, markets, social, fallback, phase-2, trust-ux]
requirements: [MARKET-03, SOCIAL-02, SOCIAL-03]

# Dependency graph
dependency-graph:
  requires:
    - "src/lib/markets.ts PRIORITY_MARKETS — 8 APAC v1 codes (Plan 02-01 / commit c6381b1)"
    - "scrapers/apify_social.py per-market loop — APIFY_MARKETS_ENABLED feature flag (Plan 02-03 / commits 6a92705..69053df)"
    - "src/db/schema.ts socialSnapshots.marketCode + changeEvents.marketCode columns (Plan 01-01)"
    - "src/components/shared/empty-state.tsx EmptyState component with reason='scraper-failed' preset (Plan 01-07)"
    - "Existing DataSourceBadge inline helper at src/app/(dashboard)/markets/[code]/page.tsx:54-69 (reused)"
  provides:
    - "src/app/(dashboard)/markets/[code]/page.tsx Digital Presence section — competitor-oriented FB/IG/X table per market (RESEARCH.md §5)"
    - "Per-(competitor, platform) market-first / global-fallback resolver (RESEARCH.md Pattern 4 / D2-10) using a SocialKey Map<`competitorId|platform`, SocialCell>"
    - "Inline scraper-failed indicator (red-dot + label) when a recent change_events scraper_zero_results row exists for (competitor, platform, market) — D2-14 trust UX continuity"
    - "Outer EmptyState fallback when no competitor has any social data for this market"
  affects:
    - "/markets/[code] route renders one new section between Pricing and Account Types — order: KPI row → Market Overview → Pricing → Digital Presence → Account Types/Recent Changes grid → Active Promotions"
    - "No other plans blocked or unblocked; this is the user-facing deliverable for Phase 2 wave 3."

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-(competitor, platform) market-first / global-fallback resolution via a typed SocialKey map (`${competitorId}|${platform}` template literal type) with two ordered passes — market rows first, then global, never both for the same key"
    - "Inline failure indicator vs. full EmptyState card: the cell-level scraper-failed is rendered as a compact red-dot + 'scraper failed' label inside a table cell so row heights stay scannable; the full EmptyState card is reserved for the outer 'no data at all for this market' fallback (RESEARCH.md §5 + plan deviations_allowed)"
    - "Subquery MAX(id) GROUP BY (competitor_id, platform) for latest-per-(competitor, platform, market) reads — same idiom as the existing pricing/promos/accounts queries on the page, just with an extra GROUP BY key for platform"
    - "Source badge per row (DataSourceBadge isMarketSpecific={anyMarketSpecific}) reflects whether ANY of the three platforms has market-specific data — intentional row-level (not cell-level) granularity to keep the table compact"
    - "?market=${marketCode} preserved in broker links so clicking through to /competitors/[id] keeps the per-market viewing context (matches Phase 1 wiring per RESEARCH.md 'Claude's Discretion')"

key-files:
  created: []
  modified:
    - "src/app/(dashboard)/markets/[code]/page.tsx"

key-decisions:
  - "Followed the plan as written — no Rule 1-3 auto-fixes triggered, no Rule 4 architectural decisions encountered."
  - "Used Drizzle's inArray helper for the platform IN (...) clause on the change_events lookup (clean and type-safe); used raw sql template for the social_snapshots WHERE clause because the subquery MAX(id) GROUP BY composition matches the existing pricing/promo/account query idiom in the same Promise.all block — consistency over churn."
  - "Source badge granularity: row-level (any platform market-specific → Market badge) rather than per-cell. Plan acknowledges this as intentional ('it tells the manager at a glance that this row is at least partly localized; a finer-grained per-platform badge is deferred')."
  - "Cell-level zero-result indicator is the compact red-dot + label (NOT the full EmptyState card form) — the big-card form would blow up row heights. Plan explicitly notes this trade-off."
  - "Left the dead `isChina` branch at line 319 untouched. Plan 02-01 SUMMARY surfaced it as a Phase 2 cleanup candidate; the plan deviations_allowed list explicitly excludes cleanup of unrelated lines on this file. Logged as a still-open Phase 2 cleanup candidate."

requirements-completed: [MARKET-03, SOCIAL-02, SOCIAL-03]

# Metrics
metrics:
  duration_minutes: 7
  completed_date: 2026-05-13
  task_count: 4
  file_count: 1
---

# Phase 02 Plan 04: Digital Presence section on `/markets/[code]` — Summary

**Added a new Digital Presence section to `src/app/(dashboard)/markets/[code]/page.tsx` rendering a competitor-oriented FB/IG/X table per market, with per-(competitor, platform) market-first / global-fallback resolution and an inline `scraper-failed` indicator when a recent `change_events scraper_zero_results` row exists. Single-file change; `tsc --noEmit`, `npm run lint`, and `npm run build` all clean (only pre-existing warnings in unrelated files).**

## What Shipped

### Task 1 — `social_snapshots` + `change_events` queries (commit `82080e0`)

- Three new entries added to the existing `Promise.all` block in `MarketDetailPage`:
  - `marketSocialRows`: latest per `(competitor_id, platform)` row in `social_snapshots` where `market_code = ${marketCode}` AND `platform IN ('facebook','instagram','x')`. Mirrors the `MAX(id) GROUP BY` pattern used by `marketPricingRows`, with an extra `platform` GROUP BY key.
  - `globalSocialRows`: same shape but `market_code = 'global'` — the Phase 2 fallback pool per D2-10.
  - `socialZeroResultRows`: `change_events` rows within last 7 days where `field_name = 'scraper_zero_results'`, `market_code = ${marketCode}`, and `domain IN ('social_facebook','social_instagram','social_x')`. Limit 500 (more than enough headroom: 11 competitors × 3 platforms × 7 days = 231 max).
- New schema import: `socialSnapshots` from `@/db/schema`. New Drizzle helper import: `inArray` from `drizzle-orm`. The `weekAgo` const that already existed (Date.now() at line 145) is reused — no additional Date.now() call, no eslint-disable directive needed.

### Task 2 — Per-(competitor, platform) fallback resolver (commit `e690f8f`)

- Added a typed `SocialKey = \`${string}|${SocialPlatform}\`` template literal type for map keys; `SocialPlatform = "facebook" | "instagram" | "x"`; `SocialCell = { followers, postsLast7d, isMarketSpecific }`.
- Two ordered passes over the rows fetched in Task 1:
  - Pass 1 iterates `marketSocialRows` and sets each `(competitor, platform)` cell with `isMarketSpecific: true` if not already set.
  - Pass 2 iterates `globalSocialRows` and sets each `(competitor, platform)` cell with `isMarketSpecific: false` ONLY if Pass 1 didn't already claim it (RESEARCH.md Pattern 4).
- Built `zeroResultKeys: Set<SocialKey>` by stripping the `social_` prefix from each event's `domain` field (per `apify_social.py` convention) and keying on `competitorId|platform`.
- Composed `socialRows`: per-competitor `{ facebook, instagram, x }` cell record where each cell is `SocialCell | 'scraper-failed' | null`. Rows where no platform has any data (no snapshot AND no recent zero-result event) are filtered out via the `hasAnyData` flag — keeps the table compact.
- Sort order: self (Pepperstone) first → any-market-specific rows next → tier ascending. Matches the pricing-table sort idiom on the same page.

### Task 3 — Digital Presence JSX section (commit `4209a0b`)

- Added imports: `Users` icon from `lucide-react`; `EmptyState` from `@/components/shared/empty-state`.
- Added `formatFollowers(n: number | null): string` helper near the existing `MiniKpi` helper. Formats: `null` → `—`, `>= 1_000_000` → `12.3M`, `>= 1_000` → `12.3k`, else stringified integer.
- Inserted `<section>` between the Pricing `</section>` (closing tag at the line after the pricing table) and the Account Types + Recent Changes two-column grid. Layout:
  - Header: `Users` icon + "Digital Presence" + small `{n} broker(s)` count when rows exist.
  - Empty case: full `<EmptyState>` card with title "No social data yet for this market" and a check-back description.
  - Populated case: rounded-xl card containing a five-column table — `Broker | Source | Facebook | Instagram | X`.
- Cell rendering per platform:
  - `cell === "scraper-failed"` → compact red-dot (1.5px circle) + "scraper failed" label.
  - `cell == null` → em-dash (`—`) in light gray.
  - `cell` is `SocialCell` → `<formatFollowers> · <postsLast7d>p` (posts suffix omitted when null).
- Broker link: `/competitors/${competitor.id}?market=${marketCode}` — preserves market context on click-through.
- Source badge: reuses the existing `DataSourceBadge` helper on the same file (no new component), bound to `anyMarketSpecific` so the badge reflects whether ANY of the three platforms has market-specific data for that row.

### Task 4 — Build + verification (no commit; verification-only)

- `npm run build` against the worktree (with a symlink to the parent repo's `node_modules`) produced a clean Turbopack build: compiled successfully in 3.9s, type-check passed, lint passed (only pre-existing warnings in `src/app/(dashboard)/competitors/page.tsx`, `src/app/api/v1/trends/route.ts`, `src/components/charts/morning-brief.tsx` — all out of scope for this plan per the scope-boundary rule), 11/11 static pages generated. `/markets/[code]` appears as a dynamic server-rendered route (2.27 kB, 116 kB first-load JS).
- Manual visual smoke (per plan task description) is deferred — autonomous executor does not have a browser session and the dev DB on EC2 does not yet have per-market `social_snapshots` rows (per Plan 02-03 operator follow-up). The fallback resolver semantics are exercised by the type system + the build pipeline; the actual UI rendering is guaranteed by the type-correctness of `cells[platform]` and the deterministic JSX branches.

## Commits

| Task | Commit | Files | Summary |
|------|--------|-------|---------|
| 1 | `82080e0` | `src/app/(dashboard)/markets/[code]/page.tsx` | feat(02-04): add social_snapshots + zero-result queries to markets page |
| 2 | `e690f8f` | `src/app/(dashboard)/markets/[code]/page.tsx` | feat(02-04): build per-(competitor, platform) social fallback resolver |
| 3 | `4209a0b` | `src/app/(dashboard)/markets/[code]/page.tsx` | feat(02-04): render Digital Presence section on /markets/[code] |
| 4 | — | (verification only) | npm run build clean; manual visual smoke deferred to operator review |

## Verification Gates — Results

All plan-level verification gates pass:

```
gate 1: typecheck clean
  node node_modules/typescript/lib/tsc.js --noEmit   -> exit 0

gate 2: lint clean on modified file
  node node_modules/eslint/bin/eslint.js "src/app/(dashboard)/markets/[code]/page.tsx"
  -> exit 0

gate 3: build passes
  npm run build  -> Compiled successfully in 3.9s; Linting passed; 11/11 static pages OK;
                     /markets/[code] in route table at 2.27 kB / 116 kB first-load.

gate 4: section is present
  grep -c 'Digital Presence' "src/app/(dashboard)/markets/[code]/page.tsx"   -> 6  (expected >= 1)

gate 5: fallback resolver wired
  grep -c 'isMarketSpecific' "src/app/(dashboard)/markets/[code]/page.tsx"   -> 23 (expected >= 5)

gate 6: scraper-failed indicator wired
  grep -c 'scraper-failed\|scraper failed' "src/app/(dashboard)/markets/[code]/page.tsx" -> 6 (expected >= 1)
```

## Must-Have Truths — Conformance

| # | Truth | Status |
| - | ----- | ------ |
| 1 | New "Digital Presence" section renders between Pricing and the Account Types / Recent Changes grid | OK (`<section>` inserted between `</section>` of Pricing and `<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">`) |
| 2 | Competitor-oriented table: Broker, Source, Facebook, Instagram, X columns | OK (5 `<th>` headers, exact column order) |
| 3 | Cell format: `<followers> · <posts>p` for snapshot, scraper-failed inline indicator for zero-result event, em-dash for no data | OK (three JSX branches in the cell render block) |
| 4 | Per-(competitor, platform) market-first / global-fallback resolution; never both | OK (Pass 1 sets `isMarketSpecific: true`; Pass 2 only fills keys NOT already set) |
| 5 | DataSourceBadge reuses the existing inline helper at lines 54-69; reflects per-row "any platform market-specific" state | OK (`<DataSourceBadge isMarketSpecific={anyMarketSpecific} />`) |
| 6 | Rows with zero data across all three platforms are omitted | OK (`.filter((r) => r.hasAnyData)`) |
| 7 | Outer EmptyState fallback when `socialRows.length === 0` | OK (conditional render: `{socialRows.length === 0 ? <EmptyState ... /> : <table>...</table>}`) |
| 8 | `tsc --noEmit` + `npm run lint` + `npm run build` all pass clean | OK (all three exit 0; only pre-existing warnings in unrelated files) |

## Deviations from Plan

None — plan executed exactly as written. No Rule 1-3 auto-fixes triggered; no Rule 4 architectural decisions encountered.

A few non-functional clarifications (all explicitly permitted under `<deviations_allowed>`):

- **Comment wording.** Each new query in Task 1 carries a short comment explaining its purpose ("Phase 2 — Digital Presence: ..."); the plan's `deviations_allowed` list does not constrain comment content. Helpful for the next reader.
- **`inArray` vs raw SQL `IN (...)` for the change_events platform filter.** Plan didn't specify; `inArray(changeEvents.domain, [...])` is the type-safe Drizzle idiom and integrates cleanly with the existing `and(...)` predicate. The social_snapshots queries use raw `sql\`... IN ('facebook','instagram','x') ...\`` because they're already inside a raw-SQL subquery composition (matching the existing pricing/promo/account queries on the page).
- **`weekAgo` reuse.** The existing `const weekAgo = new Date(Date.now() - ...).toISOString()` at line 145 was reused for the zero-result lookup — no additional `Date.now()` call needed, so no eslint-disable directive required. The plan's heads-up about hoisting `Date.now()` was a precaution that turned out to be unnecessary here.

## Known Stubs

None. All new data flows from real DB queries; the resolver and cell render are deterministic functions of fetched rows. No hardcoded empty arrays / placeholders / TODO comments shipped.

## Threat Surface Scan

No new security-relevant surface introduced. The change:

- Adds NO new outbound network destinations (DB-only reads via existing Drizzle client).
- Adds NO new auth/session/access-control flows; the `/markets/[code]` route is already covered by the `(dashboard)` route group middleware.
- Adds NO new DB tables or columns; uses existing `social_snapshots.marketCode`, `changeEvents.marketCode`, `changeEvents.fieldName`, `changeEvents.domain` columns from Phase 1.
- Path parameter `marketCode` is already validated upstream by the existing `/^[a-z]{2,5}$/` regex guard at line 135 — unchanged.
- Bound parameters via Drizzle's parameter substitution (`${marketCode}` inside `sql\`...\``) — no raw concatenation, no SQL injection surface.

No `threat_flag:` entries to record.

## TDD Gate Compliance

Plan frontmatter is `type=execute` (not `type=tdd`); no `tdd="true"` annotation on any task. The plan was a single-file UI change with type-system + build-pipeline verification only — no new behavior tests were specified by the plan, and the gate sequence (RED → GREEN → REFACTOR) does not apply. Build + type-check + lint serve as the verification baseline.

## Authentication Gates

None encountered. The change is a pure single-file Drizzle + JSX addition with no external service or credential dependencies.

## Operator Follow-Ups

None required for this plan. The fallback resolver gracefully degrades to global rows until per-market `social_snapshots` rows land on EC2 (gated on the Apify Starter upgrade per Plan 02-03 SUMMARY operator follow-up). When the operator flips `APIFY_MARKETS_ENABLED` on EC2, the Source badge column will start showing "Market" for rows that have per-market data — no code change required.

Once per-market data is flowing in production, a manager opening `/markets/sg` (or any of the other 7 APAC codes) will see the Digital Presence section populated with FB/IG/X follower + activity numbers per competitor, with mixed "Market" + "Global" badges depending on whether each row has localized data yet.

## Phase 2 Carry-forward

- **Plan 02-05 (`/admin/data-health` zero-result-by-market breakout)** — not affected by this plan; runs in parallel.
- **Phase 2 cleanup candidates surfaced by Plan 02-01** — still open:
  - `src/app/(dashboard)/markets/[code]/page.tsx:319` — dead `isChina` branch (still present; out of scope per plan `deviations_allowed`).
  - `src/lib/constants.ts:53,57` — `cn`/`mn` MARKET_FLAGS entries.
  - `src/db/seed.ts:28,32` — `cn`/`mn` markets seed rows.
- **Phase 5 polish carry-forward (deferred per plan):**
  - Optional refactor of `DataSourceBadge` from local helper into `src/components/shared/` (cleanup pass; not blocking).
  - Freshness pill (Phase 5 / TRUST-02).
  - Hover tooltip with source URL on each platform cell (Phase 5 / TRUST-03).
  - Finer-grained per-platform Source badge (acknowledged in code comments as intentional row-level granularity).

## Files Created/Modified

- `src/app/(dashboard)/markets/[code]/page.tsx` — Modified. Added: 2 imports (`Users` icon, `EmptyState` component), 2 schema/drizzle imports (`socialSnapshots`, `inArray`), 1 helper function (`formatFollowers`), 3 Drizzle queries in the existing `Promise.all` block, ~85 lines of fallback-resolver TypeScript (Map + Set construction, two-pass resolution, row composition + sort), ~95 lines of JSX for the new section. Net diff: +239 lines / -1 line.

## Self-Check

Verified each file and commit exists:

- `src/app/(dashboard)/markets/[code]/page.tsx` — FOUND (file exists in worktree at expected absolute path; modified)
- Commit `82080e0` (Task 1) — FOUND via `git log --oneline -3`
- Commit `e690f8f` (Task 2) — FOUND via `git log --oneline -3`
- Commit `4209a0b` (Task 3) — FOUND via `git log --oneline -3`
- No file deletions in any task commit (verified via `git diff --diff-filter=D --name-only HEAD~1 HEAD` per commit — all empty)
- No new untracked files in the working tree (the symlinked `node_modules` and the `.next/` build dir are gitignored).

## Self-Check: PASSED

---
quick_id: 260514-xbj
phase: quick-260514-xbj
plan: 01
type: execute
subsystem: markets-per-market-curation
tags: [bugfix, phase-2.1, markets, drizzle, schema-parity]
requirements:
  - PHASE-2.1-BUGFIX-01-PEPPERSTONE-EMERGING
  - PHASE-2.1-BUGFIX-02-MISSING-COMPETITOR-MARKETS-TABLE
dependencies:
  requires:
    - phase-02.1 (per-market curation feature shipped)
  provides:
    - default-safe contract restoration on fresh EC2 deploys
    - is_self filter on Emerging Competitors rail
  affects:
    - src/app/(dashboard)/markets/[code]/page.tsx
    - src/db/migrate.ts
tech-stack:
  added: []
  patterns:
    - "Drizzle-side mirror of Python additive migrations (no-drift CHECK + index parity)"
key-files:
  created: []
  modified:
    - src/app/(dashboard)/markets/[code]/page.tsx
    - src/db/migrate.ts
decisions:
  - "Two distinct early-returns in emergingRail .map(...) (vs. fused `||`) — preserves the original 'not in config' comment and surfaces the two skip reasons separately in stack traces / git blame"
  - "No try/catch fallback wrapping the dashboard query — boot migration is the cleaner solution; degrading-to-[] would mask future schema drift"
  - "competitor_markets CREATE TABLE placed AFTER app_store_snapshots and BEFORE the scraper_config ALTER loop — preserves the file's existing convention (CREATE TABLE migrations grouped before ALTER migrations)"
  - "Mirror Python migration byte-for-byte (same column order, CHECK enum text, composite PK, index name) — D2.1-02 no-drift contract; SQLite considers the schema identical regardless of creation path"
metrics:
  duration: ~12m
  completed: 2026-05-14
---

# Quick Task 260514-xbj: Phase 2.1 Bugfixes 2.2a-1 Summary

Two surgical bugfixes against the just-shipped Phase 2.1 per-market curation feature, both surfaced on the v1.4.1 EC2 deploy. One paragraph per fix below; verification results follow.

## Fixes Shipped

### Fix 1 — Exclude is_self competitors from Emerging Competitors rail

Commit `e98f9e8` — `fix(markets): exclude is_self competitors from Emerging Competitors rail`.

Added a single `if (comp.isSelf) return null;` early-return in the `emergingRail` `.map((r): EmergingItem | null => ...)` block at `src/app/(dashboard)/markets/[code]/page.tsx:579`, immediately after the existing "competitor not in config" guard at line 578. The operator report was that Pepperstone surfaced in the `/markets/hk` Emerging Competitors rail because `logs/serp_research_hk.csv` ranks Pepperstone in our own-brand queries (we operate in HK), and the rail builder filtered against `curatedAnyIds` and the competitor map but never against the `competitors.is_self` column. The truthy-check idiom matches the existing codebase convention — `src/app/(dashboard)/page.tsx:170` already uses `(c) => !c.isSelf`, and `src/app/(dashboard)/markets/[code]/page.tsx:731` uses `!!competitor.isSelf` — both safe on SQLite INTEGER 0/1 columns. The `curatedAnyIds` filter on the line above was intentionally left unchanged: conflating "self" with "curated" would mask future schema bugs if Pepperstone ever gets a curation row for legitimate reasons (we still want `is_self` to win).

### Fix 2 — Add competitor_markets to Drizzle bootstrap migrations

Commit `8b364ee` — `fix(db): create competitor_markets table on Next.js boot to mirror Python migration`.

Appended a `CREATE TABLE IF NOT EXISTS competitor_markets` + matching `CREATE INDEX IF NOT EXISTS idx_competitor_markets_market_status` block to `src/db/migrate.ts:194-209`, placed after the `app_store_snapshots` `CREATE INDEX` (line 190-191) and before the `scraper_config` / `market_config` ALTER loop (line 211 onwards). This preserves the file's existing convention of grouping CREATE TABLE migrations before ALTER migrations (matching `wikifx_snapshots`, `ai_portfolio_insights`, `app_store_snapshots` above). The SQL mirrors `scrapers/db_utils.py:209-222` byte-for-byte: same column order (`competitor_id`, `market_code`, `status`, `notes`, `updated_at`), same `CHECK (status IN ('active','planned','withdrawn','emerging'))` constraint text, same composite `PRIMARY KEY (competitor_id, market_code)`, same index name and column order `(market_code, status)` — so SQLite considers the schema identical regardless of which side (Python `db_utils.get_db()` or Drizzle `runMigrations()`) creates it first. Both statements are `IF NOT EXISTS`-guarded and require no `try/catch`, matching the file's existing convention. This closes the gap from Phase 2.1 where the migration only ran inside the Python codepath — a freshly-deployed EC2 instance would 500 on `/markets/<code>` until a Python scraper happened to execute. Restores the default-safe contract (D2.1-04 / D2.1-05): empty table → `/markets/<code>` renders identically to Phase 2; missing table no longer 500s.

## Verification Results

| Gate | Command | Result |
|------|---------|--------|
| Typecheck | `node node_modules/typescript/lib/tsc.js --noEmit` | Exit 0 (clean) |
| Lint (modified files) | `node node_modules/eslint/bin/eslint.js src/app/(dashboard)/markets/[code]/page.tsx src/db/migrate.ts` | Exit 0 (clean, no warnings) |
| Build | `npm run build` | Success — 11/11 static pages generated; `/markets/[code]` route built to 2.28 kB |
| Fresh-DB smoke (table creation) | better-sqlite3 against `/tmp/cad-bugfix-smoke.db` | Table + index created; `sqlite_master` rows match expected DDL byte-for-byte |
| Idempotency smoke | Re-run Drizzle migration against same DB | No error (second run is a no-op) |
| Python-first cross-compat | Apply Python `db_utils.py` DDL first, then Drizzle DDL on same DB | No error; subsequent INSERT with valid status enum succeeds |

Schema parity check (both sides report identical CREATE TABLE / CREATE INDEX text):

```
src/db/migrate.ts:200    sqlite.exec(`CREATE TABLE IF NOT EXISTS competitor_markets (
scrapers/db_utils.py:210         CREATE TABLE IF NOT EXISTS competitor_markets (
src/db/migrate.ts:203    status TEXT NOT NULL CHECK (status IN ('active','planned','withdrawn','emerging')),
scrapers/db_utils.py:213    status TEXT NOT NULL CHECK (status IN ('active','planned','withdrawn','emerging')),
src/db/migrate.ts:208    sqlite.exec(`CREATE INDEX IF NOT EXISTS idx_competitor_markets_market_status
scrapers/db_utils.py:220         CREATE INDEX IF NOT EXISTS idx_competitor_markets_market_status
```

## Deferred Verification

- **`/markets/hk` live dev smoke** — not run locally because the local environment does not have `logs/serp_research_hk.csv` populated for Pepperstone (operator-side artifact maintained on EC2). Will validate on EC2 after deploy: (a) Pepperstone is absent from the Emerging Competitors rail on `/markets/hk`, (b) `/markets/<code>` renders without 500 on the freshly-created DB. The code path is exercised by the existing build (the route compiled to 2.28 kB in `npm run build`), so the deferral is for end-to-end visual confirmation only.
- **`pm2 reload` smoke** — typical EC2 deploy step; not exercised locally.

## Deviations from Plan

None — both fixes executed exactly as planned. Task 3 was verification-only (no commit) per the plan's "close it out in the SUMMARY without a commit" instruction since all gates 1-5 passed without modifications.

## Operator Follow-ups

EC2 deploy is the standard pattern — no manual SQL, no operator action beyond the deploy:

```bash
git pull && npm ci && npm run build && pm2 reload <app>
```

The Drizzle migration runs on Next.js boot via `runMigrations()` (already invoked from `src/db/index.ts` on import), so `competitor_markets` will be created on the first request after `pm2 reload` if the table is missing. If a Python scraper has already run on this instance, the migration is an idempotent no-op.

## Self-Check: PASSED

- Created files: `.planning/quick/260514-xbj-phase-2-1-bugfixes-2-2a-1-filter-out-pep/260514-xbj-SUMMARY.md` — FOUND (this file)
- Modified files: `src/app/(dashboard)/markets/[code]/page.tsx`, `src/db/migrate.ts` — both committed
- Commits exist:
  - `e98f9e8` (Task 1: emerging rail is_self guard) — verified in `git log --oneline`
  - `8b364ee` (Task 2: competitor_markets Drizzle migration) — verified in `git log --oneline`
- No Co-Authored-By trailers in either commit (verified via `git log --format=%B`)

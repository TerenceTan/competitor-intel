---
phase: quick-260514-xbj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/(dashboard)/markets/[code]/page.tsx
  - src/db/migrate.ts
autonomous: true
requirements:
  - PHASE-2.1-BUGFIX-01-PEPPERSTONE-EMERGING
  - PHASE-2.1-BUGFIX-02-MISSING-COMPETITOR-MARKETS-TABLE

must_haves:
  truths:
    - "Pepperstone never appears in the Emerging Competitors rail on any /markets/<code> page, including HK where Pepperstone shows in the SERP CSV"
    - "/markets/<code> renders successfully on a freshly-deployed EC2 instance where no Python scraper has run yet (competitor_markets table is auto-created by the Next.js process at boot)"
    - "The default-safe contract (D2.1-04 / D2.1-05) is preserved: an empty competitor_markets table behaves like Phase 2 (show all competitors); a missing table no longer 500s"
    - "Existing Phase 2.1 behavior is unchanged when the table is present and populated (curation filter and Emerging rail continue to work)"
  artifacts:
    - path: "src/app/(dashboard)/markets/[code]/page.tsx"
      provides: "Emerging rail filter that excludes is_self competitors"
      contains: "comp.isSelf"
    - path: "src/db/migrate.ts"
      provides: "CREATE TABLE IF NOT EXISTS competitor_markets idempotent migration mirroring scrapers/db_utils.py"
      contains: "competitor_markets"
  key_links:
    - from: "src/app/(dashboard)/markets/[code]/page.tsx (emergingRail builder)"
      to: "competitors.isSelf flag"
      via: "competitorById.get(r.competitorId).isSelf truthy check"
      pattern: "comp\\.isSelf"
    - from: "src/db/index.ts (runMigrations() invocation on import)"
      to: "competitor_markets table existence"
      via: "src/db/migrate.ts sqlite.exec CREATE TABLE IF NOT EXISTS"
      pattern: "CREATE TABLE IF NOT EXISTS competitor_markets"
---

<objective>
Two surgical bugfixes against Phase 2.1's just-shipped per-market curation feature, both surfaced on the v1.4.1 EC2 deploy:

1. The Emerging Competitors rail on /markets/<code> shows Pepperstone in HK (and any other market where we rank in the SERP CSV) because the rail builder filters against curated rows and the competitor map but never against the `is_self` flag.

2. /markets/<code> 500s on any environment where `competitor_markets` doesn't exist yet, because Phase 2.1's migration block lives in `scrapers/db_utils.py get_db()` (Python-only) and never runs on the Next.js side. The default-safe contract (D2.1-04 / D2.1-05) was meant to mean "empty table → Phase 2 behavior" but it currently means "missing table → 500".

Purpose: Restore the default-safe contract on freshly-deployed instances and ensure Pepperstone never appears as its own emerging competitor.

Output: One commit per fix (and a final commit for combined verification if helpful), no schema changes, no new dependencies, no observable behavior change when the table is already present and populated.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/02.1-per-market-competitor-curation-operator-driven-show-hide/02.1-CONTEXT.md

# Existing implementations to mirror / extend
@src/app/(dashboard)/markets/[code]/page.tsx
@src/db/migrate.ts
@src/db/schema.ts
@scrapers/db_utils.py

<interfaces>
<!-- Key signatures the executor needs. No codebase exploration required. -->

From src/db/schema.ts (competitors table — note the isSelf flag):
```typescript
export const competitors = sqliteTable("competitors", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  tier: integer("tier").notNull(),
  website: text("website").notNull(),
  isSelf: integer("is_self").notNull().default(0),
  // ...other columns
});
```

From src/db/schema.ts (competitorMarkets table — what Drizzle expects):
```typescript
export const competitorMarkets = sqliteTable(
  "competitor_markets",
  {
    competitorId: text("competitor_id").notNull().references(() => competitors.id),
    marketCode: text("market_code").notNull(),
    status: text("status").notNull(), // 'active' | 'planned' | 'withdrawn' | 'emerging'
    notes: text("notes"),
    updatedAt: text("updated_at").notNull(),
  },
  (t) => ({ pk: primaryKey({ columns: [t.competitorId, t.marketCode] }) }),
);
```

Current emergingRail builder (src/app/(dashboard)/markets/[code]/page.tsx ~lines 566–587):
```typescript
const serpRows = await readEmergingSerpRows(marketCode);
const curatedAnyIds = new Set(curatedMarketRows.map((r) => r.competitorId));
const competitorById = new Map(allCompetitors.map((c) => [c.id, c]));
type EmergingItem = {
  competitor: (typeof allCompetitors)[number];
  queriesAppeared: number;
  bestRank: number;
};
const emergingRail: EmergingItem[] = serpRows
  .filter((r) => !curatedAnyIds.has(r.competitorId))
  .map((r): EmergingItem | null => {
    const comp = competitorById.get(r.competitorId);
    if (!comp) return null; // SERP found a competitor not yet in config — skip
    return { competitor: comp, queriesAppeared: r.queriesAppeared, bestRank: r.bestRank };
  })
  .filter((r): r is EmergingItem => r !== null)
  .sort((a, b) => a.bestRank - b.bestRank);
```

Python-side migration to MIRROR EXACTLY (scrapers/db_utils.py ~lines 209–222):
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS competitor_markets (
        competitor_id TEXT NOT NULL REFERENCES competitors(id),
        market_code TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('active','planned','withdrawn','emerging')),
        notes TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (competitor_id, market_code)
    )
""")
conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_competitor_markets_market_status
    ON competitor_markets (market_code, status)
""")
```

Existing additive-migration convention in src/db/migrate.ts (the file already runs sqlite.exec for CREATE TABLE IF NOT EXISTS for ai_portfolio_insights, wikifx_snapshots, app_store_snapshots — mirror that style; no try/catch needed because CREATE TABLE IF NOT EXISTS is idempotent).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Filter Pepperstone (and any future is_self competitor) out of the Emerging Competitors rail</name>
  <files>src/app/(dashboard)/markets/[code]/page.tsx</files>
  <action>
In the emergingRail builder around lines 566–587 of `src/app/(dashboard)/markets/[code]/page.tsx`, exclude any competitor where `isSelf` is truthy (it's stored as INTEGER 0/1 in SQLite — both `!== 1` and `!comp.isSelf` work; prefer `!comp.isSelf` for consistency with how `isSelf` is checked elsewhere in the codebase; verify the idiom with `grep -n "isSelf" src/app/(dashboard)/markets/[code]/page.tsx src/app/(dashboard)/page.tsx src/lib` and match the existing pattern).

Implementation: extend the existing `.map((r): EmergingItem | null => { ... })` block so that the early-return covers BOTH "competitor not in config" AND "competitor is self":

```typescript
.map((r): EmergingItem | null => {
  const comp = competitorById.get(r.competitorId);
  if (!comp) return null; // SERP found a competitor not yet in config — skip
  if (comp.isSelf) return null; // Pepperstone shows in own-brand SERPs (e.g., HK) — never emerge ourselves
  return { competitor: comp, queriesAppeared: r.queriesAppeared, bestRank: r.bestRank };
})
```

The dedicated second early-return (vs. fusing into one `if` with `||`) keeps the existing comment intact and makes the two distinct reasons visible in a stack trace / git blame.

Do NOT touch the `curatedAnyIds` filter on the line above — it's correct for its purpose (dedupe against curated rows) and conflating "self" with "curated" would mask future schema bugs (e.g., if Pepperstone ever gets curation rows for legitimate reasons we still want is_self to win).

This fix is per the operator report: "Pepperstone shows as Emerging Competitor in HK" — Pepperstone ranks in HK SERPs because we operate there, but we are the benchmark, not a competitor.

Commit message: `fix(markets): exclude is_self competitors from Emerging Competitors rail`
  </action>
  <verify>
    <automated>grep -n "comp.isSelf" "src/app/(dashboard)/markets/[code]/page.tsx" && npm run lint -- --max-warnings=0 src/app/\(dashboard\)/markets/\[code\]/page.tsx</automated>
  </verify>
  <done>
- The emergingRail `.map(...)` block contains an explicit `if (comp.isSelf) return null;` (or equivalent unambiguous is_self guard) before the EmergingItem return
- `npm run lint` passes with no new warnings on the modified file
- No other lines in `src/app/(dashboard)/markets/[code]/page.tsx` are modified
- Manual reasoning recorded in commit body: on HK (where the SERP CSV contains a Pepperstone row), the rail no longer surfaces Pepperstone; on any other market where Pepperstone happens to appear in the CSV, same result
  </done>
</task>

<task type="auto">
  <name>Task 2: Add competitor_markets table to the Next.js Drizzle bootstrap migrations</name>
  <files>src/db/migrate.ts</files>
  <action>
Append a `CREATE TABLE IF NOT EXISTS competitor_markets` block to `src/db/migrate.ts` so the Next.js process creates the table at boot (via `runMigrations()` already invoked from `src/db/index.ts`). This closes the gap where Phase 2.1's migration only ran inside Python `scrapers/db_utils.py get_db()` — the dashboard could crash on a freshly-deployed EC2 instance until a Python scraper happened to run.

Place the new block AFTER the existing `app_store_snapshots` CREATE TABLE / CREATE INDEX section (around line 192) and BEFORE the `scraper_config + market_config columns — DB-driven competitor configuration` ALTER loop. This keeps "create-table" migrations grouped before "alter-column" migrations, matching the file's existing ordering.

Mirror the Python migration in `scrapers/db_utils.py` EXACTLY — same column order, same CHECK constraint, same composite PK, same index — so Drizzle reads and Python writes never drift (per D2.1-02). Use the file's existing `sqlite.exec(...)` style (no try/catch needed for CREATE TABLE IF NOT EXISTS, same as wikifx_snapshots / ai_portfolio_insights elsewhere in this file):

```typescript
  // Phase 2.1 — competitor_markets (D2.1-01 / D2.1-02): operator-curated
  // per-market SHOW/HIDE list. MIRRORS scrapers/db_utils.py get_db() — keep
  // in sync. Empty/missing table is the default-safe state (D2.1-04 /
  // D2.1-05): /markets/<code> falls back to Phase 2 "show all" behavior.
  // Bugfix 2.2a-1 (2026-05-15): the Python-side migration only ran when a
  // Python scraper executed, so a freshly-deployed EC2 instance 500'd on
  // /markets/<code> until then. Drizzle migration here closes that gap.
  sqlite.exec(`CREATE TABLE IF NOT EXISTS competitor_markets (
    competitor_id TEXT NOT NULL REFERENCES competitors(id),
    market_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active','planned','withdrawn','emerging')),
    notes TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (competitor_id, market_code)
  )`);
  sqlite.exec(`CREATE INDEX IF NOT EXISTS idx_competitor_markets_market_status
    ON competitor_markets (market_code, status)`);
```

Idempotency: `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` are no-ops if the Python side already created them. The CHECK constraint must match byte-for-byte (`'active','planned','withdrawn','emerging'`) so SQLite considers the schema identical across creation paths.

Do NOT touch any other migration in the file. Do NOT add a try/catch — `CREATE TABLE IF NOT EXISTS` does not throw on existing tables. Do NOT add an Anti-Pattern fallback (e.g., wrapping the dashboard query in a try/catch and degrading to `[]` on missing table) — that approach was considered and rejected because it would mask future schema drift; the boot migration is the cleaner solution and matches the file's existing convention for additive table creation.

Commit message: `fix(db): create competitor_markets table on Next.js boot to mirror Python migration`
  </action>
  <verify>
    <automated>npx --yes drizzle-kit --version >/dev/null 2>&1 ; grep -n "CREATE TABLE IF NOT EXISTS competitor_markets" src/db/migrate.ts && grep -n "idx_competitor_markets_market_status" src/db/migrate.ts && rm -f /tmp/competitor-intel-test.db && DB_PATH=/tmp/competitor-intel-test.db node -e "require('./src/db/index.ts');" 2>&1 | head -20 ; sqlite3 /tmp/competitor-intel-test.db ".tables" 2>/dev/null | grep -c competitor_markets</automated>
  </verify>
  <done>
- `src/db/migrate.ts` contains the `CREATE TABLE IF NOT EXISTS competitor_markets` block and matching `CREATE INDEX IF NOT EXISTS idx_competitor_markets_market_status` block
- The CHECK constraint text matches `scrapers/db_utils.py get_db()` exactly: `CHECK (status IN ('active','planned','withdrawn','emerging'))`
- Running the Next.js process against a fresh SQLite file creates the `competitor_markets` table (verified by `sqlite3 <db> .tables` containing `competitor_markets`)
- Re-running against an existing DB that already has the table is a no-op (idempotent)
- No other migration in `src/db/migrate.ts` is modified
  </done>
</task>

<task type="auto">
  <name>Task 3: End-to-end verification — typecheck, lint, build, and fresh-DB smoke</name>
  <files>(verification only — no files modified)</files>
  <action>
Run the project's standard quality gates on the two-file diff and verify the bugfix against a fresh SQLite file. No code changes in this task — if any gate fails, fix the underlying issue with a follow-up commit (do NOT amend Task 1 or Task 2 commits).

Sequence:

1. `npm run lint` — must exit 0 with no new warnings on `src/app/(dashboard)/markets/[code]/page.tsx` or `src/db/migrate.ts`.

2. `npx tsc --noEmit` (or `npm run typecheck` if defined in `package.json`; check `package.json` `scripts` first — run whichever exists) — must exit 0. The diff only adds a property access (`comp.isSelf`) on an already-typed competitor row and a `sqlite.exec(...)` string, so type errors are unexpected.

3. `npm run build` — must succeed. This catches any Turbopack / Next.js 15 / React 19 surprise the diff might trigger (unlikely given the surgical scope, but the project's deployment posture requires it: `npm ci && npm run build` is the EC2 path per CLAUDE.md).

4. Fresh-DB smoke: confirm the migration creates the table on a clean SQLite file.
   ```bash
   rm -f /tmp/cad-bugfix-smoke.db
   DB_PATH=/tmp/cad-bugfix-smoke.db npx tsx -e "import('./src/db/index.ts').then(() => console.log('migrations ran'))"
   sqlite3 /tmp/cad-bugfix-smoke.db ".schema competitor_markets"
   ```
   Expected output: the CREATE TABLE statement echoed back, identical column shape to the Python side. If `npx tsx` is not available locally, fall back to `node --experimental-strip-types -e "..."` or compile via `npm run build` and let Next.js bootstrap touch the DB on first request.

5. Re-run smoke against the same file to confirm idempotency: a second run must not throw.

6. (Optional, only if local environment allows) Spin up `npm run dev`, navigate to `/markets/hk` against a DB where Pepperstone is in `logs/serp_research_hk.csv` and confirm: (a) the Emerging rail does NOT show Pepperstone, (b) the page renders without 500 even on a freshly-created DB. If local SERP CSVs are not available, mark this step as deferred to the EC2 deploy smoke and call it out in the commit body.

Commit message (only if any follow-up fix is needed): `chore(db): <specific follow-up>`. If gates 1–5 all pass without modifications, this task is verification-only — close it out in the SUMMARY without a commit.
  </action>
  <verify>
    <automated>npm run lint --silent && (npm run typecheck --silent 2>/dev/null || npx tsc --noEmit) && npm run build --silent</automated>
  </verify>
  <done>
- `npm run lint` exits 0 with no new warnings on the two modified files
- TypeScript typecheck exits 0
- `npm run build` succeeds
- Fresh-DB smoke shows `competitor_markets` table created on first import of `src/db/index.ts`
- Second smoke run is idempotent (no error)
- If a /markets/hk dev smoke was possible: Pepperstone is absent from the Emerging rail; page renders without 500 on fresh DB
- Any deferred verification step is explicitly called out in the SUMMARY's "Operator follow-ups" section
  </done>
</task>

</tasks>

<verification>
- Both fixes are independently committable and revertable (Task 1 touches only the rail builder; Task 2 touches only `migrate.ts`)
- The default-safe contract is preserved end-to-end: missing table → table created on boot → empty table → /markets/<code> renders identically to Phase 2 (show all)
- No schema drift between Drizzle and Python: the CREATE TABLE strings are byte-identical (same column order, same CHECK list, same PK shape, same index name)
- No new dependencies, no env var changes, no operator action required on EC2 beyond `npm ci && npm run build && pm2 reload` (or equivalent deploy step)
</verification>

<success_criteria>
- /markets/hk (and any other market where Pepperstone appears in the SERP CSV) no longer surfaces Pepperstone in the Emerging Competitors rail
- /markets/<code> renders without a 500 on a freshly-deployed EC2 instance even when no Python scraper has run yet
- Existing Phase 2.1 behavior is unchanged on markets where `competitor_markets` is already populated
- `npm run lint`, typecheck, and `npm run build` all pass on the diff
</success_criteria>

<output>
After completion, create `.planning/quick/260514-xbj-phase-2-1-bugfixes-2-2a-1-filter-out-pep/260514-xbj-SUMMARY.md` summarizing:
- The two fixes (one paragraph each, referencing line numbers / commit SHAs)
- Verification results (lint / typecheck / build / fresh-DB smoke)
- Any deferred verification steps for the EC2 deploy smoke
- Operator follow-ups: a one-liner `git pull && npm ci && npm run build && pm2 reload <app>` (or the project's equivalent) — the migration runs on Next.js boot, no manual SQL required
</output>

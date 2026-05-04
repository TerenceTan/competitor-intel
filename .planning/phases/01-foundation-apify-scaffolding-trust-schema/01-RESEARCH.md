# Phase 1: Foundation — Apify + Scaffolding + Trust Schema - Research

**Researched:** 2026-05-04
**Domain:** Apify Python SDK integration + Python orchestration scaffolding + additive SQLite/Drizzle trust schema
**Confidence:** HIGH on SDK call signatures, schema delta shape, healthchecks ping pattern; MEDIUM on exact Apify actor version tag history (Apify Store does not publish a version timeline page — pin must be confirmed by the planner at implementation time via Apify Console for the actor); HIGH on the competitor pick.

## Summary

Phase 1 is a vertically integrated PR: a new Python module that calls a single pinned Apify actor for one competitor's Facebook page, all the silent-failure guards around it, and the trust-UX schema columns/tables that every later phase reads. CONTEXT.md already locks 21 of the 21 design decisions — research below fills in the concrete API surface details, file targets, and verification commands the planner needs to write executable tasks.

**Verified facts that drive the plan:**

- `apify-client` Python **2.5.0** is current (released 2026-02-18, requires Python ≥3.10) `[VERIFIED: pypi.org/project/apify-client]`. `ActorClient.call()` accepts `run_input`, `build` (the version pin parameter), `max_total_charge_usd` (per-call cost cap, Decimal), `timeout_secs` (per-run hard cap), and `memory_mbytes`. Returns a run dict containing `defaultDatasetId`, `status`, `usageTotalUsd`, `stats`, `startedAt`, `finishedAt` `[VERIFIED: docs.apify.com/api/client/python ActorClient]`.
- `DatasetClient.get()` returns dataset metadata; `itemCount` is **not propagated immediately after push** — fetch via `list_items().items` and use `len(items)` for the assertion required by D-07 `[VERIFIED: docs.apify.com — Dataset metadata note]`.
- `apify/facebook-posts-scraper` is priced at **$2.00 / 1,000 posts** (≈ $0.002/post); free tier ships 500 posts/month `[VERIFIED: apify.com/apify/facebook-posts-scraper]`. At D-05's 1 competitor × weekly cadence × 50 posts/run = 200 posts/month ≈ **$0.40/month** — three orders of magnitude under the $100/mo cap.
- Healthchecks.io free **Hobbyist** tier: 20 checks, 100 log entries per check `[VERIFIED: healthchecks.io/pricing]`. Ping URL pattern is `https://hc-ping.com/<uuid>` (or slug-based). Append `/start`, `/fail`, or `/<exit_status>` for status signals `[VERIFIED: healthchecks.io/docs/signaling_failures]`. Recommended cron pattern is `curl --retry 3 https://hc-ping.com/<uuid>/$?` after the command runs (single-line, idempotent, status-aware).
- `subprocess.run(..., timeout=N)` raises `subprocess.TimeoutExpired`; the run() variant kills + waits internally, so per-scraper timeout in `run_all.py` only requires wrapping the existing call with `try/except TimeoutExpired` and continuing `[VERIFIED: docs.python.org subprocess.run]`. No `Popen` rewrite needed.
- The codebase **already has** an `EmptyState` component at `src/components/shared/empty-state.tsx` (not `src/components/ui/empty-state.tsx` as CONTEXT.md D-16 states). Phase 1 can extend the existing one rather than create a parallel file `[VERIFIED: ls src/components/shared/]`.
- **Local Python is 3.9.6** but `apify-client` 2.5.0 needs ≥3.10. EC2 production runs "Python 3" (no specific minor confirmed in repo) — this is a **must-verify** environment dependency before Phase 1 ships.

**Primary recommendation:** Plan Phase 1 in 4 logical waves the planner can parallelize where dependencies allow:
1. **Schema waves first** (Python migrations + Drizzle mirror) — additive, deployable ahead of code.
2. **Scaffolding waves** (log redaction module, run_all.py timeout/healthcheck wrapper) — pure Python, no external API, easy to verify in isolation.
3. **Apify integration wave** (apify_social.py + Thunderbit cutover for FB only) — depends on schema + scaffolding being merged.
4. **Trust UI wave** (extend EmptyState, build /admin/data-health page) + **calibration wave** (parallel with Apify integration).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SOCIAL-01 | Scrape competitor FB posts via pinned Apify actor (`apify/facebook-posts-scraper`) → `social_snapshots` | Apify SDK call signature verified; `build` parameter confirmed for version pinning; output mapping to existing `_upsert_social()` helper documented (Architecture Patterns → Pattern 2) |
| SOCIAL-04 | Zero-result detection: write `change_events` row typed `scraper_zero_results`, skip snapshot insert | `len(items) == 0` assertion pattern documented; `change_events` table reuse (no new table needed); existing `detect_change()` helper sidestepped because this is a synthetic event, not a value diff (Architecture Patterns → Pattern 3) |
| SOCIAL-05 | Log every Apify run to `apify_run_logs` with actor_id, version, market_code, dataset count, cost, status | Run object fields `usageTotalUsd`, `defaultDatasetId`, `status`, `startedAt`, `finishedAt` verified; full DDL in Standard Stack → Schema Deltas |
| SOCIAL-06 | Pay-per-run actors only (no `:latest`); monthly spending cap enforced in Apify Console before first scheduled run | `build` parameter required in every `.call()`; D-06 cap is operator-set (cannot be enforced in code); runbook entry shape provided in Code Examples |
| INFRA-01 | Each scheduled scraper pings healthcheck on success | Healthchecks.io ping URL pattern + curl retry pattern verified; one URL per scraper per D-10; runbook entry for operator HC.io account creation (Code Examples → Healthcheck Wrapper) |
| INFRA-02 | `run_all.py` enforces 30-min per-scraper timeout, continues on hang | `subprocess.run(timeout=1800)` + `TimeoutExpired` pattern verified; no Popen rewrite needed (Code Examples → run_all timeout wrapper) |
| INFRA-03 | Logs use redaction filter that strips API keys/tokens before writing | `logging.Filter` subclass attached at root logger; pattern + applied-to-every-scraper-entry-point list in Code Examples → Log Redaction |
| INFRA-04 | Healthcheck endpoints monitored — silent cron failures detected within hours | Healthchecks.io missed-ping policy verified: state moves Late → Down, Down sends configured alert; free tier supports email |
| INFRA-05 | All schema changes additive — no FK changes to existing tables, defaults so legacy rows unchanged | Existing `db_utils.get_db()` migration pattern (lines 41–135) is the precedent — additive `ALTER TABLE ADD COLUMN` wrapped in try/except for idempotency; new tables use `CREATE TABLE IF NOT EXISTS`; full DDL provided |
| TRUST-01 | `extraction_confidence TEXT` column on `promo_snapshots` and `social_snapshots`; populated at insert time | Two `ALTER TABLE ADD COLUMN` statements; nullable; new Apify scraper writes 'high'/'medium'/'low' at insert per D-18 heuristic; legacy rows stay NULL (no backfill); Drizzle schema mirror required (Schema Deltas) |
| TRUST-04 | `<EmptyState reason="scraper-failed">` distinguishes scraper failure from "no activity" | Existing `EmptyState` component at `src/components/shared/empty-state.tsx` extended (not duplicated) with a `reason` discriminated union; reads from `scraper_runs` (existing) + `apify_run_logs` (new); see Code Examples → EmptyState extension |
| TRUST-05 | Data Health page at `/admin/data-health` shows per-scraper status, last successful run, zero-result counts (7d), Apify cost-to-date | `force-dynamic` server component, `Promise.all()` of 3 Drizzle queries; cost rendered as `$X.XX of $100/mo (XX%)` per CONTEXT.md specifics; placement next to existing `/admin/page.tsx`; full query shape in Code Examples |
| EXTRACT-05 | 20–30 hand-labeled items per non-English language (TH/VN/TW/HK/ID); `validate_extraction.py` reports per-language accuracy ≥85% | JSONL format per D-19; validator imports the existing `ai_analyzer.py` extraction prompt (no new prompt invented); per-D-21 NOT a blocker for Apify cutover; structural-equivalence comparison (not strict string match) for nested expected_output |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Apify integration**
- **D-01:** New file `scrapers/apify_social.py`, sibling to `scrapers/social_scraper.py`, replacing the Thunderbit `_thunderbit_extract()` call site for FB only in Phase 1. YouTube path in `social_scraper.py` stays untouched.
- **D-02:** Python SDK `apify-client` v2.5.0 (PyPI). Python-only scraper layer; no Node.js scraping path.
- **D-03:** Synchronous actor invocation. Pattern: `client.actor("apify/facebook-posts-scraper").call(run_input=...)`. No webhooks, no async polling.
- **D-04:** Phase 1 actor: `apify/facebook-posts-scraper` only, version pinned to a specific tag (TBD by planner — must NOT use `:latest`). IG and X deferred to Phase 2.
- **D-05:** One competitor for the Phase 1 demo. Choose from `scrapers/config.py`. Acceptance: dashboard displays non-stale FB posts/follower count for that competitor in the global market view.
- **D-06:** Apify spending cap = $100/month, set in the Apify Console before the first scheduled run. Manual operator step.

**Zero-result detection**
- **D-07:** After every actor call, assert `dataset.itemCount > 0`. On zero results, write `change_events` row of type `scraper_zero_results` (with competitor_id, platform, market_code, run_id metadata) and skip the snapshot insert entirely.
- **D-08:** New table `apify_run_logs` (additive migration). Columns: `run_id`, `actor_id`, `actor_version`, `competitor_id`, `platform`, `market_code`, `started_at`, `finished_at`, `status`, `dataset_count`, `cost_usd`, `error_message`.

**Healthchecks**
- **D-09:** Healthchecks.io free tier. Each scheduled job pings on success.
- **D-10:** One ping URL per scheduled scraper, env vars `HEALTHCHECK_URL_APIFY_SOCIAL`, `HEALTHCHECK_URL_PROMO`, etc. Pings at successful completion only; failures rely on missed-ping alarm.

**Run timeouts**
- **D-11:** Per-scraper timeout in `run_all.py` using `subprocess.run(..., timeout=1800)` (30 min). On timeout: kill, log failure, write `scraper_runs` failure row, continue to next scraper.

**Log redaction**
- **D-12:** Python logging Filter at the root logger, applied across all scrapers. Strips known secret values from `os.environ` (`THUNDERBIT_API_KEY`, `SCRAPERAPI_KEY`, `ANTHROPIC_API_KEY`, `YOUTUBE_API_KEY`, new `APIFY_API_TOKEN`, `HEALTHCHECK_URL_*`) plus common token patterns. New `scrapers/log_redaction.py` module imported at top of every scraper entry-point.

**Schema deltas**
- **D-13:** Additive migrations only. No FK changes. New columns get defaults so existing rows don't need backfill.
- **D-14:** Phase 1 schema deltas (one PR):
  - `ALTER TABLE promo_snapshots ADD COLUMN extraction_confidence TEXT`
  - `ALTER TABLE social_snapshots ADD COLUMN extraction_confidence TEXT`
  - `CREATE TABLE IF NOT EXISTS apify_run_logs (...)` per D-08
  - `CREATE TABLE IF NOT EXISTS share_of_search_snapshots (...)` — table only, no Phase 3 sync code
- **D-15:** Drizzle schema in `src/db/schema.ts` updated to match SQLite migrations. Both land in same PR.

**Trust UX skeleton**
- **D-16:** `<EmptyState reason="scraper-failed">` React component placed at `src/components/ui/empty-state.tsx`. *(Research note: existing component already lives at `src/components/shared/empty-state.tsx` — see Architecture Patterns for reconciliation.)*
- **D-17:** Data Health page at `/admin/data-health`. Server component (`force-dynamic`). Shows per-scraper status, Apify cost-to-date for current month, total scraper run count.
- **D-18:** Confidence column populated at insert by Apify scraper. `'high'` when actor returned complete post object; `'medium'` when partial; `'low'` when inferred/partial.

**Calibration**
- **D-19:** JSONL format at `scrapers/calibration/promo_extraction.jsonl`. 20–30 items per non-English language (TH, VN, TW, HK, ID).
- **D-20:** Validation script at `scrapers/calibration/validate_extraction.py`. Phase 1 acceptance: ≥85% accuracy per language; markets failing flagged for Phase 3 prompt iteration.
- **D-21:** Calibration is Phase 1 deliverable, NOT a Phase 1 blocker for Apify cutover. Both proceed in parallel.

### Claude's Discretion
- Specific Apify actor version tag for `apify/facebook-posts-scraper` — pick from current Apify Store actor history; pin to a recent stable release.
- Specific competitor for the Phase 1 demo — pick from `scrapers/config.py`; prefer one with a confirmed-active public FB page.
- Exact column types for `apify_run_logs` and `share_of_search_snapshots` (TEXT vs INTEGER vs REAL) — follow existing column-type conventions in `src/db/schema.ts`.
- Run input parameters for Apify actors (`maxPosts`, `resultsLimit`, etc.) — pick reasonable defaults that fit the $100/mo cap with margin.
- Healthcheck.io account creation, project setup, ping URL provisioning — operator task; planner produces the runbook entry.

### Deferred Ideas (OUT OF SCOPE)
- Visualping / Wayback diff for promo page changes
- Slack/email alerting on healthcheck failure beyond HC.io's built-in email
- Auto-rotating Apify actor versions when current pin reaches EOL
- Per-actor cost projections in the Data Health page (Phase 5 polish — Phase 1 shows total only)
- Calibration set automation (synthetic data generation)
</user_constraints>

## Project Constraints (from CLAUDE.md)

The planner must verify every plan honors these directives:

- **Stack is locked:** Next.js 15.2.4, React 19.2.3, Drizzle 0.45.1, better-sqlite3 12.8.0, anthropic 0.40.0, Python 3 scrapers. No framework or DB swaps.
- **SQLite stays.** Schema additions kept additive and simple (matches D-13).
- **Deploy:** `npm ci` on EC2 only — never `npm install`.
- **No expensive new SaaS** beyond modest Apify usage (≈ pay-per-run × handful of competitors × weekly).
- **Naming:** Python = snake_case files/functions; TS = camelCase functions, PascalCase components/types; SQL columns = snake_case; constants = UPPER_SNAKE_CASE.
- **Error handling for new API routes (none in Phase 1, but if introduced):** `NextResponse.json({ error: "message" }, { status: CODE })`; status codes 400/401/403/409/429/503; descriptive messages.
- **URL validation in any new outbound HTTP:** use `isPublicHttpUrl()` (in `src/lib/utils.ts`) — rejects localhost/private/loopback/metadata IPs.
- **Cookies:** `httpOnly`, `secure` in production, `sameSite: "strict"` (only relevant if Phase 1 adds new auth surfaces — it doesn't).
- **Timing-safe comparison** for any token check using Node `crypto.timingSafeEqual()` or middleware Edge equivalent.
- **No `Co-Authored-By` lines in commits** (per user MEMORY).
- **Comments on security/validation logic** must document the threat model.
- **All dashboard pages stay `force-dynamic`** — D-17's Data Health page must declare `export const dynamic = "force-dynamic"`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Apify actor invocation + dataset fetch | Python scrapers (`scrapers/apify_social.py`) | — | All scraper logic lives in Python per D-01/D-02 and matches existing scraper layer pattern |
| Zero-result detection + `change_events` write | Python scrapers | Database (SQLite via `db_utils`) | Detection is per-run logic; persistence reuses existing `db_utils.get_db()` connection |
| `apify_run_logs` insert per actor run | Python scrapers | Database | New table but written through `db_utils` connection — no new write path |
| Healthcheck ping on success | Python orchestrator (`scrapers/run_all.py`) | OS / cron | Wrapper around subprocess invocation; pings via `curl` shelled out OR via `requests.get()` inside Python wrapper |
| Per-scraper subprocess timeout | Python orchestrator | OS | `subprocess.run(timeout=...)` lives in `run_all.py`; OS handles SIGTERM on timeout via subprocess module |
| Log redaction | Python (`scrapers/log_redaction.py`) | — | `logging.Filter` attached at root logger from each scraper entry-point; runs in-process before any handler writes |
| Additive SQLite migrations | Python (`scrapers/db_utils.py`) | — | Existing precedent (lines 41–135); migrations run inside `get_db()` on first connection per process |
| Drizzle schema mirror | Frontend / API (`src/db/schema.ts`) | — | TS types only — Drizzle does NOT push schema changes to SQLite; Python migrations are the source of truth |
| `<EmptyState reason="scraper-failed">` | Frontend (React server components) | — | Renders inside dashboard pages; reads from server-side queries |
| `/admin/data-health` page | Frontend Server (Next.js SSR) | Database (Drizzle reads) | `force-dynamic` server component; parallel `Promise.all` queries; matches existing `/admin/page.tsx` pattern |
| Apify spending cap enforcement | Apify Console (external) | Operator | Cannot be set from code per D-06; lives in deploy runbook |
| Calibration JSONL + validator | Python (`scrapers/calibration/`) | — | Standalone CLI script; imports existing extraction prompt from `ai_analyzer.py` |

## Standard Stack

### Core (already in `scrapers/requirements.txt` or to be added)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `apify-client` | **2.5.0** (PyPI, Python ≥3.10 required) `[VERIFIED: pypi.org/project/apify-client]` | Synchronous Apify actor invocation + dataset fetch | Locked by D-02; official Apify Python SDK; same toolchain as existing scrapers |
| `requests` | 2.32.3 (already pinned) | Healthcheck pings inside `run_all.py` wrapper (alternative to shelling `curl`) | Already in repo |
| `python-dotenv` | 1.0.1 (already pinned) | Load `.env.local` into env (existing pattern in `social_scraper.py` line 36) | Already in repo |

### Supporting (existing — no new deps)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `better-sqlite3` | 12.8.0 | Drizzle reads (TypeScript) | When the dashboard reads `apify_run_logs` for the Data Health page |
| `drizzle-orm` | 0.45.1 | Type-safe queries against new tables | All TypeScript reads of new tables — never raw SQL in Drizzle code |
| `lucide-react` | 0.577.0 | Icons for `<EmptyState reason="scraper-failed">` (e.g., `<AlertOctagon>`) | Phase 1 UI — already used by `stale-data-banner.tsx` |
| `next-themes`, `shadcn/ui Table` | (already in stack) | Data Health page table styling | Reuse the same Table component already used by admin pages |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `apify-client` Python | `apify-client` Node.js + Drizzle write path | Rejected by D-02 — second toolchain in maintenance-mode codebase, two write paths to one SQLite file |
| Synchronous `actor.call()` | Webhook-triggered async run | Rejected by D-03 — webhooks add inbound auth surface; current scraper times are sub-minute; cron-driven sync model matches every other scraper |
| Healthchecks.io | Self-hosted dead-man-switch / Cronitor | Rejected by D-09 — Healthchecks.io free tier covers our 8 scrapers; ships immediately; integrates as one curl per cron |
| `subprocess.Popen` + manual `kill()` | `subprocess.run(timeout=...)` | Use `run()` per D-11 — built-in timeout handling, raises `TimeoutExpired`, kills + waits internally; less code than Popen |

### Schema Deltas (additive only — D-13, D-14)

Append to `scrapers/db_utils.py` `get_db()` function following existing try/except idempotency pattern (lines 41–135). All deltas in the **same** Phase 1 PR:

```sql
-- Delta 1: extraction_confidence on promo_snapshots
ALTER TABLE promo_snapshots ADD COLUMN extraction_confidence TEXT;

-- Delta 2: extraction_confidence on social_snapshots
ALTER TABLE social_snapshots ADD COLUMN extraction_confidence TEXT;

-- Delta 3: apify_run_logs (per-actor-run diagnostics, used by Data Health page)
CREATE TABLE IF NOT EXISTS apify_run_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraper_run_id INTEGER REFERENCES scraper_runs(id),
    apify_run_id TEXT,                   -- Apify's UUID for the actor run
    actor_id TEXT NOT NULL,              -- e.g., 'apify/facebook-posts-scraper'
    actor_version TEXT,                  -- the build tag pinned in code (NEVER 'latest')
    competitor_id TEXT NOT NULL REFERENCES competitors(id),
    platform TEXT NOT NULL,              -- 'facebook' (Phase 2: 'instagram', 'x')
    market_code TEXT NOT NULL DEFAULT 'global',
    status TEXT NOT NULL,                -- 'success' | 'failed' | 'empty'
    dataset_count INTEGER DEFAULT 0,
    cost_usd REAL,                       -- from run.usageTotalUsd
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_apify_runs_competitor_platform_market
    ON apify_run_logs (competitor_id, platform, market_code);
CREATE INDEX IF NOT EXISTS idx_apify_runs_started_at
    ON apify_run_logs (started_at DESC);

-- Delta 4: share_of_search_snapshots (table only — no Phase 3 sync code yet)
CREATE TABLE IF NOT EXISTS share_of_search_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL,
    term TEXT NOT NULL,
    brand TEXT NOT NULL,
    share_of_search REAL NOT NULL,
    captured_at TEXT NOT NULL,           -- BQ source timestamp (ISO 8601 UTC)
    snapshot_date TEXT NOT NULL,         -- when the sync wrote this row
    UNIQUE (market_code, term, brand, captured_at)
);
CREATE INDEX IF NOT EXISTS idx_sos_market_brand
    ON share_of_search_snapshots (market_code, brand);
```

**Drizzle mirror** (`src/db/schema.ts`) — required by D-15, lands in same PR:

```typescript
// Append to existing promoSnapshots / socialSnapshots tables:
extractionConfidence: text("extraction_confidence"),  // 'high' | 'medium' | 'low' | null

// New tables:
export const apifyRunLogs = sqliteTable("apify_run_logs", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  scraperRunId: integer("scraper_run_id").references(() => scraperRuns.id),
  apifyRunId: text("apify_run_id"),
  actorId: text("actor_id").notNull(),
  actorVersion: text("actor_version"),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  platform: text("platform").notNull(),
  marketCode: text("market_code").notNull().default("global"),
  status: text("status").notNull(),
  datasetCount: integer("dataset_count").default(0),
  costUsd: real("cost_usd"),
  errorMessage: text("error_message"),
  startedAt: text("started_at").notNull(),
  finishedAt: text("finished_at"),
});

export const shareOfSearchSnapshots = sqliteTable("share_of_search_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  marketCode: text("market_code").notNull(),
  term: text("term").notNull(),
  brand: text("brand").notNull(),
  shareOfSearch: real("share_of_search").notNull(),
  capturedAt: text("captured_at").notNull(),
  snapshotDate: text("snapshot_date").notNull(),
});
```

**Important:** Drizzle 0.45.1 does NOT auto-push schema changes to the SQLite file. The Python `db_utils.py` migrations are the runtime source of truth; `schema.ts` only declares types so Drizzle reads compile and return correct shapes. **No `drizzle-kit generate` / `drizzle-kit push` step is required** — confirmed by reading `src/db/schema.ts` and `db_utils.py` (every existing column was added to both files in tandem with no migration files in `src/db/`).

**Installation:**

```bash
# Append to scrapers/requirements.txt:
apify-client==2.5.0

# Then install:
pip install -r scrapers/requirements.txt
```

**Version verification command:**

```bash
pip show apify-client | grep Version  # Should print "Version: 2.5.0"
python3 -c "from apify_client import ApifyClient; print(ApifyClient.__module__)"  # Sanity import
```

`apify-client` 2.5.0 published 2026-02-18 `[VERIFIED: pypi.org/project/apify-client]`.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ EC2 cron (already configured)                                   │
└────────────────────┬────────────────────────────────────────────┘
                     │ python scrapers/run_all.py
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│ scrapers/run_all.py  (MODIFIED)                                 │
│  • for each script: subprocess.run(..., timeout=1800)           │
│  • try/except TimeoutExpired → log + continue to next           │
│  • on success: curl HEALTHCHECK_URL_<scraper> (per D-10)        │
│  • SCRIPTS list now includes "apify_social.py"                  │
└────┬────────────┬────────────┬──────────────────────────────────┘
     │            │            │
     ▼            ▼            ▼
┌────────────┐ ┌────────────┐ ┌─────────────────────────────────┐
│ existing   │ │ social_    │ │ apify_social.py  (NEW)           │
│ scrapers   │ │ scraper.py │ │  • imports log_redaction         │
│ (untouched │ │ (MODIFIED: │ │  • client.actor("apify/fb-...")  │
│ except     │ │ FB path    │ │      .call(run_input=...,        │
│ for log    │ │ removed,   │ │            build="<pinned tag>", │
│ redaction  │ │ YouTube    │ │            max_total_charge_usd, │
│ import)    │ │ stays)     │ │            timeout_secs=900)     │
└────┬───────┘ └────┬───────┘ │  • items = client.dataset(...)   │
     │              │         │      .list_items().items         │
     │              │         │  • if len(items) == 0:           │
     │              │         │      write change_events row     │
     │              │         │      typed scraper_zero_results, │
     │              │         │      SKIP snapshot insert        │
     │              │         │  • else: _upsert_social() with   │
     │              │         │      extraction_confidence='high'│
     │              │         │  • always: insert apify_run_logs │
     │              │         │      with cost_usd from          │
     │              │         │      run["usageTotalUsd"]        │
     │              │         └────┬─────────────────────────────┘
     │              │              │
     ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│ scrapers/db_utils.py  (MODIFIED)                                 │
│  • get_db() runs additive migrations on first connection:       │
│      - extraction_confidence on promo_snapshots/social_snapshots│
│      - CREATE TABLE apify_run_logs                              │
│      - CREATE TABLE share_of_search_snapshots                   │
│  • existing detect_change(), log_scraper_run() reused unchanged │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│ data/competitor-intel.db  (SQLite, WAL mode)                    │
│  • social_snapshots (existing + new column)                     │
│  • apify_run_logs (new)                                         │
│  • change_events (existing — new event_type values)             │
│  • scraper_runs (existing — used by Data Health page)           │
└──────────┬──────────────────────────────────────────────────────┘
           │
           │ Drizzle reads at render time
           ▼
┌─────────────────────────────────────────────────────────────────┐
│ src/app/(dashboard)/admin/data-health/page.tsx  (NEW)           │
│  • force-dynamic server component                               │
│  • Promise.all([                                                │
│      latestRunPerScraper(),    ← scraper_runs                   │
│      apifyCostThisMonth(),     ← apify_run_logs SUM(cost_usd)   │
│      zeroResultCount7d(),      ← apify_run_logs WHERE status='empty'│
│    ])                                                           │
│  • Renders shadcn Table                                         │
│  • "$X.XX of $100/mo (XX%)" cost line, color-coded if >70%      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ src/components/shared/empty-state.tsx  (MODIFIED)                │
│  • Existing component extended with optional `reason` prop:     │
│    'scraper-failed' | 'scraper-empty' | 'no-activity' | undef   │
│  • Renders distinct icon + message per reason                   │
│  • 'scraper-failed' variant: AlertOctagon icon, red-tinted bg,  │
│    "Couldn't reach <competitor>'s <platform> page since <date>" │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ scrapers/log_redaction.py  (NEW)                                │
│  • SecretRedactionFilter(logging.Filter)                        │
│      - reads env vars at init (APIFY_API_TOKEN,                 │
│        HEALTHCHECK_URL_*, ANTHROPIC_API_KEY, etc.)              │
│      - filter() scans record.msg + record.args, replaces        │
│        secrets with "[REDACTED]"                                │
│      - regex pass for Bearer tokens, apify_api_*,               │
│        hex strings >32 chars                                    │
│  • install_redaction() helper attaches filter to root logger    │
│  • Imported as first line of every scraper entry-point          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ scrapers/calibration/  (NEW directory)                          │
│  • promo_extraction.jsonl  ← 100–150 hand-labeled items         │
│      (20–30 each for TH, VN, TW, HK, ID)                        │
│  • validate_extraction.py  ← imports prompt from ai_analyzer,   │
│      runs each input, structurally compares output to expected, │
│      reports per-language accuracy %                            │
│  • Acceptance: ≥85% per language → green; <85% → flag for       │
│      Phase 3 prompt iteration (NOT a Phase 1 blocker per D-21)  │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
scrapers/
├── apify_social.py          # NEW — Apify FB scraper (Phase 2 extends to IG/X)
├── log_redaction.py         # NEW — root-logger Filter for secret redaction
├── social_scraper.py        # MODIFIED — drop FB Thunderbit path; YouTube stays
├── run_all.py               # MODIFIED — per-scraper timeout + healthcheck pings
├── db_utils.py              # MODIFIED — append 4 schema deltas to get_db()
├── requirements.txt         # MODIFIED — add apify-client==2.5.0
└── calibration/             # NEW directory
    ├── promo_extraction.jsonl
    └── validate_extraction.py

src/
├── app/(dashboard)/admin/
│   └── data-health/
│       └── page.tsx         # NEW — Data Health page
├── components/shared/
│   └── empty-state.tsx      # MODIFIED — add reason="scraper-failed" variant
└── db/
    └── schema.ts            # MODIFIED — mirror SQLite migrations to Drizzle types
```

### Pattern 1: Apify actor invocation with version pin and cost cap

```python
# scrapers/apify_social.py (excerpt)
from apify_client import ApifyClient
from decimal import Decimal
import os, sys
from datetime import datetime, timezone

# IMPORTANT: install log redaction BEFORE any other import that may log.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from log_redaction import install_redaction
install_redaction()

# Pin actor version explicitly per A2 / D-04 — NEVER use `:latest`.
# Planner: confirm the current pin from Apify Console > Builds tab for this actor.
ACTOR_ID = "apify/facebook-posts-scraper"
ACTOR_BUILD = "1.16.0"  # PLACEHOLDER — planner must verify exact tag at implementation time

# Per-call cost cap belt-and-braces with the account-level $100/mo cap (D-06).
# 50 posts at $0.002 = $0.10 per call; cap at $1.00 to guard against runaway scrolls.
PER_CALL_COST_CAP_USD = Decimal("1.00")
PER_RUN_TIMEOUT_SECS = 900  # 15 min (subprocess gives 30 min outer cap per INFRA-02)

client = ApifyClient(os.environ["APIFY_API_TOKEN"])

run = client.actor(ACTOR_ID).call(
    run_input={
        "startUrls": [{"url": f"https://www.facebook.com/{competitor['facebook_slug']}"}],
        "resultsLimit": 50,           # bound output volume
        # Phase 2 will add: "proxy": {"useApifyProxy": True, "apifyProxyCountry": market_code}
    },
    build=ACTOR_BUILD,                # version pin per D-04
    max_total_charge_usd=PER_CALL_COST_CAP_USD,  # cost belt-and-braces
    timeout_secs=PER_RUN_TIMEOUT_SECS,
)

# run is a dict with: defaultDatasetId, status, usageTotalUsd, startedAt, finishedAt, ...
items = client.dataset(run["defaultDatasetId"]).list_items().items
```

`[VERIFIED: docs.apify.com/api/client/python ActorClient.call signature]`

### Pattern 2: Zero-result detection (silent-success guard, D-07)

```python
# scrapers/apify_social.py (excerpt)
from db_utils import get_db, log_scraper_run, update_scraper_run

conn = get_db()
snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

if len(items) == 0:
    # Zero-result silent-success — write change_events row, SKIP snapshot insert.
    # Use raw INSERT (not detect_change()) because this is a synthetic event,
    # not a value diff. detect_change() compares old vs new value strings.
    conn.execute(
        """
        INSERT INTO change_events
            (competitor_id, domain, field_name, old_value, new_value,
             severity, detected_at, market_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            competitor["id"],
            f"social_facebook",
            "scraper_zero_results",
            None,
            json.dumps({
                "actor_id": ACTOR_ID,
                "actor_version": ACTOR_BUILD,
                "apify_run_id": run["id"],
                "platform": "facebook",
            }),
            "medium",
            datetime.now(timezone.utc).isoformat(),
            market_code,  # 'global' for Phase 1
        ),
    )
    conn.commit()
    apify_status = "empty"
else:
    # Successful path: extract fields, write social_snapshot with confidence
    follower_count = _extract_followers(items[0])  # actor returns page metadata in items
    posts_last_7d = sum(1 for it in items if _is_within_7d(it.get("time")))
    confidence = "high" if all([follower_count, posts_last_7d is not None]) else "medium"

    # Reuse existing _upsert_social() helper from social_scraper.py — DO NOT
    # bypass db_utils. New extraction_confidence column added per D-14/D-18:
    conn.execute(
        """
        INSERT INTO social_snapshots
          (competitor_id, platform, snapshot_date, followers,
           posts_last_7d, latest_post_url, market_code, extraction_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (competitor["id"], "facebook", snapshot_date, follower_count,
         posts_last_7d, items[0].get("url"), market_code, confidence),
    )
    conn.commit()
    apify_status = "success"
```

### Pattern 3: `apify_run_logs` insert (always, regardless of success/empty/failure)

```python
# scrapers/apify_social.py (excerpt) — runs in finally block
conn.execute(
    """
    INSERT INTO apify_run_logs
        (scraper_run_id, apify_run_id, actor_id, actor_version,
         competitor_id, platform, market_code, status,
         dataset_count, cost_usd, error_message,
         started_at, finished_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        scraper_run_id,
        run.get("id"),
        ACTOR_ID,
        ACTOR_BUILD,
        competitor["id"],
        "facebook",
        market_code,
        apify_status,                    # 'success' | 'failed' | 'empty'
        len(items) if items else 0,
        float(run.get("usageTotalUsd", 0.0)),
        err_msg,                         # None on success
        run.get("startedAt"),
        run.get("finishedAt"),
    ),
)
conn.commit()
```

### Pattern 4: Per-scraper subprocess timeout (`run_all.py`, D-11)

```python
# scrapers/run_all.py (modified excerpt)
import subprocess

PER_SCRAPER_TIMEOUT_SECS = 1800  # 30 min hard cap per D-11

def run_script(script_name: str) -> tuple[bool, float, str]:
    script_path = os.path.join(SCRAPERS_DIR, script_name)
    log_path = os.path.join(LOGS_DIR, f"{_log_name(script_name)}.log")
    start = time.time()
    timed_out = False
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=PER_SCRAPER_TIMEOUT_SECS,  # subprocess.run() handles kill+wait internally
        )
        elapsed = time.time() - start
        output = result.stdout + (("\n--- STDERR ---\n" + result.stderr) if result.stderr else "")
        success = result.returncode == 0
    except subprocess.TimeoutExpired as e:
        timed_out = True
        elapsed = PER_SCRAPER_TIMEOUT_SECS
        output = (e.stdout.decode("utf-8", "replace") if e.stdout else "") + \
                 f"\n--- TIMEOUT after {PER_SCRAPER_TIMEOUT_SECS}s ---\n"
        success = False

    # Write to per-scraper log file (existing pattern)
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\nRun at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write(f"Status: {'TIMEOUT' if timed_out else ('OK' if success else 'FAILED')}\n")
        f.write(f"{'='*60}\n{output}\n")

    # Healthcheck ping on success ONLY (D-10) — failures rely on missed-ping alarm
    if success:
        _ping_healthcheck(script_name)

    return success, elapsed, output


def _ping_healthcheck(script_name: str):
    """Ping Healthchecks.io on successful scraper completion (D-09, D-10)."""
    env_var = f"HEALTHCHECK_URL_{script_name.replace('.py', '').upper()}"
    url = os.environ.get(env_var)
    if not url:
        return  # No HC URL configured for this scraper — skip silently
    try:
        # 5s timeout — never block scraper completion on HC.io being slow.
        # --retry 3 in curl analog: requests has no built-in retry, but
        # Healthchecks.io's missed-ping alarm covers transient ping failures.
        requests.get(url, timeout=5)
    except Exception:
        pass  # Ping failure is non-fatal; HC.io will catch the missed ping.
```

`[VERIFIED: docs.python.org/3/library/subprocess.html#subprocess.run timeout behavior]`

### Pattern 5: Log redaction (`scrapers/log_redaction.py`, D-12)

```python
# scrapers/log_redaction.py (NEW)
"""
Root-logger filter that strips known secret values + common token patterns
from every log record before any handler writes. Per CLAUDE.md error
handling rules + EC2 security incident history (April 2026), no API key
or credential should ever appear in scraper stdout/log files.

Threat model: a leaked log file (committed accidentally, attached to a
ticket, or read by a compromised process) must not expose secrets.

Install at top of every scraper entry-point BEFORE any other logging:
    from log_redaction import install_redaction
    install_redaction()
"""
import logging
import os
import re

# Env vars whose VALUES must be redacted from log output (not just keys).
_SECRET_ENV_VARS = (
    "APIFY_API_TOKEN",
    "ANTHROPIC_API_KEY",
    "YOUTUBE_API_KEY",
    "THUNDERBIT_API_KEY",     # legacy — still in env until cutover validated
    "SCRAPERAPI_KEY",         # legacy
    "DASHBOARD_PASSWORD",
    "GOOGLE_APPLICATION_CREDENTIALS",  # path, but redact in case path leaks UUID-y dir
)

# Healthcheck URLs are also secret (anyone with the URL can ping it).
_SECRET_ENV_PREFIX = "HEALTHCHECK_URL_"

# Generic token patterns — defense in depth for tokens that aren't in env.
_TOKEN_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"apify_api_[A-Za-z0-9]+"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),       # Anthropic tokens
    re.compile(r"\b[A-Fa-f0-9]{40,}\b"),         # generic hex tokens (40+ chars)
]

class SecretRedactionFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self._secrets = []
        for name in _SECRET_ENV_VARS:
            val = os.environ.get(name)
            if val and len(val) >= 6:  # avoid redacting trivially short values
                self._secrets.append(val)
        for name, val in os.environ.items():
            if name.startswith(_SECRET_ENV_PREFIX) and val:
                self._secrets.append(val)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for secret in self._secrets:
            redacted = redacted.replace(secret, "[REDACTED]")
        for pattern in _TOKEN_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()  # avoid double-format
        return True

def install_redaction():
    """Attach the filter to the root logger so every handler downstream sees redacted records."""
    root = logging.getLogger()
    # Idempotent: don't double-attach
    if not any(isinstance(f, SecretRedactionFilter) for f in root.filters):
        root.addFilter(SecretRedactionFilter())
```

**Performance impact:** Filter runs once per log call; string `.replace()` and pre-compiled regex on a typical log line (<1KB) is sub-microsecond. Negligible compared to subprocess + network IO that dominates scraper runtime.

**Caveat:** Existing scrapers use `print()` extensively, not `logging`. Print bypasses the logging system entirely. For Phase 1, the new `apify_social.py` uses `logging.getLogger(__name__).info(...)`. Existing scrapers' `print()` calls will be addressed when each is converted (out of Phase 1 scope per D-12 says "applied across all scrapers" via the import in entry-points; the planner should pick one of these reconciliations and document it):
- **Option A (recommended):** Phase 1 converts only `apify_social.py` to use `logging`; redaction module installed at every scraper entry-point but no-ops on `print()` output. Note this in the runbook for Phase 2.
- **Option B:** Add a `print()` shim that routes through `logging.info()`. Riskier — may break existing log shapes.

### Pattern 6: `<EmptyState reason="scraper-failed">` (D-16, with reconciliation)

**Reconciliation note:** D-16 specifies `src/components/ui/empty-state.tsx`, but the codebase already has `src/components/shared/empty-state.tsx` (verified). Two options for the planner:
- **Option A (recommended):** Extend the existing `src/components/shared/empty-state.tsx` with an optional `reason` prop. Single source of truth, no duplication, matches existing import sites.
- **Option B:** Create a new file at `src/components/ui/empty-state.tsx` per D-16 verbatim. Risks duplicate components and inconsistent imports.

Recommended extension:

```typescript
// src/components/shared/empty-state.tsx (extended)
import type { LucideIcon } from "lucide-react";
import { AlertOctagon, Inbox, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type EmptyStateReason = "scraper-failed" | "scraper-empty" | "no-activity" | undefined;

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  reason?: EmptyStateReason;  // NEW
}

const REASON_PRESETS: Record<NonNullable<EmptyStateReason>, { icon: LucideIcon; bg: string; iconColor: string }> = {
  "scraper-failed": { icon: AlertOctagon, bg: "bg-red-50 border-red-200", iconColor: "text-red-500" },
  "scraper-empty": { icon: AlertCircle, bg: "bg-amber-50 border-amber-200", iconColor: "text-amber-500" },
  "no-activity": { icon: Inbox, bg: "bg-white border-gray-200", iconColor: "text-gray-400" },
};

export function EmptyState({ icon: Icon, title, description, action, reason }: EmptyStateProps) {
  const preset = reason ? REASON_PRESETS[reason] : null;
  const ResolvedIcon = Icon ?? preset?.icon;
  return (
    <div className={cn("rounded-xl border p-10 text-center", preset?.bg ?? "bg-white border-gray-200")}>
      {ResolvedIcon && (
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-white">
          <ResolvedIcon className={cn("h-6 w-6", preset?.iconColor ?? "text-gray-400")} />
        </div>
      )}
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

Existing call sites continue to work unchanged (reason is optional). New uses:

```tsx
<EmptyState
  reason="scraper-failed"
  title="Couldn't reach IC Markets' Facebook page"
  description={`Last successful scrape: ${formatRelative(lastSuccessAt)}.`}
  action={<Link href="/admin/data-health" className="text-sm underline">View Data Health</Link>}
/>
```

### Pattern 7: Data Health page (`/admin/data-health`, D-17)

```typescript
// src/app/(dashboard)/admin/data-health/page.tsx (NEW)
import { db } from "@/db";
import { scraperRuns, apifyRunLogs } from "@/db/schema";
import { desc, sql, gte, and, eq } from "drizzle-orm";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { SCRAPERS } from "@/lib/constants";
import { formatDateTime } from "@/lib/utils";

export const dynamic = "force-dynamic";  // matches existing dashboard pages

const APIFY_MONTHLY_CAP_USD = 100;

export default async function DataHealthPage() {
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString();

  const [latestRuns, costRow, zeroCounts] = await Promise.all([
    // Latest run per scraper (collapse via Map in JS — Drizzle doesn't have a clean DISTINCT ON for SQLite)
    db.select({
      scraperName: scraperRuns.scraperName,
      finishedAt: scraperRuns.finishedAt,
      status: scraperRuns.status,
      errorMessage: scraperRuns.errorMessage,
    })
      .from(scraperRuns)
      .orderBy(desc(scraperRuns.startedAt))
      .limit(200),

    // Apify cost-to-date for current month
    db.select({
      total: sql<number>`COALESCE(SUM(${apifyRunLogs.costUsd}), 0)`,
    })
      .from(apifyRunLogs)
      .where(gte(apifyRunLogs.startedAt, monthStart))
      .then(r => r[0]),

    // Zero-result counts per (scraper) over last 7d
    db.select({
      actorId: apifyRunLogs.actorId,
      count: sql<number>`COUNT(*)`,
    })
      .from(apifyRunLogs)
      .where(and(eq(apifyRunLogs.status, "empty"), gte(apifyRunLogs.startedAt, sevenDaysAgo)))
      .groupBy(apifyRunLogs.actorId),
  ]);

  const latestByScraper = new Map<string, { finishedAt: string | null; status: string; error: string | null }>();
  for (const r of latestRuns) {
    if (!latestByScraper.has(r.scraperName)) {
      latestByScraper.set(r.scraperName, { finishedAt: r.finishedAt, status: r.status, error: r.errorMessage });
    }
  }

  const costPct = Math.round((costRow.total / APIFY_MONTHLY_CAP_USD) * 100);
  const costColor = costPct >= 70 ? "text-red-600" : costPct >= 40 ? "text-amber-600" : "text-green-700";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Data Health</h1>
        <p className="text-sm text-gray-500 mt-1">Per-scraper status, zero-result counts, and Apify cost-to-date.</p>
      </div>

      <section className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="text-sm font-medium text-gray-700 mb-2">Apify Cost (this month)</h2>
        <p className={`text-3xl font-semibold ${costColor}`}>
          ${costRow.total.toFixed(2)} <span className="text-base font-normal text-gray-500">of ${APIFY_MONTHLY_CAP_USD}/mo cap ({costPct}%)</span>
        </p>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Scraper</TableHead>
              <TableHead>Last run</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Zero-result runs (7d)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {SCRAPERS.map((s) => {
              const latest = latestByScraper.get(s.dbName);
              const zr = zeroCounts.find(z => z.actorId.includes(s.name))?.count ?? 0;
              return (
                <TableRow key={s.name}>
                  <TableCell className="font-medium">{s.label}</TableCell>
                  <TableCell>{latest?.finishedAt ? formatDateTime(latest.finishedAt) : "—"}</TableCell>
                  <TableCell>
                    <span className={latest?.status === "success" ? "text-green-700" : "text-red-600"}>
                      {latest?.status ?? "never run"}
                    </span>
                  </TableCell>
                  <TableCell>{zr > 0 ? <span className="text-amber-600">{zr}</span> : "0"}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </section>
    </div>
  );
}
```

### Anti-Patterns to Avoid

- **Don't use `:latest` for the actor build.** Pin per D-04. Schema drift between actor minor versions (e.g., `caption` → `text`) silently inserts `null` rows. Use the `build="<tag>"` parameter.
- **Don't bypass `db_utils.get_db()` for new scraper writes.** Existing migration discipline (lines 41–135) and the WAL/`PRAGMA foreign_keys=ON` setup are non-trivial; reusing the connection helper guarantees consistency.
- **Don't add Drizzle migrations files (`drizzle-kit generate`).** This codebase uses Python as the migration source of truth. Adding `drizzle-kit` would create two migration paths that drift.
- **Don't write a `print()`-based logger in `apify_social.py`.** Use `logging.getLogger(__name__)` so the redaction filter (D-12) actually runs. Existing `print()` calls in other scrapers are out of Phase 1 scope.
- **Don't insert a `social_snapshots` row when `len(items) == 0`.** That is exactly the silent-success failure mode D-07/SOCIAL-04 exists to prevent. Write a `change_events` row instead and skip the snapshot.
- **Don't try to enforce the $100/mo Apify cap in code.** Per D-06 it's an Apify Console setting only. Code can enforce per-call `max_total_charge_usd` as belt-and-braces but cannot replace the account-level cap.
- **Don't pin the existing `EmptyState` to `src/components/ui/`** if reconciling D-16 — the existing component lives at `src/components/shared/empty-state.tsx` and is already imported by callers.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry / backoff for Apify | Custom retry loop in `apify_social.py` | `apify-client`'s built-in retry (configurable on `ApifyClient` init) | The SDK already handles 429s and transient 5xxs |
| Subprocess timeout + cleanup | `Popen` + manual `kill()` + `waitpid()` | `subprocess.run(timeout=N)` | Built-in handles kill+wait+pipe drain in one call (D-11) |
| Cron healthcheck dead-man-switch | Self-hosted MAILTO + log parser | Healthchecks.io free tier | D-09; one curl per scraper; reliability is HC.io's problem, not ours |
| SQL change tracking | Bespoke change feed | Existing `change_events` + `detect_change()` helper | Already production-grade; new scraper just adds new event_type values |
| Per-run cost tracking | Cost rate × items math in code | `run["usageTotalUsd"]` directly from Apify run object | Apify computes the actual billed amount including proxy/CU; trust the source |
| Schema migration runner | `drizzle-kit migrate` + migration files | Existing `db_utils.get_db()` `ALTER TABLE` block | Pattern works, one source of truth (Python), zero new tooling |
| Empty-state UI | Brand new `<ScraperFailedEmptyState>` component | Extend existing `<EmptyState>` with optional `reason` prop | Existing component already used; consistency, less surface area |
| Currency formatting | Hand-rolled `$X.XX` template | `Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })` | Built-in; locale-aware; matches existing codebase patterns |

## Runtime State Inventory

> Phase 1 is mostly greenfield (new module + additive schema), but it does deprecate parts of an existing path (Thunderbit FB extraction) and writes new env vars + log files.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | `social_snapshots` rows already exist with `extraction_confidence = NULL` (column added by Phase 1 migration). New rows from `apify_social.py` write `'high'`/`'medium'`. **No backfill** — D-18 explicitly says null on legacy rows is acceptable; UI treats null as "no badge." | None — write-time only, no migration of existing rows |
| **Live service config** | Apify Console: $100/mo spending cap (D-06) MUST be set before first scheduled run; Healthchecks.io account: 1 check per scheduled scraper (currently 8 in `SCRIPTS` list); EC2 cron: `social-scraper.py` cron line still wires to existing entry-point (no change to cron lines this phase) | Operator runbook — see Environment Availability section. Two manual steps before first production run: (1) set Apify cap; (2) provision HC.io URLs and set env vars on EC2 |
| **OS-registered state** | EC2 cron entries — none change in Phase 1 (existing `python scrapers/run_all.py` cron line continues; `apify_social.py` is added to the SCRIPTS list inside `run_all.py`, not a new cron line). PM2 / systemd: dashboard pm2 service unaffected. | None |
| **Secrets / env vars** | NEW: `APIFY_API_TOKEN`, `HEALTHCHECK_URL_*` (one per scraper). EXISTING (still needed): `THUNDERBIT_API_KEY`, `SCRAPERAPI_KEY` (kept until Apify cutover validated per STACK.md "Remove/deprecate" section), `YOUTUBE_API_KEY`, `ANTHROPIC_API_KEY`, `DASHBOARD_PASSWORD`. The redaction filter must read all of these at install time (D-12). | Add new secrets to `.env.local` AND EC2 environment. Document in runbook. Do NOT remove THUNDERBIT_API_KEY until cutover validated. |
| **Build artifacts / installed packages** | `pip install -r scrapers/requirements.txt` adds `apify-client==2.5.0` to the EC2 Python environment. **Local dev runs Python 3.9.6 but `apify-client` 2.5.0 requires Python ≥3.10** — verify EC2 Python version before deploy; may require `python3.10`+ install on EC2. | Phase 1 task: confirm EC2 Python version meets ≥3.10 (or add task to upgrade). Local dev needs `pyenv install 3.10` or equivalent to import `apify-client` |

## Common Pitfalls

(Drawn from `.planning/research/PITFALLS.md`; concrete prevention for Phase 1.)

### Pitfall 1: Apify actor returns empty array, run.status=SUCCEEDED, dashboard shows "fresh" empty data (PITFALLS A1)

**What goes wrong:** Geo-block, broken selector, or actor regression returns `[]`. Apify reports SUCCEEDED. Naive scraper inserts a row timestamped now with NULL fields → dashboard shows "updated 2 hours ago, 0 followers."

**Why it happens:** Apify treats "actor didn't throw" as success.

**How to avoid:**
- After every `client.actor(...).call(...)`, fetch `items = client.dataset(run["defaultDatasetId"]).list_items().items` and assert `len(items) > 0`.
- On `len(items) == 0`: write `change_events` row typed `scraper_zero_results` with `actor_id`/`actor_version`/`apify_run_id` in `new_value` JSON; SKIP the `social_snapshots` insert; status='empty' in `apify_run_logs`.
- Do NOT use `dataset.get()["itemCount"]` — Apify's docs note `itemCount` propagation is not immediate after push. Use `len(items)` after `list_items()`.

**Warning signs:** A `(competitor, platform, market)` triple with zero new posts when historical cadence is daily/weekly; spike in `apify_run_logs.status='empty'` rows.

### Pitfall 2: Actor schema drift between minor versions (PITFALLS A2)

**What goes wrong:** `:latest` pulls a new minor version where `caption` becomes `text` or `likesCount` becomes `likes`. Parser inserts `null`. Engagement metrics drop to 0 across all competitors at once.

**How to avoid:**
- Pass explicit `build="<exact tag>"` to `.call()` per D-04. Never `:latest` (the SDK default).
- Document the pinned tag and the date it was pinned in a code comment AND in the deploy runbook.
- When bumping the pin: run against the demo competitor in dev, diff parsed output against the previous run, then deploy.

**Warning signs:** New fields appearing as `null` after a code/SDK update; sudden drop in `extraction_confidence='high'` rows.

### Pitfall 3: Apify cost runaway (PITFALLS A4)

**What goes wrong:** A long-running actor + transient retry burns $29/run; undetected for a week → $200–400 surprise bill.

**How to avoid:**
- D-06 account-level cap: $100/mo (manual operator step in Apify Console).
- Belt-and-braces: pass `max_total_charge_usd=Decimal("1.00")` per `.call()` and `timeout_secs=900`.
- Set `resultsLimit=50` in the actor input — bound output volume.
- Data Health page shows live cost vs cap (Pattern 7).

**Warning signs:** Apify daily spend > $5 (sanity baseline). Data Health "cost-to-date" trending past 70% of cap mid-month.

### Pitfall 4: `run_all.py` hangs because one scraper hangs (PITFALLS F5)

**What goes wrong:** Without per-scraper timeout, a hung Playwright session in one scraper blocks every subsequent scraper. Cron looks like it's running; nothing's actually happening.

**How to avoid:**
- D-11: `subprocess.run(..., timeout=1800)` + `try/except TimeoutExpired` (Pattern 4).
- On TimeoutExpired: log + continue to next script. The `subprocess.run()` form kills + waits internally — no zombie processes.
- Healthchecks.io ping happens only on success of each subprocess; missed-ping alarm catches the case where the entire `run_all.py` itself hangs.

**Warning signs:** `scraper_runs` shows long-running rows with no `finished_at`; HC.io shows scrapers as "Down".

### Pitfall 5: Secrets in scraper logs (PITFALLS F6)

**What goes wrong:** A library logs a request with the `Authorization: Bearer apify_api_xxx` header. Log file gets attached to a Slack message or pushed to a public log aggregator. Secret is leaked.

**How to avoid:**
- D-12 + Pattern 5: install `SecretRedactionFilter` at root logger via `install_redaction()` as the first import in every scraper entry-point.
- Filter scans every log message for env-var values and known token patterns.
- Verification: temporarily log the secret in dev (`logger.info(f"token={os.environ['APIFY_API_TOKEN']}")`) and confirm `[REDACTED]` appears.

**Warning signs:** Manual grep of `logs/apify-social.log | grep -E 'apify_api|Bearer'` returns hits.

### Pitfall 6: Drizzle types lag Python migrations (PITFALLS-style: causes type-incorrect Drizzle reads)

**What goes wrong:** Python migration adds `extraction_confidence` column. Drizzle `schema.ts` not updated in same PR. TS code that reads social_snapshots can't see the new column; new column is invisible to the dashboard.

**How to avoid:**
- D-15: both files updated in the same PR. Plan-checker should grep both for `extraction_confidence` to confirm.
- CI: `npm run lint && npx tsc --noEmit` catches Drizzle reads of nonexistent columns.

### Pitfall 7: Failed-vs-stale UX confusion (PITFALLS D2 — Phase 1 skeleton)

**What goes wrong:** A scraper succeeded-but-empty looks identical to "no competitor activity" — both render as "—" or empty cells.

**How to avoid:**
- TRUST-04 + Pattern 6: introduce `<EmptyState reason="scraper-failed">` distinct from default empty state.
- TRUST-05 + Pattern 7: Data Health page surfaces zero-result counts so operator can triage.

### Pitfall 8: Healthchecks.io URL leakage (custom)

**What goes wrong:** A leaked HC.io ping URL allows anyone to send fake "success" pings, masking real outages.

**How to avoid:**
- Treat ping URLs as secrets; redaction filter (Pattern 5) covers them via `HEALTHCHECK_URL_` prefix scan.
- Do NOT commit URLs to git. Provision in `.env.local` and EC2 environment only.

## Code Examples

(See Architecture Patterns 1–7 above for full code blocks. Sources annotated inline.)

### Healthcheck wrapper — alternative shell form (cron-side, optional)

If the planner prefers shell-side ping over Python `requests` in `run_all.py`:

```bash
# /etc/cron.d/dashboard-scrapers (example — actual file lives on EC2)
0 3 * * 0 ubuntu cd /opt/competitor-dashboard && \
  python3 scrapers/run_all.py && \
  curl --retry 3 --max-time 5 "$HEALTHCHECK_URL_RUN_ALL/$?"
```

`$?` propagates run_all's exit code → HC.io distinguishes success (0) from failure (>0). `[VERIFIED: healthchecks.io/docs/signaling_failures]`

### Picked competitor for Phase 1 demo (D-05)

**Recommended pick: `ic-markets`** (`facebook_slug: "icmarkets"`).

Reasoning:
- Tier-1 competitor with established global presence (verified in `scrapers/config.py` line 4–40).
- Facebook page slug `icmarkets` is the primary global handle (not a regional offshoot likely to be inactive).
- IC Markets is named explicitly in PITFALLS.md A3 as the suggested "canary competitor" for the daily-coverage assertion ("Run a daily 'canary' against a known-active competitor (e.g., IC Markets SG)").
- Already used as a manual-test target in the existing scraper (`python scrapers/social_scraper.py --broker ic-markets` per line 16 docstring).

**Backup pick: `exness`** (`facebook_slug: "Exness"`) — also tier-1, very active page.

**Planner action:** before writing the plan task, manually visit `https://www.facebook.com/icmarkets` to confirm the page is publicly accessible and posting recently. If dormant, fall back to `exness`. Take 2 minutes; saves a phase-1 demo embarrassment.

### Apify actor version pin candidate (D-04, Claude's discretion)

The Apify Store does not publish a public version-history page for `apify/facebook-posts-scraper` that the planner can deep-link from RESEARCH.md. The actor is "Last modified 3 days ago" as of 2026-05-04 `[VERIFIED: apify.com/apify/facebook-posts-scraper]` so any pre-2026-05 build is current.

**Recommended planner action:** at implementation time, log into Apify Console → Actor `apify/facebook-posts-scraper` → Builds tab. Pick the most recent **non-beta** build tag (typical format `<major>.<minor>.<patch>`, e.g., `1.16.0`) and pin that string as `ACTOR_BUILD` in code. Document the pin choice and date in a code comment AND in the runbook ("Pinned 2026-05-XX to build vX.Y.Z").

**Placeholder for plan tasks:** use `ACTOR_BUILD = "1.16.0"  # PLACEHOLDER` in the example and have the implementer replace it during the Apify Console step. Mark this as a `[ASSUMED]` claim — the exact tag must be user-confirmed.

### Apify input parameters fitting the $100/mo cap (D-06, Claude's discretion)

| Parameter | Recommended value | Why |
|-----------|-------------------|-----|
| `startUrls` | `[{"url": "https://www.facebook.com/icmarkets"}]` | One competitor per call (Phase 1) |
| `resultsLimit` | `50` | Bound output volume; matches existing `_FB_SCHEMA` `posts_last_7d` granularity |
| `onlyPostsOlderThan` / `onlyPostsNewerThan` | omit (use defaults) | Actor returns most recent posts first; 50 is enough for a weekly check |
| `commentsMode` / `replyMode` | omit (default off) | Comments are out of scope per FEATURES.md anti-features |
| `proxy` | omit (Phase 2 adds `apifyProxyCountry` per market) | Phase 1 is global-market only |

Cost arithmetic at recommended params: 50 posts × $0.002/post = **$0.10 per call**; weekly cadence = **$0.40/month** for one competitor. At Phase 2 (5 competitors × 8 markets × 3 platforms × weekly), STACK.md projects ~$35/month. Phase 1 is well clear of any cap.

### Calibration validate_extraction.py shape (D-19, D-20)

```python
# scrapers/calibration/validate_extraction.py (NEW)
"""
Validate the existing promo-extraction prompt against a hand-labeled JSONL set.

Phase 1 deliverable per D-19/D-20. Per D-21, NOT a Phase 1 blocker for Apify
cutover — markets failing the ≥85% bar are flagged for Phase 3 prompt iteration.

Usage:
    python scrapers/calibration/validate_extraction.py --jsonl scrapers/calibration/promo_extraction.jsonl
    python scrapers/calibration/validate_extraction.py --language th  # filter to one language
"""
import argparse
import json
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from log_redaction import install_redaction
install_redaction()

# Import the existing promo-extraction prompt + Claude call from ai_analyzer.py.
# Planner: confirm the exact symbol name (likely `extract_promo_fields()` or
# similar) at implementation time. If ai_analyzer.py doesn't expose a clean
# extraction function, refactor minimally to extract one — do NOT duplicate
# the prompt in this file (single source of truth).
from ai_analyzer import extract_promo_from_text  # PLACEHOLDER — verify exact symbol

ACCURACY_BAR = 0.85  # 85% per D-20

def structural_match(actual, expected) -> bool:
    """
    Compare extracted output to expected. For nested dicts, recurse field-by-field.
    Numbers compared with type coercion (1 == 1.0); strings normalized (lowercase, strip).
    Returns True if all expected fields are present and equal in actual.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(structural_match(actual.get(k), v) for k, v in expected.items())
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(expected - actual) < 0.001
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    return expected == actual

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", default="scrapers/calibration/promo_extraction.jsonl")
    parser.add_argument("--language", default=None, help="Filter to one language (th/vn/tw/hk/id)")
    args = parser.parse_args()

    by_language: dict[str, list[bool]] = defaultdict(list)

    with open(args.jsonl, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  ✗ line {line_no}: invalid JSON ({e})")
                continue
            if args.language and item.get("language") != args.language:
                continue
            try:
                actual = extract_promo_from_text(item["input_text"], language=item["language"])
            except Exception as e:
                print(f"  ✗ line {line_no} ({item['language']}): extraction error: {e}")
                by_language[item["language"]].append(False)
                continue
            ok = structural_match(actual, item["expected_output"])
            by_language[item["language"]].append(ok)
            if not ok:
                print(f"  ✗ line {line_no} ({item['language']}): expected={item['expected_output']}, got={actual}")

    print("\n=== Per-language accuracy ===")
    overall_pass = True
    for lang, results in sorted(by_language.items()):
        accuracy = sum(results) / len(results) if results else 0.0
        status = "PASS" if accuracy >= ACCURACY_BAR else "FAIL (flag for Phase 3)"
        print(f"  {lang}: {accuracy:.1%}  ({sum(results)}/{len(results)})  {status}")
        if accuracy < ACCURACY_BAR:
            overall_pass = False
    print()
    sys.exit(0 if overall_pass else 1)

if __name__ == "__main__":
    main()
```

JSONL line shape per D-19:

```json
{"market": "TH", "language": "th", "input_text": "...scraped page snippet...", "expected_output": {"promo_type": "deposit_bonus", "value": 50, "currency": "USD", "valid_from": "2026-05-01"}, "source_url": "..."}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Thunderbit AI extraction for FB/IG/X (existing in `social_scraper.py`) | Apify managed actor `apify/facebook-posts-scraper` (FB only Phase 1; IG/X Phase 2) | Phase 1 deliverable | Replaces broken pipeline; pay-per-result vs Thunderbit's cost model; structured output schema |
| ScraperAPI regex fallback for FB | Removed for FB path (kept in code for legacy YouTube safety only — see PROJECT.md "stabilize first") | Phase 1 (partial) | Removes dual-path complexity for FB; reduces secret surface (`SCRAPERAPI_KEY` still in env until cutover validated) |
| Silent cron via raw EC2 cron | EC2 cron + Healthchecks.io dead-man-switch per scraper | Phase 1 | Detection latency drops from days to ~hours (HC.io alarm window) |
| `run_all.py` runs scrapers without timeout | `subprocess.run(timeout=1800)` per scraper | Phase 1 | One hung scraper no longer blocks the rest of the pipeline |
| Logs may contain raw API tokens | Root-logger `SecretRedactionFilter` | Phase 1 | Defense-in-depth against the EC2 incident pattern |
| No per-row data confidence | `extraction_confidence TEXT` on `promo_snapshots` and `social_snapshots`, populated at insert | Phase 1 (column + writes); Phase 5 (UI surface) | Preserves the trust contract; legacy rows = NULL = no badge |
| No per-actor diagnostics | `apify_run_logs` table | Phase 1 | Per-(competitor, platform, market) triage and cost tracking |
| Only `/admin/page.tsx` for admin views | `/admin/data-health` skeleton | Phase 1 (skeleton); Phase 5 (polish) | Triage surface from day one |

**Deprecated/outdated:**
- Thunderbit FB extraction path (`_thunderbit_extract` calls for FB) — removed Phase 1.
- Apify SDK v1.x — superseded by 2.x line; 2.5.0 is current `[VERIFIED]`.
- `apify-client` Python <2.5 patterns that don't include `max_total_charge_usd` or `build` parameters — superseded.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Apify actor `apify/facebook-posts-scraper` build version `1.16.0` is a valid recent stable tag | Pattern 1, Code Examples → "Apify actor version pin candidate" | LOW — placeholder is clearly marked; planner verifies in Apify Console at implementation time and replaces. Wrong tag → `.call()` fails fast with "build not found" |
| A2 | EC2 production runs Python ≥3.10 (required by `apify-client` 2.5.0) | Standard Stack → Installation, Runtime State Inventory | HIGH — if EC2 is on Python 3.9 or lower, `pip install apify-client==2.5.0` will succeed but `import apify_client` will fail at runtime (Python 3.10+ syntax in package). Must confirm before deploy |
| A3 | `ic-markets` Facebook page (`https://www.facebook.com/icmarkets`) is publicly accessible and currently posting | Code Examples → Picked competitor | MEDIUM — if dormant or blocked, demo shows zero results and triggers the zero-result code path (which is itself testable). Backup is `exness` |
| A4 | `ai_analyzer.py` exposes (or can trivially expose) a `extract_promo_from_text(text, language)` function | Code Examples → Calibration validate_extraction.py | MEDIUM — symbol name is a guess; planner must inspect `ai_analyzer.py` and either use the existing function or refactor minimally to expose one. Risk is implementation-time, not Phase 1 acceptance |
| A5 | `print()` calls in existing scrapers are acceptable to leave un-redacted in Phase 1 (only new `apify_social.py` uses `logging`) | Pattern 5, Anti-Patterns | LOW — secrets are not currently being printed to logs by existing scrapers (verified by reading social_scraper.py); D-12's "applied across all scrapers" satisfied by import-at-entry-point even if `print()` bypasses it. Planner should flag for follow-up if any existing `print()` line includes a secret |
| A6 | The Apify run object's `usageTotalUsd` field is populated for synchronous `.call()` returns | Pattern 3, schema for `apify_run_logs.cost_usd` | MEDIUM — verified that the field exists in the Apify v2 API response shape, but the synchronous `.call()` may return before final usage settlement. If `usageTotalUsd` is null on first read, fall back to `client.run(run["id"]).get()` after a short delay |
| A7 | Local Python 3.9.6 is fine for development of non-Apify code in Phase 1; only `apify_social.py` requires Python 3.10+ | Environment Availability | LOW — developers can run schema migrations, calibration validator, and Drizzle changes on 3.9; only `apify_social.py` import will fail. Workaround: pyenv install 3.10 |

## Open Questions

1. **EC2 Python version (≥3.10 required by apify-client 2.5.0)?**
   - What we know: `scrapers/requirements.txt` doesn't pin a Python version; PROJECT.md says "Python 3" generically.
   - What's unclear: whether EC2 has 3.10+ or just 3.9.x.
   - Recommendation: Phase 1 task #0 is `ssh ec2 && python3 --version`. If <3.10, add an "install Python 3.10" task before any Apify deploy. Block the Apify cutover task until Python is confirmed.

2. **Should the redaction filter be applied to `print()` calls in existing scrapers?**
   - What we know: D-12 says "applied across all scrapers" but `print()` bypasses `logging`.
   - What's unclear: whether existing scrapers ever `print()` a secret (a quick grep of the existing files shows they don't, but that's not a guarantee).
   - Recommendation: Phase 1 plan adds a verification task — `grep -rE '(API_KEY|TOKEN|PASSWORD|SECRET)' scrapers/*.py | grep -v "os.environ"` — and if no hits, defer the `print()` shim to a future maintenance pass. If hits found, fix in same PR.

3. **Where does the Apify actor version pin get documented for ops?**
   - What we know: D-04 says "version pinned to a specific tag". Code comment + runbook entry recommended.
   - What's unclear: which file is the runbook (no `RUNBOOK.md` in repo).
   - Recommendation: Phase 1 plan creates `docs/APIFY_RUNBOOK.md` (or appends to existing `SCRAPER_SCHEDULE.md`) with: pinned actor versions, Apify cap setting steps, HC.io URL provisioning steps, secret rotation procedure. One file per integration.

4. **Healthchecks.io account ownership?**
   - What we know: D-09 says HC.io free tier; this is a manual operator step.
   - What's unclear: who owns the HC.io account (team-shared inbox? individual?).
   - Recommendation: use a team-shared inbox for the HC.io account so alerts don't depend on one person's email. Document in runbook.

5. **Does `extraction_confidence` need migration of existing rows?**
   - What we know: D-18 says "populated at insert" — null on legacy rows is acceptable. Phase 5 UI treats null as "no badge."
   - What's unclear: confirmation from product side that legacy rows showing "no badge" is acceptable UX (vs e.g., backfilling everything to "medium").
   - Recommendation: ship as null; document in Phase 5 plan as expected behavior.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | `apify-client` 2.5.0 | ✗ on local (3.9.6) / **UNKNOWN on EC2** | local: 3.9.6; EC2: TBD | Install Python 3.10+ on EC2 (likely via deadsnakes PPA or `pyenv`); local devs use `pyenv` |
| Node.js 22 LTS (EC2) / 25 (local) | Drizzle schema changes, Data Health page | ✓ | EC2: 22 LTS; local: 25.6.1 | — |
| `apify-client` Python | `scrapers/apify_social.py` | ✗ (not yet installed) | needed: 2.5.0 | Install: `pip install apify-client==2.5.0` (after Python 3.10+ confirmed) |
| `requests` Python | Healthcheck pings in `run_all.py` | ✓ | 2.32.3 (already in requirements.txt) | — |
| SQLite 3 | Database (already in use) | ✓ | local: 3.51.0; EC2: per build | — |
| `curl` | Optional shell-side healthcheck | ✓ | local: 8.7.1 | — |
| Apify account + API token | actor invocation | ✗ (must be created) | n/a | Operator: create account, generate API token, set monthly $100 cap, store token as `APIFY_API_TOKEN` |
| Healthchecks.io account | Cron monitoring | ✗ (must be created) | n/a | Operator: create free Hobbyist account (20 checks), provision 1 check per scraper, store URLs as `HEALTHCHECK_URL_*` |
| Drizzle Kit | Schema migration tooling | N/A — not used | — | Codebase pattern is Python-as-source-of-truth; Drizzle schema.ts is types-only. No `drizzle-kit` invocation needed |

**Missing dependencies with no fallback (block Phase 1 execution):**

- **Python 3.10+ on EC2** — must verify or upgrade before Apify code can run.
- **Apify API token + $100/mo cap set** — must exist before first scheduled run (operator step, D-06).

**Missing dependencies with fallback (operator setup tasks, do not block code work):**

- **Healthchecks.io URLs** — code can be deployed without them (the wrapper no-ops when env var is absent); HC.io alerts won't fire until provisioned.
- **`apify-client` install** — install during deploy, not a code-side blocker.

## Security Domain

### Applicable ASVS Categories (Level 1 per `.planning/config.json`)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Reuses existing `DASHBOARD_PASSWORD` cookie auth on `/admin/data-health` (gated by middleware on `(dashboard)` group). No new auth surface in Phase 1 |
| V3 Session Management | no | No new session surfaces |
| V4 Access Control | yes | `/admin/data-health` lives under `(dashboard)` route group → existing middleware enforces auth. No new role/permission surface |
| V5 Input Validation | yes | All user-facing input on this phase is via existing `?market=` query param (validated by `parseMarketParam()` in `src/lib/markets.ts`). New API surface (none in Phase 1) — Data Health page reads SQL directly via Drizzle (parameterized) |
| V6 Cryptography | yes | Use Python `secrets` for any token comparison if needed; reuse existing `crypto.timingSafeEqual()` if a new auth check appears (it doesn't in Phase 1) |
| V7 Error Handling & Logging | **yes — primary focus** | D-12 redaction filter (Pattern 5); fail-loud-not-silent for zero-result + timeout (Pitfalls 1, 4) |
| V9 Communications | yes | Apify HTTPS only (SDK default); HC.io HTTPS (`hc-ping.com`); reject http:// in any new outbound URL (use `isPublicHttpUrl()` if relevant) |
| V10 Malicious Code | no | No new untrusted code execution paths |
| V13 API & Web Service | yes | Reuses existing `/api/v1/*` middleware patterns if any new endpoint is added (none in Phase 1; Data Health is a server page, not an API route) |
| V14 Configuration | yes | All secrets in `.env.local`, never committed; redaction filter covers leaked-log scenarios |

### Known Threat Patterns for Phase 1 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API token leakage in logs (Apify, Anthropic, HC.io) | Information Disclosure | `SecretRedactionFilter` at root logger (D-12, Pattern 5); env vars + `.env.local` not committed; runbook for rotation |
| HC.io ping URL leakage allows fake "success" pings | Spoofing | Treat URLs as secrets; redaction filter `HEALTHCHECK_URL_` prefix scan; URLs only on EC2 + `.env.local`, never in repo |
| Apify cost runaway (denial of wallet) | Denial of Service (financial) | D-06 account-level cap; `max_total_charge_usd` per call; `timeout_secs` per run; `resultsLimit` cap on input |
| Silent zero-result success (data quality DoS) | Tampering / DoS-like | D-07 assertion; `change_events` zero-result row; Data Health page surfaces count |
| Hung scraper blocks pipeline | Denial of Service | D-11 `subprocess.run(timeout=1800)`; per-scraper isolation |
| Schema drift between Python migrations and Drizzle types | Tampering (data integrity) | D-15 same-PR rule; CI: `npx tsc --noEmit` |
| `printf`-style log injection (record values in log lines) | Tampering / Information Disclosure | Use parameterized log calls (`logger.info("got %s", value)`) not f-strings — this lets the redaction filter run on arguments before format. Existing scrapers use `print()` so this is greenfield discipline only |
| Cross-tenant data exposure via market filter bypass | Information Disclosure (low — internal tool) | Existing `parseMarketParam()` validates inputs; no new market-aware surface in Phase 1 |

**Phase 1 has no new authentication or authorization surface** beyond reusing the existing dashboard password gate via middleware on `(dashboard)` routes. Risk surface is dominated by V7 (logging/error handling) and V14 (configuration / secrets).

## Sources

### Primary (HIGH confidence)
- [apify-client PyPI page](https://pypi.org/project/apify-client/) — version 2.5.0, Python ≥3.10, release date 2026-02-18
- [Apify Python ActorClient.call() reference](https://docs.apify.com/api/client/python/reference/class/ActorClient) — `build`, `max_total_charge_usd`, `timeout_secs`, `memory_mbytes`, `run_input` parameters
- [Apify Python DatasetClient reference](https://docs.apify.com/api/client/python/reference/class/DatasetClient) — `get`, `list_items`, `iterate_items`, `get_statistics` methods
- [Apify Facebook Posts Scraper](https://apify.com/apify/facebook-posts-scraper) — pricing $2.00/1,000 posts, output schema, last modified 2026-05-01
- [Apify Dataset platform docs](https://docs.apify.com/platform/storage/dataset) — note that `itemCount` is not propagated immediately after push
- [Healthchecks.io signaling failures](https://healthchecks.io/docs/signaling_failures/) — `/start`, `/fail`, `/<exit_status>` URL suffixes
- [Healthchecks.io pricing](https://healthchecks.io/pricing/) — Hobbyist free tier: 20 checks, 100 log entries/check
- [Python subprocess.run docs](https://docs.python.org/3/library/subprocess.html#subprocess.run) — `timeout`, `TimeoutExpired`, automatic kill+wait
- [apify-client-python GitHub README](https://github.com/apify/apify-client-python) — usage example, current version
- `.planning/research/SUMMARY.md`, `STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `FEATURES.md` — milestone-level research
- `.planning/codebase/STRUCTURE.md`, `CONVENTIONS.md`, `TESTING.md` — codebase patterns
- `scrapers/db_utils.py`, `scrapers/social_scraper.py`, `scrapers/run_all.py`, `scrapers/config.py` — verified directly via Read
- `src/db/schema.ts`, `src/components/shared/empty-state.tsx`, `src/components/layout/stale-data-banner.tsx`, `src/app/(dashboard)/layout.tsx`, `src/lib/constants.ts` — verified directly via Read

### Secondary (MEDIUM confidence — verified against official docs)
- [Apify Python client overview](https://docs.apify.com/api/client/python/) — quick-start example
- [apify-client-python CHANGELOG](https://github.com/apify/apify-client-python/blob/master/CHANGELOG.md) — version history
- [Healthchecks.io monitoring cron jobs](https://healthchecks.io/docs/monitoring_cron_jobs/) — ping URL patterns

### Tertiary (LOW — needs validation at implementation time)
- Exact `apify/facebook-posts-scraper` build tag for pin (no public version-history page; Apify Console required)
- `ai_analyzer.py` symbol name for the existing extraction function (planner confirms by reading the file)
- Whether `run["usageTotalUsd"]` is fully settled at synchronous `.call()` return time (may need a re-fetch via `client.run(...).get()` after a short delay)

## Metadata

**Confidence breakdown:**
- Standard stack & schema deltas: **HIGH** — versions verified against PyPI/Apify Store/codebase ground truth on 2026-05-04; DDL grounded in existing `db_utils.py` migration pattern
- SDK call patterns: **HIGH** for `build`/`max_total_charge_usd`/`timeout_secs` (verified in ActorClient docs); **MEDIUM** for `run["usageTotalUsd"]` field shape (verified the field exists in v2 API but settlement timing on synchronous call uncertain)
- Healthchecks.io integration: **HIGH** — ping URL pattern, `/fail` suffix, free tier limits all verified
- `subprocess.run(timeout=)` pattern: **HIGH** — verified against Python docs
- Log redaction pattern: **HIGH** — standard `logging.Filter` subclass approach
- Pitfalls: **HIGH** — drawn from milestone PITFALLS.md which itself cites Apify/HC.io/community sources
- Competitor pick (`ic-markets`): **MEDIUM-HIGH** — supported by tier-1 status + canary-competitor reference in PITFALLS.md A3, but the planner should confirm FB page is active (2-min manual check)
- Actor version tag: **MEDIUM (LOW for the specific tag)** — the practice of pinning is verified; the specific tag must be confirmed in Apify Console at implementation time

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30 days for stable infrastructure pieces; Apify actor catalog and SDK versions can shift, so re-verify if planning slips past this date)

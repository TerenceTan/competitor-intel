# Architecture Research — APAC Localized Promo Intelligence v1

**Milestone:** Localized Promo Intelligence — APAC v1 (8 markets: SG, HK, TW, MY, TH, PH, ID, VN)
**Researched:** 2026-05-04
**Posture:** Brownfield architecture deltas. Existing system is mapped at `.planning/codebase/ARCHITECTURE.md` — this document only describes what NEW components do and where EXISTING components change.
**Confidence:** HIGH — recommendations are grounded in the existing two-layer scraper pattern, the additive-migration discipline already established in `scrapers/db_utils.py`, and the maintenance-mode constraint (mostly-solo support, primary attention on `marketing-portal`).

---

## Summary

The cleanest extension is **a Python-first, additive integration**: keep all new ingestion in `scrapers/` (Python), keep all new persistence in SQLite via `db_utils.get_db()`, and introduce **zero new languages, zero new orchestrators, and one new third-party SDK** (`apify-client` Python). Reuse the existing cron + `run_all.py` model rather than building a webhook-driven Node.js path.

Concretely:

1. **Apify** — Add `scrapers/apify_social.py` mirroring the structure of `scrapers/social_scraper.py`. Replace the Thunderbit `_thunderbit_extract()` call site with `apify-client` calls to FB/IG/X actors. Keep YouTube logic untouched. Continue writing through `db_utils.detect_change()` and `socialSnapshots`. Triggered synchronously by `run_all.py` (Apify SDK blocks on actor completion). No webhook surface added.
2. **BigQuery sync** — Add `scrapers/share_of_search_sync.py`, a third-party-data-only Python script using `google-cloud-bigquery`. Writes a single new table `share_of_search_snapshots`. Wired into `run_all.py` after `news_scraper` and before `ai_analyzer` so SoS lands in time for AI synthesis. New nightly cron entry.
3. **Schema** — Five additive migrations, all FK-safe and Postgres-portable: a new `share_of_search_snapshots` table, a new `apify_run_logs` table for actor diagnostics, and three additive columns on `promoSnapshots` (`source_run_id`, `extraction_confidence`, `language_detected`). Pattern follows the existing `ALTER TABLE ... ADD COLUMN` block in `db_utils.get_db()` lines 41–135.
4. **Market attribution** — Done at scrape time, **not** parse time. One Apify run per (competitor × platform × market) so the `market_code` column is set from caller context, not inferred from post content. This matches the existing per-market URL pattern in `competitors.market_config` (already DB-driven, see `db_utils.get_market_urls_from_db()`).
5. **Confidence/freshness** — A two-axis model. `freshness` is computed from `MAX(snapshotDate)` per (competitor, market, platform/domain) — exactly the pattern already used for the global "last updated" pill (`scraper_runs.finishedAt`). `confidence` is set at scrape time as `'high' | 'medium' | 'low'` and stored on the snapshot row. UI reads both via existing server pages.
6. **Build order** — Phase 1 (schema + Apify integration → restore social), Phase 2 (per-market scrape coverage for 8 APAC markets), Phase 3 (BigQuery SoS sync), Phase 4 (per-market AI promo recommendations), Phase 5 (confidence/freshness UX layer). Phases 1+3 and 4+5 are partially parallelizable; Phase 2 sequentially follows Phase 1.

---

## Apify Integration Placement

### Recommendation: Option (a) — Python script in `scrapers/`, invoked synchronously by cron

Add `scrapers/apify_social.py`. Use `apify-client` Python SDK (`pip install apify-client`). Run actors synchronously via `client.actor("apify/instagram-scraper").call(run_input=...)` which blocks until the actor finishes, then read results via `client.dataset(run["defaultDatasetId"]).iterate_items()`.

### Why not (b) Node.js apify-client

- The team's *only* existing scraper language is Python. Adding Node.js scraping introduces a second toolchain (`package.json` deps, build step, deployment surface) for one feature, in maintenance posture, with mostly-solo support. Direct violation of the "Maintenance burden" risk in `PROJECT.md`.
- All shared infrastructure — `db_utils.get_db()`, `detect_change()`, `log_scraper_run()`, `_noise_counters`, market config loaders — is Python. Rewriting this in TS to support a Node.js social scraper is significant non-feature work.
- The Drizzle ORM pattern is for *reads* at render time, not for batch writes. Mixing scraper writes through Drizzle means two write paths to one SQLite file with different migration assumptions. Bad.

### Why not (c) Webhook-triggered API route

- Adds an inbound webhook surface that needs hardening (auth, replay protection, signature verification). The codebase intentionally has *no* incoming webhooks today (`INTEGRATIONS.md` line 134: "None"). Introducing one for a single integration is poor cost/benefit.
- Apify async runs are pull-based by default and well-served by `client.actor(...).call()` synchronous mode. Webhooks are useful when actors run for hours; FB/IG/X scraping per-account is sub-minute.
- Forces a new failure surface (webhook delivery retries, idempotency tokens) for zero gain over a synchronous cron-driven script.

### File structure (concrete)

```
scrapers/
├── social_scraper.py              # EXISTING — keep YouTube path here, REMOVE Thunderbit call
├── apify_social.py                # NEW — FB/IG/X via Apify; same write path through db_utils
├── apify_client_helpers.py        # NEW (optional) — _run_actor(), _resolve_competitor_inputs()
├── db_utils.py                    # MODIFY — add migrations for new columns/tables
├── run_all.py                     # MODIFY — add "apify_social.py" and "share_of_search_sync.py" to SCRIPTS
└── ...
```

**Key design rule:** `apify_social.py` must use the same `log_scraper_run() / detect_change() / update_scraper_run()` triplet as every other scraper. The noise-floor counters (`_noise_counters`) and the `scraper_runs` row exist precisely so the admin page and stale-data banner work uniformly. No new logging path.

### Replacing Thunderbit specifically

In `scrapers/social_scraper.py` lines 125–165 (the `_thunderbit_extract()` function and its callers), the cleanest move is:

1. Move the YouTube path to its own file or keep it in `social_scraper.py` (cheap, working).
2. Delete the Thunderbit code path entirely (do not gate behind a feature flag — dead code is technical debt and Thunderbit is broken).
3. In `apify_social.py`, define platform-specific input builders that produce the actor input shape per Apify's docs (FB Pages scraper, IG Profile scraper, X User scraper actor IDs are stable, store in `apify_social.py` as constants).
4. Map actor output to the same dict shape that `socialSnapshots` expects: `{ "followers", "posts_last_7d", "engagement_rate", "latest_post_url" }`.
5. Set `market_code` from the caller's loop variable (one run per market — see Data Flow below).

Out-of-scope but worth noting: ScraperAPI fallback (`_fetch_via_scraperapi()` in `social_scraper.py`) is not blocked, but per `PROJECT.md` "stabilize the social fix first; widening sources before stabilizing fundamentals just compounds maintenance burden" — leave the fallback path alone in v1, or remove it if it's cleanly orphaned.

---

## BigQuery Sync Placement

### Recommendation: Option (a) — New Python script in `scrapers/`, separate cron entry

Add `scrapers/share_of_search_sync.py`. Use `google-cloud-bigquery` Python SDK. Pull last N days of SoS rows, upsert into a single new SQLite table.

### Why not (b) Node.js + Drizzle

Same reasoning as Apify: avoid second-language sprawl. Drizzle was chosen for typed *reads* at render time and is genuinely good there. Drizzle for batch ETL writes from BigQuery → SQLite is unnecessarily heavy and re-implements migrations the Python side already owns.

### Why not (c) Next.js API route triggered externally

- Triggering BQ sync via HTTP introduces auth concerns and removes the "everything cron does is one script per concern" mental model. Cron + run_all.py works; no need to wedge the API surface into ETL.
- API routes share process memory with the dashboard. A long-running BQ sync (rare, but possible on first backfill) blocks the event loop or competes with user requests.

### Minimum-surface-area integration

```
scrapers/
└── share_of_search_sync.py        # NEW
```

Wire-up:

1. Add `"share_of_search_sync.py"` to `run_all.py` `SCRIPTS` list — between `news_scraper.py` and `ai_analyzer.py` so SoS lands in the SQLite snapshot before AI synthesis runs.
2. Or, add a separate cron entry that runs only this script nightly. Single-script cron is fine because the script is idempotent (UPSERT by `(market_code, term, snapshot_date)`).
3. New env var: `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON). Add to EC2 systemd/PM2 env block. Document in `INTEGRATIONS.md` after milestone closes.
4. New Python dep in `scrapers/requirements.txt`: `google-cloud-bigquery`.

### What this script does (pseudocode)

```python
# scrapers/share_of_search_sync.py
from google.cloud import bigquery
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change

SCRAPER_NAME = "share_of_search_sync"

def main():
    run_id = log_scraper_run(SCRAPER_NAME, "running")
    try:
        bq = bigquery.Client()
        # Pull last 7 days of SoS data, partitioned by market
        query = """SELECT market, term, brand, share_of_search, captured_at
                   FROM `pepperstone-data.marketing.share_of_search`
                   WHERE captured_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)"""
        rows = bq.query(query).result()
        conn = get_db()
        records = 0
        for row in rows:
            conn.execute("""
                INSERT INTO share_of_search_snapshots
                  (market_code, term, brand, share_of_search, captured_at, snapshot_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (market_code, term, brand, captured_at) DO UPDATE SET
                  share_of_search = excluded.share_of_search,
                  snapshot_date = excluded.snapshot_date
            """, (row.market, row.term, row.brand, row.share_of_search,
                  row.captured_at.isoformat(), datetime.now(timezone.utc).isoformat()))
            records += 1
        conn.commit()
        update_scraper_run(run_id, "success", records=records)
    except Exception as e:
        update_scraper_run(run_id, "failed", error=str(e))
        raise
```

This treats SoS sync as just another scraper in the pipeline. Failures land in `scraper_runs` like everything else; the existing stale-data banner and admin page surface failures with no extra UI work.

---

## Schema Deltas

All deltas are **additive**, FK-safe, and use only types/idioms that translate cleanly to Postgres (`TEXT`, `INTEGER`, `REAL`, no SQLite-specific features). Migrations follow the existing pattern in `scrapers/db_utils.py` lines 41–135 (`ALTER TABLE ... ADD COLUMN` wrapped in try/except for idempotency).

### Delta 1: New table `share_of_search_snapshots`

```sql
CREATE TABLE IF NOT EXISTS share_of_search_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_code TEXT NOT NULL,
    term TEXT NOT NULL,
    brand TEXT NOT NULL,
    share_of_search REAL NOT NULL,
    captured_at TEXT NOT NULL,            -- BQ source timestamp (ISO 8601)
    snapshot_date TEXT NOT NULL,          -- when the sync wrote this row
    UNIQUE (market_code, term, brand, captured_at)
);

CREATE INDEX IF NOT EXISTS idx_sos_market_brand
    ON share_of_search_snapshots (market_code, brand);

CREATE INDEX IF NOT EXISTS idx_sos_market_captured
    ON share_of_search_snapshots (market_code, captured_at DESC);
```

**Why this shape:** No FK to `competitors` because BQ uses brand strings (`"pepperstone"`, `"ic markets"`) that may not always map 1:1 to `competitor_id`. The `brand` column is denormalized text; resolution to `competitor_id` happens at query time in the dashboard via a lookup table or `LIKE` join. This avoids breaking the sync when BQ data has a brand the competitors table doesn't know about.

### Delta 2: New table `apify_run_logs`

```sql
CREATE TABLE IF NOT EXISTS apify_run_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scraper_run_id INTEGER REFERENCES scraper_runs(id),
    competitor_id TEXT NOT NULL REFERENCES competitors(id),
    platform TEXT NOT NULL,              -- 'facebook' | 'instagram' | 'x'
    market_code TEXT NOT NULL,
    actor_id TEXT NOT NULL,              -- e.g. 'apify/instagram-profile-scraper'
    apify_run_id TEXT,                   -- Apify's run UUID for diagnostics
    status TEXT NOT NULL,                -- 'success' | 'failed' | 'empty'
    items_returned INTEGER DEFAULT 0,
    cost_usd REAL,                       -- Apify charges per run; useful for budget tracking
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_apify_runs_competitor_platform
    ON apify_run_logs (competitor_id, platform, market_code);
```

**Why this shape:** `scraper_runs` records *one* row per scraper invocation (e.g., one row for `apify_social` total). But Apify integration fans out to N actor runs (one per competitor × platform × market). To debug "why is IC Markets IG SG showing zero followers?" we need per-run diagnostics. This table answers that without bloating `scraper_runs`. Cost tracking helps the maintenance-burden risk by surfacing budget creep early.

### Delta 3: Additive columns on `promo_snapshots`

```sql
ALTER TABLE promo_snapshots ADD COLUMN source_run_id INTEGER;
-- Reference to scraper_runs.id; lets the dashboard trace which run produced this row
ALTER TABLE promo_snapshots ADD COLUMN extraction_confidence TEXT;
-- 'high' | 'medium' | 'low'; null for legacy rows. Computed at scrape time.
ALTER TABLE promo_snapshots ADD COLUMN language_detected TEXT;
-- ISO language code (e.g., 'en', 'th', 'vi'). Useful for non-English markets.
```

**Why these three:** They mirror the existing `leverage_confidence` / `leverage_sources_json` / `leverage_reconciliation_json` triple already on `pricing_snapshots` (see `schema.ts` lines 31–34). Same UX intent: give the marketer a "this number is high-confidence" signal. `source_run_id` is the cheap audit trail.

### Delta 4: Additive columns on `social_snapshots`

```sql
ALTER TABLE social_snapshots ADD COLUMN source_run_id INTEGER;
ALTER TABLE social_snapshots ADD COLUMN extraction_confidence TEXT;
ALTER TABLE social_snapshots ADD COLUMN apify_run_log_id INTEGER;
-- FK to apify_run_logs.id when source is Apify; null for YouTube path.
```

### Delta 5: Drop nothing, add nothing for confidence/freshness UX

Freshness is a derived value (computed in queries from `snapshotDate` and `scraper_runs.finishedAt`). No schema change needed for freshness — the UI already has all the data it needs. Confidence requires Deltas 3 and 4 above.

### Migration mechanics

All five deltas added to the existing `get_db()` function in `scrapers/db_utils.py` following the established try/except pattern. The `src/db/schema.ts` file gets updated to mirror the new columns/tables for Drizzle reads. Migration on Drizzle side is currently file-based; the addition of `source_run_id` etc. requires updating `schema.ts` only (Drizzle doesn't enforce existence at runtime, it relies on the schema you declare).

---

## Data Flow

### New scraper-side flow (per cron run)

```
cron
 │
 ▼
python scrapers/run_all.py
 │
 ├─→ pricing_scraper.py            (existing)
 ├─→ account_types_scraper.py      (existing)
 ├─→ promo_scraper.py              (MODIFY — add confidence/language fields)
 ├─→ social_scraper.py             (MODIFY — keep YouTube only, drop Thunderbit)
 ├─→ apify_social.py               (NEW)
 │     │
 │     │   for competitor in get_all_brokers():
 │     │     for market in competitor.markets_in_scope:
 │     │       for platform in ['facebook', 'instagram', 'x']:
 │     │         input = build_actor_input(competitor, market, platform)
 │     │         run = client.actor(ACTOR_IDS[platform]).call(run_input=input)
 │     │         items = client.dataset(run["defaultDatasetId"]).list_items()
 │     │         normalized = normalize_to_social_snapshot_shape(items)
 │     │         insert_social_snapshot(competitor.id, platform, market, normalized,
 │     │                                source_run_id=run_id,
 │     │                                extraction_confidence=score(items))
 │     │         log_apify_run(run, competitor, platform, market)
 │     ▼
 │   socialSnapshots (with market_code set from loop, not inferred)
 │   apify_run_logs  (per-actor-run diagnostics)
 │
 ├─→ reputation_scraper.py         (existing)
 ├─→ wikifx_scraper.py             (existing)
 ├─→ news_scraper.py               (existing)
 ├─→ share_of_search_sync.py       (NEW)
 │     │
 │     ▼
 │   share_of_search_snapshots
 │
 └─→ ai_analyzer.py                (MODIFY — read SoS + per-market promos for richer synthesis)
```

### New dashboard-side flow (per request)

```
User → /markets/sg
 │
 ▼
src/app/(dashboard)/markets/[code]/page.tsx
 │
 ├── parseMarketParam(params.code)  →  market = "sg"
 │
 ├── Promise.all([
 │     promosForMarket(market),                  // EXISTING + new confidence column read
 │     socialForMarket(market),                  // EXISTING + new confidence column read
 │     shareOfSearchForMarket(market),           // NEW query against share_of_search_snapshots
 │     latestScraperRunForFreshness(),           // EXISTING
 │     aiPromoRecsForMarket(market)              // NEW (Phase 4)
 │   ])
 │
 ▼
React render
 ├── <PromoTable data={promos} />                // EXISTING + new <ConfidenceBadge>
 ├── <SocialBarChart data={social} />            // EXISTING + new freshness pill
 ├── <ShareOfSearchPanel data={sos} />           // NEW component
 └── <AIPromoRecs data={recs} market={market} /> // NEW component
```

### Market attribution: scrape time, not parse time

The architectural call is to attribute market at scrape time (one Apify run per market). Reasons:

- **Source authority.** When you load `https://www.icmarkets.com/sg/en/` versus `https://www.icmarkets.com/global/en/`, you get different promo content. The market is a property of the *URL you fetched*, not of the *content you got back*. Inferring market from content (account name, language, regulatory disclaimers) is a guess; using the URL is ground truth.
- **Existing pattern alignment.** The codebase already does per-market scraping via `competitors.market_config` — see `db_utils.get_market_urls_from_db()` lines 344–360. The Apify integration should plug into this pattern, not invent a new one.
- **Cost tradeoff.** One Apify run per market across 8 markets × 3 platforms × N competitors *is* more expensive than one run per platform that infers market post-hoc. But: (a) per-market URLs often differ for FB Pages (e.g., `pepperstoneSG`, `pepperstoneAU`), (b) inference is brittle for tier-2 markets where competitors share a global page, (c) confidence/freshness becomes muddier when one row is "30% SG inferred, 40% generic, 30% other".
- **Postgres migration friendliness.** Per-row attribution remains atomic; no need for a `market_attributions_json` blob.

For competitors that genuinely have one global FB/IG/X account (no per-market presence), record one row with `market_code = 'global'` and let the per-market views fall back to global data via the same pattern already used in `pricing_snapshots`. The `competitor.market_config` JSON already supports this — no schema change needed.

---

## Confidence/Freshness Propagation

### Two-axis model

| Axis | Type | Source | Storage | UI |
|------|------|--------|---------|----|
| **Freshness** | Derived | `snapshotDate` column | Already on every snapshot table | "Updated 4h ago" pill |
| **Confidence** | Computed at scrape time | Scraper signal (parse success, source agreement, item count) | New `extraction_confidence TEXT` column | Coloured badge (green/amber/red) |

### Freshness — derive, don't store

Freshness is **always** computed from `MAX(snapshotDate)` within scope (per competitor, per market, per domain). This is exactly what `src/lib/utils.ts` `timeAgo()` already does for the global "last updated" pill.

```typescript
// Pattern (extends existing usage in src/components/layout/stale-data-banner.tsx)
const freshness = timeAgo(latestSnapshot.snapshotDate);
const stalenessClass = isStale(latestSnapshot.snapshotDate, expectedCadence)
  ? "text-amber-600"
  : "text-green-600";
```

The expected cadence per scraper already lives in `src/lib/constants.ts` `SCRAPERS` array — reuse the `cadenceHours` field with `STALE_MULTIPLIER` to flag stale-but-not-failed data.

### Confidence — compute at scrape time, store on row

Each scraper that produces snapshots in this milestone (`apify_social.py`, the modified `promo_scraper.py`) computes a confidence value at write time. Heuristics by scraper:

**Apify social:**
- `high`: actor returned items, all expected fields present, follower count > 0, run completed without retries.
- `medium`: actor returned items but some fields null, or run required retry, or follower count looks suspicious (e.g., dropped >50% from previous snapshot).
- `low`: actor returned empty dataset or run failed (no row written, or row written with the prior values plus `extraction_confidence='low'` and no `source_run_id` — design choice; lean toward "don't write a low row" to keep the freshness signal honest).

**Promo scraper:**
- `high`: AI extraction succeeded, language detected matches market expectation, ≥2 promos parsed.
- `medium`: AI extraction succeeded but lower item count, or language mismatch (e.g., market=th but language_detected=en — possible default-language fallback page).
- `low`: AI extraction returned empty or threw.

### UI propagation

```typescript
// New component, e.g. src/components/shared/confidence-badge.tsx
type Confidence = 'high' | 'medium' | 'low' | null;

export function ConfidenceBadge({ value }: { value: Confidence }) {
  if (!value) return null;  // Legacy rows show no badge
  const styles = {
    high:   'bg-green-100 text-green-800',
    medium: 'bg-amber-100 text-amber-800',
    low:    'bg-red-100 text-red-800',
  };
  const labels = { high: 'High confidence', medium: 'Some uncertainty', low: 'Low confidence' };
  return <span className={cn('px-2 py-0.5 rounded text-xs', styles[value])}>{labels[value]}</span>;
}
```

Mounted on:
- `<PromoTable>` row-level (per promo, since multiple promos can have different confidence per row).
- `<SocialBarChart>` series-level (per platform).
- `<ShareOfSearchPanel>` panel-level (BigQuery data is always high — it's our own data).

### Fail-soft default

For all legacy snapshot rows (pre-migration), `extraction_confidence` is `NULL`. The UI treats `NULL` as "no badge shown" — same as how `leverage_confidence` is handled today on the competitors page. No retroactive backfill needed.

---

## Build Order

The five active requirements in `PROJECT.md` map cleanly to five phases. Each phase is independently shippable (delivers stakeholder value) and each prior phase is a hard prerequisite for the next where indicated.

### Phase 1: Schema + Apify integration → restore broken social data

**Hard deliverable:** Working FB/IG/X data in the dashboard for at least the global market.

**Components touched:**
- `scrapers/db_utils.py` — add migrations for Deltas 1, 2, 4 (skip Delta 3 for now)
- `src/db/schema.ts` — mirror new columns
- `scrapers/apify_social.py` (NEW)
- `scrapers/social_scraper.py` (MODIFY — drop Thunderbit, keep YouTube)
- `scrapers/run_all.py` — add `apify_social.py` to `SCRIPTS`
- `scrapers/requirements.txt` — add `apify-client`
- `.env.local` and EC2 env — add `APIFY_API_TOKEN`

**Sequencing:** Schema migrations land first (additive, safe to deploy ahead of code that uses them). Apify code lands second.

**Validation:** Run `python scrapers/apify_social.py --broker pepperstone` (mirror the existing `--broker` arg pattern in `social_scraper.py`). Verify rows in `socialSnapshots` and `apify_run_logs`. Verify dashboard shows non-stale FB follower count.

**Dependencies:** None — this can start immediately.

### Phase 2: Per-market scrape coverage for 8 APAC markets

**Hard deliverable:** Per-market views (`/markets/sg`, `/markets/th`, etc.) show market-specific FB/IG/X data for each of the 8 v1 markets.

**Components touched:**
- `scrapers/market_config.py` — verify all 8 markets defined (likely already are; confirm)
- `competitors.market_config` JSON in DB — populate per-market FB/IG/X handles for each competitor in scope
- `scrapers/apify_social.py` — enable the per-market loop (was hardcoded to one market in Phase 1)
- `scrapers/promo_scraper.py` (MODIFY) — improve language-aware extraction for non-English markets

**Sequencing:** Hard prerequisite is Phase 1 (Apify must work end-to-end before fanning out). Market config research (which competitor has a real per-market FB page vs. shared global) is the long pole — needs human judgment, not code.

**Validation:** `/markets/th` shows TH-specific promos and TH-specific social data; `/markets/global` continues to work; no double-counting.

**Dependencies:** Phase 1 complete.

### Phase 3: BigQuery → SQLite Share of Search sync

**Hard deliverable:** Share of Search data joins with promo and social data per-market in the dashboard.

**Components touched:**
- `scrapers/db_utils.py` — add migration for Delta 1 (`share_of_search_snapshots`)
- `src/db/schema.ts` — mirror new table
- `scrapers/share_of_search_sync.py` (NEW)
- `scrapers/run_all.py` — add `share_of_search_sync.py` to `SCRIPTS`
- `scrapers/requirements.txt` — add `google-cloud-bigquery`
- EC2 — install `GOOGLE_APPLICATION_CREDENTIALS` JSON, env var, IAM role
- `src/app/(dashboard)/markets/[code]/page.tsx` — add `<ShareOfSearchPanel>` query and component

**Sequencing:** Independent of Phases 1–2. The data domains don't share code paths. Schema migrations and ETL script can land first; UI panel lands separately.

**Validation:** `share_of_search_snapshots` table populated nightly; `/markets/sg` panel shows SG SoS data correctly.

**Dependencies:** None on Phase 1–2; can run in parallel.

### Phase 4: Per-market AI promo recommendations

**Hard deliverable:** AI insights panel on each per-market page shows market-specific actionable recommendations.

**Components touched:**
- `scrapers/ai_analyzer.py` — add per-market synthesis loop, reading from per-market promo + social + SoS data
- `aiInsights` or new `aiInsightsPerMarket` table — TBD; if reusing existing table, add `market_code` column (additive)
- `src/app/(dashboard)/markets/[code]/page.tsx` — render market-specific insights

**Sequencing:** Soft prerequisite is Phase 3 (SoS data significantly enriches AI synthesis). Can technically ship without SoS but quality will be lower.

**Dependencies:** Phase 1 (need real social data); Phase 3 strongly recommended (SoS data improves AI output meaningfully).

### Phase 5: Confidence/freshness UX layer

**Hard deliverable:** Every dashboard panel showing scraper-derived data carries a confidence badge and freshness pill.

**Components touched:**
- `scrapers/db_utils.py` — add migration for Delta 3 (`promo_snapshots` confidence columns) if not yet shipped
- `scrapers/promo_scraper.py` and `apify_social.py` — populate `extraction_confidence` at write time
- `src/components/shared/confidence-badge.tsx` (NEW)
- `src/components/shared/freshness-pill.tsx` (NEW or extension of existing `<TimeAgo>`)
- All per-market dashboard pages and panels — add badges/pills

**Sequencing:** This is a UX polish phase but `PROJECT.md` Key Decisions list it as "in v1, not deferred" because data quality risk is the top milestone risk. It can ship in parallel with Phase 4 if scope allows.

**Dependencies:** Phases 1–3 (need real, market-attributed data to put confidence/freshness on).

---

## Parallelization

### Sequential constraints

```
Phase 1 → Phase 2  (must be sequential; per-market fanout requires working integration)
Phase 1 → Phase 4  (must be sequential; AI synthesis needs real social data)
Phase 1 → Phase 5  (must be sequential; confidence badges need confidence data)
```

### Parallelizable work

```
Phase 1  ───┐
            ├─→ ship social-restored MVP (8 markets to global)
Phase 3  ───┤
            ├─→ ship SoS panel (independent data domain)
            │
Phase 1 → Phase 2 → Phase 4 ─┐
                              ├─→ ship per-market AI recs
              Phase 3 ────────┘
                              │
                Phase 5 ──────┴─→ ship confidence/freshness UX
```

**In a one-engineer / mostly-solo support model**, parallelization opportunities are limited but real:

1. **Phase 1 schema delta + Phase 3 schema delta land in one PR.** Both are additive `db_utils.py` migrations; deploy together to amortize the EC2 deploy cycle.
2. **Phase 3 ETL script can be drafted alongside Phase 1 Apify code.** Different files, no shared state. Code review them as one batch.
3. **Phase 4 prompts and Phase 5 components can be designed (but not built) in parallel with Phase 2.** Designing the AI prompt and the confidence badge while waiting for Phase 2 data validation reduces critical-path time.

### What must NOT be parallelized

- **Drizzle schema in `src/db/schema.ts` must lag the Python migration in `db_utils.py`.** Drizzle types are read at compile time; if the schema declares columns that don't exist yet in the running DB, queries fail at runtime. Always: Python migration first → deploy → then Drizzle schema update → deploy.
- **`run_all.py` SCRIPTS list updates must lag the new scraper files landing.** Otherwise cron tries to run a missing file.
- **Apify actor selection should not happen in parallel with code.** Pick the actor (free vs. paid, FB Pages Scraper vs. FB Page Scraper Lite, etc.) before writing the code that calls it. Apify's actor catalog churns — locking the actor IDs is a small upfront task with big downstream stability impact.

### Suggested critical path (~3–4 weeks for a focused solo engineer)

```
Week 1: Phase 1 schema + Apify integration + replace Thunderbit (global market)
Week 2: Phase 1 hardening + Phase 2 per-market fanout for 4 markets (SG, TH, MY, ID)
Week 3: Phase 2 remaining markets (HK, TW, PH, VN) + Phase 3 BQ sync (parallel)
Week 4: Phase 4 per-market AI + Phase 5 confidence/freshness UX (parallel)
```

This fits the "Medium milestone (3–6 weeks, 3–5 phases)" timeline in `PROJECT.md` constraints with some slack for the Apify actor surprises that will inevitably surface.

---

## Sources

- `.planning/codebase/ARCHITECTURE.md` — existing two-layer scraper pattern, force-dynamic rendering, market-aware filtering pattern (HIGH confidence — codebase ground truth)
- `.planning/codebase/STRUCTURE.md` — directory layout, "Where to Add New Code" conventions (HIGH)
- `.planning/codebase/INTEGRATIONS.md` — current Thunderbit/ScraperAPI integration shape, env var patterns (HIGH)
- `.planning/codebase/CONVENTIONS.md` — Python snake_case, additive migrations, error handling patterns (HIGH)
- `.planning/PROJECT.md` — milestone scope, validated baseline, key decisions, risks (HIGH)
- `scrapers/db_utils.py` lines 41–135 — existing additive migration pattern that all new schema deltas mirror (HIGH)
- `scrapers/social_scraper.py` lines 125–165 — Thunderbit call site to be replaced (HIGH)
- `src/db/schema.ts` — existing snapshot tables and confidence-column precedent on `pricing_snapshots` (HIGH)
- Apify Python client docs (`apify-client` PyPI) — synchronous `client.actor().call()` pattern used in recommendation (MEDIUM — not verified against current Apify SDK version in this research; verify at Phase 1 implementation time)
- Google Cloud BigQuery Python client docs — standard `bigquery.Client().query().result()` pattern (MEDIUM — verify SDK version against EC2 Python at Phase 3 implementation time)

---

*Architecture research for: APAC Localized Promo Intelligence v1*
*Researched: 2026-05-04*

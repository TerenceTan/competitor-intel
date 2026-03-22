# Changelog

All notable changes to the Competitor Analysis Dashboard.

---

## [Unreleased] — 2026-03-22 (Session 6: Pricing Scraper — WikiFX Leverage + Type Fixes)

### Fixed

- **WikiFX leverage not extracted** — `scrapers/pricing_scraper.py`
  Added `_parse_leverage_value()` helper that handles all common leverage formats (`1:500`, `500:1`, plain `500`, `x500`). WikiFX enrichment now also falls back to a full page-text scan when no account table is found, catching leverage data in non-table HTML layouts.

- **Pyre2 type errors** — `scrapers/pricing_scraper.py`
  Annotated `result` dict as `dict[str, object]` to resolve bad-argument-type errors on `min_deposit_usd` and `instruments_count` assignments. Added explicit `status: int` / `html: str` annotations to unpack from `_fetch()` return value. Added `# type: ignore[import]` to dynamic `sys.path` imports (`playwright`, `config`, `db_utils`, `wikifx_scraper`) which are valid at runtime but unresolvable by Pyre2 static analysis.

- **Pepperstone account types incorrect in DB** — `scrapers/pricing_scraper.py`, `scrapers/config.py`
  Added `"Razor"` and `"Razor+"` to the known account type list in `_extract_account_types()`. Added `known_leverage` and `known_account_types` authoritative override fields to `PEPPERSTONE_CONFIG` (`["1:200", "1:1000"]` and `["Razor", "Standard"]` respectively). These config values now always override scraped results so stale/incorrect extractions are never persisted. Existing DB rows were patched directly.

---

## [Unreleased] — 2026-03-19 (Session 5: Security Hardening + QA Audit)

### Security — Fixed

- **Weak session token (critical)** — `src/middleware.ts`, `src/app/api/auth/login/route.ts`
  Replaced reversible Java-style bitwise `simpleHash()` with SHA-256 via Node.js `node:crypto`. Added `export const runtime = "nodejs"` to middleware.

- **Hardcoded password fallback (critical)** — `src/middleware.ts`, `src/app/api/auth/login/route.ts`
  Removed `|| "pepperstone2026"` default. Server now returns HTTP 503 if `DASHBOARD_PASSWORD` is not set, rather than falling back to a known public password.

- **Unprotected admin API route (critical)** — `src/app/api/admin/run-scraper/route.ts`
  Added `isAuthenticated()` check using the SHA-256 cookie. Route previously had no auth — any caller could trigger scraper runs.

- **Missing security headers** — `next.config.js`
  Added `async headers()` block with: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.

- **NULL-unsafe `is_self` filter** — `src/app/api/competitors/route.ts`, `src/app/api/changes/route.ts`
  Changed `ne(isSelf, 1)` to `or(eq(isSelf, 0), isNull(isSelf))` to correctly handle pre-migration rows where the column may be NULL.

- **Pepperstone changes visible in change feed** — `src/app/api/changes/route.ts`
  Added `ne(competitorId, "pepperstone")` filter so Pepperstone's own change events are excluded from the `/changes` UI.

- **NULL backfill in migration** — `src/db/migrate.ts`
  Added `UPDATE competitors SET is_self = 0 WHERE is_self IS NULL` and `UPDATE competitors SET is_self = 1 WHERE id = 'pepperstone'` to handle databases upgraded from older schema versions.

---

## [Unreleased] — 2026-03-19 (Session 4: Pepperstone Self-Benchmark + Crawler Blocking + UI)

### Added

- **Pepperstone self-benchmark scraping** — `scrapers/config.py`
  Added `PEPPERSTONE_CONFIG` dict with full scraping config (Trustpilot, FPA, MyFXBook, pricing, promos, social). Added `ALL_BROKERS = COMPETITORS + [PEPPERSTONE_CONFIG]` list. All 6 scrapers now import `ALL_BROKERS as COMPETITORS` so Pepperstone is scraped on every run.

- **`is_self` DB flag** — `scrapers/db_utils.py`, `src/db/schema.ts`, `src/db/migrate.ts`, `src/db/seed.ts`
  New `is_self INTEGER DEFAULT 0` column on `competitors` table. Pepperstone is seeded with `is_self = 1`. `get_db()` runs the additive `ALTER TABLE` migration and `INSERT OR IGNORE` for the Pepperstone row on every DB open — fully idempotent.

- **Pepperstone filtered from all UI and API** — `src/app/api/competitors/route.ts`, `src/app/api/changes/route.ts`
  Both routes filter `is_self` so Pepperstone never appears in the dashboard competitor list or change feed.

- **Live Pepperstone context in AI prompts** — `scrapers/ai_analyzer.py`
  Added `get_pepperstone_snapshot(conn)` and `build_pepperstone_context(snap)`. Both `build_prompt()` and `build_portfolio_prompt()` now receive a `pepperstone_context` parameter populated with live scraped data (pricing, Trustpilot, FPA, App Store, MyFXBook ratings). Falls back gracefully to static description if no data has been scraped yet.

- **Pepperstone excluded from change analysis** — `scrapers/ai_analyzer.py`
  `fetch_todays_changes()` now JOINs `competitors` and filters `is_self = 0`, so Pepperstone's own metric changes are never analysed as competitive threats.

- **`robots.txt`** — `public/robots.txt`
  Created with `Disallow: /` for all crawlers plus explicit named blocks for: GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, anthropic-ai, Google-Extended, CCBot, Omgilibot, FacebookBot, Bytespider, Amazonbot, PerplexityBot.

- **`noindex` / `nofollow`** — `src/app/layout.tsx`
  Added `robots: { index: false, follow: false, googleBot: { index: false, follow: false } }` to global metadata so every page emits the appropriate meta tags.

- **Scraper anonymisation** — `scrapers/config.py`, all scrapers
  Added `SCRAPER_UA` and `SCRAPER_HEADERS` constants. All Playwright browser contexts now reference `SCRAPER_UA` (single source of truth instead of inline strings). `wikifx_scraper.py` std_requests fallback now includes `User-Agent`. `news_scraper.py` replaced `"CompetitorIntelBot/1.0; +https://techaway.online"` with generic Chrome UA.

- **Recommended Actions styling** — `src/app/(dashboard)/page.tsx`
  Sequential `01`/`02`/… numbering across all urgency groups. Urgency group headers now show an icon (`AlertCircle` / `Clock` / `Calendar`) and action count pill (e.g. "3 actions"). Cards have increased padding, shadow, and italic rationale text with a left border for visual hierarchy. Summary block is now italicised with a left accent border.

### Fixed

- **Webshare proxy for MyFXBook** — `scrapers/reputation_scraper.py`
  Added `elif webshare_proxy:` branch between ScraperAPI and curl-cffi. Reads `WEBSHARE_PROXY_URL` env var. No new dependencies — uses existing `requests` library.

---

## [Unreleased] — 2026-03-17 (Session 3: Data Quality Fixes + Admin UX)

## [Unreleased] — 2026-03-17 (Session 3: Data Quality Fixes + Admin UX)

### Added

- **Multi-entity reputation config** — `scrapers/config.py`
  Each competitor now has an `entities` array with `trustpilot_slug`, `fpa_slug`, `ios_app_id`, and `android_package` fields. IC Markets is configured with two entities (Global and EU). XM Group corrected to use `trading-point.com` as its Trustpilot slug. All brokers have `pricing_wait_selector: None` as a new optional config field.

- **Multi-entity reputation scraping** — `scrapers/reputation_scraper.py`
  Full rewrite. Now iterates through `entities` per competitor instead of using the `website` field for all lookups. App Store uses direct iTunes lookup API (`/lookup?id=`) when `ios_app_id` is set; falls back to name search. Google Play fetches the direct app page (`/store/apps/details?id=`) when `android_package` is set; falls back to search. Determines the "primary" entity by highest Trustpilot review count, promotes its scores to the top-level columns, and writes the full per-entity breakdown to `entities_breakdown_json`.

- **`entities_breakdown_json` DB column** — `src/db/schema.ts`, `src/db/migrate.ts`
  New `entities_breakdown_json TEXT` column on `reputation_snapshots`. Schema updated in Drizzle; `runMigrations()` runs a catch-ignored `ALTER TABLE` so existing databases are upgraded on next app start without manual intervention.

- **Entity Breakdown table** — `src/app/(dashboard)/competitors/[id]/page.tsx`
  Reputation tab now renders an Entity Breakdown card (table showing Trustpilot score+count, FPA, App Store, Google Play per entity) when `entitiesBreakdownJson` contains more than one entity. Single-entity competitors are unaffected.

- **Claude API + MyFXBook promotion extraction** — `scrapers/promo_scraper.py`
  Full rewrite of `_extract_promos_generic()`. Now runs a three-step pipeline: (A) pre-fetch MyFXBook forex broker promotions page once per run using Playwright + a single Claude API call to extract all broker promos as structured JSON; (B) per-competitor page scrape + Claude API extraction with a strict prompt that rejects generic product content; (C) merge MyFXBook promos with competitor-scraped promos, deduplicating by ≥80% word-overlap on title. Uses `claude-haiku-4-5-20251001` for speed and cost. Gracefully degrades to empty results if `ANTHROPIC_API_KEY` is unset. Shares `.env.local` loading pattern with `ai_analyzer.py`.

- **Pricing extraction guard** — `scrapers/pricing_scraper.py`
  After scraping, checks `has_data` (any of `min_deposit_usd`, `leverage`, `account_types`, `instruments_count` non-empty) before executing DELETE + INSERT. If empty, logs `⚠ {name}: no pricing data extracted — preserving existing record` and skips the upsert, protecting previously scraped data from being overwritten with nulls.

- **Improved Playwright wait for pricing** — `scrapers/pricing_scraper.py`
  Changed `wait_until` from `"domcontentloaded"` to `"networkidle"` and added `asyncio.sleep(3)` after navigation. Supports optional `pricing_wait_selector` per competitor in `config.py` — if set, waits for that CSS selector (10 s timeout, best-effort) before extracting body text.

- **"Run All Scrapers" button** — `src/components/admin/scraper-table.tsx`
  Added a header bar inside the `<Card>` above the scraper table. Right-aligned "Run All Scrapers" button calls `handleRun("all")` (the API already maps `"all"` to `run_all.py`). Button disables with "Running all…" label while running; re-enables after the standard 2 s refresh delay.

---

## [Unreleased] — 2026-03-17 (Session 2: QA Round 2 Bug Fixes)

### Fixed

#### Frontend

- **Admin scraper name mismatch (critical)** — `src/app/(dashboard)/admin/page.tsx`
  Added `dbName` field to each entry in the `SCRAPERS` array, mapping dash-format display names to the underscore-format names stored in the DB (e.g. `"pricing-scraper"` → `"pricing_scraper"`). The admin page was previously always showing "Never run" for all scrapers.

- **Admin scraper table key lookup (critical)** — `src/components/admin/scraper-table.tsx`
  Updated `Scraper` interface to include `dbName: string`. `ScraperTable` now looks up `latestRunMap[scraper.dbName]` instead of `latestRunMap[scraper.name]` to correctly find prior runs.

- **Admin table static time display (high)** — `src/components/admin/scraper-table.tsx`
  Replaced `timeAgo(run.startedAt)` (static SSR string) with `<TimeAgo dateStr={run.startedAt} />` client component so the relative time updates live in the browser. Updated import accordingly.

- **Layout "Last updated" shows render time (high)** — `src/app/(dashboard)/layout.tsx`
  Replaced `new Date()` (current render time) with a DB query for the most recent `finishedAt` across all `scraperRuns`. Falls back to "—" if no runs exist. Added import of `scraperRuns` schema and `desc` from drizzle-orm.

- **`aiInsights` query non-deterministic ordering (high)** — `src/app/(dashboard)/page.tsx`
  Added `desc(aiInsights.id)` as tiebreaker sort to the top-insights query.

- **`aiInsights` query non-deterministic ordering (high)** — `src/app/(dashboard)/competitors/[id]/page.tsx`
  Added `desc(aiInsights.id)` as tiebreaker sort to the latest-insight query.

- **Unlimited `changeEvents` query (high)** — `src/app/(dashboard)/competitors/[id]/page.tsx`
  Added `.limit(50)` to the `changeEvents` query for competitor detail pages, preventing unbounded memory use for active competitors.

#### Python Scrapers

- **Naive datetimes in `db_utils.py` (critical)** — `scrapers/db_utils.py`
  Added `timezone` to `datetime` import. Replaced all `datetime.utcnow().isoformat()` calls with `datetime.now(timezone.utc).isoformat()` so `started_at` and `finished_at` columns in `scraper_runs` are timezone-aware.

- **Naive datetime for `snapshot_date` (critical)** — `scrapers/pricing_scraper.py`
  Added `timezone` to `datetime` import. Replaced `datetime.utcnow().strftime(...)` with `datetime.now(timezone.utc).strftime(...)`.

- **`INSERT OR REPLACE` without UNIQUE constraint (critical)** — `scrapers/pricing_scraper.py`
  Replaced `INSERT OR REPLACE INTO pricing_snapshots` with a DELETE + INSERT pattern (matching the approach already used in `promo_scraper.py` and `social_scraper.py`). Prevents seed data from persisting and scraped data from appending instead of replacing.

- **Naive datetime for `snapshot_date` (critical)** — `scrapers/promo_scraper.py`
  Added `timezone` to `datetime` import. Replaced `datetime.utcnow().strftime(...)` with `datetime.now(timezone.utc).strftime(...)`.

- **Naive datetime for `snapshot_date` (critical)** — `scrapers/reputation_scraper.py`
  Added `timezone` to `datetime` import. Replaced `datetime.utcnow().strftime(...)` with `datetime.now(timezone.utc).strftime(...)`.

- **Naive datetime for `generated_at` (critical)** — `scrapers/ai_analyzer.py`
  Replaced `datetime.utcnow().isoformat()` with `datetime.now(timezone.utc).isoformat()` (`timezone` was already imported).

- **Naive datetime for `snapshot_date` (critical)** — `scrapers/social_scraper.py`
  Replaced `datetime.utcnow().strftime(...)` with `datetime.now(timezone.utc).strftime(...)` (`timezone` was already imported).

- **Blocking `time.sleep()` in async context (medium)** — `scrapers/social_scraper.py`
  Replaced `time.sleep(DELAY_BETWEEN_REQUESTS)` in the YouTube async scrape loop with `await asyncio.sleep(DELAY_BETWEEN_REQUESTS)` to avoid blocking the event loop.

### Added

- `docs/QA_REPORT.md` — Consolidated QA findings from Rounds 1 and 2, including severity, description, and fix applied for each issue.
- `CHANGELOG.md` — This file.

---

## [Initial] — 2026-03-17 (Session 1: Initial Build)

### Added

- Next.js 15 app with App Router, Tailwind CSS, shadcn/ui components
- SQLite database via Drizzle ORM with schema for: `competitors`, `pricing_snapshots`, `promo_snapshots`, `social_snapshots`, `reputation_snapshots`, `news_items`, `change_events`, `ai_insights`, `scraper_runs`
- Dashboard pages: Executive Summary, Competitor Detail (with tabbed view), Admin Panel
- Python scrapers: `pricing_scraper.py`, `promo_scraper.py`, `social_scraper.py`, `reputation_scraper.py`, `news_scraper.py`, `ai_analyzer.py`
- Shared scraper utilities: `db_utils.py`, `config.py`
- Login page with session-based auth middleware
- `<TimeAgo>` live-updating client component (`src/components/ui/time-ago.tsx`)
- Sidebar navigation with competitor count
- Admin run-scraper API route (`/api/admin/run-scraper`)

# Changelog

All notable changes to the Competitor Analysis Dashboard.

---

## [Unreleased] — Phase 1 + Phase 2 Apify cutover (2026-05-04 → 2026-05-05)

### Added

- **Apify FB scraper for ic-markets** (`scrapers/apify_social.py`) replacing the broken Thunderbit FB code path (D-01). Pinned actor build `0.0.293`, `apify_run_logs` diagnostics table, zero-result silent-success guard, `extraction_confidence` per snapshot.
- **Phase 2 Apify cutover for IG + X across all 11 competitors.** Same `apify_social.py` now batches three actor calls per run:
  - `apify/instagram-profile-scraper` for follower counts
  - `kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest` (with mock-data detection)
  - `apify/facebook-posts-scraper` (5 posts/page) for activity signal
  Total cost ~$0.36/run, ~$1.46/mo at weekly cadence — fits in Apify free tier ($5/mo platform credit).
- **Schema deltas (Plan 01-01):** `apify_run_logs` table, `share_of_search_snapshots` table, `extraction_confidence` column on social/promo/pricing snapshot tables.
- **Trust UX skeleton (Plan 01-05):** `<EmptyState reason="scraper-failed">` variant + `/admin/data-health` page surfacing per-actor zero-result counts.
- **Operational hardening (Plan 01-04):** per-scraper 30-min subprocess timeout in `run_all.py` + Healthchecks.io ping helper. 9 HC.io checks provisioned + cron block in `SCRAPER_SCHEDULE.md`. `run_all.py` now accepts a single-script CLI arg so per-cadence cron entries route through the same orchestrator and inherit ping coverage.
- **Log redaction filter** (`scrapers/log_redaction.py`) attached to root logger; Apify SDK Authorization headers stripped before reaching log files (April 2026 EC2 incident anchor).
- **Calibration validator** (`scrapers/calibration/validate_extraction.py`) + JSONL skeleton for TH/VN/TW/HK/ID promo extraction (EXTRACT-05).

### Changed

- `social_scraper.py` is now **YouTube-only** (Google Data API). Instagram and X paths removed — Thunderbit account exhausted (HTTP 402 INSUFFICIENT_CREDITS), ScraperAPI HTTP 403'd on both. All three platforms now flow through Apify.
- `/admin/data-health` `APIFY_MONTHLY_CAP_USD` constant updated to `5` (free-tier reality, was `100` per D-06's paid-tier assumption).
- Dashboard `/admin` Run-Scraper API now uses `.venv/bin/python` (PEP-668 / venv-only `apify_client`) and routes through `run_all.py` so manual UI-triggered runs inherit HC.io ping + INFRA-02 timeout.

### Marketing-portal integration *(action required)*

The new social-platform data lives in `social_snapshots` rows but is **not yet exposed via `/api/v1/*`** — only `/api/v1/promotions` and `/api/v1/trends` are public. To consume IG/X/FB follower counts from marketing-portal, add `/api/v1/social-snapshots/route.ts` modeled on the existing `/api/v1/promotions` pattern (auth, rate-limit, query params already handled in `middleware.ts`). Counts as one of the four missing routes from the in-flight cutover.

---

## [1.4.1] — 2026-04-15

### Security

- **Patched 8 npm advisories** via `npm audit fix` — Next.js (critical cache-key confusion, RCE in RSC flight protocol, SSRF via middleware redirects, multiple DoS vectors), drizzle-orm SQL injection via identifier escaping, path-to-regexp / picomatch ReDoS, flatted prototype pollution, brace-expansion hang, hono/@hono/node-server bypasses. Remaining 4 advisories are dev-only in the `drizzle-kit` → `esbuild` chain and do not ship to production.

- **SSRF hardening in admin auto-discovery** — `fetchHtml()` in `src/app/(dashboard)/admin/actions.ts` now rejects non-HTTP(S) schemes, loopback (`127.0.0.0/8`, `::1`), link-local metadata (`169.254.0.0/16`, including the `169.254.169.254` cloud metadata endpoint), and RFC1918 private ranges before issuing any outbound request. `redirect: "manual"` prevents a public URL from silently redirecting into an internal host.

- **Rate limiting on `/api/v1/*`** — 60 requests/minute per Bearer token (fallback: client IP) via an in-memory fixed-window limiter in `middleware.ts`. Returns `429` with `Retry-After` and `X-RateLimit-*` headers. Moves a leaked API key from "free DoS against the scraper DB" to a bounded, debuggable problem.

- **Pinned Python scraper dependencies** — `scrapers/requirements.txt` now uses exact `==` versions for `anthropic`, `requests`, and `python-dotenv`. Eliminates supply-chain drift between EC2 and local environments on nightly cron runs.

---

## [1.4.0] — 2026-04-15

### Added

- **Thunderbit AI extraction for social scraper** — Facebook, Instagram, and X now use Thunderbit's structured AI extraction as the primary method, with ScraperAPI regex as automatic fallback. Richer data: `posts_last_7d` and `posts_count` now populated for FB/IG/X (previously always NULL). Retry logic with backoff (2 attempts, 5s delay) for Thunderbit API calls.

- **`/api/v1/trends` endpoint** — aggregated market intelligence (promo activity, spread direction, reputation moves, AI morning brief) without exposing competitor names. Query params: `days` (1–90) and `market` filter.

- **API documentation** — `docs/API_GUIDE.md` covering `/api/v1/promotions` and `/api/v1/trends` endpoints, authentication, competitor IDs, market codes.

### Fixed

- **Morning brief bullet splitting** — handles abbreviations (e.g. "vs.", "e.g.") and inline `(N)` numbered patterns without false sentence breaks.

- **Empty recommended actions** — AI analyzer `fetch_todays_changes()` switched from calendar-day `LIKE` match to rolling 24h window, fixing missed changes when `run_all.py` straddles midnight UTC. Added 20h deduplication guard to prevent duplicate portfolio insights.

- **Account types junk change events** — widened `_JUNK_PATTERNS` regex to catch trailing text from Claude extraction artifacts. Added junk-to-junk skip so replacing one junk value with another no longer triggers a change event.

- **Account types name flip-flopping** — improved Claude prompt to prefer product names over marketing tiers, added `EXPECTED_ACCOUNTS` name remapping, and 7-day cooldown on change detection to prevent Vantage-style oscillation between "Standard STP" and "Novice Traders".

### Changed

- Social scraper now accepts optional `THUNDERBIT_API_KEY` env var. Without it, behaviour is unchanged (ScraperAPI regex only).

---

## [1.3.0] — 2026-04-10

### Added

- **Noise filtering** — configurable per-domain thresholds (`scrapers/change_thresholds.py`) with percentage and absolute min-delta guards to suppress insignificant change events.

- **Stale-data banner** — top-of-dashboard warning when any scraper data is older than its expected refresh cadence.

- **Pepperstone self-scraping** — removed `is_self` skips so Pepperstone is scraped alongside competitors for benchmarking.

- **KPI sparklines** — 7-day historical trending sparklines on the executive summary KPI row.

- **External API v1** — Bearer token authentication middleware, `/api/v1/promotions` endpoint.

- **Reputation scraper cadence** — reduced from daily to 3-day to match Trustpilot update frequency.

---

## [1.2.0] — 2026-04-03

### Added

- **Admin UI for competitor management** — `src/app/(dashboard)/admin/page.tsx`, `src/components/admin/competitor-table.tsx`, `src/components/admin/competitor-form.tsx`, `src/app/(dashboard)/admin/actions.ts`
  Replaced the read-only competitor config table with a full CRUD interface. "Add Competitor" button opens a dialog with a 2-step Smart Add flow: Step 1 asks for name + website only, then auto-detects URLs, social handles, WikiFX ID, app store IDs, and Trustpilot slug by scraping the broker homepage and searching external platforms. Step 2 shows a pre-filled review form with green highlights on auto-discovered fields. Edit (pencil icon) and Delete (trash icon with confirmation) actions per row. Key-based remount pattern ensures form state resets correctly when switching between competitors.

- **DB-driven competitor config** — `src/db/schema.ts`, `src/db/migrate.ts`, `scrapers/db_utils.py`
  Added `scraper_config TEXT` and `market_config TEXT` JSON columns to the `competitors` table. All scraper metadata (URLs, social handles, entities, research slugs) is now stored in the DB instead of hardcoded in `config.py`. Added `get_all_brokers()` and `get_market_urls_from_db()` helper functions to `db_utils.py` that reconstruct the same dict shape scrapers expect.

- **Scraper cutover to DB config** — all 8 scrapers + `ai_analyzer.py`
  All scrapers now import `get_all_brokers()` from `db_utils` instead of `ALL_BROKERS` from `config.py`. `market_config.py` reads from DB first with fallback to hardcoded URLs. `config.py` retained for global settings (`DELAY_BETWEEN_REQUESTS`, `SCRAPER_UA`, `SCRAPER_HEADERS`).

- **Auto-discovery server action** — `src/app/(dashboard)/admin/actions.ts`
  `discoverCompetitorConfig()` fetches the broker homepage to extract social links (Facebook, Instagram, X, YouTube) and key page URLs (pricing, promotions, account types) from HTML. Searches iTunes API for iOS app ID and Android package. Searches WikiFX for broker ID. Generates Trustpilot and research slugs from domain/name.

- **Backfill script** — `scrapers/backfill_config_to_db.py`
  One-time script that reads existing hardcoded config from `config.py` and `market_config.py`, serializes to JSON, and writes to the `scraper_config` and `market_config` DB columns for all 11 competitors.

- **Market-level localisation** — `scrapers/market_config.py`, `src/app/(dashboard)/markets/[code]/page.tsx`, `src/app/(dashboard)/markets/page.tsx`
  Added `market_code TEXT NOT NULL DEFAULT 'global'` column to 4 snapshot tables. 9 priority APAC markets (SG, MY, TH, VN, ID, HK, TW, CN, MN) with per-competitor URL overrides. Market detail page shows market-specific data with global fallback, data source badges, leverage bars, KPI cards, collapsible account types accordion, and recent changes feed. Markets index shows coverage indicators per market.

- **Collapsible account types accordion** — `src/components/shared/account-accordion.tsx`
  Replaced inline account type cards on market detail page with a collapsible accordion. Each competitor row is collapsed by default showing account count; expands to a table with Account, Min Deposit, Leverage, Spread, and Commission columns.

### Fixed

- **"Unable to determine" junk values in account data** — `src/app/(dashboard)/markets/[code]/page.tsx`
  Added `sanitiseAccounts()` that regex-matches "Unable to determine", "Not available", "Not specified", and "N/A" strings and converts them to null (displayed as "—"). Affects Exness and FxPro data.

- **MiniKpi divide-by-zero** — `src/app/(dashboard)/markets/[code]/page.tsx`
  Added `totalCompetitors > 0` guard before division in coverage color calculation.

- **LeverageBar negative value** — `src/app/(dashboard)/markets/[code]/page.tsx`
  Added `Math.max(..., 0)` to clamp percentage at 0 minimum.

- **Market code input validation** — `src/app/(dashboard)/markets/[code]/page.tsx`
  Added regex allowlist (`/^[a-z]{2,5}$/`) that rejects malformed route params before any DB query.

- **Competitor form stale state on edit** — `src/components/admin/competitor-form.tsx`
  Extracted inner form to `CompetitorFormInner` with key-based remount so clicking Edit on different competitors correctly resets all form fields.

---

## [1.1.0] — 2026-04-01

### Added

- **Visual AI Overview tab** — `src/app/(dashboard)/competitors/[id]/page.tsx`
  Replaced text-heavy AI Overview tab with a visual-first layout: 4 severity stat cards (critical/high/medium/low), 2 Recharts donut charts (findings by severity + actions by urgency), compact expandable finding rows with evidence (previously discarded `evidence` field now surfaced), Kanban-style actions board grouped by urgency (immediate/this week/this month), and collapsible summary + implications cards.

- **New components:**
  - `src/components/ai-overview/severity-cards.tsx` — 4-card severity count grid with colored icons
  - `src/components/ai-overview/finding-row.tsx` — Compact finding row with expand/collapse for evidence
  - `src/components/ai-overview/actions-kanban.tsx` — 3-column urgency Kanban board showing full action text
  - `src/components/ai-overview/collapsible-text.tsx` — Line-clamped text with "Read more" toggle
  - `src/components/charts/severity-donut.tsx` — Reusable Recharts donut chart with center label

- **Account types scraper** — `scrapers/account_types_scraper.py`
  Dedicated 3-layer scraper for detailed account type specifications (15+ fields per account). Layer 1: official broker pages via Playwright + Claude AI. Layer 2: help centre pages via HTTP + Claude AI. Layer 3: aggregator cross-check (TradingFinder + DailyForex). Includes per-field cross-source reconciliation with Claude Haiku for disagreements, change detection, and audit trail stored in `reconciliation_json` column.

- **Account type snapshots DB table** — `src/db/schema.ts`, `scrapers/db_utils.py`
  New `account_type_snapshots` table with `accounts_detailed_json`, `source_urls`, `extraction_method`, and `reconciliation_json` columns.

- **UIUX review Claude skill** — `.claude/commands/uiux-review.md`
  Custom slash command for auditing dashboard pages against a 5-criteria UX framework (information hierarchy, data presentation, visual design, content strategy, responsive/accessibility).

- **`StatCard` customization** — `src/components/charts/stat-card.tsx`
  Added `iconBgClassName` and `iconClassName` props to allow severity-colored icon backgrounds instead of default primary.

### Changed

- **Global font size upgrade** — `src/app/globals.css`
  Bumped `--text-xs` from `0.8125rem` (13px) to `0.875rem` (14px) and `--text-sm` from `0.9375rem` (15px) to `1rem` (16px). All body text now meets the 16px minimum readability threshold.

- **Eliminated sub-14px custom font sizes** — sidebar, mobile header, competitors page, severity donut
  Replaced all `text-[10px]` (6 instances) and `text-[11px]` (2 instances) with `text-xs` (now 14px). Chart tooltip font sizes upgraded from 12px to 14px across 4 chart components.

- **Increased spacing throughout** — layout, sidebar, insight cards, insight modal, finding rows
  Main content padding `md:p-6` → `md:p-8`. Sidebar/mobile nav: `py-2` → `py-2.5`, `space-y-0.5` → `space-y-1`. Insight cards: `p-5` → `p-6`, increased internal margins. Modal findings/actions: `p-3` → `p-3.5`, `space-y-2` → `space-y-2.5`.

- **Competitors table overhaul** — `src/app/(dashboard)/competitors/page.tsx`
  Replaced "Latest AI Insight" and "Last Updated" columns with Spread, Instruments, and AI Findings (severity dots). Added `TrustpilotCell` (color-coded score + progress bar), `FindingDots`, and `FreshnessDot` components. Mobile cards show 3-column metric grid.

- **Competitors API enriched** — `src/app/api/competitors/route.ts`
  Added `spreadFrom`, `accountTypesCount`, and `findingCounts` fields. Removed `latestInsightSummary` and `latestInsightDate`.

- **Insights page polish** — `src/app/(dashboard)/insights/page.tsx`, `insight-modal.tsx`
  Cards sorted by highest severity first, summary preview shows first sentence only, severity dots in card footer. Modal: severity count bar, colored finding borders, urgency-tagged actions, increased spacing.

- **Junk data display cleanup** — `src/app/(dashboard)/competitors/[id]/page.tsx`
  Added `displayValue()` helper that converts null, empty, and verbose fallback strings ("Unable to determine", "Not available", etc.) to clean "—" dashes.

---

## [1.0.0] — 2026-03-31

### UI/UX Overhaul
- Unified color system: standardized all `slate-*` to `gray-*`, eliminated dual-palette inconsistency
- Sidebar redesign: tinted active state (`bg-primary/10 text-primary`) instead of solid blue block, icon color treatment, nav divider, focus-visible rings
- Mobile drawer: matching sidebar design, escape key handler, animations
- Table headers: subtle `bg-gray-50/80` background for visual separation across all tables
- Table rows: primary-tinted hover (`hover:bg-primary/[0.03]`) across all tables
- All buttons: proper hover/active/focus states (`hover:bg-primary/90 active:bg-primary/80`)
- Filter selects: hover border, focus ring with primary color
- Cards: consistent hover shadow, primary-tinted border on hover
- KPI stat cards: icon with tinted background (`bg-primary/10`)
- Insight cards: improved "no insight" contrast (was `opacity-40`, now `bg-gray-50/50`)
- Market cards: primary-themed hover instead of hardcoded blue
- Focus rings: all interactive elements use `focus-visible:ring-primary/40`
- Links: `hover:text-primary` instead of `hover:text-blue-600`
- Login page: improved input focus ring, button states

### Data Visualization (Recharts)
- KPI sparkline stat cards on Executive Summary (competitors, changes, Trustpilot, promos)
- Reputation radar chart on competitor detail (Trustpilot, MyFXBook, iOS, Android, WikiFX)
- Social media horizontal bar chart on competitor detail
- Changes activity timeline (14-day bar chart colored by severity)

### Loading & Error States
- Skeleton loading tables for competitors and changes pages
- Error states with retry buttons
- Dashboard-level error boundary (`error.tsx`)
- Scraper run buttons with `Loader2` spinner

### Accessibility
- Skip-to-main-content link
- `role="navigation"` and `aria-label` on nav elements
- `aria-current="page"` on active nav links
- `aria-label` on filter selects
- `aria-haspopup="dialog"`, `aria-modal`, escape key handler on insight modal
- Focus management: auto-focus close button on modal open
- `scope="col"` on all table headers

### Performance
- Fixed N+1 database queries across 3 routes (competitors, insights, markets) using batch `SELECT MAX(id) GROUP BY` pattern
- Replaced N×4 individual queries with 4 batch queries + O(1) lookup maps

### Security
- Timing-safe string comparison for auth tokens (Edge: XOR loop, Node: `crypto.timingSafeEqual`)
- Password length limit (500 chars) to prevent DoS
- Session timeout reduced from 7 days to 8 hours
- Path traversal guard on scraper execution endpoint

### Code Quality
- Created `safeParseJson()` utility with dev-mode logging, replacing ~25 silent `catch {}` blocks
- Extracted shared constants (`SCRAPERS`, `MARKET_FLAGS`, `PLATFORMS`) into `src/lib/constants.ts`
- Deduplicated `SeverityBadge` into `src/components/shared/severity-badge.tsx`
- Created shared components: `EmptyState`, `PageHeader`, `DataTable`
- Response validation: `r.ok` checks before `.json()` on all fetch calls
- BetaBar: fixed hydration with `useSyncExternalStore`, non-fixed positioning
- Client-side pagination (20 items/page), mobile card views, sort indicators, diff-style changes

---

## [Unreleased] — 2026-03-25 (Session 8: AI-Powered Pricing Scraper + QA & Security Audit)

### Added

- **Claude API extraction for all pricing fields** — `scrapers/pricing_scraper.py`
  Replaced all brittle regex helpers (`_extract_account_types`, `_extract_min_deposit`, `_extract_leverage`, `_extract_instruments_count`, `_extract_funding_methods`) with a single `_extract_with_claude()` call using `claude-haiku-4-5-20251001`. Claude extracts account types (with per-account spread, leverage, min deposit, currency), minimum deposit (USD), max leverage, instruments count, and funding methods from combined page text in one pass. Falls back to WikiFX data for any fields Claude could not extract.

- **Multi-URL scraping per broker** — `scrapers/config.py`, `scrapers/pricing_scraper.py`
  Added `account_urls` list to every broker config (3–4 verified URLs each), covering account types pages, funding/payment pages, and instruments/markets pages. URLs were researched and verified against live broker sites. The scraper now visits all URLs per broker, concatenates the text, and passes it to Claude — giving a much richer picture than scraping a single page.

- **WikiFX fallback for account types** — `scrapers/pricing_scraper.py`
  Extended `_enrich_from_wikifx()` to also fall back on `account_types` (not just `min_deposit_usd` and `leverage`) when Claude returns an empty list. Priority chain: Claude API → WikiFX → config overrides.

- **`known_min_deposit_usd` config override** — `scrapers/config.py`
  Added `known_min_deposit_usd` field alongside existing `known_account_types` / `known_leverage`. Set to `0.0` for Pepperstone (no minimum deposit). Always wins over scraped/AI-extracted values.

- **Scraper schedule documentation** — `SCRAPER_SCHEDULE.md`
  New file documenting the recommended cron schedule for all 7 scrapers: news every 6h, reputation + AI daily, promos every 2 days, pricing + WikiFX + social weekly. Includes ready-to-paste crontab block, environment variable requirements, and estimated run times.

### Fixed

- **`ANTHROPIC_API_KEY` not loaded in pricing scraper** — `scrapers/pricing_scraper.py`
  Added `python-dotenv` `.env.local` loading (same pattern as `promo_scraper.py` and `ai_analyzer.py`). Previously the scraper always skipped AI extraction when run directly.

- **`IndexError` on malformed leverage strings** — `scrapers/pricing_scraper.py`
  Change detection block called `int(lev.split(":")[1])` without checking `":"` was present. Added guard: only parses strings matching `":" in lev` with a digit after the colon. Wrapped in explicit try/except so failures are logged rather than silently swallowing the change detection call.

- **Fragile Claude response JSON parsing** — `scrapers/pricing_scraper.py`
  Replaced `startswith("```")` markdown fence stripping (fails on leading whitespace or trailing text) with `re.search(r'\{[\s\S]*\}')` to extract the JSON object from anywhere in the response.

- **`unsafe-eval` in CSP served to production** — `next.config.js`
  `unsafe-eval` is required by Turbopack HMR in development but not production. Made it conditional: only appended to `script-src` when `NODE_ENV !== "production"`.

- **Unauthenticated API requests return 302 redirect** — `src/middleware.ts`
  API routes (`/api/*`) now return `401 { error: "Unauthorized" }` for unauthenticated requests instead of redirecting to `/login`. Page routes still redirect as before.

- **`spreadJson` missing from Drizzle schema** — `src/db/schema.ts`
  Added `spreadJson: text("spread_json")` to `pricingSnapshots` table definition. The column existed in the DB (added via `ALTER TABLE` migration) but was absent from the ORM schema, causing it to be invisible to Drizzle queries.

- **Sidebar competitor count includes Pepperstone** — `src/app/(dashboard)/layout.tsx`
  Added `where(eq(competitors.isSelf, 0))` filter to the sidebar competitor count query so Pepperstone is not counted as a competitor in the navigation.

- **DB path resolution broken for local development** — `scrapers/db_utils.py`
  Simplified path resolution to always use `os.path.join(_PROJECT_ROOT, path.lstrip("./"))`, fixing local runs after `config.py` was switched to the relative `./data/competitor-intel.db` path.

---

## [Unreleased] — 2026-03-22 (Session 7: QA Audit Fixes)

### Fixed — Critical

- **Fresh-install schema mismatch** — `src/db/migrate.ts`
  Added `is_self INTEGER NOT NULL DEFAULT 0` to the initial `CREATE TABLE competitors` and `spread_json TEXT` to `CREATE TABLE pricing_snapshots`. Previously both were only added via `ALTER TABLE` after initial create, causing Drizzle ORM constraint failures and missing spread data on clean installs. The `ALTER TABLE` guards remain for existing databases.

- **Unbounded scraper process spawning** — `src/app/api/admin/run-scraper/route.ts`
  Added in-memory concurrency lock (`runningScraperName`) so only one scraper can run at a time — returns HTTP 409 if already running. Added per-IP rate limiter (max 10 starts per 15 min) returning HTTP 429. Fixed `req.json()` to safely parse with a `.catch(() => ({}))` fallback and validate `scraper` is a string before use.

- **No brute-force protection on login** — `src/app/api/auth/login/route.ts`
  Added per-IP failed-attempt tracker: max 5 failed logins per 15 minutes, returns HTTP 429 with retry countdown. Successful login clears the counter. Upgraded session cookie from `sameSite: "lax"` to `sameSite: "strict"`. Added safe body parsing fallback.

### Fixed — Medium

- **Silent leverage JSON parse failures** — `src/app/api/competitors/route.ts`
  Added `console.error` to the catch block so malformed `leverage_json` is logged with competitor ID rather than silently returning null.

- **`detect_change()` skips without logging** — `scrapers/db_utils.py`
  Added print statement when `new_value is None` so skipped change detection is visible in scraper output.

- **Entity-level errors not surfaced in scraper run summary** — `scrapers/reputation_scraper.py`
  `scrape_entity()` now collects per-source errors (Trustpilot, FPA, Google Play, App Store) into an `errors` list on its return dict. The caller in `scrape_all()` pops and propagates these into `error_summary`, so the run's final status and `error_message` column accurately reflect entity-level failures.

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

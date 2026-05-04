<!-- refreshed: 2026-05-04 -->
# Architecture

**Analysis Date:** 2026-05-04

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     Web UI Layer (Next.js SSR)                      │
│  Pages: Dashboard, Competitors, Markets, Changes, Admin, Insights   │
│  Client components: Selectors, charts, tables (React 19 + Tailwind) │
└────────────────┬────────────────────────────────┬────────────────────┘
                 │                                │
                 ▼                                ▼
┌──────────────────────────────┐   ┌──────────────────────────────────┐
│   API Routes (Next.js SSR)    │   │  Middleware (Auth, Rate Limit)  │
│  /api/competitors             │   │  /middleware.ts                  │
│  /api/changes                 │   │  • SHA-256 session token         │
│  /api/admin/run-scraper       │   │  • Bearer API key validation     │
│  /api/v1/promotions (ext)     │   │  • Fixed-window rate limiting    │
│  /api/v1/trends (ext)         │   │  • Timing-safe comparison        │
│  /api/auth/login              │   │                                  │
└────────────┬───────────────────┘   └──────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Data Layer (SQLite + Drizzle ORM)                 │
│                     `src/db/schema.ts`, `src/db/index.ts`           │
│  • WAL mode enabled                                                  │
│  • Foreign key constraints ON                                        │
│  • Additive migrations auto-run on startup                           │
└────────────────┬──────────────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    ▼                         ▼
SQLite DB              Scraper Feeds
`data/competitor-     `scrapers/` (Python)
intel.db`             • pricing_scraper.py
                      • promo_scraper.py
                      • social_scraper.py
                      • reputation_scraper.py
                      • ai_analyzer.py
                      • Others...
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Next.js App Router | Dashboard pages, layouts, routing | `src/app/**` |
| API Routes | Database queries, external integrations | `src/app/api/**` |
| Middleware | Authentication, rate limiting, security | `src/middleware.ts` |
| Database Schema | Tables, columns, types | `src/db/schema.ts` |
| Database Client | Drizzle ORM instance, migrations | `src/db/index.ts` |
| React Components | UI rendering, client interactivity | `src/components/**` |
| Utilities | Formatting, parsing, validation helpers | `src/lib/**` |
| Python Scrapers | Data ingestion, change detection | `scrapers/` |

## Pattern Overview

**Overall:** Next.js 14+ App Router with server-side rendering (SSR) for dashboard pages, SQLite backend with Drizzle ORM, Python data ingestion pipeline.

**Key Characteristics:**
- All dashboard pages are **force-dynamic** — rendered server-side on every request (no static prerendering)
- Database-at-render-time model: pages query SQLite directly during page generation
- Parallel data fetching via `Promise.all()` to minimize query latency
- Market-aware filtering via URL parameter `?market=<code>` propagated through all queries
- API routes expose snapshot data to external callers and MCP server
- Two-layer scraper pattern: aggregator sites + official broker pages + AI analysis
- Change detection noise-floor filtering to suppress irrelevant diffs

## Layers

**Presentation Layer:**
- Purpose: Render dashboard UI, handle user interactions, display market/competitor intelligence
- Location: `src/app/(dashboard)/**`, `src/components/**`
- Contains: Server components (pages), client components (charts, selectors), UI primitives
- Depends on: API routes, utilities, database (via server pages)
- Used by: Browser clients via HTTP

**API & Middleware Layer:**
- Purpose: Route requests, enforce authentication, apply rate limiting, serve data to internal pages and external callers
- Location: `src/app/api/**`, `src/middleware.ts`
- Contains: Route handlers (GET/POST), request validation, response formatting
- Depends on: Database, configuration (env vars)
- Used by: Frontend pages, external integrations (MCP server, marketing portal)

**Data Access Layer:**
- Purpose: Provide typed database interface, run migrations, manage schema
- Location: `src/db/index.ts`, `src/db/schema.ts`, `src/db/migrate.ts`
- Contains: Drizzle ORM instance, schema definitions, migration logic
- Depends on: SQLite, better-sqlite3
- Used by: API routes, server pages

**Data Storage Layer:**
- Purpose: Persist competitor intelligence snapshots, change events, AI insights, scraper metadata
- Location: `data/competitor-intel.db` (SQLite)
- Contains: Competitors table, pricing/promo/social/reputation snapshots, change events, AI insights, scraper runs
- Depends on: WAL-mode SQLite configuration
- Used by: All data access layer queries

**Scraper/Ingestion Layer:**
- Purpose: Crawl broker websites, aggregators, and social platforms; normalize data; detect changes; store results
- Location: `scrapers/` (Python)
- Contains: Per-domain scrapers (pricing, promo, social, reputation, wikifx, news), change threshold logic, AI analysis integration
- Depends on: SQLite, curl-cffi/requests, Playwright, Anthropic API
- Used by: Cron jobs, manual admin triggers via `/api/admin/run-scraper`

## Data Flow

### Primary Request Path (Dashboard Page Load)

1. **User navigates to `/` (Executive Summary)** (`src/app/(dashboard)/page.tsx`)
2. **Server component reads `?market` param and establishes market context** (via `parseMarketParam()` in `src/lib/markets.ts`)
3. **Parallel data queries execute:**
   - All competitors (filtered if market = "pepperstone" → exclude self-benchmark)
   - Latest AI portfolio insights
   - AI insights (top 20 by severity)
   - Recent changes (10 events)
   - High-severity count (this week & last week for WoW delta)
   - Change event aggregations (by day, severity, competitor domain)
   - Latest reputation/social/promo snapshots (market-filtered if set)
   - Latest scraper runs (for "last updated" timestamp)
   - Trustpilot/promo/social trend data
4. **Database returns results via Drizzle ORM** (`.where(sql\`...\`)` for market filters)
5. **Server component processes and structures data** (parse JSON, calculate metrics)
6. **React components render UI with data** (`<KpiRow>`, `<ReputationLeaderboard>`, etc.)
7. **HTML sent to browser** (Next.js hydrates with client component event listeners)

### Per-Market View Data Flow

1. **User selects market via `<MarketSelector>` dropdown** (`src/components/layout/market-selector.tsx`)
2. **Client component updates URL to `?market=sg` (using `useRouter.push()`)** 
3. **Page re-renders on server** with new `searchParams.market`
4. **Promo & pricing queries filter to `market_code = 'sg'`**
5. **Reputation & insights remain global** (not market-filtered)
6. **UI reflects filtered dataset** (shows only SG promos, SG-specific pricing)

### External API Data Flow (MCP Server / Marketing Portal)

1. **External client** sends `GET /api/v1/promotions?market=sg&competitor=octa HTTP/1.1` with `Authorization: Bearer <API_KEY>`
2. **Middleware validates API key** (timing-safe comparison in `src/middleware.ts` lines 78–87)
3. **Rate limit check** executed (per-key, 60 req/min window)
4. **Route handler** (`src/app/api/v1/promotions/route.ts`) queries latest promo snapshot(s) for competitor
5. **JSON response returned** with `X-RateLimit-*` headers
6. **External client parses and uses data** (marketing portal displays promos)

### Scraper → Database → Dashboard Flow

1. **Cron job triggers** `python scrapers/run_all.py`
2. **`pricing_scraper.py` executes first:**
   - Fetches pricing from official broker pages + aggregators
   - Computes change diffs vs. previous snapshot
   - Applies noise-floor thresholds (`change_thresholds.py`)
   - Inserts `pricing_snapshots` row + optionally `change_events` rows
   - Logs run metadata to `scraper_runs` table
3. **`promo_scraper.py` executes next:**
   - Scrapes BrokersOfForex.com, official promo pages (Playwright + Claude)
   - Deduplicates by hash
   - Inserts to `promo_snapshots`
   - Creates `change_events` if promos changed significantly
4. **Other scrapers follow** in sequence (`social_scraper`, `reputation_scraper`, etc.)
5. **`ai_analyzer.py` runs last:** generates AI insights from change feed
6. **Dashboard queries new snapshots** on next page load
7. **User sees updated data** with "last updated" timestamp from `scraper_runs.finishedAt`

**State Management:**
- **Server-side state:** Database is single source of truth; all page data fetched at render time
- **Client-side state:** Minimal — mainly UI state (sidebar collapsed, sort direction, market selection via URL)
- **Market state:** Stored in URL `?market=<code>` — state is serializable, shareable, bookmarkable
- **Rate limiter state:** In-memory Map in middleware (per-process); does not persist across restarts
- **Session state:** SHA-256-derived token in `auth_token` cookie; password stored as env var

## Key Abstractions

**Market Code System:**
- Purpose: Represent geographic/regulatory markets (Singapore, Malaysia, etc.)
- Examples: `src/lib/markets.ts` (TypeScript), `scrapers/market_config.py` (Python)
- Pattern: Strict enum (`MarketCode = "sg" | "my" | "th"...`); validation function `isMarketCode()` prevents invalid filters

**Snapshot Pattern:**
- Purpose: Store point-in-time data (pricing, promos, social followers) with market awareness
- Examples: `pricingSnapshots`, `promoSnapshots`, `socialSnapshots` (all in `src/db/schema.ts`)
- Pattern: Each snapshot tied to competitor + snapshot date + market code; latest snapshot identified via `MAX(id) GROUP BY competitor_id`

**Change Event Model:**
- Purpose: Track what changed, when, how severe, across all domains (pricing, promos, social, etc.)
- Examples: `changeEvents` table with fields: `competitorId`, `domain`, `fieldName`, `oldValue`, `newValue`, `severity`, `detectedAt`, `marketCode`
- Pattern: Noise-floor filtering in Python (`change_thresholds.py`) prevents storing trivial diffs; dashboard aggregates and displays

**AI Insights Model:**
- Purpose: Summarize competitor changes with recommendations and severity scoring
- Examples: `aiInsights` (per-competitor), `aiPortfolioInsights` (portfolio-wide summary)
- Pattern: Generated post-scraper by `ai_analyzer.py`; stored as JSON arrays (key findings, actions)

**Component Composition:**
- Purpose: Share behavior across dashboard pages (market filtering, pagination, data refetch)
- Examples: `<MarketSelector>` (client component), `<KpiRow>`, `<ReputationLeaderboard>` (server-aware components)
- Pattern: Server pages pass data as props; client components maintain UI state only

## Entry Points

**Web Application Entry:**
- Location: `src/app/layout.tsx`
- Triggers: HTTP request to `/`
- Responsibilities: Wrap app in theme provider, global styles, font configuration, Sonner toaster

**Dashboard Entry:**
- Location: `src/app/(dashboard)/layout.tsx`
- Triggers: Any dashboard route (`/(dashboard)/**`)
- Responsibilities: Fetch sidebar data (competitor count, last run), render layout shell, enforce `force-dynamic`

**Executive Summary Page:**
- Location: `src/app/(dashboard)/page.tsx`
- Triggers: GET `/` or `/?market=sg`
- Responsibilities: Fetch all dashboard metrics (KPIs, changes, insights), render cards/charts

**Authentication Entry:**
- Location: `src/middleware.ts` (lines 89–151)
- Triggers: Every request
- Responsibilities: Validate session token or API key, redirect to `/login` if missing, enforce rate limits for `/api/v1/`

**Scraper Trigger (Admin):**
- Location: `src/app/api/admin/run-scraper/route.ts`
- Triggers: POST `/api/admin/run-scraper` with auth token + scraper name
- Responsibilities: Validate authentication, check concurrency guard, spawn Python subprocess, stream output

**Scraper Trigger (Scheduled):**
- Location: Cron (system-level, not in this codebase; documented in `SCRAPER_SCHEDULE.md`)
- Triggers: Hourly/daily/weekly based on scraper
- Responsibilities: Execute `python scrapers/run_all.py` from project root

## Architectural Constraints

- **Threading:** Node.js single-threaded event loop per process; Python scrapers run as subprocess (blocking, one-at-a-time guard in route handler)
- **Global state:** Rate limiter Map in `src/middleware.ts` (in-memory, resets on restart); scraper concurrency guard (`runningScraperName` variable) in run-scraper route
- **Circular imports:** Scrapers avoid circular imports via explicit sys.path setup and conditional imports; dashboard components use barrel exports in `src/components/`
- **Database concurrency:** WAL mode (Write-Ahead Logging) allows readers while a writer is active; foreign key constraints enabled for referential integrity
- **Market awareness:** All snapshot queries must be market-aware; queries default to `market_code = "global"` if market param not set
- **Scraper isolation:** Each scraper runs independently; must manage DB connection and error handling; change detection is per-scraper responsibility

## Anti-Patterns

### Missing Market Filter in Query

**What happens:** A new feature queries `pricingSnapshots` without filtering by market, returns global data even when user selected `?market=sg`.

**Why it's wrong:** Misleads user into thinking they're viewing SG-specific data when they're seeing global/all-market data.

**Do this instead:** Check if market is set via `parseMarketParam(searchParams?.market)` and include `market_code` filter in all snapshot queries. See `src/app/(dashboard)/page.tsx` lines 38–40 for example:
```typescript
const promoMarketSql = market
  ? sql`AND market_code = ${market}`
  : sql``;
```

### Storing Unstructured Change Metadata

**What happens:** Change event stores `oldValue` and `newValue` as strings without documenting structure; later queries try to parse as JSON and fail silently.

**Why it's wrong:** Change events become un-queryable and unactionable; severity calculation can't extract metrics.

**Do this instead:** Normalize change values at scraper time. If change is a pricing tier, store `{ "leverage": "1:500", "spread": "0.5 pips" }` as valid JSON in the `oldValue`/`newValue` fields. Use `safeParseJson()` with explicit fallback (`src/lib/utils.ts` lines 92–103).

### Rendering Scraper Output as Trusted HTML

**What happens:** A page renders broker-provided promo text directly in JSX without sanitization.

**Why it's wrong:** Allows stored XSS if a scraper captures malicious HTML from a broker website.

**Do this instead:** Always escape user/scraper-provided content. Use React's default text rendering (not `dangerouslySetInnerHTML`). If HTML rendering is needed, use a sanitization library (not currently integrated; mark as concern if needed).

### Not Updating `lastUpdated` Timestamp

**What happens:** Scraper inserts new snapshots but forgets to record timestamp; dashboard shows stale "last updated" forever.

**Why it's wrong:** Users can't tell if data is fresh or outdated; debugging scraper failures becomes impossible.

**Do this instead:** Always insert `snapshotDate` at scraper time (`datetime.now(timezone.utc).isoformat()`); dashboard queries `MAX(snapshotDate)` across all snapshot types to compute "last updated".

## Error Handling

**Strategy:** Fail-safe with fallbacks; log errors; continue operation.

**Patterns:**
- **JSON parsing errors:** Use `safeParseJson(json, fallback)` to return fallback value and log warning in dev mode (`src/lib/utils.ts`)
- **Database query errors:** Route handlers return `NextResponse.json({ error: "..." }, { status: 500 })`
- **Middleware errors:** Reject with 401/429 status before reaching route handler (auth failure, rate limit)
- **Scraper errors:** Catch exceptions, log to file (`logs/<scraper>.log`), update `scraper_runs` with `error_message` and `status: "failed"`
- **Missing env vars:** Server refuses to start (middleware checks `DASHBOARD_PASSWORD` exists; scraper checks `ANTHROPIC_API_KEY`)

## Cross-Cutting Concerns

**Logging:** 
- Dashboard: `console.warn()` in `safeParseJson()` during development; all API errors logged to stdout
- Scrapers: Dual-stream logging — stdout + `logs/<scraper-name>.log` file (managed by `run_all.py`)

**Validation:** 
- Market codes: `isMarketCode(value)` guard in `src/lib/markets.ts`; invalid codes treated as "show all markets"
- Market config sync: TS list mirrors Python list; any change to markets must update both files
- API request params: Parsed and validated in route handlers (e.g., `limit` clamped to 1–50)

**Authentication:** 
- Dashboard: SHA-256-derived token from `DASHBOARD_PASSWORD`, stored in `auth_token` cookie
- API (`/api/v1/*`): Bearer token via `Authorization` header, constant-time comparison to prevent timing attacks
- Rate limiting: Per-bearer-token or per-IP, fixed-window (60 req/min), headers included in responses

**Security hardening (v1.4.1):**
- SSRF guard: Scrapers validate URLs before fetching (not shown in code samples; check `config.py`)
- CVE patches: Dependencies updated in `package.json` and Python requirements (via pip audit)
- Rate limiting: Middleware applies to `/api/v1/*` and admin scraper trigger to prevent abuse/DOS

---

*Architecture analysis: 2026-05-04*

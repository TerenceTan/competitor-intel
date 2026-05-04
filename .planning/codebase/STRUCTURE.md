# Codebase Structure

**Analysis Date:** 2026-05-04

## Directory Layout

```
competitor-analysis-dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx                 # Root layout (fonts, theme, toaster)
│   │   ├── login/
│   │   │   └── page.tsx               # Login page
│   │   ├── (dashboard)/               # Protected routes (auth required)
│   │   │   ├── layout.tsx             # Dashboard shell (sidebar, header)
│   │   │   ├── page.tsx               # Executive summary (/dashboard)
│   │   │   ├── admin/
│   │   │   │   └── page.tsx           # Admin scraper controls
│   │   │   ├── changes/
│   │   │   │   └── page.tsx           # Change events feed
│   │   │   ├── competitors/
│   │   │   │   ├── page.tsx           # Competitors table (sortable, filterable)
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx       # Competitor detail page
│   │   │   ├── insights/
│   │   │   │   └── page.tsx           # AI insights summary
│   │   │   ├── markets/
│   │   │   │   ├── page.tsx           # Markets overview
│   │   │   │   └── [code]/
│   │   │   │       └── page.tsx       # Per-market dashboard (promos, pricing by market)
│   │   │   ├── pepperstone/
│   │   │   │   └── page.tsx           # Pepperstone self-benchmark
│   │   │   └── error.tsx              # Error boundary for dashboard
│   │   └── api/
│   │       ├── auth/
│   │       │   └── login/
│   │       │       └── route.ts       # POST /api/auth/login (set auth_token cookie)
│   │       ├── admin/
│   │       │   └── run-scraper/
│   │       │       └── route.ts       # POST /api/admin/run-scraper (trigger Python scraper)
│   │       ├── competitors/
│   │       │   └── route.ts           # GET /api/competitors (table data with market filter)
│   │       ├── changes/
│   │       │   └── route.ts           # GET /api/changes (change event feed)
│   │       └── v1/
│   │           ├── promotions/
│   │           │   └── route.ts       # GET /api/v1/promotions (external, auth + rate limit)
│   │           └── trends/
│   │               └── route.ts       # GET /api/v1/trends (external, auth + rate limit)
│   ├── components/
│   │   ├── ui/                        # Shadcn/UI primitives
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── time-ago.tsx
│   │   │   └── ... (other primitives)
│   │   ├── layout/                    # Dashboard layout components
│   │   │   ├── sidebar.tsx            # Left navigation menu
│   │   │   ├── mobile-header.tsx      # Mobile menu button + logo
│   │   │   ├── market-selector.tsx    # Market dropdown (client component)
│   │   │   ├── beta-bar.tsx           # Beta notice banner
│   │   │   └── stale-data-banner.tsx  # Warning when scrapers missed cycles
│   │   ├── charts/                    # Visualization components
│   │   │   ├── kpi-row.tsx            # KPI cards (count, trend)
│   │   │   ├── reputation-leaderboard.tsx  # Trustpilot scores ranked
│   │   │   ├── reputation-radar.tsx   # Radar chart of reputation metrics
│   │   │   ├── social-bar-chart.tsx   # Social follower counts bar chart
│   │   │   ├── activity-heatmap.tsx   # Change events heatmap
│   │   │   ├── severity-donut.tsx     # Distribution of change severity
│   │   │   ├── morning-brief.tsx      # Top changes summary (today)
│   │   │   ├── competitive-position.tsx  # Market positioning
│   │   │   └── changes-timeline.tsx   # Timeline of change events
│   │   ├── shared/                    # Shared UI components
│   │   │   ├── empty-state.tsx        # "No data" placeholder
│   │   │   ├── severity-badge.tsx     # Colored severity indicator
│   │   │   ├── account-accordion.tsx  # Expandable account types list
│   │   │   └── ... (other shared)
│   │   ├── admin/                     # Admin-specific components
│   │   │   ├── competitor-form.tsx    # Form to add/edit competitors
│   │   │   ├── competitor-table.tsx   # Competitor management table
│   │   │   └── scraper-table.tsx      # Scraper run history table
│   │   └── ai-overview/               # AI insights components
│   │       └── ... (insight rendering)
│   ├── db/
│   │   ├── index.ts                   # Database client (Drizzle instance)
│   │   ├── schema.ts                  # Table definitions (competitors, snapshots, changes, etc.)
│   │   ├── migrate.ts                 # Migration runner
│   │   └── seed.ts                    # Data seeding for development
│   ├── lib/
│   │   ├── utils.ts                   # Utilities (formatting, parsing, cn())
│   │   ├── constants.ts               # SCRAPERS metadata, PLATFORMS, MARKET_FLAGS
│   │   ├── markets.ts                 # Market code validation, PRIORITY_MARKETS, MARKET_NAMES
│   │   └── styles.ts                  # (if needed) Tailwind utilities
│   └── middleware.ts                  # Auth, rate limiting, security checks
├── scrapers/
│   ├── run_all.py                     # Orchestrator (runs all scrapers in sequence)
│   ├── pricing_scraper.py             # Pricing & leverage data
│   ├── promo_scraper.py               # Promotions (multi-source: aggregators + official)
│   ├── social_scraper.py              # Social media followers/engagement
│   ├── reputation_scraper.py          # Trustpilot, FPA, App Store ratings
│   ├── account_types_scraper.py       # Account type definitions
│   ├── wikifx_scraper.py              # WikiFX profile data
│   ├── news_scraper.py                # Financial news monitoring
│   ├── ai_analyzer.py                 # AI insight generation (Anthropic API)
│   ├── config.py                      # Scraper configuration (DB path, delays, UA)
│   ├── market_config.py               # Market definitions (mirrors src/lib/markets.ts)
│   ├── db_utils.py                    # Database helpers, migration, change detection
│   ├── change_thresholds.py           # Noise-floor filtering logic
│   └── backfill_config_to_db.py       # Data migration utility
├── mcp-server/
│   ├── src/
│   │   └── index.ts                   # MCP server exposing DB as tools (Claude Code compatible)
│   ├── package.json
│   └── tsconfig.json
├── data/
│   ├── competitor-intel.db            # SQLite database (WAL mode)
│   ├── competitor-intel.db-shm        # WAL shared memory file
│   ├── competitor-intel.db-wal        # WAL log file
│   └── competitors.db                 # (Legacy, empty)
├── public/
│   ├── robots.txt                     # Disallow search engine indexing
│   └── ... (SVG assets, favicon)
├── logs/
│   ├── pricing-scraper.log            # Scraper output logs
│   ├── promo-scraper.log
│   └── ... (per-scraper)
├── docs/
│   └── ... (markdown documentation)
├── .claude/
│   └── settings.local.json            # Local Claude IDE settings
├── .planning/
│   └── codebase/                      # Generated analysis documents (ARCHITECTURE.md, etc.)
├── .next/                             # Next.js build output (not committed)
├── next.config.js                     # Next.js configuration
├── tsconfig.json                      # TypeScript configuration
├── eslint.config.mjs                  # ESLint rules
├── postcss.config.mjs                 # PostCSS configuration
├── components.json                    # Shadcn/UI config
├── package.json                       # Node dependencies (Next.js, React, Drizzle, etc.)
├── CHANGELOG.md                       # Version history
├── README.md                          # Project overview
├── SCRAPER_SCHEDULE.md                # Cron schedule for scrapers
└── .gitignore                         # Exclude node_modules, logs, .env
```

## Directory Purposes

**`src/app/`:**
- Purpose: Next.js App Router pages and API routes
- Contains: Page components (SSR), layout wrappers, route handlers
- Key files: `layout.tsx` (root), `page.tsx` (route pages), `route.ts` (API handlers)

**`src/app/(dashboard)/`:**
- Purpose: Protected dashboard routes (require authentication)
- Contains: Dashboard pages, layout shell, sidebar, headers
- Key files: `layout.tsx` (shell), `page.tsx` (executive summary), `[id]/page.tsx` (dynamic routes)

**`src/components/ui/`:**
- Purpose: Reusable UI primitives (shadcn/UI)
- Contains: Button, Card, Dialog, Table, Tabs, etc. — all unstyled but themed
- Key files: All follow shadcn naming convention

**`src/components/layout/`:**
- Purpose: Dashboard layout and navigation components
- Contains: Sidebar, header, market selector, banners
- Key files: `sidebar.tsx`, `market-selector.tsx` (client), `stale-data-banner.tsx` (server)

**`src/components/charts/`:**
- Purpose: Data visualization components using Recharts library
- Contains: KPI cards, leaderboards, heatmaps, donut charts, radar charts
- Key files: `kpi-row.tsx`, `reputation-leaderboard.tsx`, `activity-heatmap.tsx`

**`src/db/`:**
- Purpose: Database schema, ORM instance, migrations
- Contains: Drizzle table definitions, database client, migration runner
- Key files: `schema.ts` (all tables), `index.ts` (client), `migrate.ts` (migrations)

**`src/lib/`:**
- Purpose: Utility functions, constants, validators
- Contains: Formatting (dates, time ago), parsing (JSON, market codes), styling (cn helper)
- Key files: `utils.ts` (formatting), `markets.ts` (market validation), `constants.ts` (SCRAPERS list)

**`scrapers/`:**
- Purpose: Python data ingestion pipeline
- Contains: Per-domain scrapers, orchestrator, database utils, change detection logic
- Key files: `run_all.py` (orchestrator), individual `*_scraper.py` files, `db_utils.py` (shared DB logic)

**`mcp-server/`:**
- Purpose: Model Context Protocol server for Claude Code integration
- Contains: Standalone TypeScript server exposing database queries as tools
- Key files: `src/index.ts` (server implementation, tools definition)

**`data/`:**
- Purpose: Persistent data storage
- Contains: SQLite database file + WAL artifacts
- Key files: `competitor-intel.db` (main database)

## Key File Locations

**Entry Points:**
- `src/app/layout.tsx` - Root layout (root HTML, global styles, providers)
- `src/app/login/page.tsx` - Login page
- `src/app/(dashboard)/page.tsx` - Executive summary dashboard
- `src/middleware.ts` - Auth and rate limit enforcement

**Configuration:**
- `src/db/schema.ts` - Database schema (all table definitions)
- `src/lib/constants.ts` - Scraper metadata, platforms list
- `src/lib/markets.ts` - Market code definitions and validation
- `next.config.js` - Next.js build and server options

**Core Logic:**
- `src/app/(dashboard)/page.tsx` - Executive summary (658 lines, main dashboard)
- `src/app/api/competitors/route.ts` - Competitors API with market filter
- `src/app/api/v1/promotions/route.ts` - External promotions API (115 lines)
- `scrapers/promo_scraper.py` - Two-layer promo scraper (aggregators + official)
- `scrapers/db_utils.py` - Shared scraper database utilities and change detection

**Testing:**
- No test files present (no test framework detected)

## Naming Conventions

**Files:**
- Pages: `page.tsx` (Next.js convention)
- API routes: `route.ts` (Next.js convention)
- Components: PascalCase (`MarketSelector.tsx`, `KpiRow.tsx`)
- Utilities: camelCase (`safeParseJson`, `timeAgo`)
- Database schema: camelCase table names with `Snapshots` or `Entries` suffix

**Directories:**
- Feature-based: `/app/(dashboard)/markets`, `/components/charts`, `/scrapers`
- Lowercase with hyphens: `admin`, `app-store`, `better-sqlite3` (packages)

**Identifiers:**
- Competitor IDs: lowercase with no spaces (`icmarkets`, `pepperstone`)
- Market codes: ISO-like 2-letter codes (`sg`, `my`, `th`)
- Severity levels: lowercase (`critical`, `high`, `medium`, `low`)

## Where to Add New Code

**New Feature (e.g., new competitor metric):**
- Primary code: `src/app/(dashboard)/[relevant-page]/page.tsx` or new `src/app/(dashboard)/[feature]/page.tsx`
- API endpoint: `src/app/api/[feature]/route.ts`
- Database schema changes: `src/db/schema.ts` (add table or column)
- Scraper integration: `scrapers/[domain]_scraper.py` or extend existing scraper
- Tests: Create `src/app/(dashboard)/[feature]/page.test.tsx` (pattern not yet established)

**New Component:**
- Implementation: `src/components/[category]/[ComponentName].tsx`
- Imports: Use path alias `@/components/[category]/[ComponentName]`
- If UI primitive: Place in `src/components/ui/`
- If layout element: Place in `src/components/layout/`
- If chart/visualization: Place in `src/components/charts/`

**New Utility Function:**
- Shared helpers: `src/lib/utils.ts` (if formatting/parsing) or create `src/lib/[domain].ts`
- Database queries: Keep in route handlers (`src/app/api/**`) or extract to `src/db/queries.ts` if reused
- Market logic: Add to `src/lib/markets.ts`

**New Scraper or Scraper Extension:**
- New data source: Create `scrapers/[domain]_scraper.py` following template in `promo_scraper.py`
- Change detection logic: Update `scrapers/change_thresholds.py`
- Database insertion: Use `db_utils.py` functions (`get_db()`, `log_scraper_run()`, `detect_change()`)
- Register in `scrapers/run_all.py` SCRIPTS list and `src/lib/constants.ts` SCRAPERS array

**API Endpoint (Internal):**
- Location: `src/app/api/[resource]/route.ts`
- Pattern: Fetch from DB via Drizzle, apply market filter if needed, return `NextResponse.json()`
- Authentication: Middleware handles; check `request.headers` for data if needed

**API Endpoint (External, v1):**
- Location: `src/app/api/v1/[resource]/route.ts`
- Pattern: Validate Bearer token (middleware), apply rate limiting (middleware), fetch and return data
- Documentation: Add query parameter comments at top of route.ts

## Special Directories

**`.next/`:**
- Purpose: Next.js build output (compiled pages, static assets)
- Generated: Yes (created by `next build`)
- Committed: No (in .gitignore)

**`logs/`:**
- Purpose: Scraper execution logs
- Generated: Yes (created by `scrapers/run_all.py`)
- Committed: No (in .gitignore)

**`data/`:**
- Purpose: SQLite database files
- Generated: Partially (database itself is auto-created if missing; WAL artifacts are runtime)
- Committed: `competitor-intel.db` is committed (historical data); `-shm` and `-wal` files are not

**`.planning/codebase/`:**
- Purpose: Analysis documents generated by `/gsd-map-codebase` tool
- Generated: Yes (created by this mapper)
- Committed: Yes (serves as reference for other GSD tools)

---

*Structure analysis: 2026-05-04*

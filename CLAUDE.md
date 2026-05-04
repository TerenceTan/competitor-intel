<!-- GSD:project-start source:PROJECT.md -->
## Project

**Pepperstone Competitor Analysis Dashboard**

Internal marketing intelligence tool that pulls competitor signals (websites, app stores, social media, reviews, AI analysis) into a per-market dashboard for the Pepperstone web/marketing team. Currently at v1.4.1, in maintenance posture while the marketing-portal repo is the team's primary build. Primary audience: marketing managers operating per-market who use it to track competitor promo activity in their region.

**Core Value:** **Promo intelligence per market.** If everything else fails, the dashboard must continue to surface what competitors are running for promotions — broken down by market — accurately enough that marketing managers trust it.

### Constraints

- **Timeline**: Medium milestone (3–6 weeks, 3–5 phases). Time/shipping cadence is the top constraint — stakeholder wants visible value soon. Pragmatic choices beat comprehensive ones when they conflict.
- **Team**: Mostly solo support on the dashboard side (web team is small; primary attention is on marketing-portal). Maintenance burden of 8 markets × multiple scrapers must stay manageable.
- **Tech stack**: Locked to current stack — Next.js 15, React 19, Drizzle/SQLite, Python scrapers, EC2 + cron. No framework or DB swaps in this milestone.
- **Database**: Stays on SQLite for this milestone. Schema additions kept additive and simple to minimize cost of the eventual Postgres migration.
- **Budget**: Apify usage modest (≈ pay-per-run for handful of competitors × weekly cadence). BigQuery read costs minimal at nightly sync cadence. Anthropic costs already budgeted in existing AI flow. No expensive new SaaS subscriptions (Similarweb, Bright Data) this milestone.
- **Deployment**: `npm ci` on EC2, never `npm install` (lockfile drift). All deploys go through the existing pattern.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- TypeScript 5 - Dashboard frontend, API routes, and database layer (`src/**/*.ts`, `src/**/*.tsx`)
- Python 3 - Web scrapers, AI analysis, database utilities (`scrapers/**/*.py`)
- JavaScript - Configuration files, build setup (`next.config.js`, `postcss.config.mjs`, `eslint.config.mjs`)
## Runtime
- Node.js 22 LTS (production EC2)
- Node.js 25 (local development)
- Python 3 (scrapers/analysis)
- npm (JavaScript/TypeScript)
- pip (Python)
- Lockfile: `package-lock.json` present
## Frameworks
- Next.js 15.2.4 - Full-stack React framework with API routes
- React 19.2.3 - Component library and UI rendering
- React DOM 19.2.3 - DOM rendering
- Drizzle ORM 0.45.1 - Type-safe query builder for SQLite
- Drizzle Kit 0.31.9 - Schema migrations and code generation
- better-sqlite3 12.8.0 - Native SQLite driver (`src/db/schema.ts`, `scrapers/db_utils.py`)
- Tailwind CSS 4 - Utility-first CSS framework
- shadcn/ui components - Built on Base UI React
- @base-ui/react 1.3.0 - Headless component library
- lucide-react 0.577.0 - Icon library
- Recharts 3.8.0 - Charting library
- Sonner 2.0.7 - Toast notifications
- class-variance-authority 0.7.1 - Component variant management
- tailwind-merge 3.5.0 - Tailwind class resolution
- clsx 2.1.1 - Conditional CSS classes
- next-themes 0.4.6 - Dark mode switching
- ESLint 9 - Linting (configured via `eslint.config.mjs`)
- eslint-config-next 16.1.6 - Next.js ESLint rules
- TypeScript 5 - Type checking
- Turbopack - Next.js bundler (enabled in `next.config.js`)
- PostCSS 4 - CSS processing
- Playwright 1.49.0 - Browser automation for JavaScript-heavy sites (`scrapers/pricing_scraper.py`, `scrapers/reputation_scraper.py`)
- feedparser 6.0.11 - RSS/Atom feed parsing (`scrapers/news_scraper.py`)
- requests 2.32.3 - HTTP client (`scrapers/social_scraper.py`)
- python-dotenv 1.0.1 - Environment variable loading
- Anthropic 0.40.0 - Claude API client (`scrapers/ai_analyzer.py`)
## Key Dependencies
- next-auth 5.0.0-beta.30 - Authentication middleware (login session management via `src/app/api/auth/login/route.ts`)
- better-sqlite3 12.8.0 - Embedded SQLite database (stores competitor data, snapshots, changes, insights)
- @modelcontextprotocol/sdk 1.12.1 - MCP (Model Context Protocol) server for competitor intel (`mcp-server/`)
## Configuration
- `.env.local` file (required — contains secrets, not committed)
- `next.config.js` - Configures security headers (CSP, X-Frame-Options, Referrer-Policy), Turbopack, webpack fallbacks
- `tsconfig.json` - TypeScript compiler options (target ES2017, path aliases `@/*` → `./src/*`)
- `postcss.config.mjs` - PostCSS configuration for Tailwind
- `.prettierrc` - Code formatting (exact config not present, uses defaults)
- `eslint.config.mjs` - Linting rules
## Platform Requirements
- Node.js 25 (local) or Node.js 22 LTS (EC2 production)
- npm (for package management)
- Python 3 (for scrapers)
- SQLite (data storage)
- Git (version control)
- EC2 instance running Node.js 22 LTS
- SQLite database at `data/competitor-intel.db`
- Cron jobs for scheduled scraper runs
- Secrets in `.env.local` (EC2 environment setup)
## Database
- Location: `data/competitor-intel.db` (production)
- Backup: `data/competitors.db` (legacy or backup)
- Schema: `src/db/schema.ts`
- Tables: competitors, markets, pricingSnapshots, promoSnapshots, socialSnapshots, reputationSnapshots, appStoreSnapshots, wikifxSnapshots, accountTypeSnapshots, changeEvents, aiInsights
- Config: `drizzle.config.ts` (if present) or inline in build
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- React components (client): PascalCase with `.tsx` extension (e.g., `MarketSelector.tsx`, `TierBadge`)
- Server components: PascalCase with `.tsx` extension (e.g., `CompetitorsPage`, `KpiRow`)
- Utilities and helpers: camelCase with `.ts` extension (e.g., `utils.ts`, `markets.ts`, `constants.ts`)
- Database schema and queries: camelCase with `.ts` extension (e.g., `schema.ts`, `migrate.ts`, `seed.ts`)
- Server actions: `actions.ts` in feature directories
- API routes: lowercase-kebab-case directory structure (e.g., `/api/v1/promotions/route.ts`, `/api/auth/login/route.ts`)
- Scrapers (Python): snake_case (e.g., `social_scraper.py`, `pricing_scraper.py`)
- TypeScript: camelCase (e.g., `extractMaxLeverage()`, `safeParseJson()`, `checkRateLimit()`)
- Helper functions with leading underscore for internal/private helpers: `_fetchViaScraperapi()`
- React component functions: PascalCase for exported components (e.g., `MarketSelector()`, `TierBadge()`)
- Callbacks and event handlers: `on` prefix (e.g., `onChange()`, `onSort()`)
- Boolean checkers: `is`/`check` prefix (e.g., `isPublicHttpUrl()`, `checkRateLimit()`, `checkLoginRateLimit()`)
- Validation functions: `validate` prefix (e.g., `validateId()`, `validateForm()`)
- Derivation/parsing functions: extract/derive/parse prefix (e.g., `extractMaxLeverage()`, `deriveToken()`, `safeParseJson()`)
- Local variables: camelCase (e.g., `maxLeverage`, `minDepositUsd`, `competitorMap`)
- Constants: UPPER_SNAKE_CASE (e.g., `SCRAPER_NAME`, `RATE_LIMIT_MAX`, `MAX_ATTEMPTS`)
- Map/dictionary results: descriptive camelCase with `Map` or explicit type suffix (e.g., `competitorMap`, `reputationMap`, `pricingMap`)
- Boolean variables: `is`/`has` prefix (e.g., `isPending`, `hasUnlimited`, `isSelf`)
- Type-specific suffixes for clarity in parsed JSON: `Json` suffix (e.g., `leverageJson`, `promotionsJson`, `leverageConfidence`)
- Query parameter extractions: descriptive name with `Filter` suffix (e.g., `competitorFilter`, `marketFilter`, `activeOnly`)
- Exported interfaces: PascalCase (e.g., `CompetitorFormData`, `CompetitorRow`)
- String union types: lowercase (e.g., `type SortKey = keyof CompetitorRow`)
- Severity values: lowercase (e.g., `"critical" | "high" | "medium" | "low"`)
- Record/enum keys: match business domain (e.g., MARKET_NAMES uses lowercase market codes as keys)
## Code Style
- ESLint 9 with Next.js core web vitals and TypeScript configs
- Config: `eslint.config.mjs` (flat config format)
- No explicit Prettier config found — relies on ESLint default formatting
- Line length: practical limits observed in code (~80-100 chars for readability)
- Indentation: 2 spaces
- Framework: ESLint 9
- Extends: `eslint-config-next/core-web-vitals` and `eslint-config-next/typescript`
- Entry point: `eslint.config.mjs`
- Run: `npm run lint` (no auto-fix script configured)
- Key ignores: `.next/`, `out/`, `build/`, `next-env.d.ts`
## Import Organization
- `@/*` maps to `./src/*` (configured in `tsconfig.json`)
- Consistently used throughout codebase for internal imports
- No nested aliases observed
## Error Handling
- Return `NextResponse.json({ error: "message" }, { status: CODE })` for client errors
- Status codes: `400` (invalid input), `401` (unauthorized), `403` (forbidden), `409` (conflict), `429` (rate limit), `503` (server misconfiguration)
- Include descriptive error messages in response body (e.g., "Too many requests — try again in 15 minutes")
- Rate limit responses include headers: `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Pattern: Check conditions, return error response early; no deep nesting
- Server actions: explicit validation function (e.g., `validateId()`, `validateForm()`) returns `null` on success or error string on failure
- API query parameters: type coercion with defaults (e.g., `Math.min(Math.max(parseInt(...) || 1, 1), 50)`) to enforce bounds
- Request bodies: `.catch(() => ({}))` fallback for JSON parse errors; property type checks before use (e.g., `typeof body?.scraper === "string"`)
- Path traversal guard: verify resolved path stays within expected directory (e.g., `!scriptPath.startsWith(scrapersDir + path.sep)`)
- URL validation: `isPublicHttpUrl()` checks protocol (http/https), rejects localhost/metadata IPs, private ranges (10.x, 127.x, 169.254.x)
- Timing-safe comparison: `timingSafeEqual()` from `crypto` module (Node.js) or custom implementation in `middleware.ts` (Edge runtime)
- Rate limiting: per-IP or per-Bearer-token in-memory Map with sliding window (configurable `RATE_LIMIT_WINDOW_MS`, `RATE_LIMIT_MAX`)
- Password length cap: `MAX_PASSWORD_LENGTH = 500` before hashing to prevent DoS
- Brute-force protection: failed login attempts tracked by IP, lockout after `MAX_ATTEMPTS` (5 for login, 10 for scraper runs)
- SSRF mitigation: reject URLs with private/loopback hostnames or IPs before issuing outbound requests
- Cookies: `httpOnly`, `secure` (in production), `sameSite: "strict"`
- Use Drizzle ORM query builders to prevent SQL injection
- Batch queries with `Promise.all()` instead of sequential loops (e.g., 4 parallel queries instead of N*4)
- Fallback parsing: `safeParseJson(json, fallback, label?)` returns fallback if JSON is invalid; logs warning in development
- Null coalescing for optional fields: `field ?? null` or `field ?? "—"` for display
- Return `{ error: string }` on validation failure or `{ success: true }` on success
- No exceptions thrown; validation errors returned as object properties
- Call `revalidatePath()` on success to invalidate cached pages
- Components use conditional rendering for null/undefined fields
- Display "—" (em-dash) for missing/null values consistently
- Severity indicators (color-coded dots, badges) for status/health
- Fallback states for loading/skeleton states
## Logging
- `console.warn()` in development for malformed data (e.g., `[safeParseJson] Malformed JSON in promotionsJson`)
- API routes log status/errors via `console.log()` or `print()` (for Python scrapers)
- Rate limit and auth failures log via response HTTP status (implicit, no explicit logging)
- Scraper runs logged to database via `log_scraper_run()`, `update_scraper_run()` Python functions
- Keywords in CLI output: `[module-name]` prefix for origin context (e.g., `[ScraperAPI]`, `[Thunderbit]`)
## Comments
- **Security/validation logic:** Always document the threat model (e.g., "Path traversal guard", "Timing-safe comparison to prevent timing attacks", "SSRF guard")
- **Non-obvious algorithms:** Complex business logic or data transformations (e.g., leverage extraction, change detection heuristics)
- **Configuration & defaults:** Constants and their purpose (e.g., rate limit windows, cadence hours for stale data detection)
- **Workarounds:** Temporary fixes or known limitations (e.g., DNS rebinding not fully mitigated)
- **External dependencies:** Where external APIs/scrapers are used and why (e.g., Thunderbit for social extraction, YouTube API for subscriber counts)
- Obvious code (e.g., `// increment counter` for `count++`)
- Restating variable names
- Used for complex functions: `/** Returns HTML string or None on failure. */`
- Used for security/validation: `/** Reject URLs that point at private/loopback/link-local hosts... */`
- Function signature comments: single-line JSDoc when it clarifies intent
- Type parameter documentation: when types are complex or domain-specific
## Function Design
- Prefer functions under ~50 lines
- Longer functions acceptable for data fetching (e.g., page components with multiple `Promise.all()` queries)
- Break out validation/helper functions into separate named functions for clarity
- Destructure object parameters for readability (e.g., `{ searchParams }` instead of passing entire context)
- Use type aliases for complex parameter objects (e.g., `CompetitorFormData` interface)
- Optional parameters: use `?:` in types, not function overloads
- Maximum 3-4 parameters; beyond that, use object destructuring
- Functions return rich objects with semantic names (e.g., `{ allowed: boolean; retryAfterSecs?: number }`)
- Null-safe: functions return `null` or fallback for missing data rather than throwing
- Boolean checkers return `boolean` directly (e.g., `checkRateLimit()`)
- Server actions return `{ error: string }` or `{ success: true }`
## Module Design
- Named exports for utilities (e.g., `export function cn(...) {}`, `export function timeAgo(...) {}`)
- Default export for page components (e.g., `export default function CompetitorsPage() {}`)
- Default export for API routes (e.g., `export async function GET() {}`)
- Type exports: `export interface CompetitorFormData {}`, `export type SortKey = ...`
- Not heavily used; most imports are direct from source files
- Component libraries (`/ui/`, `/charts/`) export individual components
- Type definitions co-located with feature files
- Leading underscore for private helper functions (e.g., `_fetch_via_scraperapi()`, `_FB_SCHEMA`)
- No explicit "private" exports; convention is that underscore-prefixed items are internal
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
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
- All dashboard pages are **force-dynamic** — rendered server-side on every request (no static prerendering)
- Database-at-render-time model: pages query SQLite directly during page generation
- Parallel data fetching via `Promise.all()` to minimize query latency
- Market-aware filtering via URL parameter `?market=<code>` propagated through all queries
- API routes expose snapshot data to external callers and MCP server
- Two-layer scraper pattern: aggregator sites + official broker pages + AI analysis
- Change detection noise-floor filtering to suppress irrelevant diffs
## Layers
- Purpose: Render dashboard UI, handle user interactions, display market/competitor intelligence
- Location: `src/app/(dashboard)/**`, `src/components/**`
- Contains: Server components (pages), client components (charts, selectors), UI primitives
- Depends on: API routes, utilities, database (via server pages)
- Used by: Browser clients via HTTP
- Purpose: Route requests, enforce authentication, apply rate limiting, serve data to internal pages and external callers
- Location: `src/app/api/**`, `src/middleware.ts`
- Contains: Route handlers (GET/POST), request validation, response formatting
- Depends on: Database, configuration (env vars)
- Used by: Frontend pages, external integrations (MCP server, marketing portal)
- Purpose: Provide typed database interface, run migrations, manage schema
- Location: `src/db/index.ts`, `src/db/schema.ts`, `src/db/migrate.ts`
- Contains: Drizzle ORM instance, schema definitions, migration logic
- Depends on: SQLite, better-sqlite3
- Used by: API routes, server pages
- Purpose: Persist competitor intelligence snapshots, change events, AI insights, scraper metadata
- Location: `data/competitor-intel.db` (SQLite)
- Contains: Competitors table, pricing/promo/social/reputation snapshots, change events, AI insights, scraper runs
- Depends on: WAL-mode SQLite configuration
- Used by: All data access layer queries
- Purpose: Crawl broker websites, aggregators, and social platforms; normalize data; detect changes; store results
- Location: `scrapers/` (Python)
- Contains: Per-domain scrapers (pricing, promo, social, reputation, wikifx, news), change threshold logic, AI analysis integration
- Depends on: SQLite, curl-cffi/requests, Playwright, Anthropic API
- Used by: Cron jobs, manual admin triggers via `/api/admin/run-scraper`
## Data Flow
### Primary Request Path (Dashboard Page Load)
### Per-Market View Data Flow
### External API Data Flow (MCP Server / Marketing Portal)
### Scraper → Database → Dashboard Flow
- **Server-side state:** Database is single source of truth; all page data fetched at render time
- **Client-side state:** Minimal — mainly UI state (sidebar collapsed, sort direction, market selection via URL)
- **Market state:** Stored in URL `?market=<code>` — state is serializable, shareable, bookmarkable
- **Rate limiter state:** In-memory Map in middleware (per-process); does not persist across restarts
- **Session state:** SHA-256-derived token in `auth_token` cookie; password stored as env var
## Key Abstractions
- Purpose: Represent geographic/regulatory markets (Singapore, Malaysia, etc.)
- Examples: `src/lib/markets.ts` (TypeScript), `scrapers/market_config.py` (Python)
- Pattern: Strict enum (`MarketCode = "sg" | "my" | "th"...`); validation function `isMarketCode()` prevents invalid filters
- Purpose: Store point-in-time data (pricing, promos, social followers) with market awareness
- Examples: `pricingSnapshots`, `promoSnapshots`, `socialSnapshots` (all in `src/db/schema.ts`)
- Pattern: Each snapshot tied to competitor + snapshot date + market code; latest snapshot identified via `MAX(id) GROUP BY competitor_id`
- Purpose: Track what changed, when, how severe, across all domains (pricing, promos, social, etc.)
- Examples: `changeEvents` table with fields: `competitorId`, `domain`, `fieldName`, `oldValue`, `newValue`, `severity`, `detectedAt`, `marketCode`
- Pattern: Noise-floor filtering in Python (`change_thresholds.py`) prevents storing trivial diffs; dashboard aggregates and displays
- Purpose: Summarize competitor changes with recommendations and severity scoring
- Examples: `aiInsights` (per-competitor), `aiPortfolioInsights` (portfolio-wide summary)
- Pattern: Generated post-scraper by `ai_analyzer.py`; stored as JSON arrays (key findings, actions)
- Purpose: Share behavior across dashboard pages (market filtering, pagination, data refetch)
- Examples: `<MarketSelector>` (client component), `<KpiRow>`, `<ReputationLeaderboard>` (server-aware components)
- Pattern: Server pages pass data as props; client components maintain UI state only
## Entry Points
- Location: `src/app/layout.tsx`
- Triggers: HTTP request to `/`
- Responsibilities: Wrap app in theme provider, global styles, font configuration, Sonner toaster
- Location: `src/app/(dashboard)/layout.tsx`
- Triggers: Any dashboard route (`/(dashboard)/**`)
- Responsibilities: Fetch sidebar data (competitor count, last run), render layout shell, enforce `force-dynamic`
- Location: `src/app/(dashboard)/page.tsx`
- Triggers: GET `/` or `/?market=sg`
- Responsibilities: Fetch all dashboard metrics (KPIs, changes, insights), render cards/charts
- Location: `src/middleware.ts` (lines 89–151)
- Triggers: Every request
- Responsibilities: Validate session token or API key, redirect to `/login` if missing, enforce rate limits for `/api/v1/`
- Location: `src/app/api/admin/run-scraper/route.ts`
- Triggers: POST `/api/admin/run-scraper` with auth token + scraper name
- Responsibilities: Validate authentication, check concurrency guard, spawn Python subprocess, stream output
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
```typescript
```
### Storing Unstructured Change Metadata
### Rendering Scraper Output as Trusted HTML
### Not Updating `lastUpdated` Timestamp
## Error Handling
- **JSON parsing errors:** Use `safeParseJson(json, fallback)` to return fallback value and log warning in dev mode (`src/lib/utils.ts`)
- **Database query errors:** Route handlers return `NextResponse.json({ error: "..." }, { status: 500 })`
- **Middleware errors:** Reject with 401/429 status before reaching route handler (auth failure, rate limit)
- **Scraper errors:** Catch exceptions, log to file (`logs/<scraper>.log`), update `scraper_runs` with `error_message` and `status: "failed"`
- **Missing env vars:** Server refuses to start (middleware checks `DASHBOARD_PASSWORD` exists; scraper checks `ANTHROPIC_API_KEY`)
## Cross-Cutting Concerns
- Dashboard: `console.warn()` in `safeParseJson()` during development; all API errors logged to stdout
- Scrapers: Dual-stream logging — stdout + `logs/<scraper-name>.log` file (managed by `run_all.py`)
- Market codes: `isMarketCode(value)` guard in `src/lib/markets.ts`; invalid codes treated as "show all markets"
- Market config sync: TS list mirrors Python list; any change to markets must update both files
- API request params: Parsed and validated in route handlers (e.g., `limit` clamped to 1–50)
- Dashboard: SHA-256-derived token from `DASHBOARD_PASSWORD`, stored in `auth_token` cookie
- API (`/api/v1/*`): Bearer token via `Authorization` header, constant-time comparison to prevent timing attacks
- Rate limiting: Per-bearer-token or per-IP, fixed-window (60 req/min), headers included in responses
- SSRF guard: Scrapers validate URLs before fetching (not shown in code samples; check `config.py`)
- CVE patches: Dependencies updated in `package.json` and Python requirements (via pip audit)
- Rate limiting: Middleware applies to `/api/v1/*` and admin scraper trigger to prevent abuse/DOS
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

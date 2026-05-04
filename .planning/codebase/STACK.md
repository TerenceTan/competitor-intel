# Technology Stack

**Analysis Date:** 2026-05-04

## Languages

**Primary:**
- TypeScript 5 - Dashboard frontend, API routes, and database layer (`src/**/*.ts`, `src/**/*.tsx`)
- Python 3 - Web scrapers, AI analysis, database utilities (`scrapers/**/*.py`)

**Secondary:**
- JavaScript - Configuration files, build setup (`next.config.js`, `postcss.config.mjs`, `eslint.config.mjs`)

## Runtime

**Environment:**
- Node.js 22 LTS (production EC2)
- Node.js 25 (local development)
- Python 3 (scrapers/analysis)

**Package Manager:**
- npm (JavaScript/TypeScript)
- pip (Python)
- Lockfile: `package-lock.json` present

## Frameworks

**Core:**
- Next.js 15.2.4 - Full-stack React framework with API routes
- React 19.2.3 - Component library and UI rendering
- React DOM 19.2.3 - DOM rendering

**Database:**
- Drizzle ORM 0.45.1 - Type-safe query builder for SQLite
- Drizzle Kit 0.31.9 - Schema migrations and code generation
- better-sqlite3 12.8.0 - Native SQLite driver (`src/db/schema.ts`, `scrapers/db_utils.py`)

**UI & Styling:**
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

**Testing & Dev:**
- ESLint 9 - Linting (configured via `eslint.config.mjs`)
- eslint-config-next 16.1.6 - Next.js ESLint rules
- TypeScript 5 - Type checking

**Build:**
- Turbopack - Next.js bundler (enabled in `next.config.js`)
- PostCSS 4 - CSS processing

**Scraping (Python):**
- Playwright 1.49.0 - Browser automation for JavaScript-heavy sites (`scrapers/pricing_scraper.py`, `scrapers/reputation_scraper.py`)
- feedparser 6.0.11 - RSS/Atom feed parsing (`scrapers/news_scraper.py`)
- requests 2.32.3 - HTTP client (`scrapers/social_scraper.py`)
- python-dotenv 1.0.1 - Environment variable loading

**AI/Analysis:**
- Anthropic 0.40.0 - Claude API client (`scrapers/ai_analyzer.py`)

## Key Dependencies

**Critical:**
- next-auth 5.0.0-beta.30 - Authentication middleware (login session management via `src/app/api/auth/login/route.ts`)
- better-sqlite3 12.8.0 - Embedded SQLite database (stores competitor data, snapshots, changes, insights)

**Infrastructure:**
- @modelcontextprotocol/sdk 1.12.1 - MCP (Model Context Protocol) server for competitor intel (`mcp-server/`)

## Configuration

**Environment:**
- `.env.local` file (required — contains secrets, not committed)
  - `DASHBOARD_PASSWORD` - Authentication token
  - `ANTHROPIC_API_KEY` - Claude API for AI analysis
  - `YOUTUBE_API_KEY` - YouTube Data API for social media metrics
  - `THUNDERBIT_API_KEY` - Thunderbit AI extraction for Facebook, Instagram, X
  - `SCRAPERAPI_KEY` - Fallback scraper for social platforms

**Build:**
- `next.config.js` - Configures security headers (CSP, X-Frame-Options, Referrer-Policy), Turbopack, webpack fallbacks
- `tsconfig.json` - TypeScript compiler options (target ES2017, path aliases `@/*` → `./src/*`)
- `postcss.config.mjs` - PostCSS configuration for Tailwind
- `.prettierrc` - Code formatting (exact config not present, uses defaults)
- `eslint.config.mjs` - Linting rules

## Platform Requirements

**Development:**
- Node.js 25 (local) or Node.js 22 LTS (EC2 production)
- npm (for package management)
- Python 3 (for scrapers)
- SQLite (data storage)
- Git (version control)

**Production:**
- EC2 instance running Node.js 22 LTS
- SQLite database at `data/competitor-intel.db`
- Cron jobs for scheduled scraper runs
- Secrets in `.env.local` (EC2 environment setup)

## Database

**Type:** SQLite (embedded, file-based)
- Location: `data/competitor-intel.db` (production)
- Backup: `data/competitors.db` (legacy or backup)

**ORM:** Drizzle ORM with TypeScript type safety
- Schema: `src/db/schema.ts`
- Tables: competitors, markets, pricingSnapshots, promoSnapshots, socialSnapshots, reputationSnapshots, appStoreSnapshots, wikifxSnapshots, accountTypeSnapshots, changeEvents, aiInsights

**Migration:** Drizzle Kit manages schema migrations
- Config: `drizzle.config.ts` (if present) or inline in build

---

*Stack analysis: 2026-05-04*

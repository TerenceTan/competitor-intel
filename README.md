# Competitor Intelligence Dashboard

Internal tool for the Pepperstone APAC marketing team. Monitors 10 competitor brokers across pricing, promotions, reputation, social media, and news — then generates AI-powered insights and recommended actions via Claude.

> **Internal use only.** Access is password-protected. All crawlers and search engines are blocked via `robots.txt` and `noindex` meta tags.

---

## What It Does

1. **Scrapes** daily data from competitor broker websites, app stores, Trustpilot, ForexPeaceArmy, WikiFX, MyFXBook, Google News, YouTube, and Telegram.
2. **Scrapes Pepperstone itself** as a self-benchmark — stored separately, never shown as a competitor.
3. **Detects changes** across pricing, promotions, reputation, and social metrics.
4. **Analyses** detected changes with Claude (Sonnet 4.6) to produce per-competitor insights and a consolidated recommended action plan that directly references Pepperstone's live metrics.
5. **Displays** everything in a Next.js dashboard with an Executive Summary, competitor detail pages, change feed, and market views.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), Tailwind CSS, shadcn/ui |
| Database | SQLite (WAL mode) via better-sqlite3 + Drizzle ORM |
| Scrapers | Python 3 — Playwright, curl-cffi, requests |
| AI analysis | Anthropic Claude API (Sonnet 4.6 for analysis, Haiku 4.5 for extraction) |
| Social data | YouTube Data API v3 |
| Auth | Password-protected via cookie (SHA-256 derived token) |

---

## Competitors Tracked

**Tier 1:** IC Markets, Exness, Vantage Markets, XM Group, HFM

**Tier 2:** FBS, IUX, FxPro, Mitrade, TMGM

**Self-benchmark (not shown as competitor):** Pepperstone — scraped daily and used as live reference data in AI analysis

---

## Project Structure

```
.
├── scrapers/                   # Python scraping + AI analysis
│   ├── config.py               # Competitor configs, PEPPERSTONE_CONFIG, SCRAPER_UA/SCRAPER_HEADERS
│   ├── db_utils.py             # SQLite helpers, change detection, DB migrations
│   ├── run_all.py              # Orchestrator — runs all scrapers in sequence
│   ├── pricing_scraper.py      # Playwright — account types, leverage, min deposit
│   ├── promo_scraper.py        # Playwright + Claude — promotions extraction
│   ├── reputation_scraper.py   # Trustpilot, FPA, App Store, Google Play, MyFXBook
│   ├── social_scraper.py       # YouTube API + Playwright (Telegram)
│   ├── wikifx_scraper.py       # curl-cffi (bypasses WAF) — WikiFX scores
│   ├── news_scraper.py         # Google News RSS — headlines + sentiment
│   └── ai_analyzer.py          # Claude tool-use — per-competitor + portfolio insights
├── src/
│   ├── app/
│   │   ├── (dashboard)/        # Protected pages: /, /competitors, /insights, /changes, /markets, /admin
│   │   ├── api/                # API routes: competitors, changes, auth, admin
│   │   └── login/              # Login page
│   ├── db/
│   │   ├── schema.ts           # Drizzle schema
│   │   ├── migrate.ts          # CREATE TABLE + additive ALTER TABLE migrations
│   │   └── seed.ts             # Initial competitor + market seed data
│   └── components/             # Shared UI components
├── public/
│   └── robots.txt              # Disallows all crawlers + AI training bots
├── data/                       # SQLite DB (git-ignored)
└── logs/                       # Scraper logs (git-ignored)
```

---

## Setup

### Prerequisites

- Node.js 18+
- Python 3.10+
- `pip install playwright curl-cffi requests anthropic python-dotenv`
- `playwright install chromium`

### Environment Variables

Create `.env.local` at the project root (never commit — it is git-ignored):

```bash
DASHBOARD_PASSWORD=your_secure_password      # Required — no hardcoded fallback
ANTHROPIC_API_KEY=sk-ant-...                 # Required for AI analysis + promo extraction
YOUTUBE_API_KEY=AIza...                      # Required for YouTube social metrics
WEBSHARE_PROXY_URL=http://user:pass@host:port  # Recommended — bypasses EC2 IP block on MyFXBook
```

### Install & Run

```bash
npm install
npm run db:migrate    # Create DB tables (safe to re-run — additive only)
npm run db:seed       # Seed competitors + markets
npm run dev           # Start dashboard at http://localhost:3000
```

### Run Scrapers

```bash
# Run all scrapers in sequence
python3 scrapers/run_all.py

# Run individual scrapers
python3 scrapers/pricing_scraper.py
python3 scrapers/reputation_scraper.py
python3 scrapers/ai_analyzer.py
```

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `competitors` | Master list — includes Pepperstone with `is_self=1` |
| `markets` | APAC regions tracked |
| `pricing_snapshots` | Daily: leverage, min deposit, account types, instruments |
| `promo_snapshots` | Daily: active promotions (JSON array) |
| `reputation_snapshots` | Daily: Trustpilot, FPA, App Store, Google Play, MyFXBook |
| `social_snapshots` | Daily: YouTube/Telegram followers, posts, engagement |
| `wikifx_snapshots` | Daily: WikiFX score, accounts, marketing strategy |
| `news_items` | Headlines with sentiment (positive/neutral/negative) |
| `change_events` | Detected changes with severity: critical/high/medium/low |
| `ai_insights` | Per-competitor Claude analysis |
| `ai_portfolio_insights` | Consolidated action plan across all competitors |
| `scraper_runs` | Execution log: status, records processed, errors |

---

## Pepperstone Self-Benchmark

Pepperstone is scraped identically to competitors but stored with `is_self = 1`. It is:

- **Excluded** from all competitor-facing UI and API responses
- **Injected** into Claude prompts as live benchmark data, enabling concrete comparisons:

  > *"IC Markets' Trustpilot dropped to 4.2 — below Pepperstone's current 4.6 — an opportunity to highlight in APAC marketing."*

To activate full Pepperstone scraping, fill in the following fields in `PEPPERSTONE_CONFIG` in `scrapers/config.py`:

```python
"ios_app_id": None,      # Replace with App Store numeric ID
"android_package": None, # Replace with Play Store package name
"wikifx_id": None,       # Replace with WikiFX broker page ID
```

---

## Scraping Architecture & Anti-Detection

- **Shared UA** — All Playwright browser contexts and `requests` calls use `SCRAPER_UA` (Chrome 124) defined centrally in `config.py`
- **curl-cffi** — `wikifx_scraper.py` impersonates Chrome's TLS fingerprint to bypass Sucuri/Cloudflare WAF
- **Residential proxy** — MyFXBook routing via Webshare.io free proxy (`WEBSHARE_PROXY_URL`) bypasses AWS datacenter IP blocks
- **No identifying headers** — No custom bot name, no Pepperstone branding in any HTTP request

### MyFXBook proxy fallback order

1. `SCRAPERAPI_KEY` (trial/legacy)
2. `WEBSHARE_PROXY_URL` (recommended — free, 1 GB/month)
3. curl-cffi direct (local dev only — blocked from EC2)

---

## Scheduled Runs (Server)

```cron
0 2 * * * cd /home/ubuntu/app && export $(grep -v '^#' .env.local | xargs) && .venv/bin/python3 scrapers/run_all.py >> logs/cron.log 2>&1
```

---

## Security

- Session cookie uses **SHA-256** derived token via Node.js `crypto`
- `DASHBOARD_PASSWORD` must be set as an env var — server returns HTTP 503 if missing
- `/api/admin/run-scraper` requires a valid authenticated cookie (was previously unprotected)
- HTTP security headers on all responses: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`
- `robots.txt` blocks all crawlers including AI training bots: GPTBot, ClaudeBot, Google-Extended, CCBot, Bytespider, PerplexityBot, and more
- `noindex` / `nofollow` meta tags on every page via Next.js metadata API
- All SQL queries use parameterised statements — no injection risk
- No `dangerouslySetInnerHTML` anywhere — no XSS risk

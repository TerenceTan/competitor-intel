# Pepperstone APAC Competitor Analysis Dashboard
## Product Requirements Document (PRD)

**Version:** 1.1
**Date:** 16 March 2026
**Author:** Terence Tan, APAC Marketing
**Status:** Final — Ready for Engineering

---

## 1. Executive Summary

Pepperstone's APAC marketing team currently has no systematic way to monitor competitor activity across the region. This document defines the requirements for a **fully automated, web-based competitor intelligence dashboard** that continuously collects, analyses, and presents competitive data — with zero manual intervention in the pipeline.

The system monitors **11 competitor brokers** across **12 APAC markets**, spanning four data domains: pricing, promotions, digital presence, and brand reputation. An AI layer powered by **Claude claude-sonnet-4-6** generates daily summaries and actionable recommendations. The MVP is scoped to be deployed within **1 day using vibecoding** (AI-assisted development), using only free data sources and the approved Anthropic API and AWS infrastructure. The dashboard is served at `competitor-intel.pepperstone-asia.live` and protected by password authentication.

---

## 2. Problem Statement

The APAC region accounts for ~32% of global FX volume and 66.6% of all global FX/CFD website traffic — the largest and fastest-growing market for online brokers. Pepperstone competes against aggressive regional players who constantly launch new promotions, adjust pricing, and run localised campaigns across a fragmented set of platforms (LINE in Japan/Taiwan, Zalo in Vietnam, TikTok in Indonesia).

Today, the marketing team:
- Has no single view of what competitors are doing
- Discovers competitor promotions manually and often late
- Cannot easily compare pricing across the market
- Has no way to track competitor sentiment or reputation trends

This dashboard solves all of the above.

---

## 3. Goals

| Goal | Success Metric |
|---|---|
| Centralised competitive view | All 11 competitors visible in one dashboard |
| Fully automated data pipeline | Zero manual data entry required post-setup |
| Timely intelligence | Data refreshed daily; changes surfaced within 24 hours |
| AI-powered analysis | Claude generates competitor summaries daily |
| Low cost | Total running cost under $200/month for MVP |
| Fast deployment | Live on AWS within 1 working day |

### Non-Goals (MVP)

- Email report distribution (future phase)
- WeChat/China real-time monitoring (manual only — Great Firewall)
- eDM/email newsletter capture (requires Owletter/Panoramata subscription — deferred post-MVP)
- SEMrush SEO keyword tracking (paid — deferred post-MVP)
- Paid social listening tools (Apify, Brandwatch — deferred post-MVP)
- SimilarWeb traffic data (paid — deferred)

---

## 4. Target Users

**Primary:** APAC Marketing Team (campaign managers, regional managers)
**Secondary:** Head of APAC Marketing, Product team

**User profile:** Non-technical marketers who need fast, clear competitive intelligence — not raw data. The dashboard must communicate insights in plain language, not spreadsheet rows.

---

## 5. Competitors to Monitor

All 11 competitors are monitored **daily** with no tier differentiation for frequency.

| Tier | Competitor | Website |
|---|---|---|
| 1 — Direct | IC Markets | icmarkets.com |
| 1 — Direct | Exness | exness.com |
| 1 — Direct | Vantage Markets | vantagemarkets.com |
| 1 — Direct | XM Group | xm.com |
| 2 — Regional | FXTM | fxtm.com |
| 2 — Regional | ATFX | atfx.com |
| 2 — Regional | FP Markets | fpmarkets.com |
| 2 — Regional | FBS | fbs.com |
| 3 — Watch List | Titan FX | titanfx.com |
| 3 — Watch List | Monex / MIFX | mifx.com |
| 3 — Watch List | Fintrix Markets | fintrix.com |

> **Note on Fintrix Markets:** Founded January 2026 by three former Pepperstone executives. Priority watch — monitor closely for strategy that leverages insider knowledge of Pepperstone operations.

---

## 6. APAC Markets to Monitor

All markets are treated under the same foreign investment lens. No per-market regulatory distinction is tracked in the system.

| Market | Code | Characteristics | Key Platforms |
|---|---|---|---|
| Singapore | sg | Asia's largest FX hub. Institutional-grade expectations. High LTV but high CAC. | LinkedIn, Facebook, Telegram |
| Hong Kong | hk | Major financial centre. Bilingual (Cantonese/English). Sophisticated retail and HNW clients. Strong appetite for leveraged products. | Facebook, Instagram, Telegram, YouTube |
| Thailand | th | Strong retail participation. Responds well to education, influencers, local payments (PromptPay). | Facebook, YouTube, LINE |
| Vietnam | vn | High-growth. Regulatory uncertainty makes trust and credibility paramount. Community-driven learning culture. | Facebook, Zalo, YouTube |
| Indonesia | id | Largest growth market in SEA. Extremely high mobile engagement. Monex/MIFX holds ~32% local market share. | TikTok, Instagram, WhatsApp |
| Malaysia | my | Risk-aware traders who prioritise regulation and security. Islamic finance offerings are a key differentiator. | Facebook, WhatsApp |
| Japan | jp | One of the world's most active retail FX communities. Deep localisation and platform reliability are non-negotiable. | LINE, X/Twitter, YouTube |
| Mongolia | mn | Small but emerging market. Mobile-first. Price-sensitive. Growing FX awareness driven by social media. | Facebook, Telegram |
| India | in | Massive population. Offshore FX/CFD trading is technically restricted by SEBI/RBI but widely practised. Trust and INR payment options are key differentiators. | WhatsApp, YouTube, Instagram, Telegram |
| Philippines | ph | Fast-growing retail FX market. Mobile-first culture. Strong Facebook dominance. Localised payments (GCash, Maya) are critical. | Facebook, TikTok, YouTube, Viber |
| Taiwan | tw | Sophisticated, Japan-influenced FX culture. High retail participation rate. Traditional Chinese localisation required. | LINE, Facebook, YouTube |
| China | cn | Largest potential market but most restricted. Great Firewall blocks foreign tools. Foreign FX brokers operate in a grey zone. **Monitoring: manual only.** | WeChat (manual), Weibo (manual), Douyin (manual) |

---

## 7. Data Domains

### 7.1 Core Offering & Pricing

**What we track:** Maximum leverage per account type, minimum deposit (USD), account types available, number of tradeable instruments, accepted funding/withdrawal methods.

> **Out of scope:** Spreads and commissions are product-specific with too much variability to collect and compare reliably. These are excluded from MVP.

**Data sources (all free):**
- Competitor pricing and accounts pages — Playwright web scraping (localised URLs where available, e.g. `xm.com/th/`, `exness.com/vn/`)

**Frequency:** Daily (02:00 UTC)

**Output per competitor:** A structured snapshot stored in `pricing_snapshots`. If any field changes vs the previous day, a `change_event` is written.

---

### 7.2 Marketing & Promotions

**What we track:** Active promotions (deposit bonuses, cashback, NFP events), trading competitions (demo and live), IB/affiliate program terms, new or modified landing pages, visible ad copy.

**Data sources (all free):**
- Competitor promotions pages — Playwright scraping
- Competitor homepage change detection — Playwright scraping

> **Note:** eDM (email newsletter) monitoring is deferred to post-MVP as it requires a paid tool (Owletter/Panoramata ~$99–$199/month).

**Frequency:** Daily (02:15 UTC)

---

### 7.3 Digital Presence & Content

**What we track:** YouTube channel activity (new videos, subscriber count, view counts), Telegram public channel posts and member counts, Facebook/Instagram public page posts and follower count (best-effort), LINE and Zalo public page activity (best-effort).

**Data sources:**
- YouTube Data API v3 — **FREE** (10,000 units/day) — scrapes competitor's localised channels (e.g. IC Markets Thailand YouTube channel)
- Telegram — Telethon Python library — **FREE** (public channels, including market-specific channels e.g. Exness Vietnam Telegram)
- Facebook/Instagram — Playwright direct scraping — **FREE** (fragile; shown as N/A if blocked)
- LINE / Zalo — Playwright scraping — **FREE** (fragile; shown as N/A if blocked)

> **Note:** The dashboard UI is English-only. Data is pulled from localised sources (competitor pages in local languages) but displayed in English via AI translation/summarisation where needed. SEO keyword rankings and website traffic estimates (SEMrush, SimilarWeb) are deferred to post-MVP.

**Frequency:** Daily (02:30 UTC)

---

### 7.4 Brand & Reputation

**What we track:** Trustpilot review score and count, ForexPeaceArmy rating, Google Play and Apple App Store ratings and review counts, recent news mentions with sentiment.

**Data sources (all free):**
- Trustpilot broker pages — Playwright scraping
- ForexPeaceArmy broker pages — Playwright scraping
- Google Play Store — Playwright scraping
- Apple App Store — Playwright scraping
- Google News RSS — Free, no API key needed

**Frequency:** Daily (03:00 UTC)

---

## 8. Tech Stack

The stack is intentionally minimal — optimised for a **non-professional developer building via vibecoding** (using Claude Code / Cursor). No complex infrastructure, no microservices, no Docker for MVP.

| Layer | Technology | Rationale |
|---|---|---|
| Full-stack framework | **Next.js 15** (App Router) | Single framework handles both frontend and backend API routes. No separate server needed. |
| Styling | **Tailwind CSS v4** | Utility-first, fast to build with. No custom CSS needed. |
| Component library | **shadcn/ui** | Pre-built accessible components on top of Tailwind. |
| Charts | **Recharts** | Simple React chart library. Zero cost. |
| Database | **SQLite** | Zero infrastructure setup. Single file. Free. More than sufficient at this data volume. |
| ORM | **Drizzle ORM** | Lightweight, TypeScript-native, pairs perfectly with SQLite. |
| Scrapers | **Python 3.11 + Playwright** | Industry standard for browser automation. Handles JS-rendered sites. |
| Scheduling | **Linux crontab** | Built into every Linux server. No extra tools or services. |
| YouTube data | **YouTube Data API v3** | Official, free (10k units/day), reliable. |
| Telegram data | **Telethon** (Python) | Free Python library for reading public Telegram channels. |
| AI analysis | **Anthropic Claude API** (`claude-sonnet-4-6`) | Core differentiator. Approved spend. |
| Process manager | **PM2** | Keeps Next.js running on the server after SSH disconnect. |
| Hosting | **AWS EC2 t3.small** | Single instance runs everything: Next.js + Python cron jobs. ~$15–20/month. |

> **No Redis, no Bull queues, no separate microservices, no Docker for MVP.** Everything runs on one machine with cron and SQLite.

---

## 9. System Architecture

```
AWS EC2 t3.small
│
├── PYTHON SCRAPER SCRIPTS (crontab, daily 02:00–03:30 UTC)
│   ├── pricing_scraper.py        → Playwright → SQLite: pricing_snapshots
│   ├── promo_scraper.py          → Playwright → SQLite: promo_snapshots
│   ├── social_scraper.py         → YouTube API + Telethon + Playwright → SQLite: social_snapshots
│   ├── reputation_scraper.py     → Playwright → SQLite: reputation_snapshots
│   └── news_scraper.py           → Google News RSS → SQLite: news_items
│
├── AI ANALYSIS SCRIPT (crontab, daily 03:30 UTC)
│   └── ai_analyzer.py            → reads change_events → Claude API → SQLite: ai_insights
│
└── NEXT.JS APP (PM2, always-on)
    ├── API ROUTES (/api/*)        → Drizzle ORM reads/writes SQLite
    └── FRONTEND (React/Tailwind)  → fetches /api/* → renders dashboard
```

### Database Schema (SQLite, Drizzle ORM)

| Table | Contents |
|---|---|
| `competitors` | id, name, tier, website, created_at |
| `markets` | id, name, code, characteristics, platforms |
| `pricing_snapshots` | competitor_id, snapshot_date, leverage_json (per account type), account_types_json, min_deposit_usd, instruments_count, funding_methods_json |
| `promo_snapshots` | competitor_id, snapshot_date, promotions_json |
| `social_snapshots` | competitor_id, platform, snapshot_date, followers, posts_last_7d, engagement_rate, latest_post_url |
| `reputation_snapshots` | competitor_id, snapshot_date, trustpilot_score, trustpilot_count, fpa_rating, ios_rating, android_rating |
| `news_items` | competitor_id, title, url, source, published_at, sentiment |
| `change_events` | competitor_id, domain, field_name, old_value, new_value, severity, detected_at |
| `ai_insights` | competitor_id, generated_at, summary, key_findings_json, implications, actions_json |

### Change Detection Severity

| Severity | Trigger Examples |
|---|---|
| **Critical** | Leverage reduction, account type removed |
| **High** | Minimum deposit increase >20%, new promotion launched, significant traffic shift |
| **Medium** | New social campaign, new landing page, SEO ranking shift |
| **Low** | Minor copy change, small follower count fluctuation |

---

## 10. AI Analysis Layer

**Model:** `claude-sonnet-4-6` (Anthropic API)

**When invoked:**
- After each daily scraper run, for every competitor where `change_events` were generated
- Once per week (Sunday 09:00 UTC) — full digest across all competitors and domains

**Structured output format** (via Anthropic tool-use for consistent JSON):

```json
{
  "competitor_id": "exness",
  "summary": "Exness launched a new cashback promotion targeting Vietnam traders, offering up to $500 cashback on deposits above $1,000. This is their third Vietnam-specific campaign in 2026.",
  "key_findings": [
    {
      "finding": "New cashback promotion live on exness.com/vn/",
      "severity": "high",
      "evidence": "Promotions page shows 'VN Cashback Offer March 2026', live as of 16 March"
    }
  ],
  "pepperstone_implications": "Exness is aggressively targeting Pepperstone's Vietnam growth market with a high-value cashback offer that undercuts current Pepperstone promotions.",
  "recommended_actions": [
    {
      "action": "Review Pepperstone Vietnam promotion calendar — consider counter-offer",
      "urgency": "this_week"
    },
    {
      "action": "Inform Vietnam regional manager of competitive development",
      "urgency": "immediate"
    }
  ]
}
```

**Prompt design principles:**
- Inject APAC market context (which markets are affected, key platform characteristics)
- Reference Pepperstone's own positioning for relative comparison
- Focus on actionable intelligence, not raw data reporting
- Apply severity classification: Critical → High → Medium → Low

---

## 11. Dashboard — Screen-by-Screen Specification

### 11.1 Home — Executive Summary (`/`)

**Purpose:** The marketing team's daily morning brief. Instant overview of what changed.

**Components:**
- **"Top Things to Know Today"** — 3–5 AI-generated alert cards (Claude-powered). Each card: competitor logo | one-sentence summary | severity badge | link to detail.
- **Recent Changes Feed** — Last 20 `change_events` across all competitors. Columns: time ago | competitor | what changed | severity. Click row → competitor detail page.
- **Data Freshness Grid** — Status table showing last successful scraper run per domain (Pricing / Promotions / Social / Reputation / News). Green if <25h ago, red if overdue.
- **Quick Filters** — Market filter (multi-select dropdown), Tier filter (1 / 2 / 3)

---

### 11.2 Competitors List (`/competitors`)

**Purpose:** Scannable overview of all 11 competitors.

**Components:**
- Table with rows = competitors, columns:
  - Competitor name + logo + tier badge
  - Max Leverage (latest)
  - Min Deposit (USD, latest)
  - Active Promotions (count badge)
  - Trustpilot Score
  - Last AI insight summary (one line, truncated)
  - Last updated timestamp
- Click any row → Competitor Detail
- Sort by any column header

---

### 11.3 Competitor Detail (`/competitors/[id]`)

**Header:** Competitor name | logo | tier badge | website link | last updated timestamp

**Tab 1 — AI Overview**
- Full AI-generated summary (latest `ai_insights` record)
- Key findings list with severity badges
- Pepperstone implications paragraph
- Recommended actions checklist (with urgency labels: Immediate / This Week / This Month)
- "Regenerate Analysis" button (triggers on-demand Claude API call)
- Generated-at timestamp

**Tab 2 — Pricing**
- Account types table: account name | min deposit (USD) | max leverage | instruments count | funding methods
- Pepperstone comparison toggle (adds Pepperstone row, highlighted in blue)
- Leverage history chart (line chart, last 30 days — shows leverage changes over time)
- Market selector filter (shows localised data where available, e.g. leverage caps differ by country)

**Tab 3 — Promotions**
- Active promotions cards: name | type (deposit bonus / cashback / competition / IB) | value | dates | target market(s)
- Promotion history (collapsed list of past promotions)
- Recent landing page changes (URL + change detected date)

**Tab 4 — Digital Presence**
- Per-platform metric cards: YouTube | Telegram | Facebook | Instagram | LINE | Zalo
  - Each card: followers/subscribers | posts last 7 days | engagement rate | status badge (Live / N/A)
- YouTube: latest 3 video titles with view counts
- Telegram: last 3 posts preview

**Tab 5 — Reputation**
- Score cards: Trustpilot | ForexPeaceArmy | Google Play | App Store — score + review count + 7-day delta
- Score trend chart (line chart, last 90 days)
- Recent news mentions: headline | source | published date | sentiment badge (Positive / Neutral / Negative)

**Tab 6 — Change History**
- Full filterable table of all `change_events` for this competitor
- Columns: Date | Domain | Field | Old Value | New Value | Severity
- Export to CSV button

---

### 11.4 Markets View (`/markets`)

**Purpose:** Country-level competitive intelligence.

**Components:**
- Grid of 12 market flag cards. Click to open market detail.

**Market Detail (`/markets/[code]`):**
- Pricing comparison table: all competitors in this market, Pepperstone row highlighted
- Active promotions targeting this market
- Platform presence grid (which competitors are active on which platforms in this market)
- Recent changes in this market (last 20 `change_events` filtered by market tag)

---

### 11.5 Change Feed (`/changes`)

**Purpose:** Full chronological audit log of all detected competitive changes.

**Components:**
- Auto-refreshing table (every 5 minutes)
- Columns: Timestamp | Competitor | Domain | Field Changed | Old Value | New Value | Severity
- Filters: Competitor | Domain | Severity | Date range
- Export to CSV

---

### 11.6 AI Insights (`/insights`)

**Purpose:** Browse all AI-generated competitive analyses.

**Components:**
- Card grid: one card per competitor showing latest AI insight (logo | 2-line summary | top finding | generated timestamp)
- Click card → full insight modal
- Weekly digest section (AI narrative covering all significant changes in last 7 days)
- Insight history (collapsible list, newest first)

---

### 11.7 Admin (`/admin`)

**Purpose:** Operational control panel.

**Components:**
- **Scraper Status Table:** scraper name | last run time | last run outcome (Success / Failed / Running) | next scheduled run | Manual Trigger button
- **System Logs:** last 100 lines from each scraper log file (tabbed by scraper)
- **Competitor Config:** editable table (name, website URL, tier)
- **Market Config:** activate/deactivate markets

---

## 12. Data Collection Schedule

| Script | Cron (UTC) | What It Does |
|---|---|---|
| `pricing_scraper.py` | `0 2 * * *` | Scrapes pricing pages for all 11 competitors |
| `promo_scraper.py` | `15 2 * * *` | Scrapes promotions pages for all 11 competitors |
| `social_scraper.py` | `30 2 * * *` | YouTube API + Telethon + Playwright (FB/IG/LINE/Zalo) |
| `reputation_scraper.py` | `0 3 * * *` | Trustpilot, FPA, App Stores for all 11 competitors |
| `news_scraper.py` | `15 3 * * *` | Google News RSS for all 11 competitors |
| `ai_analyzer.py` | `30 3 * * *` | Reads that day's change_events → Claude API → ai_insights |

---

## 13. Non-Functional Requirements

| Requirement | Specification |
|---|---|
| **Availability** | Dashboard accessible 24/7; scraper failures must not take down the UI |
| **Resilience** | Each scraper runs independently; one failure does not block others; all errors are logged |
| **Performance** | Dashboard pages load in <3 seconds |
| **Authentication** | Password protection via Next.js middleware (`next-auth` or custom middleware with `.env` credentials). URL: `competitor-intel.pepperstone-asia.live`. EC2 security group allows HTTPS (443) only. |
| **Simplicity** | Every script and component must be readable and editable by a non-professional developer |
| **Graceful degradation** | If a scraper fails for a platform (e.g. Facebook blocks scraping), the dashboard shows "Data unavailable — last updated [date]" rather than an error |
| **Scraping etiquette** | 2–3 second delays between requests. No more than 1 concurrent request per domain. Respect `robots.txt` where feasible. |

---

## 14. Tooling Cost Estimate (MVP)

| Tool | Monthly Cost |
|---|---|
| **Anthropic Claude API** (claude-sonnet-4-6) | ~$50–$150 (usage-based) |
| **AWS EC2 t3.small** | ~$15–$20 |
| YouTube Data API v3 | Free |
| Telethon (Telegram) | Free |
| Google News RSS | Free |
| Playwright + Python | Free |
| Next.js + shadcn/ui + Drizzle | Free |
| **Total MVP** | **~$65–$170/month** |

**Post-MVP additions (when budget approved):**
| Tool | Purpose | Cost |
|---|---|---|
| Owletter / Panoramata | Competitor eDM monitoring | ~$99–$199/month |
| SEMrush Pro | SEO keyword tracking + SEM ad intelligence | ~$120–$229/month |
| Apify | Reliable social media scraping (FB/IG) | ~$49–$99/month |

---

## 15. Implementation Plan — 1-Day Vibecoding Sprint

The full sprint is broken into three sessions. Each session is self-contained — if a session overruns, the next can continue without blockers.

### Morning Session (3–4 hours) — Foundation + UI Shell
- [ ] Initialise Next.js 15 project with Tailwind CSS + shadcn/ui + Drizzle ORM + SQLite
- [ ] Define full database schema and run Drizzle migrations
- [ ] Seed database with all 11 competitors + 12 markets
- [ ] Configure password authentication (Next.js middleware, credentials in `.env`)
- [ ] Build app layout: sidebar navigation + top header
- [ ] Build `/competitors` list page (real seeded data)
- [ ] Build `/competitors/[id]` with 5 tabs: Overview | Pricing | Promotions | Social | Reputation
- [ ] Build `/` Home page shell (placeholders for AI cards + change feed)

### Afternoon Session (3–4 hours) — Scrapers + Data + AI
- [ ] Write `reputation_scraper.py` (Trustpilot + FPA + App Stores, all 11 competitors)
- [ ] Write `news_scraper.py` (Google News RSS, all 11 competitors)
- [ ] Write `pricing_scraper.py` (leverage + min deposit via Playwright, all 11 competitors)
- [ ] Write `promo_scraper.py` (Playwright promotions pages, all 11 competitors)
- [ ] Write `ai_analyzer.py` (reads change_events → Claude API → ai_insights)
- [ ] Connect all Next.js API routes (`/api/*`) to SQLite via Drizzle
- [ ] Render real data on: Reputation tab + Pricing tab + AI Overview tab
- [ ] Build `/changes` change feed page

### Evening Session (2–3 hours) — Social + Deploy + Go Live
- [ ] Write `social_scraper.py` (YouTube Data API + Telethon, all 11 competitors)
- [ ] Complete `/` Home page (AI Top Things cards + data freshness grid)
- [ ] Build `/insights` AI insights page
- [ ] Build `/admin` page (manual scraper triggers + log viewer)
- [ ] Deploy to AWS EC2 t3.small:
  - SSH → install Node.js 20, Python 3.11, Playwright deps (`playwright install-deps`)
  - Clone repo → `npm run build` → `pm2 start`
  - Set up Linux crontab for all 6 scraper scripts
  - Point `competitor-intel.pepperstone-asia.live` DNS → EC2 IP, configure HTTPS (Certbot/nginx)
- [ ] Trigger all scrapers manually → verify data populates in dashboard
- [ ] Smoke test: login → competitors list → competitor detail → change feed

---

## 16. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Facebook/Instagram scraping blocked by Meta | High | Mark as "N/A — Manual check required" in dashboard. Add Apify post-MVP if needed. |
| LINE/Zalo scraping fragility | Medium | Best-effort only. Dashboard shows N/A gracefully. |
| SQLite concurrent write conflict | Low | Run scrapers at staggered cron times + enable SQLite WAL mode |
| Playwright memory usage on t3.small (2GB) | Medium | Run one Playwright instance at a time. Upgrade to t3.medium (~$30/mo) if needed. |
| Playwright missing Chromium deps on fresh EC2 | High | Document `playwright install-deps` in setup guide |
| China/WeChat monitoring gap | Certain | Dashboard shows "Manual monitoring required" for `cn` market |
| Fintrix Markets low public data | Medium | Smaller broker, less public content. Monitor what's available; mark gaps clearly. |
| YouTube API quota (10k units/day) | Low | 11 competitors × ~50 units = ~550 units/day. Well within free tier. |

---

## 17. Resolved Decisions

| Question | Decision |
|---|---|
| Authentication | Password authentication via Next.js middleware. Credentials stored in `.env`. |
| Dashboard URL | `competitor-intel.pepperstone-asia.live` served over HTTPS via nginx + Certbot on EC2 |
| Spreads data | **Excluded from MVP.** Too product-specific and high-volume. Pricing domain tracks leverage and minimum deposit only. |
| Dashboard language | English-only UI. Data is scraped from localised sources (competitor pages in local languages) and displayed/summarised in English via Claude. |

---

*Document prepared by Terence Tan — 16 March 2026*
*PRD v1.1 — Final. Ready for 1-day vibecoding sprint.*

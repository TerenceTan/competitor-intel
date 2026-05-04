# Pepperstone Competitor Analysis Dashboard

## What This Is

Internal marketing intelligence tool that pulls competitor signals (websites, app stores, social media, reviews, AI analysis) into a per-market dashboard for the Pepperstone web/marketing team. Currently at v1.4.1, in maintenance posture while the marketing-portal repo is the team's primary build. Primary audience: marketing managers operating per-market who use it to track competitor promo activity in their region.

## Core Value

**Promo intelligence per market.** If everything else fails, the dashboard must continue to surface what competitors are running for promotions — broken down by market — accurately enough that marketing managers trust it.

## Requirements

### Validated

<!-- Shipped in v1.4.1 and earlier — confirmed working. -->

- ✓ Multi-source competitor data ingestion: websites (Playwright), promos, app store ratings, social, reviews, news (RSS) — existing
- ✓ Per-market views via `?market=<code>` URL filter across all dashboard pages — existing (v1.4)
- ✓ Per-market promos, App Store ratings, and social media views — existing (v1.4, commit fb78ebe)
- ✓ AI portfolio recommendations (Anthropic Claude) synthesizing competitor data into actionable insights — existing
- ✓ Change-event detection and noise-floor filtering across competitor snapshots — existing
- ✓ Auth + security hardening: SHA-256 session tokens, bearer API key validation, fixed-window rate limiting, SSRF guard, CVE patches — existing (v1.4.1)
- ✓ External API surface: `/api/v1/promotions`, `/api/v1/trends` for outside callers and MCP server — existing
- ✓ MCP server exposing competitor intel to LLM clients — existing
- ✓ SQLite + Drizzle ORM persistence with WAL mode, FK constraints, additive migrations on startup — existing
- ✓ EC2 deployment on Node 22 LTS with cron-driven scraper runs — existing

### Active

<!-- This milestone: Localized Promo Intelligence — APAC v1. -->

- [ ] **Replace broken Thunderbit social scraper with Apify** (FB/IG/X actors) for the 8 v1 markets
- [ ] **APAC market coverage v1**: SG, HK, TW, MY, TH, PH, ID, VN — per-market promo + social data flowing into existing per-market views
- [ ] **Better promo extraction**: improve reliability and structuring of detected promos (cleaner fields, fewer misses, language-aware parsing for non-English markets)
- [ ] **Share of Search integration**: nightly BigQuery → SQLite sync of existing SoS data, joined per-market with promo and social data
- [ ] **Per-market AI promo recommendations**: extend the existing AI portfolio synthesis with promo-specific, per-market recommendations marketing managers can act on
- [ ] **Confidence and freshness indicators** in the UI so users can tell trustworthy data from stale/uncertain data (mitigation for the data-quality risk below)

### Out of Scope

<!-- Each exclusion includes the reason so it isn't quietly re-added later. -->

**Markets deferred:**
- Mainland China (CN) — Facebook/Instagram/X are blocked. Needs a separate workstream covering Weibo/Douyin/Xiaohongshu/WeChat with Chinese-language NLP. Different scrapers, different competitors, different complexity. Plan as its own phase later.
- India (IN) — large market with regulatory sensitivity, deferred to v1.5 (next milestone) so we don't dilute APAC v1.
- Mongolia (MN) — too small to justify engineering effort for dedicated coverage.
- AU, UK, EU markets — already covered adequately by global scrapers; localization gap is concentrated in APAC.

**Data sources deferred:**
- SERP rankings (DataForSEO/Semrush) — useful but Share of Search already covers the demand side. Add later if SoS reveals SERP-shaped gaps.
- Website traffic per market (Similarweb) — only credible source is ~$10–30k/year API. Out of budget for a maintenance-mode dashboard. Reconsider if the wider org already licenses Similarweb.
- New affiliate/comparison-site sources, Telegram channels, YouTube market-specific channels — explicitly deferred. Fix the existing social blocker first; widening sources before stabilizing fundamentals just compounds maintenance burden.

**Infrastructure deferred:**
- SQLite → Postgres migration — soft dependency for the marketing-portal cutover, not hard-blocking. Explicit next-milestone candidate. Schema changes in this milestone stay simple to keep migration cost low.
- Marketing-portal cutover work — lives in the `~/Documents/projects/marketing-portal` repo, not this one.

**Approaches considered and rejected:**
- Bright Data social datasets — works but $300+/mo committed cost is overkill for our competitor count and cadence. Apify pay-per-run wins on commitment shape.
- Meta Graph API for competitor pages — only returns public metadata (name, follower count). No post or promo content available for non-owned pages. Worthless for competitive intelligence.
- Self-hosted social scraping with residential proxies — high maintenance, aggressive bot detection, legally grey under time pressure.
- Embedded Looker Studio iframe for SoS — cheap but doesn't allow joining SoS with per-market promo/social data in queries. Loses the most valuable use case.

## Context

**Codebase state (2026-05-04):** Codebase fully mapped at `.planning/codebase/`. Next.js 15.2.4 + React 19 + Drizzle/SQLite + Python scrapers (Playwright, requests, feedparser) + Anthropic Claude for AI analysis. EC2 production runs Node 22 LTS; local dev on Node 25.

**Recent history:** Per-market filtering shipped in v1.4 (commit fb78ebe). Security audit and hardening shipped in v1.4.1 (commit 1c6eb88). Codebase mapping landed in commit fab7a1a. Resolved EC2 security incident mid-April 2026 — instance rebuilt clean. Thunderbit social scraper integrated but broken for FB/IG/X — this milestone replaces it.

**Position in the ecosystem:** Dashboard is in maintenance mode. The marketing-portal repo is the team's primary build target. Work here is justified by stakeholder-visible per-market value (promo intel for APAC) and by avoiding work duplication once the eventual cutover happens.

**Stakeholder pressure:** A marketing stakeholder wants per-market promo deepening soon — this is what tipped the milestone choice toward APAC promo intelligence over Postgres migration.

**Known data-source blocker:** Thunderbit scraping for Facebook, Instagram, X is broken. Until this milestone fixes it, social data on the dashboard is stale or missing for those platforms.

## Constraints

- **Timeline**: Medium milestone (3–6 weeks, 3–5 phases). Time/shipping cadence is the top constraint — stakeholder wants visible value soon. Pragmatic choices beat comprehensive ones when they conflict.
- **Team**: Mostly solo support on the dashboard side (web team is small; primary attention is on marketing-portal). Maintenance burden of 8 markets × multiple scrapers must stay manageable.
- **Tech stack**: Locked to current stack — Next.js 15, React 19, Drizzle/SQLite, Python scrapers, EC2 + cron. No framework or DB swaps in this milestone.
- **Database**: Stays on SQLite for this milestone. Schema additions kept additive and simple to minimize cost of the eventual Postgres migration.
- **Budget**: Apify usage modest (≈ pay-per-run for handful of competitors × weekly cadence). BigQuery read costs minimal at nightly sync cadence. Anthropic costs already budgeted in existing AI flow. No expensive new SaaS subscriptions (Similarweb, Bright Data) this milestone.
- **Deployment**: `npm ci` on EC2, never `npm install` (lockfile drift). All deploys go through the existing pattern.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build APAC promo deepening before Postgres migration | Stakeholder pressure + time constraint + soft (not hard) dependency on migration. Visible value beats invisible infrastructure under cadence pressure. | — Pending |
| Apify (pay-per-run actors) for FB/IG/X | Works today, no commitment, fits time constraint. Bright Data overkill, Graph API yields no useful competitor data, self-hosted scraping too risky. | — Pending |
| Nightly BigQuery → SQLite sync for Share of Search | Looks native, joins with per-market promo/social data in SQL, stays cheap. Beats Looker iframe (no joins) and live BQ-on-render (cost/latency). | — Pending |
| Tier markets — 8 in v1, IN to v1.5, CN as separate workstream, MN deferred | Realistic scope for medium milestone. CN is fundamentally different (Weibo/Douyin/WeChat, Chinese NLP) and shouldn't be bundled. | — Pending |
| Defer SERP rankings, website traffic, new affiliate/Telegram/YouTube sources | Share of Search covers demand side. Stabilize the social fix first; widening sources compounds maintenance burden. Reconsider after milestone. | — Pending |
| Use current dashboard's competitor list as-is for this milestone | Don't re-litigate competitor selection — out of scope for the milestone's actual deliverable. | — Pending |
| Confidence/freshness indicators are in v1, not deferred | Data quality is one of the two top risks for this milestone. Trust degrades fast in marketing dashboards if numbers look wrong. Indicator UX must ship with the data. | — Pending |

## Risks

- **Data quality / accuracy** — wrong numbers in a marketing dashboard kill stakeholder trust faster than missing numbers. Mitigation: confidence/freshness indicators baked into v1, plus extraction-quality monitoring for the new sources.
- **Maintenance burden** — 8 markets × FB + IG + X + per-market URLs + Apify quirks = lots of breakage surface for a mostly-solo support model. Mitigation: lean on Apify managed actors over self-hosted; structured failure modes and retry; only widen sources after fundamentals are stable.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-04 after initialization*

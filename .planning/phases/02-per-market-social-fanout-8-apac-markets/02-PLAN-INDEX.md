# Phase 2 — Plan Index

**Phase:** 02-per-market-social-fanout-8-apac-markets
**Planned:** 2026-05-13
**Goal:** Marketing managers operating in any of the 8 APAC v1 markets can open `/markets/<code>` and see FB/IG/X data scrape-attributed per market, with graceful global fallback.

## Wave Structure

```
Wave 1 (parallel, no deps):
  ├── 02-01  Fix src/lib/markets.ts PRIORITY_MARKETS (8 APAC v1 codes)
  └── 02-02  scrapers/market_config.py — APAC_V1_MARKETS + parse_target_markets + Wave 0 tests

Wave 2 (depends on Wave 1):
  └── 02-03  Refactor scrapers/apify_social.py to thread market_code through every actor call

Wave 3 (depends on 02-01 + 02-03):
  ├── 02-04  Add Digital Presence section to /markets/[code]/page.tsx
  └── 02-05  Extend /admin/data-health with per-market zero-result breakdown
```

## Plan Summary

| ID    | Wave | Title                                                           | Files Modified                                                    | Requirements                                | Autonomous | Tests             |
|-------|------|-----------------------------------------------------------------|-------------------------------------------------------------------|---------------------------------------------|------------|-------------------|
| 02-01 | 1    | Fix PRIORITY_MARKETS to 8 APAC v1 codes                         | src/lib/markets.ts                                                | MARKET-04                                   | yes        | tsc + lint        |
| 02-02 | 1    | APAC_V1_MARKETS + parse_target_markets + Wave 0 unit tests      | scrapers/market_config.py, scrapers/test_apify_social_market.py   | MARKET-01, MARKET-02, MARKET-04             | yes        | stdlib unittest   |
| 02-03 | 2    | Thread market_code through apify_social.py (5 actor calls)      | scrapers/apify_social.py, scrapers/test_apify_social_market.py    | SOCIAL-02, SOCIAL-03, MARKET-01, MARKET-02  | NO (checkpoint:human-verify for 2-market smoke) | mock-Apify integration |
| 02-04 | 3    | /markets/[code] Digital Presence section (competitor-row table) | src/app/(dashboard)/markets/[code]/page.tsx                       | MARKET-03, SOCIAL-02, SOCIAL-03             | yes        | tsc + lint + build |
| 02-05 | 3    | /admin/data-health per-market zero-result breakdown             | src/app/(dashboard)/admin/data-health/page.tsx                    | MARKET-02, SOCIAL-02, SOCIAL-03             | yes        | tsc + lint + build |

## File Ownership (no overlaps within wave)

- **Wave 1:**
  - 02-01 owns: `src/lib/markets.ts`
  - 02-02 owns: `scrapers/market_config.py`, `scrapers/test_apify_social_market.py`
  - Zero overlap → parallel-safe.

- **Wave 2:**
  - 02-03 owns: `scrapers/apify_social.py`, `scrapers/test_apify_social_market.py`
  - Plan 02-03 extends the test file created by 02-02. Sequential by virtue of wave assignment; safe.

- **Wave 3:**
  - 02-04 owns: `src/app/(dashboard)/markets/[code]/page.tsx`
  - 02-05 owns: `src/app/(dashboard)/admin/data-health/page.tsx`
  - Zero overlap → parallel-safe.

## Dependency Graph

```
                            02-01 (markets.ts fix)
                                       │
              ┌────────────────────────┼─────────────────────────┐
              │                        │                          │
              │                  02-02 (market_config.py + parse) │
              │                        │                          │
              │                        ▼                          │
              │                  02-03 (apify_social.py loop)     │
              │                        │                          │
              ▼                        ▼                          ▼
       02-04 (UI: /markets/[code])               02-05 (UI: /admin/data-health)
```

Both Wave 3 plans depend on 02-01 (for the corrected 8-market list) AND 02-03 (for the per-market data flowing into the DB). Their files do not overlap, so they merge in parallel.

## Requirements Coverage Audit

| Requirement | Plan(s) Covering | Notes |
|-------------|------------------|-------|
| SOCIAL-02 (IG Apify scrape) | 02-03, 02-04, 02-05 | Phase 1 already scaffolded IG; Phase 2 threads per-market |
| SOCIAL-03 (X Apify scrape) | 02-03, 02-04, 02-05 | Phase 1 already scaffolded X; Phase 2 threads per-market |
| MARKET-01 (market_config populated OR global fallback) | 02-02, 02-03 | Option C per RESEARCH §2 — global fallback this cycle, per-market handles deferred to Phase 2.1 |
| MARKET-02 (apifyProxyCountry per (competitor, platform, market)) | 02-02, 02-03, 02-05 | Helper + threading + diagnostics |
| MARKET-03 (/markets/[code] displays per-market social with fallback) | 02-04 | Digital Presence section |
| MARKET-04 (all 8 markets load) | 02-01, 02-02 | PRIORITY_MARKETS fix on both TS and Python sides |

All 6 phase requirements covered. Every plan's `requirements` frontmatter field is non-empty.

## Success Criteria → Plan Map (from ROADMAP Phase 2)

| Success Criterion | Closed By |
|-------------------|-----------|
| 1. All 8 APAC markets appear in selector and load without errors | 02-01 (TS markets list), 02-02 (Python markets list), 02-04 (UI renders even on empty data) |
| 2. Per-market views display IG + X alongside FB, attributed at scrape time | 02-03 (proxyConfiguration threading), 02-04 (Digital Presence section) |
| 3. Competitors without per-market data fall back to global; no empty panels | 02-03 (writes both market-specific and global rows), 02-04 (market-first / global-fallback resolver) |
| 4. apifyProxyCountry on every call; apify_run_logs records per-(competitor, platform, market) | 02-03 (threading), 02-05 (diagnostic surface) |

## Operator Setup Gates (carry into SUMMARYs)

Surface these in each plan's SUMMARY as the operator-action checklist:

1. **Apify Starter upgrade** (D2-08 / STATE.md cost ceiling) — REQUIRED before setting `APIFY_MARKETS_ENABLED` with the full 8-market list.
2. **Apify monthly cap bump** — raise from $5 (free tier) to $100 (per D-06) in Apify Console after upgrading.
3. **`.env.local` env var** — `APIFY_MARKETS_ENABLED="sg,hk,tw,my,th,ph,id,vn"` on EC2 after upgrade.
4. **Smoke run** — Plan 02-03 checkpoint requires a 2-market smoke (`APIFY_MARKETS_ENABLED="sg,my"`) for cost-bounded verification before opening the full 8-market fanout.

These setup tasks are NOT plan tasks — they are operator pre-conditions for the feature to activate in production. Code ships safely either way; default behavior (flag empty) preserves Phase 1.

## Out of Scope (deferred, NOT planned here)

- Per-market FB/IG/X handles in `scrapers/config.py` (Option B in RESEARCH §2 / Q1) — deferred to Phase 2.1, gated on observed Option-A failure modes.
- FB cost optimization (swap `apify/facebook-posts-scraper` for `apify/facebook-pages-scraper` only) — STATE.md follow-up optimization, not a Phase 2 deliverable.
- DataSourceBadge extraction to `src/components/shared/` — optional polish per RESEARCH §8.
- Freshness pill / TRUST-02 / TRUST-03 — Phase 5.
- BigQuery SoS / extraction work — Phase 3.
- AI recommendations — Phase 4.

## Risk Register

| Risk | Mitigation |
|------|-----------|
| A1: kaitoeasyapi X actor may not honor proxyConfiguration | Plan 02-03 checkpoint includes a 2-market smoke; if X data is identical across markets, the failure mode is observable in `apify_run_logs.market_code` diagnostics surfaced by Plan 02-05. Phase 2.1 swaps the X actor if needed. |
| A2: Some APAC codes may not be Apify proxy exit countries | Same checkpoint; failure surfaces as `apify_run_logs.status='failed'` per market in Plan 02-05's per-market breakdown. |
| Cost overrun on first per-market run | Feature flag default = `['global']` keeps the free tier safe. Operator sets `APIFY_MARKETS_ENABLED` only after Starter upgrade. Per-call `max_total_charge_usd` caps unchanged from Phase 1. |
| Per-market wall clock exceeds 30-min INFRA-02 budget | RESEARCH.md §3 math: 8 × ~41s = ~5.5min, well inside budget. Serial loop, no asyncio (anti-pattern). |

## Phase Exit Criteria

Phase 2 is COMPLETE when:
1. All 5 plans (02-01..02-05) have shipped + SUMMARY.md files.
2. Plan 02-03 operator checkpoint shows the 2-market smoke writing `apify_run_logs` rows with `market_code` ∈ {'sg', 'my'}.
3. ROADMAP Phase 2 success criteria 1-4 manually verified by visiting `/markets/sg`, `/markets/my`, etc.
4. Plan 02-05's per-market badge appears on `/admin/data-health` for at least one scraper after a real per-market run.
5. ROADMAP Phase 2 marked complete; STATE.md updated.

After Phase 2 lands, the operator can choose to:
- Flip `APIFY_MARKETS_ENABLED` to the full 8-market list (production activation).
- Roll back by unsetting the env var (returns to Phase 1 global-only behavior, no code change needed).

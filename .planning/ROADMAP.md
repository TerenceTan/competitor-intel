# Roadmap: APAC Localized Promo Intelligence v1

**Milestone:** Localized Promo Intelligence — APAC v1 (8 markets: SG, HK, TW, MY, TH, PH, ID, VN)
**Created:** 2026-05-04
**Granularity:** coarse (5 phases)
**Parallelization:** enabled — Phase 3 (BigQuery + extraction track) is independent of Phases 1–2 social work

## Overview

This milestone replaces the broken Thunderbit social pipeline with Apify, fans social and promo data out across the 8 APAC v1 markets, joins Share of Search data per market via a nightly BigQuery → SQLite sync, layers grounded per-market AI promo recommendations on top, and lands the confidence/freshness UX needed to keep marketing managers' trust as new data sources come online. The journey: restore broken social → cover all 8 markets → enrich with SoS + cleaner extraction → synthesize into actionable per-market recs → polish the trust UX. Phase 1 doubles as the cross-cutting infrastructure phase — every maintenance scaffold (healthchecks, version pinning, log redaction, run timeouts, additive schema, trust-UX skeleton) lands here so it doesn't have to be retrofitted across 3 platforms × 8 markets later.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Foundation — Apify + Scaffolding + Trust Schema** - Replace broken Thunderbit with pinned Apify actors for one market end-to-end, install all maintenance scaffolding, land the trust-UX schema and skeleton Data Health page
- [ ] **Phase 2: Per-Market Social Fanout (8 APAC Markets)** - Fan FB/IG/X scrapes across SG, HK, TW, MY, TH, PH, ID, VN with per-market URL/handle attribution at scrape time
- [ ] **Phase 3: BigQuery SoS Sync + Better Promo Extraction** - Nightly BigQuery → SQLite Share of Search sync, plus multilingual confidence-scored promo extraction with currency normalization and disclaimer stripping
- [ ] **Phase 4: Per-Market AI Promo Recommendations** - Grounded, structured, per-market AI promo recommendations with snapshot-ID citations and bounded action verbs
- [ ] **Phase 5: Confidence & Freshness UX Polish** - Per-row freshness pills, hover tooltips, and full Data Health page completing the v1 data-trust contract

## Phase Details

### Phase 1: Foundation — Apify + Scaffolding + Trust Schema
**Goal**: Marketing managers see fresh, non-stale Facebook/Instagram/X follower and post data on the dashboard for the global market for the first time since Thunderbit broke; every silent-failure mode that would erode their trust later is closed before any APAC data flows.
**Depends on**: Nothing (first phase)
**Requirements**: SOCIAL-01, SOCIAL-04, SOCIAL-05, SOCIAL-06, INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, TRUST-01, TRUST-04, TRUST-05, EXTRACT-05
**Success Criteria** (what must be TRUE):
  1. The dashboard shows non-stale Facebook follower/post data for at least one competitor in the global market, sourced from a pinned Apify actor (no `:latest` tags) — verifiable on the existing social view
  2. When an Apify actor returns zero results, the dashboard renders an `<EmptyState reason="scraper-failed">` (visually distinct from "no competitor activity") and a `change_events` row of type `scraper_zero_results` exists — silent success is impossible
  3. A Data Health page at `/admin/data-health` lists every scraper, its last successful run timestamp, zero-result counts (last 7 days), and Apify cost-to-date — giving the team a single triage surface from day one
  4. A scheduled scraper run that hangs longer than 30 minutes is killed by `run_all.py` and other scrapers continue; a healthcheck ping confirms each scheduled job's success within hours, not days
  5. A 20–30-item hand-labeled calibration set per non-English language (TH, VN, TW, HK, ID) exists in the repo with measured extraction accuracy — markets failing the ≥85% bar are flagged before Phase 3 goes live
**Plans**: 6 plans

Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Schema deltas (apify_run_logs + share_of_search_snapshots tables; extraction_confidence columns) + Drizzle mirror + apify-client pin
- [x] 01-02-PLAN.md — Log redaction filter (scrapers/log_redaction.py) + unit tests; foundation for safe Apify scraper logging
- [x] 01-06-PLAN.md — EXTRACT-05 calibration set (JSONL) + per-language accuracy validator (parallelizable; deferrable per D-21)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-03-PLAN.md — Apify FB scraper (scrapers/apify_social.py) with zero-result guard + apify_run_logs writes; SCRAPERS constant updated

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 01-04-PLAN.md — run_all.py hardening: per-scraper timeout (1800s) + Healthchecks.io ping helper; apify_social.py registered in SCRIPTS
- [ ] 01-05-PLAN.md — EmptyState extension (scraper-failed variant) + /admin/data-health page + remove FB Thunderbit code from social_scraper.py

### Phase 2: Per-Market Social Fanout (8 APAC Markets)
**Goal**: Marketing managers operating in any of the 8 APAC v1 markets (SG, HK, TW, MY, TH, PH, ID, VN) can open `/markets/<code>` and see Facebook, Instagram, and X data that is genuinely market-specific — not global content guessed at by content inference — for the competitors that have a per-market presence, with clean fallback for those that don't.
**Depends on**: Phase 1
**Requirements**: SOCIAL-02, SOCIAL-03, MARKET-01, MARKET-02, MARKET-03, MARKET-04
**Success Criteria** (what must be TRUE):
  1. All 8 APAC markets (SG, HK, TW, MY, TH, PH, ID, VN) appear in the market selector and load competitor social data without errors
  2. Per-market views display Instagram and X data alongside Facebook, all attributed at scrape time via per-market URLs/handles (not inferred from post content)
  3. Competitors with no per-market handle for a platform fall back gracefully to `global` data — no empty panels, no double-counting against a competitor with a real per-market account
  4. Each Apify call uses `apifyProxyCountry: <market_code>` so geo-routed competitor pages return market-correct content; `apify_run_logs` records per-(competitor, platform, market) diagnostics for triage
**Plans**: TBD
**UI hint**: yes

### Phase 3: BigQuery SoS Sync + Better Promo Extraction
**Goal**: Marketing managers can see, on each per-market view, whether competitor promo activity correlates with Share of Search demand changes — driven by clean, multilingual, confidence-scored promo data and a nightly BigQuery sync that costs cents, not thousands. (This phase runs as an independent track from Phases 1–2 and can be developed in parallel by a second contributor; merge sequencing only matters at the schema/run_all.py touch points already landed in Phase 1.)
**Depends on**: Phase 1 (schema deltas + calibration set already in place)
**Requirements**: SOS-01, SOS-02, SOS-03, SOS-04, SOS-05, EXTRACT-01, EXTRACT-02, EXTRACT-03, EXTRACT-04
**Success Criteria** (what must be TRUE):
  1. A nightly BigQuery → SQLite sync populates `share_of_search_snapshots` with column-explicit, partition-filtered queries; re-running the same day's sync overwrites cleanly without duplicating rows
  2. Per-market views display a Share-of-Search-vs-promo correlation panel joining SoS and promo data on `(market_code, period_start)` — the killer view that justified this approach over a Looker iframe
  3. Promo extraction in non-English markets (TH, VN, TW, HK, ID) returns structured promos with original-locale currency + USD-equivalent, regulatory disclaimer text excluded from the body, and a `confidence: high|medium|low` field on every extracted promo
  4. BigQuery custom project quotas (10 GB/query, 100 GB/day) are configured and visibly enforced — making the documented $10k/22sec runaway physically impossible
**Plans**: TBD
**UI hint**: yes

### Phase 4: Per-Market AI Promo Recommendations
**Goal**: When a marketing manager opens their market's view, they see specific, citation-backed, action-tagged AI recommendations they could forward to a regional director without editing — generated from real per-market promo, social, and SoS data, not invented prose.
**Depends on**: Phase 3 (SoS data and clean extraction strongly recommended for recommendation quality)
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05, AI-06
**Success Criteria** (what must be TRUE):
  1. Each per-market view (`/markets/[code]`) displays the latest AI recommendations for that market with linked snapshot citations users can click through to verify
  2. Every AI recommendation includes a non-empty `supporting_snapshot_ids[]` array — recommendations missing this field are rejected at the schema level, not displayed
  3. A market with fewer than 3 supporting snapshots in the last 7 days returns "insufficient data" instead of generating a recommendation — no hallucinated recs on thin data
  4. Every recommendation's `suggested_action` is one of `match | counter | ignore | investigate` — vague verbs like "monitor" or "consider" are impossible by schema
  5. Re-running generation against the same data produces the same recommendation (Batch API, `temperature: 0`, cache keyed by `(market_code, generation_date)`) — no jittery output between page loads
**Plans**: TBD
**UI hint**: yes

### Phase 5: Confidence & Freshness UX Polish
**Goal**: Every panel showing scraper-derived data on every per-market view carries a freshness pill and surfaces source/scrape metadata on hover — turning the trust contract that's been quietly building since Phase 1 into something marketing managers can see, point to, and explain to their stakeholders.
**Depends on**: Phases 1–4 (schema and empty-state from Phase 1; data and recs from Phases 2–4)
**Requirements**: TRUST-02, TRUST-03
**Success Criteria** (what must be TRUE):
  1. Every promo, social, and Share-of-Search panel on every per-market view displays a freshness pill (GREEN <24h / YELLOW 1–7d / RED >7d-or-failed)
  2. Hovering or tapping any data row reveals scrape time, source URL, and parse status — managers can verify before acting on a data point
  3. Freshness thresholds and visual styling are consistent across panels (no "amber on this page, yellow on that page" drift)
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5
Phase 3 may overlap with Phase 2 in execution if a second contributor is available (parallelization enabled in config).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation — Apify + Scaffolding + Trust Schema | 5/6 | In progress (Wave 3: 01-04 done, 01-05 pending) | - |
| 2. Per-Market Social Fanout (8 APAC Markets) | 0/TBD | Not started | - |
| 3. BigQuery SoS Sync + Better Promo Extraction | 0/TBD | Not started | - |
| 4. Per-Market AI Promo Recommendations | 0/TBD | Not started | - |
| 5. Confidence & Freshness UX Polish | 0/TBD | Not started | - |

---
*Roadmap created: 2026-05-04*

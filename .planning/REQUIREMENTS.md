# Requirements: APAC Localized Promo Intelligence v1

**Defined:** 2026-05-04
**Core Value:** Promo intelligence per market — competitor promo activity, broken down by market, accurate enough that marketing managers trust it.
**Milestone scope:** 8 APAC markets (SG, HK, TW, MY, TH, PH, ID, VN). Brownfield additions to v1.4.1 dashboard.

## v1 Requirements

### Social Scraping (Apify cutover)

Replaces broken Thunderbit integration. Apify managed actors with version pinning, zero-result detection, and per-actor cost tracking.

- [ ] **SOCIAL-01**: System scrapes competitor Facebook posts via pinned Apify actor (`apify/facebook-posts-scraper`) and writes results to `social_snapshots`
- [ ] **SOCIAL-02**: System scrapes competitor Instagram posts via pinned Apify actor (`apify/instagram-scraper`) and writes results to `social_snapshots`
- [ ] **SOCIAL-03**: System scrapes competitor X (Twitter) posts via pinned Apify actor (`apidojo/tweet-scraper`) and writes results to `social_snapshots`
- [ ] **SOCIAL-04**: When an Apify actor returns zero results, system writes a `change_events` row typed `scraper_zero_results` and does NOT insert a snapshot — preventing silent-success failures from looking like fresh data
- [ ] **SOCIAL-05**: System logs each Apify run to `apify_run_logs` with actor ID, version, market_code, dataset count, cost, and run status — enabling Data Health diagnostics
- [ ] **SOCIAL-06**: Apify integration uses pay-per-run actors (no `:latest` tags); a monthly spending cap is enforced in the Apify console before first scheduled run

### Per-Market Coverage (APAC fanout)

Per-market FB/IG/X data flows into existing per-market views for 8 APAC markets. Market attribution at scrape time via per-market URLs/handles, not inferred from content.

- [ ] **MARKET-01**: `competitors.market_config` JSON is populated with per-market social handles (or `global` fallback) for each in-scope competitor across the 8 APAC markets
- [ ] **MARKET-02**: Scrapers run one Apify call per (competitor, platform, market) tuple using `apifyProxyCountry: <market_code>` to fetch geo-correct content
- [ ] **MARKET-03**: Per-market dashboard views (`/markets/[code]`) display social data filtered by `market_code`, falling back to `global` when no per-market handle exists for a competitor
- [ ] **MARKET-04**: All 8 markets (SG, HK, TW, MY, TH, PH, ID, VN) appear in the market selector and load competitor social/promo data without errors

### Promo Extraction (multilingual + reliability)

Better promo extraction with confidence scoring, currency normalization, and language-aware parsing for non-English markets.

- [ ] **EXTRACT-01**: Promo extraction uses Claude Sonnet 4.6 with strict tool-use schema; outputs include a `confidence: high|medium|low` field per promo
- [ ] **EXTRACT-02**: Extraction handles non-English markets (TH, VN, TW, HK, ID) — single language per call, native-language context in system prompt, no preprocessing translation
- [ ] **EXTRACT-03**: Extracted promos store original-locale currency code and amount alongside a normalized USD-equivalent for cross-market comparison
- [ ] **EXTRACT-04**: Regulatory disclaimer text (MAS, SFC, FSC, etc.) is detected and excluded from the promo body before extraction to reduce signal dilution
- [ ] **EXTRACT-05**: Extraction calibration: a 20–30 item hand-labeled set per non-English language is used during Phase 1 to validate ≥85% accuracy; markets failing the bar are flagged for prompt iteration before going live

### Share of Search (BigQuery sync)

Nightly BigQuery → SQLite sync makes Share of Search data joinable with promo and social data per market in the dashboard.

- [ ] **SOS-01**: A new SQLite table `share_of_search_snapshots` stores SoS data with columns for `market_code`, `competitor_id`, `period_start`, `period_end`, `share_pct`, `volume`, `data_source`, `synced_at`
- [ ] **SOS-02**: A nightly Python script (`scrapers/share_of_search_sync.py`) queries BigQuery using `@google-cloud/bigquery` (or Python equivalent), with column-explicit SELECT and partition-column WHERE — never `SELECT *`
- [ ] **SOS-03**: BigQuery sync is idempotent: re-running the same day's sync overwrites without duplicating; uses `INSERT OR REPLACE` keyed on `(market_code, competitor_id, period_start)`
- [ ] **SOS-04**: BigQuery project-level custom quota is configured before first run: 10 GB per query, 100 GB per day — hard cap to prevent the documented $10k/22sec cost runaway
- [ ] **SOS-05**: Per-market dashboard views display a SoS-vs-promo correlation panel — joining `share_of_search_snapshots` and `promo_snapshots` by `(market_code, period_start)` to show whether promo activity correlates with search demand changes

### AI Recommendations (per-market, grounded)

Per-market AI promo recommendations grounded in snapshot IDs, with structured outputs and cost discipline.

- [ ] **AI-01**: AI recommendation prompt is per-market (one Claude call per market per generation cycle), not global — caps context size and prevents recommendation drift across markets
- [ ] **AI-02**: AI output schema requires `supporting_snapshot_ids[]` (non-empty array of `promo_snapshots`/`social_snapshots`/`share_of_search_snapshots` IDs); outputs missing this field are rejected
- [ ] **AI-03**: AI recommendations require ≥3 supporting snapshots from the last 7 days for the target market; insufficient data returns "insufficient data" rather than generating
- [ ] **AI-04**: AI output schema constrains `suggested_action` to one of `match | counter | ignore | investigate` — vague verbs ("monitor", "consider") are rejected at the schema level
- [ ] **AI-05**: AI recommendations are cached in `ai_recommendations` keyed by `(market_code, generation_date)` with `temperature: 0` and Anthropic Batch API for nightly runs; same data → same recommendation
- [ ] **AI-06**: Each per-market dashboard view (`/markets/[code]`) displays the latest AI recommendations for that market with linked snapshot citations

### Trust UX (confidence + freshness)

Confidence and freshness indicators baked in from Phase 1 as a v1 data-trust contract, not Phase 5 polish.

- [ ] **TRUST-01**: `extraction_confidence TEXT` column added to `promo_snapshots` and `social_snapshots`; scrapers populate it at insert time (no backfill is feasible)
- [ ] **TRUST-02**: Per-market dashboard views display a freshness pill (GREEN <24h / YELLOW 1–7d / RED >7d-or-failed) on every promo, social, and SoS panel
- [ ] **TRUST-03**: Each row hover/tooltip exposes scrape time, source URL, parse status — letting marketing managers verify before acting on a data point
- [ ] **TRUST-04**: Scraper-failed rows render an `<EmptyState reason="scraper-failed">` component, visually distinct from "no competitor activity" — preventing confusion of silent failure with genuine inactivity
- [ ] **TRUST-05**: A Data Health page (`/admin/data-health`) lists per-scraper status, last successful run, zero-result counts (last 7 days), and Apify cost-to-date — operational triage surface for the team

### Maintenance Infrastructure (cross-cutting, Phase 1)

Maintenance scaffolding that must land before any new scrapers go live. Retrofitting after data flows means doing this work across 3 platforms × 8 markets.

- [ ] **INFRA-01**: Each scheduled scraper job pings a healthcheck endpoint (Healthchecks.io or equivalent) on success — silent cron failures are detected within hours, not days
- [ ] **INFRA-02**: `run_all.py` orchestration enforces a per-scraper timeout (30-min hard cap) and continues to other scrapers if one hangs — no single scraper can block the whole pipeline
- [ ] **INFRA-03**: All scraper logs use a redaction filter that strips API keys, tokens, and credentials before writing — non-negotiable per the EC2 security incident history
- [ ] **INFRA-04**: BigQuery service-account credentials are stored in `.env.local` only, never committed; key rotation procedure is documented in the team runbook
- [ ] **INFRA-05**: All schema changes in this milestone are additive (new tables / new columns with defaults / no FK changes to existing tables) to keep the future SQLite → Postgres migration cost low

## v2 Requirements

Deferred to v1.5 (next milestone) or later. Tracked but not in current roadmap.

### India Market (v1.5)

- **INDIA-01**: Add IN to the market selector and scraper coverage
- **INDIA-02**: Validate Hindi/regional-language extraction quality for IN-specific competitor pages

### China Workstream (separate milestone)

- **CN-01**: Replace Apify-based FB/IG/X scrapers with Weibo/Douyin/Xiaohongshu/WeChat equivalents for mainland China
- **CN-02**: Add Chinese-language NLP layer if Claude extraction quality on simplified Chinese promo pages falls below the 85% bar
- **CN-03**: Per-market view for CN with appropriate competitor list (some competitors only operate in CN)

### Counter-Promo Suggestion (deferred from this milestone)

- **AI-07**: AI generates concrete counter-promo suggestions (e.g., "AUD/USD spread reduction promo for THB-funded accounts in TH for 2 weeks") — explicit dial cut from v1 due to time-pressure scope discipline; revisit when data quality and rec acceptance are validated

## Out of Scope

Explicitly excluded for this milestone. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| AU/UK/EU markets | Already covered adequately by global scrapers; localization gap is concentrated in APAC |
| Mongolia (MN) | Too small to justify engineering effort for dedicated coverage |
| SERP rankings (DataForSEO/Semrush) | Share of Search already covers the demand side; reconsider if SoS reveals SERP-shaped gaps |
| Website traffic per market (Similarweb) | Only credible source ~$10–30k/yr API; out of budget for maintenance-mode dashboard |
| New affiliate / Telegram / YouTube sources | Stabilize the social fix first; widening sources before fundamentals are stable compounds maintenance burden |
| SQLite → Postgres migration | Soft (not hard) dependency on marketing-portal cutover; deferred to next milestone |
| Marketing-portal cutover work | Lives in `~/Documents/projects/marketing-portal` repo, not this one |
| Bright Data social datasets | $300+/mo committed cost overkill for our competitor count and cadence |
| Meta Graph API for competitor pages | Returns no useful competitor post or promo content for non-owned pages |
| Self-hosted social scraping with residential proxies | High maintenance, aggressive bot detection, legally grey under time pressure |
| Looker Studio iframe for SoS | Cannot join SoS with per-market promo/social data in queries — loses the most valuable use case |
| Hashtag clustering / sentiment / OCR on social posts | Anti-features per FEATURES.md — scope inflation without proportional value |
| Real-time alerting (push/email/Slack) | Considered separately; current milestone is about data depth, not notification |

## Traceability

To be populated by gsd-roadmapper after roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (Populated by roadmapper) | — | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: TBD (set by roadmapper)
- Unmapped: TBD

---
*Requirements defined: 2026-05-04*
*Last updated: 2026-05-04 after initial definition*

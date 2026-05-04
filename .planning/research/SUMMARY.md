# Research Summary — APAC Localized Promo Intelligence v1

**Project:** Pepperstone Competitor Analysis Dashboard — APAC Promo Intelligence milestone
**Domain:** Brownfield competitor intelligence dashboard (8 APAC markets, forex broker monitoring)
**Researched:** 2026-05-04
**Confidence:** HIGH on stack and architecture; MEDIUM on Apify cost projections and TH/VN/TW/HK language quality

---

## TL;DR

- **The social scraper fix is the critical-path gate.** Every per-market social, engagement, and promo-mention feature is blocked until `apify_social.py` replaces the broken Thunderbit integration. Phase 1 is unconditional.
- **Phase 1 must also install all maintenance scaffolding** (zero-result detection, healthchecks, actor version pinning, spending cap, log-redaction, scraper timeout). Retrofitting this after real data flows means doing it across 3 platforms × 8 markets — triple the work. These are not polish items.
- **BigQuery sync (Phase 3) is independent of social (Phases 1–2)** and its schema migration can land in the same Phase 1 PR, saving an EC2 deploy cycle and keeping the SoS-vs-promo correlation view on track.
- **The five-phase order in ARCHITECTURE.md and PITFALLS.md is consistent.** The only reconciliation needed: PITFALLS.md labels its concern blocks using its own numbering (B-series as "Phase 2 BigQuery", C-series as "Phase 3 extraction"), while ARCHITECTURE.md numbers BigQuery as Phase 3 in build order. Follow ARCHITECTURE.md's build order numbering — BigQuery sync is Phase 3, after per-market social fanout (Phase 2).
- **Confidence/freshness UX belongs in Phase 1 as a skeleton, not Phase 5 as an afterthought.** The `<EmptyState reason="scraper-failed">` component and skeleton Data Health page must exist before data flows, or silent scraper failures are indistinguishable from genuine competitor inactivity.

---

## Headline Decisions

**1. Python-only scraper layer; no Node.js scraping path added.**
ARCHITECTURE.md is unambiguous: adding Node.js scraping for one integration in a maintenance-mode, mostly-solo codebase violates the maintenance-burden constraint. All new ingestion (`apify_social.py`, `share_of_search_sync.py`) stays in `scrapers/` alongside existing Python scrapers. The only new npm dependency is `@google-cloud/bigquery`. Rationale: one toolchain, shared `db_utils.py` infrastructure, no second write path to SQLite.

**2. Apify managed actors over self-hosted scraping; pay-per-result over committed subscription.**
Three actors: `apify/instagram-scraper`, `apify/facebook-posts-scraper`, `apidojo/tweet-scraper`. Projected steady-state ~$35–50/month on an Apify Starter plan. Bright Data ($300+/mo committed) and Meta Graph API (no competitor post content) are confirmed non-starters. Residential proxies with per-market country targeting (`apifyProxyCountry: <market_code>`) are included in actor pricing — no separate proxy configuration needed.

**3. Apify actor calls must pin version and assert non-empty results from day one.**
Never use `:latest`. Actor output schemas change between minor versions, causing silent null fields. Equally critical: Apify returns `status: SUCCEEDED` with an empty dataset when geo-blocked or selector-broken. Every actor call must assert `dataset.itemCount > 0`; zero results write a `change_events` row typed `scraper_zero_results` and do not insert a snapshot.

**4. BigQuery sync via plain Python script + EC2 system crontab; no n8n, no Airflow, no node-cron.**
STACK.md and ARCHITECTURE.md agree. Pattern mirrors existing scrapers. The BQ query must be column-explicit (never `SELECT *`), use the partition column in WHERE, and be validated with a dry run before first production execution. A custom BigQuery project-level quota of 10 GB per query / 100 GB per day is mandatory before the first scheduled run.

**5. Claude Sonnet 4.6 with tool-use (strict schema) handles all multilingual extraction; no separate NLP layer.**
Benchmarks: Indonesian 97.3%, Chinese 96.9%, Korean 96.7%, Japanese 96.8% relative to English MMLU. Thai, Vietnamese, Traditional Chinese are not directly benchmarked but expected in the 90%+ range for structured extraction. Use tool-use (not raw JSON-in-prompt), single language per call, explicit native-language context in the system prompt, and a `confidence: "high"|"medium"|"low"` field in the extraction schema. spaCy, Google Translate preprocessing, and per-language model forks are all rejected.

**6. Market attribution happens at scrape time (one Apify run per market), not inferred from post content.**
When you fetch `competitor.com/sg/en/` you get different content than `competitor.com/global/en/`. Market is a property of the URL fetched. For competitors with no per-market social account, record one row with `market_code = 'global'` and let per-market views fall back to it — the same fallback pattern already used in `pricing_snapshots`. This decision determines the `apify_run_logs` table shape and cost envelope.

**7. Confidence/freshness UX is a v1 data-trust contract, not a polish layer.**
PROJECT.md names data quality as one of the two top milestone risks. PITFALLS.md documents the failure mode explicitly: silent empty rows from a broken scraper look identical to "competitor has no promos." The minimum Phase 1 footprint — scraper-failed empty state, market-aware stale-data banner, `extraction_confidence` column on `promo_snapshots` and `social_snapshots`, skeleton Data Health page — must be present before data flows through new scrapers. Full badge polish is Phase 5; the schema and empty-state logic are Phase 1.

**8. Per-market AI recommendations must be grounded in snapshot IDs, use per-market prompts, and enforce a 7-day window cap.**
PITFALLS.md quantifies the gap: $5–10/month disciplined vs. $26k/month naive (200× difference). Every recommendation must include `supporting_snapshot_ids[]`; outputs missing this field are rejected. Fewer than 3 snapshots for a market in the last 7 days returns "insufficient data" rather than generating. Use `temperature: 0`, Batch API for nightly runs, outputs cached in `ai_recommendations` keyed by `(market, generation_date)`. The counter-promo suggestion sketch (L-complexity) is the first scope dial to cut under time pressure.

---

## Recommended Phase Shape

| Phase | Name | Primary Deliverable | Key Risks Addressed | Parallelization Opportunities |
|-------|------|---------------------|---------------------|-------------------------------|
| **1** | Foundation: Apify + Scaffolding | Working FB/IG/X data for global market; all maintenance infrastructure installed | A1 (zero-result silent success), A2 (actor versioning), A4 (Apify cost runaway), F1 (silent cron), F5 (run_all fragility), F6 (log leaks), D2 (failed vs stale — skeleton) | Schema deltas 1+2+4 (social) and BQ schema delta (SoS table) land in one PR; market config research runs alongside coding |
| **2** | Per-market Social Fanout | Per-market views show market-specific FB/IG/X data for all 8 APAC markets | C1 (wrong locale/proxy), A3 (anti-bot degradation), F3 (SQLite migration drift on EC2) | Market config research (which competitor has per-market vs. global account) is the long pole — done by a human while Phase 1 code is reviewed |
| **3** | BQ SoS Sync + Better Promo Extraction | SoS data joins with promo/social per-market; language-aware extraction for non-English markets | B1 (BQ scan cost), B2 (timezone), B3 (idempotency), B5 (BQ schema drift), C2 (currency normalization), C3 (disclaimer dilution), C4 (mixed script), C5 (date formats) | BQ ETL script and promo extraction improvements are in different files; can alternate in the same sprint |
| **4** | Per-market AI Recommendations | AI insights panel on each market page with structured, grounded, market-specific recs | E1 (hallucination), E2 (context blowup), E3 (drift), E4 (generic recos) | Phase 4 prompt design can be drafted during Phase 3 validation; building waits on real per-market promo data |
| **5** | Confidence/Freshness UX Polish | Full confidence badge and freshness pill on every panel; Data Health page complete | D1 (indicator noise), D3 (inconsistent thresholds) | UI components can be built alongside Phase 4; they read from columns present since Phase 1 |

**Phase ordering rationale:**

- **Phase 1 before Phase 2:** Apify must work end-to-end for one market before fanning to 8. Phase 2's long pole (market config research) runs concurrently.
- **Phase 3 after Phase 1:** The BQ sync and promo extraction improvements both write to tables (`share_of_search_snapshots`, `promo_snapshots`) whose schema is stabilized in Phase 1. Running Phase 3 concurrently with Phase 1 creates merge conflicts on `db_utils.py`.
- **Phase 4 after Phase 3:** SoS data is a strong-preference prerequisite for AI recs quality. Technically optional but explicitly flagged by ARCHITECTURE.md as "strongly recommended." Ship Phase 3 first; prompt design for Phase 4 can happen in parallel.
- **Phase 5 after Phase 1 (full build after Phases 1–4):** The confidence badge schema lands in Phase 1. Phase 5 just renders what's stored. Can overlap with Phase 4 for the UI components that don't depend on Phase 4 data.

**Where ARCHITECTURE.md and PITFALLS.md diverge — reconciliation:**
PITFALLS.md uses its own phase numbering (B1–B5 as "Phase 2 BigQuery", C1–C5 as "Phase 3 extraction"). ARCHITECTURE.md numbers them as Phase 3 (BQ) and includes per-market extraction inside Phase 3 as well. This is a labeling difference only — no substantive disagreement about what belongs together or why. Follow ARCHITECTURE.md's build-order numbering throughout the roadmap.

---

## Cross-Cutting Requirements

Must land in **Phase 1** even though their full feature surface lives in a later phase:

| Requirement | Why Phase 1 | Later phase it enables |
|-------------|-------------|------------------------|
| `extraction_confidence TEXT` column on `promo_snapshots` and `social_snapshots` | Scrapers must write confidence at insert time; cannot backfill meaningfully | Phase 5 confidence badge UI |
| `apify_run_logs` table | Per-actor diagnostics for zero-result detection and cost tracking; must exist on the first run | Phase 2 debugging; Phase 5 Data Health page |
| Zero-result detection: assert `dataset.itemCount > 0` after every actor call | Without this, geo-blocked or selector-broken runs appear as fresh data | Phase 5 scraper-failed empty state |
| Healthcheck ping per scheduled job (dead-man's-switch) | Silent cron failures are undetectable without this; retroactive installation means days of blind gaps | All subsequent phases |
| Per-scraper timeout in `run_all.py` (30-min hard cap) | New Apify scraper is the highest-risk hang candidate in the pipeline | All subsequent phases |
| Apify monthly spending cap in Apify console ($100/month) | Must be set before the first production-scheduled run; not retroactive | Phase 2 cost safety |
| Skeleton Data Health page (queries `scraper_runs` only) | Gives the team a triage surface from day one; full polish is Phase 5 but the page shell pays back immediately | Phase 5 Data Health polish |
| Actor version pinned (not `:latest`) | Schema drift from actor updates is introduced at Phase 1 and cannot be undone after rows are corrupted | All social feature phases |
| BQ `share_of_search_snapshots` schema delta in Phase 1 PR | Amortizes EC2 deploy cycle; table exists before Phase 3 code references it | Phase 3 BQ sync |
| Log redaction filter (no API keys in scraper log output) | EC2 security incident history makes this non-negotiable for any new external API integration | Ongoing |

---

## Open Questions

**1. How many competitors actually have per-market FB/IG/X accounts vs. a single global account?**
STACK.md flags this explicitly: most forex brokers run one global account. If true for our competitor list, the "8 markets × 3 platforms" matrix collapses to "≤12 social handles per competitor regardless of market count," saving 5–8× on Apify costs and significantly simplifying Phase 2. Verify by manually checking 4–5 primary competitors before Phase 1 kicks off.

**2. What is the exact BigQuery table name, dataset, project ID, and partition column for the SoS data?**
ARCHITECTURE.md and STACK.md use placeholder names. The correct values, partition strategy, and whether the table is already partitioned must be confirmed with the data team before Phase 3 begins. Without partition confirmation, the dry-run cost gate cannot work.

**3. Does the data team maintain a fixed schema for the SoS BigQuery table, and who owns breaking changes?**
The sync will hash the column list and fail loudly on schema drift — but that requires a human response. Agree up front: who is notified when the schema hash changes, and what is the SLA for acknowledging a blocked sync?

**4. Which 4–5 competitors are in scope for APAC v1, and are their per-market social handles documented?**
PROJECT.md says "use the current competitor list as-is" but Phase 2 requires populating `competitors.market_config` JSON with per-market social handles. This is a human research task, not a code task, and it is the long pole in Phase 2.

**5. Has any language-detection validation been done on sample TH/VN/TW/HK promo pages?**
STACK.md rates Claude's Thai and Vietnamese capability as MEDIUM confidence. Recommend a 20–30-item hand-labeled calibration set per unvalidated language during Phase 1, before committing to Phase 3's extraction pipeline. If quality falls below ~90%, the extraction approach for those markets needs adjustment.

**6. Is `run_all.py` the primary cron entry, or do individual scrapers already have independent cron lines?**
PITFALLS.md F5 flags `run_all.py` as a single-point-of-failure. Clarify EC2 crontab structure before Phase 1 refactors the orchestration. If individual scrapers already have independent cron lines, the refactor scope changes.

**7. What is the Anthropic API billing ceiling for this project?**
PITFALLS.md E2 documents a 200× cost gap between disciplined and naive AI rec generation. Disciplined approach is ~$5–30/month on top of existing `ai_analyzer.py` usage. Confirm the current ceiling accommodates this before Phase 4 starts.

---

## Confidence Map

| Area | Confidence | Notes |
|------|------------|-------|
| Stack — Apify actors and SDK versions | HIGH | Actor slugs and SDK versions verified directly against Apify Store, PyPI, and npm on 2026-05-04 |
| Stack — BQ SDK and cron pattern | HIGH | `@google-cloud/bigquery` 8.3.0 verified; cron-over-node-cron is industry consensus for EC2 maintenance-mode |
| Stack — Apify monthly cost projection | MEDIUM | Depends on per-market vs. global account reality (Open Question 1); verify after first 2 weeks |
| Stack — Claude TH/VN/TW/HK extraction quality | MEDIUM | Not benchmarked by Anthropic; expected 90%+ by pattern; needs calibration set |
| Features — table stakes (promo display, confidence UX, social engagement) | HIGH | Validated against mature CI tools and codebase ground truth |
| Features — AI rec quality bar | MEDIUM | Quality depends on grounding quality; "would a manager forward this unedited?" is the right test but requires live data |
| Architecture — scraper layer placement and schema deltas | HIGH | Grounded directly in codebase map; additive migration pattern verified against `db_utils.py` |
| Architecture — build order and parallelization | HIGH | Dependencies are explicit and based on codebase inspection, not inference |
| Pitfalls — Apify silent-success, BQ cost runaway, AI hallucination | HIGH | Quantified with real incident data and vendor pricing pages |
| Pitfalls — APAC locale/currency/script specifics | MEDIUM-HIGH | Verified across multiple APAC-specific sources; specific competitor CDN behavior only provable in live testing |
| Pitfalls — solo-team maintenance patterns | HIGH | Grounded in EC2 security incident history and CONCERNS.md findings |

**Overall confidence: HIGH** on the build approach; **MEDIUM** on cost envelope and language quality for tier-2 APAC markets until validated in Phase 1.

---

*Research completed: 2026-05-04*
*Ready for roadmap: yes*

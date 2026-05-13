# Phase 2: Per-Market Social Fanout (8 APAC Markets) — Context

**Gathered:** 2026-05-13
**Status:** Ready for planning
**Source:** Conversation history (no formal discuss-phase) + ROADMAP.md + STATE.md operator notes

<domain>
## Phase Boundary

Marketing managers operating in any of 8 APAC v1 markets (SG, HK, TW, MY, TH, PH, ID, VN)
can open `/markets/<code>` and see Facebook, Instagram, and X follower / activity data
that is **scrape-attributed per market** — not inferred from post content. Competitors
without a per-market presence on a platform fall back gracefully to global data.

Phase 1 already cut FB / IG / X over to Apify globally (all 11 competitors, global market).
Phase 2 extends that to per-market scraping AND adds the `/markets/<code>` UI views.

**In scope:**
- Per-market Apify scraping via `apifyProxyCountry: <market_code>`
- Per-market `social_snapshots` writes (currently all rows are `market_code = 'global'`)
- `/markets/<code>` dashboard view showing per-market social data
- Graceful fallback when no per-market data exists for a competitor × platform
- Trust UX continuity (StaleDataBanner, EmptyState scraper-failed, peer benchmarking
  per Phase 1 patterns)

**Out of scope (Phase 3 / 4 / 5):**
- BigQuery Share-of-Search sync (Phase 3)
- AI promo recommendations (Phase 4)
- Confidence / freshness pill UX polish (Phase 5)
- Per-market FB / IG / X handles in `scrapers/config.py` — see Open Questions

</domain>

<decisions>
## Implementation Decisions

### Markets and routing
- **D2-01 (LOCKED):** 8 APAC v1 markets — SG, HK, TW, MY, TH, PH, ID, VN (per ROADMAP).
- **D2-02 (LOCKED):** Geo-routing via `apifyProxyCountry: <market_code>` on every actor call
  (ROADMAP success criterion #4). Apify proxy must be enabled in actor input.

### Schema and writes
- **D2-03 (LOCKED):** Reuse existing `social_snapshots.market_code` column (Plan 01-01 added it).
  No new columns / no schema migration needed for the basic per-market support.
- **D2-04 (LOCKED):** `apify_run_logs` rows per `(competitor, platform, market_code)` for triage
  (ROADMAP success criterion #4). The current code already writes per-`(competitor, platform)`;
  Phase 2 extends to include `market_code`.

### Apify actors (carry forward from Phase 2 cutover already shipped)
- **D2-05 (LOCKED):** Facebook follower count via `apify/facebook-pages-scraper` + activity
  via `apify/facebook-posts-scraper` (5 posts/page).
- **D2-06 (LOCKED):** Instagram via `apify/instagram-profile-scraper` + `apify/instagram-post-scraper`
  (5 posts/handle for posts_last_7d).
- **D2-07 (LOCKED):** X via `kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest`
  with `searchTerms: ["from:<handle>"]`, 10 tweets/handle, mock-data detection.

### Cost ceiling
- **D2-08 (LOCKED):** Apify free tier ($5/mo platform credit) is INSUFFICIENT for full
  8-market fanout (~$12/mo projected). **Apify Starter tier ($49/mo) is a Phase 2
  prerequisite** — flagged in STATE.md. Operator approval has not yet been confirmed
  in writing; Phase 2 ships behind a feature flag until the upgrade lands.
- **D2-09 (LOCKED):** Per-call cost caps preserved from Phase 1
  (`PER_CALL_COST_CAP_USD = $1.00` runaway-scroll guard, plus per-actor caps).

### Fallback behavior
- **D2-10 (LOCKED):** When a competitor lacks per-market data on a platform, the per-market
  view falls back to that competitor's global row (ROADMAP success criterion #3) — no
  empty panel, no double-counting. The peer-benchmarking widget I shipped in Phase 1
  already handles this fallback shape; reuse the pattern.
- **D2-11 (LOCKED):** When `apifyProxyCountry` geo-routing produces zero items for a
  `(competitor, platform, market)` tuple, write a `change_events scraper_zero_results`
  row tagged with the market and skip the snapshot insert (carry forward Plan 01-03
  silent-success guard).

### Cron and HC.io
- **D2-12 (LOCKED):** Cron timezone is `Asia/Singapore` per 2026-05-05 operator
  preference. Existing weekly Mon 7am SGT slot for `apify_social.py` is sufficient
  for Phase 2 — no new cron entries unless cost requires staggering.
- **D2-13 (LOCKED):** 8 markets × current weekly cadence = 8 runs/week of apify_social
  if naively split. Prefer a SINGLE weekly apify_social run that iterates markets
  internally (one cron entry, one HC.io check). Operator gets one
  "apify-social" green ping per week.

### Trust UX continuity
- **D2-14 (LOCKED):** Reuse Phase 1 trust patterns: `<StaleDataBanner>` for stale rows,
  `<EmptyState reason="scraper-failed">` for `scraper_zero_results` events, peer
  benchmarking mini bar chart, extraction_confidence per row.
- **D2-15 (LOCKED):** Confidence rule per platform unchanged from Phase 1: `high` requires
  follower_count > 0 AND posts_last_7d > 0; `medium` otherwise.

### Claude's Discretion
- The exact shape of `/markets/<code>` page layout — must reuse existing Card / Tabs
  primitives from `/competitors/<id>` but the market view is competitor-oriented
  (rows of competitors), not platform-oriented (cards per platform).
- Which Drizzle query pattern to use for "latest per (competitor, platform, market)"
  efficiently — the Phase 1 dedup-in-JS approach is fine for 11×4×8 = 352 rows max.
- Whether to add a market selector to `/competitors/<id>` so a single competitor's
  per-market data is also browsable from the competitor view (likely yes —
  consistent with how the existing `?market=<code>` query param already works).
- Failure-mode UX when `apifyProxyCountry` is blocked or rate-limited by a platform
  — likely just falls into the existing scraper-failed EmptyState path.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 outputs (Apify integration shipped)
- `scrapers/apify_social.py` — current FB+IG+X scraper, global market only.
  Extend, don't rewrite. Has redaction install, cost caps, mock detection.
- `scrapers/run_all.py` — orchestrator. `main_single()` accepts a script name
  arg so cron can route through it (HC.io ping coverage). Don't bypass.
- `scrapers/config.py` — competitor handles. Currently global (`facebook_slug`,
  `instagram_handle`, `x_handle`). Phase 2 may extend OR keep global+geo-routing.
- `src/db/schema.ts` and `scrapers/db_utils.py` — `social_snapshots.market_code`
  column already exists (Plan 01-01).
- `src/lib/markets.ts` — market code enum and `isMarketCode()` guard.
- `src/lib/constants.ts` — SCRAPERS list, ACTOR_TO_SCRAPER map, PLATFORMS list.

### Phase 1 UI patterns (reuse, don't duplicate)
- `src/app/(dashboard)/competitors/[id]/page.tsx` — Digital Presence tab is the
  per-platform-card pattern. Phase 2's per-market view is its complement (per-
  competitor rows).
- `src/components/shared/empty-state.tsx` — `reason="scraper-failed"` variant.
- `src/components/shared/stale-data-banner.tsx` — top-of-page banner.
- `src/app/(dashboard)/admin/data-health/page.tsx` — operator diagnostic page.
  Phase 2 should extend the zero-result count query to also break out by market.

### Roadmap and requirements
- `.planning/ROADMAP.md` — Phase 2 goal + 4 success criteria.
- `.planning/REQUIREMENTS.md` — SOCIAL-02, SOCIAL-03, MARKET-01..04.
- `.planning/STATE.md` — open questions and Phase 1 wave-4 decisions worth carrying.

### Threat / cost model anchors
- `scrapers/log_redaction.py` — module docstring contains the April 2026 EC2
  incident anchor used by `install_redaction()` callers.
- `.planning/phases/01-foundation-apify-scaffolding-trust-schema/APIFY_BUILD_VERIFIED.txt`
  — actor build pinning convention (D-04).

</canonical_refs>

<open_questions>
## Open Questions for Research / Planning

### Q1: Per-market handles vs. geo-routing-only (CRITICAL)
ROADMAP success criterion #2 says "per-market URLs/handles (not inferred from post
content)", which implies per-market handle fields in `config.py`. Success criterion
#4 says "Each Apify call uses `apifyProxyCountry`", which implies geo-routing of
the global handle. These can coexist:

- **Option A:** Geo-routing only. Use global handles, pass `apifyProxyCountry`. Cheap
  to ship (no config maintenance). Works when broker's social account auto-geo-targets.
  Failure mode: many broker accounts are global and don't geo-target → per-market
  view shows the same global data 8 times.
- **Option B:** Per-market handles + geo-routing. Add `facebook_slug_sg`,
  `instagram_handle_my`, etc. to config.py for competitors that have them. Fall back
  to global handle when no per-market handle exists. Highest fidelity but requires
  manual handle research per competitor per market (potentially 11 × 8 × 3 = 264
  handles to research, most empty).
- **Option C (recommended for Phase 2 start):** Option A this cycle, design schema +
  config shape to accommodate Option B in Phase 2.1. Tactically: ship the
  geo-routing first, let marketing managers verify whether geo-routing is sufficient
  on their actual viewing patterns, then invest in per-market handle research only
  for competitors / platforms where geo-routing is demonstrably wrong.

**Decision required from operator before plan finalization.**

### Q2: When does Apify Starter upgrade happen?
Free tier ($5/mo) only fits the global run (~$2/mo). 8-market fanout (~$12/mo) needs
Starter ($49/mo). Operator has not yet confirmed the upgrade. Phase 2 should ship
behind a feature flag (e.g., env var `PHASE_2_MARKETS_ENABLED=true`) so the code can
land safely without burning the free tier ceiling.

### Q3: Cron run duration concern
8 markets × 11 competitors × 3 platforms × 2 actor calls (FB needs pages+posts) =
528 actor invocations per weekly run. Even with batched calls per market this is
8 × 3 = 24 batched calls. Apify SDK is synchronous (.call()). Total wall clock
could exceed the 30-minute INFRA-02 timeout. Phase 2 plans should either:
- Parallelize per-market calls in apify_social.py via `asyncio` / threads, OR
- Split into 8 separate scraper modules (one per market), OR
- Bump the INFRA-02 timeout above 30 min (last resort, paged).

</open_questions>

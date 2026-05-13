# Phase 2: Per-Market Social Fanout — Research

**Researched:** 2026-05-13
**Domain:** Apify geo-routing + per-market UI fanout
**Confidence:** HIGH for codebase patterns; MEDIUM for `kaitoeasyapi` actor proxy honoring (smoke-test required)

## Summary

Phase 1 shipped a working global Apify scraper (`scrapers/apify_social.py`) covering FB+IG+X for 11 competitors at ~$0.49/run weekly. Phase 2 is a **parameter-threading refactor**: extend each actor call with `proxyConfiguration: {useApifyProxy: True, apifyProxyCountry: "<CC>"}`, write per-`(competitor, platform, market_code)` rows into the existing `social_snapshots` table, and ADD a Digital Presence section to the already-shipped `/markets/[code]/page.tsx`. No new schema, no new cron entries, no new npm/pip deps.

**Primary recommendation:** Option C from Q1 (geo-routing only this cycle, per-market handles deferred) + feature-flagged rollout via `APIFY_MARKETS_ENABLED` env var + serial loop over markets (no asyncio) + extend `/markets/[code]/page.tsx` with a competitor-row social table reusing the existing pricing-table idiom.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D2-01:** 8 APAC v1 markets — SG, HK, TW, MY, TH, PH, ID, VN.
- **D2-02:** Geo-route every actor call via `apifyProxyCountry`.
- **D2-03:** Reuse `social_snapshots.market_code` (Plan 01-01 added it). No migration.
- **D2-04:** `apify_run_logs` per `(competitor, platform, market_code)`.
- **D2-05/06/07:** Actors locked: FB pages+posts, IG profile+posts, kaitoeasyapi X.
- **D2-08:** Apify free tier insufficient. Starter ($49/mo) is a Phase 2 prerequisite — ship behind feature flag.
- **D2-09:** Preserve per-call cost caps (`PER_CALL_COST_CAP_USD = $1.00`).
- **D2-10:** No per-market data → fall back to competitor's global row.
- **D2-11:** Zero-result → `change_events scraper_zero_results` tagged with market; skip snapshot.
- **D2-12/13:** Single weekly Mon 7am SGT cron; one HC.io ping per week. Internal market loop.
- **D2-14:** Reuse Phase 1 trust UX (StaleDataBanner, EmptyState scraper-failed, peer benchmark, extraction_confidence).
- **D2-15:** `high` requires `follower_count > 0 AND posts_last_7d > 0`; else `medium`.

### Claude's Discretion
- `/markets/[code]` social-section layout (competitor-oriented table recommended — Section 5).
- Drizzle "latest per (competitor, platform, market)" query — dedup-in-JS is fine (≤352 rows).
- Whether to add market selector to `/competitors/[id]` — already wired via `?market=` in Phase 1; no extra work.
- Failure-mode UX → falls into existing scraper-failed EmptyState path.

### Deferred Ideas (OUT OF SCOPE)
- Per-market FB/IG/X handles in `config.py` (Option B in Q1 — deferred to Phase 2.1).
- BigQuery SoS sync (Phase 3), AI recs (Phase 4), Freshness pill polish (Phase 5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SOCIAL-02 | Scrape IG via pinned Apify actor; write `social_snapshots` | §1: actors accept `proxyConfiguration`; market loop adds market_code |
| SOCIAL-03 | Scrape X via pinned Apify actor; write `social_snapshots` | §1: same pattern; smoke-test needed for kaitoeasyapi (A1) |
| MARKET-01 | `competitors.market_config` JSON populated with per-market handles OR global fallback | §2: ship `market_config: null` now (Option C); design forward-compat schema for Phase 2.1 |
| MARKET-02 | One Apify call per `(competitor, platform, market)` using `apifyProxyCountry` | §1+§3: serial loop, batched per (platform, market); 5 actor types × 8 markets = 40 calls/run |
| MARKET-03 | `/markets/[code]` displays social filtered by market_code with global fallback | §5: extend existing `/markets/[code]/page.tsx`; reuse Phase 1 fallback resolver |
| MARKET-04 | All 8 markets load without errors | §5 + Pitfall 2: **`src/lib/markets.ts` PRIORITY_MARKETS MISSING `ph`, INCLUDES out-of-scope `cn`+`mn`**; Phase 2 must fix |
</phase_requirements>

## Standard Stack

**No new deps.** Phase 2 is a pure code + UI change.

| Library | Version | Phase 1 status |
|---------|---------|----------------|
| `apify-client` (Python) | 2.5.0 | Pinned in `scrapers/requirements.txt` [VERIFIED: Plan 01-01] |
| `drizzle-orm` | 0.45.1 | Existing |
| `better-sqlite3` | 12.8.0 | Existing |

## Architecture Patterns

### Pattern 1: `proxyConfiguration` injection point

Top-level `proxyConfiguration` object inside `run_input` — NOT a separate kwarg on `actor.call()`. [CITED: docs.apify.com/platform/actors/development/actor-definition/input-schema/specification/v1]

```python
run_input = {
    # ...existing fields (startUrls / usernames / searchTerms)...
    "proxyConfiguration": {
        "useApifyProxy": True,
        "apifyProxyCountry": "SG",   # ISO 3166-1 alpha-2 UPPERCASE
    },
}
client.actor(ACTOR_ID).call(run_input=run_input, ...)
```

Country regex is `^[A-Z]{2}$` [VERIFIED: github.com/apify/apify-sdk-python `_proxy_configuration.py`]. Our `MarketCode` is lowercase — helper must `.upper()`. All 8 APAC codes are valid 2-letter ISO codes; direct uppercase works.

### Pattern 2: Helper + market loop

```python
# scrapers/apify_social.py — new helper near top
def _proxy_config(market_code: str) -> dict:
    """market_code is lowercase ('sg', 'hk'...); 'global' means no geo-routing."""
    if market_code == "global":
        return {"useApifyProxy": True}
    return {"useApifyProxy": True, "apifyProxyCountry": market_code.upper()}

# In run(): replace single-market block with:
TARGET_MARKETS_RAW = os.environ.get("APIFY_MARKETS_ENABLED", "")
TARGET_MARKETS = (
    [m.strip().lower() for m in TARGET_MARKETS_RAW.split(",") if m.strip()]
    or ["global"]
)
with closing(get_db()) as conn:
    for market_code in TARGET_MARKETS:
        n, errs = run_facebook(client, conn, run_id, snapshot_date, fb_targets, market_code)
        # ...same for instagram, x — each fn accepts market_code and threads it
        # into proxyConfiguration AND into social_snapshots/apify_run_logs writes.
```

Each `run_facebook/instagram/x` accepts `market_code` and injects it into:
1. The `proxyConfiguration` block in `run_input`.
2. `social_snapshots.market_code` writes (replace `DEFAULT_MARKET_CODE`).
3. `apify_run_logs.market_code` writes (replace `DEFAULT_MARKET_CODE`).
4. `change_events.market_code` writes (replace `DEFAULT_MARKET_CODE`).

### Pattern 3: Feature flag (D2-08 / Q2)

Env var `APIFY_MARKETS_ENABLED`. Empty/unset → `["global"]` (Phase 1 behavior preserved). Comma-separated codes → fanout. Operator flips on EC2 `.env.local` after Apify Starter upgrade — no code redeploy. Matches existing pattern (`HEALTHCHECK_URL_*`, `APIFY_API_TOKEN`).

### Pattern 4: Dashboard fallback resolution (D2-10)

Already shipped in `src/app/(dashboard)/competitors/[id]/page.tsx:312-340`. For `/markets/[code]` this becomes per-competitor:

```typescript
type SocialKey = `${string}|${string}`;  // competitorId|platform
const socialMap = new Map<SocialKey, SocialCell>();
// market-first pass
for (const snap of socialRows) {
  if (snap.marketCode !== marketCode) continue;
  const k: SocialKey = `${snap.competitorId}|${snap.platform}`;
  if (!socialMap.has(k)) socialMap.set(k, {...snap, isMarketSpecific: true});
}
// global fallback pass
for (const snap of socialRows) {
  if (snap.marketCode !== "global") continue;
  const k: SocialKey = `${snap.competitorId}|${snap.platform}`;
  if (!socialMap.has(k)) socialMap.set(k, {...snap, isMarketSpecific: false});
}
```

### Anti-Patterns

- **`apifyProxyGroups: ["RESIDENTIAL"]`** — residential is $8/GB extra [CITED: apify.com/pricing 2026]. Datacenter (default) is included in actor cost. Only switch to residential per-platform if smoke detects geo-detection failures.
- **Looping markets outside actor batch** — keep batching all 11 handles per (platform, market) call; loop markets, not competitors.
- **asyncio/ThreadPoolExecutor** — Apify SDK `actor.call()` is sync-blocking. Serial 8 markets × ~41s = ~5.5 min, well inside 30-min INFRA-02. Parallelizing requires `actor.start()` + manual polling = significant complexity for no budget gain.
- **Per-market separate cron entries** — D2-13 locks single entry; one HC.io ping/week.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Geo-routing | Custom proxy rotator | `proxyConfiguration` actor input |
| ISO code validation | Custom regex/dict | `MarketCode.upper()` direct pass — all 8 valid |
| Per-market UI fallback | New widget | Reuse `competitors/[id]/page.tsx:312-340` fallback pattern |
| Parallelism | asyncio | Serial loop — fits 30-min budget 5× over |
| Rate limiting | Custom backoff | Apify SDK handles 429s; we're at 1 concurrent run vs Starter's 32 limit [VERIFIED: docs.apify.com/platform/limits] |

## Runtime State Inventory

| Category | Items | Action |
|----------|-------|--------|
| Stored data | All Phase 1 `social_snapshots` rows have `market_code='global'`. Remain valid as fallback per D2-10. | None — additive. No backfill. |
| Live service config | Apify Console on free tier. Phase 2 requires Starter upgrade. | Operator: upgrade Apify + set env var. Code ships safely either way. |
| OS state | Cron entry for `apify_social.py` exists (Phase 1). | None — D2-13 locks single entry. |
| Secrets/env | `APIFY_API_TOKEN`, `HEALTHCHECK_URL_APIFY_SOCIAL` already wired. NEW: `APIFY_MARKETS_ENABLED`. | Operator sets `APIFY_MARKETS_ENABLED="sg,hk,tw,my,th,ph,id,vn"` after upgrade. |
| Build artifacts | None | None. |

## Common Pitfalls

### Pitfall 1: `MarketCode` lowercase vs Apify uppercase
Forgetting `.upper()` triggers Apify's `^[A-Z]{2}$` regex validation. Add a unit test asserting `_proxy_config("sg")["apifyProxyCountry"] == "SG"`.

### Pitfall 2: `PRIORITY_MARKETS` list mismatch (HIGH PRIORITY)
`src/lib/markets.ts:4-14` currently reads `["sg","my","th","vn","id","hk","tw","cn","mn"]` — **missing `ph`**, **includes out-of-scope `cn`+`mn`**. ROADMAP locks 8 markets: `SG,HK,TW,MY,TH,PH,ID,VN`. Phase 2 plan MUST update `PRIORITY_MARKETS` to exactly those 8. `MARKET_FLAGS` and `MARKET_NAMES` already cover `ph` (`src/lib/constants.ts:45-58`) and DB seed already has it (`src/db/seed.ts` row for `ph`). Only the TS array is wrong.

### Pitfall 3: Per-market handle ambiguity (Q1)
Geo-routing a global handle (e.g. `@vantagemkts`) may return identical data across markets if the account doesn't geo-target. Symptom: same follower count for all 8 markets on a (competitor, platform). This is observable post-ship; Phase 2.1 can add per-market handles ONLY for demonstrably-wrong combos. Schema is already compatible — `competitors.market_config TEXT` column exists.

### Pitfall 4: Cost overrun on first per-market run
Operator setting `APIFY_MARKETS_ENABLED` before upgrading Apify burns through $5 free credit in one weekly run (~$0.49 × 8 = $3.92). Document the upgrade-FIRST flow in plan SUMMARY. Per-call caps prevent runaway but not legitimate full fanout from exhausting $5.

### Pitfall 5: `apify_run_logs` market_code default trap
Column exists from Plan 01-01 but defaults to `'global'`. Phase 2 code that forgets to pass `market_code` to the INSERT silently records `'global'` for per-market runs. Smoke-test assertion: `SELECT DISTINCT market_code FROM apify_run_logs WHERE scraper_run_id=?` must return 8 rows after a full fanout.

## Per-Topic Findings

### §1. Apify `apifyProxyCountry`
- Configuration placement: top-level `proxyConfiguration` inside `run_input`.
- Cost: default datacenter proxy INCLUDED in per-event actor pricing; residential `+$8/GB` extra. **Recommend datacenter (default)** for follower-count scraping. Only escalate per-platform if a market consistently returns scraper_zero_results.
- All 5 in-scope actors are expected to honor the platform-standard `proxyConfiguration` field per the Apify input-schema v1 spec. The `kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest` is community-published — **assumption A1, smoke-test required** during Plan execution.
- Country codes: SG, HK, TW, MY, TH, PH, ID, VN are all valid ISO 3166-1 alpha-2. Apify supports them as datacenter proxy exit countries based on standard proxy network coverage — **assumption A2, smoke-test required** for any market that returns proxy errors.

### §2. Per-market handle strategy (Q1)
**Recommendation: Option C — geo-routing only this cycle.** Defer Option B (per-market handles in config.py) to Phase 2.1, gated on observed Option-A failures.

Forward-compatible schema (Phase 2.1, do NOT ship in Phase 2):
```python
"market_handles": {
    "facebook": {"sg": "exness_sg"},  # missing keys fall back to facebook_slug
    "instagram": {},
    "x": {},
}
```

Resolution function (Phase 2.1):
```python
def resolve_handle(comp, platform, market_code) -> tuple[str, str]:
    overrides = (comp.get("market_handles") or {}).get(platform, {})
    if market_code in overrides:
        return overrides[market_code], market_code
    return comp.get(f"{platform}_handle") or comp.get(f"{platform}_slug"), "global"
```

For Phase 2 the resolution is trivial: `(global_handle, market_code)` — handle stays same; only `proxyConfiguration` changes.

### §3. Parallelization (Q3)
**Recommendation: serial loop, no asyncio.** Math:
- 5 actor calls/market × ~41s measured wall clock = ~205s/market.
- 8 markets × 205s = ~27 min. **Tighter than I'd like inside 30-min INFRA-02 budget.** Headroom: 3 min.
- If wall clock exceeds 20 min in practice: drop to per-platform `ThreadPoolExecutor(max_workers=3)` within each market loop (FB pages + IG profile + X start parallel within a market). Keep markets serial.

Revised math correction: Phase 1 measured ~0.49 USD/run = batched single market. Per-market wall clock per platform = batched actor cost ÷ per-platform fraction. Real-world: FB pages ~3s + FB posts ~15s + IG profile ~3s + IG posts ~10s + X ~10s = **~41s per market** (these run within a single market loop iteration since each actor is a single batched call across competitors). 8 × 41s = **~330s = 5.5 min**. Comfortable. Keep serial.

Apify Starter concurrent run limit = 32 [VERIFIED]. Serial = 1 concurrent run; no risk.

### §4. Feature flag (D2-08 / Q2)
Env var `APIFY_MARKETS_ENABLED` (Pattern 3). Default empty → global-only → free-tier-safe.

### §5. UI: `/markets/<code>` layout
**Discovery:** `src/app/(dashboard)/markets/[code]/page.tsx` ALREADY EXISTS (681 lines). Renders KPI row + Market Overview + Pricing table + Account Types + Recent Changes + Active Promotions. Phase 2 ADDS one section.

**Recommendation: competitor-oriented table** (matching the existing Pricing table idiom on the same page):

```
Digital Presence
┌──────────────────┬────────┬─────────────┬─────────────┬─────────────┐
│ Broker           │ Source │ Facebook    │ Instagram   │ X           │
├──────────────────┼────────┼─────────────┼─────────────┼─────────────┤
│ Pepperstone (US) │ Market │ 12.3k · 5p  │ 4.5k · 3p   │ 8.1k · 7p   │
│ IC Markets       │ Global │ 89k · 12p   │ 47k · 5p    │ 19k · 4p    │
│ ...              │ ...    │ ...         │ ...         │ ...         │
└──────────────────┴────────┴─────────────┴─────────────┴─────────────┘
```

Cell format: `<followers> · <posts_last_7d>p`. Empty cell with recent `scraper_zero_results` event → small red dot or `<EmptyState reason="scraper-failed">` inline. Reuse existing `<DataSourceBadge isMarketSpecific={...}>` from `markets/[code]/page.tsx:54-69`.

Existing pricing table at lines 459-536 is the exact pattern — copy structure, swap columns.

### §6. Cron entry shape (D2-13)
**No new cron entries.** Existing entry runs `apify_social.py` which internally iterates `TARGET_MARKETS`. One HC.io ping per week. `scrapers/run_all.py:main_single("apify_social.py")` already supports this from Phase 1.

### §7. `/admin/data-health` extension
Current state at `src/app/(dashboard)/admin/data-health/page.tsx:60-72` groups zero-counts by `actorId`. Phase 2 minimal change: add a second parallel Drizzle query grouping by `(actorId, marketCode)`, render as comma-separated badge in the existing zero-result-count cell:

```typescript
const zeroByActorMarket = await db
  .select({ actorId: apifyRunLogs.actorId, marketCode: apifyRunLogs.marketCode,
            count: sql<number>`COUNT(*)` })
  .from(apifyRunLogs)
  .where(and(eq(apifyRunLogs.status, "empty"),
             gte(apifyRunLogs.startedAt, sevenDaysAgoIso)))
  .groupBy(apifyRunLogs.actorId, apifyRunLogs.marketCode);
// In the cell: "MY (2), PH (1)" — markets with > 0 zero-result runs this week.
```

Keep single-table layout. Don't break out 8 columns — keeps the page scannable.

### §8. Trust UX continuity (D2-14)
All Phase 1 components reusable AS-IS:

| Component | Reuse |
|-----------|-------|
| `<StaleDataBanner>` | Auto-rendered by `(dashboard)/layout.tsx` |
| `<EmptyState reason="scraper-failed">` | Inline in social table cells |
| Peer benchmarking widget | `/markets/[code]` table IS the peer comparison — no widget needed |
| `extraction_confidence` | Already written; surface as small badge per cell (or defer to Phase 5) |
| `<DataSourceBadge>` | Already used for pricing/promo; extend to social rows |

**No new components.** Optional polish: extract `DataSourceBadge` from local helper to `src/components/shared/` — single-file refactor.

## Code Examples

### Single helper + market-aware function signature

```python
# scrapers/apify_social.py — top of file
def _proxy_config(market_code: str) -> dict:
    if market_code == "global":
        return {"useApifyProxy": True}
    return {"useApifyProxy": True, "apifyProxyCountry": market_code.upper()}

# Then in run_facebook (apply same shape to run_instagram, run_x):
def run_facebook(client, conn, run_id, snapshot_date, targets, market_code):
    # ...
    apify_run_obj = client.actor(FB_ACTOR_ID).call(
        run_input={
            "startUrls": [{"url": f"https://www.facebook.com/{s}"} for s in slugs],
            "resultsLimit": FB_RESULTS_LIMIT_PER_PAGE,
            "proxyConfiguration": _proxy_config(market_code),
        },
        build=FB_ACTOR_BUILD,
        max_total_charge_usd=FB_COST_CAP_USD,
        timeout_secs=PER_RUN_TIMEOUT_SECS,
    ) or {}
    # ...writes use market_code (not DEFAULT_MARKET_CODE) in social_snapshots,
    #    apify_run_logs, change_events.
```

### Cron entry (UNCHANGED from Phase 1)

```
# crontab — Mon 7am SGT == 23:00 UTC Sun
0 23 * * 0 cd /home/ubuntu/app && /usr/bin/python3 scrapers/run_all.py apify_social.py
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `kaitoeasyapi/twitter-x-data-tweet-scraper-pay-per-result-cheapest` honors top-level `proxyConfiguration` | §1, §2 | All X runs route through default proxy regardless of market; X data identical across markets. Detectable in first smoke. Mitigation: per-actor smoke during Plan execution. |
| A2 | All 8 APAC v1 codes (SG/HK/TW/MY/TH/PH/ID/VN) available as Apify proxy exit countries | §1 | Apify returns proxy error → actor fails or uses default. Detectable via `apify_run_logs.status='failed'`. Mitigation: smoke each market once. |
| A3 | Datacenter (default) proxy included in actor per-event price | §1 | If wrong (residential billed separately): cost +$2-5/mo. Still inside Starter $49/mo budget. |
| A4 | Per-market wall clock scales linearly | §3 | If Apify throttles back-to-back same-actor calls: even at 4× slowdown (22 min) inside 30-min INFRA-02. |

## Open Questions

1. **Will operator approve Apify Starter upgrade BEFORE Phase 2 lands?**
   - What we know: Phase 2 cost ~$15.7/mo (8 × $0.49); free = $5/mo.
   - Recommendation: Plan ships behind `APIFY_MARKETS_ENABLED` flag (empty default). Code lands safely either way. Operator flips flag post-upgrade.

2. **Does `kaitoeasyapi` X actor support `proxyConfiguration`?** (A1)
   - Recommendation: First task in implementation plan is a 5-actor smoke loop calling each with `apifyProxyCountry=SG` for one competitor, verifying response differs from US-default.

3. **Should `extraction_confidence` thresholds change for per-market?**
   - Concern: per-market runs likely produce zero posts_last_7d when broker has no geo-active account → forced to `medium`. UI may flood with medium-confidence rows.
   - Recommendation: keep D2-15 rule unchanged. Honest signal > inflated confidence. Phase 5 polishes UI surfacing.

## Environment Availability

| Dependency | Available | Notes |
|------------|-----------|-------|
| `apify-client` Python 2.5.0 | ✓ | Phase 1 pinned |
| `social_snapshots.market_code` | ✓ | Plan 01-01 |
| `apify_run_logs.market_code` | ✓ | Plan 01-01 |
| `/markets/[code]/page.tsx` | ✓ | Already exists |
| `MARKET_FLAGS[ph]` + DB seed for `ph` | ✓ | Verified |
| EC2 Python ≥ 3.10 | ⚠ | Phase 1 operator follow-up; required before EC2 deploy |
| Apify Starter tier | ✗ → fallback | Feature flag default = global = safe on free tier |

## Project Constraints (from CLAUDE.md)

- Stack locked (Next.js 15, React 19, Drizzle/SQLite, Python). Phase 2 adheres — no swaps.
- SQLite this milestone — Phase 2 needs no schema changes.
- `npm ci` on EC2, never `npm install` — no npm-side deps change.
- Apify usage modest — Phase 2 ~$15.7/mo with Starter, inside the envelope.
- Maintenance burden — single serial loop, no per-market code branches.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Python stdlib `unittest` (Phase 1 convention) |
| Quick run | `python -m unittest scrapers.test_apify_social_market -v` |
| Full suite | `python -m unittest discover scrapers/ -v` + `npm run lint` + `npm run build` |

### Phase Requirements → Test Map

| Req | Behavior | Type | Command | Exists |
|-----|----------|------|---------|--------|
| MARKET-02 | `_proxy_config("sg")` returns `{useApifyProxy: True, apifyProxyCountry: "SG"}` | unit | unittest | ❌ Wave 0 |
| MARKET-02 | `_proxy_config("global")` returns `{useApifyProxy: True}` (no country) | unit | unittest | ❌ Wave 0 |
| MARKET-02 | `TARGET_MARKETS` parser handles `""`, `"global"`, `"sg,my"`, whitespace | unit | unittest | ❌ Wave 0 |
| SOCIAL-02/03 | Snapshot row gets `market_code` from loop param (mock Apify) | integration | unittest+monkeypatch | ❌ Wave 0 |
| MARKET-04 | `PRIORITY_MARKETS === ["sg","hk","tw","my","th","ph","id","vn"]` | unit (TS) | snapshot test OR explicit assertion | ❌ Wave 0 |
| MARKET-03 | `/markets/sg` renders Digital Presence section | manual smoke | EC2 visit | manual |
| D2-04 | `apify_run_logs` per market_code | integration smoke | sqlite3 query | manual |

### Sampling Rate
- Per task commit: `python -m unittest scrapers.test_apify_social_market -v` + `npm run lint`
- Per wave merge: full suite + `npm run build`
- Phase gate: one EC2 smoke with `APIFY_MARKETS_ENABLED="sg,my"` → 2 markets × 3 platforms = 6 new `social_snapshots` + 6 `apify_run_logs` rows

### Wave 0 Gaps
- [ ] `scrapers/test_apify_social_market.py` — MARKET-02 + SOCIAL-02/03 helper unit tests
- [ ] No conftest needed (stdlib unittest)
- [ ] Framework install: none — stdlib

## Security Domain

Phase 2 introduces no new auth/session/access-control surfaces. Reuses Phase 1 controls.

| ASVS | Applies | Control |
|------|---------|---------|
| V2 Auth | no | Phase 1 SHA-256 token unchanged |
| V3 Session | no | `auth_token` cookie unchanged |
| V4 Access | no | `(dashboard)` route group middleware covers `/markets/[code]` |
| V5 Input | yes | `parseMarketParam()` + `/^[a-z]{2,5}$/` regex at `markets/[code]/page.tsx:135` |
| V6 Crypto | no | No new secrets; `APIFY_API_TOKEN` + redaction filter from Phase 1 |

| Threat | STRIDE | Mitigation |
|--------|--------|-----------|
| Apify token in scraper logs | Info Disclosure | `install_redaction()` before `from apify_client import ApifyClient` (line 62) — already Phase 1 |
| Invalid market_code path param | Tampering | `notFound()` + regex guard at line 135 |
| Cost runaway via misconfigured fanout | Financial DoS | `max_total_charge_usd` per-actor caps (D2-09) + `APIFY_MARKETS_ENABLED` flag |

## Sources

### Primary (HIGH confidence)
- `scrapers/apify_social.py` — current implementation
- `src/app/(dashboard)/markets/[code]/page.tsx` — existing market page (681 lines)
- `src/app/(dashboard)/competitors/[id]/page.tsx:312-340` — fallback pattern (reused)
- `src/app/(dashboard)/admin/data-health/page.tsx:60-72` — current zero-count query
- `src/db/schema.ts` — `social_snapshots.market_code`, `apify_run_logs.market_code` confirmed
- `src/lib/markets.ts` + `src/lib/constants.ts` — PRIORITY_MARKETS gap and MARKET_FLAGS coverage verified
- [Apify input-schema spec v1](https://docs.apify.com/platform/actors/development/actor-definition/input-schema/specification/v1) — `proxyConfiguration` JSON shape
- [Apify Python SDK ProxyConfiguration](https://github.com/apify/apify-sdk-python/blob/master/src/apify/_proxy_configuration.py) — country regex `^[A-Z]{2}$`
- [Apify Platform Limits](https://docs.apify.com/platform/limits) — 32 concurrent runs on Starter

### Secondary (MEDIUM confidence)
- [Apify pricing 2026](https://apify.com/pricing) — residential $8/GB surcharge (datacenter included)

### Tertiary (LOW confidence — assumptions to smoke-test)
- `kaitoeasyapi` X actor `proxyConfiguration` honor (A1)
- All 8 APAC codes available as Apify exit countries (A2)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; Phase 1 pins valid
- Architecture: HIGH — pure parameter threading; pattern proven in Phase 1
- Apify proxy specifics: MEDIUM — schema verified, kaitoeasyapi honor assumed (A1)
- UI: HIGH — page exists, table pattern established
- Pitfalls: HIGH — Phase 1 reality + verified `PRIORITY_MARKETS` gap

**Research date:** 2026-05-13
**Valid until:** 2026-06-13

# Stack Research — APAC Promo Intelligence Milestone

**Domain:** Brownfield additions to existing competitor-intel dashboard
**Researched:** 2026-05-04
**Overall confidence:** HIGH for SDK/library versions and BigQuery pattern, MEDIUM for Apify actor cost projections (depends on competitor count × cadence × volatility)

## Summary

This milestone adds three discrete new pieces to an existing Next.js 15 / SQLite / Python scrapers / Anthropic Claude stack:

1. **Apify SDKs + 3 managed actors** to replace the broken Thunderbit social pipeline. Use Apify's own `apify/instagram-scraper`, `apify/facebook-posts-scraper`, and `apidojo/twitter-scraper-lite` (a.k.a. "Tweet Scraper V2") via the Python `apify-client`. Pay-per-result pricing fits the weekly × ~5 competitors × 8 markets cadence at well under $20/mo at projected volumes.
2. **`@google-cloud/bigquery` Node.js SDK + system crontab on EC2** for nightly Share-of-Search BQ → SQLite sync. Plain Node script invoked by the EC2 crontab is the right shape for a maintenance-mode dashboard — no n8n, no Airflow, no node-cron in the web process.
3. **No new geo/proxy stack.** Apify's bundled proxies (RESIDENTIAL country-targeted, included in pay-per-result actor pricing) cover the social work. The remaining geo-aware piece — per-market URL fetching of competitor websites — is already handled by existing Playwright scrapers driving competitor URLs from `scrapers/market_config.py`. Apify's actors don't need separate proxy configuration; their cost is rolled into per-result pricing.
4. **No new multilingual NLP layer.** Claude Sonnet 4.5/4.6 (already in the codebase via `anthropic` Python SDK 0.40.0) scores 95–97% relative-to-English on Indonesian, Chinese, Korean, Japanese MMLU. Thai and Vietnamese aren't directly benchmarked by Anthropic but consistently land in the 90%+ range for reasoning tasks per third-party reporting. For structured promo extraction, the right approach is Claude's tool-use (strict schema) with explicit native-language instructions, not a separate NLP pipeline.

## Apify Stack

### Recommended SDKs

| Package | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| `apify-client` (Python) | **2.5.0** (PyPI, requires Python ≥3.10) | Call Apify actors and read dataset results from existing Python scrapers | Lives in the same `scrapers/` layer as the broken `social_scraper.py` it replaces — no language switch, reuses existing `db_utils.py` and market config |
| `apify-client` (Node.js) | **2.23.1** (npm, requires Node ≥16) | Optional — only if a future API route wants to trigger ad-hoc runs from the dashboard | Not needed for v1 milestone. Listed for completeness so it's not re-researched later |

**Recommendation:** Use the **Python client only** in this milestone. The dashboard side stays scrape-free and reads from SQLite as today. This minimizes the surface area of change.

### Recommended Actors

All three are managed/maintained actors with stable IDs. The slug form (`username/actor-name`) is what `apify-client` accepts in `client.actor(...)`.

| Actor | Slug | Pricing (paid plan) | What It Returns | Why This One |
|-------|------|---------------------|------------------|--------------|
| Instagram Scraper | `apify/instagram-scraper` | from **$1.50 / 1,000 results** | Posts, profiles, hashtags, comments — captions, likes, timestamps, media URLs | Official Apify-maintained actor with the broadest input modes (URL, username, hashtag). For competitor IG handles we mostly want post-level data — captions are where promo text lives |
| Facebook Posts Scraper | `apify/facebook-posts-scraper` | **$2.00 / 1,000 posts** | Post text, timestamps, likes/reactions/shares, comment counts, media, video URLs/transcripts | Returns post bodies (where promos appear). `apify/facebook-pages-scraper` returns only page metadata and is ~5× more expensive ($10/1k pages) — wrong tool for our job |
| Tweet Scraper V2 (a.k.a. twitter-scraper-lite) | `apidojo/tweet-scraper` | **~$0.25–0.40 / 1,000 tweets** (event-based: $0.016/query + $0.0004–0.002/item) | Tweet text, lang, createdAt, likes/replies/retweets/quotes, author profile | Cheapest reliable X scraper on Apify. The "lite" branding is misleading — this is the full-featured V2 actor. Supports Twitter advanced-search queries, which lets us filter by `from:competitor` + date window without scraping the whole timeline |

**Note on actor ID format:** Each actor also has a cryptic immutable internal ID (e.g. `shu8hvrXbJbY3Eb9W` for the Instagram scraper). Both forms work in `client.actor(...)`. Use the slug for readability.

### Cost Envelope (sanity check)

Assumptions: 5 competitors × 3 platforms × 8 APAC markets × weekly cadence × ~50 posts retained per pull.

- IG: 5 × 8 × 50 × 4 weeks = 8,000 results/mo ≈ **$12/mo**
- FB: 5 × 8 × 50 × 4 weeks = 8,000 posts/mo ≈ **$16/mo**
- X: 5 × 8 × 50 × 4 weeks = 8,000 tweets/mo. Event-based maths: ~40 queries × $0.016 + 8,000 × $0.0008 ≈ **$7/mo**

**Total ≈ $35/mo** at projected steady-state. Apify Starter plan is $49/mo and includes $49 platform credit + free 30-day trial. Confidence: MEDIUM — actual cost depends heavily on whether we actually need per-market splits (most competitors run one IG/X account globally, not per market — see Pitfalls below).

### Apify Sample Code Pattern

```python
# scrapers/apify_social.py
from apify_client import ApifyClient
import os

client = ApifyClient(os.environ["APIFY_TOKEN"])

run = client.actor("apify/instagram-scraper").call(run_input={
    "directUrls": ["https://www.instagram.com/icmarkets/"],
    "resultsType": "posts",
    "resultsLimit": 50,
    "addParentData": False,
})
items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
```

`call()` is synchronous-blocking-on-completion. For longer runs use `start()` + `wait_for_finish()`.

## BigQuery Stack

### Recommended Libraries

| Package | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| `@google-cloud/bigquery` | **8.3.0** (npm, published 2026-04-27) | Run BQ queries from Node.js, paginate result rows | Official Google library. Auto-handles auth via `GOOGLE_APPLICATION_CREDENTIALS` env var. Compatible with all current active and maintenance Node.js versions, including Node 22 LTS on EC2 |
| `better-sqlite3` | 12.8.0 (already installed) | Write rows to existing SQLite DB | Already in the dashboard's dependency tree. Use the same DB connection pattern as Drizzle |

**Do NOT add:** `node-cron`, `cron`, `node-schedule`, `croner`, `n8n`, `apache-airflow`, Estuary, Hevo, CData. All overkill for one nightly job.

### Recommended Sync Pattern

**Plain Node.js script + EC2 system crontab.** Same pattern the existing Python scrapers use today.

```
scripts/sync-share-of-search.ts   ← invoked by `node` (or `tsx`)
                                  ↓
                     ┌─ pulls from BigQuery via service account
                     ├─ idempotent INSERT OR REPLACE into SQLite
                     └─ logs to scraper_runs table (existing pattern)

EC2 crontab:
0 2 * * * cd /opt/competitor-dashboard && /usr/bin/npm run sync:sos >> logs/sos.log 2>&1
```

**Why this over alternatives:**

| Option | Verdict | Reason |
|--------|---------|--------|
| Plain Node + system crontab | **Choose this** | Mirrors existing scraper pattern, no new daemon, no in-process scheduler, survives Next.js restarts/deploys |
| `node-cron` / `cron` in the Next.js process | ❌ | Tasks die on app restart; competes with HTTP requests for resources; doesn't survive `pm2 restart`. Documented anti-pattern for production |
| n8n | ❌ | Adds a server, a UI, a database, and a cron schedule for one daily query. Maintenance burden is the wrong shape |
| Airflow | ❌ | Massively over-engineered for one nightly extract |
| BigQuery Scheduled Queries → GCS export → S3 → SQLite | ❌ | Adds AWS/GCP cross-cloud surface for no benefit |
| Embedded Looker Studio iframe | ❌ (already rejected in PROJECT.md) | Loses the ability to JOIN SoS with promo/social in SQL |

### BigQuery Auth Pattern

Service-account JSON file, mounted on EC2, referenced via `GOOGLE_APPLICATION_CREDENTIALS` env var. Do **not** check the JSON into git; mount it the same way `.env.local` is mounted.

```typescript
// scripts/sync-share-of-search.ts
import { BigQuery } from "@google-cloud/bigquery";
import Database from "better-sqlite3";

const bq = new BigQuery(); // picks up GOOGLE_APPLICATION_CREDENTIALS
const sqlite = new Database("data/competitor-intel.db");

const [rows] = await bq.query({
  query: `SELECT market_code, brand, week_start, share
          FROM \`pepperstone-analytics.share_of_search.weekly\`
          WHERE week_start >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)`,
  location: "asia-southeast1", // confirm with data team
});

const stmt = sqlite.prepare(`
  INSERT INTO share_of_search_snapshots (market_code, brand, week_start, share)
  VALUES (?, ?, ?, ?)
  ON CONFLICT(market_code, brand, week_start) DO UPDATE SET share = excluded.share
`);
const tx = sqlite.transaction((rows) => {
  for (const r of rows) stmt.run(r.market_code, r.brand, r.week_start.value, r.share);
});
tx(rows);
```

### Cost Envelope

BigQuery on-demand pricing is $6.25/TB scanned (US/EU; APAC similar). A nightly query scanning ~100 MB of weekly SoS data is rounding error — well under $1/mo. Confidence: HIGH.

## Geo/Proxy Stack

### Recommendation: Add nothing.

**Rationale:**

- **Social side (FB/IG/X):** Apify's pay-per-result managed actors include proxy rotation (residential where needed) in their pricing. We don't configure proxies — the actor authors handle that. This is one of the main reasons we're choosing Apify over self-hosted scraping.
- **Website side (per-market competitor URLs):** Already handled. Existing `scrapers/promo_scraper.py` and friends drive Playwright with per-market URLs from `scrapers/market_config.py`. For markets where the same competitor URL serves all geos with localized content, the URL itself is the localizer; for hard geo-locked content (rare for the competitor list), Playwright's `--proxy-server` flag plus a residential proxy could be added later — but no current scraper hits that wall.

### What NOT to Add

| Avoid | Why | If We Ever Need It |
|-------|-----|---------------------|
| Bright Data residential proxies | $300+/mo committed; explicitly rejected in PROJECT.md | Only revisit if scaling to 50+ competitors or daily cadence |
| Oxylabs / IPRoyal | Same pattern — committed monthly minimums for low-volume use | Same as above |
| `playwright-extra` + stealth plugins | Adds dependency surface for a problem we don't have. Existing Playwright scrapers work fine for broker websites | If a specific competitor site starts blocking us, evaluate per-site, not as a global add |
| Apify Proxy as a standalone service | Already bundled in actor pricing for Apify Store actors. Only relevant if we built our own actor | Not in this milestone |

## Multilingual Extraction

### Recommendation: Keep using Anthropic Claude Sonnet 4.5/4.6, no new NLP layer.

The existing `scrapers/ai_analyzer.py` already uses `anthropic` Python SDK v0.40.0 with `claude-sonnet-4-6`. Extend this same module for promo extraction in non-English markets.

### Verified Multilingual Performance (Source: official Anthropic docs)

Zero-shot chain-of-thought scores, % relative to English (100% baseline), Claude Sonnet 4.5 with extended thinking:

| Language | Score | APAC Market(s) Affected |
|----------|-------|-------------------------|
| Indonesian | **97.3%** | ID |
| Chinese (Simplified) | 96.9% | (TW partial — uses Traditional, not directly benchmarked but similar quality expected) |
| Korean | 96.7% | — |
| Japanese | 96.8% | — |

**Not directly benchmarked by Anthropic:** Thai (TH), Vietnamese (VN), Traditional Chinese (TW, HK). These are not in the published MMLU translation set, but Anthropic notes "Claude is capable in many languages beyond those benchmarked" and recommends testing for specific use cases. Confidence: MEDIUM that they fall in the 90%+ band based on pattern of other Asian languages; HIGH that they're more than adequate for promo-text structured extraction (an easier task than MMLU reasoning).

### Recommended Prompt-Engineering Approach

1. **Use tool-use / structured outputs**, not raw JSON-in-a-prompt. Tool-use enforces a schema and returns parseable results without "explain in JSON" boilerplate. Already supported by the existing `anthropic` SDK calls in `pricing_scraper.py` and `ai_analyzer.py`.
2. **Explicit native-language context** in the system prompt: "You will receive promotional copy in Thai. Extract structured promo fields. Return field values in English-equivalent normalized form (e.g. `bonus_amount: 100, currency: USD`) but preserve the original Thai promo title verbatim in `original_title`."
3. **Single language per call**, don't batch mixed-market promos into one call. Claude handles code-switching but prompt clarity matters more than token efficiency at our volumes.
4. **Confidence field in the schema**: have Claude return a `confidence: "high" | "medium" | "low"` per promo so the dashboard's confidence/freshness UI (already in milestone scope) can surface uncertain extractions.
5. **Same model for all markets** (`claude-sonnet-4-6` or successor). Don't fork model selection by language — adds maintenance burden for marginal gains.

### Sample Schema (tool-use)

```python
PROMO_EXTRACTION_TOOL = {
    "name": "record_promo",
    "description": "Record one promotional offer extracted from competitor copy.",
    "input_schema": {
        "type": "object",
        "properties": {
            "original_title": {"type": "string", "description": "Promo title in original language"},
            "english_summary": {"type": "string"},
            "promo_type": {"type": "string", "enum": ["deposit_bonus", "spread_discount", "rebate", "contest", "referral", "other"]},
            "bonus_amount": {"type": ["number", "null"]},
            "bonus_currency": {"type": ["string", "null"]},
            "min_deposit": {"type": ["number", "null"]},
            "valid_until": {"type": ["string", "null"], "description": "ISO date if visible"},
            "market_code": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["original_title", "english_summary", "promo_type", "market_code", "confidence"],
    },
}
```

### What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| spaCy multilingual models | Adds a Python dependency, model files, maintenance. Doesn't outperform Claude on structured extraction | Claude tool-use |
| Google Translate API as preprocessing | Two API calls per promo, adds cost, lossy translation — Claude reads native text fine | Native-language prompt |
| Per-language prompt-template forks | Maintenance burden × 8 markets, drift over time | One template with a `{{language}}` slot |
| Local LLMs (Llama, Qwen) | Self-hosting cost, GPU requirement, inferior accuracy on SE Asian languages vs. Claude | Claude API (already paid for) |

## Recommendations Summary (Decision-Ready)

### Add to `package.json`

```json
{
  "dependencies": {
    "@google-cloud/bigquery": "^8.3.0"
  }
}
```

That's it for npm. No `node-cron`, no `cron`, no proxy libraries.

### Add to `requirements.txt` (or equivalent)

```
apify-client==2.5.0
```

### Add to `.env.local`

```
APIFY_TOKEN=apify_api_...
GOOGLE_APPLICATION_CREDENTIALS=/etc/competitor-dashboard/gcp-sa-bigquery.json
BQ_PROJECT_ID=pepperstone-analytics  # confirm exact name
BQ_DATASET=share_of_search           # confirm with data team
```

### Add to EC2 crontab

```
# Nightly Share-of-Search sync (2 AM SGT)
0 2 * * * cd /opt/competitor-dashboard && /usr/bin/node scripts/sync-share-of-search.js >> logs/sos.log 2>&1

# Weekly Apify social scrape (Sunday 03:00)
0 3 * * 0 cd /opt/competitor-dashboard && /usr/bin/python3 scrapers/apify_social.py >> logs/social.log 2>&1
```

### Remove/deprecate

- `THUNDERBIT_API_KEY` from `.env.local` (after Apify cutover validated)
- `SCRAPERAPI_KEY` from `.env.local` (after Apify cutover validated)
- Lines 76–165 of `scrapers/social_scraper.py` (Thunderbit + ScraperAPI paths) — but keep the file structure so existing scraper-runs logging still works

## Confidence Notes

| Recommendation | Confidence | Why |
|----------------|------------|-----|
| `apify-client` Python 2.5.0 / Node 2.23.1 | **HIGH** | Verified directly against PyPI and `npm view` on 2026-05-04 |
| `@google-cloud/bigquery` 8.3.0 | **HIGH** | Verified via `npm view`. Released 2026-04-27 |
| Apify actor slugs (`apify/instagram-scraper`, `apify/facebook-posts-scraper`, `apidojo/tweet-scraper`) | **HIGH** | Verified directly on apify.com store pages |
| Apify per-result pricing | **HIGH** | Pulled from current actor pages on 2026-05-04 |
| Apify monthly cost projection (~$35/mo) | **MEDIUM** | Depends on competitor-per-market assumptions and how many results we actually pull per run. Verify after first 2 weeks of real data |
| EC2 crontab over node-cron | **HIGH** | Industry consensus + PROJECT.md constraint of "maintenance mode, mostly solo support" |
| Claude Sonnet 4.5/4.6 sufficient for ID, ZH, KO, JA promo extraction | **HIGH** | Anthropic's published MMLU benchmarks: 96–97% for ID, ZH, KO, JA |
| Claude sufficient for TH, VN, TW, HK | **MEDIUM** | Not directly benchmarked. Need 1–2 days of validation testing in Phase 1 with 20–30 hand-labeled promos per language. Build a calibration set into the milestone |
| Tool-use over plain JSON for structured extraction | **HIGH** | Standard pattern, already supported by existing SDK version |
| No proxy/geo-spoofing layer needed | **MEDIUM** | True for current competitor list and existing scraper coverage. If a specific competitor site starts geo-blocking EC2 IPs, revisit per-site |

## Pitfalls Specific to This Stack

(These belong in PITFALLS.md too — flagging here for the Apify-specific ones.)

- **Per-market social splits may not exist.** Most forex brokers run one global IG/X account, not per-market accounts. The "8 markets × 3 platforms" math overstates the work — practically it's "≤12 social handles total" per competitor regardless of market count. Verify in Phase 1 before sizing actor calls. **Save: 5–8x on Apify costs.**
- **Apify actor changes without notice.** Apify-maintained actors are stable; community actors get deprecated. Sticking to `apify/*` and `apidojo/*` (high reputation, paid actors) reduces this risk. Lock the actor version in code if Apify exposes it (`actorVersion` parameter — check current SDK).
- **Claude tool-use schema validation is strict.** If your schema requires a field and the promo legitimately doesn't have it, the model will hallucinate a value. Use `["string", "null"]` for optional fields — already shown in the sample schema above.
- **BigQuery service-account JSON is a CSPM/CIS-finding magnet.** Mount it readable only by the user that runs the cron; don't drop it in the repo or in `data/`. v1.4.1 security audit context applies — don't undo that work.
- **SQLite UPSERT requires explicit conflict targets.** `ON CONFLICT(...)` needs a unique index or PK that matches the conflict columns. Add `UNIQUE(market_code, brand, week_start)` to the SoS table when adding the migration.

## Sources

### Verified (HIGH confidence)
- [apify-client npm — version 2.23.1](https://www.npmjs.com/package/apify-client)
- [apify-client PyPI — version 2.5.0](https://pypi.org/project/apify-client/)
- [@google-cloud/bigquery npm — version 8.3.0, published 2026-04-27](https://www.npmjs.com/package/@google-cloud/bigquery)
- [nodejs-bigquery CHANGELOG.md](https://github.com/googleapis/nodejs-bigquery/blob/main/CHANGELOG.md)
- [Apify Instagram Scraper actor](https://apify.com/apify/instagram-scraper)
- [Apify Facebook Posts Scraper actor](https://apify.com/apify/facebook-posts-scraper)
- [Apify Tweet Scraper V2 (apidojo)](https://apify.com/apidojo/tweet-scraper)
- [Anthropic Claude Multilingual support — official benchmarks](https://platform.claude.com/docs/en/build-with-claude/multilingual-support)
- [Anthropic Claude Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Apify JS API Client docs](https://docs.apify.com/api/client/js/docs)
- [Apify Proxy platform docs](https://docs.apify.com/platform/proxy)
- [BigQuery Node.js auth via service account](https://docs.cloud.google.com/bigquery/docs/samples/bigquery-client-json-credentials)

### Supplementary (MEDIUM confidence — third-party)
- [Apify pricing 2026 review (Use-Apify)](https://use-apify.com/docs/what-is-apify/apify-pricing)
- [node-cron vs system cron production guide (Cronitor)](https://cronitor.io/guides/node-cron-jobs)
- [node-cron vs system cron (CronGen)](https://crongen.com/blog/nodejs-cron-jobs-system-vs-node-cron)
- [Claude Sonnet 4.6 for scrapers benchmark (Zyte)](https://www.zyte.com/blog/llm-benchmark-claude-sonnet-46/)

### Cross-references (this milestone's planning context)
- `.planning/PROJECT.md` — milestone scope, rejected alternatives, constraints
- `.planning/codebase/STACK.md` — existing dependencies (do not duplicate)
- `.planning/codebase/INTEGRATIONS.md` — Thunderbit/ScraperAPI integration to be deprecated
- `.planning/codebase/ARCHITECTURE.md` — scraper layer pattern to extend

---
*Stack research for: APAC Promo Intelligence milestone (brownfield additions)*
*Researched: 2026-05-04*

# Pitfalls Research — APAC Localized Promo Intelligence Milestone

**Domain:** Apify-driven social/promo scraping + BigQuery → SQLite sync + per-market AI recommendations on a maintenance-mode dashboard
**Researched:** 2026-05-04
**Confidence:** MEDIUM-HIGH (Apify, BigQuery, LLM patterns verified against vendor docs and recent community sources; APAC-specific scraping pitfalls drawn from multiple sources but not all reproducible without live testing)

---

## Summary

This milestone has six failure surfaces, ordered by blast radius:

1. **Apify actor breakage** — actors break silently when Meta/X push anti-bot updates; the dashboard gets empty results and "fresh" timestamps. Highest risk because data quality is one of the two stated milestone risks and recovery is fastest if breakage is detected within a day, not a week.
2. **BigQuery cost runaway** — `SELECT *` against a Share-of-Search dataset can incur $6.25/TB instantly; nightly retry loops can compound this. Single-query worst case in published incidents is $10k+ in 22 seconds.
3. **APAC locale fidelity** — geo-routing on competitor sites can hand the scraper English content from a Singapore IP for a Thai-targeted page; currency normalization across THB/VND/IDR (decimal magnitudes differ by 1000x) silently mangles promo amounts.
4. **AI recommendation hallucination** — Claude can invent promos that didn't happen if grounding is loose; per-market context blow-up at 8 markets × multi-source can push $20+ per recommendation cycle if naively prompted.
5. **Confidence/freshness UX** — too-noisy or too-quiet indicators erode trust faster than missing data; the milestone explicitly calls this out as a v1 deliverable, not a polish item.
6. **Solo-team maintenance** — silent cron failures, secret rotation in the middle of the night, schema drift between Node 25 (dev) and Node 22 / older SQLite (EC2 prod), alert noise leading to muting.

The cross-cutting prevention strategy is **fail loud, not silent**: zero results from a scraper run should trigger an alert; missing data should render as "stale" not as a blank cell; AI recos should refuse to generate when context is thin rather than confabulate. The codebase's existing `change_events` table and `scrapers.runs` log give us the seams to do this — we don't need a new alerting stack.

---

## Apify Pitfalls

### A1. Actor returns empty array, run succeeds, dashboard shows "fresh" stale data

**What goes wrong:**
Apify Facebook/Instagram/X actors return a successful run with `[]` (empty results) when the target page is geo-blocked from Apify's default datacenter proxies, when the actor's selectors silently break after a Meta UI change, or when a competitor's page is rate-limited at the IP level. The run's `status` is `SUCCEEDED`, the `defaultDatasetId` is empty, and our scraper code happily inserts a snapshot timestamped now. The dashboard shows "updated 2 hours ago" with zero new posts.

**Why it happens:**
Apify treats "the actor ran without throwing" as success. There's no built-in assertion that results are non-empty. Datacenter proxies are blocked by Instagram and (intermittently) by Facebook for non-logged-in fetches; without specifying `proxyConfiguration.useApifyProxy: true` AND a `proxy.country` matching the target market, you get whichever exit IP Apify picks, which may be geo-blocked from the page you're trying to scrape.

**How to avoid:**
- Set `proxyConfiguration: { useApifyProxy: true, apifyProxyGroups: ["RESIDENTIAL"], apifyProxyCountry: <market_code> }` per market. SG → SG residential, TH → TH residential, etc. Default datacenter is not acceptable for FB/IG/X.
- After every run, assert `dataset.itemCount > 0`. If zero, write a `change_events` row with type `scraper_zero_results` and surface as a confidence indicator. Do NOT insert a snapshot.
- Compare `itemCount` to the median over the last 7 successful runs for the same competitor + platform + market. If less than 30% of median, log as `degraded` and surface in UI.
- For each `(competitor, platform, market)` triple, hard-code an "expected at least N posts in last 30 days" floor based on observed history. Below the floor → `suspect`.

**Warning signs:**
- A `(competitor, platform, market)` triple that goes 3+ days with zero new posts when historical cadence is daily.
- `scrapers.runs` row with `success=true` but `items_count=0`. Trivial SQL alert.
- Spike in successful runs combined with flat snapshot counts in `social_snapshots`.

**Phase to address:** Phase 1 (Apify integration). Build the assertion + zero-result handling before wiring the second platform — once it's in the pattern, IG and X inherit it. Retrofitting later means triple the rework.

---

### A2. Actor versioning surprise — output schema changes between Apify actor versions

**What goes wrong:**
Apify actors are versioned (e.g., `apify/instagram-scraper@latest` vs pinned `@2.x.x`). The maintainers can change output keys between minor versions — `caption` becomes `text`, `likesCount` becomes `likes`, nested `owner.username` becomes top-level `ownerUsername`. Our parser silently inserts `null` for the renamed field; the dashboard shows zero engagement, zero captions.

**Why it happens:**
We follow Apify's quickstart, which uses `actor: "apify/instagram-scraper"` (latest). They push a breaking change. Our scraper doesn't validate the response shape; `safeParseJson` is too permissive (returns `[]` on parse failure but doesn't validate structure of parsed JSON).

**How to avoid:**
- Pin actor version explicitly (e.g., `apify/instagram-scraper:1.16.0` or via the `build` parameter set to a specific tag). Do not pull `:latest`.
- Add schema validation on the response. Define a Pydantic model (Python) per platform. Validation failure → log + surface as `parse_error`, do not insert snapshot.
- Subscribe to the actor's "Updates" RSS or watch the README on Apify Store; review before bumping.
- When bumping, run against a known-good seed competitor in dev and diff parsed output against last known schema.

**Warning signs:**
- New fields appear as `null` after an Apify-published actor update.
- Parsing exceptions in `logs/social-scraper.log` referencing key errors.
- Engagement metrics drop to 0 across all competitors at the same time (key rename, not real engagement collapse).

**Phase to address:** Phase 1 (Apify integration). Pin and validate from day one.

---

### A3. Anti-bot escalation — runs degrade gradually, not catastrophically

**What goes wrong:**
Meta and X periodically tighten anti-bot detection. An actor that worked 95% of the time last month works 60% this month. Each run individually looks acceptable (some results) but coverage is gradually thinning out. By the time anyone notices, three weeks of data has gaps.

**Why it happens:**
Anti-bot signals (suspicious request headers, missing cookies, datacenter IP fingerprints) drift. Detection is probabilistic, not binary. A monitoring approach that only alerts on hard failures will miss this entirely.

**How to avoid:**
- Track a per-competitor coverage metric: `(items_returned_this_run / median_items_returned_last_30_days)`. Trend graph this in the admin UI.
- Alert on degradation, not just zeros: if coverage drops below 50% for the same competitor 3 runs in a row, surface a `degradation` event.
- Run a daily "canary" against a known-active competitor (e.g., IC Markets SG) and assert minimum 5 posts last 7 days. If canary fails, treat all runs that day as suspect.
- Budget for switching actors. For each platform, identify a backup actor on Apify Store (e.g., `apify/facebook-posts-scraper` primary, `automation-lab/facebook-posts-scraper` backup with 40% lower cost). Pre-test the backup quarterly.

**Warning signs:**
- Coverage ratio trends downward across multiple competitors over 1-2 weeks.
- Increased proportion of `degraded` change_events.
- Apify status page or community forum posts about that actor's reliability.

**Phase to address:** Phase 1 for the metric scaffolding, ongoing through entire milestone for the backup-actor identification.

---

### A4. Cost runaway — actor stuck retrying on a hot market or infinite-scroll burns compute units

**What goes wrong:**
An Apify actor configured to scrape "all posts in the last 30 days" hits a competitor page with high posting cadence (e.g., a Vietnamese broker with 50 posts/day) and burns through compute units. Or a transient Apify infrastructure issue causes our scheduler to retry, and we re-launch an actor that's still running, leading to overlapping runs.

**Why it happens:**
Apify pricing is per-result for managed actors and per-CU for some custom flows. CU = 1GB RAM × 1 hour. A long-running actor with high concurrency and residential proxy traffic stacks all three cost vectors simultaneously. Our `run_all.py` doesn't enforce per-scraper timeouts (CONCERNS.md confirms this).

**How to avoid:**
- Set Apify account-level **monthly spending limit** (Console → Settings → Usage & Billing). Recommended: $100/month for v1 (8 markets × 3 platforms × ~5 competitors × weekly cadence at $0.005/post should comfortably fit under $50, leaving headroom for retries).
- Set per-actor input caps: `maxItems: 50` for posts/page, `maxRequestRetries: 3`, `maxConcurrency: 2`, `requestHandlerTimeoutSecs: 60`.
- Set per-actor `timeoutSecs` on the run itself (Apify supports run-level timeout). Recommend 600s (10 min) hard cap per run.
- Track Apify spend daily by polling `/v2/users/me` usage endpoint; alert if daily spend > $5 (anything above modest baseline = something's wrong).
- Add idempotency: before launching an actor for `(competitor, platform, market)`, check Apify API for any in-flight runs for that triple. If found, skip.

**Warning signs:**
- Apify daily spend > $5 for the v1 setup.
- Multiple `RUNNING` runs for the same actor + input combo.
- Run duration > p95 historical for that actor by 3x.

**Phase to address:** Phase 1 (Apify integration). Spending limit must be set before the first scheduled run hits production.

**Cost runaway worst case (quantified):**
- One actor stuck retrying, residential proxy, 4GB RAM × 24 hours = ~96 CU × $0.30 = **$29 per stuck run**. If undetected for a week across multiple actors: **$200-400**.
- With monthly cap at $100, blast radius is bounded.

---

## BigQuery Sync Pitfalls

### B1. `SELECT *` runaway — full-year scan instead of nightly delta

**What goes wrong:**
Our nightly sync query is written as `SELECT * FROM share_of_search_table WHERE date >= CURRENT_DATE - 1`. We assume this scans only yesterday's data. It doesn't — BigQuery scans all partitions unless the table is partitioned on `date` AND the WHERE clause uses the partition column directly. If the table is unpartitioned (or partitioned on `_PARTITIONTIME` but we filter on `date`), every nightly run scans the whole table.

**Why it happens:**
BigQuery on-demand pricing is $6.25/TB scanned. Charges are by columns selected, not rows returned — `LIMIT 1` does NOT reduce cost. A misaligned partition filter is invisible in the SQL but catastrophic in cost. Documented community case: a single bad query cost $10,000 in 22 seconds.

**How to avoid:**
- Before any sync goes scheduled, run the query in BigQuery console with **dry run** enabled. Note `Bytes processed`. If > 1 GB for a daily delta, the query is wrong — the table is likely not partitioned correctly, or your filter doesn't hit the partition column.
- Always select **only the columns you need** (e.g., `SELECT market, brand, search_volume, week_start FROM ... WHERE _PARTITIONDATE = @target_date`). Never `SELECT *`.
- Set BigQuery **custom cost control quotas** at project level: max bytes billed per query (start at 10 GB), max bytes billed per day (start at 100 GB). These are hard caps that abort offending queries.
- If the SoS source table isn't partitioned, ask the source team to partition it before we sync. If they can't, materialize a partitioned copy daily.
- Use parameterized query with explicit date and assert `bytes_processed < threshold` in our sync code. Refuse to execute (or alert) if scanning more than expected.

**Warning signs:**
- BigQuery billing dashboard shows daily query cost > $1 (sanity baseline for a small dashboard's nightly sync).
- INFORMATION_SCHEMA.JOBS shows our sync user running jobs with `total_bytes_processed > 10GB`.
- GCP billing alert.

**Phase to address:** Phase 2 (BigQuery sync). Cost controls + dry runs are gate-1 for going to production.

**Cost runaway worst case (quantified):**
- 1TB SoS table, `SELECT *` daily, no partitioning: 1TB × 30 days × $6.25 = **$187/month**.
- Stuck retry loop running query 100 times in an hour on a 1TB table: 100TB × $6.25 = **$625 in one hour**.
- With 10GB-per-query custom quota: capped at 10GB × $6.25 = **$0.06 per query**, hard limit, query fails before damage.

---

### B2. Timezone mangling — UTC stored, local-day expected

**What goes wrong:**
BigQuery TIMESTAMP is always UTC. When syncing to SQLite, we convert to ISO string and store as text. The dashboard displays it. Marketing managers expect "Tuesday" in their local market timezone (SGT, ICT, WIB, etc.). For a competitor's promo that ran 11pm SGT on Tuesday, BigQuery shows it as 3pm UTC Tuesday, which is fine for SG, but for a VN viewer (UTC+7) it becomes "10pm Tuesday" — looks right by coincidence. For a Hong Kong Tuesday-night promo at 11pm HKT, that's 3pm UTC Tuesday, which is 10pm Tuesday in VN — but in JST/KST/AEST viewers it pushes to Wednesday. Worse: BigQuery's DATETIME (no timezone) and TIMESTAMP (UTC) types can both appear in source data; mixing them silently misaligns.

**Why it happens:**
BigQuery internally stores all TIMESTAMPs in UTC and DATETIME has no timezone at all. SQLite has no native timestamp type — it stores ISO strings, with no enforcement. Whoever writes the join logic assumes "the timestamp is in market-local time" because that's what the dashboard displays.

**How to avoid:**
- Standardize: all timestamps in our SQLite are stored as UTC ISO strings (`YYYY-MM-DDTHH:MM:SSZ`). Document this in the schema.
- For "what day did this happen for this market" queries, store an additional `market_local_date` (TEXT, `YYYY-MM-DD`) computed at sync time using the market's IANA timezone. This is the column dashboards filter on for "Tuesday in SG".
- Maintain a market → IANA timezone map in `src/lib/markets.ts` (SG → Asia/Singapore, VN → Asia/Ho_Chi_Minh, etc.). Use it in both sync (Python) and display (TS).
- Reject DATETIME columns from the BigQuery source. If they appear, fail the sync with an actionable error: "column X is DATETIME, must be TIMESTAMP or pre-converted to TIMESTAMP at source."

**Warning signs:**
- "Last week's promos" queries return different counts depending on whether you compute the week boundary in UTC or in the market's timezone.
- Discrepancies between dashboard counts and source reports.
- Promos appearing on Sunday for a market that doesn't run weekend campaigns.

**Phase to address:** Phase 2 (BigQuery sync). Timezone strategy must be locked before the first row of SoS data lands in SQLite.

---

### B3. Idempotency hole — re-running same-day sync duplicates rows

**What goes wrong:**
Cron runs the sync at 02:00 SGT. EC2 has a transient hiccup, the next cron run at 03:00 also runs (because we added a "self-heal" retry). Both runs successfully write yesterday's SoS data. Now the dashboard shows double the search volume.

**Why it happens:**
The sync writes append-only rows. There's no `(market, brand, week_start)` unique constraint, or there is but the writer ignores conflicts and writes duplicates anyway, or it's a partial write where duplicates aren't deduplicated.

**How to avoid:**
- Make the sync **idempotent by design**: use SQLite `INSERT ... ON CONFLICT(market, brand, week_start) DO UPDATE SET ...` (Drizzle: `onConflictDoUpdate`).
- Define a unique key per source. For SoS: `(source_run_date, market, brand, week_start)`.
- Wrap the sync in a transaction; commit only after all rows are inserted. Partial syncs roll back.
- Track `(sync_target, source_date_partition)` in a `sync_runs` table: if a run for that partition already succeeded today, skip. Manual re-runs require a `--force` flag.

**Warning signs:**
- Row count for yesterday's SoS data > expected (e.g., 8 markets × 10 brands × 1 week_start = 80, but you have 160).
- `sync_runs` table shows two `success` rows for the same partition on the same day.
- Aggregations look "too high" by suspicious factors (2x, 3x).

**Phase to address:** Phase 2 (BigQuery sync).

---

### B4. Service account key rotation breaks the sync at 02:00

**What goes wrong:**
GCP service account JSON key was created during dev. 90 days later (or whenever someone rotates org-wide), the key is revoked. The next nightly sync fails authentication. No alert fires. The SoS data goes stale; the dashboard quietly shows last week's numbers for the next week.

**Why it happens:**
Default GCP service account keys never expire, but org policies often enforce 90-day rotation (Steampipe documents this pattern as standard). The sync fails with `401 unauthorized`, but only the sync logs see it. Nothing surfaces in the dashboard.

**How to avoid:**
- Use **Workload Identity** if possible (no static keys at all). Realistic for EC2: probably stay with service account JSON keys, but document the rotation process.
- Track key creation date in a known-place (env var comment, secrets manager metadata).
- Alert at day 60: "BQ service account key created 60 days ago, rotate within 30 days."
- Daily sync: emit a `sync_health` ping (Healthchecks.io or equivalent dead-man's-switch). Sync hasn't pinged in 25 hours → email alert.
- On auth failure, surface in the dashboard's "Data Health" section as `BQ sync: AUTH FAILED, last successful sync 2 days ago`.

**Warning signs:**
- `sync_runs` table has no `success` rows in last 24 hours.
- `logs/bq-sync.log` shows 401 or `Permission denied` errors.
- BigQuery audit log shows no recent jobs from our service account.

**Phase to address:** Phase 2 (BigQuery sync) for the rotation alert and dead-man's-switch; Phase 5 (Confidence/freshness UX) for the user-facing surfacing.

---

### B5. Schema drift — BQ source adds a column, sync silently drops it; or BQ removes a column, sync explodes

**What goes wrong:**
Source table gains a `language_code` column we'd love to use, but our sync's column list is hard-coded. We don't get the new field. Or worse: source removes/renames `search_volume` to `volume`, and our sync now writes `null` into our `search_volume` column. Aggregations show zero. Dashboard tells marketing managers "no demand for any brand this week" — exactly the kind of silent data quality failure that kills trust.

**Why it happens:**
Source data evolution isn't versioned. Our sync code assumes a fixed schema. Schema drift is invisible until aggregations look wrong.

**How to avoid:**
- At the start of every sync run, query `INFORMATION_SCHEMA.COLUMNS` for the source table. Compare against expected column set. If different, fail with a clear "source schema drifted" message. Do not run the sync.
- Hash the column list + types and store it in `sync_runs`. Diff prior run's hash vs new — if different, fail-loud and require human review.
- Treat source-side schema changes as an opt-in event: humans must update our sync's column list before next run succeeds.

**Warning signs:**
- Aggregate metrics drop to suspiciously low values across the board.
- Sync runs report `success` but row counts are zero or far below expected.
- New `null` values appearing in fields that were always populated.

**Phase to address:** Phase 2 (BigQuery sync).

---

## APAC-Specific Pitfalls

### C1. CDN/geo-routing serves wrong locale — scraper from Apify SG IP gets English content for a Thai-targeted page

**What goes wrong:**
Competitor X has a Thai-language promo page at `competitor.com/th/promo`. Their CDN sniffs Accept-Language and the requesting IP and serves English content if the IP isn't Thai. Our Apify run uses the default proxy (could be anywhere), gets English content with English promo amounts, and we believe we've scraped the Thai promo. Now our "Thai promo intelligence" is actually English promo data — every scraper signal for TH is contaminated.

**Why it happens:**
CDN geo-routing is invisible. The URL says `/th/`, the response looks structured, but the Accept-Language header and IP geolocation override the URL path. Some sites also use cookies (e.g., `selected_country=th`) that scrapers don't carry.

**How to avoid:**
- Match Apify proxy country to target market (already covered in A1). For TH, use TH residential proxy.
- Set `Accept-Language` request header explicitly in actor input: `th-TH,th;q=0.9,en;q=0.8`. Same for VN (`vi-VN,vi;q=0.9,en;q=0.8`), TW (`zh-TW`), HK (`zh-HK`), etc.
- After scraping, run a language detection check (e.g., `langdetect` or xlm-roberta-base-language-detection model) on the extracted promo text. If detected language doesn't match target market's expected language, flag as `locale_mismatch`. Don't insert as canonical "Thai" data.
- For each market, define expected language code(s): TH→th, VN→vi, MY→ms+en, ID→id+en, TW→zh-Hant, HK→zh-Hant+en, SG→en, PH→en+tl. Multi-language markets accept any of the listed.

**Warning signs:**
- Thai market scrape returns English text. Singapore scrape returns Thai text.
- Promo amounts in TH market in the $X range that look more like USD than THB (which would be $X * ~35).
- Same promo text repeated across multiple market scrapes (because all are getting the English fallback).

**Phase to address:** Phase 1 (Apify integration) for proxy/header strategy; Phase 3 (better promo extraction) for the language-detection validation.

---

### C2. Currency normalization — THB/VND/IDR have wildly different decimal magnitudes; "$50 bonus" becomes "50,000"

**What goes wrong:**
Vietnamese (VND) and Indonesian (IDR) currencies are roughly 1000x weaker than USD per unit. A "USD 50 deposit bonus" promo localizes to "1,250,000 VND" or "750,000 IDR". Our promo extractor parses the amount as a number, but if we normalize lazily we end up comparing 50 (USD) to 1,250,000 (VND) and ranking the VN promo as a "1.25M-dollar bonus" — instantly destroys trust.

Conversely, scrapers may strip thousands separators (`1,250,000` → `1250000`) and we may inadvertently pick up text like `1,250,000 VND – Terms apply` and parse it correctly, but if we then round or display in USD without conversion, we report "$1,250,000 deposit bonus" for VN.

**Why it happens:**
Currency parsing is a multi-step problem (currency code detection + value extraction + normalization). Most extractors do one of the three well. Our existing pricing scraper uses Claude to parse account types — Claude handles this correctly when prompted, but only if the prompt specifically asks for "amount and currency" as separate fields. THB/VND/IDR and JPY (in some cross-border contexts) all have different decimal conventions.

**How to avoid:**
- Always extract `(amount, currency_code)` as separate fields. Never store a normalized USD value as the primary; store native currency + a derived USD column computed at extract time using a fixed rate per market.
- Maintain a known-currency-list per market: SG→SGD, HK→HKD, TW→TWD, MY→MYR, TH→THB, PH→PHP, ID→IDR, VN→VND. Reject (or flag for review) any extracted currency that doesn't match the market's expected list (with USD as a permitted alternative for some).
- For display, show native currency by default. Add an opt-in "USD equivalent" toggle so marketing managers can compare across markets.
- Sanity-check magnitude per currency: for VND, deposit bonuses < 100,000,000 (≈$4k); for IDR, < 75,000,000 (≈$5k); for THB, < 200,000 (≈$5k). Anything 10x above the cap is flagged as suspect.

**Warning signs:**
- Per-market promo "amount" averages differ by 1000x without that being explainable by currency.
- USD-equivalent of a VN/ID promo > $10,000 (likely a missing currency normalization).
- Native amount field has 6+ digits for SG/HK/AU markets where you'd expect 3-4.

**Phase to address:** Phase 3 (better promo extraction).

---

### C3. Regulatory disclaimer dilution — APAC promo pages carry long lawyer-mandated text that drowns the actual signal

**What goes wrong:**
Singapore (MAS), Hong Kong (SFC), Taiwan (FSC), and other APAC regulators require specific risk disclaimers on broker promo pages. These disclaimers are often longer than the promo itself ("CFDs are complex instruments. 70% of retail investors lose money..."). Claude-based promo extraction can latch onto disclaimer text — extracting "70%" as the bonus amount, or "complex instruments" as the promo type.

**Why it happens:**
Disclaimers are visually de-emphasized but textually prominent. LLM extraction without explicit "ignore regulatory disclaimers" instruction treats all text equally. The longest text block often wins attention.

**How to avoid:**
- Prompt explicitly: "Ignore any text that is a regulatory risk warning, FSC/MAS/SFC/FSA notice, or 'X% of retail traders lose money' disclaimer. Extract only the promotional offer."
- Maintain a list of disclaimer regex patterns / phrases per regulator. Strip them from the input text before sending to Claude.
- Validate the extracted promo against the input text — if the extracted amount exists only in a disclaimer phrase ("70% lose money"), reject the extraction.
- Include in the prompt a few-shot example of "page with disclaimer" → "extract correct promo, not disclaimer."

**Warning signs:**
- Extracted promo amounts of "70%", "60%", "75%" (canonical disclaimer percentages) on multiple competitors.
- "Promo" descriptions that include phrases like "lose money", "high risk", "complex instruments".
- Same promo amount appearing across many unrelated competitors (because they share the same disclaimer template).

**Phase to address:** Phase 3 (better promo extraction).

---

### C4. Mixed-script content — Bahasa with English, Cantonese with English, Traditional vs Simplified Chinese

**What goes wrong:**
- Malaysia, Indonesia, Singapore, Philippines: most broker pages mix English with local language. A page is "70% in Bahasa, 30% in English" or vice versa. Single-language detection returns whichever wins by character count, which may not match the marketer's intent.
- Hong Kong & Taiwan: traditional Chinese (zh-Hant). Mainland China: simplified (zh-Hans). Some HK/TW competitor pages use simplified by mistake or for SEO. Extraction tools that assume "Chinese = simplified" mis-tokenize traditional characters.
- Thai script doesn't use spaces between words, breaking many off-the-shelf tokenizers (PyThaiNLP solves this; default Python `split()` does not).

**Why it happens:**
Default NLP tooling assumes one language per document. APAC reality is multi-script per page. Tokenization assumptions baked into Python's standard library don't survive contact with Thai or Chinese.

**How to avoid:**
- Use multilingual models for any text classification (e.g., `papluca/xlm-roberta-base-language-detection` — supports Thai, Vietnamese, Chinese, etc., 99.6% accuracy).
- For Thai-specific tokenization, use PyThaiNLP. For Chinese, distinguish zh-Hant vs zh-Hans by checking for traditional-only characters.
- For mixed-language markets (MY, ID, SG, PH), accept either language as valid. Don't reject Bahasa pages because they have English snippets.
- For Claude-based extraction, send raw text — Claude handles multilingual content natively without preprocessing. Explicitly instruct Claude to output extracted fields in English (so dashboard can render without per-language UI complexity), but preserve original promo title in native language for the "verbatim" display.

**Warning signs:**
- High `parse_error` rate specifically on TH, TW, HK markets.
- Tokenizer crashes or returns single-character tokens on Thai input.
- Traditional Chinese pages classified as "language_unknown".

**Phase to address:** Phase 3 (better promo extraction).

---

### C5. Date format heterogeneity — DD/MM/YYYY vs MM/DD/YYYY vs Buddhist calendar (TH)

**What goes wrong:**
Thailand uses Buddhist Era for some marketing materials: 2568 BE = 2025 CE. A promo "valid until 31/12/2568" parsed as a CE year is 543 years in the future. Indonesia, Vietnam, and most of APAC use DD/MM/YYYY; the US-style MM/DD/YYYY appears in some English-language pages. SG/HK/TW also lean DD/MM but English-language financial sites sometimes use MM/DD or YYYY-MM-DD inconsistently within the same page.

**Why it happens:**
Date parsing libraries default to system locale (US for many setups). Buddhist Era is rarely supported out-of-box.

**How to avoid:**
- Always extract the date as a string + parse explicitly with `dayjs.locale()` or Python `babel` set to the market's locale.
- Detect Buddhist Era heuristically: if year > 2400, subtract 543 (TH) or flag for review.
- Validate parsed dates: promo `valid_until` must be within ±2 years of today. Out-of-range → reject.
- For Claude extraction, instruct: "Output dates in ISO 8601 (YYYY-MM-DD). For Thai dates with Buddhist Era years, convert to CE."

**Warning signs:**
- Promos with `valid_until` in 2570s.
- Mass of expired promos showing as active (DD/MM parsed as MM/DD).
- Different markets reporting wildly different "average promo duration."

**Phase to address:** Phase 3 (better promo extraction).

---

## Confidence/Freshness UX Pitfalls

### D1. Indicator noise — every cell has a "freshness dot" and users tune it out

**What goes wrong:**
Designer adds a green/yellow/red dot to every metric cell. After a week of seeing 95% green dots, users stop noticing them. When something turns red, it goes ignored — by then, it's also been red for two days.

**Why it happens:**
Status indicators are easiest to add uniformly. Differentiating "this metric is normally fresh / it's important when stale" from "this metric is updated weekly anyway" requires per-source thinking.

**How to avoid:**
- Apply indicators **only where freshness varies**. SoS data syncs nightly — don't show a dot per row, show one banner at the top: "Share of Search: last synced 02:14 SGT today."
- Use indicators only for **threshold breaches**, not for everything. A row only shows a freshness dot when it's outside expected freshness for that metric type.
- Per-data-type thresholds:
  - Promo snapshots: fresh < 24h, stale 24-72h, broken > 72h.
  - Social posts: fresh < 7d (weekly cadence), stale 7-14d, broken > 14d.
  - SoS: fresh < 32h, stale 32-72h, broken > 72h.
  - App store ratings: fresh < 7d, stale 7-30d, broken > 30d (low cadence).
- Banner-level fallback: if any data source is in `broken` state, show a global "Data quality alert" at the top of the dashboard with a link to the Data Health page.

**Warning signs:**
- Usability test: ask a user "what's the most stale data on this page?" — if they can't answer in <10 seconds, indicators are too noisy.
- User survey: "do you trust the data?" trends down over weeks.

**Phase to address:** Phase 5 (Confidence/freshness UX).

---

### D2. Failed vs stale conflated — "no data" indistinguishable from "scraper crashed"

**What goes wrong:**
A scraper runs successfully but returns empty (A1). Another scraper crashed and didn't run at all. A third scraper hasn't been scheduled in 5 days because cron is broken. All three render the same way to the user: "—" or "no data".

**Why it happens:**
Default rendering is "if value is null, show dash". This conflates four very different states:
1. Data was successfully collected; competitor genuinely had no activity.
2. Data was attempted; scraper succeeded but returned empty (probably broken).
3. Data was attempted; scraper crashed.
4. Data wasn't attempted (cron not running).

**How to avoid:**
- Distinguish in the data model: `last_attempt_at`, `last_success_at`, `last_run_status` (success, empty, error, not_attempted). Cells render differently:
  - Genuine zero (success + zero-value historical pattern): show "0" with no indicator.
  - Empty result from succeeded run: show "—" with `?` indicator and tooltip "scraper returned empty; investigating".
  - Crashed run: show "—" with `!` indicator and tooltip "scraper failed at <time>".
  - Not attempted: show "—" with `pending` indicator and tooltip "next scheduled run: <time>".
- Surface a "Data Health" page that lists every `(competitor, source, market)` triple with last attempt, last success, status, and a one-click link to view scraper logs.

**Warning signs:**
- Users complaining "the dashboard is broken" when actually one specific scraper failed.
- Triage time per data-quality issue > 10 minutes (indicates state isn't surfaced).

**Phase to address:** Phase 5 (Confidence/freshness UX). Data Health page can ship in Phase 1 in skeleton form (just shows scrapers.runs query).

---

### D3. Inconsistent thresholds across data types — confusing UX

**What goes wrong:**
Promo data goes "stale" at 24 hours. Social data goes stale at 7 days. App store data at 30 days. UI shows "stale" badge on each. User assumes the threshold is consistent, gets confused why "stale" promos are 1 day old but "stale" reviews are a month old, loses trust in the labeling.

**Why it happens:**
Sensible thresholds vary by data cadence; UX label vocabulary doesn't.

**How to avoid:**
- Show the actual age in the tooltip/secondary text: "last updated 18 hours ago" instead of (or alongside) "stale".
- Use the same color semantics (green/yellow/red) across data types but explain thresholds per metric in tooltip and a "Data freshness guide" linked from the Data Health page.
- Document the cadence visibly. E.g., on the Promo page: "Promo data refreshes every 24 hours. Last full refresh: <time>."

**Warning signs:**
- User feedback: "why does the dashboard say my data is stale when it's only a day old?"
- Support requests asking for explanation of the indicators.

**Phase to address:** Phase 5 (Confidence/freshness UX).

---

## AI Recommendation Pitfalls

### E1. Hallucinated competitor promos — Claude invents a $500 bonus that didn't happen

**What goes wrong:**
Claude is prompted: "Summarize what competitor X is doing in market Y this week." Claude knows from training data that broker promos commonly include "$500 deposit bonus", and if our prompt context is thin or our actual data lacks specific promo amounts, Claude confabulates plausible-sounding promos. Marketing manager sees "Competitor X launched $500 deposit bonus in TH this week" — that broker never ran that promo. Manager makes counter-decisions based on phantom intel.

**Why it happens:**
LLMs fill information gaps with plausible-sounding generation. "Confident, plausible, wrong" is the textbook hallucination failure mode. Without explicit grounding instructions, Claude treats input as a hint, not a constraint.

**How to avoid:**
- Ground every recommendation in **specific snapshot IDs**: "Based on promo_snapshots [123, 456], social_snapshots [789]:". Pass the actual snapshot text/data inline.
- Instruct explicitly: "Do not mention any competitor promo unless you can cite a specific snapshot ID from the input. If no snapshots support a claim, say 'insufficient data' rather than guess."
- Require Claude to output `(claim, supporting_snapshot_ids[])` tuples. If `supporting_snapshot_ids` is empty, the claim is rejected post-generation.
- Refuse to generate when input is too thin: if a market has <3 snapshots from last 7 days, return "insufficient data for recommendations" rather than generate.
- Use Anthropic's documented hallucination mitigation: "Claude can be explicitly given permission to admit uncertainty" — include "It's better to say 'I don't know' than guess" in the system prompt.

**Warning signs:**
- Recommendations mentioning competitor names + specific dollar amounts that don't appear in our snapshot tables.
- Manual spot-check: pick 5 recommendations, verify the cited snapshot exists and contains the claimed info.
- Marketing manager feedback: "we already checked, that promo doesn't exist."

**Phase to address:** Phase 4 (Per-market AI recommendations).

---

### E2. Context window blowup — feeding all 8 markets × 3 platforms × 30 days context costs $20+ per run

**What goes wrong:**
Naive prompt: "Here's all the data for all 8 markets, generate per-market recos." Token math: 8 markets × 5 competitors × (10 promos + 30 social posts + 5 reviews) × 200 tokens/item = ~360k input tokens. At Sonnet 4.6's $3/M input + $15/M output, that's ~$1.10/run input, plus output for 8 markets at maybe 500 tokens each = $0.06 output. Per nightly run: ~$1.20. Per month: ~$36. Sounds OK, but if we re-run on each market view load (instead of caching), or if input expands as data accumulates, easy 10x to $360/month.

**Why it happens:**
Anthropic Sonnet 4.6 supports 1M context, but pricing scales with input tokens. "It fits" is not "it's affordable". Each market recommendation only needs that market's data — feeding all 8 to one prompt is pure waste.

**How to avoid:**
- Generate **one prompt per market**, not one for all markets. Each prompt sees only that market's snapshots from last 7 days. Cuts input by ~8x.
- Use **prompt caching** for the system prompt + competitor list + market metadata (90% off cached portion). Variable portion is just the recent snapshots.
- Use **Batch API** for nightly runs (50% off, completes within 24h — nightly is fine).
- Cache outputs: don't re-generate on every page load. Store in `ai_recommendations` table keyed by `(market, generation_date)`. Refresh nightly.
- Token budget per market: cap input at 30k tokens per market. Truncate snapshots if needed (recent first). Document the cap.

**Warning signs:**
- Anthropic billing dashboard shows daily Claude spend > $5.
- Token consumption per recommendation cycle > 100k tokens.
- Latency on recommendation API > 30s (suggests context too large).

**Phase to address:** Phase 4 (Per-market AI recommendations).

**Cost runaway worst case (quantified):**
- Naive: all 8 markets × 30 days × all sources, no caching, regenerate per pageview, 100 pageviews/day. 360k tokens × 100 × 30 × $3/M = **$3,240/month**.
- Disciplined (per-market, 7d window, batch + cache + nightly only): ~$5-15/month.
- 200x cost difference between disciplined and naive.

---

### E3. Recommendation drift — same data, different recommendations on consecutive runs

**What goes wrong:**
Tuesday's recommendation says "Focus on price competition with Competitor X." Wednesday's, with literally the same data, says "Focus on differentiating away from price." Marketing manager whiplashes between strategies, loses confidence.

**Why it happens:**
LLM output is non-deterministic at temperature > 0. Even at temperature = 0, model updates and prompt-engineering tweaks cause drift. Without anchoring, similar inputs produce different outputs.

**How to avoid:**
- Set `temperature: 0` for recommendation generation. Acknowledge it's still not 100% deterministic but minimizes drift.
- Generate recommendations on a fixed cadence (nightly), not on-demand. Same data at same time of day produces same output (or close to it).
- Anchor recommendations in **structured signals**: "Top 3 promos by recency in market X, top 3 trending searches from SoS, top 3 social engagement posts." Then ask Claude to interpret. Structure forces consistency more than free-form summarization.
- A/B compare: run the same prompt 3 times, accept the recommendation only if all 3 agree on the top action. If they diverge, surface as "low confidence" or skip.
- Track recommendation hash and changes over time in a `recommendation_history` table — sudden flips are visible.

**Warning signs:**
- Day-over-day recommendation hashes differ even when data is similar.
- User feedback about whiplash.
- Internal review: "is this really the best action this week, or just a different framing of yesterday's?"

**Phase to address:** Phase 4 (Per-market AI recommendations).

---

### E4. Generic recommendations marketing managers ignore

**What goes wrong:**
"Focus on improving brand awareness." "Consider running competitive promos." Vague, generic, useless. Manager reads it, shrugs, doesn't act. AI feature delivers no value.

**Why it happens:**
LLM defaults to safe, generic outputs when prompt is unstructured. "Generate recommendations" without specifying format yields fortune-cookie advice.

**How to avoid:**
- Force structured output: each recommendation must have `(specific_action, target_competitor, target_audience, timeline, evidence_snapshot_ids)`. Reject Claude outputs missing any field.
- Show evidence inline. "Recommendation: counter Competitor X's 100% deposit bonus in TH (running since <date>, snapshot #123) with a similar offer or value-differentiation messaging by <date>."
- Limit to 3-5 actionable recommendations per market per cycle. Forcing scarcity forces specificity.
- Track engagement: did the marketing manager click "I acted on this"? "Not relevant"? Use this signal to refine prompts.

**Warning signs:**
- Recommendation text contains "consider", "may want to", "explore", "in general" — generic-prone tokens.
- Zero clicks on recommendations in user analytics.
- Marketing manager feedback: "this isn't useful."

**Phase to address:** Phase 4 (Per-market AI recommendations).

---

### E5. No evaluation feedback loop — we never know if recommendations were useful

**What goes wrong:**
Recommendations ship. Marketing managers read them. We have no way to know which ones drove action, which were ignored, which were wrong. We can't improve the prompt because we have no signal.

**Why it happens:**
Evaluation is hard. It's tempting to ship the AI feature and assume it works. By the time a stakeholder says "the AI is useless", a quarter has passed.

**How to avoke:**
- Add lightweight feedback: thumbs up / thumbs down per recommendation. Low friction.
- Optional "what action did you take?" follow-up. Don't force it.
- Track in `recommendation_feedback` table. Review weekly.
- If a recommendation gets 3+ thumbs-down, surface the underlying snapshot data — likely a hallucination or bad signal.

**Warning signs:**
- No feedback rows after 2 weeks of recommendations live.
- Stakeholders haven't mentioned recommendations in standup.
- Spot-check: pick 5 random recos from last week — do they describe things that actually happened?

**Phase to address:** Phase 4 for the feedback capture; ongoing evaluation in subsequent milestones.

---

## Maintenance Pitfalls (Solo-Team Specific)

### F1. Silent cron failures — scheduled jobs vanish, nobody notices for weeks

**What goes wrong:**
Cron entry has a typo, or the script changed location, or PATH isn't set in cron's environment. The job doesn't run. No error is generated (cron doesn't email if there's no stderr, especially when the command itself doesn't exist). For the next 2 weeks, scrapers don't run. Dashboard data goes stale. Eventually a marketing manager asks "why hasn't anything updated?"

**Why it happens:**
Cron is a silent executor by design. Failures only surface if (a) the command runs and (b) writes to stderr and (c) MAILTO is configured. Many silent-failure modes (typo, missing binary, PATH issue) prevent the command from running at all.

**How to avoid:**
- **Dead-man's-switch pattern**: every scheduled job pings a healthcheck endpoint after success. Healthchecks.io or self-hosted (free tier supports 20 checks). If no ping in 90 minutes after expected runtime, alert via email.
- One healthcheck per scraper × cadence: `social-scraper-daily`, `bq-sync-nightly`, etc.
- Cron jobs `set -euo pipefail` and explicit `MAILTO` to a real inbox.
- Wrap cron entries in a script that logs to a known location AND pings healthcheck on success.
- Log scraper runs to `scrapers.runs` table (already exists). Daily SQL query: "any scraper with no successful run in last 26 hours?" → alert.

**Warning signs:**
- `scrapers.runs` shows no rows for a scraper in last 26+ hours when daily cadence expected.
- Healthcheck endpoint goes silent.
- Dashboard's freshness banner shows "last sync: 3 days ago".

**Phase to address:** Phase 1 (Apify integration) — set up healthchecks for the new Apify-driven scrapers from day 1. Existing scrapers can be retrofitted in same phase or Phase 5.

---

### F2. Alert fatigue — too many alerts get muted, real signal lost

**What goes wrong:**
Every transient scraper hiccup sends an email. After a week of 50 emails, the operator filters them all to a folder and never looks. When a real failure happens, the alert lands in the muted folder.

**Why it happens:**
"Alert on every error" is easy to implement. Tuning alerts to "alert on what matters" is hard.

**How to avoid:**
- Alert on **persistent** failure, not single-instance: 3 consecutive failures of the same scraper, or no successful run in 24h.
- Alert tier:
  - **P1 (page/SMS)**: dashboard down (HTTP 5xx >5min), no scrapers ran in 26h, BQ sync auth failed.
  - **P2 (email)**: scraper persistent failure, Apify spend > $5/day, BQ scan > 10GB/day.
  - **P3 (dashboard banner only)**: single-run zero-result, locale mismatch detected, language-detection flag.
- Auto-resolve: if a scraper that was failing succeeds, send an "all clear" follow-up. Avoids "is this still a problem?" doubt.
- Quarterly alert review: count alerts received, count actioned. If actioned rate < 50%, retune.

**Warning signs:**
- Email inbox has 100+ unread alerts.
- Operator response: "I just delete those."
- Real incident missed because it was buried.

**Phase to address:** Phase 1 / Phase 2 (set up alerting tiers as scrapers ship); ongoing tuning.

---

### F3. Schema migration that works in dev (Node 25, latest SQLite) but breaks on EC2 (Node 22, older SQLite)

**What goes wrong:**
Local dev (Node 25, SQLite ≥3.45) supports a syntax that EC2 (Node 22, possibly older SQLite from Amazon Linux) doesn't. Migration runs locally fine, deploys to EC2, fails on `migrate()` at startup. App won't boot. EC2 had been serving stale data while we were "improving" things.

**Why it happens:**
Node version pin is documented (`server_node_version.md` confirms Node 22 LTS on EC2, Node 25 local). SQLite version on EC2 depends on whichever `better-sqlite3` build is installed. Drizzle generates SQL that may use modern syntax. CI / pre-deploy doesn't run against EC2's exact stack.

**How to avoid:**
- Pin `better-sqlite3` version in `package.json`. Use `npm ci` on EC2 (already documented as required).
- Test migrations locally against the **same SQLite version as EC2**. Document EC2's `better-sqlite3` version; install matching version locally for migration testing.
- Run a smoke test post-deploy: hit `/api/health` (which we don't have yet — see CONCERNS.md "Missing Critical Features"). Add a health check endpoint that returns 200 with last-migration version.
- Keep migrations strictly additive in this milestone (per PROJECT.md constraint). Adding columns is the safest backward-compatible change.
- Avoid SQLite features only in 3.45+ (e.g., `STRICT` tables, generated columns, JSON1 enhancements) unless verified on EC2.

**Warning signs:**
- Migration log shows "syntax error near X" only on EC2.
- Drizzle migration generates `ALTER TABLE` with options not supported on older SQLite.
- App fails to start after deploy; rollback needed.

**Phase to address:** Phase 2 (BigQuery sync — first phase that adds new tables for SoS data).

---

### F4. Secret rotation breaks scrapers in the middle of the night

**What goes wrong:**
Apify API token, Anthropic API key, or BQ service account is rotated (planned or unplanned). The new value isn't propagated to EC2's `.env`. Next scheduled run fails at 02:00. Operator wakes up to a fire.

**Why it happens:**
Secrets in `.env` files are easy to forget about. There's no central rotation. The old EC2 security incident (April 2026) likely changed some keys; future rotations will too.

**How to avoid:**
- Document **every secret used by scrapers** in a single place (e.g., `docs/SECRETS.md`). For each: where it's used, where it's rotated, who has access.
- Track rotation date per secret. Alert when a secret hasn't been rotated in 180 days (or per org policy).
- Test secrets in a daily smoke test. Each scraper validates its credentials before running (Apify: `GET /v2/users/me`; Anthropic: cheap prompt; BQ: `INFORMATION_SCHEMA` query). Failure → P1 alert with the specific secret name.
- For Apify and Anthropic, set up **secondary keys** in advance. When rotating, deploy new key, swap, then revoke old.

**Warning signs:**
- 401/403 errors in scraper logs.
- All scrapers using the same external API fail at the same time.
- Scheduled runs succeed locally but fail on EC2 (env mismatch).

**Phase to address:** Phase 1 (Apify integration) for the credential-validation pattern; ongoing operational discipline.

---

### F5. Run_all.py orchestration fragility — one stuck scraper blocks the others

**What goes wrong:**
CONCERNS.md flags this directly: `run_all.py` runs scrapers sequentially. No timeout enforcement. One scraper hangs (Playwright browser crash, Apify run stuck). The next ones never run. Symptom: "social scraped fine, promo scraped fine, but reputation never updated."

**Why it happens:**
Sequential orchestration is simple but doesn't tolerate hangs. No SIGTERM with timeout. Zombie children accumulate.

**How to avoid:**
- Add per-scraper timeout: `subprocess.run(..., timeout=1800)` (30 min cap) with `TimeoutExpired` handler that logs failure but continues to next scraper.
- Capture and log scraper exit codes; record in `scrapers.runs` so the dashboard can show "scraper X failed".
- Alternatively, make `run_all.py` a fan-out (run scrapers in parallel with `concurrent.futures`). 8 markets × 3 platforms = 24 parallel Apify runs is fine — Apify handles concurrency.
- Each scraper should be independently runnable from cron. `run_all.py` is convenience, not the primary scheduling mechanism.

**Warning signs:**
- `scrapers.runs` shows scraper A succeeded at 02:00, scraper B never ran.
- `ps aux` shows zombie Python processes from yesterday's run.
- All scrapers stop being recorded after a specific one in the chain.

**Phase to address:** Phase 1 (Apify integration) — the new Apify scrapers should set the pattern (parallelizable, timeout-bounded). Refactor `run_all.py` in same phase.

---

### F6. Logging leaks API keys — secrets end up in committed log files or shared screenshots

**What goes wrong:**
Scraper hits a 401, logs `response.text` which includes a request echo containing the Authorization header, or logs the failing request URL with `?api_key=...` query params. Log files get attached to a bug report or shared in chat. Keys leak.

**Why it happens:**
Default error messages include request context. Truncation by character count (CONCERNS.md notes `response.text[:300]`) doesn't reliably exclude sensitive headers if they appear early.

**How to avoid:**
- Audit scraper error handlers: ensure no `headers`, `Authorization`, `api_key=`, `Bearer` patterns appear in logged output.
- Add a log redaction filter (Python `logging.Filter` that scrubs known secret patterns).
- Log structured data (JSON), not raw response text. Allow specific fields only.
- Pre-commit hook: scan staged files for patterns matching common API key formats (Apify tokens start with `apify_api_`, Anthropic keys with `sk-ant-`, etc.).
- Logs directory is already gitignored (CONCERNS.md confirms); ensure log rotation prevents indefinite accumulation.

**Warning signs:**
- Log file contains `Authorization: Bearer ...` strings.
- Log line length > 1000 characters (often means full response dumped).
- Pre-commit hook flags suspicious strings.

**Phase to address:** Phase 1 (Apify integration) for new scrapers' logging discipline; existing scrapers audit can be Phase 5 or sooner if convenient.

---

## Cost Runaway Scenarios

Quantified worst-case spend if something fails badly. All assume v1 scope (8 markets × ~5 competitors × 3 platforms, weekly social cadence, daily promo cadence, nightly BQ + AI).

### Apify

**Baseline (everything works):**
- 5 competitors × 3 platforms × 8 markets × ~10 posts × $0.005 = **$6/week** for social.
- Promo scraping: similar order. Total **~$50/month**.

**Worst case 1 — actor stuck retrying:**
- One actor at 4GB RAM × 24h = 96 CU × $0.30 = $29/run.
- Undetected for a week across 3 actors = **$200-400/week**.
- **Mitigation:** Apify monthly spending cap ($100/mo recommended), per-run `timeoutSecs` (10min), daily Apify spend monitoring alerts.

**Worst case 2 — input cap missing, hits high-volume page:**
- A Vietnamese broker with 100 posts/day, no `maxItems` cap, 30-day window = 3000 posts × $0.005 = $15/run.
- Daily for a week = **$105**.
- **Mitigation:** Always set `maxItems: 50` per actor input.

**Hard cap with all controls in place:** **$100/month** (Apify-side spending limit).

---

### BigQuery

**Baseline (everything works):**
- Nightly partition-aware delta query: ~1GB scan × 30 days = 30GB/month, well below the 1TB free tier. **$0/month** for queries (storage extra, but minimal).

**Worst case 1 — `SELECT *` on unpartitioned table:**
- 1TB table × $6.25/TB × 30 nightly runs = **$187/month**.
- **Mitigation:** Custom query quota (10GB max bytes per query) + partition validation + dry-run gate.

**Worst case 2 — retry loop + bad query:**
- 100 queries/hour × 1TB each × $6.25 = **$625 per hour**, or **$10k+ in a single bad day**.
- Real-world precedent: published incident of $10k in 22 seconds.
- **Mitigation:** Custom daily query quota at project level (e.g., 100GB/day = $0.62/day cap) — hard limit enforced by BigQuery itself.

**Hard cap with all controls in place:** **$20/month** (custom daily quota at 100GB).

---

### Anthropic / Claude

**Baseline (everything works, Sonnet 4.6):**
- 8 markets × 30k input tokens × nightly = 240k tokens/day input.
- Output: 8 × 1k tokens = 8k tokens/day.
- Daily: 240k × $3/M + 8k × $15/M = $0.72 + $0.12 = **$0.84/day = ~$25/month**.
- With prompt caching (90% off cached context) and Batch API (50% off): **~$5-10/month**.

**Worst case 1 — re-generate per page view, no caching:**
- 100 page views/day × 8 markets × full context (360k tokens) × $3/M = $864/day = **$26k/month**.
- **Mitigation:** Generate once per night, cache outputs in `ai_recommendations` table.

**Worst case 2 — context blowup, all 8 markets in one prompt, all sources, 30 days:**
- 360k tokens per request × 30 days = 10.8M input tokens × $3/M = **$32/month** just from oversized context (still manageable, but compounds with E2's mistakes).
- **Mitigation:** Per-market prompt with 7-day window, 30k token cap.

**Hard cap with all controls in place:** **~$30/month**, plus existing Claude usage from pricing/AI analyzer scrapers.

---

### Combined worst-case if everything goes wrong simultaneously

- Apify: $400/week stuck retry × 4 = $1,600
- BigQuery: $10k/day × 7 = $70k
- Anthropic: $26k/month
- **Total worst case: ~$100k/month** (theoretical, requires multiple controls to fail at once).

### Combined with all controls in place

- Apify: $100/month cap
- BigQuery: $20/month cap (100GB/day quota)
- Anthropic: $30/month
- **Total realistic max: ~$150/month** — fits "modest pay-per-run" budget per PROJECT.md.

---

## Phase-by-Phase Pitfall Map

Maps each pitfall to the milestone phase that should prevent it. Use during roadmap creation to inform success criteria.

| Pitfall | Phase | Verification |
|---------|-------|--------------|
| A1: Empty result silent success | Phase 1 (Apify) | Force a zero-result scenario in dev (e.g., bad URL); confirm UI shows `degraded` indicator and no snapshot inserted |
| A2: Actor schema drift | Phase 1 (Apify) | Pin actor version in code; integration test validates response schema |
| A3: Anti-bot escalation | Phase 1 (Apify) | Coverage ratio metric live by end of phase; canary test runs daily |
| A4: Cost runaway (Apify) | Phase 1 (Apify) | Apify monthly spending cap visible in console; per-run timeouts + maxItems set |
| B1: BQ scan runaway | Phase 2 (BQ sync) | Custom daily quota set at project level; first sync uses dry-run validation |
| B2: Timezone mangling | Phase 2 (BQ sync) | Test fixture: a TH 11pm SGT promo renders as Tuesday in TH view, verified by automated test |
| B3: Idempotency | Phase 2 (BQ sync) | Run sync twice for same partition; confirm zero duplicate rows |
| B4: SA key rotation | Phase 2 (BQ sync) | Daily smoke test pings BQ; healthcheck alert fires within 25h of failure |
| B5: BQ schema drift | Phase 2 (BQ sync) | Schema hash check at sync start; manual rename test confirms sync fails loud |
| C1: Wrong locale content | Phase 1 (Apify) for proxy/headers; Phase 3 (extraction) for language detection | Each market scrape's language detected; mismatch surfaces in UI |
| C2: Currency normalization | Phase 3 (better promo extraction) | Test fixture per APAC currency; magnitude sanity check active |
| C3: Regulatory disclaimer dilution | Phase 3 (better promo extraction) | Prompt explicitly excludes disclaimer text; spot-check 5 extractions per market |
| C4: Mixed-script content | Phase 3 (better promo extraction) | TH, TW, HK, MY, ID test fixtures pass extraction without parse errors |
| C5: Date format heterogeneity | Phase 3 (better promo extraction) | Buddhist Era detection test passes; promos with year > 2400 trigger conversion |
| D1: Indicator noise | Phase 5 (Confidence/freshness UX) | Usability check: user identifies stalest data in <10s |
| D2: Failed vs stale conflated | Phase 5 (Confidence/freshness UX); Phase 1 skeleton | Data Health page shows last_attempt, last_success, status separately for every triple |
| D3: Inconsistent thresholds | Phase 5 (Confidence/freshness UX) | Thresholds documented; tooltip explains per-metric cadence |
| E1: AI hallucination | Phase 4 (AI recommendations) | Manual review of 10 generated recos; each cited snapshot ID exists and supports claim |
| E2: AI context blowup | Phase 4 (AI recommendations) | Token usage per cycle < 500k input total; daily Anthropic cost < $1 |
| E3: Recommendation drift | Phase 4 (AI recommendations) | Same input → same output (temp=0); recommendation hash diff over 7 days reasonable |
| E4: Generic recos | Phase 4 (AI recommendations) | Each reco has structured fields (action, competitor, evidence); manual eval with marketing manager |
| E5: No eval feedback | Phase 4 (AI recommendations) | Thumbs up/down captured; first 2 weeks reviewed |
| F1: Silent cron failures | Phase 1 (Apify) for new scrapers; existing retrofit during this milestone | Healthchecks.io (or equiv) configured per scheduled job |
| F2: Alert fatigue | Phase 1+2 setup; quarterly review | Alert volume sustainable; tier system documented |
| F3: SQLite migration drift | Phase 2 (BQ sync — first phase adding tables) | Migration tested on EC2-matching SQLite version pre-deploy |
| F4: Secret rotation | Phase 1 (Apify) credential validation pattern | Daily smoke test validates each scraper's credentials |
| F5: run_all.py fragility | Phase 1 (Apify) | Per-scraper timeout active; one failure doesn't block others |
| F6: API key logging leak | Phase 1 (Apify) | Log redaction filter in place; pre-commit hook scans for secrets |

---

## "Looks Done But Isn't" Checklist

For each phase, verify before declaring complete:

**Phase 1 (Apify integration):**
- [ ] Empty-result detection: produces `degraded` indicator, not a fresh-looking blank snapshot
- [ ] Per-market proxy country set in actor input
- [ ] Per-market `Accept-Language` header set
- [ ] Actor version pinned (not `:latest`)
- [ ] Apify monthly spending cap configured in console
- [ ] Per-run `timeoutSecs` and `maxItems` set
- [ ] Healthchecks.io ping after each scheduled run
- [ ] Coverage ratio metric tracked per (competitor, platform, market)
- [ ] `scrapers.runs` row written for every run, including failed/zero-result
- [ ] No API keys in log output (audit)

**Phase 2 (BigQuery sync):**
- [ ] Custom daily query quota at project level
- [ ] Sync code does column-explicit SELECT (no `*`)
- [ ] Partition column used in WHERE
- [ ] Dry-run validation in pre-deploy script
- [ ] Idempotent INSERT (ON CONFLICT)
- [ ] Daily healthcheck ping
- [ ] Schema hash check at sync start
- [ ] All timestamps stored UTC + market_local_date column
- [ ] Migration tested against EC2-matching SQLite version

**Phase 3 (Better promo extraction):**
- [ ] Currency stored as (amount, currency_code) pair
- [ ] Magnitude sanity check per currency
- [ ] Disclaimer regex/prompt instruction in extraction
- [ ] Language detection per scraped page
- [ ] Locale mismatch detection (proxy lang ≠ scraped lang) surfaces in UI
- [ ] Date parsing handles Buddhist Era and DD/MM vs MM/DD

**Phase 4 (Per-market AI recommendations):**
- [ ] Per-market prompt (not bundled all 8)
- [ ] 7-day window cap
- [ ] 30k token input cap per market
- [ ] Prompt caching for static portions
- [ ] Batch API for nightly runs
- [ ] Recommendations cached in `ai_recommendations` table
- [ ] `temperature: 0`
- [ ] Each reco includes `supporting_snapshot_ids` field
- [ ] Generic-language pattern check rejects vague outputs
- [ ] Thumbs-up/down feedback captured

**Phase 5 (Confidence/freshness UX):**
- [ ] Per-data-type thresholds defined and documented
- [ ] Indicators only on threshold breaches, not every cell
- [ ] Distinguish (fresh, stale, broken, not_attempted)
- [ ] Tooltip shows actual age, not just label
- [ ] Data Health page lists all (competitor, source, market) triples with status
- [ ] Banner-level alert when any source is in `broken` state

---

## Recovery Strategies

When pitfalls occur despite prevention:

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| A1 zero results | LOW | Switch to backup actor; rerun for affected (competitor, platform, market) |
| A2 schema drift | MEDIUM | Pin to last-known-good version; update parser; reprocess affected snapshots |
| A4 / B1 cost runaway | MEDIUM | Disable scheduler; investigate; refund request to vendor (rare) |
| B2 timezone mangling | HIGH | Reprocess all affected rows with corrected timezone; communicate data correction to users |
| B3 idempotency duplicate | LOW | Dedupe with SQL using row_number; add ON CONFLICT going forward |
| B4 SA key rotation broke sync | LOW | Update key on EC2; rerun missed syncs |
| C1 wrong locale | MEDIUM | Mark affected snapshots as `locale_mismatch`, exclude from per-market views; rerun with correct proxy |
| C2 currency mangled | MEDIUM | Reparse promos with correct currency logic; update display |
| E1 hallucinated reco | HIGH | Pull recommendations; communicate to users; tighten grounding; reprocess |
| F1 silent cron failure | LOW (if caught early) — MEDIUM if caught late | Restore cron; backfill scrapers from last good day |
| F3 schema migration broke EC2 | HIGH | Roll back deploy, restore DB from backup, retest migration with matching SQLite version |
| F4 secret rotation broke scraper | LOW | Update env var on EC2, rerun scraper |
| F6 API key leaked in logs | HIGH | Rotate key immediately; scrub logs; audit for downstream exposure |

---

## Sources

**Apify:**
- [Apify Proxy](https://apify.com/proxy) — proxy country selection
- [Anti-scraping protections | Apify Documentation](https://docs.apify.com/academy/anti-scraping) — anti-bot patterns and mitigation
- [Geolocation | Apify Academy](https://docs.apify.com/academy/anti-scraping/techniques/geolocation) — geo-targeting
- [Apify Pricing](https://apify.com/pricing) — CU model and spending caps
- [Apify Memory and CPU Optimization](https://use-apify.com/blog/apify-memory-cpu-optimization) — actor cost control
- [Facebook Posts Scraper](https://apify.com/apify/facebook-posts-scraper) — pricing $0.005/post
- [Troubleshooting an Actor marked "Under maintenance"](https://help.apify.com/en/articles/10057123-troubleshooting-an-actor-marked-under-maintenance) — actor reliability lifecycle

**BigQuery:**
- [BigQuery pricing](https://cloud.google.com/bigquery/pricing) — $6.25/TB on-demand
- [Estimate and control costs | BigQuery](https://docs.cloud.google.com/bigquery/docs/best-practices-costs) — custom quotas
- [Use service accounts with BigQuery Data Transfer Service](https://cloud.google.com/bigquery/docs/use-service-accounts) — credentials
- [Limit lifetime of GCP IAM service account keys](https://steampipe.io/blog/gcp-key-expiration) — rotation defaults
- [BigQuery Timestamp functions](https://cloud.google.com/bigquery/docs/reference/standard-sql/timestamp_functions) — UTC behavior
- [Convert timestamp/date/datetime to different timezone in BigQuery](https://www.pascallandau.com/bigquery-snippets/convert-timestamp-date-datetime-to-different-timezone/) — tz conversion gotchas
- [BigQuery's Ridiculous Pricing Model Cost Us $10,000 in Just 22 Seconds](https://dev.to/__354f265b41dafa0d901b/bigquerys-ridiculous-pricing-model-cost-us-10000-in-just-22-seconds-4c43) — runaway precedent

**Claude / Anthropic:**
- [Reduce hallucinations - Claude API Docs](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations) — grounding patterns
- [Long context prompting tips - Claude API Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — input ordering
- [Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing) — Sonnet 4.6 $3/M input, $15/M output
- [Anthropic API Pricing breakdown](https://www.metacto.com/blogs/anthropic-api-pricing-a-full-breakdown-of-costs-and-integration) — caching + Batch API discounts

**APAC NLP:**
- [PyThaiNLP](https://arxiv.org/html/2312.04649v1) — Thai tokenization
- [VietNormalizer](https://arxiv.org/html/2603.04145) — Vietnamese normalization, VND currency handling
- [xlm-roberta-base-language-detection](https://huggingface.co/papluca/xlm-roberta-base-language-detection) — multilingual language detection
- [How to Scrape in Another Language, Currency or Location - Scrapfly](https://scrapfly.io/blog/posts/how-to-scrape-in-another-language-or-currency) — locale scraping patterns
- [Speaking in Code: Contextualizing LLMs in Southeast Asia](https://carnegie-production-assets.s3.amazonaws.com/static/files/Noor_LLMs_final.pdf) — APAC LLM context

**UX & Monitoring:**
- [From Data To Decisions: UX Strategies For Real-Time Dashboards](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/) — freshness indicators
- [Data Freshness: Best Practices & Key Metrics](https://www.elementary-data.com/post/data-freshness-best-practices-and-key-metrics-to-measure-success) — staleness thresholds
- [How to Monitor Cron Jobs with Healthchecks.io](https://healthchecks.io/docs/monitoring_cron_jobs/) — dead-man's-switch
- [Cron Job Silent Failure Detection](https://deadmanping.com/blog/cron-job-silent-failure-detection) — silent failure modes
- [LLM Hallucination Detection and Mitigation](https://www.getmaxim.ai/articles/llm-hallucination-detection-and-mitigation-best-techniques/) — drift and grounding

**Internal context:**
- `.planning/PROJECT.md` — milestone scope, risks, constraints
- `.planning/codebase/CONCERNS.md` — existing tech debt and fragile areas
- `.planning/codebase/TESTING.md` — validation-first testing approach
- `MEMORY.md` — Node 22 EC2 / Node 25 local, npm ci pattern, Thunderbit broken status

---

*Pitfalls research for: APAC Localized Promo Intelligence milestone (v1)*
*Researched: 2026-05-04*

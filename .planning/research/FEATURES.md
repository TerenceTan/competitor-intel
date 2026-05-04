# Feature Research — APAC Localized Promo Intelligence v1

**Domain:** Internal competitive intelligence dashboard (forex broker promo monitoring, 8 APAC markets)
**Researched:** 2026-05-04
**Confidence:** MEDIUM-HIGH (most patterns verified across multiple SaaS CI tools; some scraper-output details inferred from Apify actor docs)
**Scope:** Feature-level requirements for THIS milestone only. Generic competitor-intel features (per-market filtering, AI portfolio recommendations, change-event detection) already exist and are out of scope for this research.

---

## Summary

Marketing managers will trust the dashboard if and only if **what they see is correct, attributable, and recent enough to act on**. Everything else (pretty charts, fancy AI prose, hashtag clouds) is secondary to that trust contract. The v1 milestone has six concrete feature surfaces:

1. Per-market promo display — currency, regulator, and language correctness; diff/change visibility
2. Confidence + freshness UX — colored chips on every promo, social, and SoS row; banner-level warnings only when fundamentally broken
3. Per-market AI promo recommendations — specific (named competitor + market + measurable action), not generic
4. Apify social features — engagement deltas, paid-promo disclosure, story/reel detection (table stakes); hashtag clustering (defer)
5. Share of Search views — per-market SoV table, week-over-week deltas, joined-with-promo correlation table (table stakes); brand-trend line per market (differentiator)
6. Anti-features — automated counter-promo execution, real-time alerts, multi-language NLP topic modeling, image OCR on creatives (all explicitly OOS)

The biggest scope-inflation risk is **AI recommendations**: it is easy to spend a phase polishing prose that no marketing manager reads. The single test that matters: would a manager forward this line to their regional director without editing it? If not, it's noise.

---

## Per-Market Promo Display

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Currency-aware promo amounts** — show "$50" with explicit `USD` suffix; show "RM200" not "200" for MY; show "฿1,000" not "1000" for TH | A "200" deposit bonus is meaningless without currency. MY managers expect MYR; TH expects THB. Mis-formatting is an immediate trust killer. | S | Format on render via `Intl.NumberFormat(locale, { style: 'currency', currency })`. Currency code stored on promo row (already exists or trivial schema add). |
| **Promo type taxonomy chip** — fixed set: `deposit-bonus`, `spread-reduction`, `cashback`, `contest`, `referral`, `welcome-credit`, `rebate` | Without category labels managers can't compare apples to apples across competitors. | S | Constrain LLM extraction to enum; reject free-text categories during parse. |
| **Regulator/eligibility chip** — show which regulator the promo applies to (e.g., `CIMA`, `FSC`, `ASIC offshore`) and whether SG/MY/TH residents are eligible | Many APAC promos are explicitly NOT for residents of the regulator's home market (e.g., ASIC promos exclude AU residents). Marketing managers need this to know if a competitor promo is actually competing in their market. | M | Requires extraction prompt to surface eligibility text; default to `unspecified` if not extracted. |
| **Promo source link + screenshot timestamp** — every promo row clickable to source URL, with the "as scraped at" timestamp | Trust requires verifiability. If a manager doubts a value, they need to click through and confirm. | S | URL + scraper timestamp already in `promoSnapshots`. Just surface it. |
| **Promo expiry / "valid until" badge** — show "expires in 5 days", "expired 2 days ago", or "no expiry stated" | Expired promos should not be shown as live. Manager should not act on a 6-week-old promo that ended last week. | S | Parse from extracted text; render with simple date diff. Sort active above expired. |
| **Comparison view: competitor × promo type matrix per market** — rows = competitors, columns = promo types, cells = current offer or "—" | Managers need at-a-glance "do my competitors all offer cashback in TH? what's my gap?" | M | New table component on `/markets/[code]` page. Reuses existing `promoSnapshots` market filter. |
| **Change badge: NEW (last 7d), UPDATED (last 7d), STALE (>30d, scraper still seeing it), DROPPED (last seen >7d ago)** | The whole point of competitive intel is to catch what's *changed*. Static snapshots are low-value. | M | Compute from `MAX(snapshotDate)` per (competitor, promo_hash, market). Already partly in `change_events`. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Inline diff on UPDATED promos** — "spread reduction: ~~0.5 pips~~ → **0.3 pips**" rendered with strikethrough on old value | Managers can see *what* changed without clicking through change feed. Saves ~1 click per row, but compounds across daily review. | M | Pull from `changeEvents.oldValue`/`newValue`. Render via simple JSX diff component. |
| **"Translated from"** badge on non-English source — show original language tag (TH, VI, ID) and indicate dashboard text is LLM-translated summary | Manager can decide whether to trust the translation; can click through to original if doubt. | M | Store `source_lang` on snapshot; tag chip in UI. Translation already happens implicitly during LLM extraction; just surface the source. |
| **Per-market "Pepperstone gap" row** — pin a row at the top of the comparison matrix showing what Pepperstone is currently offering in that market vs. competitors | Most actionable single view: "where am I weaker than the field?" | S | Pepperstone is already a tracked competitor (`pepperstone` ID); just filter to it and pin. |

### Anti-Features (per-market promo display)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Real-time websocket / SSE updates of promo changes | "Wouldn't it be cool if it just appeared?" | Scrapers run on cron (hourly/daily). There is no real-time signal to push. Adds infra complexity for zero data benefit. | "Last updated" timestamp + manual refresh button. |
| Image/banner OCR to extract promo text from creative imagery | Some competitors put promo terms only in banner images | OCR pipeline = new dependency (Tesseract or vision LLM), new failure modes, low extraction accuracy on stylized fonts. Scope explosion. | Defer. If a competitor only advertises in images, current LLM extraction misses it; flag as a known limitation rather than solve. |
| User-editable promo entries / overrides in UI | "What if the scraper misses one?" | Every override creates a divergence between dashboard truth and scraper truth. Corrupts data lineage. | Fix the scraper. Use admin DB edits as escape hatch. |
| Multi-currency conversion ("show all promos in USD") | Comparison ease | Conversion rates change daily; stored conversions go stale; live conversion adds API dependency. Managers want *native currency* anyway because that's what their customers see. | Show native currency only. Add a tooltip with USD-equivalent estimate as a stretch goal in v1.x. |

---

## Confidence / Freshness UX

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Per-row freshness chip** with three states: GREEN (`<24h`), YELLOW (`1–7 days`), RED (`>7 days` or scraper-failed) | The single most-cited need in the project doc ("data quality risk"). Without this, every dashboard view is suspect. | S | Compute `Date.now() - snapshotDate`; map to chip. Existing `<TimeAgo>` component is the natural place. Add color via Tailwind classes. |
| **Per-row extraction confidence chip**: HIGH / MEDIUM / LOW based on parse-quality signal from the scraper | Some promos have all fields cleanly extracted; others are partial. Manager needs to know which to trust. | M | Add `extraction_confidence` column to `promo_snapshots` (`high`/`medium`/`low`); compute at scraper time based on field-completeness heuristic (e.g., missing currency + missing amount → low). |
| **Tooltip on chips** — hover/tap reveals: "Scraped at 2026-05-03 14:22 UTC. Source: brokersofforex.com/octa-thailand. Parsed: full schema match." | Power users want to verify; casual users ignore tooltips. Cost is negligible. | S | Native `title` attribute or shadcn `<Tooltip>` (already in dependencies). |
| **Page-level stale-data banner** when ANY scraper for the current market hasn't run successfully in >48h | Already exists (`stale-data-banner.tsx`); needs to be market-aware | S | Existing component; just thread `?market` through and check market-specific scraper runs. |
| **"Scraper failed" empty state** — when a scraper has 0 successful runs in 7d for this market, show explicit "We couldn't reach [Competitor X]'s [TH] promo page since [date]" instead of silent empty rows | Silent empty = "competitor has no promos" (false). Loud failure = "scraper is broken" (true). | S | Replace empty array render with `<EmptyState reason="scraper-failed" .../>`. |
| **Color is never the only signal** — chips include text label and icon, not just hue | Color-blind accessibility is table stakes; also relevant for cross-team forwarding (screenshots in Slack lose context). | S | Already a known-good pattern in the codebase via `<SeverityBadge>`. Mirror the convention. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Confidence-aware sort** — sort promo table by confidence DESC by default; manager sees high-confidence rows first, low-confidence at bottom | Reading order = trust order. Subtle but compounding ROI. | S | Default sort param. |
| **Weekly "data quality digest" line in executive summary** — "This week: 142 promos extracted across 8 markets; 12% flagged low-confidence; 3 scraper failures for VN." | Pre-empts the "is the data right?" Slack message from stakeholders. | M | Aggregate from existing `scraper_runs` + new `extraction_confidence` column. |
| **"Why is this low confidence?"** expander — click to see what fields were missing or what parse error fired | Managers who burn ~3 minutes investigating once will trust the chip forever after. | M | Store parse errors / missing-field list as JSON column on snapshot. |

### Anti-Features (confidence UX)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Numeric confidence score (e.g., "0.87") | Looks scientific | Three-bucket categorical (HIGH/MED/LOW) is easier to act on. Continuous scores invite false precision and threshold-quibbling. | Three buckets. Tooltip can mention reasons but not numerics. |
| User-adjustable confidence thresholds in UI | "Power users want to tune" | Adds settings surface, persistence layer, and per-user state. Maintenance cost outweighs the ~0 users who will actually tune it. | Hardcoded thresholds in a single config constant. Iterate based on feedback. |
| Confidence on individual fields within a promo (e.g., "amount: HIGH, expiry: LOW") | Granularity ideal | UI gets noisy; managers don't read field-level chips. | Roll up to row-level. Reveal field-level only in expander. |
| Predictive freshness ("data will go stale at...") | Cute | Cron schedule is documented; "data will be refreshed at 02:00 UTC" is enough. | Static "next scheduled run" footer line. |

---

## AI Recommendations (Per-Market, Promo-Specific)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Named-entity recommendation** — every recommendation must reference (a) a specific competitor, (b) a specific market, (c) a specific promo or change | Generic prose ("monitor closely") is filler. Specific prose ("Octa launched a 50% rebate in TH on 2026-04-30") is signal. | M | Extend prompt to require `{competitor, market, promo_type, observation, suggested_action}` JSON output. Reject prose without those fields. |
| **Suggested action verb is concrete** — "match", "counter with X", "ignore", "investigate further" — never "consider", "monitor", "be aware" | Vague verbs = ignored recommendations. Concrete verbs = forwardable to a regional director. | S | Prompt constraint: `suggested_action` must start with one of an enumerated list of verbs. |
| **Per-market grouping** — recommendations grouped under market headings, not interleaved | Marketing managers operate per-market; a SG manager doesn't care about TH recommendations. | S | Group by `market` field. Already supported by `?market=` filter for filtering down to one. |
| **Severity / urgency tag** — `act-this-week`, `act-this-month`, `informational` | Existing AI insights have severity already. Promo recs need same so managers can triage. | S | Reuse `severityBadge` component. |
| **Source-promo backlink** — every recommendation links to the underlying promo row (and that row's source URL) | Trust = verifiability. "Why are you recommending this?" must be one click away. | S | Store `source_promo_id` on the recommendation row. |
| **"Ignore this" / "Acted on this"** dismissal control persisting per-user | Without dismissal, the same recommendation appears every page load and managers tune it out. | M | Adds `recommendation_status` table keyed by (rec_id, user_id). Schema cost is small but real. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Counter-promo suggestion sketch** — for high-severity recs, AI proposes a specific Pepperstone counter (e.g., "Consider a 0.3-pip spread reduction on AUDUSD for THB-funded accounts, valid 14 days, capped at $50k notional volume.") | This is the difference between "intel tool" and "marketing copilot." Big lift in perceived value. | L | Higher prompt complexity, lower confidence in output, more risk of bad suggestions. Gate behind a "draft" badge so users know it's not pre-approved. |
| **Recommendation rationale: 1-line "why this matters"** — single sentence explaining the business logic ("Octa's 50% rebate in TH undercuts our retention offer for THB accounts.") | Managers don't always know why a fact is significant; rationale teaches the system's reasoning and builds trust. | M | Prompt extension; minor token cost. |
| **Weekly-digest mode** — Sunday-night summary email/page with the top 3 actionable recs per market for the upcoming week | Push, not pull. Catches managers who don't open the dashboard daily. | L | Email infra is real work; defer to v1.x unless the marketing-portal already has email. |

### Anti-Features (AI recommendations)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Auto-execution / auto-launch of counter-promos | "Why not just let the AI launch?" | Compliance, regulator approval, brand voice, account-economics — none of these are AI-decidable. Auto-execution is a career-ending bug waiting to happen. | Suggestions only, with explicit "draft — review before launching" labeling. |
| AI-generated competitor sentiment analysis ("traders feel positive about Exness in TH") | Sounds insightful | Without sufficient social text + ground truth, sentiment outputs are noise dressed as data. Fails the "would you forward this unedited?" test. | Defer until social-data fundamentals are stable AND we have ground-truth labels. |
| Free-form chat-with-the-data interface ("ask me anything") | Trendy | Open-ended chat invites hallucination; managers need structured, predictable outputs. MCP server already serves this need for power users. | Keep recs structured. MCP for ad-hoc queries. |
| AI-written competitor "personality profiles" | Engaging | Pure fluff; no manager has ever forwarded one. | Don't build. |
| Daily / hourly recommendation regeneration | "Always fresh" | Most insights are stable for days; daily regen burns tokens for marginal value and creates a noisy "X new recommendations" badge that managers tune out. | Regenerate on scraper-completion or weekly cadence. |

---

## Social Data Features (Apify-Backed)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Per-market post engagement (likes/comments/shares) over last 30 days** as bar/line chart per platform | Without this, the "social" tab is a follower-count museum. Engagement is the actual leading indicator. | M | Apify FB/IG/X actors return per-post likes/comments/shares/views/timestamps. Aggregate weekly per (competitor, market, platform). |
| **Post type breakdown: post / reel / story / video** | Reels and stories drive different engagement; managers need to know what *format* competitors are using. | S | Apify actors expose `media_type`, `is_video`, `is_reel`. Render as stacked bar. |
| **Recent top posts panel** — top 5 posts by engagement in last 30d per competitor + market, with link out | Concrete examples ("Octa's reel about THB cashback got 12k likes") are forwardable. Aggregate numbers aren't. | S | Sort by engagement DESC, LIMIT 5. |
| **Paid-promo disclosure flag** — boolean: "this post is marked as paid partnership / sponsored content" | Apify actors expose this when present. Knowing a competitor is paying for distribution is intel. | S | Pass-through field from scraper. Display as a "Paid" chip on the row. |
| **Per-market account selection** — competitor accounts per market are explicit (Octa-TH ≠ Octa-Global); follower trends per market account | Many competitors run market-specific IG/FB pages. Treating them as one global account loses the per-market signal entirely. | M | Schema change: `social_accounts(competitor_id, platform, market_code, handle)`. Backfill needed. |
| **Engagement-rate normalization** — show engagement / follower count, not just raw engagement | Big accounts with low engagement rates ≠ small accounts with high engagement rates. Raw counts mislead. | S | `(likes + comments) / followers` per post; aggregate. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Promo-mention detection in post captions** — flag posts whose caption matches the active-promo set ("found 14 IG posts mentioning the new 50% rebate") | Cross-correlates social activity with promo intel. Strong signal of marketing push intensity. | M | Substring match on caption against active-promo terms; store boolean column. |
| **Posting cadence per market** — "Octa is posting 3x/day in TH but 0x/week in MY this month" | Cadence shift = strategy shift. Managers should know. | S | Group by week; count posts. |
| **Top hashtags last 7d per (competitor, market)** | Hashtag clustering reveals campaign themes. | M | Frequency count from Apify caption field; LIMIT top 10. |

### Anti-Features (social)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Hashtag *clustering* / topic modeling (e.g., k-means or LLM-based topic groups) | "What themes are trending?" | Requires substantial tuning; clusters drift; output rarely actionable beyond what raw top-hashtag list already shows. Big maintenance liability. | Top-N raw hashtags. Defer clustering. |
| Sentiment analysis on competitor posts | "Are people responding positively?" | Engagement-rate is a stronger and cheaper proxy. Sentiment NLP is expensive in cost + maintenance for marginal accuracy gain. | Engagement-rate over raw counts. |
| Automated comment-scraping (collecting comment text for sentiment) | Depth | Large data volume, low signal-to-noise, increased Apify spend, GDPR/PII risk on user-generated content. | Don't store comment text. Counts only. |
| TikTok / YouTube Shorts coverage | "More platforms = more data" | OOS per project doc. Stabilize FB/IG/X first. | Defer to next milestone. |
| Image/video creative download + thumbnail display | Visual richness | Storage cost (R2/S3 needed), DMCA risk, scrape-cost ×N. Manager can click out. | Link out to original post; don't host media. |
| Comparing follower counts across markets when accounts are global | Easy "metric" | Global account ≠ market account. Mixing them produces misleading numbers. | Per-market account model only. |

---

## Share of Search Features

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Per-market SoS ranking table** — competitors ranked by SoS within market, current week | First view managers want: "where am I ranked in TH this week?" | S | After nightly BQ → SQLite sync, simple `ORDER BY sos DESC GROUP BY market`. |
| **Week-over-week (WoW) delta column** — `+2.3pp` / `−1.1pp` arrows next to each competitor row | Static rankings get boring fast. WoW tells the story of who's gaining. | S | `LAG()` SQL or two-week join. |
| **Pepperstone-row pinning** — Pepperstone always pinned + highlighted in the table | Manager's first instinct: "where am I?" Pinning saves a scroll. | S | UI sort tweak. |
| **SoS trendline per market** — 12-week line chart of top 5 brands' SoS over time | Trend = direction of travel. Single-point ranks are not enough. | M | Recharts (already in stack). One line per competitor. |
| **"Last synced from BigQuery"** timestamp on the SoS view | Standard freshness pattern; managers will ask "is this current?" | S | Mirror the freshness chip pattern. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **SoS-vs-promo correlation panel** — for each market, table showing weeks where SoS spiked alongside an active promo from the same competitor (or didn't) | This is the killer view that justifies BQ → SQLite (vs. Looker iframe). Joins SoS with promo data in SQL. Concrete answer to "do their promos move search?" | M | SQL join on (week, competitor, market). Compute correlation or just visualize side-by-side. |
| **SoS leader/laggard alerts in AI recs** — "Octa's SoS in TH grew +4.2pp WoW — your last 4 weeks of SoS in TH have been flat. Investigate Octa's TH posts and promos this week." | Auto-surfaced via existing AI rec pipeline. Otherwise the SoS data sits unread. | M | Extend AI prompt to include SoS deltas as input. |
| **Brand-share-of-voice donut per market (current week)** | Snapshotable / screenshot-friendly for monthly reports. | S | Recharts `<PieChart>`. |

### Anti-Features (SoS)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| Live BQ-on-render queries (instead of nightly sync) | "Always-current data" | Per-render BQ cost + latency + auth complexity. Project decision (already locked) is nightly sync. | Nightly sync. Document "data is up to ~24h old" on the page. |
| Embedded Looker Studio iframe | Cheap | Already considered + rejected (no SQL joins with promo/social data). | Render in Next.js using SQLite-synced data. |
| Forecasting / predicted-SoS line | "What's next quarter look like?" | Forecast accuracy on weekly brand-search data is poor; would mislead managers. | Show history only. Let humans forecast. |
| Daily SoS sync (more often than nightly) | Freshness | BQ source itself is daily/weekly cadence; syncing more often than the source updates buys nothing. | Nightly. |
| SoS for non-tracked competitors ("show me everyone in TH") | Comprehensive view | Each new tracked competitor adds scraper + maintenance burden across other domains. SoS without matching promo/social data is orphaned. | Match SoS competitor list to existing tracked-competitor list. |

---

## Anti-Features for v1 (Cross-Cutting — Explicit OOS for This Milestone)

Single consolidated list of things deliberately NOT built this milestone. Each one will be tempting to add mid-phase; pre-committing to OOS prevents scope drift.

| Anti-Feature | Why It's Tempting | Why OOS for v1 | Reconsider When |
|--------------|-------------------|----------------|------------------|
| **Real-time alerting (email/Slack/webhook on new promo)** | "Marketing will love instant alerts" | Cron is not real-time; alerts add config UI, dedup logic, delivery infra. | After daily-cadence is verified working and managers ask for it explicitly. |
| **Mobile-app version / native mobile UI** | Stakeholder convenience | Existing dashboard is responsive; native app is a separate product. | Never on this codebase — falls under marketing-portal. |
| **Multi-user permissions / per-market role-based access** | "Only TH manager should see TH" | Single shared password is fine for a small internal team. RBAC is ~weeks of work. | If team grows or external sharing is needed. |
| **Historical-promo time-machine (browse promos as of date X)** | "Audit trail" | Snapshots already store history; a UI to browse it is a separate feature. | If a stakeholder asks for it twice. |
| **Image OCR for banner-image promo extraction** | "Some competitors only show promos in images" | OCR pipeline = new dependency, low accuracy, high failure modes. | If LLM extraction proves systematically incomplete *and* a vision LLM API is already in stack. |
| **Multi-language sentiment / topic modeling** | "We have non-English markets" | Each language adds NLP tuning + maintenance × 8 markets. | Never on this dashboard — defer to a dedicated NLP workstream if needed. |
| **Automated counter-promo generation/launch** | "Close the loop end-to-end" | Compliance, regulator, brand-voice, account-economics — none AI-decidable. Career-risk. | Never automated. Suggestions only. |
| **Currency conversion to USD-equivalent** | "Easier comparison" | Live FX rates = new dependency; static rates go stale; managers want native currency anyway. | If managers explicitly ask twice. v1.x maybe. |
| **Free-form chat-with-data UI on the dashboard** | Trendy | MCP server already serves this for power users. Free-form chat in dashboard invites hallucination. | Use MCP for ad-hoc queries. Don't build chat in dashboard. |
| **Per-user dashboards / saved views / personal filters** | "Customization" | Adds user-state persistence layer; minimal benefit at small team size. | If team grows to >10. |
| **Comment-text scraping from social (sentiment dataset)** | "Capture audience reaction" | Volume + low signal + PII risk. | Defer. Engagement-rate is a sufficient proxy. |
| **TikTok / YouTube Shorts / Telegram coverage** | "More platforms" | OOS per project doc. Fix FB/IG/X first. | Next milestone earliest. |
| **CN / IN / MN markets** | Coverage completeness | OOS per project doc. CN needs Weibo/Douyin/WeChat + Chinese NLP. | CN as separate workstream; IN in v1.5; MN deferred indefinitely. |
| **Postgres migration / schema redesign** | "Future-proof the schema" | OOS per project doc. Soft dependency on marketing-portal cutover. | Next milestone. Keep schema additions in this milestone simple. |
| **Numeric confidence scores (0.0–1.0)** | Looks scientific | Three-bucket categorical is more usable. | Probably never; keep three-bucket. |
| **Hashtag clustering / topic modeling** | "Trend detection" | High maintenance, low actionability vs. raw top-N hashtag list. | If raw top-N proves insufficient over time. |

---

## Complexity Map

| Feature | Complexity | Phase Hint |
|---------|------------|------------|
| Currency-aware promo formatting | S | Promo-display phase |
| Promo type taxonomy chip | S | Extraction phase (scraper-side) |
| Regulator/eligibility chip | M | Extraction phase |
| Source link + scrape timestamp visibility | S | Promo-display phase |
| Promo expiry badge | S | Promo-display phase |
| Competitor × promo-type matrix per market | M | Promo-display phase |
| Change badge (NEW/UPDATED/STALE/DROPPED) | M | Change-detection phase |
| Inline diff on UPDATED promos | M | Change-detection phase |
| Translated-from badge | M | Extraction phase |
| Pepperstone-gap row | S | Promo-display phase |
| Per-row freshness chip (3-state) | S | Confidence-UX phase (foundational) |
| Per-row extraction confidence chip | M | Confidence-UX phase + scraper phase |
| Confidence tooltip detail | S | Confidence-UX phase |
| Market-aware stale-data banner | S | Confidence-UX phase |
| Scraper-failed empty state | S | Confidence-UX phase |
| Confidence-aware default sort | S | Confidence-UX phase |
| Weekly data-quality digest line | M | Confidence-UX phase |
| "Why low-confidence" expander | M | Confidence-UX phase |
| Named-entity AI recommendation (structured fields) | M | AI-rec phase |
| Concrete-verb constraint | S | AI-rec phase |
| Per-market grouping of AI recs | S | AI-rec phase |
| AI rec severity tag | S | AI-rec phase (reuses existing) |
| AI rec source-promo backlink | S | AI-rec phase |
| AI rec dismissal control | M | AI-rec phase |
| Counter-promo suggestion sketch | L | AI-rec phase (stretch) |
| AI rec rationale line | M | AI-rec phase |
| Per-post engagement chart | M | Social phase |
| Post-type breakdown | S | Social phase |
| Top posts panel | S | Social phase |
| Paid-promo disclosure flag | S | Social phase (scraper field passthrough) |
| Per-market social account model | M | Social phase (schema change) |
| Engagement-rate normalization | S | Social phase |
| Promo-mention detection in posts | M | Social phase + cross-domain join |
| Posting cadence chart | S | Social phase |
| Top hashtags per (competitor, market) | M | Social phase |
| Per-market SoS ranking table | S | SoS phase (post BQ-sync) |
| WoW delta column on SoS | S | SoS phase |
| Pepperstone pinning on SoS | S | SoS phase |
| SoS 12-week trendline | M | SoS phase |
| BQ-sync timestamp on SoS view | S | SoS phase |
| SoS-vs-promo correlation panel | M | SoS phase (the killer view) |
| SoS spikes feeding AI recs | M | AI-rec phase + SoS phase |
| Brand SoV donut | S | SoS phase |

---

## Dependencies

```
[Apify scraper integration]
    └──unlocks──> [Per-post engagement chart]
    └──unlocks──> [Post-type breakdown]
    └──unlocks──> [Top posts panel]
    └──unlocks──> [Paid-promo disclosure flag]
    └──unlocks──> [Posting cadence chart]
    └──unlocks──> [Top hashtags]
    └──unlocks──> [Promo-mention detection in posts] (also needs promo extraction)

[Per-market social account model (schema change)]
    └──prerequisite-for──> [Per-market engagement chart]
    └──prerequisite-for──> [Engagement-rate normalization]

[Improved promo extraction (LLM prompt + schema constraints)]
    └──unlocks──> [Promo type taxonomy chip]
    └──unlocks──> [Regulator/eligibility chip]
    └──unlocks──> [Currency-aware formatting] (needs structured currency field)
    └──unlocks──> [Promo expiry badge]
    └──unlocks──> [Per-row extraction confidence chip] (needs parse-quality signal)
    └──unlocks──> [Competitor × promo-type matrix] (needs taxonomy)
    └──unlocks──> [Translated-from badge]

[Per-row extraction confidence chip]
    └──enables──> [Confidence-aware default sort]
    └──enables──> [Weekly data-quality digest]
    └──enables──> ["Why low-confidence" expander]

[Per-row freshness chip]
    └──foundational-for──> [Trust contract — every other view depends on it]

[Change-event detection (already exists, needs extension)]
    └──unlocks──> [Change badge NEW/UPDATED/STALE/DROPPED]
    └──unlocks──> [Inline diff on UPDATED promos]

[BigQuery → SQLite nightly sync]
    └──unlocks──> [Per-market SoS ranking]
    └──unlocks──> [WoW delta]
    └──unlocks──> [SoS trendline]
    └──unlocks──> [SoS-vs-promo correlation panel]   ← needs promo data also
    └──unlocks──> [SoS spikes feeding AI recs]
    └──unlocks──> [Brand SoV donut]

[Structured AI rec output (named-entity, JSON-shaped)]
    └──unlocks──> [Per-market grouping]
    └──unlocks──> [Severity tag]
    └──unlocks──> [Source-promo backlink]
    └──unlocks──> [Concrete-verb constraint]
    └──unlocks──> [Dismissal control] (needs stable rec IDs)
    └──unlocks──> [Counter-promo suggestion sketch] (further extension)

[Confidence + freshness UX — foundational]
    └──blocks-trust-of──> [All AI recommendations]
    └──blocks-trust-of──> [All Share of Search views]
    └──blocks-trust-of──> [All social engagement views]
```

### Dependency Notes

- **Confidence/freshness UX is foundational and should land in an early phase, not a late polish phase.** If the data-quality risk materializes mid-milestone (a competitor changes their promo page format, a scraper silently breaks), confidence chips are the difference between "users notice the broken data and Slack us" vs. "users keep acting on bad numbers and lose trust permanently."
- **Apify integration must precede all social features**, but its output schema directly drives which features are cheap (engagement, post-type, paid-flag — already returned) vs. expensive (engagement-rate-normalized requires also fetching follower count; cadence requires also storing post timestamps over time).
- **Per-market social account model is a one-time schema cost** that pays back across every social feature. Doing it before any social UI work is built is much cheaper than retrofitting.
- **Extraction-confidence chip depends on the scraper emitting a parse-quality signal**, not just the dashboard rendering one. If we can't agree on the heuristic, fall back to a simpler "all required fields present" boolean (HIGH/LOW only, skip MEDIUM).
- **AI rec dismissal-control needs stable recommendation IDs.** Today, recs may be regenerated each scraper cycle and re-key; if dismissal is to persist, recs must have a content-hash-derived stable ID. Decide before building dismissal, not after.
- **SoS-vs-promo correlation panel is the single biggest justification for nightly BQ-sync over Looker iframe.** If this view is cut for time, the case for nightly sync weakens. Protect it from de-scoping.
- **Counter-promo suggestion sketch (the L-complexity differentiator)** can be entirely cut for v1 without breaking anything else. It is the single best dial for time-pressure response: cut early, ship the rest.

---

## Sources

- [Klue — How AI Helps with Competitive Intelligence](https://klue.com/topics/how-ai-helps-with-competitive-intelligence) — actionable vs. generic AI rec patterns; battlecard-style structuring
- [Crayon — Crayon vs Klue](https://www.crayon.co/crayon-vs-klue) — what mature CI tools track (websites, promos, app stores, news, social, reviews); battlecard-as-structured-output pattern
- [Smashing Magazine — UX Strategies For Real-Time Dashboards](https://www.smashingmagazine.com/2025/09/ux-strategies-real-time-dashboards/) — "Live / Stale / Paused" indicators, manual-refresh UX, last-updated timestamp as table stakes
- [Sifflet — Data Freshness in Data Observability](https://www.siffletdata.com/blog/data-freshness) — freshness signals as an observability primitive
- [Box Blog — Confidence Scores for Box Extract API](https://blog.box.com/confidence-scores-box-extract-api-know-when-rely-your-extractions) — pattern of confidence scores driving human-in-the-loop review queues; numeric vs. categorical tradeoff
- [Carbon Design System — Status Indicator Pattern](https://carbondesignsystem.com/patterns/status-indicator-pattern/) — severity-classified status indicators (high/medium/low attention) as a design-system primitive
- [Bloomberg UX — Designing the Terminal for Color Accessibility](https://www.bloomberg.com/ux/2021/10/14/designing-the-terminal-for-color-accessibility/) — color + non-color cues (icons, patterns) for accessibility, including in financial-data UIs
- [Apify — Instagram Scraper](https://apify.com/apify/instagram-scraper) — fields available from FB/IG/X actors: caption, hashtags, mentions, likes, comments, views, media type, timestamps, paid-partnership flag
- [Branquo — Share of Search Reports](https://branquo.com/) — SoS visualization patterns (rank table, trendline, WoW deltas)
- [42 Signals — Measuring Share of Search](https://www.42signals.com/blog/measuring-your-share-of-search-a-visual-guide-to-tracking-and-improvement/) — visual conventions for SoS dashboards
- [Pencil & Paper — Dashboard Design UX Patterns](https://www.pencilandpaper.io/articles/ux-pattern-analysis-data-dashboards) — "last updated" timestamp on each card; badge/pill conventions for status alerts
- [Mobbin — Badge UI Design](https://mobbin.com/glossary/badge) — change-badge ("NEW"/"UPDATED") sizing, contrast, color rules
- [Quadcode — Forex Broker Marketing Plan](https://quadcode.com/marketing-guide) — APAC forex marketing context; localized currency / language expectations per market
- [DailyForex — Best Asian Forex Brokers](https://www.dailyforex.com/forex-brokers/best-forex-brokers/asia) — APAC competitive set; regulator-by-market context (MAS, SC, BNM, BAPPEBTI, BoT/SEC TH)
- Project doc — `.planning/PROJECT.md` (HIGH confidence — direct source of milestone scope, OOS list, decision log)
- Codebase doc — `.planning/codebase/STRUCTURE.md` and `.planning/codebase/ARCHITECTURE.md` (HIGH confidence — confirms existing components: `<DataSourceBadge>`, `<TimeAgo>`, `<SeverityBadge>`, `stale-data-banner`, market URL filter, change-event noise floor)

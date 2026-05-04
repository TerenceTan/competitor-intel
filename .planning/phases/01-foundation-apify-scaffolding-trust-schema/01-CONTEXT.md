# Phase 1: Foundation — Apify + Scaffolding + Trust Schema - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning
**Mode:** Auto (decisions selected from research recommendations; user can amend before planning)

<domain>
## Phase Boundary

Replace the broken Thunderbit social pipeline with a pinned Apify-based scraper that delivers fresh Facebook data for the global market for at least one competitor; in the same PR install all maintenance scaffolding (zero-result detection, healthchecks, run timeouts, log redaction, version pinning, Apify spending cap) and the trust-UX schema (confidence columns, scraper-failed empty state, skeleton Data Health page) that everything in Phases 2–5 will build on.

**In scope:** SOCIAL-01, SOCIAL-04, SOCIAL-05, SOCIAL-06, INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, TRUST-01, TRUST-04, TRUST-05, EXTRACT-05 (13 requirements).

**Out of scope (this phase, in roadmap):**
- Instagram and X scraping (Phase 2)
- Per-market fanout to APAC markets (Phase 2)
- BigQuery sync and SoS table (table delta lands in Phase 1 PR per cross-cutting requirements; sync code is Phase 3)
- Better promo extraction (Phase 3)
- AI per-market recommendations (Phase 4)
- Full freshness pill / hover tooltip UX (Phase 5)

</domain>

<decisions>
## Implementation Decisions

### Apify integration

- **D-01: New file `scrapers/apify_social.py`.** New module, sibling to `scrapers/social_scraper.py`, replacing the Thunderbit `_thunderbit_extract()` call site for FB only in Phase 1. Keeps the YouTube path in `social_scraper.py` untouched. Phase 2 extends the same file to IG and X. *(Source: research/ARCHITECTURE.md — sibling-to-social_scraper, no Node.js path.)*
- **D-02: Python SDK `apify-client` v2.5.0** (PyPI). Python-only scraper layer; do not introduce a Node.js scraping path for this integration. *(Source: STACK.md headline decision #1.)*
- **D-03: Synchronous actor invocation.** Call pattern `client.actor("apify/facebook-posts-scraper").call(run_input=...)`. No webhooks, no async polling — matches existing scraper-as-cronjob pattern. *(Source: ARCHITECTURE.md.)*
- **D-04: Phase 1 actor: `apify/facebook-posts-scraper` only**, version pinned to a specific tag (TBD by planner — must NOT use `:latest`). IG (`apify/instagram-scraper`) and X (`apidojo/tweet-scraper`) deferred to Phase 2.
- **D-05: One competitor for the Phase 1 demo.** Choose a competitor with a known public Facebook page that returns >0 posts (planner picks from `scrapers/config.py`). Acceptance: dashboard displays non-stale FB posts/follower count for that competitor in the global market view.
- **D-06: Apify spending cap = $100/month**, set in the Apify Console before the first scheduled run. Manual operator step (cannot be enforced from code). Documented in the deploy runbook and verified in Phase 1 acceptance checklist.

### Zero-result detection (silent-success guard)

- **D-07: After every actor call, assert `dataset.itemCount > 0`.** On zero results, write a `change_events` row of type `scraper_zero_results` (with competitor_id, platform, market_code, run_id metadata) and skip the snapshot insert entirely. *(Source: SUMMARY.md headline decision #3.)*
- **D-08: New table `apify_run_logs`** (additive migration). Columns at minimum: `run_id`, `actor_id`, `actor_version`, `competitor_id`, `platform`, `market_code`, `started_at`, `finished_at`, `status`, `dataset_count`, `cost_usd`, `error_message`. Used by Data Health page and Phase 5 confidence pipeline. *(Source: SOCIAL-05, ARCHITECTURE.md.)*

### Healthchecks (silent-cron guard)

- **D-09: Healthchecks.io (free tier).** Each scheduled job pings on success. Free tier covers 20 checks; current scraper count fits comfortably. Self-hosted and `MAILTO`-based monitoring rejected — Healthchecks.io ships immediately and integrates as a single curl per cron. *(Source: PITFALLS.md, SUMMARY.md cross-cutting requirements.)*
- **D-10: One ping URL per scheduled scraper**, stored as env vars (`HEALTHCHECK_URL_APIFY_SOCIAL`, `HEALTHCHECK_URL_PROMO`, etc.). Pings happen at successful completion only — failures rely on Healthchecks.io's missed-ping alarm.

### Run timeouts (hung-scraper guard)

- **D-11: Per-scraper timeout enforced in `run_all.py`** orchestrator using `subprocess.run(..., timeout=1800)` (30 minutes) per scraper invocation. On timeout, kill that subprocess, log the failure, write `scraper_runs` failure row, continue with the next scraper. *(Source: INFRA-02, PITFALLS.md F5.)*

### Log redaction (secret-leak guard)

- **D-12: Python logging Filter at the root logger** applied across all scrapers. Filter strips known secret values (loaded from `os.environ` for `THUNDERBIT_API_KEY`, `SCRAPERAPI_KEY`, `ANTHROPIC_API_KEY`, `YOUTUBE_API_KEY`, plus new `APIFY_API_TOKEN`, `HEALTHCHECK_URL_*`) plus common token patterns (`Bearer [...]`, `apify_api_*`, hex strings >32 chars in known positions). Applied via a new `scrapers/log_redaction.py` module imported at the top of every scraper entry-point. *(Source: INFRA-03, PROJECT.md EC2 incident history.)*

### Schema deltas (trust + diagnostics + cross-cutting)

- **D-13: Additive migrations only.** New columns/tables only; no FK changes to existing tables; new columns get defaults so existing rows don't need backfill. Pattern matches existing `scrapers/db_utils.py` migration code (additive `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN`). *(Source: INFRA-05, ARCHITECTURE.md, PROJECT.md constraint to keep future Postgres migration cheap.)*
- **D-14: Phase 1 schema deltas (all in one PR):**
  - `ALTER TABLE promo_snapshots ADD COLUMN extraction_confidence TEXT` (values: `'high' | 'medium' | 'low' | NULL`)
  - `ALTER TABLE social_snapshots ADD COLUMN extraction_confidence TEXT`
  - `CREATE TABLE IF NOT EXISTS apify_run_logs (...)` per D-08
  - `CREATE TABLE IF NOT EXISTS share_of_search_snapshots (...)` — table only, no Phase 3 sync code yet (lands schema early to amortize an EC2 deploy cycle, per SUMMARY.md cross-cutting requirements)
- **D-15: Drizzle schema in `src/db/schema.ts` updated to match** the SQLite migrations so TypeScript types stay accurate. Both must land in the same PR; Drizzle types lagging Python migrations is an explicit pitfall to avoid.

### Trust UX skeleton (Phase 1 footprint)

- **D-16: `<EmptyState reason="scraper-failed">` React component** placed at `src/components/ui/empty-state.tsx`. Reads from `scraper_runs` (existing) and `apify_run_logs` (new) to detect failed/zero-result runs and render a visually distinct empty state vs. "no competitor activity." Used in social view rows during Phase 1; reused by all per-market views in later phases.
- **D-17: Data Health page at `/admin/data-health`.** Server component (`force-dynamic`) — no client-side data fetching this phase. Shows: per-scraper status (last successful run, last failure, zero-result count over 7d), Apify cost-to-date for the current month (from `apify_run_logs.cost_usd` SUM), and total scraper run count. Minimal styling — table layout using existing shadcn Table component. Phase 5 polishes it. *(Source: TRUST-05, SUMMARY.md cross-cutting.)*
- **D-18: Confidence column populated at insert time** by the new Apify scraper. `'high'` when actor returned a complete post object (all required fields non-null); `'medium'` when partial; `'low'` when the row was inferred or partial. Confidence reading by UI components is Phase 5 — Phase 1 just persists the field.

### EXTRACT-05 calibration set

- **D-19: JSONL format at `scrapers/calibration/promo_extraction.jsonl`**, one labeled item per line: `{"market": "TH", "language": "th", "input_text": "<scraped page snippet>", "expected_output": {"promo_type": "...", "value": "...", "currency": "...", "valid_from": "..."}, "source_url": "..."}`. 20–30 items per non-English language (TH, VN, TW, HK, ID). Hand-labeled by the team owner in Phase 1; ownership is the dashboard maintainer.
- **D-20: Validation script at `scrapers/calibration/validate_extraction.py`.** Runs the existing extraction prompt against each input, compares structured output to expected, reports per-language accuracy. Phase 1 acceptance: ≥85% accuracy on the labeled set per language; markets failing the bar are flagged and noted in CONTEXT.md for Phase 3 prompt iteration.
- **D-21: Calibration is Phase 1 deliverable, NOT a Phase 1 blocker for Apify cutover.** Apify cutover for FB Phase 1 demo can ship without calibration completing — calibration gates Phase 3 (when extraction is improved), not Phase 1. Both proceed in parallel during Phase 1.

### Claude's Discretion
- Specific Apify actor version tag for `apify/facebook-posts-scraper` — planner picks from current Apify Store actor history; pin to a recent stable release.
- Specific competitor for the Phase 1 demo — planner picks from `scrapers/config.py` competitors list; prefers one with a confirmed-active public FB page returning >0 posts on a manual test query.
- Exact column types for `apify_run_logs` and `share_of_search_snapshots` (TEXT vs INTEGER vs REAL choices) — planner follows existing column-type conventions in `src/db/schema.ts`.
- Run input parameters for Apify actors (`maxPosts`, `resultsLimit`, etc.) — planner picks reasonable defaults that balance freshness with cost; verifies projected cost fits the $100/mo cap with margin.
- Healthcheck.io account creation, project setup, and ping URL provisioning — operator task; planner produces the runbook entry.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level
- `.planning/PROJECT.md` — Project context, milestone scope, validated baseline, out-of-scope, top risks (data quality, maintenance burden), key decisions log
- `.planning/REQUIREMENTS.md` — All 36 v1 requirements with REQ-IDs and per-phase traceability mapping
- `.planning/ROADMAP.md` — 5-phase milestone structure, success criteria per phase, parallelization notes
- `.planning/STATE.md` — Project state, open questions carried forward (per-market vs. global accounts, BQ table identity, calibration set sourcing)

### Research (this milestone)
- `.planning/research/SUMMARY.md` — Synthesized research with headline decisions, recommended phase shape, cross-cutting requirements; **read first**
- `.planning/research/STACK.md` — Apify SDK selection (Python `apify-client` v2.5.0), `@google-cloud/bigquery` v8.3.0, Claude Sonnet 4.6 multilingual approach, no new proxy/NLP layers
- `.planning/research/FEATURES.md` — Confidence/freshness UX as foundational (not polish), AI rec quality bar, anti-features for v1 (hashtag clustering, sentiment, OCR — out of scope)
- `.planning/research/ARCHITECTURE.md` — Component placement (`scrapers/apify_social.py`, `scrapers/share_of_search_sync.py`), full schema deltas in DDL, build order, parallelization map; **single most actionable research doc for planners**
- `.planning/research/PITFALLS.md` — Apify silent-success (A1), actor versioning (A2), Apify cost runaway (A4), silent cron (F1), `run_all.py` fragility (F5), log leaks (F6), failed-vs-stale UX (D2). Each pitfall has detection + prevention guidance.

### Existing codebase (read for patterns and integration points)
- `.planning/codebase/ARCHITECTURE.md` — Existing system layout (Next.js + SQLite + Python scrapers, EC2 cron)
- `.planning/codebase/INTEGRATIONS.md` — Existing scraper integrations (Thunderbit, ScraperAPI, YouTube, Anthropic), env var conventions, secrets pattern
- `.planning/codebase/STACK.md` — Existing dependency versions (Next.js 15.2.4, React 19, Drizzle 0.45.1, better-sqlite3 12.8.0, anthropic 0.40.0)
- `.planning/codebase/CONVENTIONS.md` — Naming patterns (snake_case Python, camelCase TS, PascalCase components), import organization, ESLint config
- `.planning/codebase/STRUCTURE.md` — File and directory layout (`src/app/(dashboard)/admin/`, `scrapers/`, `src/components/`)
- `.planning/codebase/TESTING.md` — How the codebase is tested (informs prevention strategy for new scraper)
- `.planning/codebase/CONCERNS.md` — Existing concerns documented during codebase mapping (relevant for `run_all.py` fragility and other touched areas)

### External docs (referenced during planning)
- Apify Python client: https://docs.apify.com/api/client/python (verify API surface for `client.actor(...).call(...)` and dataset access)
- Apify FB posts scraper: https://apify.com/apify/facebook-posts-scraper (input schema, output schema, pricing, recent version history)
- Apify proxy docs: https://docs.apify.com/platform/proxy (`apifyProxyCountry` parameter behavior — full list in Phase 2)
- Healthchecks.io docs: https://healthchecks.io/docs/monitoring_cron_jobs/ (ping URL pattern, missed-ping policy)

### File targets (where new code will land)
- `scrapers/apify_social.py` — NEW; Apify FB scraper module
- `scrapers/log_redaction.py` — NEW; logging filter for secret redaction
- `scrapers/calibration/promo_extraction.jsonl` — NEW; hand-labeled calibration set
- `scrapers/calibration/validate_extraction.py` — NEW; calibration validator
- `scrapers/db_utils.py` — MODIFIED; add new migrations (`apify_run_logs`, `share_of_search_snapshots`, confidence columns)
- `scrapers/run_all.py` — MODIFIED; per-scraper timeout enforcement, healthcheck pings
- `scrapers/social_scraper.py` — MODIFIED; route FB calls to `apify_social.py` instead of `_thunderbit_extract()`; YouTube path stays
- `src/db/schema.ts` — MODIFIED; mirror SQLite migrations into Drizzle schema
- `src/components/ui/empty-state.tsx` — NEW; `<EmptyState reason="scraper-failed">` component
- `src/app/(dashboard)/admin/data-health/page.tsx` — NEW; skeleton Data Health page
- `src/lib/constants.ts` — MODIFIED; add new SCRAPERS entry for `apify_social` if list-driven

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scrapers/db_utils.py`**: Existing additive-migration pattern — every Phase 1 schema delta should mirror it. Also exposes `detect_change()` and `log_scraper_run()` write helpers that the new Apify scraper must use (not bypass) so existing change-detection + run-tracking continues to work.
- **`scrapers/run_all.py`**: Existing orchestrator; needs minimal changes (add per-scraper subprocess timeout + healthcheck ping wrapper). Already structured as a SCRIPTS list — the Apify scraper just gets added.
- **`scrapers/config.py`**: Existing competitor list with social handles — pick a competitor with a known active FB page from here for the Phase 1 demo. Don't re-invent competitor selection.
- **`scrapers/market_config.py`**: Existing per-market URL config — Phase 2 extends this; Phase 1 only needs `global` market.
- **`src/components/layout/stale-data-banner.tsx`**: Existing stale-data UX pattern — `<EmptyState>` should be visually consistent with this. Reuse styling tokens.
- **shadcn Table component**: Already in the codebase — use it for the Data Health page table layout.
- **`scraper_runs` table** (existing in schema): Already tracks scraper success/failure with timestamp; Data Health page reads from this for last-run-status. Don't duplicate it.
- **`change_events` table** (existing): Already used for change detection; new `scraper_zero_results` event type is just a new value in the existing `event_type` column.

### Established Patterns
- **Cron + Python scraper writing to SQLite via `db_utils`**: Every existing scraper follows this pattern. New `apify_social.py` must too — no new write paths to SQLite.
- **Snapshot tables (`*_snapshots`)**: Every snapshot row carries `(competitor_id, market_code, scraped_at)` plus type-specific fields. New columns added in Phase 1 follow this rule.
- **`force-dynamic` server pages with parallel `Promise.all` queries**: Pattern for the Data Health page — no client fetching needed.
- **Env var secrets in `.env.local`**, never committed: Apify token, Healthcheck URLs, BigQuery service-account JSON path all follow this pattern.
- **Naming**: Python = snake_case files/functions; TS = camelCase functions, PascalCase components/types; SQL columns = snake_case; constants = UPPER_SNAKE_CASE.
- **Schema migrations**: Additive only, run on startup via `db_utils.py`. Drizzle types in `src/db/schema.ts` updated alongside.

### Integration Points
- **Apify scraper → existing change/run-log infrastructure**: New scraper writes to `social_snapshots` (existing), `apify_run_logs` (new), `change_events` (existing), `scraper_runs` (existing) via `db_utils.py` helpers.
- **`run_all.py` → new healthcheck pings**: Wrap each subprocess invocation in a try/finally that pings `HEALTHCHECK_URL_*` on success, lets failure bubble to Healthchecks.io's missed-ping alarm.
- **Data Health page → existing tables**: Joins `scraper_runs`, `apify_run_logs`, and `change_events` via SQL. No new ORM model needed; raw `db.select()` calls in Drizzle.
- **`<EmptyState>` component → social view rows**: Wraps existing social card/row rendering. Renders the failed-state variant when the corresponding `scraper_runs` row is failure or `apify_run_logs` count for that (competitor, platform, market) shows zero results in the last run.
- **Drizzle schema → SQLite migrations**: Both must update together — Drizzle types lagging is an explicit pitfall.

</code_context>

<specifics>
## Specific Ideas

- **Failure visualization parity with marketing-portal**: If the marketing-portal uses a specific empty-state pattern, mirror it for visual consistency across the team's tooling. (Cross-repo check — flag if anything close exists.)
- **Apify cost dashboard pattern**: The Data Health page's "Apify cost-to-date" should feel like a cost-tracker, not just a number. A simple "$X.XX of $100/mo cap" string with the percentage works for Phase 1 — color-coded if >70%.
- **One competitor demo target**: Pick a competitor whose FB page actually publishes recent content (not a dormant page). Verify with a manual Facebook page visit before settling on the choice.

</specifics>

<deferred>
## Deferred Ideas

- **Visualping / Wayback diff for promo page changes** — would complement Apify-scraped social with website-side diffing. Not in this milestone (out of scope per PROJECT.md).
- **Slack/email alerting on healthcheck failure** — Healthchecks.io's free tier supports email; Slack webhook integration is a paid feature. Phase 1 uses email only; Slack alerts are a future enhancement (no requirement covers it in this milestone).
- **Auto-rotating Apify actor versions when current pin reaches EOL** — interesting maintenance automation but explicit anti-feature for this milestone (manual version tracking is the v1 trust contract).
- **Per-actor cost projections in the Data Health page** — Phase 1 shows total Apify spend; per-actor breakdown is Phase 5 polish.
- **Calibration set automation (synthetic data generation)** — current calibration is hand-labeled; auto-generation is interesting but adds verification debt. Defer.

### Reviewed Todos (not folded)
None — no todos in the project todo list at phase init.

</deferred>

---

*Phase: 1 — Foundation: Apify + Scaffolding + Trust Schema*
*Context gathered: 2026-05-04*

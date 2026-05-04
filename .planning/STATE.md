---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Plan 01-04 complete; Wave 3 first plan landed (run_all.py hardened with 1800s subprocess timeout + HC.io ping helper); only Plan 01-05 (Data Health page) remains in Phase 1; operator follow-ups for Plan 04 are 9 HEALTHCHECK_URL_* env vars + 9 HC.io checks
last_updated: "2026-05-04T06:36:53Z"
last_activity: 2026-05-04 -- Plan 01-04 executed (scrapers/run_all.py timeout + healthcheck wrapper + scrapers/test_run_all_smoke.py 5 unittest cases; INFRA-02 + INFRA-04 closed)
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 6
  completed_plans: 5
  percent: 83
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-04)

**Core value:** Promo intelligence per market — competitor promo activity broken down by market, accurate enough that marketing managers trust it.
**Current focus:** Phase 01 — foundation-apify-scaffolding-trust-schema

## Current Position

Phase: 01 (foundation-apify-scaffolding-trust-schema) — EXECUTING
Plan: 5 of 6 complete (next: 01-05 EmptyState scraper-failed variant + /admin/data-health page + Thunderbit FB removal — Wave 3 final)
Status: Executing Phase 01 — Wave 3 in progress (01-04 done)
Last activity: 2026-05-04 -- Plan 01-04 executed (scrapers/run_all.py timeout + healthcheck wrapper + scrapers/test_run_all_smoke.py 5 unittest cases; INFRA-02 + INFRA-04 closed)

Progress: [████████▎░] 83%

## Performance Metrics

**Velocity:**

- Total plans completed: 5 (01-01, 01-02, 01-06, 01-03, 01-04)
- Average duration: ~8.4 min
- Total execution time: ~42 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01    | 5     | ~42m  | ~8.4m    |

**Recent Trend:**

- Last 5 plans: 01-04 (~3m), 01-03 (~3m), 01-02 (~3m), 01-06 (~30m), 01-01 (~3m)
- Trend: Wave 3 first plan (01-04 run_all hardening) closed in ~3m — same shape as the small atomic Wave 1/2 plans. Phase 1 has held a tight ~3-min cadence on every wiring plan; the only ~30-min outlier is 01-06 (calibration validator). Final Phase 1 plan (01-05 Data Health page) is a UI plan and may extend beyond ~3m.

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Pre-milestone: Build APAC promo deepening before Postgres migration (stakeholder pressure + soft dependency)
- Pre-milestone: Apify pay-per-run actors over Bright Data committed plans
- Pre-milestone: Nightly BigQuery → SQLite sync over Looker iframe (preserves SoS-vs-promo joins)
- Pre-milestone: 8 APAC markets in v1; IN to v1.5; CN as separate workstream; MN deferred
- Pre-milestone: Confidence/freshness in v1, not deferred (data quality is a top milestone risk)
- Plan 01-01: Reused existing try/except + CREATE TABLE IF NOT EXISTS idempotent migration pattern in db_utils.py — no schema_version table introduced (matches existing 7+ ALTER blocks)
- Plan 01-01: apify-client install deferred to EC2 (local Python is 3.9.6, below 3.10+ runtime floor); requirements.txt pin is what matters for this plan
- Plan 01-01: Local migration applied via DB_PATH override because config.py hardcodes EC2 production path; production EC2 will run migration naturally on first scraper invocation
- Plan 01-02: Shipped RESEARCH.md Pattern 5 verbatim for SecretRedactionFilter (no improvements deemed safer than diverging from a reviewed, requirement-anchored pattern); hoisted 6-char min-secret-length floor into a named _MIN_SECRET_LEN constant
- Plan 01-02: Applied min-secret-length floor to HEALTHCHECK_URL_* prefix scan in addition to the named env-var list (forward-compat hardening; Plan 04 URLs are >>6 chars so not a regression)
- Plan 01-02: Used stdlib unittest with snake_case test_* names and tearDown env pop — matches plan's hard "no pytest dependency on bare EC2 Python" constraint
- Plan 01-02: Snapshot-at-init secret loading pattern (read os.environ once in __init__, not per filter() call) adopted as the convention for future scraper-side secret-aware filters/validators
- Plan 01-03: RESEARCH.md Patterns 1/2/3 shipped verbatim for actor.call() + zero-result branch + apify_run_logs finally-block — diverging from reviewed, requirement-anchored patterns deemed not safer
- Plan 01-03: ACTOR_BUILD pinned to 1.16.0 as auto-mode reasonable default (the example tag in the plan); APIFY_BUILD_VERIFIED.txt records this with explicit operator-follow-up flag; same pattern Plan 01-01 used for EC2 Python verification gate
- Plan 01-03: Imported COMPETITORS from scrapers/config.py at module level (not via db_utils.get_all_brokers()) to avoid get_db()-triggered migration at import time; DB connection deferred to log_scraper_run() inside run()
- Plan 01-03: Apify scraper boilerplate convention established for future Apify modules: install_redaction() before apify_client import; pinned ACTOR_BUILD with marker-file attestation; per-call max_total_charge_usd; zero-result silent-success guard; always-insert apify_run_logs in finally
- Plan 01-03: Marker-file-attested operator gate pattern: when checkpoint:human-action cannot be served autonomously (no console/SSH access), write marker file with documented reasonable default + explicit operator follow-up flag; downstream tasks proceed; SUMMARY surfaces the follow-up
- Plan 01-04: RESEARCH.md Pattern 4 shipped verbatim for the subprocess.run(timeout=) + try/except subprocess.TimeoutExpired wrapper and the _ping_healthcheck helper — anchored to D-09/D-10/D-11 + INFRA-01/02/04, diverging would force re-review for no functional gain
- Plan 01-04: Module-preamble install_redaction() placed AFTER PROJECT_ROOT/SCRAPERS_DIR/LOGS_DIR computation but BEFORE the SCRIPTS list — earliest correct slot in run_all.py; required adding `sys.path.insert(0, SCRAPERS_DIR)` with idempotency guard since the orchestrator did not have one before
- Plan 01-04: Per-script log header expanded from 2 lines (Run at: + Exit code:) to 3 lines (Run at: + new Status: TIMEOUT|OK|FAILED + Exit code:) — preserves backward-compat for any external log-parsing automation while making OK/FAILED/TIMEOUT triage immediately scannable
- Plan 01-04: Smoke tests deliberately do NOT mock subprocess.run — RESEARCH.md "Don't Hand-Roll" guidance: subprocess.run(timeout=) is documented Python stdlib and trusting it at this layer is appropriate; integration test is implicit in EC2 cron run
- Plan 01-04: Belt-and-braces tearDown: pop HEALTHCHECK_URL_APIFY_SOCIAL unconditionally even when setUp didn't capture a saved value — defends against test pollution if a future test or harness sets the env var out of band

### Pending Todos

None yet.

### Blockers/Concerns

- **Operator follow-ups before EC2 deploy of Plan 03:** (1) Re-verify Apify actor build tag at https://console.apify.com/store/apify~facebook-posts-scraper > Builds tab; auto-mode default of `1.16.0` may need updating in BOTH `scrapers/apify_social.py` `ACTOR_BUILD` constant AND `.planning/phases/01-foundation-apify-scaffolding-trust-schema/APIFY_BUILD_VERIFIED.txt`; (2) set `APIFY_API_TOKEN` in EC2 `.env.local` from Apify Console > Settings > Integrations > Personal API tokens; (3) set Apify Console monthly $100 spending cap (Settings > Usage limits) per D-06; (4) carryover Plan 01-01 Task 0 EC2 Python ≥3.10 verification — write `.planning/phases/01-foundation-apify-scaffolding-trust-schema/EC2_PYTHON_VERIFIED.txt`; (5) `pip install -r scrapers/requirements.txt` on EC2 (installs apify-client==2.5.0 from Plan 01-01 pin); (6) one-time smoke test `python3 scrapers/apify_social.py` and verify `apify_run_logs` row + either `social_snapshots` row OR `change_events scraper_zero_results` row.
- **Operator follow-ups before EC2 deploy of Plan 04:** (1) Provision 9 Healthchecks.io checks (one per scraper: pricing_scraper, account_types_scraper, promo_scraper, social_scraper, apify_social, reputation_scraper, wikifx_scraper, news_scraper, ai_analyzer) at https://healthchecks.io with appropriate cron schedules + grace periods; (2) copy each check's ping URL into EC2 `/home/ubuntu/app/.env.local` (and local `.env.local` if you want pings during local testing) as `HEALTHCHECK_URL_<SCRIPT_NAME_UPPER>` (e.g. `HEALTHCHECK_URL_APIFY_SOCIAL=https://hc-ping.com/<uuid>`); (3) smoke-test wiring on EC2 by running `python3 scrapers/run_all.py` (or waiting for next cron) and verifying each scraper produces a "ping received" event in HC.io; (4) optional belt-and-braces — add HC.io email/Slack notification rules so missed pings page someone within 1–4h. **No code change required** — orchestrator picks up URLs the moment env vars are present.
- Open question: Per-market vs. global social account split for current competitor list — verify before Phase 2 kicks off (impacts Phase 2 scope and Apify cost projection by 5–8×)
- Open question: BigQuery SoS table name, dataset, project ID, partition column — confirm with data team before Phase 3
- Open question: Calibration set sourcing for TH/VN/TW/HK/ID promo extraction (EXTRACT-05) — needs ~20–30 hand-labeled items per language during Phase 1
- Coverage note: REQUIREMENTS.md contains 36 v1 requirements; planning context referenced 32 — all 36 are mapped to phases below

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-05-04T06:36:53Z
Stopped at: Plan 01-04 complete; Wave 3 first plan landed (run_all.py hardened with 1800s subprocess timeout + HC.io ping helper); only Plan 01-05 (Data Health page) remains in Phase 1; operator follow-ups for Plan 04 are 9 HEALTHCHECK_URL_* env vars + 9 HC.io checks
Resume file: .planning/phases/01-foundation-apify-scaffolding-trust-schema/01-05-PLAN.md

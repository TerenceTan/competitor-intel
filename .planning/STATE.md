---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 1 wave-4 gap closure complete — 10/10 plans shipped (01-01..01-10); SC2 + SC3 closed (scraper-failed EmptyState wired into Digital Presence; Data Health zero-result lookup correct); WR-01..05 closed (ACTOR_TO_SCRAPER equality, apify_social conn-leak/confidence fixes, calibration validator broker_name fix, run_all.py honest redaction-coverage comment); ROADMAP SC5 reconciliation note added per D-21; ready to transition to Phase 2 (Per-Market Social Fanout) once Phase 1 operator follow-ups (Apify token + cap, EC2 Python check + pip install + smoke run, 9 Healthchecks.io URLs) are completed
last_updated: "2026-05-04T08:10:00Z"
last_activity: 2026-05-04 -- Wave 4 gap closure executed (01-07/08/09/10 in parallel worktrees; SC2/SC3 + WR-01..05 closed; ROADMAP SC5 reconciliation per D-21)
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 10
  completed_plans: 10
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-04)

**Core value:** Promo intelligence per market — competitor promo activity broken down by market, accurate enough that marketing managers trust it.
**Current focus:** Phase 01 — foundation-apify-scaffolding-trust-schema

## Current Position

Phase: 01 (foundation-apify-scaffolding-trust-schema) — COMPLETE (all 10 plans shipped, including Wave 4 gap closure)
Plan: 10 of 10 complete (Wave 4 gap closure: 01-07 SC2 + 01-08 SC3/WR-01/03/04 + 01-09 WR-02 + 01-10 WR-05)
Status: Phase 1 + gap closure complete — ready to transition to Phase 2 (Per-Market Social Fanout) once Phase 1 operator follow-ups are completed
Last activity: 2026-05-04 -- Wave 4 gap closure executed (01-07/08/09/10 in parallel worktrees; SC2/SC3 + WR-01..05 closed; ROADMAP SC5 reconciliation per D-21)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 10 (01-01, 01-02, 01-06, 01-03, 01-04, 01-05, 01-07, 01-08, 01-09, 01-10)
- Average duration: ~6.4 min
- Total execution time: ~64 min (Wave 1-3: ~46m; Wave 4 gap closure: ~18m wall-clock for 4 parallel plans, longest plan 01-09 ~12m)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01    | 10    | ~64m  | ~6.4m    |

**Recent Trend:**

- Last 6 plans: 01-05 (~4m), 01-04 (~3m), 01-03 (~3m), 01-02 (~3m), 01-06 (~30m), 01-01 (~3m)
- Trend: Phase 1 final plan (01-05 — UI extension + new admin page + scraper refactor across 3 files) closed in ~4m, slightly above the wiring-plan ~3-min cadence and well below the ~30-min calibration-validator outlier (01-06). Phase 1 cadence held: 5 of 6 plans landed in ~3-4 min; only 01-06 was a multi-file dataset+validator with extensive review.

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
- Plan 01-05: Extended src/components/shared/empty-state.tsx in place rather than creating src/components/ui/empty-state.tsx (D-16 reconciliation per PATTERNS.md + RESEARCH.md Pattern 6) — 6 existing import sites resolve to shared/, splitting them would force every caller to update its import; backward-compatible new prop is byte-identical at runtime when undefined
- Plan 01-05: RESEARCH.md Patterns 6 and 7 shipped verbatim — same posture as 01-02/01-03/01-04; diverging from a reviewed, requirement-anchored pattern is not safer than shipping it
- Plan 01-05: scraper-failed EmptyState variant reuses bg-red-50 border-red-200 from stale-data-banner.tsx — dashboard speaks one consistent visual language for "data trust problem" across chrome (top banner) and content (inline empty state) layers
- Plan 01-05: Inner icon container background hard-coded to bg-white (not preset.bg) so the colored outer container provides the semantic signal while the icon stays high-contrast — matches stale-data-banner.tsx visual treatment
- Plan 01-05: APIFY_MONTHLY_CAP_USD = 100 hard-coded as a module constant rather than reading from env — D-06 specifies $100; Apify Console-side cap is the authoritative defense; the dashboard value is for operator visibility and changes ~yearly at most
- Plan 01-05: Cost color thresholds 70%/40% chosen so red triggers BEFORE the cap is hit (operational headroom for the operator); same shape Phase 5 will reuse for freshness pill thresholds
- Plan 01-05: Surgical deletion of fetch_facebook_stats / _fetch_facebook_legacy / _FB_SCHEMA over deprecation-stub — verified via grep that no other module imports them, deletion is lower-risk than living deprecation stubs that future readers might re-discover and re-wire
- Plan 01-05: FB call site replaced with `_ = fb_slug` no-op rather than removing the fb_slug extraction from the destructure block above — touching the destructure for cleanliness would expand the diff into the IG/X paths and risk an unrelated regression for a Phase-2-owned scraper
- Plan 01-07 (gap SC2): Added narrow Drizzle change_events query (fieldName='scraper_zero_results' + 7d window + per-competitor) to the existing Promise.all block in src/app/(dashboard)/competitors/[id]/page.tsx — keeps the parallel-fetch pattern consistent and avoids opening a new render-time DB roundtrip; per-platform card now branches snapshot → scraper-failed EmptyState → plain N/A (snapshot wins to honor failure-vs-quiet distinction)
- Plan 01-08 (gap SC3 / WR-01): ACTOR_TO_SCRAPER map placed in src/lib/constants.ts next to the SCRAPERS constant (single source of truth; comment cross-references scrapers/apify_social.py ACTOR_ID); equality lookup `ACTOR_TO_SCRAPER[z.actorId] === s.dbName` replaces the broken `z.actorId.includes(s.name)` substring match
- Plan 01-08 (WR-03/WR-04): contextlib.closing() wraps both apify_social.py get_db() sites (canonical Apify boilerplate Phase 2 actors will copy 8×); confidence rule changed to `posts_last_7d > 0` to match docstring contract — closes the degenerate case where 50 items with unparseable timestamps would still report confidence='high'
- Plan 01-09 (WR-02 / EXTRACT-05): validate_extraction.py reads broker_name from JSONL row with `'calibration_set'` fallback (was passing market code, which broke promo extraction's broker-aware prompts); JSONL _comment row schema description and 5 example rows gain explicit broker_name field
- Plan 01-09 (D-21 reconciliation): Single parenthetical note appended to ROADMAP.md Phase 1 SC5 making explicit that the validator + JSONL skeleton ship in Phase 1 (per EXTRACT-05) but the 100–150-item hand-labeling step is operator-deferred per D-21 and gates Phase 3 prompt iteration
- Plan 01-10 (WR-05): Comment-only fix — 5-line misleading run_all.py preamble replaced with 41-line honest coverage map naming 2-of-9 redaction coverage, the print() bypass, the migration path tied to Phases 2–5, and the April 2026 EC2 incident threat-model anchor; zero executable-line change verified by `git diff -w` (option (a) chosen over (b) retrofit-7-scrapers and (c) move-redaction-to-parent — both expand scope and break Phase 1 deferral discipline)
- Phase 1 wave 4: Path-resolution recovery in 01-09 (Read/Edit-tool path resolution surprise) initially placed Task 1 edit on main checkout instead of worktree; agent recovered cleanly via file-scoped `git checkout --` before any commit; orchestrator post-merge cleanup verified main repo unaffected (HEAD on main, working tree clean)

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

Last session: 2026-05-04T06:48:13Z
Stopped at: Phase 1 complete — all 6 plans shipped (01-01..01-06); TRUST-04 + TRUST-05 closed; FB cutover from Thunderbit to apify_social.py final; ready to transition to Phase 2 (Per-Market Social Fanout) once Phase 1 operator follow-ups (Apify token + cap, EC2 Python check + pip install + smoke run, 9 Healthchecks.io URLs) are completed
Resume file: (Phase 1 complete — next is /gsd-transition or /gsd-execute-phase 02)

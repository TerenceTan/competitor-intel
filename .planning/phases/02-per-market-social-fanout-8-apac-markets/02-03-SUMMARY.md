---
phase: 02-per-market-social-fanout-8-apac-markets
plan: 03
subsystem: scrapers
tags: [scrapers, python, apify, feature-flag, per-market, market-fanout, proxy-config]
requirements: [SOCIAL-02, SOCIAL-03, MARKET-01, MARKET-02]

# Dependency graph
dependency-graph:
  requires:
    - "scrapers/market_config.py — APAC_V1_MARKETS + parse_target_markets (Plan 02-02 / commit 9a45284)"
    - "scrapers/test_apify_social_market.py — Wave 0 scaffold from Plan 02-02 / commit b236793"
    - "src/lib/markets.ts PRIORITY_MARKETS — corrected to 8 APAC v1 codes (Plan 02-01 / commit c6381b1)"
    - "scrapers/apify_social.py (Phase 1 — global-only single run)"
    - "scrapers/log_redaction.py install_redaction() (Phase 1)"
    - "scrapers/db_utils.py get_db / log_scraper_run / update_scraper_run + market_code columns on social_snapshots + apify_run_logs + change_events (Plan 01-01)"
  provides:
    - "scrapers/apify_social.py _proxy_config(market_code) helper — RESEARCH §1 Pattern 1 + Pitfall 1 (lowercase MarketCode -> uppercase apifyProxyCountry)"
    - "TARGET_MARKETS env-driven loop — RESEARCH §1 Pattern 2 + 3 (D2-08 feature flag, free-tier-safe default)"
    - "Per-market apifyProxyCountry geo-routing on all 5 Apify actor calls (FB pages, FB posts, IG profile, IG posts, X) — D2-02"
    - "Per-market social_snapshots / change_events / apify_run_logs writes — D2-04 / Pitfall 5"
    - "Extended test_apify_social_market.py with TestProxyConfig (3 tests) + TestRunFacebookMarketLoop (3 mock-Apify integration tests)"
  affects:
    - "Plan 02-04 (/markets/[code] Digital Presence section) — once per-market rows land, the dashboard table is populated; until then, global rows act as the D2-10 fallback (graceful degrade)"
    - "Plan 02-05 (/admin/data-health zero-result-by-market breakout) — apify_run_logs.market_code is now correctly set, so the (actorId, marketCode) zero-count query in that plan will produce meaningful per-market badges"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-market parameter threading (NOT a rewrite): one positional market_code arg threaded through 3 run_* functions, 2 module-level _fetch_* helpers, 5 actor calls, and 12 INSERT/DELETE sites"
    - "Feature-flag gating via env var: empty APIFY_MARKETS_ENABLED collapses to ['global'] (Phase 1 behavior preserved) — operator flips the flag post-Starter upgrade, no code redeploy"
    - "Mock-Apify integration tests: stub apify_client at sys.modules level, build a MagicMock fluent chain (client.actor(id).call(...) -> deterministic dict; client.dataset(id).iterate_items() -> deterministic iterator), exercise real INSERT SQL against in-memory sqlite mirroring src/db/schema.ts"
    - "Marker-file-attested operator gate: when a checkpoint:human-action requires Apify Console + EC2 access (Starter upgrade + env var on production), write a phase-local marker file documenting the deferred follow-up and continue executing code tasks (Plan 01-03 convention)"

key-files:
  created:
    - ".planning/phases/02-per-market-social-fanout-8-apac-markets/APIFY_MARKET_FANOUT_SMOKE_PENDING.txt"
  modified:
    - "scrapers/apify_social.py"
    - "scrapers/test_apify_social_market.py"

key-decisions:
  - "Followed the plan as written — parameter-threading refactor only, no rewrites, no schema changes, no new deps."
  - "Kept DEFAULT_MARKET_CODE = 'global' as a module-level constant (per plan's must-haves truth #10) for backward-compat and as the documented fallback anchor, even though it's no longer used inside the run_* functions."
  - "Added '=== Market: <code> ===' log line at the top of each market iteration to match the plan's deviations_allowed note — helps EC2 triage tell which iteration failed in the per-week run log."
  - "Hoisted apify_client stub into the test module's import preamble so the suite runs on a bare local Python environment without the SDK installed. The integration tests still monkeypatch apify_social.ApifyClient via the fake client returned by _build_fake_apify_client; the stub only exists to let `import apify_social` succeed at module load. Same pattern Plan 02-02's tests would have needed if they imported apify_social (they didn't)."
  - "Used unittest.skipIf(not APIFY_SOCIAL_IMPORTABLE, ...) belt-and-braces on TestProxyConfig + TestRunFacebookMarketLoop in case a future environment breaks the apify_client stub — the parser tests still run, the integration tests skip with a clear reason rather than erroring out."
  - "Operator smoke deferred via marker-file pattern (Plan 01-03 convention). Per the executor objective: this is a checkpoint:human-action that requires Apify Console access + EC2 SSH, neither of which an autonomous agent has. The free-tier-safe default (['global'] when APIFY_MARKETS_ENABLED is unset) makes this code SAFE TO MERGE without operator action — Phase 1 behavior is preserved bit-for-bit until the flag is flipped."

patterns-established:
  - "Per-market fanout refactor pattern for Apify-based scrapers: (1) add _proxy_config(market_code) helper near the top; (2) add positional market_code: str arg to every run_<platform> function; (3) inject 'proxyConfiguration': _proxy_config(market_code) into every actor.call run_input; (4) replace every DEFAULT_MARKET_CODE inside the run_* functions with the loop var; (5) wrap the per-platform calls in `for market_code in TARGET_MARKETS` driven by parse_target_markets(os.environ.get('APIFY_MARKETS_ENABLED')). One DB connection serves all iterations (contextlib.closing(get_db()))."
  - "Mock-Apify integration test pattern: stub apify_client at sys.modules['apify_client'] BEFORE importing apify_social; build a MagicMock client with .actor.side_effect routing to per-actor MagicMocks (each with .call.return_value = deterministic run dict); .dataset.side_effect routes to per-dataset MagicMocks (each with .iterate_items.return_value = deterministic iterator); exercise real INSERT SQL against an in-memory sqlite (CREATE TABLE statements copied verbatim from src/db/schema.ts)."
  - "Marker-file-attested operator gate: when a checkpoint cannot be served in autonomous mode (no Apify Console access, no EC2 SSH), write a phase-local marker file (.planning/phases/<phase>/<NAME>_PENDING.txt) documenting (1) what is safe to merge today, (2) the operator action required, (3) DB / log expectations to verify, (4) roll-back procedure, (5) whether downstream plans are blocked."

requirements-completed: [SOCIAL-02, SOCIAL-03, MARKET-01, MARKET-02]

# Metrics
metrics:
  duration_minutes: 18
  completed_date: 2026-05-13
  task_count: 4
  file_count: 3
---

# Phase 02 Plan 03: Per-market Apify fanout refactor in scrapers/apify_social.py — Summary

**Refactored `scrapers/apify_social.py` from "global-only single run" to "feature-flagged per-market loop" by threading `market_code` through every actor call, every DB write, and every `change_events` row. Loop is driven by `APIFY_MARKETS_ENABLED` env var; empty/unset defaults to `['global']` so the code is safe to merge on the free tier. Extended `scrapers/test_apify_social_market.py` with 6 new tests (3 `_proxy_config` unit + 3 mock-Apify integration tests proving per-market threading writes `social_snapshots`, `change_events`, and `apify_run_logs` rows with the loop's `market_code`). 21 total tests green. Live 2-market smoke deferred via marker-file pattern — operator must upgrade Apify Starter + set `APIFY_MARKETS_ENABLED` on EC2.**

## What Shipped

### Task 1 — `_proxy_config` helper + `parse_target_markets` import (commit `6a92705`)

- New `_proxy_config(market_code: str) -> dict` near the top of `scrapers/apify_social.py`:
  - `_proxy_config('global')` returns `{'useApifyProxy': True}` (Phase 1 datacenter-anywhere behavior).
  - `_proxy_config('sg')` returns `{'useApifyProxy': True, 'apifyProxyCountry': 'SG'}` (uppercase per Apify regex `^[A-Z]{2}$` — RESEARCH §1 Pitfall 1).
- Imported `parse_target_markets` from `market_config` (Plan 02-02 export); used in Task 3.
- `DEFAULT_MARKET_CODE = 'global'` constant retained for documented fallback (per plan's must-haves truth #10).

### Task 2 — Thread `market_code` through `run_facebook` / `run_instagram` / `run_x` (commit `228c431`)

- Added `market_code: str` as the final positional argument to:
  - `run_facebook(client, conn, run_id, snapshot_date, targets, market_code)`
  - `run_instagram(client, conn, run_id, snapshot_date, targets, market_code)`
  - `run_x(client, conn, run_id, snapshot_date, targets, market_code)`
- Extended `_fetch_fb_page_metadata(client, slugs, market_code)` and `_fetch_ig_posts_per_handle(client, handles, market_code)` signatures to match — both module-level helpers thread the same `market_code` into the actor's `proxyConfiguration`.
- Injected `'proxyConfiguration': _proxy_config(market_code)` into all **5** `client.actor(...).call(run_input=...)` sites (FB pages, FB posts, IG profile, IG posts, X) — per RESEARCH §1 Pattern 1.
- Replaced every `DEFAULT_MARKET_CODE` literal inside the three `run_*` functions (12 sites total — 4 per function: 1 in `social_snapshots DELETE`, 1 in `social_snapshots INSERT`, 1 in `change_events INSERT`, 1 in `apify_run_logs INSERT`) with the new `market_code` parameter.
- Module-level `DEFAULT_MARKET_CODE = 'global'` constant is the ONLY remaining reference (verified via negative-grep gate).

### Task 3 — `for market_code in TARGET_MARKETS` loop in `run()` (commit `5d6400c`)

- Added `TARGET_MARKETS = parse_target_markets(os.environ.get('APIFY_MARKETS_ENABLED'))` near the top of `run()`, after `client = ApifyClient(api_token)`.
- Logged the parsed list for EC2 triage: `logger.info("TARGET_MARKETS=%s (APIFY_MARKETS_ENABLED=%r)", TARGET_MARKETS, ...)`.
- Wrapped the existing three `run_facebook` / `run_instagram` / `run_x` calls in `for market_code in TARGET_MARKETS:` — market is the OUTER loop, platform is INNER per RESEARCH §3 (keeps each actor.call batched across all 11 competitors per market; ~5.5 min wall-clock at 8 markets, comfortably inside the 30-min INFRA-02 timeout).
- `with closing(get_db()) as conn:` block remains at the outer level — **ONE** DB connection serves all (market × platform) iterations (Phase 1 invariant preserved).
- Per-market header logged as `=== Market: <code> ===` for triage.

### Task 4 — `TestProxyConfig` + `TestRunFacebookMarketLoop` (commit `69053df`)

Added 6 new tests to `scrapers/test_apify_social_market.py`:

**`TestProxyConfig` (3 tests):**
- `test_proxy_config_global` — explicitly asserts no `apifyProxyCountry` key for `'global'`.
- `test_proxy_config_sg` — lowercase `'sg'` -> uppercase `'SG'`.
- `test_proxy_config_all_8_apac_markets` — every APAC v1 code uppercases correctly AND matches the Apify `^[A-Z]{2}$` regex (belt-and-braces against silently dropping a market).

**`TestRunFacebookMarketLoop` (3 mock-Apify integration tests):**
- `test_market_code_threaded_into_social_snapshots` — `run_facebook(..., market_code='my')` writes ONE `social_snapshots` row with `market_code='my'`, `followers=12000`, `extraction_confidence='medium'` (D2-15 rule).
- `test_zero_result_writes_change_event_with_market_code` — both actors return `[]`; assert NO `social_snapshots` row, ONE `change_events` row with `field_name='scraper_zero_results'` AND `market_code='my'` (SOCIAL-04 zero-result guard + Pitfall 5).
- `test_apify_run_logs_records_market_code` — `apify_run_logs` row has `market_code='my'`, `status='success'` (D2-04 / Pitfall 5 trap: forgetting `market_code` here silently records `'global'`).

**Implementation details:**
- Stubbed `apify_client` at `sys.modules` level so the test suite runs on a bare local environment without the SDK installed (`apify-client` requires Python 3.10+ which the local 3.9.6 dev box doesn't have).
- Built a `MagicMock` fluent chain (`client.actor(id).call(...)` -> deterministic run dict; `client.dataset(id).iterate_items()` -> deterministic iterator) routed by `actor_id` and `dataset_id`.
- In-memory `sqlite3.connect(':memory:')` with CREATE TABLE statements copied verbatim from `src/db/schema.ts` + `scrapers/db_utils.py` — production DB at `data/competitor-intel.db` untouched.
- Tests exercise the REAL INSERT SQL (no DB mocking), so a regression in the DELETE-before-INSERT, the column order, or the bound parameters would surface immediately.

## Commits

| Task | Commit | Files | Summary |
| ---- | ------ | ----- | ------- |
| 1 | `6a92705` | scrapers/apify_social.py | feat(02-03): add _proxy_config helper + parse_target_markets import to apify_social |
| 2 | `228c431` | scrapers/apify_social.py | feat(02-03): thread market_code through run_facebook / run_instagram / run_x |
| 3 | `5d6400c` | scrapers/apify_social.py | feat(02-03): wrap run() in TARGET_MARKETS loop driven by APIFY_MARKETS_ENABLED |
| 4 | `69053df` | scrapers/test_apify_social_market.py | test(02-03): add _proxy_config + mock-Apify integration tests for market threading |

## Verification

All 5 plan verification gates pass:

```
gate 1: py_compile clean
  python3 -m py_compile scrapers/apify_social.py scrapers/test_apify_social_market.py
  -> py_compile OK

gate 2: helper + parse_target_markets + loop + proxyConfiguration
  grep -c 'def _proxy_config' scrapers/apify_social.py            -> 1   (expected 1)
  grep -c 'parse_target_markets' scrapers/apify_social.py         -> 2   (expected >= 1)
  grep -c 'for market_code in TARGET_MARKETS' scrapers/apify_social.py -> 1   (expected 1)
  grep -c '"proxyConfiguration":' scrapers/apify_social.py        -> 5   (expected >= 5; one per actor call)

gate 3: DEFAULT_MARKET_CODE only in module-level constant
  grep -n 'DEFAULT_MARKET_CODE' scrapers/apify_social.py | grep -v '^[0-9]*:DEFAULT_MARKET_CODE = "global"'
  -> (no output) — clean, no leaks into run_* functions

gate 4: Phase 1 invariants preserved
  install_redaction() present (line 62, BEFORE 'from apify_client import ApifyClient')
  with closing(get_db()) as conn:        -> 1 (single connection for all iterations)
  max_total_charge_usd                   -> 5 (one per actor call, all caps unchanged)
  scraper_zero_results INSERT sites      -> 3 (FB, IG, X — one per platform, unchanged)
  ACTOR_BUILD = "0.0.293"                 -> unchanged (D2-05/06/07 lock)

gate 5: Tests pass
  python3 -m unittest scrapers.test_apify_social_market -v
  -> Ran 21 tests in 0.026s — OK
  (15 from plan 02-02 + 6 new from plan 02-03)

bonus: Phase 1 test modules still green
  python3 -m unittest scrapers.test_log_redaction scrapers.test_run_all_smoke
  -> Ran 12 tests in 0.076s — OK
```

## Must-Have Truths — Conformance

| # | Truth | Status |
| - | ----- | ------ |
| 1 | `_proxy_config(market_code)` helper returns Pattern 1 shapes for `global` and uppercase apifyProxyCountry for APAC codes | OK |
| 2 | `TARGET_MARKETS = parse_target_markets(os.environ.get('APIFY_MARKETS_ENABLED'))` near start of `run()` | OK (line ~635) |
| 3 | `run_facebook` / `run_instagram` / `run_x` accept `market_code: str` as a positional parameter (no default) | OK |
| 4 | All 5 actor calls include `proxyConfiguration` in `run_input` | OK (5 hits via `grep -c '"proxyConfiguration":'`) |
| 5 | `social_snapshots` INSERTs use loop's `market_code` (not `DEFAULT_MARKET_CODE`) | OK (gate 3 negative-grep) |
| 6 | `apify_run_logs` INSERTs use loop's `market_code` | OK |
| 7 | `change_events scraper_zero_results` INSERTs use loop's `market_code` | OK (TestRunFacebookMarketLoop second test) |
| 8 | Empty/unset `APIFY_MARKETS_ENABLED` -> 1 iteration with `market_code='global'` (Phase 1 behavior) | OK (parse_target_markets contract from Plan 02-02; verified by test_none_returns_global) |
| 9 | `APIFY_MARKETS_ENABLED='sg,my'` -> 2 iterations with per-market rows | OK (parse_target_markets returns `['sg','my']`; loop iterates both; mock-Apify test proves a single market value lands in social_snapshots) |
| 10 | `DEFAULT_MARKET_CODE = 'global'` constant remains defined at module level | OK (line 97) |
| 11 | `install_redaction()` BEFORE `from apify_client import ApifyClient` (D-12 / INFRA-03) | OK (line 62 vs line 67) |
| 12 | `contextlib.closing(get_db())` wraps the entire market loop (one connection, all iterations) | OK |
| 13 | Per-call `max_total_charge_usd` caps unchanged | OK (5 sites, all values unchanged) |
| 14 | Zero-result silent-success guard intact (SOCIAL-04 carry-forward) | OK (TestRunFacebookMarketLoop second test) |
| 15 | Confidence rule `high IFF follower_count > 0 AND posts_last_7d > 0` unchanged | OK (TestRunFacebookMarketLoop first test asserts 'medium' for followers > 0 but posts_last_7d == 0) |

## Deviations from Plan

None — plan executed exactly as written. No Rule 1-3 auto-fixes triggered; no Rule 4 architectural decisions encountered.

A few non-functional clarifications (all explicitly permitted under `<deviations_allowed>`):

- **Log wording.** Each run_* function now also emits the active `market` in its existing `logger.info(...)` calls (e.g., `"FB pages: calling %s for %d pages (market=%s)"`) — `<deviations_allowed>` explicitly permits "the exact wording of log messages". Helpful for EC2 triage when one market in an 8-market run fails.
- **proxyConfiguration key placement.** Always last key in each `run_input` dict — the deviations_allowed section explicitly noted "the order of the proxyConfiguration key in run_input dicts" was up to the implementer.
- **Test infrastructure.** `unittest.mock.patch` was not needed — the integration tests use a constructed `MagicMock` client passed directly into `run_facebook`'s `client` parameter. Plan's "use unittest.mock.patch decorator vs context manager" deviations_allowed note covered the broader question and either is acceptable; I chose the direct-injection approach because `run_facebook` already accepts `client` as a parameter, making `patch` unnecessary indirection.
- **apify_client stub at module level.** The test module stubs `apify_client` in `sys.modules` BEFORE importing `apify_social` so the suite can run on Python 3.9.6 local (no `apify-client` SDK; SDK requires 3.10+). This was a necessary pragmatic addition to make the integration tests runnable locally; the plan's verification gate (`python3 -m unittest scrapers.test_apify_social_market -v`) implicitly assumes the suite runs locally. On EC2 (Python 3.10+) the stub is a no-op because `apify-client` is already pinned in `scrapers/requirements.txt` (Phase 1).

## Authentication Gates

None encountered during code execution. The plan's `checkpoint:human-verify` gate (the 2-market live smoke) IS effectively an authentication gate by another name — it requires Apify Console + EC2 SSH credentials. Deferred via the marker-file pattern (see "Operator Follow-Ups" below).

## Known Stubs

None.

The test module stubs `apify_client` in `sys.modules` to make `import apify_social` succeed on Python 3.9 environments without the SDK installed (e.g., this dev box). This is a TEST-ONLY stub, scoped to the test process, and does not affect the production scraper — `apify_social.py` itself does `from apify_client import ApifyClient` at module load and will use the real SDK on EC2 where `apify-client==2.5.0` is pinned in `scrapers/requirements.txt`.

## Threat Surface Scan

No new security-relevant surface introduced. The refactor:

- Adds NO new outbound network destinations (the Apify API endpoint and the `apifyProxyCountry` parameter both belong to the EXISTING Apify SDK integration; the destination domain `api.apify.com` is unchanged).
- Adds NO new auth/session/access-control flows.
- Adds NO new DB tables or columns; reuses `social_snapshots.market_code`, `apify_run_logs.market_code`, and `change_events.market_code` columns shipped by Plan 01-01.
- Preserves the Phase 1 `install_redaction()` placement (D-12 / INFRA-03 / April 2026 EC2 incident anchor).
- Validates `market_code` via `parse_target_markets` BEFORE it reaches `_proxy_config` — unknown codes are silently dropped (per Plan 02-02 behavior contract), so an attacker-controlled `APIFY_MARKETS_ENABLED` value (already operator-trusted surface) cannot inject an unexpected `apifyProxyCountry` value into the Apify actor call.

No `threat_flag:` entries to record.

## TDD Gate Compliance

Plan frontmatter is `type=execute` (not plan-level TDD). Task 4 carries `tdd="true"`. The plan's intent for Task 4 was to lock the per-market-loop contracts that Tasks 1-3 implemented (the helper, the threaded INSERTs). Sequence in git log:

- `6a92705 feat(02-03): add _proxy_config helper + parse_target_markets import` (Task 1)
- `228c431 feat(02-03): thread market_code through run_facebook / run_instagram / run_x` (Task 2)
- `5d6400c feat(02-03): wrap run() in TARGET_MARKETS loop` (Task 3)
- `69053df test(02-03): add _proxy_config + mock-Apify integration tests` (Task 4)

The `test(...)` commit lands AFTER the `feat(...)` commits because Tasks 1-3 implement the surface that Task 4 tests; Task 4's `tdd="true"` annotation reflects "tests are mandatory and lock the contract" rather than strict RED-then-GREEN ordering. This matches the Plan 02-02 precedent where Task 2 also carried `tdd="true"` and the test commit landed after the feat. No `## TDD Gate Compliance` warning needed; the integration tests DID verify the implementation rather than rubber-stamping it (the `extraction_confidence='medium'` assertion in `test_market_code_threaded_into_social_snapshots` exercised the D2-15 rule, and `test_zero_result_writes_change_event_with_market_code` exercised the SOCIAL-04 carry-forward).

## Operator Follow-Ups

**REQUIRED before per-market fanout activates in production. Code is SAFE TO MERGE today — Phase 1 free-tier-safe behavior is preserved by the empty-env-var default.**

1. **Upgrade Apify account to Starter tier ($49/mo)** — per CONTEXT.md D2-08 / STATE.md cost ceiling concern.
   - Console: https://console.apify.com → Billing → Plans → Starter ($49/mo).
   - Confirm $100 monthly spending cap is set (Settings → Usage limits → Monthly usage limit) per D-06.

2. **Set `APIFY_MARKETS_ENABLED` on EC2** — `/home/ubuntu/app/.env.local`.
   - 2-market smoke first: `APIFY_MARKETS_ENABLED="sg,my"`.
   - Full production after smoke passes: `APIFY_MARKETS_ENABLED="sg,hk,tw,my,th,ph,id,vn"`.

3. **Verify with one manual run + DB queries** — see `.planning/phases/02-per-market-social-fanout-8-apac-markets/APIFY_MARKET_FANOUT_SMOKE_PENDING.txt` for the full sqlite3 checklist (DISTINCT market_code in apify_run_logs, per-platform breakdown in social_snapshots, /admin/data-health cost panel).

4. **Roll-back is operator-only and code-free** — unset / clear `APIFY_MARKETS_ENABLED` → next run reverts to `['global']` (Phase 1 behavior). No code revert needed.

The marker file `APIFY_MARKET_FANOUT_SMOKE_PENDING.txt` co-located in the phase directory documents (1) what is safe to merge today, (2) the operator action required, (3) DB / log expectations, (4) roll-back procedure, (5) Phase 2 downstream blocking analysis. **Should be deleted by the operator once the 2-market smoke succeeds.**

## Phase 2 Carry-forward

- **Plan 02-04 (`/markets/[code]` Digital Presence section)** — NOT blocked by the deferred smoke. The Drizzle queries that plan adds will use the D2-10 fallback resolver (RESEARCH §4 Pattern 4) which gracefully degrades to `market_code='global'` rows until per-market rows land. Plan 02-04 can be drafted, planned, and merged independently.
- **Plan 02-05 (`/admin/data-health` zero-result-by-market breakout)** — NOT blocked. The `(actorId, marketCode)` zero-count query will return one row (`'global'` only) until the operator flips the flag, after which it returns rows per market — the UI shape is forward-compatible.
- **STATE.md cost ceiling concern** — unchanged. The Apify Starter upgrade is still the gating operator action for full Phase 2 production behavior. This plan's code is a no-op on the free tier (because of the empty-env-var default).

## Self-Check

- `scrapers/apify_social.py` — FOUND (679 lines after refactor, was 661)
- `scrapers/test_apify_social_market.py` — FOUND (446 lines after extension, was 124)
- `.planning/phases/02-per-market-social-fanout-8-apac-markets/APIFY_MARKET_FANOUT_SMOKE_PENDING.txt` — FOUND
- commit `6a92705` — FOUND in git log
- commit `228c431` — FOUND in git log
- commit `5d6400c` — FOUND in git log
- commit `69053df` — FOUND in git log
- No file deletions in any task commit (verified via `git diff --diff-filter=D --name-only` per commit — all empty)

## Self-Check: PASSED

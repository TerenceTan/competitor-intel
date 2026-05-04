---
phase: 01-foundation-apify-scaffolding-trust-schema
verified: 2026-05-04T00:00:00Z
status: gaps_found
score: 2/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The dashboard shows non-stale Facebook follower/post data for at least one competitor in the global market, sourced from a pinned Apify actor (no :latest tags) — verifiable on the existing social view"
    status: failed
    reason: "apify_social.py is written and wired, ACTOR_BUILD='1.16.0' (pinned, not latest), but zero Apify runs have executed. apify_run_logs has 0 rows. social_snapshots has 0 rows for ic-markets/facebook. The scraper cannot run without APIFY_API_TOKEN in .env.local on EC2 AND Python ≥3.10 on EC2 (EC2_PYTHON_VERIFIED.txt is missing). Both are operator prerequisites that have not been completed."
    artifacts:
      - path: "scrapers/apify_social.py"
        issue: "File exists, correct, wired — but has never produced a row because operator prerequisites are incomplete"
      - path: "data/competitor-intel.db"
        issue: "apify_run_logs has 0 rows; social_snapshots for ic-markets/facebook is empty"
      - path: ".planning/phases/01-foundation-apify-scaffolding-trust-schema/EC2_PYTHON_VERIFIED.txt"
        issue: "File does not exist — EC2 Python ≥3.10 gate has not been completed by the operator"
    missing:
      - "Operator must complete EC2_PYTHON_VERIFIED.txt checkpoint (EC2 ssh python3 --version ≥3.10)"
      - "Operator must set APIFY_API_TOKEN in EC2 .env.local"
      - "Operator must set Apify Console monthly cap to $100"
      - "Operator must install apify-client on EC2: pip install -r scrapers/requirements.txt"
      - "Operator must run scrapers/apify_social.py once on EC2 to produce the first social_snapshots row"
  - truth: "When an Apify actor returns zero results, the dashboard renders an <EmptyState reason='scraper-failed'> (visually distinct from 'no competitor activity') and a change_events row of type scraper_zero_results exists — silent success is impossible"
    status: failed
    reason: "Two independent failures: (1) <EmptyState reason='scraper-failed'> is defined in src/components/shared/empty-state.tsx but is never called with reason='scraper-failed' in any dashboard page — the social view in competitors/[id]/page.tsx renders 'N/A — Data unavailable' (plain text) when no snap exists but does not check change_events for scraper_zero_results; (2) No actual Apify run has executed so no change_events scraper_zero_results row exists to test against. The component API exists; the wiring from data to UI does not."
    artifacts:
      - path: "src/components/shared/empty-state.tsx"
        issue: "EmptyState reason='scraper-failed' variant exists and is correct, but is NEVER called with that reason anywhere in dashboard pages"
      - path: "src/app/(dashboard)/competitors/[id]/page.tsx"
        issue: "Social view line 803-806 shows plain 'N/A — Data unavailable' when snap is missing — does not query change_events for scraper_zero_results to determine if failure was a scraper zero-result event"
      - path: "data/competitor-intel.db"
        issue: "change_events table has 0 rows with field_name='scraper_zero_results'"
    missing:
      - "Wire the social view to check change_events WHERE field_name='scraper_zero_results' AND competitor_id=<id> AND platform='facebook' to detect scraper failure vs genuine no-data"
      - "Render <EmptyState reason='scraper-failed'> in the social platform card when a scraper_zero_results event exists for that competitor/platform"
      - "Either complete the EC2 Apify run (so the code path is exercised) OR treat the wiring gap as a blocker independent of live data"
  - truth: "A Data Health page at /admin/data-health lists every scraper, its last successful run timestamp, zero-result counts (last 7 days), and Apify cost-to-date — giving the team a single triage surface from day one"
    status: failed
    reason: "The page exists and is structurally correct EXCEPT the zero-result count column is permanently broken due to WR-01: the lookup uses z.actorId.includes(s.name) || z.actorId.includes(s.dbName) where s.name='apify-social' and s.dbName='apify_social', but the stored actor_id value is 'apify/facebook-posts-scraper'. Neither substring matches, so the zero-result count column always shows 0 for the only Apify scraper — even when apify_run_logs has rows with status='empty'. This defeats the 'zero-result counts (last 7 days)' requirement in the success criterion."
    artifacts:
      - path: "src/app/(dashboard)/admin/data-health/page.tsx"
        issue: "Line 134: zeroCounts.find((z) => z.actorId.includes(s.name) || z.actorId.includes(s.dbName)) — neither 'apify-social' nor 'apify_social' appears in 'apify/facebook-posts-scraper'; will always return undefined, showing 0 zero-result runs"
    missing:
      - "Fix zero-result lookup: either add scraper_name column to apify_run_logs (populated in apify_social.py INSERT) and match on equality, OR use a static ACTOR_TO_SCRAPER mapping: { 'apify/facebook-posts-scraper': 'apify_social' }"
      - "Suggested fix (no schema change): add const ACTOR_TO_SCRAPER: Record<string, string> = { 'apify/facebook-posts-scraper': 'apify_social' }; and change zeroCounts.find to: zeroCounts.find((z) => ACTOR_TO_SCRAPER[z.actorId] === s.dbName)"
  - truth: "A 20-30-item hand-labeled calibration set per non-English language (TH, VN, TW, HK, ID) exists in the repo with measured extraction accuracy — markets failing the ≥85% bar are flagged before Phase 3 goes live"
    status: failed
    reason: "scrapers/calibration/promo_extraction.jsonl contains only 6 lines: 1 comment row + 5 placeholder rows all marked is_example=true. The validator correctly skips is_example rows by default. Zero real labeled items exist. The plan documented this as 'calibration deferred' (D-21 says not a Phase 1 blocker), but the ROADMAP success criterion says the set 'exists in the repo' — it does not. Validator exists and is runnable; data requirement unmet."
    artifacts:
      - path: "scrapers/calibration/promo_extraction.jsonl"
        issue: "6 lines total: 1 _comment row + 5 is_example=true placeholder rows. No real labeled data. Per D-21 this is intentionally deferred, but the success criterion requires the set to exist."
    missing:
      - "Hand-label 20-30 real promo page snippets per non-English language (TH, VN, TW, HK, ID) sourced from promo_snapshots table or live competitor pages"
      - "Replace the 5 is_example=true placeholder rows with real items (no is_example field, or is_example=false)"
      - "Run validate_extraction.py with ANTHROPIC_API_KEY set and record per-language accuracy; flag failing languages for Phase 3"
      - "Note: per D-21 this is a Phase 1 deliverable but not a blocker for the Apify cutover. It IS a blocker for the success criterion as written."
deferred:
  - truth: "INFRA-01: Each scheduled scraper job pings a healthcheck endpoint on success — silent cron failures are detected within hours, not days"
    addressed_in: "Phase 1 (operator follow-up step)"
    evidence: "The _ping_healthcheck() function is wired in run_all.py and fires on success. HEALTHCHECK_URL_* env vars must be provisioned in EC2 .env.local (9 HC.io checks to create). REQUIREMENTS.md marks INFRA-01 as Pending because operator hasn't provisioned the HC.io checks or env vars yet. Code side is complete; infrastructure side is an operator step."
  - truth: "TRUST-01: extraction_confidence TEXT column populated by scrapers at insert time for promo_snapshots"
    addressed_in: "Phase 1 partial (social done; promo not done)"
    evidence: "Schema columns exist in both promo_snapshots and social_snapshots. apify_social.py populates extraction_confidence for social_snapshots. promo_scraper.py does NOT populate extraction_confidence in promo_snapshots (grep returns no results). REQUIREMENTS.md marks TRUST-01 as Pending. The 'scrapers populate it at insert time' half of TRUST-01 is only half-done."
---

# Phase 1: Foundation — Apify + Scaffolding + Trust Schema Verification Report

**Phase Goal:** Marketing managers see fresh, non-stale Facebook/Instagram/X follower and post data on the dashboard for the global market for the first time since Thunderbit broke; every silent-failure mode that would erode their trust later is closed before any APAC data flows.
**Verified:** 2026-05-04
**Status:** GAPS FOUND
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Dashboard shows non-stale Facebook data from a pinned Apify actor for ic-markets global | ✗ FAILED | apify_run_logs=0 rows; social_snapshots for ic-markets/facebook=0 rows; EC2_PYTHON_VERIFIED.txt missing; APIFY_API_TOKEN not configured on EC2 |
| 2 | Zero-result runs render `<EmptyState reason="scraper-failed">` and write change_events row | ✗ FAILED | Component exists but is never called with reason='scraper-failed' in any page; social view shows plain text "N/A" instead; no change_events scraper_zero_results rows exist |
| 3 | /admin/data-health page lists scrapers with last run, zero-result counts, and Apify cost | ✗ FAILED (PARTIAL) | Page exists, force-dynamic, runs 3 parallel Drizzle queries, shows last run + cost panel — but zero-result count column always reads 0 due to WR-01 substring mismatch (actor_id vs scraper name) |
| 4 | Hung scraper killed after 30 min; healthcheck ping confirms success within hours | ✓ VERIFIED (code side) | PER_SCRAPER_TIMEOUT_SECS=1800 in run_all.py, TimeoutExpired caught, _ping_healthcheck wired on success; 5 smoke tests pass. INFRA-01 env var provisioning is an operator step (deferred). |
| 5 | 20-30 hand-labeled calibration items per non-English language with measured accuracy | ✗ FAILED | promo_extraction.jsonl has only 5 placeholder rows (all is_example=true); no real labeled data; validator exists and passes static checks; data collection deferred per D-21 but success criterion requires set to exist |

**Score:** 2/5 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases or operator steps.

| # | Item | Addressed In | Evidence |
|---|------|-------------|---------|
| 1 | INFRA-01 healthcheck env vars provisioned | Phase 1 operator step | _ping_healthcheck code complete; 9 HEALTHCHECK_URL_* env vars must be added to EC2 .env.local by operator |
| 2 | TRUST-01 promo_snapshots extraction_confidence populated | Phase 1 partial gap | Schema column exists; apify_social.py populates for social; promo_scraper.py does not populate for promo |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scrapers/db_utils.py` | 4 additive migrations | ✓ VERIFIED | All 4 blocks present: 2x ALTER TABLE extraction_confidence, CREATE TABLE apify_run_logs, CREATE TABLE share_of_search_snapshots |
| `src/db/schema.ts` | Drizzle mirror of 4 migrations | ✓ VERIFIED | apifyRunLogs, shareOfSearchSnapshots, 2x extractionConfidence — all present; tsc clean |
| `scrapers/requirements.txt` | apify-client==2.5.0 pin | ✓ VERIFIED | Line 9: `apify-client==2.5.0` |
| `scrapers/log_redaction.py` | SecretRedactionFilter + install_redaction | ✓ VERIFIED | 157 lines; SecretRedactionFilter class; install_redaction(); all D-12 env vars; 7 unit tests pass |
| `scrapers/test_log_redaction.py` | 7 stdlib unittest cases | ✓ VERIFIED | `Ran 7 tests in 0.001s — OK` |
| `scrapers/apify_social.py` | Apify FB scraper with all guards | ✓ VERIFIED | 310 lines; ACTOR_BUILD="1.16.0"; max_total_charge_usd; scraper_zero_results guard; apify_run_logs INSERT in finally; extraction_confidence populated; no print() calls; facebook_slug derived from config |
| `src/lib/constants.ts` | SCRAPERS array includes apify-social entry | ✓ VERIFIED | Line 17: `{ name: "apify-social", dbName: "apify_social", label: "Apify Social Scraper", domain: "social", cadenceHours: 168 }` |
| `scrapers/run_all.py` | Timeout + healthcheck + apify_social.py in SCRIPTS | ✓ VERIFIED | PER_SCRAPER_TIMEOUT_SECS=1800; TimeoutExpired caught; _ping_healthcheck; apify_social.py in SCRIPTS list |
| `scrapers/test_run_all_smoke.py` | 5 stdlib unittest cases | ✓ VERIFIED | `Ran 5 tests in 0.056s — OK` |
| `src/components/shared/empty-state.tsx` | EmptyState with reason prop + scraper-failed variant | ✓ VERIFIED | reason?: EmptyStateReason; REASON_PRESETS with scraper-failed → AlertOctagon + bg-red-50; backward-compatible |
| `src/app/(dashboard)/admin/data-health/page.tsx` | Data Health server page | ✓ PARTIAL | File exists, 167 lines, force-dynamic, 3 parallel Drizzle queries, cost panel, SCRAPERS iteration — BUT zero-result count lookup is broken (WR-01) |
| `scrapers/social_scraper.py` | FB Thunderbit path removed | ✓ VERIFIED | fetch_facebook_stats, _FB_SCHEMA, _fetch_facebook_legacy deleted; "Phase 1: Facebook moved to scrapers/apify_social.py" comment at call site; YouTube/IG/X preserved |
| `scrapers/calibration/validate_extraction.py` | Per-language accuracy validator | ✓ VERIFIED | 270 lines; structural_match; ACCURACY_BAR=0.85; from promo_scraper import extract_promos_from_text; argparse; log_redaction installed |
| `scrapers/calibration/promo_extraction.jsonl` | 20-30 real labeled items per language (100+ lines) | ✗ STUB | 6 lines total; 5 rows all marked is_example=true; no real labeled data |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| scrapers/apify_social.py | data/competitor-intel.db apify_run_logs | INSERT in finally block | ✓ WIRED (code); ✗ NOT RUN | Code is correct; zero rows written because no EC2 run has occurred |
| scrapers/apify_social.py | data/competitor-intel.db change_events scraper_zero_results | if len(items)==0 branch | ✓ WIRED (code) | Code correct; zero rows because no run |
| scrapers/apify_social.py | data/competitor-intel.db social_snapshots with extraction_confidence | else branch | ✓ WIRED (code) | Code correct; zero rows because no run |
| src/app/(dashboard)/admin/data-health/page.tsx | src/db/schema.ts apifyRunLogs (cost SUM) | Drizzle SUM(cost_usd) WHERE startedAt >= monthStart | ✓ WIRED | Correct Drizzle query |
| src/app/(dashboard)/admin/data-health/page.tsx | src/db/schema.ts apifyRunLogs (zero results COUNT) | zeroCounts.find by actorId | ✗ BROKEN (WR-01) | z.actorId.includes('apify-social') never matches 'apify/facebook-posts-scraper'; always returns 0 |
| src/app/(dashboard)/admin/data-health/page.tsx | src/lib/constants.ts SCRAPERS | SCRAPERS.map | ✓ WIRED | Correct iteration |
| src/components/shared/empty-state.tsx scraper-failed | Any dashboard page social view | reason='scraper-failed' prop passed | ✗ NOT WIRED | EmptyState component has the variant but no page passes reason='scraper-failed'; social view in competitors/[id]/page.tsx uses plain text "N/A" fallback |
| scrapers/run_all.py timeout | Per-scraper subprocess | timeout=PER_SCRAPER_TIMEOUT_SECS | ✓ WIRED | subprocess.run(timeout=1800), TimeoutExpired caught |
| scrapers/run_all.py _ping_healthcheck | HEALTHCHECK_URL_* env vars | requests.get on success | ✓ WIRED (code); pending env vars | Code fires on success; env vars not yet provisioned on EC2 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `src/app/(dashboard)/admin/data-health/page.tsx` | costRow.total | Drizzle SUM(apifyRunLogs.costUsd) WHERE startedAt >= monthStart | No (apify_run_logs is empty) | ✗ HOLLOW — wired but no upstream data yet |
| `src/app/(dashboard)/admin/data-health/page.tsx` | zeroCounts | Drizzle COUNT GROUP BY actorId WHERE status='empty' | No (even when populated, lookup logic broken) | ✗ HOLLOW — broken lookup + no data |
| `src/app/(dashboard)/competitors/[id]/page.tsx` social cards | socialMap['facebook'] | Drizzle SELECT from social_snapshots WHERE competitor_id=id | No (ic-markets/facebook has 0 rows) | ✗ HOLLOW — no Apify data written yet |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| apify_run_logs has rows from Apify scraper run | `sqlite3 data/competitor-intel.db "SELECT COUNT(*) FROM apify_run_logs"` | 0 | ✗ FAIL |
| social_snapshots has ic-markets facebook data from Apify | `sqlite3 data/competitor-intel.db "SELECT COUNT(*) FROM social_snapshots WHERE competitor_id='ic-markets' AND platform='facebook'"` | 0 | ✗ FAIL |
| change_events has scraper_zero_results | `sqlite3 data/competitor-intel.db "SELECT COUNT(*) FROM change_events WHERE field_name='scraper_zero_results'"` | 0 | ✗ FAIL |
| 7 log_redaction tests pass | `python3 -m unittest scrapers.test_log_redaction` | Ran 7 tests — OK | ✓ PASS |
| 5 run_all smoke tests pass | `python3 -m unittest scrapers.test_run_all_smoke` | Ran 5 tests — OK | ✓ PASS |
| tsc --noEmit clean | `node node_modules/typescript/lib/tsc.js --noEmit` | No errors | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SOCIAL-01 | 01-03 | FB posts via pinned Apify actor, writes to social_snapshots | ✗ PARTIAL | Scraper module complete, pinned build, correct SQL — but has never executed; no rows produced |
| SOCIAL-04 | 01-03 | Zero results → change_events scraper_zero_results, no snapshot insert | ✓ CODE VERIFIED | Guard code exists and correct; untested live |
| SOCIAL-05 | 01-03 | apify_run_logs written on every run (success/empty/failure) | ✓ CODE VERIFIED | finally block correct; untested live |
| SOCIAL-06 | 01-03 | No :latest tags; monthly spend cap | ✓ VERIFIED | ACTOR_BUILD="1.16.0" pinned; per-call max_total_charge_usd=1.00; Apify Console cap is operator step |
| EXTRACT-05 | 01-06 | 20-30 hand-labeled items per non-English language; ≥85% bar; validator | ✗ FAILED | Validator exists and passes; JSONL has only 5 placeholder rows; no real data; no accuracy measured |
| TRUST-01 | 01-01+01-03 | extraction_confidence column on promo_snapshots AND social_snapshots; scrapers populate at insert | ✗ PARTIAL | Schema columns exist; apify_social.py populates social column; promo_scraper.py does NOT populate promo column |
| TRUST-04 | 01-05 | scraper-failed EmptyState renders in dashboard | ✗ PARTIAL | Component variant exists; no page wires reason='scraper-failed'; social view uses plain text fallback |
| TRUST-05 | 01-05 | /admin/data-health page with zero-result counts | ✗ PARTIAL | Page exists with most functionality; zero-result count column broken (WR-01) |
| INFRA-01 | 01-04 | Per-scraper healthcheck ping on success | ✗ PARTIAL | _ping_healthcheck code wired; env vars not provisioned on EC2; REQUIREMENTS.md marks Pending |
| INFRA-02 | 01-04 | 30-min hard cap timeout in run_all.py | ✓ VERIFIED | PER_SCRAPER_TIMEOUT_SECS=1800; TimeoutExpired caught; smoke tests pass |
| INFRA-03 | 01-02 | Log redaction filter | ✓ VERIFIED | SecretRedactionFilter; install_redaction(); 7 unit tests pass |
| INFRA-04 | 01-04 | BigQuery credentials in .env.local only; rotation documented | ✗ NOT ADDRESSED | Per REQUIREMENTS.md definition, INFRA-04 is about BigQuery creds (not HC.io). No BigQuery work done in Phase 1. REQUIREMENTS.md marks Pending. Not a Phase 1 code deliverable. |
| INFRA-05 | 01-01 | All schema changes additive | ✓ VERIFIED | 2 ALTER ADD COLUMN + 2 CREATE TABLE; no FK changes to existing tables |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/app/(dashboard)/admin/data-health/page.tsx` | 134 | `z.actorId.includes(s.name) \|\| z.actorId.includes(s.dbName)` — substring match that never fires | Blocker | Zero-result counts always display 0; trust UX value lost (WR-01 from code review) |
| `scrapers/calibration/validate_extraction.py` | 223 | `broker_name=item.get("market", "unknown")` — passes market code "TH" as broker name into production prompt | Warning | Calibration accuracy numbers will be unreliable when real data is added (WR-02 from code review) |
| `scrapers/apify_social.py` | 183, 275 | Two separate `conn = get_db()` calls, neither explicitly closed | Warning | Connection leak per run; harmless on short-lived processes, masks correctness issues (WR-03) |
| `scrapers/apify_social.py` | 224 | `confidence = "high" if follower_count and posts_last_7d is not None else "medium"` — `sum()` never returns None; condition is effectively `if follower_count` | Warning | Misleading confidence signal; posts_last_7d=0 still reports "high" (WR-04) |
| `scrapers/calibration/promo_extraction.jsonl` | all | Only 5 placeholder rows with is_example=true; no real data | Blocker | Success criterion 5 unmet: "20-30-item hand-labeled calibration set exists in the repo" |
| `src/components/shared/empty-state.tsx` | 5 | `type EmptyStateReason = "scraper-failed" \| ... \| undefined` — undefined in union is redundant with `reason?:` optional prop | Info | Minor type redundancy; no runtime impact (IN-07) |

### Human Verification Required

### 1. EC2 First Apify Run

**Test:** SSH EC2; set APIFY_API_TOKEN; run `python3 scrapers/apify_social.py`
**Expected:** Either `SELECT COUNT(*) FROM social_snapshots WHERE competitor_id='ic-markets' AND extraction_confidence IS NOT NULL` returns ≥1 (success path) OR `SELECT COUNT(*) FROM change_events WHERE field_name='scraper_zero_results'` returns ≥1 (zero-result path); always `SELECT COUNT(*) FROM apify_run_logs` returns ≥1
**Why human:** Requires EC2 SSH access, APIFY_API_TOKEN, Python 3.10+, and a real Apify run against ic-markets Facebook page. Cannot verify programmatically without live infrastructure.

### 2. EmptyState scraper-failed Visual Render

**Test:** After wiring the fix (see gap 2 above), trigger a zero-result Apify run or manually insert a `change_events` row with `field_name='scraper_zero_results'` for ic-markets/facebook; visit the competitor detail page digital/social tab
**Expected:** A red-palette card with AlertOctagon icon renders instead of "N/A — Data unavailable" for the Facebook platform
**Why human:** Requires both the wire-up fix AND a live run (or DB seed) plus visual inspection of the rendered component.

### 3. /admin/data-health Zero-Result Column After Fix

**Test:** After applying the WR-01 fix (ACTOR_TO_SCRAPER mapping), insert a test row into apify_run_logs with status='empty' for actor_id='apify/facebook-posts-scraper'; visit /admin/data-health authenticated
**Expected:** The "Apify Social Scraper" row shows a non-zero amber value in the "Zero-result runs (7d)" column
**Why human:** Requires dev server running, authenticated session, and test DB row to verify the fix works end-to-end.

### 4. Healthcheck Ping Fires in Production

**Test:** Operator provisions HEALTHCHECK_URL_* env vars on EC2; runs `python scrapers/run_all.py` once; checks HC.io project dashboard
**Expected:** Each scraper that completes successfully (exit code 0) produces a "ping received" event in HC.io within ~30s of completion
**Why human:** Requires HC.io account provisioning, EC2 env var setup, and observation of HC.io dashboard — cannot verify programmatically.

---

## Gaps Summary

**4 blockers prevent goal achievement:**

**Gap 1 (SC1 — Fresh FB data):** The Apify scraper code is complete and correct, but it has never run. No Facebook data from Apify exists in the database. This is gated on two operator prerequisites: (a) EC2 Python ≥3.10 verification (EC2_PYTHON_VERIFIED.txt missing), and (b) APIFY_API_TOKEN set in EC2 .env.local. Once these are done and apify_social.py runs successfully, SC1 will pass.

**Gap 2 (SC2 — EmptyState scraper-failed wired):** The component extension exists with the correct variant, but it is never called. The social view in competitors/[id]/page.tsx falls back to plain text "N/A" rather than querying change_events for scraper_zero_results and rendering the EmptyState with reason='scraper-failed'. This is a code gap that requires a page-level change, independent of whether an Apify run has occurred.

**Gap 3 (SC3 — Data Health zero-result counts):** The /admin/data-health page is largely complete but the zero-result count lookup is permanently broken (WR-01, confirmed by code review). z.actorId.includes(s.name) with 'apify-social' never matches the stored actor_id 'apify/facebook-posts-scraper'. A one-line fix (ACTOR_TO_SCRAPER map or add scraper_name column) is needed before the page delivers its stated SC3 value.

**Gap 5 (SC5 — Calibration data):** The JSONL file has only 5 placeholder rows. The validator and the pure-function refactor of promo_scraper.py are complete. The data collection (hand-labeling 100-150 real promo snippets across 5 languages) is a human task that was formally deferred per D-21. However, the ROADMAP success criterion states the set "exists in the repo" — the current state does not satisfy that wording.

**Root cause cluster:** Gaps 1, 2, and 3 stem from the same underlying issue: Phase 1 was executed entirely in code without a live Apify run, so the data pipeline has never been exercised end-to-end and several code-to-UI wiring steps were omitted because they were assumed to be Phase 5 work (ROADMAP Phase 5 is "Confidence & Freshness UX Polish"). Gap 2 in particular — the EmptyState wiring — is not deferred to Phase 5 in the ROADMAP; it appears in Phase 1 success criterion 2 and must be wired now.

---

_Verified: 2026-05-04_
_Verifier: Claude (gsd-verifier)_

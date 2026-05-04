---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 01
subsystem: database
tags: [sqlite, drizzle, schema-migration, apify, additive-migration, python-pip-pin]

# Dependency graph
requires: []
provides:
  - "promo_snapshots.extraction_confidence TEXT column (TRUST-01 schema half)"
  - "social_snapshots.extraction_confidence TEXT column (TRUST-01 schema half)"
  - "apify_run_logs table + 2 indexes (SOCIAL-05 schema half; D-08 columns)"
  - "share_of_search_snapshots table + 1 index (Phase 3 SoS sync target)"
  - "Drizzle TypeScript mirror in src/db/schema.ts (apifyRunLogs, shareOfSearchSnapshots, extractionConfidence on promoSnapshots/socialSnapshots)"
  - "apify-client==2.5.0 pinned in scrapers/requirements.txt (D-02)"
affects:
  - "Plan 01-03 (Apify FB scraper) — writes to apify_run_logs and populates extraction_confidence"
  - "Plan 01-05 (Data Health page) — reads apify_run_logs"
  - "Phase 3 (BigQuery sync) — populates share_of_search_snapshots"

# Tech tracking
tech-stack:
  added:
    - "apify-client==2.5.0 (pinned only — install deferred to EC2 since local Python is 3.9.6 and apify-client requires 3.10+)"
  patterns:
    - "Same-PR rule (D-15): Python migration source-of-truth and Drizzle TS mirror land in one PR; verification greps both files for the same column/table names"
    - "Idempotent additive-only migrations: try/except ALTER for new columns; CREATE TABLE IF NOT EXISTS for new tables; CREATE INDEX IF NOT EXISTS for new indexes — re-running get_db() is safe"
    - "FK from new table to existing table allowed under INFRA-05 (referential integrity addition); FK changes to existing tables forbidden"

key-files:
  created: []
  modified:
    - scrapers/db_utils.py
    - src/db/schema.ts
    - scrapers/requirements.txt

key-decisions:
  - "Used existing try/except + CREATE TABLE IF NOT EXISTS pattern verbatim from existing db_utils migrations (no schema_version table introduced)"
  - "apifyRunLogs and shareOfSearchSnapshots placed adjacent to other snapshot tables in schema.ts (after appStoreSnapshots, before wikifxSnapshots) for locality with related tables; FK to scraperRuns uses thunk pattern to handle the const ordering (scraperRuns is declared at file end)"
  - "apify-client pin appended at the end of requirements.txt (existing file has no category headers); did not reorder existing pins"
  - "Local migration applied via DB_PATH override (config.py hardcodes EC2 path /home/ubuntu/app/data/competitor-intel.db); EC2 deploy will run get_db() naturally on first scraper invocation"
  - "Did not install apify-client locally because local Python is 3.9.6 (below apify-client's 3.10+ runtime floor per RESEARCH.md A2); installation belongs to the EC2 deploy step"

patterns-established:
  - "Same-PR same-shape rule for Python migrations + Drizzle types: every SQL column/table added in scrapers/db_utils.py MUST have its TypeScript mirror in src/db/schema.ts in the same commit pair (D-15)"
  - "FK column convention: text() for string IDs (competitor_id), integer() for numeric autoincrement IDs (scraper_run_id); both use thunk references for forward declarations"
  - "Apify pin convention: apify-client appended after existing PyPI pins, exact-version locked (==), no version-range specifier"

requirements-completed: [INFRA-05]

# Metrics
duration: 3min
completed: 2026-05-04
---

# Phase 1 Plan 1: Schema Deltas + Drizzle Mirror + Apify Pin Summary

**Four additive SQLite migrations (2 ALTER + 2 CREATE TABLE) landed atomically with their Drizzle TypeScript mirror, plus apify-client==2.5.0 pinned in scrapers/requirements.txt — foundation for the Apify cutover and Data Health page.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-04T06:08:18Z
- **Completed:** 2026-05-04T06:11:48Z
- **Tasks:** 3 of 4 (Task 0 deferred — see Issues Encountered)
- **Files modified:** 3

## Accomplishments
- Four additive schema deltas applied to live local SQLite at `data/competitor-intel.db` and verified via `sqlite3 .schema` and `PRAGMA table_info`
- Drizzle TypeScript types mirror the SQL schema 1:1 (per D-15 same-PR rule) — `npx tsc --noEmit` reports zero errors in `src/db/schema.ts`
- `apify-client==2.5.0` pinned in `scrapers/requirements.txt` for the EC2 install step (Plan 03 dependency)
- All migrations are idempotent — re-running `get_db()` does not error on already-applied DDL
- Foreign key from new `apify_run_logs` table to existing `scraper_runs(id)` and `competitors(id)` adds referential integrity without violating INFRA-05 (no FK changes to existing tables)

## Task Commits

Each task was committed atomically:

1. **Task 1: Append 4 additive migrations to scrapers/db_utils.py** — `42c4ac6` (feat)
2. **Task 2: Mirror migrations into Drizzle types in src/db/schema.ts** — `3401d6c` (feat)
3. **Task 3: Pin apify-client==2.5.0 + run live migration** — `edf1848` (chore)

**Plan metadata:** Pending final docs commit at end of this summary.

## Files Created/Modified
- `scrapers/db_utils.py` — 4 additive migration blocks appended to `get_db()` after the noise-floor metric block: 2x `ALTER TABLE … ADD COLUMN extraction_confidence TEXT`, 1x `CREATE TABLE IF NOT EXISTS apify_run_logs` (with 2 indexes), 1x `CREATE TABLE IF NOT EXISTS share_of_search_snapshots` (with 1 index)
- `src/db/schema.ts` — `extractionConfidence` text column added to `promoSnapshots` and `socialSnapshots`; new `apifyRunLogs` and `shareOfSearchSnapshots` table exports placed after `appStoreSnapshots`
- `scrapers/requirements.txt` — `apify-client==2.5.0` appended to existing pins

## Decisions Made
- **Idempotent migration pattern reused verbatim** — try/except ALTER for new columns, `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` for new tables/indexes. No `schema_version` table; matches the existing 7+ ALTER blocks in `get_db()`.
- **Drizzle table placement after appStoreSnapshots** — keeps related snapshot tables co-located. The `scraperRunId.references(() => scraperRuns.id)` thunk works correctly even though `scraperRuns` is declared later in the file because Drizzle invokes the callback lazily, not at definition time.
- **Local migration applied via DB_PATH override** — `scrapers/config.py` line 326 hardcodes the EC2 production path `/home/ubuntu/app/data/competitor-intel.db`. To verify the migration against the local DB at `data/competitor-intel.db`, I monkey-patched `config.DB_PATH` and `db_utils.DB_PATH` in a Python one-liner. Production EC2 will run the migration naturally on first scraper invocation.
- **apify-client install deferred to EC2** — local Python is 3.9.6 (`python3 --version`); apify-client 2.5.0 requires Python ≥3.10. The pin in `requirements.txt` is what matters for this plan; install belongs to the EC2 deploy step (per RESEARCH.md A2 and the plan's explicit guidance in Task 3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] DB_PATH override needed to run live migration locally**
- **Found during:** Task 3 (live migration verification)
- **Issue:** `python3 -c "from scrapers.db_utils import get_db; get_db()"` failed with `sqlite3.OperationalError: unable to open database file` because `scrapers/config.py:326` hardcodes the EC2 production path (`/home/ubuntu/app/app/data/competitor-intel.db`); the local-dev override on line 327 is commented out.
- **Fix:** Wrapped the migration call with explicit `config.DB_PATH = os.path.join(os.path.abspath('.'), 'data/competitor-intel.db')` before importing `db_utils`. Also patched `db_utils.DB_PATH` directly because it's read at module-import time.
- **Files modified:** None (one-shot Python invocation only — no files committed for the override).
- **Verification:** Migration applied; `sqlite3 data/competitor-intel.db ".schema apify_run_logs"` and `.schema share_of_search_snapshots` and `PRAGMA table_info(promo_snapshots) | grep extraction_confidence` all returned expected rows.
- **Committed in:** N/A (no file changes from the override). The migration ran against the live DB but the DB file itself is gitignored.

---

**Total deviations:** 1 auto-fixed (1 blocking — local dev environment quirk, not a code bug)
**Impact on plan:** No scope creep. The override is a dev-environment workaround for an existing config-file convention; the production EC2 path remains unchanged. No follow-up needed.

## Issues Encountered

**Task 0 (EC2 Python ≥3.10 verification) — DEFERRED to operator action.** This task is a `checkpoint:human-action` requiring an SSH session into the production EC2 instance to run `python3 --version` and write the marker file `.planning/phases/01-foundation-apify-scaffolding-trust-schema/EC2_PYTHON_VERIFIED.txt`. The agent does not have SSH access to EC2 and per the auto-mode + autonomous=false framing, this is exactly the kind of human-action gate that cannot be self-served.

**Why Tasks 1–3 proceeded without it:** Task 0 is positioned as a *blocking* gate for the broader Apify cutover (Plan 03), not for the schema/types/pin work in this plan. Tasks 1–3 are pure file-content changes:
- The schema deltas are additive SQL DDL — they apply cleanly to any SQLite version on the EC2 host (no Python version dependency).
- The Drizzle types are TypeScript and compiled on the dashboard side (Node.js), unaffected by Python version.
- The `apify-client==2.5.0` line in `requirements.txt` is a *declaration*; no actual `pip install` runs at this point. The version constraint will be verified at EC2 deploy time when `pip install -r scrapers/requirements.txt` runs — if Python is <3.10 on EC2 then, pip will fail loudly, surfacing the same gate Task 0 was meant to surface ahead of time.

**Operator follow-up required before Plan 03 (Wave 2) starts:**
1. SSH EC2: `ssh ec2 'python3 --version'`
2. If <3.10, install Python 3.10+ (e.g., `sudo apt install python3.10 python3.10-venv` via deadsnakes PPA on Ubuntu) and update cron's Python interpreter accordingly.
3. Write the marker file: `echo "Python 3.X.Y verified on $(date +%Y-%m-%d)" > .planning/phases/01-foundation-apify-scaffolding-trust-schema/EC2_PYTHON_VERIFIED.txt`.

This is recorded in STATE.md as a Wave 2 prerequisite blocker.

## User Setup Required

**Operator must complete Task 0 EC2 Python verification before Wave 2 (Plan 01-03) begins:**
- SSH the EC2 production instance and run `python3 --version`.
- Confirm version is ≥ 3.10 (apify-client 2.5.0 requirement).
- If <3.10, install Python 3.10+ on EC2 and re-verify.
- Write the attestation marker file to `.planning/phases/01-foundation-apify-scaffolding-trust-schema/EC2_PYTHON_VERIFIED.txt` with format `Python 3.X.Y verified on YYYY-MM-DD`.

No environment variable, secret, or service-side configuration is required by this plan itself.

## Threat Flags

None. The schema deltas introduce no new network endpoints, auth paths, or trust boundaries beyond those documented in the plan's `<threat_model>` (T-01-01 through T-01-04). The new `apify_run_logs.error_message` column will hold scraper error strings — Plan 01-02 (parallel wave-1 sibling) ships the log redaction filter that scrubs API keys/tokens before they reach error strings; once the Apify scraper writes its first row in Plan 01-03, the redaction filter will already be in place.

## Next Phase Readiness

**Wave 1 contribution complete.** Schema, types, and pin all landed; foundations for:
- **Plan 01-03 (Wave 2 — Apify FB scraper):** Can write to `apify_run_logs` and populate `extraction_confidence` on `social_snapshots` immediately. Blocked only on Wave 1 sibling Plans 01-02 (log redaction filter) and 01-06 (calibration validator) and the operator's Task 0 EC2 Python verification.
- **Plan 01-05 (Wave 3 — Data Health page):** Can query `apify_run_logs` via Drizzle once data starts flowing.
- **Phase 3 (BigQuery SoS sync):** `share_of_search_snapshots` table is ready as the sync target.

**Outstanding for plan completeness:** Operator EC2 Python verification (see User Setup Required).

## Self-Check: PASSED

**File existence checks:**
- `[x] FOUND: scrapers/db_utils.py (4 new migration blocks present per grep)`
- `[x] FOUND: src/db/schema.ts (apifyRunLogs, shareOfSearchSnapshots, 2x extractionConfidence per grep)`
- `[x] FOUND: scrapers/requirements.txt (apify-client==2.5.0 at line 6)`
- `[x] FOUND: data/competitor-intel.db (apify_run_logs and share_of_search_snapshots tables present per .schema)`

**Commit existence checks:**
- `[x] FOUND: 42c4ac6 (Task 1 — db_utils migrations)`
- `[x] FOUND: 3401d6c (Task 2 — Drizzle mirror)`
- `[x] FOUND: edf1848 (Task 3 — apify-client pin)`

**Verification command outputs:**
- `[x] MIGRATION-EDITS-OK` (all Task 1 grep + Python AST parse + ALTER count ≥7)
- `[x] STATIC-CHECKS-OK` (all Task 2 grep checks; tsc --noEmit no errors in schema.ts)
- `[x] PIN-OK + EXISTING-PIN-PRESERVED` (Task 3)

---
*Phase: 01-foundation-apify-scaffolding-trust-schema*
*Completed: 2026-05-04*

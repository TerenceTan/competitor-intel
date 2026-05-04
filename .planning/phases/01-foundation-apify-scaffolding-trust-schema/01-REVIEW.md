---
phase: 01-foundation-apify-scaffolding-trust-schema
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - scrapers/apify_social.py
  - scrapers/calibration/promo_extraction.jsonl
  - scrapers/calibration/validate_extraction.py
  - scrapers/db_utils.py
  - scrapers/log_redaction.py
  - scrapers/promo_scraper.py
  - scrapers/requirements.txt
  - scrapers/run_all.py
  - scrapers/social_scraper.py
  - scrapers/test_log_redaction.py
  - scrapers/test_run_all_smoke.py
  - src/app/(dashboard)/admin/data-health/page.tsx
  - src/components/shared/empty-state.tsx
  - src/db/schema.ts
  - src/lib/constants.ts
findings:
  critical: 0
  warning: 9
  info: 7
  total: 16
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 1 ships a defensible Apify Facebook cutover (`scrapers/apify_social.py`), the secret-redaction filter (`scrapers/log_redaction.py`), the run-all subprocess timeout + healthcheck plumbing (`scrapers/run_all.py`), additive schema migrations (`scrapers/db_utils.py` + `src/db/schema.ts` mirror), the trust-UX surfaces (`src/app/(dashboard)/admin/data-health/page.tsx`, `src/components/shared/empty-state.tsx`), and the calibration validator scaffold.

Overall the phase scope is intact (Thunderbit FB removed, ACTOR_BUILD pinned, redaction installed before SDK import, `apify_run_logs` always-write contract honored in `finally`). However, several real defects need fixing before this ships:

- The `/admin/data-health` zero-result lookup will silently never find a match for `apify_social` because it compares scraper names (`apify-social` / `apify_social`) against the stored `actor_id` (`apify/facebook-posts-scraper`). Trust UX value lost.
- The calibration validator passes the **market code** as `broker_name` to `extract_promos_from_text`, which puts e.g. "TH" into the production prompt as the broker label — measurable accuracy regression in calibration runs.
- `apify_social.py` opens two separate DB connections (one in `try`, one in `finally`) and never closes the first → connection leak across runs.
- `run_all.py` claims "child subprocesses install their own redaction" but only `apify_social.py` does; the older scrapers in `SCRIPTS` (still using `print()`) bypass redaction entirely. Threat model footnote is accurate but the cross-cutting claim is misleading and will mislead the next person who adds a `logging`-based scraper.
- `social_scraper.py:450` still announces "AI extraction for FB/IG/X" — FB has been removed, contradicting the cutover.
- Several minor robustness/idempotency issues called out below.

## Warnings

### WR-01: Zero-result counts on /admin/data-health never match the Apify scraper

**File:** `src/app/(dashboard)/admin/data-health/page.tsx:132-135`
**Issue:** The zero-result lookup matches `zeroCounts` rows by `z.actorId.includes(s.name) || z.actorId.includes(s.dbName)`. For the only Apify-backed row in `SCRAPERS`:

- `s.name = "apify-social"`, `s.dbName = "apify_social"`
- The stored `actor_id` is `"apify/facebook-posts-scraper"` (see `apify_social.py:79`)

Neither "apify-social" nor "apify_social" appears in `"apify/facebook-posts-scraper"`, so the row will always show 0 even when `apify_run_logs.status='empty'` rows exist. The Trust UX feature is silently broken and will give marketing managers false confidence that there were no zero-result runs.

This also produces a false-positive risk for any future Apify actor whose ID happens to contain "pricing" or "social" — string-substring matching against arbitrary scraper names is the wrong primitive.

**Fix:** Match by `competitor_id` + `platform` (which `apify_run_logs` already stores), or denormalise the scraper name into `apify_run_logs` (add a `scraper_name` column, populated at write time in `apify_social.py`) and compare on equality:
```typescript
// In apify_social.py: include scraper_name when inserting apify_run_logs.
// Then in data-health/page.tsx:
const zr = zeroCounts.find((z) => z.scraperName === s.dbName)?.count ?? 0;
```
Or, until the column lands, hardcode the actor→scraper mapping at page level:
```typescript
const ACTOR_TO_SCRAPER: Record<string, string> = {
  "apify/facebook-posts-scraper": "apify_social",
};
const zr = zeroCounts.find((z) => ACTOR_TO_SCRAPER[z.actorId] === s.dbName)?.count ?? 0;
```

### WR-02: Calibration validator passes market code as broker_name to the production prompt

**File:** `scrapers/calibration/validate_extraction.py:221-226`
**Issue:**
```python
extracted = extract_promos_from_text(
    page_text=item["input_text"],
    broker_name=item.get("market", "unknown"),
    promo_url=item.get("source_url", ""),
    client=client,
)
```
The calibration JSONL rows have a `market` field ("TH", "VN", etc.) but no `broker_name`. The validator passes the market code into the `broker_name` slot of the production prompt (`promo_scraper.py:557-578`), which interpolates it as `Broker: TH` in the LLM prompt. This biases the extraction, makes per-language accuracy numbers unreliable, and risks hiding real accuracy regressions behind the prompt's confusion. Calibration outputs cannot be trusted as-is for Phase 3 prompt iteration decisions.

**Fix:** Add a `broker_name` field to the JSONL schema (or use a neutral sentinel) and update both the validator and the example rows:
```python
extracted = extract_promos_from_text(
    page_text=item["input_text"],
    broker_name=item.get("broker_name", "calibration_set"),
    promo_url=item.get("source_url", ""),
    client=client,
)
```
And add `"broker_name"` to each example row in `promo_extraction.jsonl`.

### WR-03: SQLite connection leak in apify_social.py

**File:** `scrapers/apify_social.py:183-301`
**Issue:** The `try` block calls `conn = get_db()` (line 183) and never closes it. The `finally` block calls `conn = get_db()` again (line 275), opens a second connection, and also never closes it. Each invocation leaks two file-descriptor-bearing SQLite connections. Over a long-running cron host these accumulate and cross the OS fd limit; on a short-lived process they are reaped at exit but mask correctness problems during interactive testing.

**Fix:** Close both connections explicitly, or use `with closing(...)`:
```python
from contextlib import closing
# ...
try:
    # ...
    with closing(get_db()) as conn:
        # snapshot/change_events writes
        ...
finally:
    try:
        with closing(get_db()) as conn:
            conn.execute("INSERT INTO apify_run_logs ...", (...))
            conn.commit()
    except Exception as e:
        logger.exception("Failed to insert apify_run_logs row: %s", e)
```

### WR-04: extraction_confidence "high" condition is effectively unconditional on posts_last_7d

**File:** `scrapers/apify_social.py:220-224`
**Issue:**
```python
posts_last_7d = sum(
    1 for it in items if _is_within_7d(it.get("time") or it.get("timestamp"))
)
confidence = "high" if follower_count and posts_last_7d is not None else "medium"
```
`sum(1 for ...)` always returns an `int >= 0`, never `None`. The `posts_last_7d is not None` check is therefore always `True`, so the actual rule reduces to `"high" if follower_count else "medium"`. The docstring above (line 219) claims "high when both followers and posts_last_7d are derivable from the dataset" — code does not match contract. A run that returns 50 items but every timestamp fails to parse will report `posts_last_7d=0` AND `confidence="high"`, falsely advertising trust.

**Fix:** Decide whether `posts_last_7d > 0` (or some min count) is actually required for "high" trust, then encode that. If the spec really is "we got a follower count", drop the misleading second clause and update the comment:
```python
confidence = "high" if (follower_count and posts_last_7d > 0) else "medium"
```

### WR-05: run_all.py header comment overstates child-subprocess redaction coverage

**File:** `scrapers/run_all.py:28-36`
**Issue:** The header comment says "child subprocesses install their own redaction." Reality: only `apify_social.py` and `calibration/validate_extraction.py` do. The other scripts in `SCRIPTS` (`pricing_scraper.py`, `account_types_scraper.py`, `promo_scraper.py`, `social_scraper.py`, `reputation_scraper.py`, `wikifx_scraper.py`, `news_scraper.py`, `ai_analyzer.py`) use `print()` directly without installing the redaction filter. This is acceptable today because `print()` bypasses the `logging`-based filter anyway, but the comment misleads the next maintainer — they will assume that adding a `logger.info(token)` call to any scraper is automatically safe.

Combined with the fact that `print(token)` bypasses the filter entirely, this is a real residual risk: the threat model in `log_redaction.py` says "no API key or credential should ever appear in scraper stdout or log files", but eight of the nine scrapers use `print()` and are not protected at all.

**Fix:** Either
1. Update the comment to be accurate ("only redaction-aware scrapers — currently `apify_social.py` and `calibration/validate_extraction.py` — install their own filter; legacy scrapers using `print()` bypass redaction"), AND add a follow-up task to migrate the legacy scrapers to `logging` once Phase 2 lands; or
2. Replace `print` with `logger.info` shims in the legacy scrapers and have them install redaction at the top of their entry-point files.

### WR-06: Stale comment claims Thunderbit AI extraction "for FB/IG/X" after FB removal

**File:** `scrapers/social_scraper.py:450`
**Issue:**
```python
if thunderbit_key:
    print("Thunderbit API key found — will use AI extraction for FB/IG/X.")
```
FB was moved to `apify_social.py` in this phase (Plan 03 / D-01). The startup banner still announces "FB/IG/X" coverage. Operators reading the log will believe FB is still being scraped via Thunderbit when it is not, and may chase phantom failures during incident triage.

**Fix:**
```python
print("Thunderbit API key found — will use AI extraction for IG/X (FB now via Apify).")
```

### WR-07: data-health TS query type assertion drops decimal precision on cost_usd sum

**File:** `src/app/(dashboard)/admin/data-health/page.tsx:49-55`
**Issue:** `sql<number>\`COALESCE(SUM(${apifyRunLogs.costUsd}), 0)\`` types the result as `number`, but the SQLite better-sqlite3 driver returns `SUM` over a REAL column as either a number or a string depending on adapter version. Line 89 wisely calls `Number(costRow.total) || 0` to coerce, but the inline `sql<number>` type assertion paints over a bug surface (e.g., a bigint return path that silently coerces to NaN, or a non-numeric string like `"NaN"` causing `Number()` to yield `NaN` and `costPct` to become `NaN%`). The current `|| 0` swallows `NaN` (because `NaN || 0 === 0`), so the user sees "$0.00" when the real cost is unparseable — silent failure.

**Fix:** Tighten the coercion path so a parse failure surfaces:
```typescript
const rawTotal = costRow.total;
const totalCost = Number.isFinite(Number(rawTotal)) ? Number(rawTotal) : NaN;
if (!Number.isFinite(totalCost)) {
  console.error("[data-health] Unparseable Apify cost sum from DB:", rawTotal);
}
const safeCost = Number.isFinite(totalCost) ? totalCost : 0;
const costPct = Math.round((safeCost / APIFY_MONTHLY_CAP_USD) * 100);
```

### WR-08: db_utils.py runs DDL on every get_db() call — incurs SQLite write contention under load

**File:** `scrapers/db_utils.py:35-208`
**Issue:** `get_db()` is called every time a scraper opens a connection. On every call it runs a long sequence of `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` statements wrapped in `try/except ... pass`. Even when the migration is a no-op, each `ALTER TABLE` that fails takes a write lock briefly, and scrapers that open and close connections in tight loops (e.g., `log_scraper_run` opens-commits-closes every time) repeat the work.

More importantly: the migration block silences ALL exceptions including ones unrelated to "column already exists" (e.g., schema corruption, disk full, lock contention from a sibling scraper). A real migration failure becomes invisible.

**Fix:** Either gate migrations behind a one-shot setup function called explicitly at scraper start (and not on every `get_db()`), or narrow the exception type:
```python
try:
    conn.execute("ALTER TABLE competitors ADD COLUMN is_self ...")
    conn.commit()
except sqlite3.OperationalError as e:
    # "duplicate column name" is the only acceptable failure here
    if "duplicate column" not in str(e).lower():
        raise
```
This is also flagged because Phase 1's *additive-only* schema constraint relies on these migrations being idempotent — if one of them fails for a reason other than "already exists", the silent `pass` hides the breakage and downstream queries that assume the new column exists will then fail in mysterious ways.

### WR-09: COMPETITORS resolved at module load time, masking config-DB drift

**File:** `scrapers/promo_scraper.py:50-52`, `scrapers/social_scraper.py:46-47`, `scrapers/apify_social.py:70`, `scrapers/apify_social.py:157`
**Issue:** `COMPETITORS = get_all_brokers()` (or `from config import COMPETITORS`) is evaluated at module import. In `apify_social.py:157`:
```python
competitor = next(c for c in COMPETITORS if c["id"] == PHASE_1_COMPETITOR_ID)
```
If the DB has no `scraper_config` populated for `ic-markets` (per `db_utils.py:386-388`, those rows are silently skipped), `next(...)` raises `StopIteration`, which is **not** caught by the broad `except Exception` at line 266 — actually it *is* caught, but the diagnosis from `log_scraper_run` will be a confusing `StopIteration` with no message. More subtly, the `try` block hasn't yet opened a `conn`, so the `finally` block writes an `apify_run_logs` row referencing the run_id but with `apify_run_obj` empty — so the operator sees a "failed" row with no actionable error.

**Fix:** Guard the lookup explicitly with a clear message:
```python
competitor = next((c for c in COMPETITORS if c["id"] == PHASE_1_COMPETITOR_ID), None)
if competitor is None:
    raise RuntimeError(
        f"Competitor '{PHASE_1_COMPETITOR_ID}' missing from get_all_brokers() — "
        f"check scraper_config in DB."
    )
if not competitor.get("facebook_slug"):
    raise RuntimeError(
        f"facebook_slug missing for {PHASE_1_COMPETITOR_ID}; aborting Apify call"
    )
```

## Info

### IN-01: scrapers/run_all.py uses datetime.utcnow() (deprecated in Python 3.12+)

**File:** `scrapers/run_all.py:121, 174, 184, 219`
**Issue:** `datetime.utcnow()` is deprecated in Python 3.12+; the runtime emits a DeprecationWarning. The other Phase 1 modules correctly use `datetime.now(timezone.utc)`.
**Fix:** `datetime.now(timezone.utc).strftime(...)` consistently.

### IN-02: PLATFORMS still lists "facebook" in src/lib/constants.ts after FB cutover

**File:** `src/lib/constants.ts:44-49`
**Issue:** `PLATFORMS` still includes `"facebook"`. That is correct *for the dashboard* (FB data still flows in via `apify_social.py`), but the comment block at the top of `social_scraper.py` (and Plan 03 docs) imply FB is now Apify-owned, so a reviewer might assume `PLATFORMS` should drop it. Add an inline comment to reduce confusion:
**Fix:**
```typescript
export const PLATFORMS = [
  "youtube",
  "facebook",   // Phase 1: scraped by apify_social.py (Apify), not social_scraper.py
  "instagram",
  "x",
] as const;
```

### IN-03: empty-state.tsx description prop has no maxWidth — long copy will stretch the card

**File:** `src/components/shared/empty-state.tsx:36-38`
**Issue:** The description renders a `<p>` with no max-width. A long description will stretch to the full container width. Minor visual issue.
**Fix:** Cap with Tailwind:
```tsx
<p className="mt-1 text-sm text-gray-500 max-w-md mx-auto">{description}</p>
```

### IN-04: log_redaction.py regex `\b[A-Fa-f0-9]{40,}\b` will redact harmless long hex values (commit SHAs, hashes)

**File:** `scrapers/log_redaction.py:67`
**Issue:** Generic 40+ hex pattern matches:
- Git commit SHAs (40 chars)
- SHA-1/SHA-256 hexdigests (40/64 chars)
- Some debug IDs

Operationally this means a scraper that logs `commit abc123...` (40-hex) will see `commit [REDACTED]` and lose triage signal. Acceptable trade-off given the threat model — but worth noting in the docstring so the next person knows why a "weird redaction" happened.
**Fix:** Add a docstring caveat at line 60:
```python
# Note: \b[A-Fa-f0-9]{40,}\b will also match git SHAs, sha256 digests, and
# arbitrary long hex IDs. This is intentional (false-positive redaction is
# preferred over false-negative secret leak), but operators triaging logs
# should be aware that "[REDACTED]" does not always indicate a secret.
```

### IN-05: db_utils.py log_scraper_run uses `error: str = None` — typing should be `Optional[str]`

**File:** `scrapers/db_utils.py:213, 240`
**Issue:** Function signature `error: str = None` is technically valid Python but doesn't match the project's typed style (other modules use `str | None` consistently). Mypy/pyright will warn.
**Fix:** `error: str | None = None` for both `log_scraper_run` and `update_scraper_run`.

### IN-06: promo_extraction.jsonl example rows lack a broker_name field

**File:** `scrapers/calibration/promo_extraction.jsonl:2-6`
**Issue:** Rows have `market`, `language`, `input_text`, `expected_output`, `source_url`, `is_example`. There is no `broker_name`. WR-02 above is the manifestation of this gap. When real calibration data is hand-labeled per Plan 01-06 Task 1, the label set must include a broker_name (or the validator must pass a constant — see WR-02).
**Fix:** Add `"broker_name": "<example_broker_or_calibration_set>"` to every existing example row and update the `_comment` schema description.

### IN-07: empty-state.tsx EmptyStateReason union includes `undefined` redundantly

**File:** `src/components/shared/empty-state.tsx:5`
**Issue:**
```typescript
type EmptyStateReason = "scraper-failed" | "scraper-empty" | "no-activity" | undefined;
```
Adding `| undefined` to the union is redundant when the prop is already declared optional with `reason?:` (line 12). It clutters the union and inverts the meaning at the type-system level (the prop type becomes `EmptyStateReason | undefined | undefined` once the optional `?` is applied).
**Fix:**
```typescript
type EmptyStateReason = "scraper-failed" | "scraper-empty" | "no-activity";
// reason?: EmptyStateReason;  // already optional via ?
```

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

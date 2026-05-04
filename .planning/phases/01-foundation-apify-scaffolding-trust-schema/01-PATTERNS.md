# Phase 1: Foundation — Apify + Scaffolding + Trust Schema - Pattern Map

**Mapped:** 2026-05-04
**Files analyzed:** 11 (4 NEW Python, 3 MODIFIED Python, 2 NEW TS/TSX, 2 MODIFIED TS)
**Analogs found:** 10 / 11 (1 greenfield with no in-repo analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scrapers/apify_social.py` (NEW) | scraper / service | request-response + DB write | `scrapers/social_scraper.py` (FB section), `scrapers/pricing_scraper.py` (run wrapper) | exact (role + flow) |
| `scrapers/log_redaction.py` (NEW) | utility (logging filter) | transform | none in-repo (greenfield) | no analog |
| `scrapers/calibration/promo_extraction.jsonl` (NEW) | data file (fixtures) | static data | none (data file) | n/a |
| `scrapers/calibration/validate_extraction.py` (NEW) | offline test/validator | batch transform | `scrapers/ai_analyzer.py` (Anthropic call shape, prompt-build helpers) | role-match |
| `scrapers/db_utils.py` (MODIFIED) | DB layer / migration runner | schema migration | self (additive `ALTER TABLE`/`CREATE TABLE IF NOT EXISTS` blocks already present, lines 41-135) | self |
| `scrapers/run_all.py` (MODIFIED) | orchestrator / cron entry | subprocess fan-out | self (`SCRIPTS` list + `subprocess.run`) | self |
| `scrapers/social_scraper.py` (MODIFIED) | scraper | request-response | self (replace `_thunderbit_extract()` call site for FB only, lines 293-312, 557-572) | self |
| `src/db/schema.ts` (MODIFIED) | DB types (Drizzle) | type definition | self (`pricingSnapshots`/`socialSnapshots`/`appStoreSnapshots` lines 22-83) | self |
| `src/lib/constants.ts` (MODIFIED) | config (constants) | static data | self (existing `SCRAPERS` array, lines 12-21) | self |
| `src/components/shared/empty-state.tsx` (MODIFIED — see reconciliation) | component | render | self (existing exported `EmptyState`, all 25 lines) | self |
| `src/app/(dashboard)/admin/data-health/page.tsx` (NEW) | server component / page | request-response (DB at render time) | `src/app/(dashboard)/admin/page.tsx`, `src/app/(dashboard)/layout.tsx` (force-dynamic + Promise.all + DB) | exact |

> **Reconciliation note (D-16 vs codebase):** CONTEXT.md D-16 specifies a NEW file at `src/components/ui/empty-state.tsx`. RESEARCH.md (Pattern 6, lines 687-733) verified the codebase already has `src/components/shared/empty-state.tsx` and recommends Option A: extend the existing file with an optional `reason` prop instead of duplicating. **Planner: prefer Option A** — every existing import site (7 files: `error.tsx`, `changes/page.tsx`, `insights/page.tsx`, `markets/page.tsx`, `competitors/page.tsx`, `competitors/[id]/page.tsx`) already imports from `@/components/shared/empty-state`. Creating a parallel `ui/empty-state.tsx` produces inconsistent imports and a duplicate component.

---

## Pattern Assignments

### `scrapers/apify_social.py` (NEW — scraper, request-response + DB write)

**Analog:** `scrapers/social_scraper.py` (Facebook code path is the cutover target)

**Imports + boot pattern** (`scrapers/social_scraper.py:17-46`):
```python
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import DELAY_BETWEEN_REQUESTS, SCRAPER_UA
from db_utils import get_all_brokers
COMPETITORS = get_all_brokers()
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change

SCRAPER_NAME = "social_scraper"
```

**Run-lifecycle pattern** (`scrapers/social_scraper.py:508-621` and `scrapers/pricing_scraper.py` mirror): every scraper opens with `run_id = log_scraper_run(SCRAPER_NAME, "running")`, accumulates `total_records` + `error_summary`, and closes with `update_scraper_run(run_id, status, total_records, error_msg)`. The `apify_social.py` module MUST adopt this exact lifecycle so the `scraper_runs` table stays consistent and the existing `<StaleDataBanner>` keeps working.

**FB call-site to replace** (`scrapers/social_scraper.py:293-312` — `fetch_facebook_stats`, callsite at 557-572):
```python
def fetch_facebook_stats(page_slug: str, scraperapi_key: str | None, thunderbit_key: str | None) -> dict | None:
    """Fetch Facebook stats. Tries Thunderbit AI extraction first, falls back to ScraperAPI regex."""
    if thunderbit_key:
        url = f"https://www.facebook.com/{page_slug}"
        result = _thunderbit_extract(url, _FB_SCHEMA, thunderbit_key)
        if result and result.get("followers"):
            followers = int(result["followers"])
            data = {"followers": followers}
            if result.get("likes"):
                data["likes"] = int(result["likes"])
            if result.get("posts_last_7d") is not None:
                data["posts_last_7d"] = int(result["posts_last_7d"])
            print(f"    [Thunderbit] Facebook OK")
            return data

        print(f"    [Thunderbit] Facebook failed, trying ScraperAPI fallback...")

    if scraperapi_key:
        return _fetch_facebook_legacy(page_slug, scraperapi_key)
    return None
```

**Snapshot upsert + change detection pattern** (`scrapers/social_scraper.py:420-442`):
```python
def _upsert_social(conn, cid: str, platform: str, snapshot_date: str,
                    followers: int, posts_last_7d: int | None = None,
                    engagement_rate: float | None = None, latest_post_url: str | None = None,
                    market_code: str = "global"):
    """Delete + insert a social snapshot row and trigger change detection."""
    conn.execute(
        "DELETE FROM social_snapshots WHERE competitor_id=? AND platform=? AND market_code=? AND snapshot_date=?",
        (cid, platform, market_code, snapshot_date),
    )
    conn.execute(
        """
        INSERT INTO social_snapshots
            (competitor_id, platform, snapshot_date, followers,
             posts_last_7d, engagement_rate, latest_post_url, market_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cid, platform, snapshot_date, followers, posts_last_7d, engagement_rate, latest_post_url, market_code),
    )
    conn.commit()
    field_suffix = "" if market_code == "global" else f"_{market_code}"
    detect_change(conn, cid, f"social_{platform}", f"followers{field_suffix}", str(followers), "low")
```

**What to copy:** Module preamble (lines 17-46) verbatim, the SCRAPER_NAME convention, the `log_scraper_run`/`update_scraper_run` lifecycle, the `_upsert_social` helper signature (extend with `extraction_confidence` per D-18), and the `detect_change()` write path. **What to change:** Replace the Thunderbit `requests.post(...)` body with `client.actor(ACTOR_ID).call(run_input=..., build=ACTOR_BUILD, max_total_charge_usd=..., timeout_secs=...)` (RESEARCH.md Pattern 1, lines 405-444); add the zero-result silent-success guard before any `_upsert_social()` call (RESEARCH.md Pattern 2, lines 448-506); always insert into `apify_run_logs` in a `finally` block regardless of outcome (RESEARCH.md Pattern 3, lines 508-538). Use `logging.getLogger(__name__).info(...)` instead of `print()` so D-12 redaction actually applies; install redaction at the top per Pattern 5.

**Anti-patterns to avoid (from RESEARCH.md lines 854-862):**
- Don't use `:latest` for actor build — pin per D-04.
- Don't bypass `db_utils.get_db()` — reuse the WAL/foreign-keys helper.
- Don't insert a `social_snapshots` row when `len(items) == 0` — that's the silent-success failure mode D-07 prevents.
- Don't try to enforce the $100/mo cap in code (Apify Console only); per-call `max_total_charge_usd` is belt-and-braces.
- Don't use `print()` in this new module — bypasses the redaction filter.

---

### `scrapers/log_redaction.py` (NEW — utility, logging Filter, no in-repo analog)

**Analog:** None in-repo. Existing scrapers use `print()` exclusively (verified via `grep -n "logging\|getLogger\|logger" scrapers/*.py` — zero hits). This is greenfield Python stdlib `logging.Filter` work.

**Reference pattern:** RESEARCH.md Pattern 5 (lines 603-679) gives the exact reference implementation. It is a `logging.Filter` subclass that snapshots secret values from `os.environ` at init and replaces them with `[REDACTED]` in `record.msg`, plus regex passes for `Bearer`, `apify_api_*`, `sk-ant-*`, and 40+ char hex tokens. `install_redaction()` attaches it to the root logger idempotently.

**Naming convention to follow** (from `CLAUDE.md` + existing scrapers): snake_case file, snake_case functions, PascalCase classes (`SecretRedactionFilter`), UPPER_SNAKE_CASE constants (`_SECRET_ENV_VARS`, `_TOKEN_PATTERNS`), leading underscore for module-private helpers.

**Threat-model comment requirement** (from `CLAUDE.md` Comments section): "Security/validation logic: Always document the threat model." Module docstring must state: "leaked log file (committed accidentally, attached to a ticket, or read by a compromised process) must not expose secrets" — explicitly reference the April 2026 EC2 incident (see MEMORY.md `project_ec2_compromise.md`).

**What to copy:** RESEARCH.md Pattern 5 verbatim — the planner can use it as-is. **What to change:** Confirm the env var list matches what's actually in `.env.local` at implementation time; add any newly discovered secrets.

**Caveat (RESEARCH.md lines 683-685):** Existing scrapers print everything; the filter no-ops on `print()` output. Phase 1 only converts `apify_social.py` to `logging`; other scrapers stay on `print()` until later phases. Document this in the runbook.

---

### `scrapers/calibration/promo_extraction.jsonl` (NEW — data fixtures, no analog needed)

**No code analog.** Data file with one JSON object per line. Schema fixed by D-19:
```json
{"market": "TH", "language": "th", "input_text": "<scraped page snippet>", "expected_output": {"promo_type": "...", "value": "...", "currency": "...", "valid_from": "..."}, "source_url": "..."}
```
20-30 items per non-English language (TH, VN, TW, HK, ID). Hand-labeled. The validator script (next file) is the only consumer.

---

### `scrapers/calibration/validate_extraction.py` (NEW — offline validator, batch transform)

**Analog:** `scrapers/ai_analyzer.py` (Anthropic client setup + prompt construction).

**Anthropic client init pattern** (`scrapers/ai_analyzer.py:355-367`):
```python
def run():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
```

**Tool-use call pattern** (`scrapers/ai_analyzer.py:425-442`):
```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    tools=[INSIGHT_TOOL],
    tool_choice={"type": "tool", "name": "record_competitive_insight"},
    messages=[{"role": "user", "content": prompt}],
)

# Extract tool use block
insight_data = None
for block in response.content:
    if block.type == "tool_use" and block.name == "record_competitive_insight":
        insight_data = block.input
        break
```

**What to copy:** The Anthropic client init guard (env var check, ImportError fallback, `sys.exit(1)` on missing prereqs), the `model="claude-sonnet-4-6"` constant, and the tool-use response extraction loop. The validator should `from ai_analyzer import build_prompt` (or whichever extraction function the existing promo flow uses) so it tests the **production** prompt, not a copy.

**What to change:** This script doesn't write to `scraper_runs` (it's an offline validator, not a cron scraper) — skip `log_scraper_run()`. Output is per-language accuracy printed to stdout + a non-zero exit code if any language is below 85%. CLI signature: `python scrapers/calibration/validate_extraction.py [--language TH]`.

**Locate the function the validator must import:** `grep -n "^def " scrapers/promo_scraper.py` and `scrapers/ai_analyzer.py` for the existing extraction entry point. RESEARCH.md notes the prompt currently lives in the promo scraper's Claude call. Planner to confirm the exact import target during planning.

---

### `scrapers/db_utils.py` (MODIFIED — DB layer, additive migration)

**Analog: self.** The existing `get_db()` (`scrapers/db_utils.py:35-146`) is a sequence of additive migrations that run on every connection.

**ALTER TABLE ADD COLUMN pattern** (`scrapers/db_utils.py:42-48`):
```python
# Additive migration: is_self flag (safe to run repeatedly)
try:
    conn.execute("ALTER TABLE competitors ADD COLUMN is_self INTEGER NOT NULL DEFAULT 0")
    conn.commit()
except Exception:
    pass  # column already exists
```

**Multi-column ALTER pattern** (`scrapers/db_utils.py:56-65`):
```python
# Additive migration: cross-source leverage validation columns
for col in (
    "leverage_sources_json", "leverage_confidence", "leverage_reconciliation_json",
    "min_deposit_sources_json", "min_deposit_confidence", "min_deposit_reconciliation_json",
):
    try:
        conn.execute(f"ALTER TABLE pricing_snapshots ADD COLUMN {col} TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists
```

**CREATE TABLE IF NOT EXISTS pattern** (`scrapers/db_utils.py:99-116`):
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS app_store_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competitor_id TEXT NOT NULL REFERENCES competitors(id),
        entity_label TEXT,
        ios_app_id TEXT NOT NULL,
        market_code TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        ios_rating REAL,
        ios_rating_count INTEGER,
        UNIQUE (competitor_id, ios_app_id, market_code, snapshot_date)
    )
""")
conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_app_store_competitor_market
    ON app_store_snapshots (competitor_id, market_code)
""")
conn.commit()
```

**What to copy:** All three patterns above. Phase 1 deltas (D-14):
1. `ALTER TABLE promo_snapshots ADD COLUMN extraction_confidence TEXT` — wrap in try/except, default `NULL`.
2. `ALTER TABLE social_snapshots ADD COLUMN extraction_confidence TEXT` — same shape.
3. `CREATE TABLE IF NOT EXISTS apify_run_logs (...)` — mirror `app_store_snapshots` shape; columns enumerated in D-08 (`run_id`, `actor_id`, `actor_version`, `competitor_id`, `platform`, `market_code`, `started_at`, `finished_at`, `status`, `dataset_count`, `cost_usd`, `error_message`); use `INTEGER PRIMARY KEY AUTOINCREMENT` for `id`; add `scraper_run_id INTEGER REFERENCES scraper_runs(id)` to join with the existing run table (RESEARCH.md Pattern 3 line 522).
4. `CREATE TABLE IF NOT EXISTS share_of_search_snapshots (...)` — schema only this phase (lands early per SUMMARY.md cross-cutting requirement).

**Column-type conventions** (from existing schema): IDs/foreign keys = `TEXT`; counts/booleans/timestamps stored as ISO strings = `INTEGER`/`TEXT`; floats (cost, rating) = `REAL`; JSON blobs = `TEXT`. Confidence values = `TEXT` (`'high'`/`'medium'`/`'low'`/`NULL`).

**Anti-pattern to avoid (RESEARCH.md line 858):** Don't add `drizzle-kit generate` migration files. This codebase uses Python (`db_utils.py`) as the migration source of truth. Adding `drizzle-kit` creates two migration paths that drift.

---

### `scrapers/run_all.py` (MODIFIED — orchestrator, subprocess fan-out)

**Analog: self.**

**Existing SCRIPTS list shape** (`scrapers/run_all.py:26-35`):
```python
SCRIPTS = [
    "pricing_scraper.py",
    "account_types_scraper.py",
    "promo_scraper.py",
    "social_scraper.py",
    "reputation_scraper.py",
    "wikifx_scraper.py",
    "news_scraper.py",
    "ai_analyzer.py",
]
```

**Existing subprocess invocation** (`scrapers/run_all.py:43-76`):
```python
def run_script(script_name: str) -> tuple[bool, float, str]:
    script_path = os.path.join(SCRAPERS_DIR, script_name)
    log_path = os.path.join(LOGS_DIR, f"{_log_name(script_name)}.log")

    start = time.time()
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    elapsed = time.time() - start
    ...
```

**What to copy:** The function shape (`run_script(script_name) -> tuple[bool, float, str]`), per-scraper log file path computation (`_log_name(script_name)` helper), and the per-script log header block. **What to change:** (1) add `"apify_social.py"` to the `SCRIPTS` list; (2) wrap `subprocess.run(...)` in `try`/`except subprocess.TimeoutExpired` with `timeout=PER_SCRAPER_TIMEOUT_SECS` (1800s per D-11) — see RESEARCH.md Pattern 4 (lines 540-583); (3) on success only, call new `_ping_healthcheck(script_name)` helper that reads `HEALTHCHECK_URL_<SCRAPER_NAME>` from env and does a 5s-timeout `requests.get(url)` (D-09/D-10) — see RESEARCH.md Pattern 4 (lines 586-598).

**Anti-pattern to avoid (RESEARCH.md line 869):** Don't hand-roll `Popen` + `kill()` + `waitpid()`. `subprocess.run(timeout=N)` handles kill+wait+pipe-drain in one call.

---

### `scrapers/social_scraper.py` (MODIFIED — replace FB Thunderbit path)

**Analog: self.** Surgical change to one function and one call site.

**Function to replace** (`scrapers/social_scraper.py:293-312` — `fetch_facebook_stats`): Currently calls `_thunderbit_extract(url, _FB_SCHEMA, thunderbit_key)` then falls back to `_fetch_facebook_legacy()`. After the change, this function should `from apify_social import extract_facebook` and delegate (or be deleted entirely if `apify_social.py` owns the FB lifecycle including `_upsert_social()` calls). Planner picks based on whether FB-specific arg routing is still needed at the call site.

**Call site to update** (`scrapers/social_scraper.py:557-572`):
```python
# --- Facebook ---
if fb_slug and (thunderbit_key or scraperapi_key):
    try:
        fb = fetch_facebook_stats(fb_slug, scraperapi_key, thunderbit_key)
        if fb:
            _upsert_social(conn, cid, "facebook", snapshot_date,
                           fb["followers"], posts_last_7d=fb.get("posts_last_7d"),
                           market_code=market_code)
            total_records += 1
            extra = f" | {fb['posts_last_7d']} posts/7d" if fb.get("posts_last_7d") is not None else ""
            print(f"  ✓ Facebook{market_label}: {fb['followers']:,} followers{extra}")
        else:
            print(f"  ✗ Facebook{market_label}: could not extract follower count")
    except Exception as e:
        msg = f"{name} facebook{market_label}: {e}"
        print(f"  ✗ Facebook{market_label}: {e}")
        error_summary.append(msg)
```

**What to copy:** Keep the YouTube/Instagram/X paths in this file untouched (D-01 explicitly says only FB moves to Apify in Phase 1). Keep the `_upsert_social()` helper, the per-market loop, and the run-lifecycle scaffolding. **What to change:** Replace the FB branch's call to `fetch_facebook_stats(...)` with either (a) an import-and-delegate to `apify_social.extract_facebook(competitor, market_code)` that returns the same `{followers, posts_last_7d, ...}` dict, or (b) move the entire FB block into `apify_social.py` and delete it from here. Option (a) is less invasive and preserves the per-scraper run summary; option (b) is cleaner but means `apify_social.py` runs as its own subprocess via `run_all.py` (which is what D-01 + the SCRIPTS-list addition implies). **Recommendation: Option (b)** — the SCRIPTS list addition in `run_all.py` is the explicit choice in CONTEXT.md, so `apify_social.py` is its own scraper script with its own `scraper_runs` row. In that case, the FB branch in `social_scraper.py` is removed and a comment points to `apify_social.py`.

---

### `src/db/schema.ts` (MODIFIED — Drizzle types mirror SQLite migrations)

**Analog: self.**

**Snapshot table convention** (`src/db/schema.ts:22-39` — `pricingSnapshots`):
```typescript
export const pricingSnapshots = sqliteTable("pricing_snapshots", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  competitorId: text("competitor_id").notNull().references(() => competitors.id),
  snapshotDate: text("snapshot_date").notNull(),
  leverageJson: text("leverage_json"),
  accountTypesJson: text("account_types_json"),
  minDepositUsd: real("min_deposit_usd"),
  instrumentsCount: integer("instruments_count"),
  fundingMethodsJson: text("funding_methods_json"),
  spreadJson: text("spread_json"),
  leverageSourcesJson: text("leverage_sources_json"),
  leverageConfidence: text("leverage_confidence"),
  leverageReconciliationJson: text("leverage_reconciliation_json"),
  minDepositSourcesJson: text("min_deposit_sources_json"),
  minDepositConfidence: text("min_deposit_confidence"),
  minDepositReconciliationJson: text("min_deposit_reconciliation_json"),
  marketCode: text("market_code").notNull().default("global"),
});
```

**Existing market_code default convention** (lines 38, 46, 58, 103, 125): `text("market_code").notNull().default("global")`. Mirror this on every new market-aware table.

**Existing socialSnapshots shape** (`src/db/schema.ts:49-59`) — extend with `extractionConfidence: text("extraction_confidence")` (nullable, no default — D-18 says null on legacy rows is acceptable).

**Existing promoSnapshots shape** (`src/db/schema.ts:41-47`) — extend with `extractionConfidence: text("extraction_confidence")` (nullable).

**App-store-snapshots as a model for new tables** (`src/db/schema.ts:74-83`): use `id: integer("id").primaryKey({ autoIncrement: true })`, `competitorId: text("competitor_id").notNull().references(() => competitors.id)`, `marketCode: text("market_code").notNull()`, ratings as `real(...)`, counts as `integer(...)`. Mirror this for `apifyRunLogs` and `shareOfSearchSnapshots`.

**Naming convention** (per `CLAUDE.md` and observed): SQL columns = snake_case, Drizzle field names = camelCase. Table export name = camelCase, SQL table name argument = snake_case (e.g., `apifyRunLogs = sqliteTable("apify_run_logs", ...)`).

**Type mapping**:
- IDs / FKs → `text(...)`
- Status enums (`'success'|'empty'|'failed'`) → `text(...)`
- Counts (`dataset_count`) → `integer(...)`
- Cost (`cost_usd`) → `real(...)`
- Timestamps (ISO strings) → `text(...)` (matches `startedAt`/`finishedAt` on `scraperRuns`, `src/db/schema.ts:148-149`)

**Anti-pattern to avoid (RESEARCH.md line 858 + D-15):** Drizzle types lagging Python migrations is an explicit pitfall. Both files must update in the same PR.

---

### `src/lib/constants.ts` (MODIFIED — add SCRAPERS entry for `apify_social`)

**Analog: self.**

**Existing SCRAPERS list shape** (`src/lib/constants.ts:12-21`):
```typescript
export const SCRAPERS = [
  { name: "pricing-scraper", dbName: "pricing_scraper", label: "Pricing Scraper", domain: "pricing", cadenceHours: 168 },
  { name: "account-types-scraper", dbName: "account_types_scraper", label: "Account Types Scraper", domain: "account_types", cadenceHours: 48 },
  { name: "promo-scraper", dbName: "promo_scraper", label: "Promo Scraper", domain: "promotions", cadenceHours: 48 },
  { name: "social-scraper", dbName: "social_scraper", label: "Social Scraper", domain: "social", cadenceHours: 168 },
  { name: "reputation-scraper", dbName: "reputation_scraper", label: "Reputation Scraper", domain: "reputation", cadenceHours: 72 },
  { name: "wikifx-scraper", dbName: "wikifx_scraper", label: "WikiFX Scraper", domain: "wikifx", cadenceHours: 168 },
  { name: "news-scraper", dbName: "news_scraper", label: "News Scraper", domain: "news", cadenceHours: 6 },
  { name: "ai-analysis", dbName: "ai_analyzer", label: "AI Analysis", domain: "insights", cadenceHours: 24 },
] as const;
```

**What to copy:** Add one new entry following the same shape:
```typescript
{ name: "apify-social", dbName: "apify_social", label: "Apify Social Scraper", domain: "social", cadenceHours: 168 },
```
**What to change:** `dbName` MUST match the `SCRAPER_NAME` constant inside `apify_social.py` (the Python scraper writes that string into `scraper_runs.scraper_name`). `name` is the slug used by the admin "Run" button (`/api/admin/run-scraper`). `cadenceHours: 168` mirrors the existing weekly social cadence; planner can adjust if Phase 1 cron schedule differs.

**Why this matters:** `<StaleDataBanner>` (`src/components/layout/stale-data-banner.tsx:23-48`) iterates `SCRAPERS` and looks up the latest `scraper_runs` row by `dbName`. Without an entry, the new scraper is invisible to the staleness check. The Data Health page also iterates `SCRAPERS` (RESEARCH.md Pattern 7 line 830).

---

### `src/components/shared/empty-state.tsx` (MODIFIED — extend with `reason` prop)

**Analog: self.** D-16 says NEW at `src/components/ui/empty-state.tsx`; RESEARCH.md (verified) says EXTEND existing `src/components/shared/empty-state.tsx`. **Use the existing path.**

**Current full file** (`src/components/shared/empty-state.tsx`, all 25 lines):
```typescript
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-10 text-center">
      {Icon && (
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
          <Icon className="h-6 w-6 text-gray-400" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-gray-500">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
```

**Existing call sites** (must continue to work — `reason` is optional):
- `src/app/(dashboard)/error.tsx:20`
- `src/app/(dashboard)/changes/page.tsx:230, 270`
- `src/app/(dashboard)/insights/page.tsx:88`
- `src/app/(dashboard)/markets/page.tsx:40`
- `src/app/(dashboard)/competitors/page.tsx:223, 277`
- `src/app/(dashboard)/competitors/[id]/page.tsx:342`

**Visual-consistency reference** (`src/components/layout/stale-data-banner.tsx:91-117`): the failed-state variant should use the same red palette tokens as the stale banner (`bg-red-50`, `border-red-200`, `text-red-600`) and the same `AlertTriangle`-family icon (`AlertOctagon` is the recommended distinct sibling per RESEARCH.md line 712). Stale banner pattern:
```typescript
<div className="w-full px-4 py-3 bg-red-50 border-b border-red-200 text-red-900 text-sm">
  <div className="flex items-start gap-3 max-w-6xl mx-auto">
    <AlertTriangle className="w-5 h-5 shrink-0 text-red-600 mt-0.5" aria-hidden="true" />
    ...
```

**What to copy:** Existing `EmptyState` signature unchanged (backward-compatible). **What to change:** Add optional `reason?: "scraper-failed" | "scraper-empty" | "no-activity"` prop and a `REASON_PRESETS` map that selects icon + bg color per reason. RESEARCH.md Pattern 6 (lines 696-732) gives the exact reference implementation. Use `cn()` from `@/lib/utils` (existing utility) for class merging.

**Anti-pattern to avoid (RESEARCH.md line 862):** Don't pin to `src/components/ui/` per D-16 verbatim. The existing component lives at `src/components/shared/empty-state.tsx` and is already imported by 7 callers.

---

### `src/app/(dashboard)/admin/data-health/page.tsx` (NEW — server component, force-dynamic)

**Analog:** `src/app/(dashboard)/admin/page.tsx` (existing admin page) + `src/app/(dashboard)/layout.tsx` (force-dynamic + Promise.all pattern).

**`force-dynamic` declaration** (`src/app/(dashboard)/layout.tsx:11-12`):
```typescript
// Dashboard pages query the SQLite DB at render time — never prerender statically
export const dynamic = "force-dynamic";
```

**Server-page DB query pattern** (`src/app/(dashboard)/admin/page.tsx:10-24`):
```typescript
export default async function AdminPage() {
  const allCompetitors = await db.select().from(competitors);
  const recentRuns = await db
    .select()
    .from(scraperRuns)
    .orderBy(desc(scraperRuns.startedAt))
    .limit(50);

  // Map latest run per scraper
  const latestRunMap: Record<string, typeof recentRuns[0]> = {};
  for (const run of recentRuns) {
    if (!latestRunMap[run.scraperName]) {
      latestRunMap[run.scraperName] = run;
    }
  }
  ...
```

**Section/header layout pattern** (`src/app/(dashboard)/admin/page.tsx:27-43`):
```typescript
return (
  <div className="space-y-8 max-w-6xl">
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
      <p className="text-gray-500 text-sm mt-1">
        System configuration, scraper management, and data overview
      </p>
    </div>

    <section>
      <div className="flex items-center gap-2 mb-4">
        <Server className="w-5 h-5 text-primary" />
        <h2 className="text-lg font-semibold text-gray-900">Scraper Status</h2>
      </div>
      ...
```

**shadcn Table imports** (`src/components/ui/table.tsx:107-116`):
```typescript
export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
```

**What to copy:** Path-alias imports (`@/db`, `@/db/schema`, `@/components/ui/table`, `@/lib/constants`, `@/lib/utils`); `export const dynamic = "force-dynamic"` (already inherited from parent layout but explicit on the page is also fine — RESEARCH.md Pattern 7 declares it explicitly); the `Promise.all([...])` pattern for parallel queries (RESEARCH.md Pattern 7 lines 765-793 has the exact three-query shape: latest runs, Apify cost SUM, zero-result counts); the page header convention (`text-2xl font-bold text-gray-900` for h1, `text-gray-500 text-sm mt-1` for subtitle); the section convention (`space-y-8 max-w-6xl` outer, `<section>` with icon + h2 inner). **What to change:** Replace the existing `ScraperTable` client component with a plain `<Table>` from shadcn (RESEARCH.md Pattern 7 lines 819-848); add the cost panel (`$X.XX of $100/mo cap (XX%)`) with color-coded text per RESEARCH.md lines 802-816 (`text-red-600` if ≥70%, `text-amber-600` if ≥40%, `text-green-700` otherwise — use `Intl.NumberFormat` per RESEARCH.md "Don't Hand-Roll" line 875).

**Routing detail:** Place at `src/app/(dashboard)/admin/data-health/page.tsx`. The `(dashboard)` route group means it inherits `src/app/(dashboard)/layout.tsx` (sidebar + market selector + stale banner) automatically. URL becomes `/admin/data-health`.

---

## Shared Patterns

### Authentication / Authorization

**Source:** `src/middleware.ts` (verified to exist via project context, not re-read here).
**Apply to:** `/admin/data-health` page is automatically gated by the existing dashboard auth middleware (login session cookie). No new auth code needed for this phase.

### Path-alias imports (TypeScript)

**Source:** `tsconfig.json` (`"@/*" → "./src/*"`); used everywhere in `src/`.
**Apply to:** All new TS files. Examples already shown in pattern assignments above.
```typescript
import { db } from "@/db";
import { scraperRuns, apifyRunLogs } from "@/db/schema";
import { SCRAPERS } from "@/lib/constants";
import { formatDateTime, cn } from "@/lib/utils";
```

### Python scraper boot block

**Source:** `scrapers/social_scraper.py:34-44` and `scrapers/promo_scraper.py:37-53` (identical structure across all scrapers).
**Apply to:** `scrapers/apify_social.py`, `scrapers/calibration/validate_extraction.py`.
```python
_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
load_dotenv(os.path.join(_PROJECT_ROOT, ".env.local"))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)
```
**Special note for `apify_social.py`:** Per RESEARCH.md Pattern 1 (lines 414-417), `install_redaction()` from `log_redaction` MUST be called **before** any other import that might log secrets. Place it immediately after the sys.path setup, before importing `apify_client`.

### Run lifecycle (every scraper)

**Source:** `scrapers/social_scraper.py:508` + `:618-621`; mirrored in every scraper.
**Apply to:** `scrapers/apify_social.py`.
```python
SCRAPER_NAME = "apify_social"
...
run_id = log_scraper_run(SCRAPER_NAME, "running")
total_records = 0
error_summary = []
try:
    # ... do work ...
finally:
    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
```

### Error-handling shape (Python scrapers)

**Source:** `scrapers/social_scraper.py:548-552` (per-platform try/except inside the per-broker loop).
**Apply to:** `scrapers/apify_social.py` per-competitor + per-platform loops.
```python
try:
    fb = fetch_facebook_stats(...)
    ...
except Exception as e:
    msg = f"{name} facebook{market_label}: {e}"
    print(f"  ✗ Facebook{market_label}: {e}")
    error_summary.append(msg)
```
**Modification for new scraper:** Replace `print()` with `logger.exception(...)` so the redaction filter applies. Always insert the `apify_run_logs` row in the `finally` (RESEARCH.md Pattern 3) so failures are still observable in Data Health.

### Drizzle DB query patterns (TypeScript)

**Source:** `src/components/layout/stale-data-banner.tsx:66-74` (basic select), `src/app/(dashboard)/admin/page.tsx:11-16` (simple full-table read), and `src/app/(dashboard)/layout.tsx:19-26` (parallel queries — implicit via two awaits; explicit `Promise.all` is preferred per existing convention).
**Apply to:** `src/app/(dashboard)/admin/data-health/page.tsx`.
```typescript
const recentRuns = await db
  .select({
    scraperName: scraperRuns.scraperName,
    finishedAt: scraperRuns.finishedAt,
  })
  .from(scraperRuns)
  .orderBy(desc(scraperRuns.startedAt))
  .limit(200);
```
For the SUM aggregation on `apify_run_logs.cost_usd`, use `sql<number>` template (RESEARCH.md Pattern 7 line 779):
```typescript
import { sql } from "drizzle-orm";
db.select({ total: sql<number>`COALESCE(SUM(${apifyRunLogs.costUsd}), 0)` })
```

### Comment conventions

From `CLAUDE.md` Comments section (and visible in `src/components/layout/stale-data-banner.tsx:51-61`):
- Document the **threat model** in security/validation code (e.g., the redaction filter must explain leaked-log scenario).
- Document **non-obvious algorithms** (e.g., the noise-floor reasoning in `scrapers/db_utils.py:25-29`).
- Document **configuration & defaults** (e.g., why `cadenceHours: 168`, why `STALE_MULTIPLIER = 2.5`).
- Avoid restating variable names or commenting obvious code.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scrapers/log_redaction.py` | utility (logging filter) | transform | Codebase has zero `logging`/`getLogger` usage today — every existing scraper uses bare `print()`. This is greenfield Python stdlib `logging.Filter` work. Use RESEARCH.md Pattern 5 (lines 603-679) as the reference implementation. |
| `scrapers/calibration/promo_extraction.jsonl` | data fixtures | static data | Pure data file with no code analog needed; schema fixed by D-19. |

---

## Cross-File Integration Map

```
apify_social.py ──reads── APIFY_API_TOKEN, HEALTHCHECK_URL_APIFY_SOCIAL (env)
       │
       ├──imports── log_redaction.install_redaction()  ← MUST be first
       ├──imports── apify_client.ApifyClient
       ├──imports── db_utils.get_db, log_scraper_run, update_scraper_run, detect_change
       │
       ├──writes── scraper_runs (existing — via log_scraper_run)
       ├──writes── social_snapshots (existing + new extraction_confidence column)
       ├──writes── apify_run_logs (NEW — always, in finally)
       └──writes── change_events (existing — new event_type='scraper_zero_results')

run_all.py ──invokes── apify_social.py (via subprocess.run with timeout=1800)
       └──pings── HEALTHCHECK_URL_<SCRAPER> on success only

db_utils.py.get_db() ──migrates── adds 2 columns + 2 tables on next connection

src/db/schema.ts ──must mirror── Python migrations (same PR per D-15)

src/lib/constants.ts.SCRAPERS ──must include── apify_social entry
       │
       ├──used by── stale-data-banner.tsx (staleness lookup)
       └──used by── admin/data-health/page.tsx (NEW — table iteration)

src/components/shared/empty-state.tsx ──extended with── reason prop
       └──new variant 'scraper-failed' ──used by── future per-market social view rows

src/app/(dashboard)/admin/data-health/page.tsx ──reads── scraper_runs, apify_run_logs
       └──renders── shadcn Table, cost panel
```

---

## Metadata

**Analog search scope:**
- `scrapers/` (all 14 .py files: account_types_scraper, ai_analyzer, backfill_config_to_db, change_thresholds, config, db_utils, market_config, news_scraper, pricing_scraper, promo_scraper, reputation_scraper, run_all, social_scraper, wikifx_scraper)
- `src/components/` (admin/, layout/, shared/, ui/)
- `src/app/(dashboard)/` (admin/, changes/, competitors/, insights/, markets/, pepperstone/, layout.tsx, page.tsx)
- `src/db/` (index.ts, schema.ts, migrate.ts, seed.ts)
- `src/lib/` (constants.ts, markets.ts, utils.ts)

**Files read for pattern extraction:**
- `scrapers/social_scraper.py` (full, 626 lines)
- `scrapers/db_utils.py` (full, 361 lines)
- `scrapers/run_all.py` (full, 148 lines)
- `scrapers/pricing_scraper.py` (lines 1-100 — boot + Claude wrapper)
- `scrapers/ai_analyzer.py` (lines 1-120 + 355-460 — Anthropic client + prompt + tool-use)
- `scrapers/promo_scraper.py` (lines 1-80 — boot, run lifecycle setup)
- `src/components/shared/empty-state.tsx` (full, 25 lines)
- `src/components/layout/stale-data-banner.tsx` (full, 118 lines)
- `src/components/admin/scraper-table.tsx` (full, 152 lines)
- `src/components/ui/table.tsx` (full, 116 lines)
- `src/db/schema.ts` (full, 159 lines)
- `src/lib/constants.ts` (full, 49 lines)
- `src/app/(dashboard)/admin/page.tsx` (full, 87 lines)
- `src/app/(dashboard)/layout.tsx` (full, 77 lines)
- `src/app/(dashboard)/changes/page.tsx` (lines 220-280 — EmptyState usage)
- `src/app/(dashboard)/admin/actions.ts` (lines 1-50 — server-action conventions)
- `.planning/phases/01-foundation-apify-scaffolding-trust-schema/01-RESEARCH.md` (Pattern 1-7, lines 300-852)

**Pattern extraction date:** 2026-05-04

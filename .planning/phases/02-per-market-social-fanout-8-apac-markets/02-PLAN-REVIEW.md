# Phase 2 Plan Review

**Reviewed:** 2026-05-04
**Plans:** 5 (02-01..02-05)
**Verdict:** PASS
**Iteration:** 1 of 3

---

## Phase-Level Summary

All five plans are well-scoped, factually grounded in the actual codebase state, and together deliver every Phase 2 requirement (SOCIAL-02, SOCIAL-03, MARKET-01..04) and all four ROADMAP success criteria. The wave structure is dependency-correct, file ownership is conflict-free within each wave, and Phase 1 invariants (redaction ordering, contextlib.closing, cost caps, zero-result guard, ACTOR_TO_SCRAPER equality) are explicitly called out and preserved in each plan that touches the relevant files. No scope creep from deferred ideas (per-market handles, BigQuery, AI recs, freshness pill) was found in any plan. Two low-severity observations are noted below as warnings — neither prevents execution.

---

## Verification Dimensions

### Dimension 1: Requirement Coverage

Phase 2 requirements per REQUIREMENTS.md: SOCIAL-02, SOCIAL-03, MARKET-01, MARKET-02, MARKET-03, MARKET-04.

| Requirement | Plan(s) | Tasks that deliver it | Status |
|---|---|---|---|
| SOCIAL-02 (IG Apify scrape + social_snapshots) | 02-03, 02-04, 02-05 | 02-03 Task 2 (run_instagram threading) + Task 3 (loop); 02-04 Task 1 (query); 02-05 Task 1 (diagnostic) | COVERED |
| SOCIAL-03 (X Apify scrape + social_snapshots) | 02-03, 02-04, 02-05 | 02-03 Task 2 (run_x threading) + Task 3 (loop); same UI/diag coverage | COVERED |
| MARKET-01 (market_config JSON or global fallback) | 02-02, 02-03 | 02-02 Task 1 (APAC_V1_MARKETS); 02-03 Task 3 (global fallback when flag empty) | COVERED (Option C per RESEARCH §2 / CONTEXT open-question resolution) |
| MARKET-02 (apifyProxyCountry per tuple; apify_run_logs per market) | 02-02, 02-03, 02-05 | 02-02 (parse_target_markets); 02-03 Task 1 (_proxy_config) + Task 2 (thread into all 5 actor calls + all INSERTs) + Task 3 (loop); 02-05 (per-market diagnostic) | COVERED |
| MARKET-03 (/markets/[code] social with global fallback) | 02-04 | Tasks 1-3 (queries + resolver + JSX) | COVERED |
| MARKET-04 (all 8 markets load without errors) | 02-01, 02-02 | 02-01 Task 2 (PRIORITY_MARKETS fix); 02-02 Task 1 (APAC_V1_MARKETS sync) | COVERED |

All 6 Phase 2 requirements covered. All 4 ROADMAP Phase 2 success criteria have covering plans (per 02-PLAN-INDEX.md success criteria map, confirmed accurate against plan contents).

### Dimension 2: Task Completeness

All tasks in all 5 plans carry `<files>`, `<action>`, `<verify>` (with `<automated>` commands), and `<done>` fields. Checkpoint tasks (02-03 Task 5) correctly omit those fields per spec. Task actions are specific: concrete function names, grep commands, exact code snippets, line references. No vague "implement X" actions found.

| Plan | Task count | Max files touched per task | Completeness |
|---|---|---|---|
| 02-01 | 3 | 1 | All fields present; automated verify runnable |
| 02-02 | 2 | 2 | All fields present; TDD behavior bullets explicit |
| 02-03 | 4 + 1 checkpoint | 2 | All fields present; checkpoint gate has concrete SQL verification |
| 02-04 | 4 | 1 | All fields present; Task 4 is verification-only (correct) |
| 02-05 | 3 | 1 | All fields present; Task 3 is verification-only (correct) |

No completeness gaps found.

### Dimension 3: Dependency Correctness

```
Wave 1 (no deps): 02-01, 02-02
Wave 2 (depends_on: ["02-01","02-02"]): 02-03
Wave 3 (depends_on: ["02-01","02-03"]): 02-04, 02-05
```

- 02-01: `depends_on: []` — correct, standalone markets.ts fix.
- 02-02: `depends_on: []` — correct, standalone Python scaffolding. Does not import from 02-01's output at runtime.
- 02-03: `depends_on: ["02-01","02-02"]` — correct. Imports `parse_target_markets` from market_config.py (02-02) and uses the corrected 8-market list (02-01 canonical reference). No forward references.
- 02-04: `depends_on: ["02-01","02-03"]` — correct. Needs the corrected PRIORITY_MARKETS type (02-01) and per-market data in social_snapshots (02-03).
- 02-05: `depends_on: ["02-01","02-03"]` — correct. Needs per-market apify_run_logs rows (02-03) and the corrected 8-market set as context (02-01).

No cycles. No missing references. Wave assignments consistent with declared deps.

### Dimension 4: Key Links Planned

| Link | From | To | Via | Status |
|---|---|---|---|---|
| 02-01: PRIORITY_MARKETS → MarketSelector | markets.ts | market-selector.tsx | PRIORITY_MARKETS.map() | Wired — plan calls out caller in key_links + interfaces block |
| 02-02: APAC_V1_MARKETS → parse_target_markets | market_config.py | apify_social.py (Plan 02-03) | import + call | Wired — key_links explicitly connect plan 02-02 → plan 02-03 consumer |
| 02-03: _proxy_config → actor.call run_input | apify_social.py | Apify API | proxyConfiguration field in run_input | Wired — Task 1 specifies exact placement inside run_input dict (not kwarg) per RESEARCH Pattern 1 |
| 02-03: market loop → social_snapshots/apify_run_logs writes | run() loop | DB | DEFAULT_MARKET_CODE replacement (verified via grep -c) | Wired — Task 2 explicit: "9 replacements total; grep -c must return 1 (only constant def remains)" |
| 02-04: social_snapshots query → Digital Presence table | page.tsx | DB | Drizzle select, market-first+global-fallback passes | Wired — Tasks 1+2 are sequenced: query first, then build socialMap, then render |
| 02-04: EmptyState import → scraper-failed cells | page.tsx | src/components/shared/empty-state.tsx | import + JSX usage | Wired — Task 3 adds import and uses it for the outer empty state; inline "red dot" for cell-level failure is differentiated and justified |
| 02-05: zeroByMarket → breakdown badge | data-health/page.tsx | apify_run_logs | 4th parallel Drizzle query + ACTOR_TO_SCRAPER equality filter | Wired — Task 1 adds query; Task 2 uses it in render; ACTOR_TO_SCRAPER preservation explicitly called out |

All key links are planned end-to-end, not just artifact creation in isolation.

### Dimension 5: Scope Sanity

| Plan | Tasks | Files modified | Wave | Assessment |
|---|---|---|---|---|
| 02-01 | 3 | 1 | 1 | Well within budget; single-file bug fix |
| 02-02 | 2 | 2 | 1 | Clean; new file + new test file |
| 02-03 | 4 + 1 checkpoint | 2 | 2 | 4 implementation tasks is borderline but justified — each task is a distinct threading step in a single Python file; the checkpoint separates code work from operator gate cleanly |
| 02-04 | 4 | 1 | 3 | Task 4 is verification-only (no writes); effectively 3 implementation tasks in 1 large file — acceptable given the file is 681 lines and each task modifies a discrete section |
| 02-05 | 3 | 1 | 3 | Task 3 is verification-only; effectively 2 implementation tasks — comfortably within budget |

Total: 14 tasks across 5 plans, ~8 files. No plan exceeds the 5-task threshold.

### Dimension 6: Verification Derivation

| Plan | Truths observable? | Artifacts support truths? | Key links connect them? |
|---|---|---|---|
| 02-01 | Yes — "PRIORITY_MARKETS contains exactly 8 codes" is a grep-verifiable fact | Yes — single file, contents directly testable | Yes |
| 02-02 | Yes — "parse_target_markets('') == ['global']" is a unittest assertion | Yes — both files contain testable exports | Yes |
| 02-03 | Yes — "scraper runs identically to Phase 1 when flag unset" is observable via DB query | Yes — _proxy_config + loop presence verifiable via grep | Yes |
| 02-04 | Yes — "Digital Presence section renders with market-first/global-fallback" is browser-visible | Yes — single file, tsc+build confirms wiring | Yes |
| 02-05 | Yes — "per-market badge appears" is browser-visible; DB INSERT test documented in Task 3 | Yes — query + render in same file | Yes |

No implementation-focused truths detected. All truths are user/operator observable or mechanically verifiable via provided bash commands.

### Dimension 7: Context Compliance

CONTEXT.md has 15 locked decisions (D2-01..D2-15). Checking each:

| Decision | Implementing Plan | Implementing Task(s) | Status |
|---|---|---|---|
| D2-01: 8 APAC v1 markets (SG,HK,TW,MY,TH,PH,ID,VN) | 02-01, 02-02 | 02-01 Task 2; 02-02 Task 1 | DELIVERED |
| D2-02: apifyProxyCountry on every actor call | 02-03 | Task 1 (_proxy_config) + Task 2 (inject into all 5 calls) | DELIVERED |
| D2-03: Reuse social_snapshots.market_code | 02-03, 02-04 | No migration — schema reuse confirmed | DELIVERED |
| D2-04: apify_run_logs per (competitor, platform, market_code) | 02-03, 02-05 | Task 2 (replace DEFAULT_MARKET_CODE in log INSERTs); Task 1 adds market diagnostic query | DELIVERED |
| D2-05/06/07: Actor locks (FB pages+posts, IG profile+posts, kaitoeasyapi X) | 02-03 | deviations_allowed MUST NOT block: actor IDs preserved; no new actors | DELIVERED |
| D2-08: Apify Starter required; ship behind feature flag | 02-03 | Task 3 (env-driven TARGET_MARKETS); default = ['global']; checkpoint gate documents operator setup | DELIVERED |
| D2-09: Per-call cost caps preserved | 02-03 | deviations_allowed MUST NOT block: "5 actor cost caps unchanged" | DELIVERED |
| D2-10: Global fallback for no per-market data | 02-03, 02-04 | Task 3 note (writes both market + global); 02-04 Task 2 (two-pass resolver) | DELIVERED |
| D2-11: Zero-result → change_events tagged with market; skip snapshot | 02-03 | Task 2 (replace DEFAULT_MARKET_CODE in zero-result INSERT); deviations_allowed MUST NOT remove guard | DELIVERED |
| D2-12/13: Single weekly cron; one HC.io ping | All plans | No cron changes anywhere; run_all.py untouched per 02-03 deviations_allowed | DELIVERED |
| D2-14: Reuse trust UX (StaleDataBanner, EmptyState scraper-failed, peer benchmarking, extraction_confidence) | 02-04 | Task 3 imports EmptyState; DataSourceBadge reused; peer benchmarking = table layout itself | DELIVERED |
| D2-15: Confidence rule unchanged (high IFF followers>0 AND posts_last_7d>0) | 02-03 | deviations_allowed MUST NOT block | DELIVERED |

No deferred ideas implemented. No locked decisions contradicted. Discretion areas handled appropriately (layout style, Drizzle query pattern, market-selector wiring all left to executor per CONTEXT.md).

### Dimension 7b: Scope Reduction Detection

Scanned all 5 plans' action sections for scope-reduction language. No instances of "v1", "v2", "simplified", "static for now", "hardcoded", "future enhancement", "placeholder", "will be wired later", or similar found that claim to deliver a decision while actually delivering less. The one explicit "Option C" deferral (per-market handles vs. geo-routing-only) is correctly sourced from CONTEXT.md open-question resolution and RESEARCH.md §2, not invented by the planner. It does not contradict any locked decision. PASS.

### Dimension 7c: Architectural Tier Compliance

No RESEARCH.md `## Architectural Responsibility Map` section found. SKIPPED per spec.

### Dimension 8: Nyquist Compliance

SKIPPED — `nyquist_validation: false` in `.planning/config.json`.

### Dimension 9: Cross-Plan Data Contracts

02-03 writes `social_snapshots.market_code` using the loop's `market_code` param. 02-04 reads `social_snapshots` with a market-first/global-fallback two-pass resolver. 02-05 reads `apify_run_logs.market_code` with a GROUP BY query. No plan strips or transforms data that another plan needs in original form. The shared data entity (`market_code` string written by 02-03, read by 02-04 and 02-05) is a simple scalar with a consistent type contract across all three plans. No incompatible transforms detected.

### Dimension 10: CLAUDE.md Compliance

Verified against CLAUDE.md project instructions:

| CLAUDE.md Rule | Plans checked | Status |
|---|---|---|
| npm ci on EC2, never npm install | No npm changes in any plan | PASS |
| Stack locked (Next.js 15, React 19, Drizzle/SQLite, Python) — no new deps | No new pip or npm deps added | PASS |
| stdlib unittest only (no pytest) | 02-02 and 02-03 explicitly require stdlib unittest per D-22; no pytest import | PASS |
| SQLite for this milestone — additive schema changes only | No schema migrations in any plan (D2-03 confirmed) | PASS |
| Error handling: return NextResponse.json errors; use Drizzle ORM to prevent SQL injection | 02-04/05 use Drizzle ORM queries throughout; no raw SQL string interpolation | PASS |
| No Co-Authored-By in commits | Multiple plans explicitly cite D-19 prohibition | PASS |
| install_redaction() BEFORE from apify_client import | 02-03 deviations_allowed MUST NOT block; current file confirmed compliant at line 61-67 | PASS |
| ACTOR_TO_SCRAPER equality lookup (WR-01) | 02-05 explicitly preserves; grep gate included in verification_gates | PASS |
| Parallel data fetching via Promise.all | 02-04 adds to existing Promise.all; 02-05 extends existing Promise.all — not sequential | PASS |

No CLAUDE.md violations detected in any plan.

### Dimension 11: Research Resolution

RESEARCH.md has an `## Open Questions` section (no `(RESOLVED)` suffix). However, examining the three questions:

1. "Will operator approve Apify Starter upgrade BEFORE Phase 2 lands?" — Resolved by design: code ships behind feature flag (D2-08). No unresolved action item that blocks plan execution.
2. "Does kaitoeasyapi X actor support proxyConfiguration?" — Resolved by design: assumption A1 flagged; 02-03 checkpoint:human-verify gate exists to catch it.
3. "Should extraction_confidence thresholds change for per-market?" — Resolved by design: D2-15 locked, rule unchanged.

The questions are operationally resolved by the decisions captured in CONTEXT.md and reflected in the plans — the `## Open Questions` heading lacking `(RESOLVED)` is a documentation cosmetic issue, not a planning blocker. Marking as WARNING (not BLOCKER) because no question remains genuinely unaddressed by the plans.

```yaml
issue:
  plan: null
  dimension: research_resolution
  severity: warning
  description: "RESEARCH.md Open Questions section lacks (RESOLVED) suffix — all 3 questions are operationally addressed by decisions in CONTEXT.md and plan designs, but the heading is not marked resolved"
  fix_hint: "After plan execution, update RESEARCH.md heading to '## Open Questions (RESOLVED)' for housekeeping"
```

### Dimension 12: Pattern Compliance

No PATTERNS.md found in the Phase 2 directory. SKIPPED per spec.

---

## Per-Plan Verdicts

### 02-01 — Fix PRIORITY_MARKETS to 8 APAC v1 codes
**Verdict:** PASS

**Evidence (confirmed by reading src/lib/markets.ts):**
- Bug confirmed: `PRIORITY_MARKETS = ["sg","my","th","vn","id","hk","tw","cn","mn"]` — 9 entries, missing `ph`, includes `cn`+`mn`.
- `MARKET_NAMES` and `MARKET_FLAGS` in `markets.ts` both contain `cn` and `mn` entries, and are typed as `Record<MarketCode, string>`, so they will compile-break if any key is removed without updating the record. Plan 02-01 Task 2 replaces all three records simultaneously — correct approach.
- Caller audit: `market-selector.tsx` imports `PRIORITY_MARKETS, MARKET_NAMES, MARKET_FLAGS` from `@/lib/markets`. All three will narrow from 9 → 8 codes. No switch exhaustiveness checks on MarketCode found. `parseMarketParam` callers (`page.tsx`, `competitors/page.tsx`, `competitors/[id]/page.tsx`) use `MARKET_NAMES[market]` where `market: MarketCode | null` — type remains safe after narrowing.
- `markets/[code]/page.tsx` imports `MARKET_FLAGS` from `@/lib/constants` (not from `markets.ts`), so the `cn`-specific `isChina` block in that file is unaffected by this plan. It will silently become dead UI (the selector won't show CN) but the route will still 404 via DB lookup — not a regression.
- `src/lib/constants.ts` `MARKET_FLAGS` is `Record<string, string>` (superset), so no type break. Plan correctly scopes NOT touching that file.
- Verification gates are concrete and runnable (grep + tsc + lint).

**Concerns:** None.

---

### 02-02 — APAC_V1_MARKETS + parse_target_markets + Wave 0 unit tests
**Verdict:** PASS

**Evidence (confirmed by reading scrapers/market_config.py):**
- Bug confirmed: Python-side `PRIORITY_MARKETS = ["sg","my","th","vn","id","hk","tw","cn","mn"]` — same 9-code error.
- `MARKET_URLS` dict contains `"cn"` and `"mn"` keys for each competitor — plan correctly does NOT touch `MARKET_URLS` (it is not keyed on `PRIORITY_MARKETS`; it is a separate ScraperAPI config). Only `PRIORITY_MARKETS`, `MARKET_NAMES`, and `SCRAPERAPI_COUNTRY_CODES` are updated.
- `parse_target_markets` contract is fully specified: empty input → `['global']`; unknown codes dropped with logging; pure function (no DB, no Apify). This is the exact D2-08 requirement.
- Test class `TestParseTargetMarkets` covers 10 behavior bullets; `TestApacV1Markets` covers list length, exact codes, cn/mn exclusion, and PRIORITY_MARKETS drift guard — comprehensive for the scope.
- Verification gates include `py_compile` + runtime assertion + `python3 -m unittest` with a runnable absolute-path command. Framework is stdlib unittest consistent with Phase 1 convention (test_log_redaction.py, test_run_all_smoke.py).

**Concerns:** None.

---

### 02-03 — Thread market_code through apify_social.py (5 actor calls)
**Verdict:** PASS

**Evidence (confirmed by reading scrapers/apify_social.py):**
- Current file confirmed: `install_redaction()` at line 62, BEFORE `from apify_client import ApifyClient` at line 67 — invariant present and plan's MUST NOT block protects it.
- `contextlib.closing(get_db()) as conn:` at line 642, wrapping all three run_* calls — plan Task 3 preserves the single-connection pattern at the outer loop level.
- `DEFAULT_MARKET_CODE` hardcoded in 9 INSERT sites (3 per run_*: social_snapshots DELETE, social_snapshots INSERT, change_events INSERT) + 3 apify_run_logs INSERTs = confirmed 9 replacement targets as plan states. Grep gate `grep -c 'DEFAULT_MARKET_CODE' scrapers/apify_social.py | Expected: 1` is a tight mechanical check.
- `_fetch_fb_page_metadata` and `_fetch_ig_posts_per_handle` are private helpers that Plan 02-03 Task 2 extends to accept `market_code` — plan correctly identifies them as injection points.
- Feature-flag default: `APIFY_MARKETS_ENABLED` unset → `parse_target_markets(None)` → `['global']` → 1 loop iteration → identical to Phase 1. This is the hard guarantee D2-08 requires.
- The checkpoint:human-verify Task 5 is blocking, has concrete SQL verification, and documents the operator setup checklist (Apify Starter, $100 cap, env var). This satisfies the verification_focus item 11 (operator follow-ups surfaced).
- TDD mock-Apify integration test design is sound: in-memory sqlite3, monkeypatched ApifyClient, real INSERT SQL exercised.

**Concerns:** None.

---

### 02-04 — /markets/[code] Digital Presence section
**Verdict:** PASS

**Evidence (confirmed by reading src/app/(dashboard)/markets/[code]/page.tsx):**
- Page confirmed at 681 lines. `DataSourceBadge` exists at lines 54-69 with the exact signature the plan references. `Promise.all` block starts at line 158 with 7 entries. Plan adds 3 more (marketSocialRows, globalSocialRows, socialZeroResultRows) — making 10 total.
- `socialSnapshots` table is not currently imported into this page. Plan Task 1 adds it to the Drizzle import alongside the new queries — correctly identified gap.
- The two-pass resolver (Pattern 4 from RESEARCH.md) correctly implements D2-10: market row wins; global fills if no market row; zero-result event renders inline failure indicator; row omitted if no data at all.
- Cell-level failure indicator is compact (red dot + text), not the full EmptyState card — plan justifies this (row height constraint). The outer empty state for "no social data at all" uses full EmptyState. This distinction is correct per D2-14 trust continuity.
- `EmptyState` import added in Task 3 — currently NOT imported in this file (confirmed by grepping existing imports). Plan correctly adds it.
- `socialSnapshots` is not in the current schema imports (the page only imports `markets, competitors, pricingSnapshots, promoSnapshots, accountTypeSnapshots, changeEvents`). Plan correctly adds `socialSnapshots` to the import.
- Verification gates: tsc + lint + build + grep checks for "Digital Presence", "isMarketSpecific", "scraper-failed". All runnable.

**Minor observation (WARNING, not BLOCKER):** Plan 02-04 Task 2 builds `socialRows` using `allCompetitors` (fetched at line 147 as `await db.select().from(competitors)`). The variable name `allCompetitors` is confirmed in the page. However, the `allCompetitors` query is outside the `Promise.all` block and runs sequentially before it. The new socialMap derivation depends on both `allCompetitors` and the new queries — correct sequential dependency. No execution-time issue, just worth noting the query ordering.

```yaml
issue:
  plan: "02-04"
  dimension: key_links_planned
  severity: warning
  description: "socialSnapshots table missing from current imports in markets/[code]/page.tsx — plan Task 1 must add it to the Drizzle import. This is called out in the plan's action but not in the files_modified frontmatter (only page.tsx is listed, which is correct — it is a single file change)"
  task: 1
  fix_hint: "No action required — plan Task 1 action explicitly says 'Append three new parallel queries' after the existing Promise.all, which implies the import is added. Executor should note to also add 'socialSnapshots' to the schema import line."
```

---

### 02-05 — /admin/data-health per-market zero-result breakdown
**Verdict:** PASS

**Evidence (confirmed by reading src/app/(dashboard)/admin/data-health/page.tsx):**
- Current file confirmed: 3-entry `Promise.all` at line 38, destructuring `[latestRuns, costRow, zeroCounts]`. Plan adds a 4th entry — `zeroByMarket`.
- `ACTOR_TO_SCRAPER[z.actorId] === s.dbName` equality pattern confirmed at line 137 (the WR-01 fix). Plan 02-05 Task 2 adds a second `ACTOR_TO_SCRAPER` lookup for the breakdown — both must use equality, not `.includes()`. Verification gate checks for 0 substring occurrences.
- `APIFY_MONTHLY_CAP_USD = 5` at line 26 — plan deviations_allowed MUST NOT block explicitly: "leave that value alone in this plan". Correct.
- `force-dynamic` export at line 19 — plan deviations_allowed MUST NOT block. Confirmed present.
- `marketCode !== "global"` filter keeps the page quiet when Phase 2 fanout is disabled. Correct alignment with D2-08 (no false alarms for operators on free tier).
- The new query adds `marketCode: apifyRunLogs.marketCode` to the select. The `apifyRunLogs` schema has `marketCode` column confirmed in schema.ts (via Plan 01-01 additive migration). No schema change needed.

**Concerns:** None.

---

## Phase Coverage Check

| Requirement | Covered by | All 4 success criteria | Verdict |
|---|---|---|---|
| SOCIAL-02 | 02-03, 02-04, 02-05 | SC #2: per-market IG + X attributed at scrape time | PASS |
| SOCIAL-03 | 02-03, 02-04, 02-05 | SC #2: per-market IG + X attributed at scrape time | PASS |
| MARKET-01 | 02-02, 02-03 | SC #3: competitors without per-market data fall back to global | PASS |
| MARKET-02 | 02-02, 02-03, 02-05 | SC #4: apifyProxyCountry on every call; per-(competitor,platform,market) log | PASS |
| MARKET-03 | 02-04 | SC #2: per-market views display IG + X alongside FB | PASS |
| MARKET-04 | 02-01, 02-02 | SC #1: all 8 APAC markets appear without errors | PASS |

All 6 requirements and all 4 success criteria covered.

---

## Issues Summary

```yaml
issues:
  - plan: null
    dimension: research_resolution
    severity: warning
    description: "RESEARCH.md Open Questions section lacks (RESOLVED) suffix — all 3 questions are operationally resolved by CONTEXT.md decisions and plan designs, but the section heading is not marked"
    fix_hint: "After execution: update '## Open Questions' to '## Open Questions (RESOLVED)' in 02-RESEARCH.md"

  - plan: "02-04"
    dimension: task_completeness
    severity: warning
    description: "Plan Task 1 action implies adding socialSnapshots to the Drizzle import line but this is not called out explicitly in the task's <action> text — executor may overlook it"
    task: 1
    fix_hint: "In Task 1 action, add an explicit step: 'Also add socialSnapshots to the Drizzle import at the top of the file (import { ..., socialSnapshots } from \"@/db/schema\"' alongside the Promise.all additions."
```

Blockers: **0**
Warnings: **2** (both minor documentation/explicitness gaps; neither prevents execution or goal delivery)

---

## Recommended Action

**PASS — ready for `/gsd-execute-phase 02`.**

The plans are factually accurate against the current codebase, correctly sequence dependency-ordered work, preserve all Phase 1 invariants, and collectively deliver every Phase 2 requirement. Execute in wave order (02-01 + 02-02 in parallel → 02-03 with its operator checkpoint → 02-04 + 02-05 in parallel).

Executor follow-up for 02-04 Task 1: add `socialSnapshots` to the Drizzle schema import line when appending the three new queries to Promise.all.

After all plans are shipped: update RESEARCH.md `## Open Questions` heading to `## Open Questions (RESOLVED)`.

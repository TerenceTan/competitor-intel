---
phase: 01-foundation-apify-scaffolding-trust-schema
plan: 08
subsystem: dashboard-ui+scrapers
tags: [data-health, actor-mapping, apify-social, connection-leak, extraction-confidence, gap-closure, code-review-fix, wave-4]

# Dependency graph
requires:
  - "Plan 01-03 (scrapers/apify_social.py is the file under repair — connection-leak and confidence-rule fixes apply to its existing structure)"
  - "Plan 01-05 (src/app/(dashboard)/admin/data-health/page.tsx is the file under repair — substring-match lookup is replaced with equality-keyed map)"
provides:
  - "src/lib/constants.ts — new ACTOR_TO_SCRAPER map: single source of truth on the TS side for actor_id → dbName mapping (mirrors scrapers/apify_social.py:79 ACTOR_ID)"
  - "src/app/(dashboard)/admin/data-health/page.tsx — zero-result count column now reads via equality lookup against ACTOR_TO_SCRAPER instead of the broken substring match that always returned 0"
  - "scrapers/apify_social.py — connection-safe DB writes (contextlib.closing on both get_db() sites) + corrected extraction_confidence rule (posts_last_7d > 0 instead of the always-True is-not-None check)"
affects:
  - "Phase 2 (Per-Market Social Fanout) — when Instagram (apify/instagram-scraper) and X (apidojo/tweet-scraper) actors land, ACTOR_TO_SCRAPER gains two entries on the TS side and the corresponding scraper modules each define their own ACTOR_ID; data-health/page.tsx renders the new rows automatically without further changes. The fixed apify_social.py is the boilerplate that will be copied 8× across markets — both the connection-closing pattern and the strict-confidence rule propagate."
  - "Phase 5 (Confidence & Freshness UX Polish) — extraction_confidence values produced by apify_social.py now reliably distinguish 'high' from 'medium' so freshness pills can be wired against truthful trust signals"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-language single-source-of-truth via mirrored map: TS-side ACTOR_TO_SCRAPER (Record<string, string> in src/lib/constants.ts) mirrors Python-side ACTOR_ID (string constant in scrapers/apify_social.py). Comments in both files cross-reference each other so anyone editing one is steered to the other. Phase 2 fanout adds entries on both sides in the same commit."
    - "Equality lookup over a static map (Record<string, string>) replaces substring-match for cross-domain key correlation — explicit, deterministic, type-safe, no dependence on string-shape coincidences. Pattern applies any time scraper-side identifiers (here Apify actor_id) need to round-trip to UI-side scraper rows."
    - "contextlib.closing() as the canonical wrapper for sqlite3.Connection objects in scraper modules — releases the file descriptor on block exit (success or exception). Lower-cognitive-load than try/finally + conn.close(); exception-safe by construction. Adopted as the convention for the Apify scraper boilerplate Phase 2 will fan out 8×."
    - "Confidence rule strictness: 'high' confidence requires BOTH followers AND posts_last_7d > 0 (not just is-not-None). When sum() always returns int >= 0, the 'is not None' guard is degenerate — replaced with a positive-integer check that matches the docstring contract. Applied here for FB; Phase 2 IG/X actors must adopt the same shape (both signals positive → high, otherwise medium) so trust signals are comparable across platforms."

key-files:
  created: []
  modified:
    - src/lib/constants.ts
    - src/app/(dashboard)/admin/data-health/page.tsx
    - scrapers/apify_social.py

key-decisions:
  - "ACTOR_TO_SCRAPER landed in src/lib/constants.ts (next to SCRAPERS, above STALE_MULTIPLIER) rather than in src/app/(dashboard)/admin/data-health/page.tsx — keeping all scraper-related constants in one file means future readers find the actor_id→scraper relationship adjacent to the SCRAPERS array it complements, and the same map can be reused by future admin pages or API routes without per-consumer re-declaration."
  - "Map shape Record<string, string> (rather than a tagged enum or object literal with extra metadata) — zero-result lookup only needs actor_id → dbName; richer metadata (cost-per-call, expected cadence, etc.) belongs in the SCRAPERS array. Keeping ACTOR_TO_SCRAPER lean defers the design choice for Phase 2 when more than one Apify scraper exists."
  - "contextlib.closing() over manual try/finally + conn.close() — closing() is the documented stdlib idiom for sqlite3.Connection (Python docs reference it explicitly), reads as 'wrap and release' in one line, and the existing project pattern referenced in 01-REVIEW.md WR-03 picked this shape. Manual try/finally would expand the diff and obscure the intent."
  - "WR-04 fix uses parenthesized boolean (`if (follower_count and posts_last_7d > 0)`) for explicitness — Python operator precedence makes the parens optional, but they signal to a reader that 'both conditions matter' and prevent a future edit from accidentally reordering the expression into something subtly different. Same posture other phases used for non-trivial conditional expressions (e.g., Plan 01-04's TIMEOUT/OK/FAILED ladder)."
  - "Comments at every fix site are anchored to the code review IDs (WR-01 / WR-03 / WR-04) and to the verification gap ID (SC3) — when someone in 6 months wonders why the lookup is equality-based or why confidence is strict, the comment immediately points them at the audit trail (01-REVIEW.md / 01-VERIFICATION.md) instead of forcing git-blame archaeology."
  - "Surgical edit posture across all 3 files: each file's diff scope is limited to the precise lines covered by the must-have truths in frontmatter — no opportunistic refactors, no formatting cleanups, no co-author lines (per project memory feedback_no_coauthor.md). The commits are small enough that a future revert is trivial if any of the three fixes turns out to have a hidden interaction."

requirements-completed: [TRUST-05, SOCIAL-01, SOCIAL-05]

# Metrics
duration: ~3min
completed: 2026-05-04
---

# Phase 1 Plan 8: Data Health Actor Mapping + Apify Scraper Hardening Summary

**Three defects across two adjacent code paths fixed in one plan because they share the apify_social.py file and the Data Health correctness story: (1) the `/admin/data-health` zero-result count column was permanently broken because `z.actorId.includes(s.name)` could never match `apify_social` against actor_id `apify/facebook-posts-scraper` — replaced with an equality lookup against a new `ACTOR_TO_SCRAPER` map in `src/lib/constants.ts` (single source of truth on the TS side, mirrors `scrapers/apify_social.py:79 ACTOR_ID`); (2) `scrapers/apify_social.py` was leaking two SQLite connections per run (one in the try block, one in the finally block) — both wrapped in `contextlib.closing()` so the file descriptor is released on block exit; (3) the extraction_confidence rule was degenerate (`sum() is not None` is always True) — replaced with `posts_last_7d > 0` so a run that returns items but no parseable timestamps now correctly reports `confidence='medium'` instead of falsely reporting `'high'`. Closes gap SC3 from 01-VERIFICATION.md and code review WR-01 / WR-03 / WR-04. The Apify scraper boilerplate is now safe for Phase 2 to fan out 8× across markets.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-04T07:59:52Z
- **Completed:** 2026-05-04T08:02:45Z
- **Tasks:** 2 of 2
- **Files created:** 0
- **Files modified:** 3 (`src/lib/constants.ts`, `src/app/(dashboard)/admin/data-health/page.tsx`, `scrapers/apify_social.py`)

## Accomplishments

- **`ACTOR_TO_SCRAPER` map shipped in `src/lib/constants.ts`** as a `Record<string, string>` exporting `"apify/facebook-posts-scraper" → "apify_social"`. Sits between the existing `SCRAPERS` array and the `STALE_MULTIPLIER` constant so anyone reading `SCRAPERS` sees the related map next. Doc comment cross-references the Python-side source of truth (`scrapers/apify_social.py:79 ACTOR_ID`) and explicitly calls out the Phase 2 fanout shape (Instagram + X actors will need entries on both sides in the same commit). One entry today (covers the only Phase 1 actor); zero-cost extension shape for Phase 2.
- **`/admin/data-health` zero-result lookup fixed (Gap SC3 closed).** Replaced the 4-line `zeroCounts.find((z) => z.actorId.includes(s.name) || z.actorId.includes(s.dbName))` block with a 2-line equality lookup `zeroCounts.find((z) => ACTOR_TO_SCRAPER[z.actorId] === s.dbName)`. The substring match was permanently returning 0 because actor_id (`apify/facebook-posts-scraper`) never contains the dbName (`apify_social`) or the slug (`apify-social`). Comment block updated to point at `@/lib/constants` and to the WR-01 / SC3 audit trail. Import line gains `ACTOR_TO_SCRAPER` alongside `SCRAPERS` from the same module — zero new import.
- **`scrapers/apify_social.py` connection leak fixed (WR-03 closed).** Both `get_db()` call sites now wrapped with `with closing(get_db()) as conn:` — Site A in the try block (handles both the zero-result `change_events` write and the success-path `social_snapshots` DELETE+INSERT), Site B in the finally block (always-write `apify_run_logs` row). The whole `if/else` body inside Site A re-indented one level (4 spaces) to live inside the new `with` block — verified by `git diff -w` that NO SQL string, parameter tuple, or status assignment changed inside the moved blocks. `from contextlib import closing` added to the stdlib import group, adjacent to `import sys` per the project's existing import-order convention. `apify_run_logs` is still inserted on every code path (success / empty / failed) — the always-write contract per SOCIAL-05 / D-08 / RESEARCH.md Pattern 3 is preserved exactly.
- **`scrapers/apify_social.py` confidence rule corrected (WR-04 closed).** `confidence = "high" if follower_count and posts_last_7d is not None else "medium"` → `confidence = "high" if (follower_count and posts_last_7d > 0) else "medium"`. The previous rule was effectively `"high" if follower_count else "medium"` because `sum()` always returns `int >= 0` (never `None`), so the `is not None` clause was always True and the rule didn't enforce the post-freshness condition the docstring promised. The docstring above the rule (`"high" when both followers and posts_last_7d are derivable`) now matches reality. A 6-line comment anchored to WR-04 explains the fix and the failure mode it prevents (a run that returns 50 items but every timestamp fails to parse will now correctly report `confidence='medium'` instead of falsely reporting `'high'`).
- **All 7 must-have truths in frontmatter satisfied.** Verified by automated gates:
  - tsc --noEmit clean (0 new errors anywhere in the repo)
  - py_compile clean for `scrapers/apify_social.py`
  - 5 positive grep gates pass on the TS side (3 on constants.ts: `ACTOR_TO_SCRAPER`, `"apify/facebook-posts-scraper"`, `"apify_social"`; 2 on page.tsx: import shape + equality lookup)
  - 3 positive grep gates pass on the Python side (`from contextlib import closing`, `with closing(get_db()) as conn:` x2, `posts_last_7d > 0`)
  - 4 negative grep gates pass (`z.actorId.includes(s.name)` and `z.actorId.includes(s.dbName)` both gone from page.tsx; bare `^conn = get_db()` and `posts_last_7d is not None` both gone from apify_social.py)
  - AST sanity passes — `run()` function still defined and exported in apify_social.py
- **`git diff --stat` shows exactly 3 files changed** (`src/lib/constants.ts` +15 lines, `src/app/(dashboard)/admin/data-health/page.tsx` ±13 lines, `scrapers/apify_social.py` re-indented + 8 net lines). No collateral edits, no formatting churn, no opportunistic refactors.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| ACTOR_TO_SCRAPER lives in `src/lib/constants.ts` next to SCRAPERS | Co-locating scraper-related constants means future Phase 2/5 readers find the actor_id→scraper relationship adjacent to the SCRAPERS array; one import per consumer covers all scraper metadata. |
| Map shape `Record<string, string>` (lean) | Zero-result lookup only needs `actor_id → dbName`. Richer metadata (cost, cadence, etc.) belongs in `SCRAPERS`. Keeping the map lean defers design decisions until Phase 2 introduces a second Apify scraper. |
| `contextlib.closing()` over manual try/finally + conn.close() | Closing is the documented stdlib idiom for `sqlite3.Connection`; expresses 'wrap and release' in one line; exception-safe by construction. RESEARCH.md / 01-REVIEW.md WR-03 already specified this shape — diverging is not safer. |
| WR-04 condition uses explicit parens `(follower_count and posts_last_7d > 0)` | Operator precedence makes the parens optional, but they signal 'both conditions matter' to a reader and prevent accidental reordering during a future edit. |
| Comments anchored to audit IDs (WR-01 / WR-03 / WR-04 / SC3) | Future readers wondering 'why equality?' or 'why strict?' get pointed at `01-REVIEW.md` / `01-VERIFICATION.md` directly, no git-blame archaeology required. |
| Surgical edit posture — no opportunistic refactors | Each file's diff is bounded by the must-have truths in frontmatter. No formatting cleanups, no co-author lines (per `feedback_no_coauthor.md`). Small reverts if any fix has a hidden interaction. |

## Deviations from Plan

None — plan executed exactly as written. All edit shapes, import positions, comment text, and acceptance criteria were followed verbatim. The plan was authored as a "surgical fix" plan and required no Rule 1-4 deviations.

## Authentication Gates

None encountered. This plan touches only TS files (compiled by `tsc --noEmit` against the worktree's main-repo `node_modules`) and a Python file (validated by `python3 -m py_compile`). Neither verification step required external auth.

## Threat Model Coverage

All 4 STRIDE threats from the plan's `<threat_model>` are mitigated by the implementation:

| Threat ID | Category | Disposition | How Mitigated |
|-----------|----------|-------------|---------------|
| T-01-08-01 | Tampering | mitigate | Equality match against `ACTOR_TO_SCRAPER` (Record<string, string>) — no string-includes ambiguity. Read at server-render time only, no untrusted input crosses the boundary. |
| T-01-08-02 | Repudiation | mitigate (preserved) | `with closing(...)` does not change the always-write contract for `apify_run_logs` — block still commits before exit on every code path; surrounding try/except still logs failures. Verified by `git diff -w` that the INSERT SQL + parameter tuple are byte-identical. |
| T-01-08-03 | DoS (resource exhaustion) | mitigate | `with closing(...)` releases the SQLite file descriptor on block exit (success or exception). Cron processes are short-lived so impact today is bounded; the pattern is now correct for Phase 2 fan-out 8×. |
| T-01-08-04 | Information Disclosure | mitigate | Confidence rule now correctly reports `'medium'` when `posts_last_7d == 0` even if items were returned. Downstream Phase 5 freshness pills will act on the truth instead of a misleading `'high'` signal. |

No new threat surface introduced.

## Operator Follow-ups

Live verification of the data-health zero-result column requires either of the following — both inherited from earlier Phase 1 plans, neither in scope for this plan:

1. **Phase 1 Apify operator follow-ups (carryover from STATE.md / 01-03 / 01-05):**
   - Re-verify Apify actor build tag at https://console.apify.com/store/apify~facebook-posts-scraper > Builds tab; auto-mode default of `1.16.0` may need updating in BOTH `scrapers/apify_social.py` `ACTOR_BUILD` constant AND `.planning/phases/01-foundation-apify-scaffolding-trust-schema/APIFY_BUILD_VERIFIED.txt`.
   - Set `APIFY_API_TOKEN` in EC2 `.env.local` from Apify Console > Settings > Integrations > Personal API tokens.
   - Set Apify Console monthly $100 spending cap (Settings > Usage limits) per D-06.
   - Verify EC2 Python ≥ 3.10; write `.planning/phases/01-foundation-apify-scaffolding-trust-schema/EC2_PYTHON_VERIFIED.txt`.
   - `pip install -r scrapers/requirements.txt` on EC2.
   - One-time smoke test `python3 scrapers/apify_social.py` and verify `apify_run_logs` row + either `social_snapshots` row OR `change_events scraper_zero_results` row.

2. **One-off DB seed for visual verification of the data-health page (optional, no operator prerequisites):**
   ```sql
   sqlite3 data/competitor-intel.db "INSERT INTO apify_run_logs (apify_run_id, actor_id, actor_version, competitor_id, platform, market_code, status, dataset_count, cost_usd, started_at, finished_at) VALUES ('test-run-001', 'apify/facebook-posts-scraper', '1.16.0', 'ic-markets', 'facebook', 'global', 'empty', 0, 0.0, strftime('%Y-%m-%dT%H:%M:%fZ','now'), strftime('%Y-%m-%dT%H:%M:%fZ','now'));"
   ```
   Visit `/admin/data-health` — expect `Apify Social Scraper` row to show `1` in the Zero-result runs (7d) column. Cleanup: `DELETE FROM apify_run_logs WHERE apify_run_id='test-run-001';`.

Neither follow-up is blocking — the static gates in this plan are sufficient to confirm the equality-lookup is wired correctly. Live verification is operator-side once the Phase 1 Apify infra prerequisites land.

## Threat Flags

None. No new network endpoints, auth paths, file-access patterns, or schema changes at trust boundaries were introduced.

## Self-Check: PASSED

- `src/lib/constants.ts` — FOUND (modified, +15 lines, ACTOR_TO_SCRAPER export verified by grep)
- `src/app/(dashboard)/admin/data-health/page.tsx` — FOUND (modified, ±13 lines, equality lookup verified by grep, broken substring match removed verified by negative grep)
- `scrapers/apify_social.py` — FOUND (modified, +8 net lines after indentation, both `with closing(get_db()) as conn:` sites verified by grep, `from contextlib import closing` import verified by grep, `posts_last_7d > 0` verified by grep, all 4 broken patterns removed verified by negative grep)
- Commit `6e435c8` — FOUND in `git log --oneline -5` (Task 1: ACTOR_TO_SCRAPER + data-health equality lookup)
- Commit `7da0b63` — FOUND in `git log --oneline -5` (Task 2: contextlib.closing + posts_last_7d > 0 confidence rule)
- tsc --noEmit — PASSED (exit 0, no new errors)
- python3 -m py_compile scrapers/apify_social.py — PASSED (exit 0)
- AST sanity — PASSED (`run()` function still defined and exported)
- `git diff --stat 3b0cc2c..HEAD` — PASSED (exactly 3 files changed: constants.ts, data-health/page.tsx, apify_social.py)

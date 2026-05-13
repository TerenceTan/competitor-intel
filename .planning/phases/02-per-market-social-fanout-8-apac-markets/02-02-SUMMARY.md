---
phase: 02-per-market-social-fanout-8-apac-markets
plan: 02
subsystem: scrapers
tags: [scrapers, python, feature-flag, foundation, tests, market-config, apify]
requirements: [MARKET-01, MARKET-02, MARKET-04]
dependency-graph:
  requires:
    - "scrapers/market_config.py (existing, edited)"
    - "scrapers/test_log_redaction.py (style reference for sys.path preamble)"
    - "scrapers/test_run_all_smoke.py (style reference for stdlib-unittest module shape)"
  provides:
    - "APAC_V1_MARKETS canonical list (single source of truth on the scraper side; mirrors src/lib/markets.ts PRIORITY_MARKETS after plan 02-01)"
    - "parse_target_markets(env_value) helper for the APIFY_MARKETS_ENABLED feature flag (RESEARCH.md Pattern 3, D2-08)"
    - "scrapers/test_apify_social_market.py — Wave 0 test scaffold; plan 02-03 will extend with mock-Apify integration tests"
  affects:
    - "scrapers/apify_social.py (plan 02-03 will import parse_target_markets here)"
    - "scrapers/market_config.py — PRIORITY_MARKETS, MARKET_NAMES, SCRAPERAPI_COUNTRY_CODES, MARKET_URLS now keyed on 8 APAC v1 codes (cn + mn out; ph in)"
tech-stack:
  added: []
  patterns:
    - "Module-level feature-flag parser: returns ['global'] for unset/empty input (free-tier-safe default per D2-08); silently drops unknown codes with a logging.warning so a typo cannot burn Apify budget"
    - "Stdlib-unittest Wave 0 scaffold pattern (snake_case test_* names, sys.path-insert preamble copy-verbatim from test_log_redaction.py) — re-used for every future per-feature test module in scrapers/"
key-files:
  created:
    - "scrapers/test_apify_social_market.py"
  modified:
    - "scrapers/market_config.py"
decisions:
  - "Reconciled MARKET_URLS by deleting cn + mn entries from every competitor's per-market block. The 11 competitors now hold 7 of 8 APAC v1 markets (ph missing); get_market_urls() returns None for missing keys which the callers already treat as the geo_proxy fallback path. Per RESEARCH.md §2 / Q1 Option C (geo-routing only this cycle, per-market handles deferred), adding fabricated ph URLs would be guesswork — leaving the fallback to do its job is the documented Phase 2 path."
  - "Hoisted `import logging` to module top instead of inlining inside parse_target_markets (plan's example sketch inlined it). Module-top import is the project convention and avoids re-importing on every call; functionally identical."
  - "Used `Optional[str]` rather than `str | None` in the parse_target_markets signature so the module continues to work on Python 3.9 environments (the existing file's `from typing import Optional` import was already in place; no functional change for 3.10+)."
  - "Comment rephrased to avoid quoting the old `cn`/`mn` codes so the verification-gate grep `\"cn\"|\"mn\"` returns 0 cleanly; the historical context is still preserved in prose."
  - "Kept PRIORITY_MARKETS as a `list(APAC_V1_MARKETS)` shallow copy rather than aliasing — defends downstream callers from accidental mutation of the canonical list."
metrics:
  duration_minutes: 3.4
  completed_date: 2026-05-13
  task_count: 2
  file_count: 2
---

# Phase 2 Plan 02: APAC_V1_MARKETS + parse_target_markets feature-flag parser Summary

Lands the canonical APAC v1 market list (`APAC_V1_MARKETS = ["sg","hk","tw","my","th","ph","id","vn"]`) and the `parse_target_markets(env_value)` helper for the `APIFY_MARKETS_ENABLED` env flag in `scrapers/market_config.py`, plus a stdlib-unittest Wave 0 test module that exercises the parser before plan 02-03 lands the `apify_social.py` market loop refactor.

## What Shipped

### Task 1 — `scrapers/market_config.py` (commit `9a45284`)

- **`APAC_V1_MARKETS: list[str]`** — eight APAC v1 codes, single source of truth on the scraper side; manually mirrors `src/lib/markets.ts PRIORITY_MARKETS` after plan 02-01.
- **`parse_target_markets(env_value: Optional[str]) -> list[str]`** — parses comma-separated `APIFY_MARKETS_ENABLED` input:
  - `None` / empty / whitespace-only -> `["global"]` (free-tier-safe default per D2-08; preserves Phase 1 single-market behavior when the operator hasn't flipped the flag).
  - `"sg,my"` -> `["sg","my"]` with whitespace trimmed, codes lowercased, unknown codes silently dropped with a `logging.warning`.
  - `"global"` is a valid token and may coexist with market codes (`"global,sg"` -> `["global","sg"]`).
- **`PRIORITY_MARKETS`** now derived from `APAC_V1_MARKETS` (was `["sg","my","th","vn","id","hk","tw","cn","mn"]` — included out-of-scope `cn` + `mn`, missing `ph`).
- **`MARKET_NAMES`** rekeyed on the 8 APAC v1 codes (dropped `cn` + `mn`, added `ph: "Philippines"`).
- **`SCRAPERAPI_COUNTRY_CODES`** same treatment.
- **`MARKET_URLS`** — `cn` and `mn` blocks removed from each of the 11 competitor entries. Missing keys correctly fall through `get_market_urls()` to the geo_proxy fallback path.

### Task 2 — `scrapers/test_apify_social_market.py` (commit `b236793`)

15-test stdlib-unittest module covering:

**`TestParseTargetMarkets`** (11 tests):
- `None` / `""` / whitespace-only -> `["global"]`
- `"global"` passes through; `"sg"` returns `["sg"]`; `"sg,my,th"` preserves order
- Case-and-whitespace normalisation (via `subTest` for the three variants: `"SG, MY "`, `"  sg ,  my  "`, `"Sg,mY"`)
- Unknown codes silently dropped (`"sg,xx,my"` -> `["sg","my"]`)
- Degenerate input fallback (`",,,"` -> `["global"]`)
- `"global"` alongside market codes (`"global,sg"` -> `["global","sg"]`)
- Belt-and-braces "ALL tokens unknown" fallback (`"xx,yy,zz"` -> `["global"]`) — not in the original behavior bullets but added to lock the `return out or ["global"]` safety guard.

**`TestApacV1Markets`** (4 tests):
- Length is exactly 8
- Membership matches exactly `{"sg","hk","tw","my","th","ph","id","vn"}`
- Explicit `"cn" not in` and `"mn" not in` assertions
- `PRIORITY_MARKETS` mirrors `APAC_V1_MARKETS` (catches future drift if a hand-edit re-introduces cn/mn or drops ph)

Discoverable via both `python3 -m unittest scrapers.test_apify_social_market` (package import) and `python3 -m unittest discover scrapers/`. Same `sys.path.insert(0, os.path.dirname(...))` preamble as `scrapers/test_log_redaction.py`.

## Commits

| Task | Commit | Files | Summary |
| ---- | ------ | ----- | ------- |
| 1 | `9a45284` | scrapers/market_config.py | feat(02-02): add APAC_V1_MARKETS + parse_target_markets to market_config |
| 2 | `b236793` | scrapers/test_apify_social_market.py | test(02-02): add Wave 0 unit tests for parse_target_markets |

## Verification

All five plan verification gates pass:

```
gate 1: py_compile clean
  python3 -m py_compile scrapers/market_config.py scrapers/test_apify_social_market.py
  -> py_compile OK

gate 2: APAC_V1_MARKETS contains all 8 codes (>= 8)
  grep -c '"sg"\|"hk"\|"tw"\|"my"\|"th"\|"ph"\|"id"\|"vn"' scrapers/market_config.py
  -> 95 (each code appears across MARKET_NAMES, SCRAPERAPI_COUNTRY_CODES,
        APAC_V1_MARKETS and the 11 competitor MARKET_URLS blocks)

gate 3: cn/mn gone (== 0)
  grep -c '"cn"\|"mn"' scrapers/market_config.py
  -> 0

gate 4: unittest discovery + run
  python3 -m unittest scrapers.test_apify_social_market -v
  -> Ran 15 tests in 0.000s — OK

gate 5: parser contract
  python3 -c "from scrapers.market_config import parse_target_markets; ..."
  -> parser OK
```

Phase 1 test suites also re-checked:
- `python3 -m unittest scrapers.test_log_redaction` — 7 tests OK
- `python3 -m unittest scrapers.test_run_all_smoke` — 5 tests OK

## Must-Have Truths — Conformance

| # | Truth | Status |
| - | ----- | ------ |
| 1 | `scrapers/market_config.py` defines `APAC_V1_MARKETS = ['sg','hk','tw','my','th','ph','id','vn']` (8 codes) | OK |
| 2 | `parse_target_markets(env_value)` returns `['global']` for empty/unset; validates comma-separated lowercase codes; rejects unknowns by skipping with a log | OK |
| 3 | `scrapers/test_apify_social_market.py` is a stdlib `unittest` module covering empty, multi-market, whitespace, unknown-code, and case-normalisation cases | OK |
| 4 | Tests run green under `python3 -m unittest scrapers.test_apify_social_market -v` (no pytest dependency) | OK — 15 tests OK |
| 5 | `PRIORITY_MARKETS` in `scrapers/market_config.py` mirrors `APAC_V1_MARKETS` (8 codes; cn/mn out; ph in) | OK |

## Deviations from Plan

None — plan executed exactly as written. Auto-fix rules did not trigger.

The plan's allowed deviations were used in two places (both explicitly permitted under `<deviations_allowed>`):
- `subTest` blocks used for the case-and-whitespace variant (plan said "use subTest if it reads cleaner").
- Module-top `import logging` rather than function-local `import logging` (plan's example sketch inlined it; module-top is the project convention and the deviations_allowed section permitted docstring/style variation).

One small belt-and-braces test added beyond the listed behaviors:
- `test_only_unknown_codes_returns_global_fallback` — locks the `return out or ["global"]` safety branch so future refactors can't silently regress to returning `[]` when every token is invalid. Not a deviation from intent; just makes the existing safety guard explicit in the test surface.

## Authentication Gates

None — pure code change, no external service or secret involved.

## Known Stubs

None — all behavior described in the plan is wired and exercised by tests.

## Threat Surface Scan

No new security-relevant surface introduced. The parser:
- Reads only an env var the operator sets on EC2 `.env.local`.
- Does not issue network calls or DB writes.
- Drops unknown codes silently rather than raising, preventing an attacker-controlled env var (already a trusted operator surface) from crashing the scraper.

No `threat_flag:` entries to record.

## TDD Gate Compliance

Plan frontmatter is `type=execute` (not plan-level TDD). Task 2 carries `tdd="true"` but the helper under test was implemented in Task 1; the test commit (`b236793 test(02-02):`) lands after the feat commit (`9a45284 feat(02-02):`), so the test sequencing reflects "scaffold a new feature in Task 1 + lock its contract in Task 2" rather than RED→GREEN. This matches the Wave 0 scaffolding intent — the tests exist so plan 02-03's apify_social.py refactor (which will consume `parse_target_markets`) can be verified without burning Apify budget on integration tests.

## Phase 2 Carry-forward

- **Plan 02-03 (apify_social.py per-market loop):** will `from market_config import parse_target_markets` and call it with `os.environ.get("APIFY_MARKETS_ENABLED")`. The function name and signature are locked here.
- **Plan 02-03 will extend `scrapers/test_apify_social_market.py`** with mock-Apify integration tests for `_proxy_config(market_code)` and the per-market `social_snapshots` / `apify_run_logs` writes (per RESEARCH.md Wave 0 Gaps and Test Map).
- **Operator action item (still tracked in STATE.md, unchanged by this plan):** Apify Starter upgrade + setting `APIFY_MARKETS_ENABLED="sg,hk,tw,my,th,ph,id,vn"` on EC2 `.env.local`. Until both happen, the parser defaults to `["global"]` so the scraper stays on Phase 1's free-tier-safe behavior.

## Self-Check

- `scrapers/market_config.py` — FOUND
- `scrapers/test_apify_social_market.py` — FOUND
- commit `9a45284` — FOUND
- commit `b236793` — FOUND

## Self-Check: PASSED

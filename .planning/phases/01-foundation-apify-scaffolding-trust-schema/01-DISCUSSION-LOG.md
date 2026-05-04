# Phase 1: Foundation — Apify + Scaffolding + Trust Schema - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 1-foundation-apify-scaffolding-trust-schema
**Mode:** `--auto` (decisions auto-selected from research recommendations; user can amend before planning)
**Areas discussed:** Apify integration placement, Apify SDK choice, Apify call shape, Healthcheck provider, Run timeout enforcement, Log redaction strategy, Schema migration mechanism, Confidence column shape, Empty state component, Data Health page scope, Calibration set format, Apify spending cap location

---

## Apify integration placement

| Option | Description | Selected |
|--------|-------------|----------|
| New `scrapers/apify_social.py` | Sibling to existing `social_scraper.py`. YouTube path stays in `social_scraper.py`; FB/IG/X route to new file. | ✓ |
| Replace `_thunderbit_extract()` in-place | Modify the existing function to call Apify instead. Keeps everything in one file. | |
| Node.js entry-point with API route trigger | Move scraping to Node side; trigger Apify actors via webhook from a new API route. | |

**Auto-selection:** Recommended option per research/ARCHITECTURE.md. Sibling file isolates new dependency surface and clarifies which integration is authoritative for each platform; matches existing per-scraper file pattern.

---

## Apify SDK choice

| Option | Description | Selected |
|--------|-------------|----------|
| Python `apify-client` v2.5.0 | Stays in Python scraper layer. Single toolchain. | ✓ |
| Node.js `apify-client` | Would require a parallel Node-side scraping path. | |

**Auto-selection:** Recommended per STACK.md headline decision #1 (Python-only scraper layer). Adding Node scraping increases toolchain footprint for a maintenance-mode dashboard.

---

## Apify call shape

| Option | Description | Selected |
|--------|-------------|----------|
| Synchronous run-and-wait via `client.actor(...).call(...)` | Cron job invokes actor, blocks until complete, reads dataset. | ✓ |
| Asynchronous webhook callback | Actor pushes result to a new API endpoint when done. | |

**Auto-selection:** Recommended per ARCHITECTURE.md. Existing scrapers all run as cron jobs that block until completion. Webhooks add a new entry-point surface area for marginal gain.

---

## Healthcheck provider

| Option | Description | Selected |
|--------|-------------|----------|
| Healthchecks.io free tier | 20 checks free, missed-ping alarm built-in, single curl per cron job to ping. | ✓ |
| Self-hosted (e.g., Healthchecks open-source on EC2) | Full control, but adds an operational service to maintain. | |
| Cron `MAILTO=` | Native cron failure notifications via email. Email-only; no missed-ping detection. | |

**Auto-selection:** Recommended per PITFALLS.md and SUMMARY.md cross-cutting requirements. Free tier covers current scraper count with margin; self-hosted is overkill for solo support.

---

## Run timeout enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| `subprocess.run(..., timeout=1800)` in `run_all.py` | 30-min hard cap per scraper subprocess; orchestrator continues if one hangs. | ✓ |
| Python `signal.alarm()` inside each scraper | In-process timeout. Doesn't help if scraper is hung in C extension. | |
| External watchdog (systemd timer or cgroup) | OS-level enforcement; more robust but more deploy surface. | |

**Auto-selection:** Recommended per INFRA-02 and PITFALLS.md F5. `subprocess.run(timeout=...)` matches existing orchestrator pattern; minimal change scope.

---

## Log redaction strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Python logging Filter at root logger, redacts known env var values + token patterns | Single import in scraper entry-points; covers all child loggers. | ✓ |
| Manual redaction in each scraper | Brittle; easy to forget when adding new scrapers. | |
| Post-process logs after writing | Defense in depth but doesn't prevent secrets from briefly hitting disk. | |

**Auto-selection:** Recommended per INFRA-03. Filter-at-root pattern is standard Python; survives addition of new scrapers without changes to redaction logic.

---

## Schema migration mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Additive migrations in `scrapers/db_utils.py`; mirror in Drizzle `src/db/schema.ts` | Matches existing pattern. Auto-runs on startup. | ✓ |
| Drizzle Kit migration files | Cleaner Drizzle-side experience but duplicates the existing Python migration path. | |
| New migration framework (Alembic, etc.) | Avoid — existing Drizzle/db_utils pattern works. | |

**Auto-selection:** Recommended per ARCHITECTURE.md and INFRA-05. Additive-only matches PROJECT.md's "schema additions stay simple to keep future Postgres migration cheap."

---

## Confidence column shape

| Option | Description | Selected |
|--------|-------------|----------|
| `extraction_confidence TEXT` enum: `'high' \| 'medium' \| 'low' \| NULL` | Categorical, easy to read in SQL, consistent with research recommendation. | ✓ |
| Numeric score (0.0–1.0) | More granular but invites false-precision quibbling. | |
| JSON metadata column with multiple confidence dimensions | Future-flex but premature for v1. | |

**Auto-selection:** Recommended per FEATURES.md. Categorical three-bucket maps cleanly to GREEN/YELLOW/RED freshness pill in Phase 5.

---

## Empty state component placement and shape

| Option | Description | Selected |
|--------|-------------|----------|
| New `<EmptyState reason="scraper-failed">` in `src/components/ui/empty-state.tsx` | Generic component, used in Phase 1 for FB; reused by all per-market views in Phase 2+. | ✓ |
| Inline conditional in each consumer | Quick but copy-paste prone. | |

**Auto-selection:** Recommended. Reusability matters because Phase 2 fans this state across every social/promo panel.

---

## Data Health page scope (Phase 1 footprint)

| Option | Description | Selected |
|--------|-------------|----------|
| Skeleton: per-scraper status + last-run + 7-day zero-result count + Apify cost-to-date | Bare minimum that pays back operationally; Phase 5 polishes. | ✓ |
| Full polish in Phase 1 | Out of scope — Phase 5 covers this. | |
| Defer entirely to Phase 5 | Loses operational triage surface for Phases 2–4. | |

**Auto-selection:** Recommended per SUMMARY.md cross-cutting. Skeleton enables triage for the social cutover and BQ sync; polish without context risks misdesigned UX.

---

## Calibration set format and ownership

| Option | Description | Selected |
|--------|-------------|----------|
| JSONL at `scrapers/calibration/promo_extraction.jsonl`, hand-labeled by maintainer | Structured, version-controllable, validates with simple Python script. | ✓ |
| CSV with column headers | Less flexible for nested expected_output. | |
| External labeling tool (Labelbox, etc.) | Overkill for 20–30 items × 5 languages. | |
| Synthetic generation via LLM | Risks circular validation (LLM grading LLM output). | |

**Auto-selection:** Recommended. JSONL handles nested structure; in-repo placement keeps validation reproducible.

---

## Apify spending cap location

| Option | Description | Selected |
|--------|-------------|----------|
| Apify Console — set monthly cap to $100 before first scheduled run | The only place the cap is actually enforced by Apify. Documented in runbook + manual verification. | ✓ |
| Code-side cost ceiling check before each run | Defense in depth but won't stop a runaway run that's already started. | |

**Auto-selection:** Recommended. Apify enforces the cap server-side; code-side check is best-effort and doesn't prevent already-issued runs from completing.

---

## Claude's Discretion

- Specific actor version tag for `apify/facebook-posts-scraper` (planner picks latest stable).
- Specific competitor for the Phase 1 demo (planner picks from `scrapers/config.py` — verify FB page is active).
- Exact column types for new tables (planner follows existing `src/db/schema.ts` conventions).
- Apify run input parameters (`maxPosts`, `resultsLimit`) — planner picks defaults that fit cost cap with margin.

## Deferred Ideas

- Visualping / Wayback diff for promo page changes (out of scope this milestone).
- Slack/email alerting beyond Healthchecks.io free tier email (no requirement covers it in v1).
- Auto-rotating Apify actor versions when current pin reaches EOL (anti-feature for v1 — manual version tracking is the trust contract).
- Per-actor cost breakdown in Data Health page (Phase 5 polish, not Phase 1 skeleton).
- Calibration set automation via synthetic data generation (deferred — verification debt).

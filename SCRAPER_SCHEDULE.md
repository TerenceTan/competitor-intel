# Scraper Schedule

## Overview

9 scrapers run on independent schedules based on how frequently the underlying data changes.
All times are **UTC**. Run from the project root (`/home/ubuntu/app`).

**Cron entries route through `run_all.py <script>` (single-script mode)** so the
INFRA-02 timeout guard and INFRA-04 healthcheck ping (Plan 01-04) both fire,
keeping HC.io ping logic in one place. Direct `python scrapers/<script>.py`
invocations bypass the ping and are NOT recommended.

---

## Schedule by Scraper

| Scraper | Frequency | Cron | Rationale |
|---|---|---|---|
| `news_scraper.py` | Every 6 hours | `0 */6 * * *` | News is time-sensitive — competitor announcements and press can break at any time |
| `reputation_scraper.py` | Every 3 days at 7am | `0 7 */3 * *` | Reputation scores drift continuously — 3-day cadence reduces raw noise by ~66% while still catching meaningful movements within a week. Noise filtering (change_thresholds.py) handles micro-deltas between runs. |
| `ai_analyzer.py` | Daily at 8am | `0 8 * * *` | Run after reputation data is fresh; produces insights based on the latest snapshot |
| `promo_scraper.py` | Every 2 days at 8am | `0 8 */2 * *` | Promotions change with campaigns (flash offers, limited-time bonuses) but not daily |
| `pricing_scraper.py` | Weekly, Monday 6am | `0 6 * * 1` | Account types and min deposits are stable; spreads can shift but aren't tracked as a time-series |
| `account_types_scraper.py` | Weekly, Monday 6am | `0 6 * * 1` | Bundled with pricing — same cadence, same hot path (broker account-type pages) |
| `wikifx_scraper.py` | Weekly, Monday 6am | `0 6 * * 1` | WikiFX scores and account tables update infrequently; bundle with pricing run |
| `social_scraper.py` | Weekly, Monday 7am | `0 7 * * 1` | Subscriber/follower counts are slow-moving; weekly snapshots sufficient for trend analysis |
| `apify_social.py` | Weekly, Monday 7am | `0 7 * * 1` | Phase 1 — Apify FB cutover (Plan 01-03). Pay-per-event (~$0.30/run); weekly cadence keeps cost under D-06 $100/mo cap with margin for 8-market Phase 2 fanout |

---

## Crontab Setup

SSH into the server and run `crontab -e`, then add:

```cron
# ── Competitor Intelligence Scrapers ────────────────────────────────────────
# Working directory: /home/ubuntu/app
# Logs:              /home/ubuntu/app/logs/
# Python:            .venv/bin/python (Ubuntu 24.04 PEP-668 — system pip blocked)
# Pattern:           run_all.py <script.py> routes through INFRA-02 timeout +
#                    INFRA-04 HC.io ping; HEALTHCHECK_URL_<NAME> env vars must
#                    be present in .env.local for pings to fire.

TZ=UTC
APP=/home/ubuntu/app
PY=$APP/.venv/bin/python

# News — every 6 hours
0 */6 * * * cd $APP && $PY scrapers/run_all.py news_scraper.py >> logs/news_scraper.log 2>&1

# Reputation — every 3 days at 7am UTC
0 7 */3 * * cd $APP && $PY scrapers/run_all.py reputation_scraper.py >> logs/reputation_scraper.log 2>&1

# AI analysis — daily at 8am UTC (after reputation is done)
0 8 * * * cd $APP && $PY scrapers/run_all.py ai_analyzer.py >> logs/ai_analyzer.log 2>&1

# Promos — every 2 days at 8am UTC
0 8 */2 * * cd $APP && $PY scrapers/run_all.py promo_scraper.py >> logs/promo_scraper.log 2>&1

# Pricing + AccountTypes + WikiFX — weekly, Monday 6am UTC
0 6 * * 1 cd $APP && $PY scrapers/run_all.py pricing_scraper.py >> logs/pricing_scraper.log 2>&1
0 6 * * 1 cd $APP && $PY scrapers/run_all.py account_types_scraper.py >> logs/account_types_scraper.log 2>&1
0 6 * * 1 cd $APP && $PY scrapers/run_all.py wikifx_scraper.py >> logs/wikifx_scraper.log 2>&1

# Social (legacy IG/X/YT) + Apify FB — weekly, Monday 7am UTC (after pricing/wikifx)
0 7 * * 1 cd $APP && $PY scrapers/run_all.py social_scraper.py >> logs/social_scraper.log 2>&1
0 7 * * 1 cd $APP && $PY scrapers/run_all.py apify_social.py   >> logs/apify_social.log 2>&1
```

> **Note:** Logs append to the same file each run. To prevent unbounded growth, add a weekly logrotate rule or truncate logs periodically.

---

## Ad-hoc Full Refresh

To manually trigger all 9 scrapers in sequence (e.g. after a long outage or first-time setup):

```bash
cd /home/ubuntu/app && .venv/bin/python scrapers/run_all.py
```

To run a single scraper through the same hardening pipeline (timeout + HC.io ping):

```bash
cd /home/ubuntu/app && .venv/bin/python scrapers/run_all.py news_scraper.py
```

---

## Environment Requirements

All scrapers read secrets from `.env.local` in the project root via `python-dotenv`.
The following must be set:

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | `pricing_scraper.py`, `promo_scraper.py`, `ai_analyzer.py` |
| `YOUTUBE_API_KEY` | `social_scraper.py` |
| `SCRAPERAPI_KEY` | `reputation_scraper.py` (optional, falls back to direct requests) |
| `WEBSHARE_PROXY_URL` | `reputation_scraper.py` (optional proxy) |

---

## Estimated Run Times

| Scraper | Approx. duration |
|---|---|
| `news_scraper.py` | ~1 min |
| `reputation_scraper.py` | ~4–5 min |
| `ai_analyzer.py` | ~2–3 min |
| `promo_scraper.py` | ~3 min |
| `pricing_scraper.py` | ~5–8 min (multiple URLs per broker + Claude API calls) |
| `wikifx_scraper.py` | ~1.5 min |
| `social_scraper.py` | ~2.5 min |

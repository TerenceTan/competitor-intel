# Scraper Schedule

## Overview

7 scrapers run on independent schedules based on how frequently the underlying data changes.
All times are **UTC**. Run from the project root (`/home/ubuntu/app`).

---

## Schedule by Scraper

| Scraper | Frequency | Cron | Rationale |
|---|---|---|---|
| `news_scraper.py` | Every 6 hours | `0 */6 * * *` | News is time-sensitive — competitor announcements and press can break at any time |
| `reputation_scraper.py` | Every 3 days at 7am | `0 7 */3 * *` | Reputation scores drift continuously — 3-day cadence reduces raw noise by ~66% while still catching meaningful movements within a week. Noise filtering (change_thresholds.py) handles micro-deltas between runs. |
| `ai_analyzer.py` | Daily at 8am | `0 8 * * *` | Run after reputation data is fresh; produces insights based on the latest snapshot |
| `promo_scraper.py` | Every 2 days at 8am | `0 8 */2 * *` | Promotions change with campaigns (flash offers, limited-time bonuses) but not daily |
| `pricing_scraper.py` | Weekly, Monday 6am | `0 6 * * 1` | Account types and min deposits are stable; spreads can shift but aren't tracked as a time-series |
| `wikifx_scraper.py` | Weekly, Monday 6am | `0 6 * * 1` | WikiFX scores and account tables update infrequently; bundle with pricing run |
| `social_scraper.py` | Weekly, Monday 7am | `0 7 * * 1` | Subscriber/follower counts are slow-moving; weekly snapshots sufficient for trend analysis |

---

## Crontab Setup

SSH into the server and run `crontab -e`, then add:

```cron
# ── Competitor Intelligence Scrapers ────────────────────────────────────────
# Working directory: /home/ubuntu/app
# Logs: /home/ubuntu/app/logs/

# News — every 6 hours
0 */6 * * * cd /home/ubuntu/app && python scrapers/news_scraper.py >> logs/news_scraper.log 2>&1

# Reputation — every 3 days at 7am UTC
0 7 */3 * * cd /home/ubuntu/app && python scrapers/reputation_scraper.py >> logs/reputation_scraper.log 2>&1

# AI analysis — daily at 8am UTC (after reputation is done)
0 8 * * * cd /home/ubuntu/app && python scrapers/ai_analyzer.py >> logs/ai_analyzer.log 2>&1

# Promos — every 2 days at 8am UTC
0 8 */2 * * cd /home/ubuntu/app && python scrapers/promo_scraper.py >> logs/promo_scraper.log 2>&1

# Pricing + WikiFX — weekly, Monday 6am UTC
0 6 * * 1 cd /home/ubuntu/app && python scrapers/pricing_scraper.py >> logs/pricing_scraper.log 2>&1
0 6 * * 1 cd /home/ubuntu/app && python scrapers/wikifx_scraper.py >> logs/wikifx_scraper.log 2>&1

# Social — weekly, Monday 7am UTC (after pricing/wikifx)
0 7 * * 1 cd /home/ubuntu/app && python scrapers/social_scraper.py >> logs/social_scraper.log 2>&1
```

> **Note:** Logs append to the same file each run. To prevent unbounded growth, add a weekly logrotate rule or truncate logs periodically.

---

## Ad-hoc Full Refresh

To manually trigger all scrapers in sequence (e.g. after a long outage or first-time setup):

```bash
cd /home/ubuntu/app && python scrapers/run_all.py
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

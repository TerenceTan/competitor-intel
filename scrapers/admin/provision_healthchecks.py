"""One-shot operator script: provision Healthchecks.io checks for the 9 scrapers
in scrapers/run_all.py SCRIPTS, idempotently (re-runs are safe).

Usage:
    export HC_API_KEY=hcw_...                # read-write project API key
    python scrapers/admin/provision_healthchecks.py

Output (stdout): one HEALTHCHECK_URL_<NAME>=<ping_url> line per scraper.
Append the lines to /home/ubuntu/app/.env.local and run_all.py picks them up
on next invocation (no code change needed).

Schedules pulled from SCRAPER_SCHEDULE.md. apify_social and account_types_scraper
were not in SCRAPER_SCHEDULE.md when this was written — defaults match the closest
sibling (social_scraper for apify_social, pricing_scraper for account_types). Adjust
in HC.io UI if cron entries change.
"""
import os, json, sys
from urllib import request, error

API = "https://healthchecks.io/api/v3/checks/"
KEY = os.environ.get("HC_API_KEY", "").strip()
if not KEY:
    print("ERROR: HC_API_KEY not set", file=sys.stderr); sys.exit(1)

CHECKS = [
    ("NEWS_SCRAPER",          "news-scraper",          "0 */6 * * *",   3600,  "scraper news"),
    ("REPUTATION_SCRAPER",    "reputation-scraper",    "0 7 */3 * *",   86400, "scraper reputation"),
    ("AI_ANALYZER",           "ai-analyzer",           "0 8 * * *",     14400, "scraper ai"),
    ("PROMO_SCRAPER",         "promo-scraper",         "0 8 */2 * *",   43200, "scraper promo"),
    ("PRICING_SCRAPER",       "pricing-scraper",       "0 6 * * 1",     86400, "scraper pricing weekly"),
    ("WIKIFX_SCRAPER",        "wikifx-scraper",        "0 6 * * 1",     86400, "scraper wikifx weekly"),
    ("SOCIAL_SCRAPER",        "social-scraper",        "0 7 * * 1",     86400, "scraper social weekly"),
    ("APIFY_SOCIAL",          "apify-social",          "0 7 * * 1",     86400, "scraper social weekly apify"),
    ("ACCOUNT_TYPES_SCRAPER", "account-types-scraper", "0 6 * * 1",     86400, "scraper account-types weekly"),
]

def post(payload):
    req = request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={"X-Api-Key": KEY, "Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())

print("# === HC.io provisioning ===", file=sys.stderr)
ok = 0
for env_suffix, name, schedule, grace, tags in CHECKS:
    payload = {
        "name": name,
        "tags": tags,
        "schedule": schedule,
        "tz": "UTC",
        "grace": grace,
        "unique": ["name"],
    }
    try:
        status, data = post(payload)
        ping = data.get("ping_url") or "<no ping_url>"
        flag = "(new)" if status == 201 else "(existing)"
        print(f"HEALTHCHECK_URL_{env_suffix}={ping}")
        print(f"  -> {name:24s} {flag} schedule='{schedule}' grace={grace}s", file=sys.stderr)
        ok += 1
    except error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  !! {name}: HTTP {e.code}: {body}", file=sys.stderr)
    except Exception as e:
        print(f"  !! {name}: {type(e).__name__}: {e}", file=sys.stderr)
print(f"# {ok}/{len(CHECKS)} provisioned. Re-runs are idempotent.", file=sys.stderr)

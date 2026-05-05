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

CHECK_TZ = "Asia/Singapore"  # match crontab.txt TZ; was "UTC" pre-2026-05-05

def _api(method: str, url: str, payload: dict | None = None):
    req = request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"X-Api-Key": KEY, "Content-Type": "application/json"},
        method=method,
    )
    with request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode())


def upsert(payload: dict) -> tuple[int, dict]:
    """Create-or-update a check by name. POST with unique:['name'] either
    creates a new check (201) or returns an existing one (200) without
    modifying it. To change schedule/tz/grace on an existing check we have
    to follow up with a PUT to its update_url."""
    status, data = _api("POST", API, payload)
    update_url = data.get("update_url")
    if status == 200 and update_url:
        # existing check — push the new schedule/tz/grace via PUT
        put_payload = {k: v for k, v in payload.items() if k != "unique"}
        _api("POST", update_url, put_payload)  # HC.io accepts POST on update_url
    return status, data


print("# === HC.io provisioning ===", file=sys.stderr)
ok = 0
for env_suffix, name, schedule, grace, tags in CHECKS:
    payload = {
        "name": name,
        "tags": tags,
        "schedule": schedule,
        "tz": CHECK_TZ,
        "grace": grace,
        "unique": ["name"],
    }
    try:
        status, data = upsert(payload)
        ping = data.get("ping_url") or "<no ping_url>"
        flag = "(new)" if status == 201 else "(updated)"
        print(f"HEALTHCHECK_URL_{env_suffix}={ping}")
        print(f"  -> {name:24s} {flag} schedule='{schedule}' tz={CHECK_TZ} grace={grace}s", file=sys.stderr)
        ok += 1
    except error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  !! {name}: HTTP {e.code}: {body}", file=sys.stderr)
    except Exception as e:
        print(f"  !! {name}: {type(e).__name__}: {e}", file=sys.stderr)
print(f"# {ok}/{len(CHECKS)} provisioned. Re-runs are idempotent and update existing checks.", file=sys.stderr)

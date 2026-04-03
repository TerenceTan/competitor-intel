"""
reputation_scraper.py
---------------------
Scrapes Trustpilot, ForexPeaceArmy (FPA), Google Play, and App Store
ratings for every competitor entity and writes results to reputation_snapshots.

Supports multi-entity competitors (e.g. IC Markets Global vs EU) via the
`entities` list in config.py. Uses direct ID lookups where available to avoid
fuzzy-search mismatches.

Runs change detection for trustpilot_score, fpa_rating, ios_rating, android_rating.

Run from the project root:
    python scrapers/reputation_scraper.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

try:
    from curl_cffi import requests as curl_requests
    _CURL_AVAILABLE = True
except ImportError:
    _CURL_AVAILABLE = False
    print("WARNING: curl-cffi not installed. MyFXBook scraping will be skipped.")

# ---------------------------------------------------------------------------
# Path setup – allow running from project root or from scrapers/ directory
# ---------------------------------------------------------------------------
_SCRAPERS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

from config import DELAY_BETWEEN_REQUESTS, SCRAPER_UA
from db_utils import get_all_brokers
COMPETITORS = get_all_brokers()
from db_utils import get_db, log_scraper_run, update_scraper_run, detect_change

SCRAPER_NAME = "reputation_scraper"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _safe_text(page, selector: str, timeout: int = 5000) -> str | None:
    """Return inner text of first matching element, or None on failure."""
    try:
        el = await page.wait_for_selector(selector, timeout=timeout)
        if el:
            return (await el.inner_text()).strip()
    except Exception:
        pass
    return None


async def scrape_trustpilot(page, trustpilot_slug: str) -> tuple[float | None, int | None]:
    """
    Visit https://www.trustpilot.com/review/<trustpilot_slug> and extract
    TrustScore (float 1-5) and review count (int).
    Returns (score, count).
    """
    url = f"https://www.trustpilot.com/review/{trustpilot_slug}"
    score: float | None = None
    count: int | None = None

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        html = await page.content()

        # --- TrustScore ---
        sd_match = re.search(r'"aggregateRating"[^}]{0,200}?"ratingValue"\s*:\s*"?([\d.]+)"?', html, re.DOTALL)
        if not sd_match:
            sd_match = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
        if sd_match:
            score = float(sd_match.group(1))
        else:
            m = re.search(r'TrustScore[^<\d]{0,30}?([\d]\.[0-9])', html, re.IGNORECASE)
            if m:
                score = float(m.group(1))
            else:
                score_text = await _safe_text(page, '[data-rating-typography]', 3000)
                if score_text:
                    m = re.search(r'([\d.]+)', score_text)
                    if m:
                        score = float(m.group(1))

        # --- Review count ---
        rc_match = re.search(r'"reviewCount"\s*:\s*"?(\d[\d,]*)"?', html)
        if rc_match:
            count = int(rc_match.group(1).replace(",", ""))
        else:
            rc_text = re.search(r'([\d,]+)\s+review', html, re.IGNORECASE)
            if rc_text:
                count = int(rc_text.group(1).replace(",", ""))

    except PlaywrightTimeout:
        print(f"    [Trustpilot] Timeout for {trustpilot_slug}")
    except Exception as e:
        print(f"    [Trustpilot] Error for {trustpilot_slug}: {e}")

    return score, count


async def scrape_fpa(page, fpa_slug: str) -> float | None:
    """
    Visit ForexPeaceArmy review page using direct slug and extract rating.
    Returns float rating or None.
    """
    url = f"https://www.forexpeacearmy.com/forex-reviews/{fpa_slug}"
    rating: float | None = None

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        html = await page.content()

        sd_match = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
        if sd_match:
            rating = float(sd_match.group(1))
        else:
            rating_text = await _safe_text(page, '.rate-num', 3000)
            if not rating_text:
                rating_text = await _safe_text(page, '.rating-number', 3000)
            if rating_text:
                m = re.search(r'([\d.]+)', rating_text)
                if m:
                    rating = float(m.group(1))
            else:
                m = re.search(r'(?i)rating[^<]{0,50}?(\b[1-5](?:\.\d)?\b)', html)
                if m:
                    rating = float(m.group(1))

    except PlaywrightTimeout:
        print(f"    [FPA] Timeout for {fpa_slug}")
    except Exception as e:
        print(f"    [FPA] Error for {fpa_slug}: {e}")

    return rating


async def scrape_google_play_direct(page, android_package: str) -> float | None:
    """
    Fetch Google Play app page directly using the package ID.
    More reliable than name search.
    """
    url = f"https://play.google.com/store/apps/details?id={android_package}"
    rating: float | None = None

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        html = await page.content()

        # Try aria-label pattern: "Rated X.X stars out of 5"
        m = re.search(r'Rated ([\d.]+) stars out of 5', html)
        if m:
            rating = float(m.group(1))
        else:
            m = re.search(r'itemprop="ratingValue"[^>]*>([\d.]+)<', html)
            if m:
                rating = float(m.group(1))
            else:
                m = re.search(r'(?:rating|stars)[^<\d]{0,20}([1-5]\.[0-9])', html, re.IGNORECASE)
                if m:
                    rating = float(m.group(1))

    except PlaywrightTimeout:
        print(f"    [Google Play] Timeout for package {android_package}")
    except Exception as e:
        print(f"    [Google Play] Error for package {android_package}: {e}")

    return rating


async def scrape_google_play_search(page, broker_name: str) -> float | None:
    """
    Search Google Play for the broker trading app and return its rating.
    Fallback when no android_package is specified.
    """
    query = f"{broker_name} trading".replace(" ", "+")
    url = f"https://play.google.com/store/search?q={query}&c=apps"
    rating: float | None = None

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        html = await page.content()

        m = re.search(r'Rated ([\d.]+) stars out of 5', html)
        if m:
            rating = float(m.group(1))
        else:
            m = re.search(r'itemprop="ratingValue"[^>]*>([\d.]+)<', html)
            if m:
                rating = float(m.group(1))
            else:
                m = re.search(r'(?:rating|stars)[^<\d]{0,20}([1-5]\.[0-9])', html, re.IGNORECASE)
                if m:
                    rating = float(m.group(1))

    except PlaywrightTimeout:
        print(f"    [Google Play] Timeout searching for {broker_name}")
    except Exception as e:
        print(f"    [Google Play] Error searching for {broker_name}: {e}")

    return rating


def scrape_app_store_direct(ios_app_id: str) -> float | None:
    """
    Lookup App Store rating directly by app ID using iTunes lookup API.
    Tries multiple storefronts since many forex broker apps are only published
    in SEA markets (th, sg) rather than au.
    """
    for country in ["th", "sg", "gb", "us", "au"]:
        try:
            url = f"https://itunes.apple.com/lookup?id={ios_app_id}&country={country}"
            resp = requests.get(url, timeout=15, headers={"Accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results:
                r = results[0]
                avg = r.get("averageUserRating") or r.get("averageUserRatingForCurrentVersion")
                if avg:
                    return float(avg)
        except Exception as e:
            print(f"    [App Store] Error for app ID {ios_app_id} (country={country}): {e}")

    return None


def scrape_myfxbook_rating(myfxbook_slug: str) -> float | None:
    """
    Fetch MyFXBook broker page.
    Priority: SCRAPERAPI_KEY (trial/legacy) → WEBSHARE_PROXY_URL (free residential proxy) → curl-cffi (local dev).
    Returns float rating or None.
    """
    target_url = f"https://www.myfxbook.com/forex-brokers/{myfxbook_slug}"

    scraper_api_key = os.environ.get("SCRAPERAPI_KEY")
    webshare_proxy  = os.environ.get("WEBSHARE_PROXY_URL")

    if scraper_api_key:
        # Server path: route through ScraperAPI residential proxy (trial / legacy)
        url = (
            f"http://api.scraperapi.com"
            f"?api_key={scraper_api_key}"
            f"&url={target_url}"
            f"&render=false"
        )
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code != 200:
                print(f"    [MyFXBook] ScraperAPI HTTP {resp.status_code} for {myfxbook_slug}")
                return None
            html = resp.text
        except Exception as e:
            print(f"    [MyFXBook] ScraperAPI error for {myfxbook_slug}: {e}")
            return None

    elif webshare_proxy:
        # Server path: Webshare static residential proxy (free tier, 1 GB/mo)
        proxies = {"http": webshare_proxy, "https": webshare_proxy}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            resp = requests.get(target_url, proxies=proxies, headers=headers, timeout=30)
            if resp.status_code != 200:
                print(f"    [MyFXBook] Webshare HTTP {resp.status_code} for {myfxbook_slug}")
                return None
            html = resp.text
        except Exception as e:
            print(f"    [MyFXBook] Webshare error for {myfxbook_slug}: {e}")
            return None

    elif _CURL_AVAILABLE:
        # Local path: curl-cffi direct
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.myfxbook.com/",
        }
        try:
            resp = curl_requests.get(target_url, headers=headers, impersonate="chrome120", timeout=30)
            if resp.status_code != 200:
                print(f"    [MyFXBook] HTTP {resp.status_code} for {myfxbook_slug}")
                return None
            html = resp.text
        except Exception as e:
            print(f"    [MyFXBook] Error for {myfxbook_slug}: {e}")
            return None
    else:
        print("    [MyFXBook] No SCRAPERAPI_KEY / WEBSHARE_PROXY_URL and curl-cffi unavailable — skipping")
        return None

    try:
        if len(html) < 1000 or "access denied" in html.lower():
            print(f"    [MyFXBook] Blocked for {myfxbook_slug}")
            return None

        # Try JSON rating key variants
        for key in ("brokerRating", "rating", "ratingValue", "score"):
            m = re.search(rf'"{key}"\s*:\s*"?([\d.]+)"?', html)
            if m:
                val = float(m.group(1))
                if 0 < val <= 10:
                    return val

        # Fallback: number near rating/score text
        m = re.search(r'(?:rating|score)[^<\d]{0,30}?([\d]+(?:\.\d+)?)', html, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 0 < val <= 10:
                return val

    except Exception as e:
        print(f"    [MyFXBook] Error for {myfxbook_slug}: {e}")

    return None


def scrape_app_store_search(broker_name: str) -> float | None:
    """
    Query the iTunes Search API by name — fallback when no ios_app_id is set.
    """
    query = quote_plus(f"{broker_name} trading")
    url = f"https://itunes.apple.com/search?term={query}&entity=software&country=au&limit=5"
    rating: float | None = None

    try:
        resp = requests.get(url, timeout=15, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        broker_lower = broker_name.lower()
        for r in results:
            app_name = (r.get("trackName") or "").lower()
            if broker_lower not in app_name and not any(
                part in app_name for part in broker_lower.split()
            ):
                continue
            avg = r.get("averageUserRating") or r.get("averageUserRatingForCurrentVersion")
            if avg:
                rating = float(avg)
                break
        # Fallback: use first result with any rating
        if rating is None:
            for r in results:
                avg = r.get("averageUserRating") or r.get("averageUserRatingForCurrentVersion")
                if avg:
                    rating = float(avg)
                    break
    except Exception as e:
        print(f"    [App Store] Error searching for {broker_name}: {e}")

    return rating


# ---------------------------------------------------------------------------
# Per-entity scraping
# ---------------------------------------------------------------------------

async def scrape_entity(page, entity: dict, broker_name: str) -> dict:
    """
    Scrape all reputation sources for one entity. Returns a dict with all fields.
    """
    label = entity.get("label", broker_name)
    trustpilot_slug = entity.get("trustpilot_slug")
    fpa_slug = entity.get("fpa_slug")
    ios_app_id = entity.get("ios_app_id")
    android_package = entity.get("android_package")

    result = {
        "label": label,
        "trustpilot_score": None,
        "trustpilot_count": None,
        "fpa_rating": None,
        "ios_rating": None,
        "android_rating": None,
        "errors": [],
    }

    # --- Trustpilot ---
    if trustpilot_slug:
        try:
            tp_score, tp_count = await scrape_trustpilot(page, trustpilot_slug)
            result["trustpilot_score"] = tp_score
            result["trustpilot_count"] = tp_count
            print(f"      [{label}] Trustpilot: score={tp_score}, reviews={tp_count}")
        except Exception as e:
            msg = f"{label}/trustpilot: {e}"
            print(f"      [{label}] Trustpilot error: {e}")
            result["errors"].append(msg)
        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    # --- FPA ---
    if fpa_slug:
        try:
            result["fpa_rating"] = await scrape_fpa(page, fpa_slug)
            print(f"      [{label}] FPA: rating={result['fpa_rating']}")
        except Exception as e:
            msg = f"{label}/fpa: {e}"
            print(f"      [{label}] FPA error: {e}")
            result["errors"].append(msg)
        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    # --- Google Play ---
    try:
        if android_package:
            result["android_rating"] = await scrape_google_play_direct(page, android_package)
        else:
            result["android_rating"] = await scrape_google_play_search(page, broker_name)
        print(f"      [{label}] Google Play: rating={result['android_rating']}")
    except Exception as e:
        msg = f"{label}/google-play: {e}"
        print(f"      [{label}] Google Play error: {e}")
        result["errors"].append(msg)
    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    # --- App Store ---
    try:
        if ios_app_id:
            result["ios_rating"] = scrape_app_store_direct(ios_app_id)
        else:
            result["ios_rating"] = scrape_app_store_search(broker_name)
        print(f"      [{label}] App Store: rating={result['ios_rating']}")
    except Exception as e:
        msg = f"{label}/app-store: {e}"
        print(f"      [{label}] App Store error: {e}")
        result["errors"].append(msg)
    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    return result


# ---------------------------------------------------------------------------
# Main scrape routine
# ---------------------------------------------------------------------------

async def scrape_all():
    run_id = log_scraper_run(SCRAPER_NAME, "running")
    total_records = 0
    error_summary = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=SCRAPER_UA,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        # Block heavy resources to speed things up
        await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,mp4,webp}", lambda r: r.abort())

        conn = get_db()

        for competitor in COMPETITORS:
            cid = competitor["id"]
            name = competitor["name"]
            print(f"Processing {name}...")

            # Build entity list — fall back to single entity from website field
            entities = competitor.get("entities") or [
                {
                    "label": name,
                    "trustpilot_slug": competitor.get("website"),
                    "fpa_slug": competitor.get("website", "").replace(".", "-").split(".")[0],
                    "ios_app_id": None,
                    "android_package": None,
                }
            ]

            entity_results: list[dict] = []
            for entity in entities:
                try:
                    result = await scrape_entity(page, entity, name)
                    # Propagate per-source errors into the run error summary
                    for err in result.pop("errors", []):
                        error_summary.append(f"{name}/{err}")
                    entity_results.append(result)
                except Exception as e:
                    print(f"    [Entity {entity.get('label')}] Unhandled error: {e}")
                    error_summary.append(f"{name} entity={entity.get('label')}: {e}")

            # Determine primary entity: most Trustpilot reviews, or first
            primary = entity_results[0] if entity_results else {}
            for er in entity_results:
                tc = er.get("trustpilot_count") or 0
                ptc = primary.get("trustpilot_count") or 0
                if tc > ptc:
                    primary = er

            tp_score = primary.get("trustpilot_score")
            tp_count = primary.get("trustpilot_count")
            fpa_rating = primary.get("fpa_rating")
            ios_rating = primary.get("ios_rating")
            android_rating = primary.get("android_rating")

            entities_breakdown_json = json.dumps(entity_results) if len(entity_results) > 0 else None

            # --- MyFXBook rating ---
            myfxbook_rating: float | None = None
            myfxbook_slug = competitor.get("myfxbook_slug")
            if myfxbook_slug:
                try:
                    myfxbook_rating = scrape_myfxbook_rating(myfxbook_slug)
                    print(f"    [MyFXBook] {name}: rating={myfxbook_rating}")
                except Exception as e:
                    print(f"    [MyFXBook] Error for {name}: {e}")
                    error_summary.append(f"{name} myfxbook: {e}")
                time.sleep(DELAY_BETWEEN_REQUESTS)

            # Add myfxbook_rating to each entity in the breakdown
            if myfxbook_rating is not None and entity_results:
                for er in entity_results:
                    er["myfxbook_rating"] = myfxbook_rating
                entities_breakdown_json = json.dumps(entity_results)

            # --- Write to DB ---
            snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            try:
                conn.execute(
                    "DELETE FROM reputation_snapshots WHERE competitor_id=? AND snapshot_date=?",
                    (cid, snapshot_date),
                )
                conn.execute(
                    """
                    INSERT INTO reputation_snapshots
                        (competitor_id, snapshot_date, trustpilot_score, trustpilot_count,
                         fpa_rating, ios_rating, android_rating, entities_breakdown_json,
                         myfxbook_rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cid, snapshot_date, tp_score, tp_count, fpa_rating, ios_rating,
                     android_rating, entities_breakdown_json, myfxbook_rating),
                )
                conn.commit()
                total_records += 1

                # Change detection
                detect_change(conn, cid, "reputation", "trustpilot_score", tp_score, "medium")
                detect_change(conn, cid, "reputation", "fpa_rating", fpa_rating, "medium")
                detect_change(conn, cid, "reputation", "ios_rating", ios_rating, "low")
                detect_change(conn, cid, "reputation", "android_rating", android_rating, "low")
                detect_change(conn, cid, "reputation", "myfxbook_rating", myfxbook_rating, "medium")

            except Exception as e:
                print(f"    [DB] Error saving {name}: {e}")
                error_summary.append(f"{name} db: {e}")

        conn.close()
        await browser.close()

    status = "success" if not error_summary else "partial"
    error_msg = "; ".join(error_summary) if error_summary else None
    update_scraper_run(run_id, status, total_records, error_msg)
    print(f"\nDone. Records written: {total_records}. Status: {status}")
    if error_summary:
        print(f"Errors: {error_msg}")


if __name__ == "__main__":
    asyncio.run(scrape_all())

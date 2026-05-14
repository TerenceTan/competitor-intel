"""One-shot per-market presence validator for Phase 2.1 competitor list curation.

For a given market code, scores every competitor in `scrapers/config.py` on
"is this broker active in market X" using signals we already collect OR
can collect cheaply from a single page fetch per competitor.

Signals (each 0/1):
  S1. local_url     — broker has a per-market URL path (e.g., /sg/, /vn/)
                      OR hreflang tag pointing at the target market
                      OR ccTLD matching the market (.sg, .com.vn, etc.)
  S2. local_lang    — landing page contains non-trivial content in the
                      market's local language (only checked for non-EN
                      markets; EN markets get a free pass)
  S3. local_payment — funding/deposit content mentions a local payment
                      rail (PromptPay/TrueMoney for TH, MoMo/ZaloPay for VN,
                      DuitNow/FPX for MY, GoPay/OVO for ID, etc.)
  S4. app_store     — competitor has an iOS/Android app row in
                      `appStoreSnapshots` with `market_code = <market>`
  S5. wikifx_local  — competitor has a WikiFX entry with the market's
                      regulator listed (MAS/SC/SEC/etc.)

Confidence rule (combined with SERP):
  STRONG  = SERP STRONG OR (>=3 of {S1, S2, S3, S4, S5})
  medium  = SERP medium OR (>=2 signals) OR (>=1 STRONG signal + SERP medium)
  weak    = otherwise

Usage:
    cd /home/ubuntu/app
    source .venv/bin/activate
    python scrapers/admin/validate_market_presence.py sg
    python scrapers/admin/validate_market_presence.py vn

Cost: ~$0 (no Apify calls; pure HTTP fetches + DB reads + SERP CSV reuse).
Runtime: ~30s for 15 competitors × 1 fetch each.

Output: logs/market_presence_<market>.csv + markdown table.
"""
from __future__ import annotations

import csv
import os
import re
import sqlite3
import sys
from urllib.parse import urlparse

import requests

_SCRAPERS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
sys.path.insert(0, _SCRAPERS_DIR)

from config import COMPETITORS, DB_PATH  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# Market metadata
# ─────────────────────────────────────────────────────────────────────────
MARKET_META: dict[str, dict] = {
    "sg": {
        "name": "Singapore",
        "lang_code": "en",        # English-dominant; lang signal skipped
        "lang_skip": True,
        "regulator_tokens": ["mas", "monetary authority of singapore"],
        "payment_tokens": ["paynow", "fast", "giro"],
        "url_path_tokens": ["/sg/", "/en-sg/", "/singapore"],
        "cctlds": [".sg", ".com.sg"],
    },
    "vn": {
        "name": "Vietnam",
        "lang_code": "vi",
        "lang_skip": False,
        "lang_markers": ["sàn", "ngoại hối", "giao dịch", "tài khoản", "việt nam"],
        "regulator_tokens": ["ssc", "state securities commission of vietnam"],
        "payment_tokens": ["momo", "zalopay", "vietcombank", "techcombank", "internet banking", "atm"],
        "url_path_tokens": ["/vn/", "/vi/", "/vi-vn/", "/vietnam"],
        "cctlds": [".vn", ".com.vn"],
    },
    "hk": {
        "name": "Hong Kong",
        "lang_code": "en",
        "lang_skip": True,
        "regulator_tokens": ["sfc", "securities and futures commission"],
        "payment_tokens": ["fps", "faster payment system"],
        "url_path_tokens": ["/hk/", "/zh-hk/", "/en-hk/", "/hongkong"],
        "cctlds": [".hk", ".com.hk"],
    },
    "tw": {
        "name": "Taiwan",
        "lang_code": "zh-tw",
        "lang_skip": False,
        "lang_markers": ["外匯", "差價合約", "經紀商", "交易帳戶", "台灣"],
        "regulator_tokens": ["fsc", "financial supervisory commission"],
        "payment_tokens": ["atm 轉帳", "信用卡", "電匯"],
        "url_path_tokens": ["/tw/", "/zh-tw/", "/taiwan"],
        "cctlds": [".tw", ".com.tw"],
    },
    "my": {
        "name": "Malaysia",
        "lang_code": "en",
        "lang_skip": True,
        "regulator_tokens": ["sc malaysia", "securities commission malaysia", "labuan fsa"],
        "payment_tokens": ["duitnow", "fpx", "maybank", "cimb"],
        "url_path_tokens": ["/my/", "/en-my/", "/malaysia"],
        "cctlds": [".my", ".com.my"],
    },
    "th": {
        "name": "Thailand",
        "lang_code": "th",
        "lang_skip": False,
        "lang_markers": ["โบรกเกอร์", "ฟอเร็กซ์", "บัญชี", "ประเทศไทย"],
        "regulator_tokens": ["sec thailand", "securities and exchange commission thailand"],
        "payment_tokens": ["promptpay", "truemoney", "bangkok bank"],
        "url_path_tokens": ["/th/", "/thailand"],
        "cctlds": [".th", ".co.th"],
    },
    "ph": {
        "name": "Philippines",
        "lang_code": "en",
        "lang_skip": True,
        "regulator_tokens": ["sec philippines", "bsp", "bangko sentral"],
        "payment_tokens": ["gcash", "paymaya", "bdo", "instapay"],
        "url_path_tokens": ["/ph/", "/en-ph/", "/philippines"],
        "cctlds": [".ph", ".com.ph"],
    },
    "id": {
        "name": "Indonesia",
        "lang_code": "id",
        "lang_skip": False,
        "lang_markers": ["broker", "trading", "akun", "indonesia", "rekening"],
        "regulator_tokens": ["bappebti", "ojk"],
        "payment_tokens": ["gopay", "ovo", "dana", "bca", "mandiri"],
        "url_path_tokens": ["/id/", "/in-id/", "/indonesia"],
        "cctlds": [".id", ".co.id"],
    },
}


# ─────────────────────────────────────────────────────────────────────────
# Per-signal validators
# ─────────────────────────────────────────────────────────────────────────
def _fetch(url: str) -> tuple[str, str]:
    """Returns (final_url, body_lowercase). Empty on error.

    Two-attempt retry: some Cloudflare-fronted sites (xm.com observed) return
    broken gzip on the default Accept-Encoding header; second attempt forces
    identity encoding to bypass the decoder.
    """
    headers_common = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for attempt, accept_encoding in enumerate(("gzip, deflate", "identity"), 1):
        try:
            r = requests.get(
                url,
                timeout=10,
                headers={**headers_common, "Accept-Encoding": accept_encoding},
                allow_redirects=True,
            )
            return r.url, r.text.lower()
        except Exception as e:
            if attempt == 2:
                print(f"  [WARN] fetch failed (both attempts): {url}: {type(e).__name__}",
                      file=sys.stderr)
                return "", ""
            continue
    return "", ""


def _localized_url_candidates(website: str, market: str) -> list[str]:
    """Ordered URL candidates: localized ccTLD first, main website as fallback.

    For LiteFinance + VN: try https://www.litefinance.vn (where their actual
    VN content lives) before https://www.litefinance.com. For brokers without
    a regional variant, both URLs may fail with one being 404 — that's fine,
    we just take the first one that returns a body.
    """
    if not website:
        return []
    parts = website.lower().split(".")
    brand = parts[1] if parts and parts[0] == "www" else parts[0] if parts else website
    meta = MARKET_META.get(market, {})
    candidates: list[str] = []
    for tld in meta.get("cctlds", []):
        candidates.append(f"https://www.{brand}{tld}")
    candidates.append(website if website.startswith("http") else f"https://www.{website}")
    return candidates


def s1_local_url(final_url: str, body: str, market: str) -> bool:
    """True if URL path / hreflang / ccTLD signals market presence."""
    meta = MARKET_META[market]
    url_lower = final_url.lower()
    # ccTLD match (strong)
    parsed_host = urlparse(final_url).netloc.lower()
    if any(parsed_host.endswith(tld) for tld in meta["cctlds"]):
        return True
    # Per-market path
    if any(tok in url_lower for tok in meta["url_path_tokens"]):
        return True
    # hreflang tag pointing at the market (e.g. hreflang="en-SG")
    if re.search(rf'hreflang=["\']\w*-?{market}["\']', body, re.IGNORECASE):
        return True
    return False


def s2_local_lang(body: str, market: str) -> bool:
    """True if body contains local-language content. Skipped for EN markets."""
    meta = MARKET_META[market]
    if meta["lang_skip"]:
        return True  # EN market — give a free pass
    markers = meta.get("lang_markers", [])
    # Require >=2 markers to avoid false-positives from incidental loan-words
    hits = sum(1 for m in markers if m in body)
    return hits >= 2


def s3_local_payment(body: str, market: str) -> bool:
    meta = MARKET_META[market]
    return any(tok in body for tok in meta["payment_tokens"])


def s4_app_store(competitor_id: str, market: str) -> bool:
    """True if appStoreSnapshots has a row for this competitor in this market."""
    if not os.path.exists(DB_PATH):
        return False
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT 1 FROM app_store_snapshots WHERE competitor_id=? AND market_code=? LIMIT 1",
                (competitor_id, market),
            ).fetchone()
            return row is not None
    except sqlite3.OperationalError:
        return False  # table may not exist on dev DB


def s5_wikifx_local(competitor_id: str, market: str) -> bool:
    """True if WikiFX has a regulator entry matching this market's tokens."""
    if not os.path.exists(DB_PATH):
        return False
    meta = MARKET_META[market]
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT regulators_json FROM wikifx_snapshots "
                "WHERE competitor_id=? ORDER BY id DESC LIMIT 1",
                (competitor_id,),
            ).fetchone()
            if not row or not row[0]:
                return False
            blob = (row[0] or "").lower()
            return any(tok in blob for tok in meta["regulator_tokens"])
    except sqlite3.OperationalError:
        return False


# ─────────────────────────────────────────────────────────────────────────
# Score combiner
# ─────────────────────────────────────────────────────────────────────────
def _load_serp_csv(market: str) -> dict[str, dict]:
    """Read previously written logs/serp_research_<market>.csv if present."""
    path = os.path.join(_PROJECT_ROOT, "logs", f"serp_research_{market}.csv")
    if not os.path.exists(path):
        print(f"  [INFO] no SERP CSV at {path}; SERP confidence will be 'weak' for all", file=sys.stderr)
        return {}
    out: dict[str, dict] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            cid = row["competitor_id"]
            out[cid] = {
                "queries_appeared": int(row.get("queries_appeared") or 0),
                "best_rank": int(row["best_rank"]) if row.get("best_rank") else None,
            }
    return out


def _serp_confidence(serp: dict) -> str:
    if not serp:
        return "weak"
    if serp.get("queries_appeared", 0) >= 2 and (serp.get("best_rank") or 99) <= 10:
        return "STRONG"
    if serp.get("queries_appeared", 0) >= 1:
        return "medium"
    return "weak"


def _combined_confidence(serp_conf: str, signal_count: int) -> str:
    if serp_conf == "STRONG" or signal_count >= 3:
        return "STRONG"
    if serp_conf == "medium" or signal_count >= 2:
        return "medium"
    return "weak"


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scrapers/admin/validate_market_presence.py <market_code>", file=sys.stderr)
        return 1
    market = sys.argv[1].lower()
    if market not in MARKET_META:
        print(f"ERROR: unknown market '{market}'. Available: {list(MARKET_META)}", file=sys.stderr)
        return 1

    meta = MARKET_META[market]
    print(f"=== Market presence validation — {meta['name']} ({market}) ===")
    serp_data = _load_serp_csv(market)
    print(f"  SERP signal: loaded {len(serp_data)} competitor row(s) from previous run")

    rows: list[dict] = []
    for c in COMPETITORS:
        cid = c["id"]
        website = c.get("website") or ""
        if not website:
            continue
        # Try the localized ccTLD variant first (e.g., litefinance.vn for VN),
        # fall back to the main website. First URL with a non-empty body wins.
        final_url, body = "", ""
        for candidate in _localized_url_candidates(website, market):
            print(f"  fetching {cid:14s} {candidate}")
            final_url, body = _fetch(candidate)
            if body:
                break

        s1 = s1_local_url(final_url, body, market) if body else False
        s2 = s2_local_lang(body, market) if body else False
        s3 = s3_local_payment(body, market) if body else False
        s4 = s4_app_store(cid, market)
        s5 = s5_wikifx_local(cid, market)

        # In EN-dominant markets (SG/HK/MY/PH) S2 is a free pass for every
        # broker — drop it from the count so the >=3 STRONG threshold reflects
        # meaningful signal density. Non-EN markets keep all 5.
        if meta["lang_skip"]:
            signal_count = sum([s1, s3, s4, s5])
        else:
            signal_count = sum([s1, s2, s3, s4, s5])

        serp = serp_data.get(cid, {})
        serp_conf = _serp_confidence(serp)
        combined = _combined_confidence(serp_conf, signal_count)

        rows.append({
            "competitor_id": cid,
            "S1_local_url": int(s1),
            "S2_local_lang": int(s2),
            "S3_payment": int(s3),
            "S4_app_store": int(s4),
            "S5_wikifx": int(s5),
            "signal_count": signal_count,
            "serp_conf": serp_conf,
            "combined": combined,
        })

    # Sort: STRONG first, then by signal_count desc
    conf_order = {"STRONG": 0, "medium": 1, "weak": 2}
    rows.sort(key=lambda r: (conf_order[r["combined"]], -r["signal_count"]))

    print(f"\n=== Combined SERP + validation — {meta['name']} ({market}) ===")
    print(f"  S1 local_url | S2 local_lang | S3 payment | S4 app_store | S5 wikifx")
    print()
    print(f"| {'competitor':14s} | S1 | S2 | S3 | S4 | S5 | total | SERP   | COMBINED |")
    print(f"|{'-'*16}|----|----|----|----|----|-------|--------|----------|")
    for r in rows:
        print(f"| {r['competitor_id']:14s} | "
              f"{r['S1_local_url']:>2} | {r['S2_local_lang']:>2} | "
              f"{r['S3_payment']:>2} | {r['S4_app_store']:>2} | {r['S5_wikifx']:>2} | "
              f"{r['signal_count']:>5} | {r['serp_conf']:6s} | {r['combined']:8s} |")

    # CSV
    csv_path = os.path.join(_PROJECT_ROOT, "logs", f"market_presence_{market}.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w") as f:
        w = csv.DictWriter(f, fieldnames=[
            "competitor_id", "S1_local_url", "S2_local_lang",
            "S3_payment", "S4_app_store", "S5_wikifx",
            "signal_count", "serp_conf", "combined",
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nCSV: {csv_path}")
    print("\nRecommendation by COMBINED confidence:")
    strong = [r["competitor_id"] for r in rows if r["combined"] == "STRONG"]
    medium = [r["competitor_id"] for r in rows if r["combined"] == "medium"]
    weak = [r["competitor_id"] for r in rows if r["combined"] == "weak"]
    print(f"  → SHOW in /markets/{market}: {', '.join(strong + medium) or '(none)'}")
    print(f"  → HIDE (review with marketing team first): {', '.join(weak) or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

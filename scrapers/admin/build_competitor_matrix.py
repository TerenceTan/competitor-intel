"""Build the consolidated Phase 2.1 competitor × market review matrix.

Reads SERP and validator CSVs for all available markets, produces a single
Markdown document that the APAC marketing team uses to approve / override
the operator-driven SHOW/HIDE lists before they seed `competitor_markets`.

Usage:
    cd /home/ubuntu/app
    .venv/bin/python scrapers/admin/build_competitor_matrix.py

Inputs (auto-detected; missing markets show as "—" in the matrix):
    logs/serp_research_<market>.csv      from serp_market_research.py
    logs/market_presence_<market>.csv    from validate_market_presence.py

Output:
    logs/PHASE_2_1_COMPETITOR_MATRIX.md
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timezone

_SCRAPERS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_SCRAPERS_DIR)
sys.path.insert(0, _SCRAPERS_DIR)

from config import COMPETITORS  # noqa: E402

MARKETS = ["sg", "hk", "tw", "my", "th", "ph", "id", "vn"]
MARKET_NAMES = {
    "sg": "Singapore", "hk": "Hong Kong", "tw": "Taiwan",
    "my": "Malaysia", "th": "Thailand", "ph": "Philippines",
    "id": "Indonesia", "vn": "Vietnam",
}
LOGS_DIR = os.path.join(_PROJECT_ROOT, "logs")
OUT_PATH = os.path.join(LOGS_DIR, "PHASE_2_1_COMPETITOR_MATRIX.md")


def _read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def _load_market(market: str) -> dict[str, dict]:
    """Per-competitor dict for ONE market. Merges SERP + validator CSVs.

    Returns {competitor_id: {serp_conf, signal_count, combined,
                             S1..S5, queries_appeared, best_rank, own_brand_hits}}
    """
    out: dict[str, dict] = {}
    # SERP first
    for row in _read_csv(os.path.join(LOGS_DIR, f"serp_research_{market}.csv")):
        cid = row["competitor_id"]
        out[cid] = {
            "queries_appeared": int(row.get("queries_appeared") or 0),
            "best_rank": int(row["best_rank"]) if row.get("best_rank") else None,
            "avg_rank": float(row["avg_rank"]) if row.get("avg_rank") else None,
            "own_brand_hits": int(row.get("own_brand_hits") or 0),
        }
    # Validator (overrides / adds)
    for row in _read_csv(os.path.join(LOGS_DIR, f"market_presence_{market}.csv")):
        cid = row["competitor_id"]
        out.setdefault(cid, {})
        out[cid].update({
            "S1_local_url": int(row.get("S1_local_url") or 0),
            "S2_local_lang": int(row.get("S2_local_lang") or 0),
            "S3_payment": int(row.get("S3_payment") or 0),
            "S4_app_store": int(row.get("S4_app_store") or 0),
            "S5_wikifx": int(row.get("S5_wikifx") or 0),
            "signal_count": int(row.get("signal_count") or 0),
            "serp_conf": row.get("serp_conf") or "weak",
            "combined": row.get("combined") or "weak",
        })
    return out


def _conf_cell(entry: dict | None) -> str:
    if not entry:
        return "—"
    combined = entry.get("combined")
    if combined == "STRONG":
        return "**STRONG**"
    if combined == "medium":
        return "medium"
    return "weak"


def _thin_fetch_flag(entry: dict | None) -> bool:
    """True when the row looks like a fetch-failure false-negative:
    competitor has STRONG SERP visibility but zero validation signals
    (suggests we hit a JS-rendered shell or got blocked).
    """
    if not entry:
        return False
    return (
        entry.get("serp_conf") == "STRONG"
        and entry.get("signal_count", 0) == 0
    )


def render(matrix: dict[str, dict[str, dict]]) -> str:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append(f"# Phase 2.1 — Per-Market Competitor Review Matrix")
    lines.append("")
    lines.append(f"**Generated:** {now_iso}")
    lines.append(f"**Source:** `logs/serp_research_*.csv` + `logs/market_presence_*.csv`")
    lines.append(f"**For review by:** APAC marketing team")
    lines.append("")
    lines.append("## What you're approving")
    lines.append("")
    lines.append("Each cell shows the algorithm's confidence that the competitor is **active** in that market, derived from SERP visibility + 5-signal validator (local URL, language, payment, app store, WikiFX).")
    lines.append("")
    lines.append("- **STRONG** → seed `competitor_markets` with `status='active'` for this (broker, market)")
    lines.append("- **medium** → operator decides: active or skip")
    lines.append("- **weak** → default skip; override to `active` if marketing knows otherwise (e.g., word-of-mouth presence)")
    lines.append("- **⚠** → fetch returned thin content (likely JS-rendered shell); HIGH chance of false negative — review manually")
    lines.append("- **—** → market not yet researched")
    lines.append("")

    # ─── Main matrix ─────────────────────────────────────────────────────
    competitor_ids = [c["id"] for c in COMPETITORS]
    header = "| Competitor      | " + " | ".join(m.upper() for m in MARKETS) + " | Notes |"
    sep = "|-----------------|" + "|".join("--------" for _ in MARKETS) + "|-------|"
    lines.append("## Competitor × Market Matrix")
    lines.append("")
    lines.append(header)
    lines.append(sep)
    for cid in competitor_ids:
        cells = []
        for m in MARKETS:
            entry = matrix.get(m, {}).get(cid)
            cell = _conf_cell(entry)
            if _thin_fetch_flag(entry):
                cell += " ⚠"
            cells.append(cell)
        line = f"| {cid:15s} | " + " | ".join(f"{c:8s}" for c in cells) + " |       |"
        lines.append(line)
    lines.append("")

    # ─── Per-market sections ─────────────────────────────────────────────
    lines.append("## Per-Market Recommendations")
    lines.append("")
    for m in MARKETS:
        market_data = matrix.get(m, {})
        if not market_data:
            lines.append(f"### {MARKET_NAMES[m]} ({m})")
            lines.append("")
            lines.append("_(no CSVs found — run `serp_market_research.py` + `validate_market_presence.py` for this market)_")
            lines.append("")
            continue
        lines.append(f"### {MARKET_NAMES[m]} ({m})")
        lines.append("")

        strong = []
        medium = []
        weak = []
        thin = []
        for cid in competitor_ids:
            e = market_data.get(cid)
            if not e:
                continue
            combined = e.get("combined", "weak")
            if _thin_fetch_flag(e):
                thin.append(cid)
            if combined == "STRONG":
                strong.append(cid)
            elif combined == "medium":
                medium.append(cid)
            else:
                weak.append(cid)

        lines.append(f"**SHOW (active by default — {len(strong)}):**")
        for cid in strong:
            e = market_data[cid]
            why = []
            if e.get("serp_conf") == "STRONG":
                why.append(f"SERP={e.get('queries_appeared', 0)}q/r{e.get('best_rank', '?')}")
            sigs = [k.replace("_", "/") for k in ("S1_local_url", "S2_local_lang", "S3_payment", "S4_app_store", "S5_wikifx")
                    if e.get(k) == 1]
            if sigs:
                why.append("+".join(sigs))
            lines.append(f"- [ ] `{cid}` ({', '.join(why) or 'reason unclear'})")
        if not strong:
            lines.append("- _(none)_")
        lines.append("")

        lines.append(f"**Review case-by-case ({len(medium)}):**")
        for cid in medium:
            e = market_data[cid]
            lines.append(f"- [ ] `{cid}` — signals={e.get('signal_count', 0)}, SERP={e.get('serp_conf', 'weak')}")
        if not medium:
            lines.append("- _(none)_")
        lines.append("")

        lines.append(f"**HIDE by default ({len(weak)}):**")
        for cid in weak:
            lines.append(f"- [ ] `{cid}` (override only if marketing knows otherwise)")
        if not weak:
            lines.append("- _(none)_")
        lines.append("")

        if thin:
            lines.append("**⚠ Thin-content fetches (likely false negatives — verify manually):**")
            for cid in thin:
                lines.append(f"- `{cid}` — STRONG SERP but 0 validator signals; landing page may be JS-rendered")
            lines.append("")

        lines.append("")

    # ─── How to use ──────────────────────────────────────────────────────
    lines.append("## How marketing team should use this doc")
    lines.append("")
    lines.append("1. For each market section, check the boxes for competitors you confirm as **active**.")
    lines.append("2. For \"Review case-by-case\" entries, mark active or leave unchecked (= skip).")
    lines.append("3. For HIDE entries, only check if you have ground truth that says they ARE active.")
    lines.append("4. For ⚠ flagged competitors, do a manual check of their site for the market.")
    lines.append("5. Add notes in the Notes column of the matrix above where needed.")
    lines.append("")
    lines.append("Once reviewed, save this file (in place) and let engineering know — they'll parse the checkmarks into the `competitor_markets` table seed.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    matrix: dict[str, dict[str, dict]] = {}
    for m in MARKETS:
        matrix[m] = _load_market(m)
        n = len(matrix[m])
        print(f"  {m}: loaded {n} competitor row(s) ({'OK' if n else 'MISSING CSV — will show — in matrix'})")

    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(render(matrix))

    print(f"\n✓ Wrote {OUT_PATH}")
    print(f"  Markets covered: {sum(1 for m in MARKETS if matrix[m])}/{len(MARKETS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/bin/bash
# One-shot operator helper — runs SERP research + presence validator for
# all 8 APAC v1 markets back-to-back. Outputs land in logs/.
#
# Usage (from project root with venv active):
#   ./scrapers/admin/run_all_market_research.sh
#
# Wall clock: ~45 min (8 SERP runs sequential at ~4-5 min each + 8 validators
# at ~30s each). Apify cost: ~$0.15 total (~$0.02/market avg).
#
# Stops on first error. Continue with `--continue` to skip a failed market.

set -euo pipefail

MARKETS=(sg vn hk tw my th ph id)
PY=${PY:-.venv/bin/python}

mkdir -p logs/research_$(date +%Y%m%d)

echo "════════════════════════════════════════════════════════════"
echo " Phase 2.1 — all-market research run"
echo " Markets: ${MARKETS[*]}"
echo " Start: $(date -u +%FT%TZ)"
echo "════════════════════════════════════════════════════════════"

for market in "${MARKETS[@]}"; do
  echo
  echo "──── $market SERP ────"
  $PY scrapers/admin/serp_market_research.py "$market"
done

for market in "${MARKETS[@]}"; do
  echo
  echo "──── $market validator ────"
  $PY scrapers/admin/validate_market_presence.py "$market"
done

echo
echo "──── consolidated review matrix ────"
$PY scrapers/admin/build_competitor_matrix.py

echo
echo "════════════════════════════════════════════════════════════"
echo " DONE at $(date -u +%FT%TZ)"
echo " Outputs:"
ls -la logs/serp_research_*.csv logs/market_presence_*.csv 2>/dev/null || true
echo " Review doc:"
ls -la logs/PHASE_2_1_COMPETITOR_MATRIX.md 2>/dev/null || true
echo "════════════════════════════════════════════════════════════"

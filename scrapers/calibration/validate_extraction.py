"""
Validate the existing promo-extraction prompt against a hand-labeled JSONL set.

Phase 1 deliverable per D-19/D-20. Per D-21, NOT a Phase 1 blocker for the
Apify cutover — markets failing the >=85% accuracy bar are flagged for Phase 3
prompt iteration rather than failing the phase.

This is an offline calibration tool (NOT a cron scraper). It:
  1. Loads scrapers/calibration/promo_extraction.jsonl
  2. For each item, calls extract_promos_from_text() from promo_scraper.py
     (the SAME prompt used in production — single source of truth, never
     duplicated here, per RESEARCH.md A4)
  3. Compares actual extraction output to expected_output structurally
  4. Reports per-language accuracy
  5. Exits 0 if all languages >= 85%; exits 1 if any language fails;
     exits 2 on environmental error (missing file, broken import, etc.)

Usage:
    ANTHROPIC_API_KEY=sk-... python3 scrapers/calibration/validate_extraction.py
    python3 scrapers/calibration/validate_extraction.py --jsonl path/to/file.jsonl
    python3 scrapers/calibration/validate_extraction.py --language th

Threat model:
  - Validator output may include input_text snippets in MISS lines so the
    developer can see expected vs actual. Do NOT publish this output to
    public channels; it may contain competitor-confidential page content.
  - log_redaction is installed at module load (D-12) when available so any
    accidental secret in input_text is masked from log output.
  - One Claude call per JSONL line — calibration set is small (100-150 lines)
    and run on-demand by the maintainer, so cost is bounded (T-01-06-04).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

# Make scrapers/ importable so this file can run as a standalone script.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRAPERS_DIR = os.path.dirname(_HERE)
if _SCRAPERS_DIR not in sys.path:
    sys.path.insert(0, _SCRAPERS_DIR)

# Install log redaction first (D-12, T-01-06-02). The log_redaction module is
# delivered by Plan 01-02 (parallel wave-1 sibling). When the worktrees merge
# the import resolves; in this worktree (or any environment where Plan 02
# hasn't landed yet) we degrade gracefully and warn rather than crash, so
# static verification of this validator passes independently of Plan 02.
try:
    from log_redaction import install_redaction
    install_redaction()
except ImportError:
    # Plan 01-02 (scrapers/log_redaction.py) not yet merged into this tree.
    # Print to stderr so it's visible in CI but does not pollute stdout
    # (which is parsed by callers checking the per-language accuracy table).
    print(
        "WARNING: scrapers/log_redaction.py not available; running without "
        "redaction filter. This is expected in a wave-1 worktree before "
        "Plan 01-02 merges. Re-run after the merge for production use.",
        file=sys.stderr,
    )

# Import the existing prompt — single source of truth (RESEARCH.md A4).
# The pure function extract_promos_from_text was extracted from the async
# Playwright wrapper (extract_promos_with_claude) in Plan 01-06 so that the
# offline validator can call the production prompt without a browser. DO NOT
# duplicate the prompt in this file — if you find yourself wanting to, add
# a parameter to extract_promos_from_text instead.
#
# Caveat: scrapers/promo_scraper.py does a module-level DB call
# (COMPETITORS = get_all_brokers() at module load) which fails on machines
# where data/competitor-intel.db is not at the production path. Catching
# ImportError here is not enough — get_all_brokers() raises sqlite3.OperationalError
# at import time. We catch the broader Exception so a dev machine without the
# DB can still pass the static-import smoke test for this module; main() will
# surface a precise error and exit 2 if the symbol is actually unavailable
# when the validator runs against real calibration data.
_PROMO_IMPORT_ERROR: Exception | None = None
try:
    from promo_scraper import extract_promos_from_text, _get_anthropic_client
except Exception as e:  # noqa: BLE001 — sqlite3.OperationalError at module load
    extract_promos_from_text = None  # type: ignore[assignment]
    _get_anthropic_client = None  # type: ignore[assignment]
    _PROMO_IMPORT_ERROR = e

ACCURACY_BAR = 0.85  # 85% per D-20


def structural_match(actual, expected) -> bool:
    """Compare extracted output to expected, recursing through nested dicts/lists.

    Numbers are compared with type coercion (1 == 1.0). Strings are normalised
    (stripped + lowercased). For nested dicts the comparison is permissive:
    extra fields in `actual` that are not in `expected` do NOT fail the match
    — the prompt may legitimately extract more than the calibration set asserts.
    Lists must match in length and order.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(structural_match(actual.get(k), v) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        if len(expected) != len(actual):
            return False
        return all(structural_match(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(float(expected) - float(actual)) < 0.001
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    return expected == actual


def _match_any_extracted(extracted_promos: list, expected: dict) -> bool:
    """Return True if at least one promo in extracted_promos structurally
    matches `expected`. The production prompt returns a list of promos per
    page; the calibration row asserts the single expected promo for that
    snippet, so we accept a match against any item in the returned list.
    """
    if not isinstance(extracted_promos, list):
        return False
    return any(structural_match(item, expected) for item in extracted_promos)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate promo extraction accuracy per language."
    )
    parser.add_argument(
        "--jsonl",
        default=os.path.join(_HERE, "promo_extraction.jsonl"),
        help="Path to calibration JSONL file (default: alongside this script)",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Filter to one language (th/vn/tw/hk/id)",
    )
    parser.add_argument(
        "--include-examples",
        action="store_true",
        help="Include rows marked is_example=true (default: skip them; they "
             "are placeholders shipped before real calibration data lands)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.jsonl):
        print(f"FAIL: calibration file not found at {args.jsonl}")
        print("Run Plan 01-06 Task 1 (hand-label calibration data) first.")
        return 2

    # Surface a deferred import failure at run time (rather than at module
    # load time) so static-import smoke tests pass even on dev machines
    # without the production SQLite DB. See note above the import block.
    if _PROMO_IMPORT_ERROR is not None or extract_promos_from_text is None:
        print(
            f"FAIL: cannot import extract_promos_from_text from promo_scraper: "
            f"{_PROMO_IMPORT_ERROR!r}",
            file=sys.stderr,
        )
        print(
            "Confirm scrapers/promo_scraper.py exposes the pure-text extraction "
            "function (Plan 01-06 refactor) and that data/competitor-intel.db "
            "exists at the path resolved by scrapers/db_utils.py:DB_PATH.",
            file=sys.stderr,
        )
        return 2

    # Initialise Anthropic client once. extract_promos_from_text accepts None
    # and returns [] in that case — useful for static-import smoke tests, but
    # for a real validation run the API key must be set.
    client = _get_anthropic_client()
    if client is None:
        print(
            "FAIL: ANTHROPIC_API_KEY not set or anthropic package not installed.",
            file=sys.stderr,
        )
        print(
            "Set ANTHROPIC_API_KEY and `pip install anthropic` before running "
            "the validator against real calibration data.",
            file=sys.stderr,
        )
        return 2

    by_language: dict[str, list[bool]] = defaultdict(list)
    seen_lines = 0
    skipped_examples = 0
    skipped_comments = 0

    with open(args.jsonl, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  FAIL line {line_no}: invalid JSON ({e})")
                continue

            # Skip the file-level _comment row that documents the schema.
            if isinstance(item, dict) and "_comment" in item and "language" not in item:
                skipped_comments += 1
                continue

            # Skip example rows unless --include-examples was passed. Example
            # rows are the placeholders shipped in Plan 01-06 Task 1 before
            # the dashboard maintainer hand-labels real data.
            if item.get("is_example") and not args.include_examples:
                skipped_examples += 1
                continue

            if args.language and item.get("language") != args.language:
                continue

            seen_lines += 1
            try:
                extracted = extract_promos_from_text(
                    page_text=item["input_text"],
                    broker_name=item.get("market", "unknown"),
                    promo_url=item.get("source_url", ""),
                    client=client,
                )
            except Exception as e:
                print(f"  FAIL line {line_no} ({item.get('language')}): extraction error: {e}")
                by_language[item["language"]].append(False)
                continue

            ok = _match_any_extracted(extracted, item["expected_output"])
            by_language[item["language"]].append(ok)
            if not ok:
                # MISS line: include expected vs got. Per threat model T-01-06-02
                # this output is for the developer's eyes only — do not publish.
                print(
                    f"  MISS line {line_no} ({item['language']}): "
                    f"expected={item['expected_output']!r}, got={extracted!r}"
                )

    if seen_lines == 0:
        if skipped_examples > 0:
            print(
                f"FAIL: calibration file contains only example placeholder rows "
                f"({skipped_examples} skipped). Hand-label real data per "
                f"Plan 01-06 Task 1, or pass --include-examples to run against "
                f"the placeholders."
            )
        else:
            print("FAIL: calibration file is empty.")
        return 2

    print("\n=== Per-language accuracy ===")
    overall_pass = True
    for lang, results in sorted(by_language.items()):
        accuracy = sum(results) / len(results) if results else 0.0
        status = "PASS" if accuracy >= ACCURACY_BAR else "FAIL (flag for Phase 3)"
        print(
            f"  {lang}: {accuracy:.1%}  ({sum(results)}/{len(results)})  {status}"
        )
        if accuracy < ACCURACY_BAR:
            overall_pass = False

    print()
    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())

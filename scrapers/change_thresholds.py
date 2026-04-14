"""
Change detection thresholds — the noise floor for the change_events feed.

A change event should answer "would a human want to look at this?", not
"is this diff non-zero?". Without thresholds, every scrape registers
rounding noise — e.g. Trustpilot score drifting from 4.5602 to 4.5610 —
which floods the change feed, burns AI analysis budget, and buries the
real signals.

Thresholds are a plain Python dict (not a DB config table) on purpose:
tuning is a once-a-month activity for a single user, and a config UI is
YAGNI. If you need to tighten or loosen a floor, edit the THRESHOLDS dict
below and redeploy the scrapers.

Principle: caller-passed severity wins when higher than the
threshold-derived severity. That way, structural events like "new promo
added" — where the calling scraper already knows the event is high-impact
— are never downgraded by this module.
"""

import json
from typing import Any, Optional, Tuple

# (domain, field) -> {mode, min_delta, high_delta}
#
# mode:
#   "absolute" — delta measured as |new - old|
#   "percent"  — delta measured as |new - old| / |old|
#
# min_delta:  smallest delta that qualifies as a change_event row
# high_delta: delta that upgrades severity to "high" (0 = caller decides)
THRESHOLDS: dict[tuple[str, str], dict[str, Any]] = {
    # --- reputation (scores drift continuously with new reviews) ---
    ("reputation", "trustpilot_score"): {"mode": "absolute", "min_delta": 0.1, "high_delta": 0.3},
    ("reputation", "ios_rating"):       {"mode": "absolute", "min_delta": 0.1, "high_delta": 0.3},
    ("reputation", "android_rating"):   {"mode": "absolute", "min_delta": 0.1, "high_delta": 0.3},
    ("reputation", "fpa_rating"):       {"mode": "absolute", "min_delta": 0.1, "high_delta": 0.3},
    ("reputation", "myfxbook_rating"):  {"mode": "absolute", "min_delta": 0.1, "high_delta": 0.3},
    ("reputation", "trustpilot_count"): {"mode": "percent",  "min_delta": 0.05, "high_delta": 0.20},

    # --- social (naturally drifts with audience growth) ---
    ("social", "followers"):        {"mode": "percent",  "min_delta": 0.02,  "high_delta": 0.10},
    ("social", "posts_last_7d"):    {"mode": "absolute", "min_delta": 2,     "high_delta": 5},
    ("social", "engagement_rate"):  {"mode": "absolute", "min_delta": 0.005, "high_delta": 0.02},

    # --- pricing (small shifts can still matter, keep floors conservative) ---
    ("pricing", "min_deposit_usd"): {"mode": "absolute", "min_delta": 1,    "high_delta": 0},
    ("pricing", "spread_from"):     {"mode": "percent",  "min_delta": 0.05, "high_delta": 0},
}

# Domains where any change is worth registering regardless of numeric delta,
# because the field is structural/categorical — a new promo is a new promo.
CATEGORICAL_DOMAINS: set[str] = {"promo", "account_types"}

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# Float tolerance for threshold comparisons. Without this, values like
# 4.6 - 4.5 = 0.09999999999999964 would incorrectly fall under a 0.1 floor.
# The thresholds in this file are all rough guidance to 2 decimal places,
# so 1e-9 slack is well below any meaningful precision we care about.
_EPSILON = 1e-9


def should_register_change(
    domain: str,
    field: str,
    old_value: Any,
    new_value: Any,
    caller_severity: str,
) -> Tuple[bool, str]:
    """
    Decide whether a diff clears the noise floor.

    Returns (should_register, severity):
      - should_register=False  -> caller should skip the change_events insert
      - severity               -> the severity to store on the row. Caller's
                                  severity wins when it is strictly higher
                                  than the threshold-derived one.

    Behaviour:
      - Categorical domains (promo, account_types): always register, caller's severity
      - No configured threshold: register at caller's severity (safe default for
        fields we haven't tuned yet — noise filtering is additive, not a gate)
      - Non-numeric old or new value: treat as categorical, register
      - Numeric values: apply the threshold rule
    """
    if domain in CATEGORICAL_DOMAINS:
        return True, caller_severity

    key = (domain, field)
    if key not in THRESHOLDS:
        return True, caller_severity

    old_num = _to_number(old_value)
    new_num = _to_number(new_value)
    if old_num is None or new_num is None:
        # Non-numeric — can't apply a threshold, so fall back to register.
        return True, caller_severity

    rule = THRESHOLDS[key]
    delta = abs(new_num - old_num)

    if rule["mode"] == "percent":
        base = abs(old_num) if old_num != 0 else 1
        delta_metric = delta / base
    else:  # absolute
        delta_metric = delta

    if delta_metric < rule["min_delta"] - _EPSILON:
        return False, caller_severity  # below noise floor

    if rule["high_delta"] > 0 and delta_metric >= rule["high_delta"] - _EPSILON:
        derived = "high"
    else:
        derived = "medium"

    return True, _max_severity(caller_severity, derived)


def _max_severity(a: str, b: str) -> str:
    """Return whichever severity is higher (falls back to `a` on unknowns)."""
    return a if _SEVERITY_RANK.get(a, 0) >= _SEVERITY_RANK.get(b, 0) else b


def _to_number(value: Any) -> Optional[float]:
    """
    Best-effort coerce a stored value to a float. Returns None if non-numeric.

    Handles the three shapes detect_change() actually stores:
      - raw int/float
      - bare string (e.g. "4.56")
      - JSON-serialized number (e.g. json.dumps(4.56) -> "4.56")
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, (int, float)):
                return float(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            return float(stripped)
        except ValueError:
            return None
    return None

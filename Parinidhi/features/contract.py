"""
Feature Availability Contract for Issue-Time Safe Forecast-Bust Sentinel.

Formally defines the strict boundary between:
1. AVAILABLE_AT_ISSUE_TIME: Predictive features known before forecast valid time.
2. UNAVAILABLE_UNTIL_VERIFICATION: Ground truth and verification error targets.
"""

from typing import List, Set

AVAILABLE_AT_ISSUE_TIME: List[str] = [
    # Spatial & Geographical Metadata
    "latitude",
    "longitude",
    "elevation_m",
    "spatial_distance_km",

    # Temporal & Astronomical Coordinates
    "lead_hours",
    "lead_days",
    "cycle_sin",
    "cycle_cos",
    "day_of_year_sin",
    "day_of_year_cos",

    # Ensemble Dispersion & Physical Uncertainty
    "forecast_value",
    "ensemble_mean",
    "ensemble_std",
    "ensemble_min",
    "ensemble_max",
    "q10",
    "q90",
    "member_count",
    "has_full_ensemble",
    "ensemble_spread",
    "ensemble_iqr",
    "ensemble_range",
    "spread_to_mean_ratio",

    # Inter-Cycle Revisions & Dynamic Volatility
    "forecast_delta_6h",
    "forecast_delta_12h",
    "forecast_delta_24h",
    "abs_forecast_delta_6h",
    "abs_forecast_delta_12h",
    "abs_forecast_delta_24h",
]

UNAVAILABLE_UNTIL_VERIFICATION: List[str] = [
    "truth_value",
    "truth_unit",
    "truth_source",
    "forecast_error",
    "forecast_abs_error",
    "ensemble_mean_error",
    "ensemble_mean_abs_error",
    "bust_label",
    "target",
]


def validate_feature_contract(features: List[str]) -> List[str]:
    """
    Validate a list of candidate feature names against the availability contract.
    Returns list of violation error strings (empty if valid).
    """
    forbidden_set: Set[str] = set(UNAVAILABLE_UNTIL_VERIFICATION)
    violations: List[str] = []

    for f in features:
        f_clean = f.strip().lower()
        if f_clean in forbidden_set:
            violations.append(f"Forbidden verification column '{f}' cannot be used as an issue-time feature.")
        for term in ["truth", "error", "bust_label", "obs_", "reanalysis"]:
            if term in f_clean and "error" in f_clean:
                violations.append(f"Suspicious feature name '{f}' contains verification term '{term}'.")

    return violations

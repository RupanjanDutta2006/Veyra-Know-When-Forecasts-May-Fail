"""
Quality Control (QC) Layer for Weather Forecast Data.

Applies 7 explicit, deterministic validation rules:
1. Missing values (NaN / Null)
2. Duplicate records (same location, variable, issue_time, valid_time)
3. Invalid timestamps (valid_time < issue_time or lead_hours < 0)
4. Inconsistent physical units
5. Missing ensemble members (insufficient member count for statistical spread)
6. Stale data (issue_time older than allowed operational threshold)
7. Physically impossible / out-of-range atmospheric values

QC never silently invents or interpolates replacement values.
It produces explicit flag columns and an auditable diagnostic report.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


PHYSICAL_BOUNDS = {
    "temperature_2m": {"min": -60.0, "max": 60.0, "expected_unit": "degC"},
    "surface_pressure": {"min": 500.0, "max": 1100.0, "expected_unit": "hPa"},
    "wind_speed_10m": {"min": 0.0, "max": 300.0, "expected_unit": "km/h"},
}

MIN_EXPECTED_ENSEMBLE_MEMBERS = 10  # Flag if ensemble has fewer than 10 members


class QualityControl:
    """Performs modular QC validation on standardized forecast DataFrames."""

    def __init__(
        self,
        bounds: Optional[Dict[str, Dict[str, Any]]] = None,
        min_ensemble_members: int = MIN_EXPECTED_ENSEMBLE_MEMBERS,
        max_stale_hours: float = 72.0,
    ):
        self.bounds = bounds or PHYSICAL_BOUNDS
        self.min_ensemble_members = min_ensemble_members
        self.max_stale_hours = max_stale_hours

    def run_qc(
        self,
        df: pd.DataFrame,
        reference_time: Optional[datetime] = None,
    ) -> (pd.DataFrame, Dict[str, Any]):
        """
        Run all 7 QC checks on a standardized DataFrame.

        Args:
            df: Standardized forecast DataFrame.
            reference_time: Current evaluation time (UTC) for staleness check. Defaults to now.

        Returns:
            Tuple of (annotated_df_with_flags, qc_summary_report).
        """
        if df.empty:
            raise ValueError("Cannot run QC on an empty DataFrame.")

        df_qc = df.copy()
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)
        elif reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        # 1. Missing values check
        df_qc["qc_flag_missing_value"] = (
            df_qc["value"].isna()
            | df_qc["ensemble_mean"].isna()
            | df_qc["ensemble_std"].isna()
        )

        # 2. Duplicate rows check
        dup_cols = ["location", "variable", "issue_time", "valid_time"]
        df_qc["qc_flag_duplicate"] = df_qc.duplicated(subset=dup_cols, keep=False)

        # 3. Invalid timestamps check
        df_qc["qc_flag_invalid_timestamp"] = (
            (df_qc["valid_time"] < df_qc["issue_time"])
            | (df_qc["lead_hours"] < 0)
            | df_qc["issue_time"].isna()
            | df_qc["valid_time"].isna()
        )

        # 4. Inconsistent units check
        def check_unit(row):
            var = row["variable"]
            unit = row["unit"]
            if var in self.bounds:
                return unit != self.bounds[var]["expected_unit"]
            return False

        df_qc["qc_flag_unit_mismatch"] = df_qc.apply(check_unit, axis=1)

        # 5. Missing ensemble members check
        df_qc["qc_flag_missing_members"] = (
            df_qc["member_count"] < self.min_ensemble_members
        )

        # 6. Stale data check
        max_age = timedelta(hours=self.max_stale_hours)
        df_qc["qc_flag_stale_data"] = df_qc["issue_time"].apply(
            lambda t: (reference_time - t) > max_age if pd.notna(t) else True
        )

        # 7. Out-of-range values check
        def check_bounds(row):
            var = row["variable"]
            val = row["value"]
            if pd.isna(val) or var not in self.bounds:
                return False
            cfg = self.bounds[var]
            return (val < cfg["min"]) or (val > cfg["max"])

        df_qc["qc_flag_out_of_range"] = df_qc.apply(check_bounds, axis=1)

        # Composite pass flag: True if NO flags are raised
        flag_cols = [
            "qc_flag_missing_value",
            "qc_flag_duplicate",
            "qc_flag_invalid_timestamp",
            "qc_flag_unit_mismatch",
            "qc_flag_missing_members",
            "qc_flag_stale_data",
            "qc_flag_out_of_range",
        ]
        df_qc["qc_passed"] = ~df_qc[flag_cols].any(axis=1)

        # Build auditable QC summary report
        total_rows = len(df_qc)
        passed_rows = int(df_qc["qc_passed"].sum())
        failed_rows = total_rows - passed_rows

        rule_failures = {col.replace("qc_flag_", ""): int(df_qc[col].sum()) for col in flag_cols}

        report = {
            "qc_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "total_records": total_rows,
            "passed_records": passed_rows,
            "failed_records": failed_rows,
            "pass_rate_pct": round((passed_rows / total_rows) * 100.0, 2) if total_rows > 0 else 0.0,
            "rule_breakdown": rule_failures,
            "action_policy": {
                "missing_value": "FLAG and exclude from feature calculation; do not interpolate",
                "duplicate": "REJECT duplicate instances",
                "invalid_timestamp": "REJECT record; timing invariant violated",
                "unit_mismatch": "FLAG and quarantine; unit conversion required before use",
                "missing_members": "FLAG; spread estimation uncertainty is degraded",
                "stale_data": "FLAG; forecast cycle is outdated for real-time monitoring",
                "out_of_range": "REJECT; physically implausible atmospheric measurement",
            },
        }

        return df_qc, report

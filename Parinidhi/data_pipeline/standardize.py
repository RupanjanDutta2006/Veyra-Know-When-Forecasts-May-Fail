"""
Standardization Layer for Forecast Data.

Converts raw GEFS forecast JSON/arrays into the project's canonical schema.
Strictly preserves:
- location, latitude, longitude
- issue_time (explicitly verified from authoritative registry, NEVER guessed)
- valid_time (strictly >= issue_time for forecast predictions)
- lead_hours (lead_hours = valid_time - issue_time >= 0)
- variable, value, unit, source
- full ensemble distribution statistics (mean, std, min, max, q10, q90, member_count)
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


STANDARD_VARIABLE_MAP = {
    "temperature_2m": {
        "standard_name": "temperature_2m",
        "unit": "degC",
        "raw_prefix": "temperature_2m",
    },
    "surface_pressure": {
        "standard_name": "surface_pressure",
        "unit": "hPa",
        "raw_prefix": "surface_pressure",
    },
    "wind_speed_10m": {
        "standard_name": "wind_speed_10m",
        "unit": "km/h",
        "raw_prefix": "wind_speed_10m",
    },
}

REQUIRED_COLUMNS = [
    "location",
    "latitude",
    "longitude",
    "issue_time",
    "valid_time",
    "lead_hours",
    "variable",
    "value",
    "unit",
    "source",
    "member_id",
    "ensemble_mean",
    "ensemble_std",
    "ensemble_min",
    "ensemble_max",
    "q10",
    "q90",
    "member_count",
]


class GEFSStandardizer:
    """Standardizes raw GEFS forecast data into the project schema."""

    def __init__(self, processed_dir: str = "data/processed/gefs"):
        self.processed_dir = Path(processed_dir)

    def standardize(
        self,
        raw_data: Dict[str, Any],
        issue_time: Union[str, datetime, pd.Timestamp],
        location_name: str = "delhi",
        source_label: str = "NOAA_GEFS",
        filter_future_only: bool = True,
    ) -> pd.DataFrame:
        """
        Convert raw GEFS JSON response into standardized DataFrame.

        Args:
            raw_data: Raw JSON dict from GEFS collector.
            issue_time: EXPLICIT forecast run / cycle initialization time (UTC).
                        Implicit derivation from valid_times[0] is strictly forbidden.
            location_name: Location identifier.
            source_label: Name of source system.
            filter_future_only: If True, only keep forecast steps where valid_time >= issue_time (lead_hours >= 0).

        Returns:
            pd.DataFrame matching the project's standard schema.

        Raises:
            ValueError: If issue_time is missing or invalid.
        """
        if issue_time is None:
            raise ValueError(
                "Explicit issue_time must be provided. Implicit derivation from valid_times[0] is forbidden."
            )

        hourly = raw_data.get("hourly", {})
        if not hourly or "time" not in hourly:
            raise ValueError("Raw GEFS data does not contain required 'hourly.time' series.")

        times = hourly["time"]
        n_steps = len(times)
        if n_steps == 0:
            raise ValueError("Empty time series in GEFS payload.")

        # Parse valid times into UTC timestamps
        valid_times = pd.to_datetime(times, utc=True)

        # Parse explicit issue_time into UTC timestamp
        parsed_issue_time = pd.to_datetime(issue_time, utc=True)
        if pd.isna(parsed_issue_time):
            raise ValueError(f"Invalid issue_time provided: {issue_time}")

        # Calculate lead hours strictly relative to the explicit issue_time
        lead_hours = ((valid_times - parsed_issue_time).total_seconds() / 3600.0).round().astype(int)

        latitude = float(raw_data.get("latitude", 0.0))
        longitude = float(raw_data.get("longitude", 0.0))

        records: List[Dict[str, Any]] = []

        for var_key, var_cfg in STANDARD_VARIABLE_MAP.items():
            std_name = var_cfg["standard_name"]
            unit = var_cfg["unit"]
            prefix = var_cfg["raw_prefix"]

            # Identify all member columns for this variable (e.g. 31 members)
            member_cols = [k for k in hourly.keys() if k == prefix or k.startswith(f"{prefix}_member")]

            if not member_cols:
                continue

            # Build 2D array: shape (n_steps, n_members)
            member_matrix = []
            for col in member_cols:
                series = hourly[col]
                if len(series) == n_steps:
                    member_matrix.append(series)

            if not member_matrix:
                continue

            member_arr = np.array(member_matrix, dtype=float).T  # Shape: (n_steps, n_members)
            n_members = member_arr.shape[1]

            # Identify valid non-empty timesteps across all members
            valid_mask = ~np.isnan(member_arr).all(axis=1)
            if not valid_mask.any():
                continue

            # Compute ensemble distribution statistics across members
            ens_mean = np.full(n_steps, np.nan)
            ens_std = np.full(n_steps, np.nan)
            ens_min = np.full(n_steps, np.nan)
            ens_max = np.full(n_steps, np.nan)
            ens_q10 = np.full(n_steps, np.nan)
            ens_q90 = np.full(n_steps, np.nan)

            ens_mean[valid_mask] = np.nanmean(member_arr[valid_mask], axis=1)
            ens_std[valid_mask] = np.nanstd(member_arr[valid_mask], axis=1, ddof=1) if n_members > 1 else np.zeros(valid_mask.sum())
            ens_min[valid_mask] = np.nanmin(member_arr[valid_mask], axis=1)
            ens_max[valid_mask] = np.nanmax(member_arr[valid_mask], axis=1)
            ens_q10[valid_mask] = np.nanpercentile(member_arr[valid_mask], 10, axis=1)
            ens_q90[valid_mask] = np.nanpercentile(member_arr[valid_mask], 90, axis=1)

            control_values = hourly.get(prefix, ens_mean)

            for i in range(n_steps):
                current_lead = int(lead_hours[i])
                if filter_future_only and current_lead < 0:
                    continue  # Omit assimilation window before forecast initialization cycle

                # Skip unforecasted time steps beyond model operational horizon where all members are NaN
                if np.isnan(member_arr[i]).all():
                    continue

                records.append({
                    "location": location_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "issue_time": parsed_issue_time,
                    "valid_time": valid_times[i],
                    "lead_hours": current_lead,
                    "variable": std_name,
                    "value": float(control_values[i]) if control_values[i] is not None and not np.isnan(control_values[i]) else np.nan,
                    "unit": unit,
                    "source": source_label,
                    "member_id": "ensemble_summary",
                    "ensemble_mean": float(ens_mean[i]),
                    "ensemble_std": float(ens_std[i]),
                    "ensemble_min": float(ens_min[i]),
                    "ensemble_max": float(ens_max[i]),
                    "q10": float(ens_q10[i]),
                    "q90": float(ens_q90[i]),
                    "member_count": int(n_members),
                })

        df = pd.DataFrame(records)
        if df.empty:
            raise ValueError("No recognized variables could be standardized from GEFS payload.")

        # Reorder columns strictly to project schema
        df = df[REQUIRED_COLUMNS]
        return df

    def save_processed(
        self,
        df: pd.DataFrame,
        location_name: str = "delhi",
        timestamp_str: Optional[str] = None,
    ) -> Path:
        """Save standardized DataFrame to processed storage."""
        if timestamp_str is None:
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        dest_dir = self.processed_dir / location_name / date_str
        dest_dir.mkdir(parents=True, exist_ok=True)

        csv_path = dest_dir / f"gefs_standardized_{location_name}_{timestamp_str}.csv"
        parquet_path = dest_dir / f"gefs_standardized_{location_name}_{timestamp_str}.parquet"

        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, index=False)

        return parquet_path

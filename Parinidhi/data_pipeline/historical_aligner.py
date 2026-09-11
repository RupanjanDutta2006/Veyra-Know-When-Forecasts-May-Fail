"""
Historical Alignment & Forecast Error Engine.

Aligns standardized GEFS forecast predictions with ECMWF ERA5 reanalysis ground truth
by location, variable, and valid_time under an explicit spatial colocation policy.

Calculates:
- Signed forecast error: error = forecast_value - truth_value
- Absolute forecast error: abs_error = |forecast_value - truth_value|
- Ensemble mean signed error: ens_mean_error = ensemble_mean - truth_value
- Ensemble mean absolute error: ens_mean_abs_error = |ensemble_mean - truth_value|
- Spatial colocation distance (km)

Scientific Safeguard:
Truth observations and error metrics are strictly for verification, historical training,
and evaluation. They are never live forecast features.
"""

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


PAIRED_DATASET_COLUMNS = [
    "location",
    "latitude",
    "longitude",
    "issue_time",
    "valid_time",
    "lead_hours",
    "variable",
    "forecast_value",
    "forecast_unit",
    "forecast_source",
    "ensemble_mean",
    "ensemble_std",
    "ensemble_min",
    "ensemble_max",
    "q10",
    "q90",
    "member_count",
    "truth_value",
    "truth_unit",
    "truth_source",
    "forecast_error",
    "forecast_abs_error",
    "ensemble_mean_error",
    "ensemble_mean_abs_error",
    "spatial_distance_km",
]


VALID_CANONICAL_CYCLES = {"00z", "06z", "12z", "18z"}


def derive_canonical_cycle(
    issue_time: Union[str, datetime, pd.Timestamp, pd.Series],
    cycle: Optional[Union[str, pd.Series]] = None,
) -> Union[str, pd.Series]:
    """
    Derive, normalize, and validate the canonical forecast cycle ('00z', '06z', '12z', '18z').

    Rules:
    - If cycle is provided and non-null:
        - Normalize to lowercase, stripped string.
        - Validate that all values belong to {'00z', '06z', '12z', '18z'}.
        - If any value is invalid, raise ValueError with clear message.
    - If cycle is absent or null:
        - Derive strictly from issue_time in UTC: issue_time.hour -> f"{hour:02d}z".
        - Validate that derived cycle belongs to {'00z', '06z', '12z', '18z'}.
        - If non-synoptic hour, raise ValueError.
    """
    if isinstance(issue_time, pd.Series):
        issue_times_dt = pd.to_datetime(issue_time, utc=True)
        if cycle is not None and isinstance(cycle, pd.Series) and not cycle.isna().all():
            norm_cycle = cycle.astype(str).str.strip().str.lower()
            if cycle.isna().any():
                derived = issue_times_dt.dt.strftime("%Hz").str.lower()
                norm_cycle = norm_cycle.where(~cycle.isna(), derived)

            invalid = norm_cycle[~norm_cycle.isin(VALID_CANONICAL_CYCLES)]
            if len(invalid) > 0:
                raise ValueError(
                    f"Invalid forecast cycle values detected: {invalid.unique().tolist()}. "
                    f"Must be one of {sorted(VALID_CANONICAL_CYCLES)}."
                )
            return norm_cycle
        else:
            derived = issue_times_dt.dt.strftime("%Hz").str.lower()
            invalid = derived[~derived.isin(VALID_CANONICAL_CYCLES)]
            if len(invalid) > 0:
                raise ValueError(
                    f"Derived invalid forecast cycle values from issue_time: {invalid.unique().tolist()}. "
                    f"Must be one of {sorted(VALID_CANONICAL_CYCLES)}."
                )
            return derived
    else:
        if cycle is not None and not (isinstance(cycle, float) and np.isnan(cycle)) and str(cycle).strip() != "":
            norm = str(cycle).strip().lower()
            if norm not in VALID_CANONICAL_CYCLES:
                raise ValueError(
                    f"Invalid forecast cycle '{cycle}'. Must be one of {sorted(VALID_CANONICAL_CYCLES)}."
                )
            return norm
        else:
            dt = pd.to_datetime(issue_time, utc=True)
            derived = f"{dt.hour:02d}z"
            if derived not in VALID_CANONICAL_CYCLES:
                raise ValueError(
                    f"Derived cycle '{derived}' from issue time '{dt}' is not a valid synoptic cycle. "
                    f"Must be one of {sorted(VALID_CANONICAL_CYCLES)}."
                )
            return derived


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two coordinates in kilometers."""
    r = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 3)


def standardize_era5_reference(
    raw_era5: Dict[str, Any],
    location_name: str = "delhi",
    truth_source: str = "ERA5_REANALYSIS",
) -> pd.DataFrame:
    """
    Standardize raw ERA5 historical JSON into structured reference DataFrame.

    Args:
        raw_era5: Raw JSON from ERA5ReferenceCollector.
        location_name: Location identifier.
        truth_source: Identifier for truth source.

    Returns:
        pd.DataFrame with columns: ['location', 'latitude', 'longitude', 'valid_time', 'variable', 'truth_value', 'truth_unit', 'truth_source']
    """
    hourly = raw_era5.get("hourly", {})
    if not hourly or "time" not in hourly:
        raise ValueError("Raw ERA5 data does not contain required 'hourly.time' series.")

    times = hourly["time"]
    if not times:
        raise ValueError("Empty time series in ERA5 payload.")

    valid_times = pd.to_datetime(times, utc=True)
    latitude = float(raw_era5.get("latitude", 0.0))
    longitude = float(raw_era5.get("longitude", 0.0))

    var_mapping = {
        "temperature_2m": "degC",
        "surface_pressure": "hPa",
        "wind_speed_10m": "km/h",
    }

    records: List[Dict[str, Any]] = []

    for var_name, unit in var_mapping.items():
        if var_name not in hourly:
            continue

        values = hourly[var_name]
        for i in range(len(times)):
            val = values[i]
            records.append({
                "location": location_name,
                "latitude": latitude,
                "longitude": longitude,
                "valid_time": valid_times[i],
                "variable": var_name,
                "truth_value": float(val) if val is not None and not np.isnan(val) else np.nan,
                "truth_unit": unit,
                "truth_source": truth_source,
            })

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("No recognized variables could be standardized from ERA5 payload.")

    return df


class HistoricalAlignmentEngine:
    """Aligns forecast records with ground-truth verification reference and calculates error metrics."""

    def __init__(self, historical_dir: str = "data/historical"):
        self.historical_dir = Path(historical_dir)

    def align(
        self,
        forecast_df: pd.DataFrame,
        truth_df: pd.DataFrame,
        join_policy: str = "inner",
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Align forecast DataFrame and truth DataFrame on (location, variable, valid_time).

        Args:
            forecast_df: Standardized forecast DataFrame from GEFSStandardizer.
            truth_df: Standardized reference DataFrame from standardize_era5_reference.
            join_policy: Join method ('inner' to only retain fully matched valid times).

        Returns:
            Tuple of (paired_historical_df, alignment_metrics_report).
        """
        if forecast_df.empty or truth_df.empty:
            raise ValueError("Cannot perform alignment on empty forecast or truth DataFrames.")

        f_df = forecast_df.copy()
        t_df = truth_df.copy()

        # Ensure valid_time is timezone-aware UTC datetime
        f_df["valid_time"] = pd.to_datetime(f_df["valid_time"], utc=True)
        t_df["valid_time"] = pd.to_datetime(t_df["valid_time"], utc=True)

        # Prepare forecast columns
        if "value" in f_df.columns and "forecast_value" not in f_df.columns:
            f_df = f_df.rename(columns={"value": "forecast_value", "unit": "forecast_unit", "source": "forecast_source"})

        # Record counts before merge
        total_forecast_rows = len(f_df)
        total_truth_rows = len(t_df)

        # Merge on location, variable, valid_time
        join_keys = ["location", "variable", "valid_time"]
        merged = pd.merge(
            f_df,
            t_df[["location", "variable", "valid_time", "latitude", "longitude", "truth_value", "truth_unit", "truth_source"]],
            on=join_keys,
            how=join_policy,
            suffixes=("", "_truth"),
        )

        if merged.empty:
            raise ValueError("No temporal overlap found between forecast and truth datasets.")

        # Spatial distance between forecast grid point and truth grid point
        merged["spatial_distance_km"] = merged.apply(
            lambda r: haversine_distance_km(r["latitude"], r["longitude"], r["latitude_truth"], r["longitude_truth"]),
            axis=1,
        )

        # Drop temporary truth coordinate column
        if "latitude_truth" in merged.columns:
            merged = merged.drop(columns=["latitude_truth", "longitude_truth"])

        # Calculate forecast errors
        # e = y_hat - y_truth (positive = overprediction, negative = underprediction)
        merged["forecast_error"] = merged["forecast_value"] - merged["truth_value"]
        merged["forecast_abs_error"] = merged["forecast_error"].abs()

        # Ensemble mean errors
        merged["ensemble_mean_error"] = merged["ensemble_mean"] - merged["truth_value"]
        merged["ensemble_mean_abs_error"] = merged["ensemble_mean_error"].abs()

        # Enforce exact column schema
        paired_df = merged[PAIRED_DATASET_COLUMNS].copy()

        # Build diagnostic alignment report
        matched_rows = len(paired_df)
        unmatched_forecast = total_forecast_rows - matched_rows
        unmatched_truth = total_truth_rows - matched_rows

        # Calculate summary error metrics per variable
        metrics_by_var = {}
        for var, group in paired_df.groupby("variable"):
            valid_errors = group["forecast_error"].dropna()
            valid_abs = group["forecast_abs_error"].dropna()
            metrics_by_var[var] = {
                "matched_records": len(group),
                "mean_error_bias": round(float(valid_errors.mean()), 3) if len(valid_errors) > 0 else 0.0,
                "mae": round(float(valid_abs.mean()), 3) if len(valid_abs) > 0 else 0.0,
                "rmse": round(float(np.sqrt((valid_errors ** 2).mean())), 3) if len(valid_errors) > 0 else 0.0,
                "ensemble_mae": round(float(group["ensemble_mean_abs_error"].dropna().mean()), 3) if len(group) > 0 else 0.0,
            }

        report = {
            "alignment_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "total_forecast_records": total_forecast_rows,
            "total_truth_records": total_truth_rows,
            "matched_paired_records": matched_rows,
            "unmatched_forecast_records": unmatched_forecast,
            "unmatched_truth_records": unmatched_truth,
            "match_rate_pct": round((matched_rows / total_forecast_rows) * 100.0, 2) if total_forecast_rows > 0 else 0.0,
            "mean_spatial_distance_km": round(float(paired_df["spatial_distance_km"].mean()), 3),
            "variable_error_metrics": metrics_by_var,
        }

        return paired_df, report

    def save_paired_dataset(
        self,
        paired_df: pd.DataFrame,
        report: Dict[str, Any],
        location_name: str = "delhi",
        timestamp_str: Optional[str] = None,
    ) -> Tuple[Path, Path, Path]:
        """Save paired historical dataset and alignment manifest to data/historical."""
        if timestamp_str is None:
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        dest_dir = self.historical_dir / location_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        parquet_path = dest_dir / f"paired_historical_{location_name}_{timestamp_str}.parquet"
        csv_path = dest_dir / f"paired_historical_{location_name}_{timestamp_str}.csv"
        manifest_path = dest_dir / f"paired_historical_{location_name}_{timestamp_str}_manifest.json"

        paired_df.to_parquet(parquet_path, index=False)
        paired_df.to_csv(csv_path, index=False)

        manifest = {
            "dataset_name": f"Paired Historical Forecast-Verification Dataset ({location_name})",
            "generation_time_utc": datetime.now(timezone.utc).isoformat(),
            "location_name": location_name,
            "total_records": len(paired_df),
            "parquet_file_path": str(parquet_path),
            "csv_file_path": str(csv_path),
            "alignment_summary": report,
        }

        import json
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return parquet_path, csv_path, manifest_path


# ===========================================================================
# Canonical Multi-Climate Historical Dataset Schema & Builder (Phase 2 Day 9)
# ===========================================================================

CANONICAL_HISTORICAL_COLUMNS = [
    # Spatial & Climate Metadata (Context & Evaluation Stratification)
    "location_id",
    "region",
    "climate_zone",
    "meteorological_regime",
    "elevation_m",
    "latitude",
    "longitude",
    "spatial_distance_km",

    # Temporal & Cycle Coordinates
    "issue_time_utc",
    "valid_time_utc",
    "lead_hours",
    "lead_days",
    "cycle",
    "variable",

    # Forecast & Ensemble Statistics (Issue-Time Safe Features)
    "forecast_value",
    "forecast_unit",
    "forecast_source",
    "ensemble_mean",
    "ensemble_std",
    "ensemble_min",
    "ensemble_max",
    "q10",
    "q90",
    "member_count",
    "has_full_ensemble",

    # Ground Truth & Verification (TARGET ONLY - Strictly Forbidden in Feature Generation)
    "truth_value",
    "truth_unit",
    "truth_source",
    "forecast_error",
    "forecast_abs_error",
    "ensemble_mean_error",
    "ensemble_mean_abs_error",
]

CANONICAL_FEATURE_COLUMNS = [
    "location_id", "region", "climate_zone", "meteorological_regime", "elevation_m",
    "latitude", "longitude", "spatial_distance_km",
    "issue_time_utc", "valid_time_utc", "lead_hours", "lead_days", "cycle", "variable",
    "forecast_value", "forecast_unit", "forecast_source",
    "ensemble_mean", "ensemble_std", "ensemble_min", "ensemble_max",
    "q10", "q90", "member_count", "has_full_ensemble",
]

CANONICAL_TARGET_COLUMNS = [
    "truth_value", "truth_unit", "truth_source",
    "forecast_error", "forecast_abs_error",
    "ensemble_mean_error", "ensemble_mean_abs_error",
]


class MultiClimateDatasetBuilder:
    """
    Assembles, validates, and preserves reproducible multi-location, multi-climate historical datasets.

    Enforces:
    1. Rich climate regime annotations from LocationRegistry without breaking spatial consistency.
    2. Strict temporal ordering (valid_time >= issue_time, lead_hours >= 0).
    3. Multi-cycle preservation (00z, 06z, 12z, 18z distinct issue times).
    4. Deterministic QC validation (physical bounds, member completeness, coordinates, duplicate checks).
    5. Anti-leakage segregation of target verification fields.
    """

    DEFAULT_MAX_SPATIAL_DISTANCE_KM = 50.0

    def __init__(
        self,
        historical_dir: str = "data/historical",
        location_registry: Optional[Any] = None,
        max_spatial_distance_km: float = DEFAULT_MAX_SPATIAL_DISTANCE_KM,
    ):
        self.historical_dir = Path(historical_dir)
        if location_registry is None:
            from api.location_service import LocationRegistry
            self.location_registry = LocationRegistry()
        else:
            self.location_registry = location_registry
        self.max_spatial_distance_km = max_spatial_distance_km

    def standardize_paired_slice(
        self,
        df_paired: pd.DataFrame,
        location_id: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Normalize a single-station paired dataset into the canonical multi-climate schema.

        Args:
            df_paired: DataFrame with paired forecast and truth records.
            location_id: Optional location ID override.

        Returns:
            pd.DataFrame matching CANONICAL_HISTORICAL_COLUMNS.
        """
        if df_paired.empty:
            raise ValueError("Input paired DataFrame is empty.")

        df = df_paired.copy()

        # Handle column naming variations between Day 2 pilot and Day 9 canonical
        if "location" in df.columns and "location_id" not in df.columns:
            df["location_id"] = df["location"]
        if location_id is not None:
            df["location_id"] = location_id

        if "issue_time" in df.columns and "issue_time_utc" not in df.columns:
            df["issue_time_utc"] = pd.to_datetime(df["issue_time"], utc=True)
        else:
            df["issue_time_utc"] = pd.to_datetime(df["issue_time_utc"], utc=True)

        if "valid_time" in df.columns and "valid_time_utc" not in df.columns:
            df["valid_time_utc"] = pd.to_datetime(df["valid_time"], utc=True)
        else:
            df["valid_time_utc"] = pd.to_datetime(df["valid_time_utc"], utc=True)

        if "lead_hours" not in df.columns:
            df["lead_hours"] = ((df["valid_time_utc"] - df["issue_time_utc"]).dt.total_seconds() / 3600.0).round().astype(int)

        if "lead_days" not in df.columns:
            df["lead_days"] = df["lead_hours"] // 24

        if "cycle" in df.columns and not df["cycle"].isna().all():
            df["cycle"] = derive_canonical_cycle(df["issue_time_utc"], df["cycle"])
        else:
            df["cycle"] = derive_canonical_cycle(df["issue_time_utc"])

        if "has_full_ensemble" not in df.columns:
            # Reforecast has 5 members on normal days and 11 on the weekly
            # extended runs. Operational GEFS/Open-Meteo may expose 30
            # perturbation fields (control availability is provider-specific).
            source_text = df.get("forecast_source", pd.Series("", index=df.index)).astype(str).str.lower()
            expected = np.where(source_text.str.contains("reforecast"), 5, 30)
            df["has_full_ensemble"] = df["member_count"].fillna(0).astype(float) >= expected

        # Populate climate & geographical metadata from LocationRegistry
        loc_keys = df["location_id"].unique()
        loc_meta_map = {}
        for loc in loc_keys:
            if self.location_registry.has_location(loc):
                info = self.location_registry.get_location(loc)
                loc_meta_map[loc] = {
                    "region": info.state_region,
                    "climate_zone": info.climate_zone or "UNKNOWN",
                    "meteorological_regime": info.meteorological_regime or "UNKNOWN",
                    "elevation_m": info.elevation_m if info.elevation_m is not None else np.nan,
                }
            else:
                # Check if the slice dataframe itself provided region / climate_zone / elevation_m
                sub_loc = df[df["location_id"] == loc]
                provided_reg = sub_loc["region"].dropna().iloc[0] if "region" in sub_loc.columns and not sub_loc["region"].dropna().empty else "Custom Region"
                provided_cz = sub_loc["climate_zone"].dropna().iloc[0] if "climate_zone" in sub_loc.columns and not sub_loc["climate_zone"].dropna().empty else "CUSTOM"
                provided_met = sub_loc["meteorological_regime"].dropna().iloc[0] if "meteorological_regime" in sub_loc.columns and not sub_loc["meteorological_regime"].dropna().empty else "Custom Operational Location"
                provided_elev = float(sub_loc["elevation_m"].dropna().iloc[0]) if "elevation_m" in sub_loc.columns and not sub_loc["elevation_m"].dropna().empty else np.nan

                # Dynamically register in location registry if latitude and longitude exist
                if "latitude" in sub_loc.columns and "longitude" in sub_loc.columns:
                    lat_val = float(sub_loc["latitude"].iloc[0])
                    lon_val = float(sub_loc["longitude"].iloc[0])
                    self.location_registry.register_location(
                        location_id=str(loc),
                        requested_latitude=lat_val,
                        requested_longitude=lon_val,
                        state_region=provided_reg,
                        city=str(loc).capitalize(),
                        climate_zone=provided_cz,
                        meteorological_regime=provided_met,
                        elevation_m=provided_elev,
                        is_benchmark=False,
                        rationale="Dynamically registered operational location during historical ingestion.",
                    )

                loc_meta_map[loc] = {
                    "region": provided_reg,
                    "climate_zone": provided_cz,
                    "meteorological_regime": provided_met,
                    "elevation_m": provided_elev,
                }

        if "region" not in df.columns or df["region"].isna().all():
            df["region"] = df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("region", "UNKNOWN"))
        else:
            df["region"] = df["region"].fillna(df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("region", "UNKNOWN")))

        if "climate_zone" not in df.columns or df["climate_zone"].isna().all():
            df["climate_zone"] = df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("climate_zone", "UNKNOWN"))
        else:
            df["climate_zone"] = df["climate_zone"].fillna(df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("climate_zone", "UNKNOWN")))

        if "meteorological_regime" not in df.columns or df["meteorological_regime"].isna().all():
            df["meteorological_regime"] = df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("meteorological_regime", "UNKNOWN"))
        else:
            df["meteorological_regime"] = df["meteorological_regime"].fillna(df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("meteorological_regime", "UNKNOWN")))

        if "elevation_m" not in df.columns or df["elevation_m"].isna().all():
            df["elevation_m"] = df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("elevation_m", np.nan))
        else:
            df["elevation_m"] = df["elevation_m"].fillna(df["location_id"].map(lambda x: loc_meta_map.get(x, {}).get("elevation_m", np.nan)))

        # Reorder and project columns strictly to CANONICAL_HISTORICAL_COLUMNS
        missing_cols = [c for c in CANONICAL_HISTORICAL_COLUMNS if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Standardized DataFrame missing required canonical columns: {missing_cols}")

        return df[CANONICAL_HISTORICAL_COLUMNS].copy()

    def validate_dataset(
        self,
        df: pd.DataFrame,
        strict: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform 8-point scientific quality control validation on canonical multi-climate dataset.

        Returns:
            Dict containing detailed validation metrics and audit pass/fail status.
        """
        if df.empty:
            raise ValueError("Cannot validate empty dataset.")

        audit_issues: List[str] = []

        # 1. Column completeness
        missing_cols = [c for c in CANONICAL_HISTORICAL_COLUMNS if c not in df.columns]
        if missing_cols:
            audit_issues.append(f"Missing canonical columns: {missing_cols}")

        # 2. Coordinate sanity
        invalid_lats = df[(df["latitude"] < -90.0) | (df["latitude"] > 90.0) | df["latitude"].isna()]
        invalid_lons = df[(df["longitude"] < -180.0) | (df["longitude"] > 180.0) | df["longitude"].isna()]
        if len(invalid_lats) > 0 or len(invalid_lons) > 0:
            audit_issues.append(f"Found {len(invalid_lats)} invalid latitudes and {len(invalid_lons)} invalid longitudes.")

        # 3. Temporal consistency (valid_time >= issue_time, lead_hours >= 0)
        neg_leads = df[df["lead_hours"] < 0]
        time_inversion = df[df["valid_time_utc"] < df["issue_time_utc"]]
        if len(neg_leads) > 0 or len(time_inversion) > 0:
            audit_issues.append(f"Temporal violation: {len(neg_leads)} negative lead_hours, {len(time_inversion)} time inversions.")

        # 4. Duplicate identity check
        dup_keys = ["location_id", "variable", "issue_time_utc", "valid_time_utc"]
        dup_count = int(df.duplicated(subset=dup_keys).sum())
        if dup_count > 0:
            audit_issues.append(f"Duplicate forecast keys detected: {dup_count} duplicate rows.")

        # 5. Spatial mismatch threshold
        excess_dist = df[df["spatial_distance_km"] > self.max_spatial_distance_km]
        if len(excess_dist) > 0:
            audit_issues.append(f"Spatial mismatch: {len(excess_dist)} rows exceed {self.max_spatial_distance_km} km max distance.")

        # 6. Physical bounds check (Temperature, Pressure, Wind)
        physical_bounds = {
            "temperature_2m": (-60.0, 60.0),
            "surface_pressure": (500.0, 1100.0),
            "wind_speed_10m": (0.0, 300.0),
        }
        phys_violations = 0
        for var, (v_min, v_max) in physical_bounds.items():
            var_rows = df[df["variable"] == var]
            f_out = var_rows[(var_rows["forecast_value"] < v_min) | (var_rows["forecast_value"] > v_max)]
            t_out = var_rows[(var_rows["truth_value"] < v_min) | (var_rows["truth_value"] > v_max)]
            phys_violations += len(f_out) + len(t_out)
        if phys_violations > 0:
            audit_issues.append(f"Physical bounds violation: {phys_violations} observations outside valid atmospheric limits.")

        # 7. Ground truth presence
        missing_truth = int(df["truth_value"].isna().sum())
        if missing_truth > 0:
            audit_issues.append(f"Missing verification truth: {missing_truth} rows lack truth_value.")

        # 8. Ensemble membership
        # Reforecast legitimately has 5 members on normal days and 11 on
        # weekly extended runs. Do not reject scientifically valid reforecast
        # rows merely because they are smaller than the 31-member operational GEFS.
        source_text = df.get("forecast_source", pd.Series("", index=df.index)).astype(str).str.lower()
        expected_members = np.where(source_text.str.contains("reforecast"), 5, 10)
        degraded_ensembles = int((df["member_count"].fillna(0).astype(float) < expected_members).sum())
        if degraded_ensembles > 0:
            audit_issues.append(f"Degraded ensembles: {degraded_ensembles} rows have fewer than the source-appropriate minimum members.")

        is_valid = len(audit_issues) == 0

        report = {
            "validation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "total_records": len(df),
            "distinct_locations": int(df["location_id"].nunique()),
            "distinct_cycles": int(df["cycle"].nunique()),
            "distinct_variables": int(df["variable"].nunique()),
            "lead_hours_min": int(df["lead_hours"].min()) if len(df) > 0 else 0,
            "lead_hours_max": int(df["lead_hours"].max()) if len(df) > 0 else 0,
            "mean_spatial_distance_km": round(float(df["spatial_distance_km"].mean()), 2) if len(df) > 0 else 0.0,
            "full_ensemble_ratio": round(float(df["has_full_ensemble"].mean()), 4) if len(df) > 0 else 0.0,
            "duplicates_found": dup_count,
            "is_valid": is_valid,
            "audit_issues": audit_issues,
        }

        if strict and not is_valid:
            raise ValueError(f"Dataset QC validation failed with {len(audit_issues)} issues: {'; '.join(audit_issues)}")

        return report

    def build_canonical_dataset(
        self,
        paired_slices: List[pd.DataFrame],
        strict_validation: bool = True,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Combine multiple paired station/cycle slices into a single canonical multi-climate table.
        """
        if not paired_slices:
            raise ValueError("No paired slices provided.")

        standardized_slices = [self.standardize_paired_slice(s) for s in paired_slices]
        combined = pd.concat(standardized_slices, ignore_index=True)

        # Drop any exact duplicates if multiple runs overlapped
        dup_keys = ["location_id", "variable", "issue_time_utc", "valid_time_utc"]
        combined = combined.drop_duplicates(subset=dup_keys, keep="last").reset_index(drop=True)

        report = self.validate_dataset(combined, strict=strict_validation)

        # Add stratification breakdowns to report
        report["location_breakdown"] = {str(k): int(v) for k, v in combined["location_id"].value_counts().items()}
        report["climate_zone_breakdown"] = {str(k): int(v) for k, v in combined["climate_zone"].value_counts().items()}
        report["cycle_breakdown"] = {str(k): int(v) for k, v in combined["cycle"].value_counts().items()}
        report["variable_breakdown"] = {str(k): int(v) for k, v in combined["variable"].value_counts().items()}

        return combined, report

    def save_canonical_dataset(
        self,
        df: pd.DataFrame,
        report: Dict[str, Any],
        dataset_name: str = "canonical_multi_climate_historical",
        dest_dir: Optional[Union[str, Path]] = None,
        timestamp_str: Optional[str] = None,
    ) -> Tuple[Path, Path, Path]:
        """Save validated canonical multi-climate historical dataset and manifest."""
        import hashlib
        import json

        if timestamp_str is None:
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        out_dir = Path(dest_dir) if dest_dir else self.historical_dir / "canonical"
        out_dir.mkdir(parents=True, exist_ok=True)

        parquet_path = out_dir / f"{dataset_name}_{timestamp_str}.parquet"
        csv_path = out_dir / f"{dataset_name}_{timestamp_str}.csv"
        manifest_path = out_dir / f"{dataset_name}_{timestamp_str}_manifest.json"

        df.to_parquet(parquet_path, index=False)
        df.to_csv(csv_path, index=False)

        with open(parquet_path, "rb") as f:
            p_sha = hashlib.sha256(f.read()).hexdigest()

        manifest = {
            "dataset_name": dataset_name,
            "schema_version": "2.0.0-multi-climate",
            "generation_time_utc": datetime.now(timezone.utc).isoformat(),
            "total_records": len(df),
            "parquet_file_path": str(parquet_path),
            "parquet_sha256": p_sha,
            "csv_file_path": str(csv_path),
            "columns": list(df.columns),
            "feature_columns": CANONICAL_FEATURE_COLUMNS,
            "target_columns": CANONICAL_TARGET_COLUMNS,
            "validation_report": report,
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return parquet_path, csv_path, manifest_path

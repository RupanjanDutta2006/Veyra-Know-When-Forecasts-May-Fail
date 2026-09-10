"""Veyra Authoritative V3 Feature Pipeline.

Constructs the exact 50-feature representation required by the authoritative V3 LightGBM model
(models/v3/lightgbm_v3_challenger.joblib) and its associated probability calibrator.

Key Scientific Constraints:
1. Pure physical issue-time features only (no lat/lon, no station ID, no elevation over-indexing).
2. Canonical V3 unit space:
   - temperature_2m: Kelvin (K)  [T_K = T_C + 273.15]
   - surface_pressure: Pascal (Pa)  [P_Pa = P_hPa * 100]
   - wind_speed_10m: m/s  [canonical SI unit]
3. Exactly 50 ordered features matching models/v3/feature_names.json.
4. Non-circular, pre-inference OOD scoring.
"""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.base import WeatherResult


# Authoritative 50 features in strict frozen order from models/v3/feature_names.json
V3_FEATURE_NAMES: List[str] = [
    "ensemble_mean",
    "ensemble_median",
    "ensemble_std",
    "ensemble_min",
    "ensemble_max",
    "ensemble_range",
    "ensemble_p10",
    "ensemble_p25",
    "ensemble_p75",
    "ensemble_p90",
    "ensemble_iqr",
    "ensemble_skew_proxy",
    "ensemble_kurtosis_proxy",
    "ensemble_cv",
    "ensemble_spread_to_iqr_ratio",
    "quantile_spacing_ratio",
    "tail_asymmetry",
    "robust_mad",
    "member_count",
    "has_full_ensemble",
    "forecast_value",
    "forecast_delta_6h",
    "forecast_delta_24h",
    "forecast_revision_mag_6h",
    "forecast_revision_mag_24h",
    "ensemble_spread_delta_6h",
    "ensemble_spread_delta_24h",
    "revision_accel_6h",
    "stability_index",
    "structural_overconfidence_risk",
    "rapid_change_proxy",
    "diurnal_phase_alignment",
    "lead_hours",
    "lead_days",
    "lead_decay_factor",
    "spread_x_lead",
    "cv_x_lead",
    "revision_x_spread",
    "valid_hour",
    "valid_month",
    "valid_dayofweek",
    "sin_hour",
    "cos_hour",
    "sin_month",
    "cos_month",
    "is_weekend",
    "is_surface_pressure",
    "is_temperature_2m",
    "is_wind_speed_10m",
    "ood_score",
]


def convert_units_to_v3(
    variable: str,
    val: float,
    unit_str: Optional[str] = None,
) -> float:
    """Transform live variable value into authoritative V3 unit space.

    temperature_2m: Celsius (°C) -> Kelvin (K)
    surface_pressure: hPa -> Pascal (Pa)
    wind_speed_10m: canonical m/s (km/h converted to m/s if detected)
    """
    if val is None or np.isnan(val):
        return np.nan

    v = float(val)
    u = (unit_str or "").lower().strip()

    if variable == "temperature_2m":
        # Convert Celsius to Kelvin
        if u in ("c", "celsius", "°c") or v < 100.0:
            return round(v + 273.15, 4)
        return round(v, 4)

    elif variable == "surface_pressure":
        # Convert hPa / mbar to Pa
        if u in ("hpa", "mb", "mbar") or v < 2000.0:
            return round(v * 100.0, 2)
        return round(v, 2)

    elif variable == "wind_speed_10m":
        # Canonical m/s
        if u in ("km/h", "kmh"):
            return round(v / 3.6, 4)
        return round(v, 4)

    return round(v, 4)


def compute_v3_ood_score(
    variable: str,
    forecast_val_v3: float,
    unit_str: Optional[str] = None,
) -> float:
    """Compute pre-inference physical domain OOD novelty score (0.0 to 100.0).

    Strictly issue-time safe and non-circular (does not depend on model output).
    """
    if forecast_val_v3 is None or np.isnan(forecast_val_v3):
        return 0.0

    val = float(forecast_val_v3)
    score = 0.0

    if variable == "temperature_2m":
        # val is in Kelvin
        if val > 350.0 or val < 200.0:  # >77°C or <-73°C
            score = min(100.0, max(45.0, abs(val - 300.0) / 10.0 * 20.0))
    elif variable == "wind_speed_10m":
        # val is in m/s
        if val > 60.0 or val < 0.0:
            score = min(100.0, max(45.0, abs(val - 10.0) / 5.0 * 20.0))
    elif variable == "surface_pressure":
        # val is in Pascal
        if val > 110000.0 or val < 50000.0:
            score = min(100.0, max(45.0, abs(val - 101325.0) / 5000.0 * 20.0))

    return round(score, 3)


def classify_v3_failure_fingerprint(row_dict: Dict[str, Any]) -> str:
    """Classify forecast step into one of 6 mutually exclusive failure archetypes.

    Conforms to Builder-2's issue-time safe atmospheric regime classification.
    """
    rev_mag = float(row_dict.get("forecast_revision_mag_6h", 0.0) or 0.0)
    std = float(row_dict.get("ensemble_std", 1.0) or 1.0)
    lead = float(row_dict.get("lead_hours", 0) or 0)
    stab = float(row_dict.get("stability_index", 100.0) or 100.0)
    cos_h = float(row_dict.get("cos_hour", 0.0) or 0.0)
    cv = float(row_dict.get("ensemble_cv", 0.0) or 0.0)
    is_wind = float(row_dict.get("is_wind_speed_10m", 0.0) or 0.0)
    p90 = float(row_dict.get("ensemble_p90", 0.0) or 0.0)
    overconf = float(row_dict.get("structural_overconfidence_risk", 0.0) or 0.0)

    if rev_mag > 1.8 * std and stab < 50.0:
        return "RAPID_REVISION_SHOCK"
    elif lead >= 48 and std > 1.5:
        return "LONG_LEAD_DECAY"
    elif cos_h > 0.3 and cv > 0.12:
        return "DIURNAL_CONVECTIVE_MISMATCH"
    elif is_wind == 1.0 and p90 > 14.0:
        return "WIND_GRADIENT_SHEAR"
    elif overconf > 25.0:
        return "TIGHT_CLUSTER_BREAKDOWN"
    else:
        return "STABLE_SYNOPTIC_CONSENSUS"


def compute_ensemble_statistics(
    members: Union[List[float], Tuple[float, ...], np.ndarray],
    eps: float = 1e-6,
) -> Dict[str, float]:
    """Compute exact ensemble dispersion and geometric statistics from member values.

    Preserves actual member count (e.g. N=31).
    Computes:
        mean, median, sample std (ddof=1), min, max, range,
        p10, p25, p75, p90, IQR (p90 - p10), MAD, CV,
        quantile spacing ratio, tail asymmetry.
    """
    arr = np.array(members, dtype=float)
    if len(arr) == 0:
        raise ValueError("Ensemble member collection cannot be empty.")

    mean = float(np.mean(arr))
    median = float(np.median(arr))
    sample_std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    min_v = float(np.min(arr))
    max_v = float(np.max(arr))
    rng = max(0.0, max_v - min_v)
    p10 = float(np.percentile(arr, 10))
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))
    p90 = float(np.percentile(arr, 90))
    iqr = max(0.0, p90 - p10)
    mad = float(0.6745 * iqr)
    cv = sample_std / (abs(mean) + eps)
    quantile_spacing = float(np.clip((p90 - median) / (median - p10 + eps), 0.01, 100.0))
    tail_asym = float(np.clip(abs(p90 - median) / (rng + eps), 0.0, 1.0))

    return {
        "ensemble_mean": mean,
        "ensemble_median": median,
        "ensemble_std": sample_std,
        "ensemble_min": min_v,
        "ensemble_max": max_v,
        "ensemble_range": rng,
        "ensemble_p10": p10,
        "ensemble_p25": p25,
        "ensemble_p75": p75,
        "ensemble_p90": p90,
        "ensemble_iqr": iqr,
        "robust_mad": mad,
        "ensemble_cv": cv,
        "quantile_spacing_ratio": quantile_spacing,
        "tail_asymmetry": tail_asym,
        "member_count": len(arr),
    }


class V3FeaturePipeline:
    """Authoritative issue-time safe 50-feature extraction pipeline for V3."""

    def __init__(self, eps: float = 1e-6):
        self.eps = eps

    def extract_from_records(
        self,
        records: List[Union[CanonicalForecastRecord, Dict[str, Any]]],
        target_variable: str = "temperature_2m",
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """Convert a sequence of CanonicalForecastRecords into a validated 50-feature DataFrame.

        Returns:
            Tuple of (features_df, metadata_rows) where features_df has shape (N, 50).
        """
        if not records:
            raise ValueError("No forecast records provided for V3 feature extraction.")

        rows: List[Dict[str, Any]] = []
        for r in records:
            if isinstance(r, CanonicalForecastRecord):
                rec = r.model_dump()
            elif isinstance(r, dict):
                rec = r
            else:
                continue

            var_name = rec.get("variable", target_variable)
            if var_name != target_variable and target_variable is not None:
                # If records contain multiple variables, filter to target_variable
                continue

            unit_str = rec.get("unit", "")
            raw_val = rec.get("value") if rec.get("value") is not None else rec.get("forecast_value")

            # Check if raw member array is supplied
            members_raw = rec.get("members") or rec.get("ensemble_members")
            if members_raw is not None and len(members_raw) > 0:
                members_v3 = [convert_units_to_v3(var_name, m, unit_str) for m in members_raw]
                stats = compute_ensemble_statistics(members_v3, eps=self.eps)
                val_v3 = convert_units_to_v3(var_name, raw_val, unit_str) if raw_val is not None else stats["ensemble_mean"]
                mean_v3 = stats["ensemble_mean"]
                std_v3 = stats["ensemble_std"]
                min_v3 = stats["ensemble_min"]
                max_v3 = stats["ensemble_max"]
                q10_v3 = stats["ensemble_p10"]
                q90_v3 = stats["ensemble_p90"]
                member_count = stats["member_count"]
            else:
                raw_mean = rec.get("ensemble_mean") if rec.get("ensemble_mean") is not None else raw_val
                raw_std = rec.get("ensemble_std", 0.0)
                raw_min = rec.get("ensemble_min")
                raw_max = rec.get("ensemble_max")
                raw_q10 = rec.get("q10")
                raw_q90 = rec.get("q90")
                member_count = int(rec.get("member_count", 31) or 31)

                # Upstream unit conversion to Kelvin / Pascal / ms
                val_v3 = convert_units_to_v3(var_name, raw_val, unit_str)
                mean_v3 = convert_units_to_v3(var_name, raw_mean, unit_str)
                min_v3 = convert_units_to_v3(var_name, raw_min, unit_str) if raw_min is not None else mean_v3
                max_v3 = convert_units_to_v3(var_name, raw_max, unit_str) if raw_max is not None else mean_v3

                # Spread / std unit conversion
                if var_name == "surface_pressure":
                    std_v3 = float(raw_std) * 100.0 if (raw_std is not None and not np.isnan(raw_std)) else 0.0
                else:
                    std_v3 = float(raw_std) if (raw_std is not None and not np.isnan(raw_std)) else 0.0

                q10_v3 = convert_units_to_v3(var_name, raw_q10, unit_str) if raw_q10 is not None else min_v3
                q90_v3 = convert_units_to_v3(var_name, raw_q90, unit_str) if raw_q90 is not None else max_v3

            # Parse timestamps
            issue_time_str = rec.get("issue_time", "")
            valid_time_str = rec.get("valid_time", "")
            lead_hours = int(rec.get("lead_hours", 24))

            try:
                dt_valid = datetime.fromisoformat(valid_time_str.replace("Z", "+00:00"))
            except Exception:
                dt_valid = datetime.now(timezone.utc)

            rows.append({
                "location": rec.get("location", "default"),
                "variable": var_name,
                "unit": unit_str,
                "issue_time": issue_time_str,
                "valid_time": dt_valid,
                "lead_hours": lead_hours,
                "val_v3": val_v3,
                "mean_v3": mean_v3,
                "std_v3": std_v3,
                "min_v3": min_v3,
                "max_v3": max_v3,
                "q10_v3": q10_v3,
                "q90_v3": q90_v3,
                "member_count": member_count,
            })

        if not rows:
            # Fallback if variable filter eliminated all records: process all records
            return self.extract_from_records(records, target_variable=None)

        # Build DataFrame
        df_work = pd.DataFrame(rows)

        feature_dicts: List[Dict[str, Any]] = []
        meta_dicts: List[Dict[str, Any]] = []

        for idx, row in df_work.iterrows():
            mean = float(row["mean_v3"])
            std = float(row["std_v3"])
            min_v = float(row["min_v3"])
            max_v = float(row["max_v3"])
            p10 = float(row["q10_v3"])
            p90 = float(row["q90_v3"])
            member_count = int(row["member_count"])
            lead_h = int(row["lead_hours"])
            var_name = str(row["variable"])
            dt_valid: datetime = row["valid_time"]

            # Higher-order moments & quantiles (matching Builder-2 formulas)
            median = mean
            p25 = 0.75 * mean + 0.25 * min_v
            p75 = 0.75 * mean + 0.25 * max_v
            rng = max(0.0, max_v - min_v)
            iqr = max(0.0, p90 - p10)

            midpoint = 0.5 * (max_v + min_v)
            skew_proxy = (mean - midpoint) / (std + self.eps)
            cv = std / (abs(mean) + self.eps)
            spread_to_iqr = std / (iqr + self.eps)
            has_full = 1 if member_count >= 30 else 0

            kurtosis_proxy = float(np.clip((rng / (iqr + self.eps)) - 2.5, -10.0, 10.0))
            quantile_spacing = float(np.clip((p90 - median) / (median - p10 + self.eps), 0.01, 100.0))
            tail_asym = float(np.clip(abs(p90 - median) / (rng + self.eps), 0.0, 1.0))
            robust_mad = float(0.6745 * iqr)

            # Revisions: for live single-cycle requests, historical cycles are not populated -> 0.0
            # (Matches historical bi-weekly training distribution where revisions had 0 splits)
            f_delta_6h = 0.0
            f_delta_24h = 0.0
            f_rev_mag_6h = 0.0
            f_rev_mag_24h = 0.0
            ens_spread_delta_6h = 0.0
            ens_spread_delta_24h = 0.0
            rev_accel_6h = 0.0
            stability_idx = 100.0
            struct_overconf = 0.0
            rapid_change = 0.0

            # Horizon and temporal harmonics
            v_hour = dt_valid.hour
            v_month = dt_valid.month
            v_dow = dt_valid.weekday()
            is_wknd = 1 if v_dow in (5, 6) else 0

            diurnal_phase = float(math.cos(2.0 * math.pi * (v_hour - 14.0) / 24.0))
            lead_d = round(lead_h / 24.0, 3)
            lead_decay = round(max(0.0, 1.0 - (lead_h / 240.0)), 4)
            spread_x_lead = round(std * math.log1p(max(0, lead_h)), 4)
            cv_x_lead = round(cv * (lead_h / 24.0), 4)
            rev_x_spread = 0.0

            sin_h = round(math.sin(2.0 * math.pi * v_hour / 24.0), 5)
            cos_h = round(math.cos(2.0 * math.pi * v_hour / 24.0), 5)
            sin_m = round(math.sin(2.0 * math.pi * v_month / 12.0), 5)
            cos_m = round(math.cos(2.0 * math.pi * v_month / 12.0), 5)

            # Variable indicators
            is_sp = 1.0 if var_name == "surface_pressure" else 0.0
            is_t2m = 1.0 if var_name == "temperature_2m" else 0.0
            is_ws = 1.0 if var_name == "wind_speed_10m" else 0.0

            # OOD Score
            ood = compute_v3_ood_score(var_name, mean, row["unit"])

            feat_row: Dict[str, Any] = {
                "ensemble_mean": float(mean),
                "ensemble_median": float(median),
                "ensemble_std": float(std),
                "ensemble_min": float(min_v),
                "ensemble_max": float(max_v),
                "ensemble_range": float(rng),
                "ensemble_p10": float(p10),
                "ensemble_p25": float(p25),
                "ensemble_p75": float(p75),
                "ensemble_p90": float(p90),
                "ensemble_iqr": float(iqr),
                "ensemble_skew_proxy": float(skew_proxy),
                "ensemble_kurtosis_proxy": float(kurtosis_proxy),
                "ensemble_cv": float(cv),
                "ensemble_spread_to_iqr_ratio": float(spread_to_iqr),
                "quantile_spacing_ratio": float(quantile_spacing),
                "tail_asymmetry": float(tail_asym),
                "robust_mad": float(robust_mad),
                "member_count": int(member_count),
                "has_full_ensemble": int(has_full),
                "forecast_value": float(row["val_v3"]),
                "forecast_delta_6h": float(f_delta_6h),
                "forecast_delta_24h": float(f_delta_24h),
                "forecast_revision_mag_6h": float(f_rev_mag_6h),
                "forecast_revision_mag_24h": float(f_rev_mag_24h),
                "ensemble_spread_delta_6h": float(ens_spread_delta_6h),
                "ensemble_spread_delta_24h": float(ens_spread_delta_24h),
                "revision_accel_6h": float(rev_accel_6h),
                "stability_index": float(stability_idx),
                "structural_overconfidence_risk": float(struct_overconf),
                "rapid_change_proxy": float(rapid_change),
                "diurnal_phase_alignment": float(diurnal_phase),
                "lead_hours": int(lead_h),
                "lead_days": float(lead_d),
                "lead_decay_factor": float(lead_decay),
                "spread_x_lead": float(spread_x_lead),
                "cv_x_lead": float(cv_x_lead),
                "revision_x_spread": float(rev_x_spread),
                "valid_hour": int(v_hour),
                "valid_month": int(v_month),
                "valid_dayofweek": int(v_dow),
                "sin_hour": float(sin_h),
                "cos_hour": float(cos_h),
                "sin_month": float(sin_m),
                "cos_month": float(cos_m),
                "is_weekend": int(is_wknd),
                "is_surface_pressure": float(is_sp),
                "is_temperature_2m": float(is_t2m),
                "is_wind_speed_10m": float(is_ws),
                "ood_score": float(ood),
            }

            fingerprint_id = classify_v3_failure_fingerprint(feat_row)

            meta_row = {
                "location": row["location"],
                "variable": var_name,
                "lead_hours": lead_h,
                "valid_time": dt_valid.isoformat(),
                "fingerprint_id": fingerprint_id,
            }

            feature_dicts.append(feat_row)
            meta_dicts.append(meta_row)

        df_features = pd.DataFrame(feature_dicts)[V3_FEATURE_NAMES]
        return df_features, meta_dicts

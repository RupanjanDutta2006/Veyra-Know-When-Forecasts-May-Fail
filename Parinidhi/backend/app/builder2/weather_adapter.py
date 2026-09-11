"""Weather Data Adapter for Builder 2 Feature Pipeline.

Converts Veyra's standard WeatherResult (from OpenMeteoGEFSWeatherService or other providers)
into a standardized pandas DataFrame conforming to Builder 2's canonical input format.
"""
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.base import WeatherResult


def weather_result_to_dataframe(weather_result: WeatherResult) -> pd.DataFrame:
    """Extract forecast records from WeatherResult and construct a standardized DataFrame.

    Preserves exact meteorological and ensemble fields without fabrication:
    - location, latitude, longitude, issue_time, valid_time, lead_hours, variable, unit, forecast_value
    - ensemble_mean, ensemble_std, ensemble_min, ensemble_max, q10, q90, member_count

    Args:
        weather_result: Standard Veyra WeatherResult container.

    Returns:
        Standardized pandas DataFrame ready for IssueTimeSafeFeaturePipeline.
    """
    if not weather_result.is_available or not weather_result.raw_data:
        return pd.DataFrame()

    raw_records = weather_result.raw_data.get("records", [])
    if not raw_records:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    for item in raw_records:
        if isinstance(item, CanonicalForecastRecord):
            rec_dict = item.model_dump()
        elif isinstance(item, dict):
            rec_dict = item
        else:
            continue

        loc = rec_dict.get("location", weather_result.location)
        lat = rec_dict.get("latitude", 0.0)
        lon = rec_dict.get("longitude", 0.0)
        issue_time = rec_dict.get("issue_time", "")
        valid_time = rec_dict.get("valid_time", "")
        lead_h = rec_dict.get("lead_hours", 0)
        var_name = rec_dict.get("variable", "")
        unit_str = rec_dict.get("unit", "")
        val = rec_dict.get("value")
        ens_mean = rec_dict.get("ensemble_mean", val)
        ens_std = rec_dict.get("ensemble_std", np.nan)
        ens_min = rec_dict.get("ensemble_min", np.nan)
        ens_max = rec_dict.get("ensemble_max", np.nan)
        q10_val = rec_dict.get("q10", np.nan)
        q90_val = rec_dict.get("q90", np.nan)
        member_cnt = rec_dict.get("member_count", 31)

        rows.append({
            "location": loc,
            "latitude": float(lat),
            "longitude": float(lon),
            "issue_time": issue_time,
            "valid_time": valid_time,
            "lead_hours": int(lead_h),
            "variable": var_name,
            "unit": unit_str,
            "value": float(val) if val is not None else np.nan,
            "forecast_value": float(val) if val is not None else np.nan,
            "ensemble_mean": float(ens_mean) if ens_mean is not None else np.nan,
            "ensemble_std": float(ens_std) if ens_std is not None and not np.isnan(ens_std) else np.nan,
            "ensemble_min": float(ens_min) if ens_min is not None and not np.isnan(ens_min) else np.nan,
            "ensemble_max": float(ens_max) if ens_max is not None and not np.isnan(ens_max) else np.nan,
            "q10": float(q10_val) if q10_val is not None and not np.isnan(q10_val) else np.nan,
            "q90": float(q90_val) if q90_val is not None and not np.isnan(q90_val) else np.nan,
            "member_count": int(member_cnt) if member_cnt is not None else 31,
        })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)

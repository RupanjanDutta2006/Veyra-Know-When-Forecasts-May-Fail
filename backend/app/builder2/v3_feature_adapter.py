"""Authoritative Builder 2 V3 Feature Engineering Adapter for Veyra.

Adapts the authoritative 50-feature V3FeaturePipeline to conform to
Builder 1's BaseFeatureService interface.
"""

import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.app.builder2.v3_feature_pipeline import (
    V3_FEATURE_NAMES,
    V3FeaturePipeline,
    classify_v3_failure_fingerprint,
)
from backend.app.builder2.weather_adapter import weather_result_to_dataframe
from backend.app.schemas.prediction import ReasonCode
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.base import BaseFeatureService, FeatureResult, WeatherResult

logger = logging.getLogger(__name__)


class Builder2V3FeatureAdapter(BaseFeatureService):
    """Production feature adapter wrapping the authoritative 50-feature V3 pipeline.

    Enforces:
    - Pure physical issue-time features only (no lat/lon in feature vector)
    - Upstream unit space transformation (Kelvin, Pascal, m/s)
    - Exactly 50 ordered features matching models/v3/feature_names.json
    - Full ensemble dispersion statistics (N=31 supported)
    - Issue-time safe OOD novelty calculation
    """

    def __init__(self, eps: float = 1e-6):
        self.pipeline = V3FeaturePipeline(eps=eps)
        self.is_ready = True

    def build_features(self, weather_result: WeatherResult) -> FeatureResult:
        """Transform WeatherResult into the authoritative 50-feature FeatureResult."""
        if not weather_result.is_available or weather_result.error:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
                error=weather_result.error or "Weather data unavailable for feature extraction",
            )

        # 1. Obtain raw forecast records
        raw_records = []
        if weather_result.raw_data and "records" in weather_result.raw_data:
            raw_records = weather_result.raw_data["records"]

        if not raw_records:
            # Fallback: construct records from weather_result_to_dataframe
            df_forecast = weather_result_to_dataframe(weather_result)
            if not df_forecast.empty:
                raw_records = df_forecast.to_dict(orient="records")

        if not raw_records:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.DATA_NOT_READY.value},
                error="Weather result contains zero parseable forecast records",
            )

        # 2. Extract 50-feature DataFrame
        target_var = weather_result.metadata.get("variable", "temperature_2m") if weather_result.metadata else "temperature_2m"
        try:
            X, meta_rows = self.pipeline.extract_from_records(
                raw_records, target_variable=target_var
            )
        except Exception as exc:
            logger.error("V3 feature extraction error: %s", exc)
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error=f"V3 feature pipeline failed: {exc}",
            )

        if X.empty:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error="V3 feature pipeline produced empty feature matrix",
            )

        # 3. Validate exact 50-column contract
        if list(X.columns) != V3_FEATURE_NAMES:
            return FeatureResult(
                location=weather_result.location,
                features={},
                feature_names=[],
                is_ready=False,
                metadata={"status": ReasonCode.QC_FAILED.value},
                error=f"V3 feature columns do not match authoritative 50-feature contract. Expected {len(V3_FEATURE_NAMES)}, got {len(X.columns)}",
            )

        # 4. Target record selection (match valid_time / target_date if specified)
        selected_idx = 0
        target_valid = weather_result.metadata.get("valid_time") if weather_result.metadata else None
        if target_valid and meta_rows:
            try:
                dt_target = pd.to_datetime(target_valid, utc=True)
                diffs = [
                    abs(pd.to_datetime(m["valid_time"], utc=True) - dt_target)
                    for m in meta_rows
                ]
                selected_idx = int(np.argmin(diffs))
            except Exception as match_err:
                logger.debug("Failed matching valid_time '%s': %s", target_valid, match_err)
                selected_idx = 0
        elif weather_result.target_date and meta_rows:
            try:
                dt_target = pd.to_datetime(weather_result.target_date, utc=True)
                diffs = [
                    abs(pd.to_datetime(m["valid_time"], utc=True) - dt_target)
                    for m in meta_rows
                ]
                selected_idx = int(np.argmin(diffs))
            except Exception as match_err:
                logger.debug("Failed matching target_date '%s': %s", weather_result.target_date, match_err)
                selected_idx = 0

        # 5. Extract target row and metadata
        target_row = X.iloc[selected_idx].to_dict()
        selected_meta = meta_rows[selected_idx] if selected_idx < len(meta_rows) else {}
        fingerprint_id = selected_meta.get("fingerprint_id", classify_v3_failure_fingerprint(target_row))

        fingerprint_dict = {
            "primary_archetype": fingerprint_id,
            "structural_overconfidence": bool(target_row.get("structural_overconfidence_risk", 0.0) > 20.0),
            "revision_instability": {
                "magnitude_6h": float(target_row.get("forecast_revision_mag_6h", 0.0)),
                "magnitude_24h": float(target_row.get("forecast_revision_mag_24h", 0.0)),
            },
            "description": f"Classified into V3 archetype '{fingerprint_id}'",
        }

        features_dict = {
            col: float(target_row[col]) for col in V3_FEATURE_NAMES
        }

        # If client passed explicit target issue_time and valid_time, calculate and propagate exact lead_hours
        target_issue = weather_result.metadata.get("issue_time") if weather_result.metadata else None
        if target_issue and target_valid:
            try:
                import math
                calc_lead = int(round((pd.to_datetime(target_valid, utc=True) - pd.to_datetime(target_issue, utc=True)).total_seconds() / 3600.0))
                if calc_lead >= 0:
                    features_dict["lead_hours"] = calc_lead
                    features_dict["lead_days"] = round(calc_lead / 24.0, 3)
                    features_dict["lead_decay_factor"] = round(max(0.0, 1.0 - (calc_lead / 240.0)), 4)
                    features_dict["spread_x_lead"] = round(features_dict["ensemble_std"] * math.log1p(max(0, calc_lead)), 4)
                    features_dict["cv_x_lead"] = round(features_dict["ensemble_cv"] * (calc_lead / 24.0), 4)
                    selected_meta["lead_hours"] = calc_lead
            except Exception:
                pass

        return FeatureResult(
            location=weather_result.location,
            features=features_dict,
            feature_names=list(V3_FEATURE_NAMES),
            is_ready=True,
            metadata={
                "is_single_target": True,
                "v3_schema": True,
                "feature_matrix_rows": X.to_dict(orient="records"),
                "metadata_rows": meta_rows,
                "instability_fingerprint": fingerprint_dict,
                "ood_score": float(target_row.get("ood_score", 0.0)),
                "variable": selected_meta.get("variable", target_var),
                "valid_time": selected_meta.get("valid_time"),
                "lead_hours": selected_meta.get("lead_hours", target_row.get("lead_hours")),
            },
            error=None,
        )

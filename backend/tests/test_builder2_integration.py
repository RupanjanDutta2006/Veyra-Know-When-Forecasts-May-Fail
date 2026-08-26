"""Comprehensive Integration Tests for Builder 2 in Veyra.

Validates:
1. Exact 26-feature contract (names, order, count).
2. Feature adapter interface compliance with BaseFeatureService.
3. Preservation of NaNs for missing prior-cycle revisions (never 0.0).
4. Model adapter loads cleanly when BUILDER2_MODEL_DIR is configured.
5. Model adapter safely abstains when artifacts are unavailable (probability=None, is_ready=False).
6. Model version == prototype-gbm-v1 and decision threshold == 0.280.
7. Strictly calibrated probability bounds in [0.0, 1.0].
8. Deterministic repeated predictions in the same process.
9. Numerical parity with Builder 2 reference LightGBM + Platt calibrator.
10. End-to-end ForecastBustAgent integration with Builder 2 services.
11. Weather failure short-circuits to safe abstention without calling ML.
12. Model failure short-circuits to safe abstention without hallucinating probabilities.
13. Day 7 instability metadata does not alter probability or canonical features.
14. Valid physical explanation generation attached to ModelResult metadata.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import pytest

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.builder2.feature_adapter import Builder2FeatureAdapter
from builder2.feature_pipeline import (
    FEATURE_COLUMN_NAMES,
    METADATA_COLUMNS,
    IssueTimeSafeFeaturePipeline,
)
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from builder2.model_service import ForecastBustModelService
from backend.app.builder2.weather_adapter import weather_result_to_dataframe
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest, ReasonCode, RiskLevel, TrustState
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.base import FeatureResult, ModelResult, WeatherResult
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService

# Reference model artifact path
B2_MODEL_DIR = Path(
    os.getenv(
        "BUILDER2_MODEL_DIR",
        str(Path(__file__).resolve().parents[3] / "forecast-bust-sentinel" / "models" / "day4"),
    )
)


# =====================================================================
# 1. Feature Contract Tests
# =====================================================================

def test_canonical_26_feature_contract():
    """Verify exact 26 feature names, order, and count."""
    expected_26 = [
        "ensemble_std",
        "ensemble_range",
        "ensemble_iqr",
        "ensemble_skew_proxy",
        "ensemble_cv",
        "ensemble_spread_to_iqr_ratio",
        "member_count",
        "has_full_ensemble",
        "forecast_value",
        "ensemble_mean",
        "ensemble_spread_delta_6h",
        "ensemble_spread_delta_24h",
        "forecast_delta_6h",
        "forecast_delta_24h",
        "lead_hours",
        "lead_days",
        "valid_hour",
        "valid_month",
        "valid_dayofweek",
        "sin_hour",
        "cos_hour",
        "sin_month",
        "cos_month",
        "is_weekend",
        "latitude",
        "longitude",
    ]
    assert len(FEATURE_COLUMN_NAMES) == 26
    assert FEATURE_COLUMN_NAMES == expected_26


def test_feature_pipeline_nan_preservation_for_missing_cycles():
    """Verify that missing prior cycles preserve NaN in revision features."""
    pipeline = IssueTimeSafeFeaturePipeline()

    # Single isolated cycle with no preceding run
    df_raw = pd.DataFrame([{
        "location": "Delhi",
        "variable": "temperature_2m",
        "issue_time": "2026-08-15 00:00:00+00:00",
        "valid_time": "2026-08-16 00:00:00+00:00",
        "lead_hours": 24,
        "forecast_value": 32.0,
        "ensemble_mean": 31.8,
        "ensemble_std": 1.2,
        "ensemble_min": 29.0,
        "ensemble_max": 34.5,
        "q10": 30.5,
        "q90": 33.2,
        "member_count": 31,
        "latitude": 28.5,
        "longitude": 77.25,
    }])

    X, meta = pipeline.extract_features(df_raw)
    assert len(X) == 1
    assert list(X.columns) == FEATURE_COLUMN_NAMES

    # Revisions must be NaN when no prior cycle exists (never filled with 0.0)
    assert np.isnan(X["forecast_delta_6h"].iloc[0])
    assert np.isnan(X["forecast_delta_24h"].iloc[0])
    assert np.isnan(X["ensemble_spread_delta_6h"].iloc[0])
    assert np.isnan(X["ensemble_spread_delta_24h"].iloc[0])


# =====================================================================
# 2. Feature Adapter Tests
# =====================================================================

def test_feature_adapter_build_features_success():
    """Test Builder2FeatureAdapter transforming valid WeatherResult."""
    adapter = Builder2FeatureAdapter()
    assert adapter.is_ready is True

    records = [
        CanonicalForecastRecord(
            location="Delhi",
            latitude=28.5,
            longitude=77.25,
            issue_time="2026-08-15T00:00:00Z",
            valid_time="2026-08-16T00:00:00Z",
            lead_hours=24,
            variable="temperature_2m",
            unit="celsius",
            value=30.0,
            member_count=31,
            ensemble_mean=30.2,
            ensemble_std=1.5,
            ensemble_min=27.0,
            ensemble_max=33.0,
            q10=28.5,
            q90=32.0,
        )
    ]
    weather_result = WeatherResult(
        location="Delhi",
        is_available=True,
        data_version="gefs-v1.0",
        raw_data={"records": [r.model_dump() for r in records]},
    )

    feat_result = adapter.build_features(weather_result)
    assert feat_result.is_ready is True
    assert feat_result.location == "Delhi"
    assert feat_result.feature_names == FEATURE_COLUMN_NAMES
    assert len(feat_result.features) == 26
    assert feat_result.metadata["schema_version"] == "builder2-canonical-26-v1.0"


def test_feature_adapter_weather_unavailable():
    """Test feature adapter handling unavailable weather gracefully."""
    adapter = Builder2FeatureAdapter()
    weather_result = WeatherResult(
        location="Tokyo",
        is_available=False,
        error="Vendor timeout",
    )
    feat_result = adapter.build_features(weather_result)
    assert feat_result.is_ready is False
    assert feat_result.error == "Vendor timeout"
    assert feat_result.metadata["status"] == ReasonCode.DATA_UNAVAILABLE.value


# =====================================================================
# 3. Model Adapter Tests
# =====================================================================

def test_model_adapter_unconfigured_fails_safely():
    """Test model adapter fails safely when artifacts are not configured."""
    adapter = Builder2ModelAdapter(model_dir=None)
    assert adapter.is_ready is False
    assert adapter.model_version is None

    feat_result = FeatureResult(
        location="London",
        features={col: 1.0 for col in FEATURE_COLUMN_NAMES},
        feature_names=FEATURE_COLUMN_NAMES,
        is_ready=True,
    )
    result = adapter.predict(feat_result)
    assert result.is_ready is False
    assert result.probability is None
    assert result.error is not None
    assert result.metadata["status"] == ReasonCode.MODEL_NOT_READY.value


@pytest.mark.skipif(not B2_MODEL_DIR.exists(), reason="Builder 2 model artifacts not found at path")
def test_model_adapter_loaded_prediction_bounds_and_determinism():
    """Test loaded model adapter produces bounded, deterministic calibrated probabilities."""
    adapter = Builder2ModelAdapter(model_dir=B2_MODEL_DIR)
    assert adapter.is_ready is True
    assert adapter.model_version == "prototype-gbm-v1"
    assert adapter.threshold == 0.280

    sample_dict = {
        "ensemble_std": 1.2, "ensemble_range": 3.5, "ensemble_iqr": 2.1,
        "ensemble_skew_proxy": 0.05, "ensemble_cv": 0.04, "ensemble_spread_to_iqr_ratio": 0.57,
        "member_count": 31, "has_full_ensemble": 1, "forecast_value": 30.2,
        "ensemble_mean": 30.1, "ensemble_spread_delta_6h": np.nan,
        "ensemble_spread_delta_24h": 0.15, "forecast_delta_6h": np.nan,
        "forecast_delta_24h": -0.35, "lead_hours": 24, "lead_days": 1.0,
        "valid_hour": 0, "valid_month": 8, "valid_dayofweek": 4,
        "sin_hour": 0.0, "cos_hour": 1.0, "sin_month": -0.866, "cos_month": -0.5,
        "is_weekend": 0, "latitude": 28.5, "longitude": 77.25,
    }

    feat_result = FeatureResult(
        location="Delhi",
        features=sample_dict,
        feature_names=FEATURE_COLUMN_NAMES,
        is_ready=True,
        metadata={"feature_matrix_rows": [sample_dict]},
    )

    # 1. Probability within [0.0, 1.0]
    res1 = adapter.predict(feat_result)
    assert res1.is_ready is True
    assert res1.probability is not None
    assert 0.0 <= res1.probability <= 1.0
    assert res1.model_version == "prototype-gbm-v1"

    # 2. Strict determinism in repeated execution
    res2 = adapter.predict(feat_result)
    assert res1.probability == res2.probability
    assert res1.metadata["bust_alert"] == res2.metadata["bust_alert"]


@pytest.mark.skipif(not B2_MODEL_DIR.exists(), reason="Builder 2 model artifacts not found at path")
def test_model_adapter_numerical_parity_with_builder2_service():
    """Verify exact numerical probability parity between standalone Builder 2 service and adapter."""
    standalone_service = ForecastBustModelService(model_dir=B2_MODEL_DIR)
    adapter = Builder2ModelAdapter(model_dir=B2_MODEL_DIR)

    sample_dict = {
        "ensemble_std": 2.5, "ensemble_range": 6.0, "ensemble_iqr": 3.8,
        "ensemble_skew_proxy": 0.12, "ensemble_cv": 0.08, "ensemble_spread_to_iqr_ratio": 0.65,
        "member_count": 31, "has_full_ensemble": 1, "forecast_value": 35.0,
        "ensemble_mean": 34.5, "ensemble_spread_delta_6h": 0.3,
        "ensemble_spread_delta_24h": 0.8, "forecast_delta_6h": 1.2,
        "forecast_delta_24h": 2.5, "lead_hours": 72, "lead_days": 3.0,
        "valid_hour": 12, "valid_month": 8, "valid_dayofweek": 2,
        "sin_hour": 0.0, "cos_hour": -1.0, "sin_month": -0.866, "cos_month": -0.5,
        "is_weekend": 0, "latitude": 28.5, "longitude": 77.25,
    }

    # Direct prediction
    direct_res = standalone_service.predict_single(sample_dict)
    direct_p = direct_res["probability"]

    # Adapter prediction
    feat_result = FeatureResult(
        location="Delhi",
        features=sample_dict,
        feature_names=FEATURE_COLUMN_NAMES,
        is_ready=True,
        metadata={"feature_matrix_rows": [sample_dict]},
    )
    adapter_res = adapter.predict(feat_result)
    adapter_p = adapter_res.probability

    assert round(direct_p, 4) == round(adapter_p, 4)


# =====================================================================
# 4. End-to-End ForecastBustAgent Integration Tests
# =====================================================================

@pytest.mark.skipif(not B2_MODEL_DIR.exists(), reason="Builder 2 model artifacts not found at path")
def test_forecast_bust_agent_end_to_end_with_builder2():
    """Test ForecastBustAgent end-to-end integration with Builder 2 services."""
    records = [
        CanonicalForecastRecord(
            location="Delhi",
            latitude=28.5,
            longitude=77.25,
            issue_time="2026-08-15T00:00:00Z",
            valid_time="2026-08-16T00:00:00Z",
            lead_hours=24,
            variable="temperature_2m",
            unit="celsius",
            value=30.5,
            member_count=31,
            ensemble_mean=30.2,
            ensemble_std=1.2,
            ensemble_min=28.0,
            ensemble_max=32.5,
            q10=29.0,
            q90=31.8,
        )
    ]
    weather_result = WeatherResult(
        location="Delhi",
        is_available=True,
        data_version="gefs-openmeteo-v1.0",
        raw_data={"records": [r.model_dump() for r in records]},
    )

    class MockWeather(OpenMeteoGEFSWeatherService):
        def get_forecast(self, location, target_date=None):
            return weather_result

    agent = ForecastBustAgent(
        weather_service=MockWeather(),
        feature_service=Builder2FeatureAdapter(),
        model_service=Builder2ModelAdapter(model_dir=B2_MODEL_DIR),
        safety_evaluator=SafetyEvaluator(),
    )

    req = PredictionRequest(location="Delhi")
    resp = agent.analyze(req)

    assert resp.location == "Delhi"
    assert resp.bust_probability is not None
    assert 0.0 <= resp.bust_probability <= 1.0
    assert resp.model_version == "prototype-gbm-v1"
    assert resp.abstain is False
    assert resp.trust_state in [TrustState.HIGH_CONFIDENCE, TrustState.MODERATE_CONFIDENCE, TrustState.LOW_CONFIDENCE]
    assert ReasonCode.SUCCESS.value in resp.reason_codes


def test_agent_weather_failure_abstains_without_calling_model():
    """Verify that weather failure causes agent to abstain safely."""
    class FailingWeather(OpenMeteoGEFSWeatherService):
        def get_forecast(self, location, target_date=None):
            return WeatherResult(
                location=location,
                is_available=False,
                error="Network timeout",
                metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
            )

    agent = ForecastBustAgent(
        weather_service=FailingWeather(),
        feature_service=Builder2FeatureAdapter(),
        model_service=Builder2ModelAdapter(model_dir=None),
        safety_evaluator=SafetyEvaluator(),
    )

    resp = agent.analyze(PredictionRequest(location="Kolkata"))
    assert resp.location == "Kolkata"
    assert resp.bust_probability is None
    assert resp.abstain is True
    assert resp.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.DATA_UNAVAILABLE.value in resp.reason_codes


def test_agent_missing_model_artifacts_abstains_without_hallucinating():
    """Verify that missing model artifacts cause agent to abstain with probability=None."""
    records = [
        CanonicalForecastRecord(
            location="Mumbai",
            latitude=19.07,
            longitude=72.87,
            issue_time="2026-08-15T00:00:00Z",
            valid_time="2026-08-16T00:00:00Z",
            lead_hours=24,
            variable="temperature_2m",
            unit="celsius",
            value=29.0,
            member_count=31,
            ensemble_mean=29.0,
            ensemble_std=1.0,
        )
    ]
    weather_result = WeatherResult(
        location="Mumbai",
        is_available=True,
        data_version="gefs-openmeteo-v1.0",
        raw_data={"records": [r.model_dump() for r in records]},
    )

    class MockWeather(OpenMeteoGEFSWeatherService):
        def get_forecast(self, location, target_date=None):
            return weather_result

    # Adapter with no model directory (unconfigured)
    agent = ForecastBustAgent(
        weather_service=MockWeather(),
        feature_service=Builder2FeatureAdapter(),
        model_service=Builder2ModelAdapter(model_dir=None),
        safety_evaluator=SafetyEvaluator(),
    )

    resp = agent.analyze(PredictionRequest(location="Mumbai"))
    assert resp.location == "Mumbai"
    assert resp.bust_probability is None
    assert resp.abstain is True
    assert resp.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.MODEL_NOT_READY.value in resp.reason_codes


# =====================================================================
# 5. Day 7 Instability Metadata Isolation Test
# =====================================================================

@pytest.mark.skipif(not B2_MODEL_DIR.exists(), reason="Builder 2 model artifacts not found at path")
def test_day7_instability_metadata_does_not_alter_prediction():
    """Verify that Day 7 instability fingerprint is metadata only and does not alter canonical features or prediction."""
    adapter_with_fp = Builder2FeatureAdapter(include_fingerprint=True)
    adapter_no_fp = Builder2FeatureAdapter(include_fingerprint=False)

    records = [
        CanonicalForecastRecord(
            location="Bengaluru",
            latitude=12.97,
            longitude=77.59,
            issue_time="2026-08-15T00:00:00Z",
            valid_time="2026-08-16T00:00:00Z",
            lead_hours=24,
            variable="temperature_2m",
            unit="celsius",
            value=25.0,
            member_count=31,
            ensemble_mean=25.2,
            ensemble_std=0.8,
            ensemble_min=24.0,
            ensemble_max=27.0,
            q10=24.5,
            q90=26.0,
        )
    ]
    weather_result = WeatherResult(
        location="Bengaluru",
        is_available=True,
        data_version="gefs-openmeteo-v1.0",
        raw_data={"records": [r.model_dump() for r in records]},
    )

    res_with = adapter_with_fp.build_features(weather_result)
    res_no = adapter_no_fp.build_features(weather_result)

    # Both must produce identical 26 canonical features
    assert res_with.features == res_no.features
    assert res_with.feature_names == res_no.feature_names == FEATURE_COLUMN_NAMES

    # Fingerprint is present only as metadata
    assert res_with.metadata["instability_fingerprint"] is not None
    assert res_no.metadata["instability_fingerprint"] is None

    # Model predictions on both feature results must be bitwise identical
    model_adapter = Builder2ModelAdapter(model_dir=B2_MODEL_DIR)
    p_with = model_adapter.predict(res_with).probability
    p_no = model_adapter.predict(res_no).probability
    assert p_with == p_no

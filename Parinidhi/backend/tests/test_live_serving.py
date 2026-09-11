"""Automated Unit Tests for Day 6 Live Model Serving & End-to-End Prediction Pipeline."""
import tempfile
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent
from backend.app.main import app
from backend.app.ml.artifacts import ModelArtifactManager
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import PredictionRequest, ReasonCode, RiskLevel, TrustState
from backend.app.schemas.weather import CanonicalForecastDataset, CanonicalForecastRecord
from backend.app.services.base import FeatureResult, WeatherResult
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_service import LiveLogisticModelService, UnavailableModelService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


def _create_mock_weather_result(location: str = "London") -> WeatherResult:
    """Create deterministic canonical forecast records for London."""
    records = []
    variables = ["temperature_2m", "surface_pressure", "wind_speed_10m", "relative_humidity_2m", "precipitation"]
    for i, var in enumerate(variables):
        rec = CanonicalForecastRecord(
            location=location,
            latitude=51.5074,
            longitude=-0.1278,
            issue_time="2026-08-26T00:00:00Z",
            valid_time="2026-08-29T12:00:00Z",
            lead_hours=84,
            variable=var,
            unit="celsius" if "temp" in var else "hPa" if "pressure" in var else "m/s" if "wind" in var else "%" if "humidity" in var else "mm",
            value=22.5 + i * 1.5,
            source="NOAA_GEFS_OPENMETEO",
        )
        records.append(rec)

    dataset = CanonicalForecastDataset(
        location=location,
        latitude=51.5074,
        longitude=-0.1278,
        issue_time="2026-08-26T00:00:00Z",
        source="NOAA_GEFS_OPENMETEO",
        records=records,
    )
    return WeatherResult(
        location=location,
        raw_data=dataset.model_dump(),
        data_version="gefs-openmeteo-v1.0",
        is_available=True,
        quality_flags={"qc_passed": True},
    )


def test_live_feature_service_build_features():
    """Test that LiveFeatureService generates 18-feature inference vectors without leakage."""
    feature_service = LiveFeatureService()
    assert feature_service.is_ready is True

    weather_result = _create_mock_weather_result("London")
    feat_result = feature_service.build_features(weather_result)

    assert feat_result.is_ready is True
    assert len(feat_result.feature_names) == 18
    assert "feature_matrix" in feat_result.metadata
    matrix = np.array(feat_result.metadata["feature_matrix"])
    assert matrix.shape == (5, 18)
    assert not np.isnan(matrix).any()


def test_live_logistic_model_service_predict_probability():
    """Test that LiveLogisticModelService generates real P(bust) strictly within [0.0, 1.0]."""
    model_service = LiveLogisticModelService()
    assert model_service.is_ready is True
    assert model_service.model_version == "baseline-logistic-v1.0"

    feature_service = LiveFeatureService()
    weather_result = _create_mock_weather_result("London")
    feat_result = feature_service.build_features(weather_result)

    model_result = model_service.predict(feat_result)
    assert model_result.is_ready is True
    assert model_result.probability is not None
    assert 0.0 <= model_result.probability <= 1.0
    assert model_result.model_version == "baseline-logistic-v1.0"


def test_missing_model_artifact_safe_abstention():
    """Test that missing model artifact causes ModelService to safely abstain with MODEL_NOT_READY."""
    with tempfile.TemporaryDirectory() as empty_dir:
        model_service = LiveLogisticModelService(artifacts_dir=empty_dir, artifact_name="nonexistent_model")
        assert model_service.is_ready is False

        feature_service = LiveFeatureService()
        weather_result = _create_mock_weather_result("London")
        feat_result = feature_service.build_features(weather_result)

        model_result = model_service.predict(feat_result)
        assert model_result.is_ready is False
        assert model_result.probability is None
        assert model_result.metadata.get("status") == ReasonCode.MODEL_NOT_READY.value


def test_end_to_end_agent_live_prediction():
    """Test ForecastBustAgent executing end-to-end live inference with real model."""
    feature_service = LiveFeatureService()
    model_service = LiveLogisticModelService()

    class MockLiveWeather(OpenMeteoGEFSWeatherService):
        def get_forecast(self, location: str, target_date=None) -> WeatherResult:
            return _create_mock_weather_result(location)

    agent = ForecastBustAgent(
        weather_service=MockLiveWeather(),
        feature_service=feature_service,
        model_service=model_service,
        safety_evaluator=SafetyEvaluator(),
    )

    req = PredictionRequest(location="London")
    response = agent.analyze(req)

    assert response.location == "London"
    assert response.bust_probability is not None
    assert 0.0 <= response.bust_probability <= 1.0
    assert response.risk_level in [RiskLevel.LOW, RiskLevel.ELEVATED, RiskLevel.CRITICAL]
    assert response.trust_state == TrustState.HIGH_CONFIDENCE
    assert response.abstain is False
    assert response.reason_codes == [ReasonCode.SUCCESS.value]
    assert response.model_version == "baseline-logistic-v1.0"
    assert response.data_version == "gefs-openmeteo-v1.0"


def test_end_to_end_predict_endpoint_with_live_pipeline(client: TestClient):
    """Test POST /v1/predict returning real model probability and high confidence on valid location."""
    class MockLiveWeather(OpenMeteoGEFSWeatherService):
        def get_forecast(self, location: str, target_date=None) -> WeatherResult:
            return _create_mock_weather_result(location)

    live_agent = ForecastBustAgent(
        weather_service=MockLiveWeather(),
        feature_service=LiveFeatureService(),
        model_service=LiveLogisticModelService(),
        safety_evaluator=SafetyEvaluator(),
    )

    app.dependency_overrides[get_forecast_bust_agent] = lambda: live_agent
    try:
        response = client.post("/v1/predict", json={"location": "Kolkata"})
        assert response.status_code == 200
        data = response.json()
        assert data["location"] == "Kolkata"
        assert data["bust_probability"] is not None
        assert 0.0 <= data["bust_probability"] <= 1.0
        assert data["abstain"] is False
        assert data["trust_state"] == "HIGH_CONFIDENCE"
        assert data["reason_codes"] == ["SUCCESS"]
        assert data["model_version"] == "baseline-logistic-v1.0"
    finally:
        app.dependency_overrides.clear()


def test_failed_weather_prerequisite_safely_abstains(client: TestClient):
    """Test that failed weather ingestion safely short-circuits without calling model."""
    class FailingWeather(OpenMeteoGEFSWeatherService):
        def get_forecast(self, location: str, target_date=None) -> WeatherResult:
            return WeatherResult(
                location=location,
                is_available=False,
                error="Upstream meteorological station timeout",
                metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
            )

    failing_agent = ForecastBustAgent(
        weather_service=FailingWeather(),
        feature_service=LiveFeatureService(),
        model_service=LiveLogisticModelService(),
        safety_evaluator=SafetyEvaluator(),
    )

    app.dependency_overrides[get_forecast_bust_agent] = lambda: failing_agent
    try:
        response = client.post("/v1/predict", json={"location": "London"})
        assert response.status_code == 200
        data = response.json()
        assert data["bust_probability"] is None
        assert data["risk_level"] is None
        assert data["abstain"] is True
        assert data["trust_state"] == "UNAVAILABLE"
        assert "DATA_UNAVAILABLE" in data["reason_codes"]
    finally:
        app.dependency_overrides.clear()

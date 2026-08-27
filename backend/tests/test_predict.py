"""Tests for POST /v1/predict endpoint and FastAPI dependency injection."""
import pytest
from fastapi.testclient import TestClient
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent
from backend.app.main import app
from backend.app.schemas.prediction import ReasonCode, RiskLevel, TrustState
from backend.app.services.base import (
    BaseFeatureService,
    BaseModelService,
    BaseWeatherService,
    FeatureResult,
    ModelResult,
    WeatherResult,
)
from backend.app.services.model_service import UnavailableModelService


def test_predict_valid_location_accepted(client: TestClient):
    """Test that POST /v1/predict accepts a valid location with HTTP 200."""
    response = client.post("/v1/predict", json={"location": "London"})
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "London"


def test_predict_bust_probability_is_null_when_model_unavailable(client: TestClient):
    """Test that bust_probability is strictly null (None) while model is unavailable."""
    unavailable_agent = ForecastBustAgent(model_service=UnavailableModelService())
    app.dependency_overrides[get_forecast_bust_agent] = lambda: unavailable_agent
    try:
        response = client.post("/v1/predict", json={"location": "Tokyo"})
        assert response.status_code == 200
        data = response.json()
        assert data["bust_probability"] is None
        assert data["risk_level"] is None
    finally:
        app.dependency_overrides.clear()


def test_predict_abstain_is_true_when_model_unavailable(client: TestClient):
    """Test that abstain flag is True while model is unavailable."""
    unavailable_agent = ForecastBustAgent(model_service=UnavailableModelService())
    app.dependency_overrides[get_forecast_bust_agent] = lambda: unavailable_agent
    try:
        response = client.post("/v1/predict", json={"location": "Paris"})
        assert response.status_code == 200
        data = response.json()
        assert data["abstain"] is True
    finally:
        app.dependency_overrides.clear()


def test_predict_trust_state_is_unavailable(client: TestClient):
    """Test that trust_state is UNAVAILABLE while model is unavailable."""
    unavailable_agent = ForecastBustAgent(model_service=UnavailableModelService())
    app.dependency_overrides[get_forecast_bust_agent] = lambda: unavailable_agent
    try:
        response = client.post("/v1/predict", json={"location": "Berlin"})
        assert response.status_code == 200
        data = response.json()
        assert data["trust_state"] == "UNAVAILABLE"
    finally:
        app.dependency_overrides.clear()


def test_predict_model_not_ready_in_reason_codes(client: TestClient):
    """Test that MODEL_NOT_READY is present in reason_codes list when model is unavailable."""
    unavailable_agent = ForecastBustAgent(model_service=UnavailableModelService())
    app.dependency_overrides[get_forecast_bust_agent] = lambda: unavailable_agent
    try:
        response = client.post("/v1/predict", json={"location": "New York"})
        assert response.status_code == 200
        data = response.json()
        assert "MODEL_NOT_READY" in data["reason_codes"]
    finally:
        app.dependency_overrides.clear()


def test_predict_with_optional_target_date(client: TestClient):
    """Test prediction request with an optional target_date provided when model is unavailable."""
    unavailable_agent = ForecastBustAgent(model_service=UnavailableModelService())
    app.dependency_overrides[get_forecast_bust_agent] = lambda: unavailable_agent
    try:
        response = client.post(
            "/v1/predict",
            json={"location": "Sydney", "target_date": "2026-09-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["location"] == "Sydney"
        assert data["abstain"] is True
        assert data["bust_probability"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {},  # Missing location
        {"location": ""},  # Empty string
        {"location": "   "},  # Whitespace only
        {"location": None},  # Null location
    ],
)
def test_predict_invalid_request_rejected(client: TestClient, invalid_payload: dict):
    """Test that invalid/empty requests are rejected with HTTP 422 Unprocessable Entity."""
    response = client.post("/v1/predict", json=invalid_payload)
    assert response.status_code == 422


def test_predict_dependency_injection_override(client: TestClient):
    """Test that FastAPI dependency override allows injecting a custom test agent."""

    class MockWeather(BaseWeatherService):
        def get_forecast(self, location: str, target_date=None) -> WeatherResult:
            return WeatherResult(location=location, is_available=True, data_version="gefs-v1.0")

    class MockFeature(BaseFeatureService):
        def build_features(self, weather_result: WeatherResult) -> FeatureResult:
            return FeatureResult(location=weather_result.location, is_ready=True)

    class MockModel(BaseModelService):
        def predict(self, feature_result: FeatureResult) -> ModelResult:
            return ModelResult(probability=0.15, model_version="lgbm-calibrated-v1", is_ready=True)

    custom_agent = ForecastBustAgent(
        weather_service=MockWeather(),
        feature_service=MockFeature(),
        model_service=MockModel(),
    )

    app.dependency_overrides[get_forecast_bust_agent] = lambda: custom_agent
    try:
        response = client.post("/v1/predict", json={"location": "Geneva"})
        assert response.status_code == 200
        data = response.json()
        assert data["location"] == "Geneva"
        assert data["bust_probability"] == 0.15
        assert data["risk_level"] == "LOW"
        assert data["trust_state"] == "HIGH_CONFIDENCE"
        assert data["abstain"] is False
        assert data["model_version"] == "lgbm-calibrated-v1"
        assert data["data_version"] == "gefs-v1.0"
    finally:
        app.dependency_overrides.clear()


# =====================================================================
# REGRESSION TESTS — API VALIDATION & SAFETY CONTRACT
# =====================================================================


def test_predict_valid_kolkata_positive_lead_accepted(client: TestClient):
    """Test A: Valid Kolkata with positive lead time is accepted and evaluated."""
    payload = {
        "issue_time": "2026-08-27T00:00:00Z",
        "valid_time": "2026-08-28T00:00:00Z",
        "region_id": "Kolkata",
        "variable": "temperature_2m",
        "model_type": None,
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Kolkata"
    assert data["abstain"] is False
    assert data["bust_probability"] is not None
    assert 0.0 <= data["bust_probability"] <= 1.0
    assert data["trust_state"] == "HIGH_CONFIDENCE"
    assert ReasonCode.SUCCESS.value in data["reason_codes"]


def test_predict_atlantis_safely_abstained(client: TestClient):
    """Test B: Atlantis unknown region returns safe abstention without reaching model."""
    payload = {
        "issue_time": "2026-08-27T00:00:00Z",
        "valid_time": "2026-08-28T00:00:00Z",
        "region_id": "Atlantis",
        "variable": "temperature_2m",
        "model_type": None,
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Atlantis"
    assert data["abstain"] is True
    assert data["bust_probability"] is None
    assert data["risk_level"] is None
    assert data["trust_state"] == "UNAVAILABLE"
    assert ReasonCode.INVALID_LOCATION.value in data["reason_codes"]


def test_predict_negative_lead_time_rejected(client: TestClient):
    """Test C: valid_time before issue_time (negative lead) is rejected with 422."""
    payload = {
        "issue_time": "2026-08-28T00:00:00Z",
        "valid_time": "2026-08-27T00:00:00Z",
        "region_id": "Kolkata",
        "variable": "temperature_2m",
        "model_type": None,
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json())
    assert "strictly after issue_time" in err_detail or "Negative or zero" in err_detail


def test_predict_zero_lead_time_rejected(client: TestClient):
    """Test D: valid_time equal to issue_time (lead=0) is rejected with 422 for forecast inference."""
    payload = {
        "issue_time": "2026-08-27T00:00:00Z",
        "valid_time": "2026-08-27T00:00:00Z",
        "region_id": "Kolkata",
        "variable": "temperature_2m",
        "model_type": None,
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json())
    assert "strictly after issue_time" in err_detail or "Negative or zero" in err_detail


def test_predict_excessive_lead_time_rejected(client: TestClient):
    """Test E: Extremely long lead time (> 384h / 16 days) is rejected with 422."""
    payload = {
        "issue_time": "2026-08-27T00:00:00Z",
        "valid_time": "2026-09-20T00:00:00Z",  # 24 days = 576h > 384h
        "region_id": "Kolkata",
        "variable": "temperature_2m",
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json())
    assert "exceeds the maximum supported forecast horizon" in err_detail


def test_predict_malformed_timestamp_rejected(client: TestClient):
    """Test F: Malformed timestamp format is rejected with 422."""
    payload = {
        "issue_time": "not-a-valid-timestamp",
        "valid_time": "2026-08-28T00:00:00Z",
        "location": "Kolkata",
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422


def test_predict_unsupported_variable_rejected(client: TestClient):
    """Test G: Unsupported forecast variable is rejected with 422."""
    payload = {
        "location": "Kolkata",
        "variable": "unsupported_crypto_metric",
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json())
    assert "Unsupported forecast variable" in err_detail


def test_predict_unsupported_model_type_rejected(client: TestClient):
    """Test H: Unsupported model_type override is rejected with 422."""
    payload = {
        "location": "Kolkata",
        "model_type": "deep_transformer_v99",
    }
    response = client.post("/v1/predict", json=payload)
    assert response.status_code == 422
    err_detail = str(response.json())
    assert "Unsupported model_type" in err_detail


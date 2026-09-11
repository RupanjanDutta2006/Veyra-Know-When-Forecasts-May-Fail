"""Day 7 Final Integration & System Robustness Automated Tests."""
import pytest
from fastapi.testclient import TestClient
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent
from backend.app.main import app
from backend.app.schemas.prediction import PredictionRequest, ReasonCode, RiskLevel, TrustState
from backend.app.schemas.weather import CanonicalForecastDataset, CanonicalForecastRecord
from backend.app.services.base import FeatureResult, ModelResult, WeatherResult
from backend.app.services.feature_service import LiveFeatureService
from backend.app.services.model_service import LiveLogisticModelService, UnavailableModelService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_location_normalization_and_whitespace(client: TestClient):
    """Test that location input is safely normalized across whitespace and casing."""
    weather_svc = OpenMeteoGEFSWeatherService()
    assert weather_svc.resolve_coordinates("  london  ") == (51.5074, -0.1278)
    assert weather_svc.resolve_coordinates("LONDON") == (51.5074, -0.1278)
    assert weather_svc.resolve_coordinates("  22.5726 , 88.3639 ") == (22.5726, 88.3639)


def test_unsupported_location_returns_invalid_location_reason(client: TestClient):
    """Test that an unresolvable location returns safe abstention with INVALID_LOCATION reason code."""
    response = client.post("/v1/predict", json={"location": "NonexistentCityXYZ"})
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "NonexistentCityXYZ"
    assert data["abstain"] is True
    assert data["bust_probability"] is None
    assert data["trust_state"] == "UNAVAILABLE"
    assert ReasonCode.INVALID_LOCATION.value in data["reason_codes"]


def test_multiple_supported_locations_live_predictions(client: TestClient):
    """Test that multiple supported benchmark locations return valid response contract (live or safe abstention on network outage)."""
    for city in ["Delhi", "Kolkata", "Mumbai"]:
        response = client.post("/v1/predict", json={"location": city})
        assert response.status_code == 200
        data = response.json()
        assert data["location"] == city
        if not data["abstain"]:
            assert data["bust_probability"] is not None
            assert 0.0 <= data["bust_probability"] <= 1.0
            assert data["trust_state"] in [TrustState.HIGH_CONFIDENCE.value, TrustState.MODERATE_CONFIDENCE.value, TrustState.LOW_CONFIDENCE.value]
            assert ReasonCode.SUCCESS.value in data["reason_codes"]
            assert data["model_version"] == "veyra-v3-benchmark-lightgbm"
            assert data["data_version"] == "gfs-ensemble-openmeteo-v2.0"
        else:
            assert any(rc in data["reason_codes"] for rc in [ReasonCode.DATA_UNAVAILABLE.value, ReasonCode.DATA_NOT_READY.value, ReasonCode.QC_FAILED.value])


def test_model_serving_is_read_only():
    """Test that LiveFeatureService and LiveLogisticModelService perform inference strictly in read-only mode."""
    feat_svc = LiveFeatureService()
    model_svc = LiveLogisticModelService()

    # Pre-inference parameter snapshots
    initial_means = feat_svc.pipeline.means.copy()
    initial_stds = feat_svc.pipeline.stds.copy()
    initial_coefs = model_svc.model.model.coef_.copy()
    initial_intercept = model_svc.model.model.intercept_.copy()

    # Create dummy records
    recs = [
        CanonicalForecastRecord(
            location="London",
            latitude=51.5074,
            longitude=-0.1278,
            issue_time="2026-08-26T00:00:00Z",
            valid_time="2026-08-27T00:00:00Z",
            lead_hours=24,
            variable="temperature_2m",
            unit="celsius",
            value=20.0,
            source="NOAA_GEFS_OPENMETEO",
        )
    ]
    ds = CanonicalForecastDataset(
        location="London", latitude=51.5074, longitude=-0.1278, issue_time="2026-08-26T00:00:00Z", source="NOAA_GEFS_OPENMETEO", records=recs
    )
    w_res = WeatherResult(location="London", raw_data=ds.model_dump(), is_available=True)

    feat_res = feat_svc.build_features(w_res)
    model_res = model_svc.predict(feat_res)

    assert model_res.is_ready is True

    # Post-inference validation: zero mutation of scaling or model weights
    assert feat_svc.pipeline.means == initial_means
    assert feat_svc.pipeline.stds == initial_stds
    assert (model_svc.model.model.coef_ == initial_coefs).all()
    assert (model_svc.model.model.intercept_ == initial_intercept).all()


def test_failure_matrix_destructions_safe_abstention():
    """Test comprehensive edge-case failure matrix ensuring zero crashes and safe abstentions."""
    feat_svc = LiveFeatureService()
    model_svc = LiveLogisticModelService()

    # 1. Corrupted feature result with wrong dimension
    corrupted_feat = FeatureResult(location="London", features={"f1": 1.0}, feature_names=["f1"], is_ready=True)
    res_dim = model_svc.predict(corrupted_feat)
    assert res_dim.is_ready is False
    assert res_dim.probability is None

    # 2. Weather result with missing raw records
    empty_weather = WeatherResult(location="London", raw_data={}, is_available=True)
    res_empty = feat_svc.build_features(empty_weather)
    assert res_empty.is_ready is False

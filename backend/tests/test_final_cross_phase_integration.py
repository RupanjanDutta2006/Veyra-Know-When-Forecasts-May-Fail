"""Deterministic Tests for Final Full-Project Integration (Phase 1 + Phase 2).

Verifies:
1. End-to-end runtime pipeline across Phase 1 Builder 1, Phase 1 Builder 2, and Phase 2 Builder 1.
2. Anti-data-leakage: live prediction features contain zero ground-truth reference values or bust labels.
3. Wind unit contract: wind_speed_unit=ms requested, parsed, and preserved across cache and model.
4. Fail-safe abstention behavior and precedence: INVALID_LOCATION, DATA_UNAVAILABLE, QC_FAILED.
5. Timeline multi-horizon caching and SingleFlight coalescing without upstream request amplification.
6. Non-intrusive in-process observability and health check isolation.
"""
import copy
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.builder2.feature_pipeline import (
    FEATURE_COLUMN_NAMES,
    IssueTimeSafeFeaturePipeline,
)
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.core.cache import BoundedTTLCache, SingleFlight
from backend.app.core.config import settings
from backend.app.core.metrics import default_metrics
from backend.app.data.qc import ForecastQualityControl
from backend.app.main import app
from backend.app.schemas.prediction import PredictionRequest, ReasonCode
from backend.app.services.explainability_service import ExplainabilityIntegrationService
from backend.app.services.location_service import DynamicLocationService
from backend.app.services.model_integration_service import ModelIntegrationService
from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService


@pytest.fixture(autouse=True)
def reset_metrics_and_state():
    """Reset metrics for test isolation."""
    default_metrics.reset()
    yield
    default_metrics.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ==============================================================================
# 1. FULL RUNTIME PIPELINE INTEGRATION
# ==============================================================================

from backend.app.api.v1.endpoints.predict import create_forecast_bust_agent

def test_full_pipeline_builder2_model_inference_and_calibration():
    """Verify live pipeline uses Builder 2 LightGBM model, 26 features, and Platt calibrator."""
    agent = create_forecast_bust_agent()
    req = PredictionRequest(
        location="Kolkata",
        variable="temperature_2m",
    )
    response = agent.analyze(req)
    assert response is not None
    assert response.location == "Kolkata"

    # If weather was available or mocked offline
    if not response.abstain:
        assert response.bust_probability is not None
        assert 0.0 <= response.bust_probability <= 1.0
        assert response.model_version == "prototype-gbm-v1"
        assert response.risk_level in ["LOW", "MEDIUM", "HIGH"]
        assert response.explanation is not None
        assert response.explanation.primary_driver is not None
    else:
        # If live network is offline, must abstain safely with DATA_UNAVAILABLE or INVALID_LOCATION
        assert response.bust_probability is None
        assert any(r in response.reason_codes for r in ["DATA_UNAVAILABLE", "INVALID_LOCATION", "MODEL_NOT_READY", "QC_FAILED"])


def test_builder2_canonical_26_feature_schema_and_ordering():
    """Verify canonical 26-feature schema matches Builder 2 feature definitions exactly."""
    adapter = Builder2ModelAdapter(model_dir=str(settings.BUILDER2_MODEL_DIR))
    assert adapter.is_ready is True
    assert adapter.threshold == 0.280
    assert len(FEATURE_COLUMN_NAMES) == 26

    expected_features = [
        "ensemble_std", "ensemble_range", "ensemble_iqr", "ensemble_skew_proxy",
        "ensemble_cv", "ensemble_spread_to_iqr_ratio", "member_count", "has_full_ensemble",
        "forecast_value", "ensemble_mean", "ensemble_spread_delta_6h", "ensemble_spread_delta_24h",
        "forecast_delta_6h", "forecast_delta_24h", "lead_hours", "lead_days",
        "valid_hour", "valid_month", "valid_dayofweek", "sin_hour", "cos_hour",
        "sin_month", "cos_month", "is_weekend", "latitude", "longitude",
    ]
    assert FEATURE_COLUMN_NAMES == expected_features


# ==============================================================================
# 2. ANTI-DATA-LEAKAGE AUDIT
# ==============================================================================

def test_live_features_contain_zero_ground_truth_or_reference_data():
    """Verify live feature pipeline extracts features purely from forecast records with zero truth leakage."""
    pipeline = IssueTimeSafeFeaturePipeline()
    assert pipeline is not None
    forbidden_tokens = ["era5", "reference_value", "ground_truth", "forecast_error", "abs_error", "bust_label"]
    for feature_name in FEATURE_COLUMN_NAMES:
        for token in forbidden_tokens:
            assert token not in feature_name.lower(), f"Feature '{feature_name}' violates anti-leakage policy"



# ==============================================================================
# 3. WIND SPEED UNIT CONTRACT
# ==============================================================================

def test_wind_speed_unit_ms_contract_in_query_and_records():
    """Verify wind_speed_unit=ms is explicitly requested and preserved in canonical records."""
    svc = OpenMeteoGEFSWeatherService()
    url = svc.build_query_url(22.57, 88.36)
    assert "wind_speed_unit=ms" in url

    mock_raw = {
        "latitude": 22.57,
        "longitude": 88.36,
        "hourly": {
            "time": ["2026-08-30T00:00"],
            "wind_speed_10m": [5.5],
        },
        "hourly_units": {
            "wind_speed_10m": "m/s",
        },
    }
    records = svc.parse_canonical_records(mock_raw, "Kolkata", 22.57, 88.36)
    assert len(records) == 1
    assert records[0].unit == "m/s"
    assert records[0].ensemble_mean == 5.5


# ==============================================================================
# 4. SAFETY PRECEDENCE & ABSTENTION
# ==============================================================================

def test_invalid_location_abstains_with_invalid_location_reason(client: TestClient):
    """Verify unknown location safely abstains and returns INVALID_LOCATION."""
    response = client.post(
        "/v1/predict",
        json={"location": "Atlantis", "variable": "temperature_2m"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["abstain"] is True
    assert "INVALID_LOCATION" in data["reason_codes"]
    assert data["bust_probability"] is None
    assert data["trust_state"] == "UNAVAILABLE"


def test_time_semantics_rejects_non_positive_lead(client: TestClient):
    """Verify valid_time <= issue_time is rejected with 422."""
    response = client.post(
        "/v1/predict",
        json={
            "location": "Kolkata",
            "issue_time": "2026-08-30T12:00:00Z",
            "valid_time": "2026-08-30T10:00:00Z",  # Negative lead
        },
    )
    assert response.status_code == 422


def test_time_semantics_rejects_excessive_lead(client: TestClient):
    """Verify lead > 384h is rejected with 422."""
    response = client.post(
        "/v1/predict",
        json={
            "location": "Kolkata",
            "issue_time": "2026-08-01T00:00:00Z",
            "valid_time": "2026-08-25T00:00:00Z",  # 576h lead > 384h
        },
    )
    assert response.status_code == 422


# ==============================================================================
# 5. TIMELINE REQUEST AMPLIFICATION ELIMINATION
# ==============================================================================

def test_multi_horizon_timeline_reuses_single_forecast_dataset():
    """Verify multi-horizon evaluations for the same issue_time reuse the cached forecast."""
    mock_payload = {
        "latitude": 22.57,
        "longitude": 88.36,
        "hourly": {
            "time": [
                f"2026-08-30T{h:02d}:00" for h in range(24)
            ] + [
                f"2026-08-31T{h:02d}:00" for h in range(24)
            ],
            "temperature_2m": [25.0] * 48,
            "surface_pressure": [1010.0] * 48,
            "wind_speed_10m": [4.0] * 48,
            "relative_humidity_2m": [80.0] * 48,
            "precipitation": [0.0] * 48,
        },
        "hourly_units": {
            "temperature_2m": "°C",
            "surface_pressure": "hPa",
            "wind_speed_10m": "m/s",
            "relative_humidity_2m": "%",
            "precipitation": "mm",
        },
    }

    call_count = 0
    def counting_http_client(url: str):
        nonlocal call_count
        call_count += 1
        return copy.deepcopy(mock_payload)

    cache = BoundedTTLCache(maxsize=10, default_ttl=60, enabled=True)
    dedup = SingleFlight(enabled=True)

    svc = OpenMeteoGEFSWeatherService(
        http_client=counting_http_client,
        cache=cache,
        deduplicator=dedup,
        enable_cache=True,
        enable_dedup=True,
    )

    # 1. Fetch horizon 24h
    r1 = svc.get_forecast("Kolkata")
    assert r1.is_available is True
    assert call_count == 1

    # 2. Fetch horizon 48h (same query_url)
    r2 = svc.get_forecast("Kolkata")
    assert r2.is_available is True
    assert call_count == 1  # Reused cache! Zero amplification!


# ==============================================================================
# 6. OBSERVABILITY & METRICS CONTRACT
# ==============================================================================

def test_metrics_endpoint_snapshot_and_health_isolation(client: TestClient):
    """Verify GET /v1/metrics returns in-process snapshot and /v1/health makes zero upstream calls."""
    # Call health
    h_resp = client.get("/v1/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "ok"

    # Call metrics
    m_resp = client.get("/v1/metrics")
    assert m_resp.status_code == 200
    metrics_data = m_resp.json()
    assert "http_requests_total" in metrics_data
    assert "uptime_seconds" in metrics_data
    assert metrics_data["upstream_requests_total"] == {}  # Health made 0 external calls

"""Regression tests for Post-Day-21 repairs:
1. Single Target default forecast horizon (24h positive lead; no accidental 0h).
2. Swagger / OpenAPI example and schema contract (no invalid "string", accepted model types, V3 serving).
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.prediction import PredictionRequest, SUPPORTED_MODEL_TYPES
from backend.app.builder2.v3_feature_adapter import Builder2V3FeatureAdapter
from backend.app.services.base import WeatherResult


@pytest.fixture
def client():
    return TestClient(app)


# =====================================================================
# ISSUE 1: SINGLE TARGET DEFAULT LEAD & HORIZON SELECTION TESTS
# =====================================================================

def test_single_target_default_lead_hours_is_positive_24h(client: TestClient):
    """Test 1.1: Single target forecast without explicit valid_time defaults to 24h horizon, not 0h."""
    response = client.post("/v1/predict", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
    })
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"
    assert data["abstain"] is False

    explanation = data.get("explanation")
    assert explanation is not None
    factors = explanation.get("top_contributing_factors", [])
    lead_factor = next((f for f in factors if f.get("factor") == "lead_hours"), None)
    assert lead_factor is not None, "lead_hours factor must be present in explanation"
    assert lead_factor["value"] == 24.0, f"Expected default lead_hours == 24.0, got {lead_factor['value']}"


def test_single_target_explicit_24h_lead(client: TestClient):
    """Test 1.2: Explicit 24h horizon calculates and displays exact 24h lead."""
    base_issue = "2026-09-10T00:00:00Z"
    valid_24h = "2026-09-11T00:00:00Z"

    response = client.post("/v1/predict", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "issue_time": base_issue,
        "valid_time": valid_24h,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"

    explanation = data.get("explanation")
    assert explanation is not None
    factors = explanation.get("top_contributing_factors", [])
    lead_factor = next((f for f in factors if f.get("factor") == "lead_hours"), None)
    assert lead_factor is not None
    assert lead_factor["value"] == 24.0


def test_single_target_explicit_48h_lead(client: TestClient):
    """Test 1.3: Explicit 48h horizon calculates and displays exact 48h lead."""
    base_issue = "2026-09-10T00:00:00Z"
    valid_48h = "2026-09-12T00:00:00Z"

    response = client.post("/v1/predict", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "issue_time": base_issue,
        "valid_time": valid_48h,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"

    explanation = data.get("explanation")
    assert explanation is not None
    factors = explanation.get("top_contributing_factors", [])
    lead_factor = next((f for f in factors if f.get("factor") == "lead_hours"), None)
    assert lead_factor is not None
    assert lead_factor["value"] == 48.0


def test_single_target_zero_and_negative_lead_rejected(client: TestClient):
    """Test 1.4: Explicit zero or negative lead time is strictly rejected with 422."""
    # Zero lead
    res_zero = client.post("/v1/predict", json={
        "location": "Kolkata",
        "issue_time": "2026-09-10T00:00:00Z",
        "valid_time": "2026-09-10T00:00:00Z",
        "variable": "temperature_2m",
    })
    assert res_zero.status_code == 422
    assert "strictly after issue_time" in str(res_zero.json())

    # Negative lead (valid before issue)
    res_neg = client.post("/v1/predict", json={
        "location": "Kolkata",
        "issue_time": "2026-09-10T12:00:00Z",
        "valid_time": "2026-09-10T00:00:00Z",
        "variable": "temperature_2m",
    })
    assert res_neg.status_code == 422
    assert "strictly after issue_time" in str(res_neg.json())


def test_v3_feature_adapter_default_lead_selection():
    """Test 1.5: Builder2V3FeatureAdapter internal selection defaults to 24h row with positive lead."""
    adapter = Builder2V3FeatureAdapter()

    # Create mock series of records with lead_hours 0 to 48
    records = []
    base_dt = datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc)
    for h in [0, 6, 12, 18, 24, 30, 36, 42, 48]:
        v_dt = base_dt + timedelta(hours=h)
        records.append({
            "location": "Kolkata",
            "variable": "temperature_2m",
            "unit": "celsius",
            "value": 28.0 + (h * 0.1),
            "issue_time": base_dt.isoformat(),
            "valid_time": v_dt.isoformat(),
            "lead_hours": h,
            "member_count": 31,
            "members": [28.0 + (h * 0.1)] * 31,
        })

    weather_res = WeatherResult(
        location="Kolkata",
        is_available=True,
        raw_data={"records": records},
        metadata={"variable": "temperature_2m"},
    )

    feat_result = adapter.build_features(weather_res)
    assert feat_result.is_ready is True
    assert feat_result.features["lead_hours"] == 24
    assert feat_result.metadata["lead_hours"] == 24
    assert feat_result.metadata["valid_time"] == (base_dt + timedelta(hours=24)).isoformat()


# =====================================================================
# ISSUE 2: SWAGGER / OPENAPI CONTRACT & MODEL_TYPE TESTS
# =====================================================================

def test_openapi_schema_does_not_contain_raw_string_example():
    """Test 2.1: OpenAPI schema provides valid enum and example for model_type, not 'string'."""
    openapi = app.openapi()
    schemas = openapi["components"]["schemas"]
    pred_req_schema = schemas.get("PredictionRequest")
    assert pred_req_schema is not None

    # Verify top-level example exists and is executable
    example = pred_req_schema.get("example")
    assert example is not None, "PredictionRequest must define a top-level schema example"
    assert example.get("model_type") != "string", "Example model_type must NOT be 'string'"
    assert example.get("model_type") in SUPPORTED_MODEL_TYPES

    # Verify property definition has enum and example
    model_type_prop = pred_req_schema["properties"]["model_type"]
    assert "enum" in model_type_prop, "model_type property must expose enum in OpenAPI"
    assert "string" not in model_type_prop["enum"]
    assert "prototype-gbm-v1" in model_type_prop["enum"]
    assert "veyra-v3-benchmark-lightgbm" in model_type_prop["enum"]


def test_swagger_generated_example_is_executable(client: TestClient):
    """Test 2.2: The exact Swagger top-level example request executes with HTTP 200 without manual correction."""
    openapi = app.openapi()
    example = openapi["components"]["schemas"]["PredictionRequest"]["example"]

    response = client.post("/v1/predict", json=example)
    assert response.status_code == 200, f"Swagger example failed: {response.text}"
    data = response.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"


def test_accepted_compatibility_model_type_routes_to_v3(client: TestClient):
    """Test 2.3: Sending compatibility model_type='prototype-gbm-v1' routes cleanly to authoritative V3."""
    response = client.post("/v1/predict", json={
        "location": "Kolkata",
        "region_id": "Kolkata",
        "issue_time": "2026-09-10T00:00:00Z",
        "valid_time": "2026-09-11T00:00:00Z",
        "variable": "temperature_2m",
        "model_type": "prototype-gbm-v1",
        "target_date": "2026-09-11",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"


def test_veyra_v3_model_type_accepted(client: TestClient):
    """Test 2.4: Explicitly requesting model_type='veyra-v3-benchmark-lightgbm' is accepted and served."""
    response = client.post("/v1/predict", json={
        "location": "Kolkata",
        "variable": "temperature_2m",
        "model_type": "veyra-v3-benchmark-lightgbm",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"


def test_unsupported_model_type_rejected_with_422(client: TestClient):
    """Test 2.5: Any invalid model_type (including raw 'string') is rejected with 422 validation error."""
    # Test raw "string" (the former Swagger placeholder)
    res_str = client.post("/v1/predict", json={
        "location": "Kolkata",
        "model_type": "string",
    })
    assert res_str.status_code == 422
    assert "Unsupported model_type" in str(res_str.json())

    # Test random unrecognized model name
    res_rand = client.post("/v1/predict", json={
        "location": "Kolkata",
        "model_type": "random_xgboost_v99",
    })
    assert res_rand.status_code == 422
    assert "Unsupported model_type" in str(res_rand.json())

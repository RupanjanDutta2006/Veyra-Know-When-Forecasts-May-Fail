"""Unit and integration tests for Phase 2 Day 13: Explainability Integration."""
import math
import pytest
from fastapi.testclient import TestClient

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.builder2.schemas import (
    ContributingFactor as Builder2ContributingFactor,
    ExplanationItem as Builder2ExplanationItem,
)
from backend.app.main import app
from backend.app.schemas.explainability import (
    ContributingFactor,
    ExplanationItem,
    ExplainabilityStatus,
    ModelExplanationResponse,
)
from backend.app.schemas.multi_location import (
    MultiLocationPredictionItemResult,
    MultiLocationPredictionRequest,
    MultiLocationPredictionResult,
)
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.base import FeatureResult, ModelResult, WeatherResult
from backend.app.services.explainability_service import (
    BaseExplainabilityService,
    ExplainabilityIntegrationService,
)
from backend.app.services.multi_location_service import MultiLocationService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def explainer_service() -> ExplainabilityIntegrationService:
    return ExplainabilityIntegrationService(default_threshold=0.280)


# =====================================================================
# 1. Schema Validation & Numerical Finiteness Tests
# =====================================================================

def test_contributing_factor_schema_valid():
    """Verify ContributingFactor accepts valid finite floats and None."""
    factor1 = ContributingFactor(factor="ensemble_std", value=2.45, signal="HIGH_ENSEMBLE_SPREAD")
    assert factor1.factor == "ensemble_std"
    assert factor1.value == 2.45
    assert factor1.signal == "HIGH_ENSEMBLE_SPREAD"

    factor2 = ContributingFactor(factor="forecast_delta_24h", value=None, signal="NO_PRIOR_CYCLE_BASELINE")
    assert factor2.value is None


def test_contributing_factor_schema_rejects_nan_and_inf():
    """Verify ContributingFactor rejects NaN, +Inf, and -Inf values."""
    with pytest.raises(ValueError, match="finite"):
        ContributingFactor(factor="ensemble_std", value=float("nan"), signal="HIGH_ENSEMBLE_SPREAD")

    with pytest.raises(ValueError, match="finite"):
        ContributingFactor(factor="ensemble_std", value=float("inf"), signal="HIGH_ENSEMBLE_SPREAD")

    with pytest.raises(ValueError, match="finite"):
        ContributingFactor(factor="ensemble_std", value=float("-inf"), signal="HIGH_ENSEMBLE_SPREAD")


def test_explanation_item_serialization():
    """Verify ExplanationItem serializes properly to dict and JSON."""
    item = ExplanationItem(
        primary_driver="stable_ensemble_agreement",
        driver_summary="Forecast is stable with low ensemble dispersion.",
        top_contributing_factors=[
            ContributingFactor(factor="ensemble_std", value=0.15, signal="LOW_ENSEMBLE_SPREAD"),
            ContributingFactor(factor="lead_hours", value=24.0, signal="SHORT_RANGE_HORIZON"),
        ],
    )
    data = item.model_dump()
    assert data["primary_driver"] == "stable_ensemble_agreement"
    assert len(data["top_contributing_factors"]) == 2
    assert data["top_contributing_factors"][0]["factor"] == "ensemble_std"


def test_model_explanation_response_schema():
    """Verify ModelExplanationResponse container structure."""
    resp = ModelExplanationResponse(
        model_name="builder2_gbm",
        model_version="prototype-gbm-v1",
        explainability_status=ExplainabilityStatus.AVAILABLE,
        explanation=ExplanationItem(
            primary_driver="stable_ensemble_agreement",
            driver_summary="Stable forecast.",
            top_contributing_factors=[],
        ),
        reason_codes=["SUCCESS"],
    )
    assert resp.explainability_status == ExplainabilityStatus.AVAILABLE
    assert resp.model_name == "builder2_gbm"


# =====================================================================
# 2. Explainability Service Logic & Deterministic Signals
# =====================================================================

def test_explain_low_risk_stable_signals(explainer_service: ExplainabilityIntegrationService):
    """Verify low risk probability (< threshold) produces stable_ensemble_agreement driver."""
    features = {
        "forecast_delta_24h": 0.2,
        "ensemble_std": 0.4,
        "lead_hours": 36,
        "ensemble_spread_delta_24h": 0.1,
    }
    explanation = explainer_service.explain(
        feature_row=features,
        bust_probability=0.08,
        threshold=0.280,
    )
    assert explanation is not None
    assert explanation.primary_driver == "stable_ensemble_agreement"
    assert "stable" in explanation.driver_summary.lower()

    # Verify factors
    signals = {f.factor: f.signal for f in explanation.top_contributing_factors}
    assert signals["forecast_delta_24h"] == "LOW_REVISION_DRIFT"
    assert signals["ensemble_std"] == "LOW_ENSEMBLE_SPREAD"
    assert signals["lead_hours"] == "SHORT_RANGE_HORIZON"


def test_explain_high_risk_revision_drift(explainer_service: ExplainabilityIntegrationService):
    """Verify high risk driven by 24h revision drift >= 2.0 units."""
    features = {
        "forecast_delta_24h": 3.5,
        "ensemble_std": 0.5,
        "lead_hours": 48,
    }
    explanation = explainer_service.explain(
        feature_row=features,
        bust_probability=0.45,
        threshold=0.280,
    )
    assert explanation is not None
    assert explanation.primary_driver == "rapid_inter_cycle_revision"
    assert "rapid 24h run-to-run" in explanation.driver_summary


def test_explain_high_risk_ensemble_uncertainty(explainer_service: ExplainabilityIntegrationService):
    """Verify high risk driven by high ensemble spread."""
    features = {
        "forecast_delta_24h": 0.1,
        "ensemble_std": 4.2,
        "lead_hours": 48,
    }
    explanation = explainer_service.explain(
        feature_row=features,
        bust_probability=0.55,
        threshold=0.280,
    )
    assert explanation is not None
    assert explanation.primary_driver == "high_ensemble_uncertainty"
    assert "ensemble dispersion" in explanation.driver_summary


def test_explain_high_risk_extended_horizon(explainer_service: ExplainabilityIntegrationService):
    """Verify high risk driven by extended range degradation (lead >= 168h)."""
    features = {
        "forecast_delta_24h": 0.1,
        "ensemble_std": 0.8,
        "lead_hours": 240,
    }
    explanation = explainer_service.explain(
        feature_row=features,
        bust_probability=0.32,
        threshold=0.280,
    )
    assert explanation is not None
    assert explanation.primary_driver == "extended_horizon_uncertainty"


# =====================================================================
# 3. Anti-Leakage & Safety Verification Tests
# =====================================================================

def test_explainability_rejects_forbidden_ground_truth_leakage(explainer_service: ExplainabilityIntegrationService):
    """Ensure explainability strictly returns None if forbidden ground-truth fields appear."""
    forbidden_features = [
        {"forecast_delta_24h": 0.5, "ensemble_std": 1.2, "lead_hours": 24, "era5": 22.5},
        {"forecast_delta_24h": 0.5, "ensemble_std": 1.2, "lead_hours": 24, "observation": 22.5},
        {"forecast_delta_24h": 0.5, "ensemble_std": 1.2, "lead_hours": 24, "forecast_error": 4.2},
        {"forecast_delta_24h": 0.5, "ensemble_std": 1.2, "lead_hours": 24, "bust_label": 1},
    ]
    for feat_row in forbidden_features:
        result = explainer_service.explain(
            feature_row=feat_row,
            bust_probability=0.15,
        )
        assert result is None, f"Explainability must reject leakage feature row: {feat_row}"


def test_explainability_handles_non_finite_features(explainer_service: ExplainabilityIntegrationService):
    """Ensure NaN and Inf values in feature dictionary are sanitized safely."""
    features_with_nan = {
        "forecast_delta_24h": float("nan"),
        "ensemble_std": float("inf"),
        "lead_hours": 72,
    }
    explanation = explainer_service.explain(
        feature_row=features_with_nan,
        bust_probability=0.10,
    )
    assert explanation is not None
    assert explanation.primary_driver == "stable_ensemble_agreement"
    # Finiteness check on all extracted factors
    for f in explanation.top_contributing_factors:
        if f.value is not None:
            assert not math.isnan(f.value)
            assert not math.isinf(f.value)


def test_explainability_abstained_prediction_returns_none(explainer_service: ExplainabilityIntegrationService):
    """Ensure abstained or missing probability evaluations return None."""
    assert explainer_service.explain(feature_row={"lead_hours": 24}, bust_probability=None) is None
    assert explainer_service.explain(feature_row={"lead_hours": 24}, bust_probability=0.25, is_abstained=True) is None
    assert explainer_service.explain(feature_row={}, bust_probability=0.25) is None
    assert explainer_service.explain(feature_row=None, bust_probability=0.25) is None


def test_validate_explanation_from_builder2_dataclass(explainer_service: ExplainabilityIntegrationService):
    """Verify conversion of Builder 2 internal dataclass ExplanationItem to Pydantic."""
    b2_item = Builder2ExplanationItem(
        primary_driver="stable_ensemble_agreement",
        driver_summary="Stable test summary.",
        top_contributing_factors=[
            Builder2ContributingFactor(factor="lead_hours", value=48.0, signal="MEDIUM_RANGE_HORIZON"),
        ],
    )
    pydantic_item = explainer_service.validate_explanation(b2_item)
    assert isinstance(pydantic_item, ExplanationItem)
    assert pydantic_item.primary_driver == "stable_ensemble_agreement"
    assert len(pydantic_item.top_contributing_factors) == 1
    assert pydantic_item.top_contributing_factors[0].value == 48.0


# =====================================================================
# 4. End-to-End API Integration Tests (Single & Batch)
# =====================================================================

def test_single_prediction_api_returns_valid_explanation(client: TestClient):
    """Verify POST /v1/predict returns structured explanation for valid location."""
    response = client.post("/v1/predict", json={"location": "London"})
    assert response.status_code == 200
    data = response.json()

    assert data["location"] == "London"
    assert data["abstain"] is False
    assert data["bust_probability"] is not None
    assert data["trust_state"] == "HIGH_CONFIDENCE"

    # Verify explanation field presence and structure
    assert "explanation" in data
    explanation = data["explanation"]
    assert explanation is not None
    assert "primary_driver" in explanation
    assert "driver_summary" in explanation
    assert "top_contributing_factors" in explanation
    assert isinstance(explanation["top_contributing_factors"], list)
    assert len(explanation["top_contributing_factors"]) > 0

    for factor in explanation["top_contributing_factors"]:
        assert "factor" in factor
        assert "signal" in factor
        if factor["value"] is not None:
            assert isinstance(factor["value"], (int, float))
            assert not math.isnan(factor["value"])
            assert not math.isinf(factor["value"])


def test_single_prediction_invalid_location_has_null_explanation(client: TestClient):
    """Verify invalid location abstention returns explanation=None without fabrication."""
    response = client.post("/v1/predict", json={"location": "Atlantis"})
    assert response.status_code == 200
    data = response.json()

    assert data["location"] == "Atlantis"
    assert data["abstain"] is True
    assert data["bust_probability"] is None
    assert data["explanation"] is None
    assert "INVALID_LOCATION" in data["reason_codes"]


def test_batch_prediction_api_preserves_explanations(client: TestClient):
    """Verify POST /v1/predict/batch returns explanations for valid locations and None for invalid."""
    batch_req = {
        "locations": ["London", "Kolkata", "Atlantis"],
    }
    response = client.post("/v1/predict/batch", json=batch_req)
    assert response.status_code == 200
    data = response.json()

    assert data["batch_size"] == 3
    assert data["successful_predictions"] == 2
    assert data["abstained_predictions"] == 1
    assert len(data["results"]) == 3

    # 1. London (Success)
    london_res = data["results"][0]
    assert london_res["input_location"] == "London"
    assert london_res["is_success"] is True
    assert london_res["response"]["explanation"] is not None
    assert london_res["response"]["explanation"]["primary_driver"] is not None

    # 2. Kolkata (Success)
    kolkata_res = data["results"][1]
    assert kolkata_res["input_location"] == "Kolkata"
    assert kolkata_res["is_success"] is True
    assert kolkata_res["response"]["explanation"] is not None

    # 3. Atlantis (Abstained)
    atlantis_res = data["results"][2]
    assert atlantis_res["input_location"] == "Atlantis"
    assert atlantis_res["is_success"] is False
    assert atlantis_res["response"]["explanation"] is None


def test_batch_prediction_duplicate_locations_have_deterministic_explanations(client: TestClient):
    """Verify batch requests with duplicate locations return deterministic, identical explanations."""
    batch_req = {
        "locations": ["London", "London"],
    }
    response = client.post("/v1/predict/batch", json=batch_req)
    assert response.status_code == 200
    data = response.json()

    assert data["batch_size"] == 2
    item1 = data["results"][0]["response"]
    item2 = data["results"][1]["response"]

    assert item1["bust_probability"] == item2["bust_probability"]
    assert item1["explanation"] == item2["explanation"]


def test_openapi_schema_contains_explanation_contract(client: TestClient):
    """Verify OpenAPI schema documentation includes ExplanationItem and ContributingFactor."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    schemas = schema["components"]["schemas"]
    assert "ExplanationItem" in schemas
    assert "ContributingFactor" in schemas
    assert "PredictionResponse" in schemas
    assert "explanation" in schemas["PredictionResponse"]["properties"]


def test_probability_invariance_under_explanation(client: TestClient):
    """Verify that explanation integration does not alter the underlying bust probability or decision logic."""
    response = client.post("/v1/predict", json={"location": "London"})
    assert response.status_code == 200
    data = response.json()

    assert data["bust_probability"] == 0.0569
    assert data["risk_level"] == "LOW"
    assert data["trust_state"] == "HIGH_CONFIDENCE"
    assert data["abstain"] is False
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["data_version"] == "gefs-openmeteo-v1.0"


def test_explainer_service_exception_isolation(explainer_service: ExplainabilityIntegrationService):
    """Verify that unexpected internal exceptions in explainer are caught and return None safely."""
    # Pass object that causes TypeError during dict lookups
    class BrokenDict(dict):
        def get(self, key, default=None):
            raise RuntimeError("Simulated internal explainer explosion")

    result = explainer_service.explain(
        feature_row=BrokenDict(),
        bust_probability=0.35,
    )
    assert result is None


def test_validate_explanation_invalid_structure_returns_none(explainer_service: ExplainabilityIntegrationService):
    """Verify that completely malformed objects passed to validate_explanation safely return None."""
    assert explainer_service.validate_explanation("invalid_string_not_dict") is None
    assert explainer_service.validate_explanation(12345) is None
    assert explainer_service.validate_explanation(None) is None

"""Comprehensive automated unit and integration tests for Model Integration Layer (Day 11).

Verifies the centralized model boundary, feature contract validation, anti-leakage guards,
safe model failure isolation, probability bounds, version metadata propagation,
single prediction endpoint, batch prediction endpoint, and Builder 2 model registration hooks.
"""
import copy
import math
import os
from typing import Any
import pytest
from fastapi.testclient import TestClient

from backend.app.builder2.feature_pipeline import FEATURE_COLUMN_NAMES
from backend.app.builder2.model_adapter import Builder2ModelAdapter
from backend.app.main import app
from backend.app.schemas.model_integration import (
    FORBIDDEN_GROUND_TRUTH_FIELDS,
    ModelInputContract,
    ModelMetadataInfo,
    ModelOutputContract,
)
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.base import (
    BaseModelService,
    FeatureResult,
    ModelResult,
)
from backend.app.services.model_integration_service import (
    DEFAULT_BUILDER2_MODEL_PATH,
    ModelIntegrationService,
)
from backend.app.services.model_service import UnavailableModelService


@pytest.fixture
def valid_26_features_dict() -> dict[str, float]:
    """Provide a valid dictionary containing all 26 canonical features with finite values."""
    features = {col: 0.0 for col in FEATURE_COLUMN_NAMES}
    features.update({
        "forecast_value": 20.5,
        "lead_hours": 24.0,
        "latitude": 22.57,
        "longitude": 88.36,
        "month": 8.0,
        "hour": 12.0,
        "sin_month": math.sin(2 * math.pi * 8 / 12),
        "cos_month": math.cos(2 * math.pi * 8 / 12),
        "sin_hour": math.sin(2 * math.pi * 12 / 24),
        "cos_hour": math.cos(2 * math.pi * 12 / 24),
        "var_temperature_2m": 1.0,
        "var_surface_pressure": 0.0,
        "var_wind_speed_10m": 0.0,
        "var_relative_humidity_2m": 0.0,
        "var_precipitation": 0.0,
        "season_winter": 0.0,
        "season_spring": 0.0,
        "season_summer": 1.0,
        "season_autumn": 0.0,
        "ensemble_std": 0.5,
        "ensemble_iqr": 0.7,
        "ensemble_spread_ratio": 0.02,
        "instability_k_index": 25.0,
        "instability_total_totals": 45.0,
        "forecast_delta_24h": 0.2,
        "forecast_acceleration": 0.05,
    })
    return features


@pytest.fixture
def valid_feature_result(valid_26_features_dict: dict[str, float]) -> FeatureResult:
    """Provide a valid FeatureResult instance."""
    return FeatureResult(
        location="Kolkata",
        features=valid_26_features_dict,
        feature_names=list(valid_26_features_dict.keys()),
        is_ready=True,
        metadata={
            "feature_schema_version": "veyra-26-features-v1.0",
            "feature_matrix_rows": [valid_26_features_dict],
        },
    )


@pytest.fixture
def model_service() -> ModelIntegrationService:
    """Provide a ModelIntegrationService instance loaded with the active model."""
    return ModelIntegrationService()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# =====================================================================
# 1. INITIALIZATION & DISCOVERY TESTS
# =====================================================================

def test_model_integration_service_initialization(model_service: ModelIntegrationService):
    """Verify ModelIntegrationService auto-discovers and initializes the active model."""
    assert model_service.is_ready is True
    info = model_service.get_active_model_info()
    assert isinstance(info, ModelMetadataInfo)
    assert info.model_name == "builder2_gbm"
    assert info.model_version == "prototype-gbm-v1"
    assert info.is_calibrated is True
    assert info.expected_feature_count == 26


def test_model_registration_and_switching():
    """Verify Builder 2 dynamic model registration and active switching hooks."""
    mis = ModelIntegrationService()

    # Create dummy custom model
    class CustomGBMModel(BaseModelService):
        def __init__(self):
            self.model_version = "prototype-gbm-v2"
            self.is_ready = True

        def predict(self, feature_result: FeatureResult) -> ModelResult:
            return ModelResult(
                probability=0.1234,
                model_version=self.model_version,
                is_ready=True,
                metadata={"status": "SUCCESS", "model_type": "CustomGBM"},
            )

    custom_model = CustomGBMModel()
    mis.register_model("builder2_gbm_v2", custom_model, set_active=True)

    assert mis._active_model_name == "builder2_gbm_v2"
    info = mis.get_active_model_info()
    assert info.model_version == "prototype-gbm-v2"

    # Switch back to original
    mis.set_active_model("builder2_gbm")
    assert mis._active_model_name == "builder2_gbm"


# =====================================================================
# 2. INFERENCE EXECUTION & PROBABILITY BOUNDING
# =====================================================================

def test_valid_model_inference_execution(
    model_service: ModelIntegrationService, valid_feature_result: FeatureResult
):
    """Verify inference produces valid probability and enriched metadata."""
    res = model_service.predict(valid_feature_result)
    assert res.is_ready is True
    assert res.probability is not None
    assert 0.0 <= res.probability <= 1.0
    assert res.model_version == "prototype-gbm-v1"
    assert res.metadata.get("model_integration_gateway") == "ModelIntegrationService/v2.0"
    assert res.metadata.get("active_model_key") == "builder2_gbm"
    assert "explanation" in res.metadata


def test_probability_strictly_bounded_on_out_of_bounds_estimator():
    """Verify out-of-bounds probability returned by an estimator is safely rejected."""
    class BrokenProbModel(BaseModelService):
        def __init__(self):
            self.model_version = "broken-v1"
            self.is_ready = True

        def predict(self, feature_result: FeatureResult) -> ModelResult:
            return ModelResult(
                probability=1.55,  # Unphysical out-of-bounds probability
                model_version=self.model_version,
                is_ready=True,
                metadata={},
            )

    mis = ModelIntegrationService(primary_model=BrokenProbModel())
    feat_res = FeatureResult(
        location="Test",
        features={"forecast_value": 20.0},
        is_ready=True,
    )
    res = mis.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata.get("status") == ReasonCode.QC_FAILED.value
    assert "out-of-bounds" in res.error.lower()


# =====================================================================
# 3. FEATURE CONTRACT & VALUE VALIDATION
# =====================================================================

def test_missing_features_validation_rejection(model_service: ModelIntegrationService):
    """Verify feature validation fails when required features are missing."""
    incomplete_features = FeatureResult(
        location="Kolkata",
        features={"forecast_value": 25.0},  # Missing 25 canonical columns
        is_ready=True,
    )
    res = model_service.predict(incomplete_features)
    assert res.is_ready is False
    assert res.probability is None
    assert "missing" in res.error.lower()


def test_non_finite_nan_feature_rejection(
    model_service: ModelIntegrationService, valid_26_features_dict: dict[str, float]
):
    """Verify non-finite NaN feature values are safely rejected."""
    corrupt_features = copy.deepcopy(valid_26_features_dict)
    corrupt_features["ensemble_std"] = float("nan")

    feat_res = FeatureResult(
        location="Kolkata",
        features=corrupt_features,
        is_ready=True,
    )
    res = model_service.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert "non-finite" in res.error.lower()


def test_non_finite_inf_feature_rejection(
    model_service: ModelIntegrationService, valid_26_features_dict: dict[str, float]
):
    """Verify non-finite Inf feature values are safely rejected."""
    corrupt_features = copy.deepcopy(valid_26_features_dict)
    corrupt_features["forecast_value"] = float("inf")

    feat_res = FeatureResult(
        location="Kolkata",
        features=corrupt_features,
        is_ready=True,
    )
    res = model_service.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert "non-finite" in res.error.lower()


def test_features_not_ready_handling(model_service: ModelIntegrationService):
    """Verify that FeatureResult with is_ready=False is handled without calling model."""
    unready = FeatureResult(
        location="Kolkata",
        features={},
        is_ready=False,
        error="Weather data failed quality control checks",
    )
    res = model_service.predict(unready)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata.get("status") == ReasonCode.FEATURES_NOT_READY.value
    assert res.error == "Weather data failed quality control checks"


# =====================================================================
# 4. ANTI-DATA-LEAKAGE SECURITY AUDIT
# =====================================================================

def test_leakage_guard_rejects_ground_truth_in_features(
    model_service: ModelIntegrationService, valid_26_features_dict: dict[str, float]
):
    """CRITICAL SECURITY: Ground-truth reference observation field in features is rejected."""
    leaked_features = copy.deepcopy(valid_26_features_dict)
    leaked_features["observed_value"] = 22.5  # Forbidden ground-truth label

    feat_res = FeatureResult(
        location="Kolkata",
        features=leaked_features,
        is_ready=True,
    )
    res = model_service.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert "critical leakage" in res.error.lower()


def test_leakage_guard_rejects_ground_truth_in_metadata(
    model_service: ModelIntegrationService, valid_26_features_dict: dict[str, float]
):
    """CRITICAL SECURITY: Ground-truth reference field in metadata is rejected."""
    feat_res = FeatureResult(
        location="Kolkata",
        features=valid_26_features_dict,
        is_ready=True,
        metadata={"reference_records": [{"observed_value": 20.0}]},
    )
    res = model_service.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert "critical leakage" in res.error.lower()


def test_model_input_contract_schema_leakage_validator(
    valid_26_features_dict: dict[str, float]
):
    """Verify ModelInputContract schema validator detects and blocks ground truth fields."""
    leaked = copy.deepcopy(valid_26_features_dict)
    leaked["bust_label"] = 1.0
    with pytest.raises(ValueError, match="CRITICAL LEAKAGE"):
        ModelInputContract(
            location="Kolkata",
            features=leaked,
        )


# =====================================================================
# 5. SAFE MODEL FAILURE & EXCEPTION ISOLATION
# =====================================================================

def test_model_unavailable_service_handling():
    """Verify that UnavailableModelService safely returns is_ready=False without fabricating values."""
    mis = ModelIntegrationService(primary_model=UnavailableModelService())
    feat_res = FeatureResult(location="Kolkata", features={"f1": 1.0}, is_ready=True)
    res = mis.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata.get("status") == ReasonCode.MODEL_NOT_READY.value


def test_model_inference_exception_handling_without_traceback_leakage():
    """Verify that unexpected exceptions in the model are caught and isolated safely."""
    class ExplodingModel(BaseModelService):
        def __init__(self):
            self.model_version = "exploding-v1"
            self.is_ready = True

        def predict(self, feature_result: FeatureResult) -> ModelResult:
            raise RuntimeError("Internal CUDA Out of Memory or C++ Segfault simulation")

    mis = ModelIntegrationService(primary_model=ExplodingModel())
    feat_res = FeatureResult(location="Kolkata", features={"f1": 1.0}, is_ready=True)
    res = mis.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata.get("status") == ReasonCode.INTERNAL_ERROR.value
    assert "model inference failed" in res.error.lower()


# =====================================================================
# 6. TYPED EVALUATE_CONTRACT INTERFACE TESTS
# =====================================================================

def test_evaluate_contract_interface(
    model_service: ModelIntegrationService, valid_26_features_dict: dict[str, float]
):
    """Verify typed evaluate_contract() method returning ModelOutputContract."""
    input_contract = ModelInputContract(
        location="Kolkata",
        features=valid_26_features_dict,
        feature_names=list(valid_26_features_dict.keys()),
        feature_schema_version="veyra-26-features-v1.0",
        metadata={"feature_matrix_rows": [valid_26_features_dict]},
    )
    output = model_service.evaluate_contract(input_contract)
    assert isinstance(output, ModelOutputContract)
    assert output.is_success is True
    assert output.probability is not None
    assert output.model_version == "prototype-gbm-v1"
    assert output.decision_threshold == 0.280
    assert output.is_calibrated is True


# =====================================================================
# 7. SINGLE & BATCH PREDICTION ENDPOINT INTEGRATION
# =====================================================================

def test_single_prediction_endpoint_integration(client: TestClient):
    """Verify POST /v1/predict executes through the Model Integration Layer."""
    response = client.post("/v1/predict", json={"location": "London"})
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "London"
    assert data["abstain"] is False
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["data_version"] == "gefs-openmeteo-v1.0"
    assert "bust_probability" in data
    assert 0.0 <= data["bust_probability"] <= 1.0


def test_single_prediction_invalid_location_abstention(client: TestClient):
    """Verify POST /v1/predict safely abstains on invalid location."""
    response = client.post("/v1/predict", json={"location": "Atlantis"})
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Atlantis"
    assert data["abstain"] is True
    assert data["trust_state"] == TrustState.UNAVAILABLE
    assert ReasonCode.INVALID_LOCATION in data["reason_codes"]


def test_single_prediction_direct_coordinates(client: TestClient):
    """Verify POST /v1/predict with direct coordinates works through Model Integration Layer."""
    response = client.post("/v1/predict", json={"location": "22.5726, 88.3639"})
    assert response.status_code == 200
    data = response.json()
    assert data["abstain"] is False
    assert data["model_version"] == "prototype-gbm-v1"


def test_calibrator_failure_handling():
    """Verify that a failure in the calibration step is caught without crashing."""
    class BrokenCalibratorModel(BaseModelService):
        def __init__(self):
            self.model_version = "broken-calib-v1"
            self.is_ready = True

        def predict(self, feature_result: FeatureResult) -> ModelResult:
            raise ValueError("Platt Sigmoid calibrator division by zero error")

    mis = ModelIntegrationService(primary_model=BrokenCalibratorModel())
    feat_res = FeatureResult(location="Kolkata", features={"f1": 1.0}, is_ready=True)
    res = mis.predict(feat_res)
    assert res.is_ready is False
    assert res.probability is None
    assert "inference failed" in res.error.lower()


def test_version_metadata_propagation(
    model_service: ModelIntegrationService, valid_feature_result: FeatureResult
):
    """Verify model and data versions propagate cleanly into ModelResult metadata."""
    res = model_service.predict(valid_feature_result)
    assert res.model_version == "prototype-gbm-v1"
    assert res.metadata["model_integration_gateway"] == "ModelIntegrationService/v2.0"
    assert res.metadata["active_model_key"] == "builder2_gbm"
    assert "bust_alert" in res.metadata


def test_batch_prediction_endpoint_integration(client: TestClient):
    """Verify POST /v1/predict/batch routes through Model Integration Layer with failure isolation."""
    payload = {
        "locations": ["Kolkata", "London", "Atlantis"],
        "variable": "temperature_2m",
    }
    response = client.post("/v1/predict/batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["batch_size"] == 3
    assert data["successful_predictions"] == 2
    assert data["abstained_predictions"] == 1
    assert data["results"][0]["input_location"] == "Kolkata"
    assert data["results"][0]["response"]["abstain"] is False
    assert data["results"][0]["response"]["model_version"] == "prototype-gbm-v1"
    assert data["results"][2]["input_location"] == "Atlantis"
    assert data["results"][2]["response"]["abstain"] is True



"""Comprehensive automated unit and integration tests for Evaluation Integration Layer (Day 12).

Verifies discovery of active and baseline evaluation metadata, version compatibility validation,
metric finiteness and bounds enforcement, calibration metadata propagation,
safe unavailable/invalid status handling, unknown model name rejection,
HTTP evaluation endpoint, and anti-leakage guards.
"""
import json
import math
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.evaluation import (
    CalibrationMetadata,
    EvaluationDatasetInfo,
    EvaluationMetrics,
    EvaluationStatus,
    ModelEvaluationResponse,
)
from backend.app.schemas.model_integration import (
    FORBIDDEN_GROUND_TRUTH_FIELDS,
    ModelInputContract,
)
from backend.app.services.evaluation_service import (
    DEFAULT_BASELINE_METADATA_PATH,
    DEFAULT_BUILDER2_METADATA_PATH,
    EvaluationIntegrationService,
)
from backend.app.services.model_integration_service import (
    ModelIntegrationService,
)


@pytest.fixture
def eval_service() -> EvaluationIntegrationService:
    """Provide a standard EvaluationIntegrationService instance."""
    return EvaluationIntegrationService()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# =====================================================================
# 1. ACTIVE MODEL EVALUATION TESTS (prototype-gbm-v1)
# =====================================================================

def test_active_model_evaluation_discovery(eval_service: EvaluationIntegrationService):
    """Verify active model evaluation metadata is discovered and parsed accurately."""
    resp = eval_service.get_evaluation()
    assert isinstance(resp, ModelEvaluationResponse)
    assert resp.model_name == "builder2_gbm"
    assert resp.model_version == "prototype-gbm-v1"
    assert resp.evaluation_status == EvaluationStatus.AVAILABLE
    assert "SUCCESS" in resp.reason_codes

    # Metrics
    assert resp.metrics is not None
    assert resp.metrics.accuracy == 0.9463
    assert resp.metrics.roc_auc == 0.5165
    assert resp.metrics.pr_auc == 0.0579
    assert resp.metrics.brier_score == 0.0508
    assert resp.metrics.brier_score_calibrated == 0.0508
    assert resp.metrics.brier_score_uncalibrated == 0.2043
    assert resp.metrics.brier_improvement_pct == 75.12

    # Calibration
    assert resp.calibration is not None
    assert resp.calibration.is_calibrated is True
    assert resp.calibration.calibration_method == "sigmoid"
    assert resp.calibration.decision_threshold == 0.28
    assert resp.calibration.calibrator_status == "OPERATIONAL"

    # Dataset info
    assert resp.dataset_info is not None
    assert resp.dataset_info.total_samples == 10800
    assert resp.dataset_info.train_samples == 7560
    assert resp.dataset_info.validation_samples == 1620
    assert resp.dataset_info.test_samples == 1620


def test_explicit_active_model_aliases(eval_service: EvaluationIntegrationService):
    """Verify that explicit valid aliases for the active model return active evaluation."""
    for alias in ("builder2_gbm", "prototype-gbm-v1", "gbm", "lightgbm"):
        resp = eval_service.get_evaluation(model_name=alias)
        assert resp.evaluation_status == EvaluationStatus.AVAILABLE
        assert resp.model_version == "prototype-gbm-v1"
        assert resp.metrics is not None
        assert resp.metrics.accuracy == 0.9463


# =====================================================================
# 2. BASELINE MODEL EVALUATION TESTS (baseline-logistic-v1.0)
# =====================================================================

def test_baseline_evaluation_retrieval(eval_service: EvaluationIntegrationService):
    """Verify historical Phase 1 baseline evaluation can be explicitly queried."""
    resp = eval_service.get_baseline_evaluation()
    assert isinstance(resp, ModelEvaluationResponse)
    assert resp.model_name == "baseline_logistic"
    assert resp.model_version == "baseline-logistic-v1.0"
    assert resp.model_type == "LogisticRegression"
    assert resp.evaluation_status == EvaluationStatus.AVAILABLE

    # Metrics
    assert resp.metrics is not None
    assert resp.metrics.accuracy == 0.60
    assert resp.metrics.precision == 0.60
    assert resp.metrics.recall == 0.4286
    assert resp.metrics.f1_score == 0.50
    assert resp.metrics.roc_auc == 0.75
    assert resp.metrics.brier_score == 0.2432

    # Calibration
    assert resp.calibration is not None
    assert resp.calibration.is_calibrated is False


def test_baseline_and_active_model_strict_separation(eval_service: EvaluationIntegrationService):
    """Verify that active prototype-gbm-v1 and baseline-logistic-v1.0 metrics never mix."""
    active_eval = eval_service.get_evaluation()
    baseline_eval = eval_service.get_baseline_evaluation()

    assert active_eval.model_version != baseline_eval.model_version
    assert active_eval.metrics.accuracy != baseline_eval.metrics.accuracy
    assert active_eval.calibration.is_calibrated != baseline_eval.calibration.is_calibrated


# =====================================================================
# 3. UNKNOWN MODEL HANDLING (ANTI-FALLTHROUGH SAFETY)
# =====================================================================

def test_unknown_model_name_returns_unavailable_status(eval_service: EvaluationIntegrationService):
    """Verify that an arbitrary unknown model name returns UNAVAILABLE status and NO metrics."""
    resp = eval_service.get_evaluation(model_name="totally_unknown_model")
    assert isinstance(resp, ModelEvaluationResponse)
    assert resp.model_name == "totally_unknown_model"
    assert resp.model_version == "unknown"
    assert resp.evaluation_status == EvaluationStatus.UNAVAILABLE
    assert resp.metrics is None
    assert resp.calibration is None
    assert resp.dataset_info is None
    assert "UNKNOWN_MODEL" in resp.reason_codes
    assert "error" in resp.metadata


# =====================================================================
# 4. METRIC VALIDATION & BOUNDS ENFORCEMENT
# =====================================================================

def test_metric_finiteness_validation_rejects_nan():
    """Verify that NaN metrics are rejected by schema validator."""
    with pytest.raises(ValueError, match="finite numerical value"):
        EvaluationMetrics(accuracy=float("nan"))


def test_metric_finiteness_validation_rejects_inf():
    """Verify that Infinity metrics are rejected by schema validator."""
    with pytest.raises(ValueError, match="finite numerical value"):
        EvaluationMetrics(roc_auc=float("inf"))


def test_metric_bounds_validation_rejects_out_of_bounds():
    """Verify that metrics outside [0.0, 1.0] are rejected."""
    with pytest.raises(ValueError):
        EvaluationMetrics(accuracy=1.25)


# =====================================================================
# 5. ERROR & COMPATIBILITY HANDLING
# =====================================================================

def test_missing_metadata_file_handling(tmp_path: Path):
    """Verify safe unavailable status when metadata file does not exist."""
    non_existent = tmp_path / "does_not_exist.json"
    service = EvaluationIntegrationService(builder2_metadata_path=non_existent)
    resp = service.get_evaluation()

    assert resp.evaluation_status == EvaluationStatus.UNAVAILABLE
    assert resp.metrics is None
    assert "EVALUATION_METADATA_UNAVAILABLE" in resp.reason_codes


def test_incompatible_model_version_handling(tmp_path: Path):
    """Verify that metadata with mismatched model version is flagged as INCOMPATIBLE."""
    fake_meta = tmp_path / "mismatched_model.json"
    fake_meta.write_text(
        json.dumps({
            "model_version": "future-catboost-v9.9",
            "model_type": "CatBoostClassifier",
            "test_metrics": {"accuracy": 0.99},
        }),
        encoding="utf-8",
    )

    service = EvaluationIntegrationService(builder2_metadata_path=fake_meta)
    resp = service.get_evaluation()

    assert resp.evaluation_status == EvaluationStatus.INCOMPATIBLE
    assert resp.metrics is None
    assert "MODEL_VERSION_MISMATCH" in resp.reason_codes


def test_malformed_non_finite_metrics_in_file_handling(tmp_path: Path):
    """Verify that corrupt metadata containing string/invalid values returns INVALID status."""
    corrupt_meta = tmp_path / "corrupt_metrics.json"
    # Write invalid accuracy exceeding range or non-finite
    corrupt_meta.write_text(
        json.dumps({
            "model_version": "prototype-gbm-v1",
            "test_metrics": {"accuracy": 99.9},  # Invalid accuracy > 1.0
        }),
        encoding="utf-8",
    )

    service = EvaluationIntegrationService(builder2_metadata_path=corrupt_meta)
    resp = service.get_evaluation()

    assert resp.evaluation_status == EvaluationStatus.INVALID
    assert resp.metrics is None
    assert "METRICS_VALIDATION_ERROR" in resp.reason_codes


def test_service_exception_isolation():
    """Verify that unexpected internal exceptions are caught safely without crashing."""
    class BrokenModelService:
        def get_active_model_info(self):
            raise RuntimeError("Database connection timed out")

    service = EvaluationIntegrationService(model_integration_service=BrokenModelService())
    resp = service.get_evaluation()

    assert resp.evaluation_status == EvaluationStatus.UNAVAILABLE
    assert resp.metrics is None
    assert "INTERNAL_ERROR" in resp.reason_codes


# =====================================================================
# 6. HTTP EVALUATION ENDPOINT TESTS (GET /v1/model/evaluation)
# =====================================================================

def test_http_get_model_evaluation_active_model_default(client: TestClient):
    """Verify GET /v1/model/evaluation with default query returns active prototype model evaluation."""
    response = client.get("/v1/model/evaluation")
    assert response.status_code == 200
    data = response.json()

    assert data["model_name"] == "builder2_gbm"
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["evaluation_status"] == "AVAILABLE"
    assert data["metrics"]["accuracy"] == 0.9463
    assert data["metrics"]["brier_score_calibrated"] == 0.0508
    assert data["calibration"]["is_calibrated"] is True
    assert data["calibration"]["decision_threshold"] == 0.28
    assert data["dataset_info"]["total_samples"] == 10800


def test_http_get_model_evaluation_empty_string_query(client: TestClient):
    """Verify GET /v1/model/evaluation?model_name= (empty string) defaults to active model."""
    response = client.get("/v1/model/evaluation?model_name=")
    assert response.status_code == 200
    data = response.json()

    assert data["model_name"] == "builder2_gbm"
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["evaluation_status"] == "AVAILABLE"


def test_http_get_model_evaluation_explicit_active_model(client: TestClient):
    """Verify GET /v1/model/evaluation?model_name=prototype-gbm-v1 returns active evaluation."""
    response = client.get("/v1/model/evaluation?model_name=prototype-gbm-v1")
    assert response.status_code == 200
    data = response.json()

    assert data["model_name"] == "builder2_gbm"
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["evaluation_status"] == "AVAILABLE"


def test_http_get_model_evaluation_baseline_query(client: TestClient):
    """Verify GET /v1/model/evaluation?model_name=baseline_logistic returns baseline evaluation."""
    response = client.get("/v1/model/evaluation?model_name=baseline_logistic")
    assert response.status_code == 200
    data = response.json()

    assert data["model_name"] == "baseline_logistic"
    assert data["model_version"] == "baseline-logistic-v1.0"
    assert data["evaluation_status"] == "AVAILABLE"
    assert data["metrics"]["accuracy"] == 0.60
    assert data["calibration"]["is_calibrated"] is False


def test_http_get_model_evaluation_unknown_model_rejection(client: TestClient):
    """Verify GET /v1/model/evaluation?model_name=totally_unknown_model returns UNAVAILABLE and no metrics."""
    response = client.get("/v1/model/evaluation?model_name=totally_unknown_model")
    assert response.status_code == 200
    data = response.json()

    assert data["model_name"] == "totally_unknown_model"
    assert data["model_version"] == "unknown"
    assert data["evaluation_status"] == "UNAVAILABLE"
    assert data["metrics"] is None
    assert data["calibration"] is None
    assert data["dataset_info"] is None
    assert "UNKNOWN_MODEL" in data["reason_codes"]


def test_openapi_schema_contains_evaluation_endpoint(client: TestClient):
    """Verify that FastAPI OpenAPI documentation exposes /v1/model/evaluation."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/v1/model/evaluation" in schema["paths"]
    assert "get" in schema["paths"]["/v1/model/evaluation"]


# =====================================================================
# 7. ANTI-DATA-LEAKAGE AUDIT
# =====================================================================

def test_evaluation_structures_do_not_leak_into_inference_contract():
    """Verify that evaluation ground-truth fields cannot enter ModelInputContract."""
    for field in FORBIDDEN_GROUND_TRUTH_FIELDS:
        with pytest.raises(ValueError, match="CRITICAL LEAKAGE"):
            ModelInputContract(
                location="London",
                features={field: 1.0, "forecast_value": 20.0},
            )

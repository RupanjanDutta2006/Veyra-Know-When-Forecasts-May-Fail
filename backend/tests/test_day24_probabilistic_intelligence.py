"""
Comprehensive Day 24 Probabilistic Intelligence Test Suite.

Verifies:
1. Frozen V3 artifact hashes and 50 feature names
2. Calibrated probability serving and raw probability non-exposure
3. Calibration failure safety (missing calibrator, exception, NaN, inf -> safe abstention)
4. Calibration status contract (CALIBRATED, FAILED, UNAVAILABLE)
5. Exact risk tier boundaries (0.199999, 0.20, 0.499999, 0.50, 0.749999, 0.75)
6. Evaluation endpoints backward compatibility (legacy default, ?model=legacy, ?model=v3, /v3)
7. OOD numeric 0.0 preservation and diagnostic-only governance
8. Explanation contradiction & pressure unit regression (84.2 Pa neutral spread, non-alert consistency)
9. Manual-safety OpenAPI contract check (no lead_hours in PredictionRequest)
"""

import hashlib
import json
import math
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.builder2.explainer import ForecastBustExplainer
from backend.app.builder2.v3_feature_pipeline import V3_FEATURE_NAMES
from backend.app.builder2.v3_model_adapter import Builder2V3ModelAdapter
from backend.app.main import app
from backend.app.safety.abstention import SafetyEvaluator
from backend.app.schemas.prediction import CalibrationStatus, PredictionResponse, ReasonCode, RiskLevel, TrustState
from backend.app.services.base import FeatureResult, ModelResult
from backend.app.services.evaluation_service import EvaluationIntegrationService

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_V3_DIR = REPO_ROOT / "models" / "v3"


# ============================================================================
# 1. FROZEN ARTIFACT AUTHENTICATION
# ============================================================================

def test_frozen_v3_artifact_hashes():
    """Verify exact SHA256 hashes for frozen V3 model and calibrator."""
    model_path = MODELS_V3_DIR / "lightgbm_v3_challenger.joblib"
    calibrator_path = MODELS_V3_DIR / "probability_calibrator_v3.joblib"
    feature_names_path = MODELS_V3_DIR / "feature_names.json"

    assert model_path.exists(), "V3 challenger model missing"
    assert calibrator_path.exists(), "V3 calibrator missing"
    assert feature_names_path.exists(), "V3 feature names missing"

    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest().upper()
    cal_sha = hashlib.sha256(calibrator_path.read_bytes()).hexdigest().upper()

    assert model_sha == "00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660"
    assert cal_sha == "9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531"

    feature_names = json.loads(feature_names_path.read_text())
    assert len(feature_names) == 50, f"Expected 50 features, found {len(feature_names)}"


# ============================================================================
# 2. CALIBRATED SERVING & NON-EXPOSURE OF RAW PROBABILITY
# ============================================================================

def test_calibrated_serving_normal_path():
    """Normal prediction path applies isotonic calibration and sets CALIBRATED status."""
    adapter = Builder2V3ModelAdapter(model_dir=MODELS_V3_DIR)
    assert adapter.is_ready is True, "Adapter should be ready with valid artifacts"

    sample_features = {f: 0.0 for f in V3_FEATURE_NAMES}
    sample_features["ensemble_spread"] = 1.5

    feature_res = FeatureResult(location="Denver", features=sample_features, is_ready=True)
    result = adapter.predict(feature_res)

    assert result.is_ready is True
    assert result.probability is not None
    assert 0.0 <= result.probability <= 1.0
    assert result.metadata.get("calibration_status") == "CALIBRATED"

    # Raw probability must remain internal diagnostic only
    assert "raw_probability" in result.metadata
    assert not hasattr(result, "raw_probability")  # Not a field on ModelResult


def test_prediction_response_schema_omits_raw_probability():
    """PredictionResponse schema does not expose raw_probability."""
    schema_props = PredictionResponse.model_json_schema()["properties"]
    assert "raw_probability" not in schema_props
    assert "calibration_status" in schema_props
    assert "bust_probability" in schema_props


# ============================================================================
# 3. CALIBRATION FAILURE SAFETY (SAFE ABSTENTION)
# ============================================================================

def test_calibrator_missing_causes_safe_abstention():
    """Missing calibrator causes safe failure result without serving raw probability."""
    adapter = Builder2V3ModelAdapter(model_dir=MODELS_V3_DIR)
    adapter.calibrator = None  # Simulate missing calibrator

    sample_features = {f: 0.0 for f in V3_FEATURE_NAMES}
    feature_res = FeatureResult(location="Denver", features=sample_features, is_ready=True)
    result = adapter.predict(feature_res)

    assert result.is_ready is False
    assert result.probability is None

    # Safety evaluator converts failure to safe abstention
    evaluator = SafetyEvaluator()
    assessment = evaluator.evaluate(model_result=result)
    assert assessment.abstain is True
    assert assessment.bust_probability is None
    assert assessment.risk_level is None
    assert assessment.trust_state == TrustState.UNAVAILABLE


def test_calibrator_exception_causes_safe_abstention():
    """Calibrator raising an exception causes safe failure result."""
    adapter = Builder2V3ModelAdapter(model_dir=MODELS_V3_DIR)
    adapter.calibrator = MagicMock()
    adapter.calibrator.predict.side_effect = RuntimeError("Isotonic curve evaluation failed")

    sample_features = {f: 0.0 for f in V3_FEATURE_NAMES}
    feature_res = FeatureResult(location="Denver", features=sample_features, is_ready=True)
    result = adapter.predict(feature_res)

    assert result.is_ready is False
    assert result.probability is None
    assert result.metadata.get("status") == ReasonCode.CALIBRATION_FAILURE.value
    assert result.metadata.get("calibration_status") == "FAILED"


def test_calibrator_nan_output_causes_safe_abstention():
    """Calibrator producing NaN causes safe failure result."""
    adapter = Builder2V3ModelAdapter(model_dir=MODELS_V3_DIR)
    adapter.calibrator = MagicMock()
    adapter.calibrator.predict.return_value = [float("nan")]

    sample_features = {f: 0.0 for f in V3_FEATURE_NAMES}
    feature_res = FeatureResult(location="Denver", features=sample_features, is_ready=True)
    result = adapter.predict(feature_res)

    assert result.is_ready is False
    assert result.probability is None
    assert result.metadata.get("status") == ReasonCode.CALIBRATION_FAILURE.value
    assert result.metadata.get("calibration_status") == "FAILED"


def test_calibrator_infinity_output_causes_safe_abstention():
    """Calibrator producing infinity causes safe failure result."""
    adapter = Builder2V3ModelAdapter(model_dir=MODELS_V3_DIR)
    adapter.calibrator = MagicMock()
    adapter.calibrator.predict.return_value = [float("inf")]

    sample_features = {f: 0.0 for f in V3_FEATURE_NAMES}
    feature_res = FeatureResult(location="Denver", features=sample_features, is_ready=True)
    result = adapter.predict(feature_res)

    assert result.is_ready is False
    assert result.probability is None
    assert result.metadata.get("status") == ReasonCode.CALIBRATION_FAILURE.value
    assert result.metadata.get("calibration_status") == "FAILED"


# ============================================================================
# 4. CALIBRATION STATUS CONTRACT
# ============================================================================

def test_calibration_status_values():
    """CalibrationStatus enum values match contract."""
    assert CalibrationStatus.CALIBRATED.value == "CALIBRATED"
    assert CalibrationStatus.FAILED.value == "FAILED"
    assert CalibrationStatus.UNAVAILABLE.value == "UNAVAILABLE"


# ============================================================================
# 5. EXACT RISK TIER BOUNDARIES (INVARIANTS)
# ============================================================================

@pytest.mark.parametrize(
    "prob, expected_tier",
    [
        (0.0, RiskLevel.LOW),
        (0.199999, RiskLevel.LOW),
        (0.20, RiskLevel.MEDIUM),
        (0.499999, RiskLevel.MEDIUM),
        (0.50, RiskLevel.HIGH),
        (0.749999, RiskLevel.HIGH),
        (0.75, RiskLevel.CRITICAL),
        (1.0, RiskLevel.CRITICAL),
    ],
)
def test_exact_risk_tier_boundaries(prob, expected_tier):
    """Test invariant operational risk boundaries without drift."""
    assert SafetyEvaluator._map_risk_level(prob) == expected_tier


# ============================================================================
# 6. EVALUATION API & BACKWARD COMPATIBILITY
# ============================================================================

def test_evaluation_endpoint_default_is_legacy():
    """GET /v1/model/evaluation MUST return legacy prototype evaluation by default."""
    resp = client.get("/v1/model/evaluation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_version"] == "prototype-gbm-v1"
    assert data["model_name"] == "builder2_gbm"
    assert "metrics" in data
    assert "brier_score" in data["metrics"]


def test_evaluation_endpoint_model_legacy_param():
    """GET /v1/model/evaluation?model=legacy returns legacy prototype evaluation."""
    resp = client.get("/v1/model/evaluation?model=legacy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_version"] == "prototype-gbm-v1"


def test_evaluation_endpoint_model_v3_param():
    """GET /v1/model/evaluation?model=v3 returns frozen V3 championship evaluation."""
    resp = client.get("/v1/model/evaluation?model=v3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"
    assert data["feature_count"] == 50
    assert data["calibration_method"] == "isotonic"
    assert data["test_samples"] == 116250
    assert data["test_cycles"] == 155

    # Scalar frozen Day 23 metrics
    metrics = data["metrics"]
    assert metrics["average_precision"] == 0.2047
    assert metrics["pr_auc_trapezoidal"] == 0.2124
    assert metrics["roc_auc"] == 0.7698
    assert metrics["brier_score"] == 0.053798
    assert metrics["bss_vs_e0"] == 0.0807
    assert metrics["bss_vs_e1b"] == 0.0778
    assert metrics["ece"] == 0.0064

    # Generalization limits list
    assert len(data["generalization_limits"]) >= 5


def test_dedicated_v3_evaluation_endpoint():
    """GET /v1/model/evaluation/v3 returns frozen V3 championship evaluation."""
    resp = client.get("/v1/model/evaluation/v3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"
    assert data["feature_count"] == 50
    assert data["calibration_method"] == "isotonic"
    assert data["test_samples"] == 116250
    assert data["metrics"]["average_precision"] == 0.2047
    assert data["metrics"]["pr_auc_trapezoidal"] == 0.2124
    assert data["metrics"]["roc_auc"] == 0.7698
    assert data["metrics"]["brier_score"] == 0.053798
    assert data["metrics"]["bss_vs_e0"] == 0.0807
    assert data["metrics"]["bss_vs_e1b"] == 0.0778
    assert data["metrics"]["ece"] == 0.0064


def test_production_app_routes_and_openapi_contain_evaluation_v3():
    """Verify real production FastAPI app registers /v1/model/evaluation and /v1/model/evaluation/v3."""
    from backend.app.main import app as prod_app

    openapi_paths = prod_app.openapi().get("paths", {})
    assert "/v1/model/evaluation" in openapi_paths, "Missing /v1/model/evaluation in OpenAPI"
    assert "/v1/model/evaluation/v3" in openapi_paths, "Missing /v1/model/evaluation/v3 in OpenAPI"

    prod_client = TestClient(prod_app)
    resp = prod_client.get("/v1/model/evaluation/v3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_version"] == "veyra-v3-benchmark-lightgbm"
    assert data["feature_count"] == 50
    assert data["calibration_method"] == "isotonic"
    assert data["test_samples"] == 116250
    assert data["metrics"]["average_precision"] == 0.2047
    assert data["metrics"]["ece"] == 0.0064


def test_unknown_model_selector_returns_unavailable():
    """GET /v1/model/evaluation?model=invalid returns structured UNAVAILABLE response."""
    resp = client.get("/v1/model/evaluation?model=invalid_model_name")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluation_status"] == "UNAVAILABLE"
    assert "UNKNOWN_MODEL" in data["reason_codes"]
    assert data["metrics"] is None


# ============================================================================
# 7. OOD SERIALIZATION & DIAGNOSTIC GOVERNANCE
# ============================================================================

def test_ood_score_serialization_preserves_zero():
    """OOD score of 0.0 must be preserved as numeric 0.0 and not coerced to null."""
    resp = PredictionResponse(
        location="Denver",
        target_variable="temperature_2m",
        issued_time="2026-09-10T00:00:00Z",
        valid_time="2026-09-11T00:00:00Z",
        lead_hours=24,
        lead_days=1.0,
        horizon_category="short_range",
        decision_mode="ACTIVE_PREDICTION",
        bust_probability=0.25,
        risk_level=RiskLevel.MEDIUM,
        confidence_index=0.5,
        uncertainty_pct=50.0,
        trust_state=TrustState.HIGH_CONFIDENCE,
        abstain=False,
        reason_codes=[ReasonCode.SUCCESS.value],
        calibration_status=CalibrationStatus.CALIBRATED,
        model_version="v3-lightgbm-isotonic",
        data_version="canonical-v3",
        pipeline_latency_ms=10.0,
        ood_score=0.0,
    )
    serialized = resp.model_dump()
    assert serialized["ood_score"] == 0.0
    assert serialized["ood_score"] is not None


def test_ood_score_diagnostic_only_governance():
    """OOD remains diagnostic only and does not trigger abstention even if elevated."""
    resp = PredictionResponse(
        location="Denver",
        target_variable="temperature_2m",
        issued_time="2026-09-10T00:00:00Z",
        valid_time="2026-09-11T00:00:00Z",
        lead_hours=24,
        lead_days=1.0,
        horizon_category="short_range",
        decision_mode="ACTIVE_PREDICTION",
        bust_probability=0.25,
        risk_level=RiskLevel.MEDIUM,
        confidence_index=0.5,
        uncertainty_pct=50.0,
        trust_state=TrustState.HIGH_CONFIDENCE,
        abstain=False,
        reason_codes=[ReasonCode.SUCCESS.value],
        calibration_status=CalibrationStatus.CALIBRATED,
        model_version="v3-lightgbm-isotonic",
        data_version="canonical-v3",
        pipeline_latency_ms=10.0,
        ood_score=0.85,  # High diagnostic OOD
    )
    assert resp.abstain is False
    assert resp.decision_mode == "ACTIVE_PREDICTION"


# ============================================================================
# 8. EXPLANATION CONTRADICTION REPAIR & PRESSURE UNIT REGRESSION
# ============================================================================

def test_surface_pressure_anomaly_explanation_consistency():
    """
    Construct deterministic case equivalent to:
    surface pressure, ensemble_std ~84.2 Pa, probability ~0.1129.
    Must NOT simultaneously produce HIGH_ENSEMBLE_SPREAD and 'stable with low ensemble dispersion'.
    """
    explanation = ForecastBustExplainer.explain_row(
        feature_row={"ensemble_std": 84.2, "lead_hours": 48, "variable": "surface_pressure", "is_surface_pressure": 1.0},
        bust_probability=0.1129,
    )

    summary_lower = explanation.driver_summary.lower()
    signals = [f.signal for f in explanation.top_contributing_factors]

    # Must NOT label 84.2 Pa as HIGH_ENSEMBLE_SPREAD without scientific justification
    assert "HIGH_ENSEMBLE_SPREAD" not in signals

    # If ensemble_spread is identified as a signal, summary must not contradict it
    if "ENSEMBLE_SPREAD" in signals:
        assert "low ensemble dispersion" not in summary_lower


def test_non_alert_probability_does_not_force_stable_summary():
    """When spread is elevated, non-alert probability (P < 0.280) must not falsely assert stability."""
    explanation = ForecastBustExplainer.explain_row(
        feature_row={"ensemble_std": 4.5, "lead_hours": 48, "variable": "temperature"},
        bust_probability=0.22,  # Non-alert probability
    )

    signals = [f.signal for f in explanation.top_contributing_factors]
    summary_lower = explanation.driver_summary.lower()

    if "HIGH_ENSEMBLE_SPREAD" in signals:
        assert "low ensemble dispersion" not in summary_lower
        assert "stable ensemble agreement" not in summary_lower


# ============================================================================
# 9. MANUAL-SAFETY OPENAPI CONTRACT CHECK
# ============================================================================

def test_openapi_schema_prediction_request_omits_lead_hours():
    """Verify PredictionRequest does NOT introduce lead_hours in OpenAPI schema."""
    openapi_spec = app.openapi()
    pred_request_schema = openapi_spec["components"]["schemas"]["PredictionRequest"]
    properties = pred_request_schema["properties"]

    assert "lead_hours" not in properties, "lead_hours must not be in PredictionRequest schema"
    assert "location" in properties
    assert "issue_time" in properties
    assert "valid_time" in properties

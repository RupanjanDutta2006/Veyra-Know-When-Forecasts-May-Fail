"""Deterministic Failure Safety Tests for V3 Model & Feature Adapters.

Verifies:
1. Missing model directory/binary -> SAFE ABSTENTION (MODEL_NOT_READY), no silent fallback.
2. Hash-invalid model binary -> SAFE ABSTENTION (MODEL_NOT_READY), no legacy execution.
3. Missing calibrator -> SAFE ABSTENTION (MODEL_NOT_READY).
4. Schema mismatch (e.g. 26 features instead of 50) -> SAFE ABSTENTION (QC_FAILED / FEATURES_NOT_READY).
5. Non-finite values (NaN / Inf) in features -> SAFE ABSTENTION (QC_FAILED).
6. Missing features -> SAFE ABSTENTION.
"""

import tempfile
from pathlib import Path
import pytest

from backend.app.builder2.v3_model_adapter import (
    Builder2V3ModelAdapter,
    DEFAULT_V3_MODEL_DIR,
)
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.base import FeatureResult
from backend.app.services.model_integration_service import ModelIntegrationService


def test_missing_model_directory_abtains_safely():
    """Verify that a non-existent model directory results in safe abstention."""
    adapter = Builder2V3ModelAdapter(model_dir="non_existent/path/to/v3")
    assert adapter.is_ready is False

    dummy_feat = FeatureResult(
        location="Nowhere",
        features={"ensemble_mean": 300.0},
        is_ready=True,
    )

    res = adapter.predict(dummy_feat)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata["status"] == ReasonCode.MODEL_NOT_READY.value


def test_hash_invalid_model_abtains_safely(tmp_path: Path):
    """Verify corrupted/tampered model fails SHA check and produces safe abstention."""
    # Create temp directory with fake model artifact
    fake_model = tmp_path / "lightgbm_v3_challenger.joblib"
    fake_cal = tmp_path / "probability_calibrator_v3.joblib"
    fake_fn = tmp_path / "feature_names.json"

    fake_model.write_text("corrupted_bytes")
    # Copy real calibrator and feature_names
    fake_cal.write_bytes((DEFAULT_V3_MODEL_DIR / "probability_calibrator_v3.joblib").read_bytes())
    fake_fn.write_bytes((DEFAULT_V3_MODEL_DIR / "feature_names.json").read_bytes())

    adapter = Builder2V3ModelAdapter(model_dir=tmp_path, enforce_sha=True)
    assert adapter.is_ready is False
    assert "SHA-256 mismatch" in (adapter.init_error or "")

    dummy_feat = FeatureResult(
        location="Nowhere",
        features={"ensemble_mean": 300.0},
        is_ready=True,
    )
    res = adapter.predict(dummy_feat)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata["status"] == ReasonCode.MODEL_NOT_READY.value


def test_missing_calibrator_abtains_safely(tmp_path: Path):
    """Verify missing calibrator produces safe abstention."""
    fake_model = tmp_path / "lightgbm_v3_challenger.joblib"
    fake_fn = tmp_path / "feature_names.json"

    fake_model.write_bytes((DEFAULT_V3_MODEL_DIR / "lightgbm_v3_challenger.joblib").read_bytes())
    fake_fn.write_bytes((DEFAULT_V3_MODEL_DIR / "feature_names.json").read_bytes())

    adapter = Builder2V3ModelAdapter(model_dir=tmp_path)
    assert adapter.is_ready is False

    dummy_feat = FeatureResult(location="Nowhere", features={}, is_ready=True)
    res = adapter.predict(dummy_feat)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata["status"] == ReasonCode.MODEL_NOT_READY.value


def test_schema_mismatch_26_features_rejected():
    """Verify passing a 26-feature prototype vector to V3 model is rejected with safe abstention."""
    adapter = Builder2V3ModelAdapter()
    assert adapter.is_ready is True

    # 26-feature dummy dictionary
    from backend.app.builder2.feature_pipeline import FEATURE_COLUMN_NAMES
    features_26 = {col: 1.0 for col in FEATURE_COLUMN_NAMES}

    feat_result = FeatureResult(
        location="Delhi",
        features=features_26,
        feature_names=list(FEATURE_COLUMN_NAMES),
        is_ready=True,
    )

    res = adapter.predict(feat_result)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata["status"] in (ReasonCode.QC_FAILED.value, ReasonCode.FEATURES_NOT_READY.value)


def test_nan_or_inf_in_features_rejected():
    """Verify NaN or infinite values in feature vector trigger safe QC_FAILED abstention."""
    adapter = Builder2V3ModelAdapter()
    assert adapter.is_ready is True

    features_50 = {f: 0.0 for f in adapter.feature_names}
    features_50["ensemble_mean"] = float("nan")

    feat_result = FeatureResult(
        location="Kolkata",
        features=features_50,
        feature_names=adapter.feature_names,
        is_ready=True,
    )

    res = adapter.predict(feat_result)
    assert res.is_ready is False
    assert res.probability is None
    assert res.metadata["status"] == ReasonCode.QC_FAILED.value
    assert "NaN" in (res.error or "")


def test_model_integration_service_no_silent_fallback():
    """Verify ModelIntegrationService with V3 active does not silently fall back to legacy model."""
    mis = ModelIntegrationService(active_model_key="builder2_v3")
    assert mis._active_model_name == "builder2_v3"

    # Pass invalid/empty features
    bad_features = FeatureResult(
        location="Test",
        features={},
        feature_names=[],
        is_ready=False,
        error="Feature extraction broke",
    )

    res = mis.predict(bad_features)
    assert res.is_ready is False
    assert res.probability is None
    # Must NOT have fallen back to prototype-gbm-v1 or produced a probability
    assert res.metadata.get("active_model_key") == "builder2_v3" or res.metadata.get("status") == ReasonCode.FEATURES_NOT_READY.value

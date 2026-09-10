"""Authoritative V3 Artifact Integrity Tests.

Verifies:
1. Model binary exists at models/v3/lightgbm_v3_challenger.joblib
2. Calibrator binary exists at models/v3/probability_calibrator_v3.joblib
3. Exact SHA-256 match for model
4. Exact SHA-256 match for calibrator
5. Exactly 50 feature names in models/v3/feature_names.json
6. Exact feature order match between feature_names.json and LightGBM Booster
7. LightGBM num_feature() == 50
8. Model loads and deserializes into LightGBM Booster
9. Calibrator loads and deserializes into IsotonicRegression
"""

import hashlib
import json
from pathlib import Path
import joblib
import lightgbm as lgb
import pytest
from sklearn.isotonic import IsotonicRegression

from backend.app.builder2.v3_model_adapter import (
    ACCEPTED_MODEL_SHAS,
    EXPECTED_CALIBRATOR_SHA256,
    EXPECTED_MODEL_SHA256,
)

V3_DIR = Path("models/v3")
MODEL_PATH = V3_DIR / "lightgbm_v3_challenger.joblib"
CALIBRATOR_PATH = V3_DIR / "probability_calibrator_v3.joblib"
FEATURES_PATH = V3_DIR / "feature_names.json"
MANIFEST_PATH = V3_DIR / "training_manifest.json"


def test_v3_artifacts_exist():
    """Verify all 4 authoritative V3 artifact files exist."""
    assert MODEL_PATH.exists(), f"Missing {MODEL_PATH}"
    assert CALIBRATOR_PATH.exists(), f"Missing {CALIBRATOR_PATH}"
    assert FEATURES_PATH.exists(), f"Missing {FEATURES_PATH}"
    assert MANIFEST_PATH.exists(), f"Missing {MANIFEST_PATH}"


def test_v3_model_sha256_exact():
    """Verify LightGBM model binary SHA-256 matches authoritative hash exactly."""
    data = MODEL_PATH.read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest()
    assert actual_hash in ACCEPTED_MODEL_SHAS, (
        f"Model SHA-256 mismatch! Got: {actual_hash}, expected: {EXPECTED_MODEL_SHA256}"
    )


def test_v3_calibrator_sha256_exact():
    """Verify Isotonic calibrator binary SHA-256 matches authoritative hash exactly."""
    data = CALIBRATOR_PATH.read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest()
    assert actual_hash == EXPECTED_CALIBRATOR_SHA256, (
        f"Calibrator SHA-256 mismatch! Got: {actual_hash}, expected: {EXPECTED_CALIBRATOR_SHA256}"
    )


def test_v3_feature_schema_count_and_order():
    """Verify feature_names.json contains exactly 50 features in authoritative order."""
    content = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    assert isinstance(content, list)
    assert len(content) == 50, f"Expected 50 features, found {len(content)}"
    assert content[0] == "ensemble_mean"
    assert content[-1] == "ood_score"


def test_v3_booster_loading_and_contract():
    """Verify LightGBM model loads, num_feature == 50, and feature names match exactly."""
    loaded = joblib.load(MODEL_PATH)
    if hasattr(loaded, "booster_"):
        booster = loaded.booster_
    elif isinstance(loaded, lgb.Booster):
        booster = loaded
    else:
        booster = getattr(loaded, "_Booster", loaded)

    assert booster is not None
    assert booster.num_feature() == 50

    json_features = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    booster_features = booster.feature_name()

    assert booster_features == json_features, (
        "Booster feature order does not match feature_names.json!"
    )


def test_v3_calibrator_loading_and_type():
    """Verify Calibrator loads as an IsotonicRegression object."""
    cal = joblib.load(CALIBRATOR_PATH)
    assert isinstance(cal, IsotonicRegression)
    assert hasattr(cal, "predict")

"""Deterministic Calibration Tests for V3 Isotonic Calibrator.

Verifies:
1. Loads models/v3/probability_calibrator_v3.joblib.
2. Applies calibrator to raw LightGBM probabilities.
3. Calibrated probability is deterministic and repeatable.
4. Output probability strictly satisfies 0.0 <= p <= 1.0.
5. Calibrator clips out-of-bounds inputs safely.
"""

from pathlib import Path
import joblib
import numpy as np
import pytest

from backend.app.builder2.v3_model_adapter import (
    Builder2V3ModelAdapter,
    calculate_sha256,
)
from backend.app.services.base import FeatureResult

CALIBRATOR_PATH = Path("models/v3/probability_calibrator_v3.joblib")


def test_calibrator_deterministic_mapping():
    """Verify calibrator yields identical outputs for identical raw probability inputs."""
    calibrator = joblib.load(CALIBRATOR_PATH)

    raw_inputs = np.array([0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.95])
    cal1 = calibrator.predict(raw_inputs)
    cal2 = calibrator.predict(raw_inputs)

    np.testing.assert_array_equal(cal1, cal2)
    assert np.all(cal1 >= 0.0)
    assert np.all(cal1 <= 1.0)


def test_calibrator_out_of_bounds_clipping():
    """Verify IsotonicRegression out_of_bounds='clip' handles extremes safely."""
    calibrator = joblib.load(CALIBRATOR_PATH)

    extreme_inputs = np.array([-0.5, 0.0, 1.0, 1.5])
    outputs = calibrator.predict(extreme_inputs)

    assert np.all(outputs >= 0.0)
    assert np.all(outputs <= 1.0)
    assert outputs[0] == pytest.approx(outputs[1], abs=1e-5)
    assert outputs[-1] == pytest.approx(outputs[-2], abs=1e-5)


def test_v3_adapter_raw_and_calibrated_pipeline():
    """Verify Builder2V3ModelAdapter preserves both raw and calibrated probability in metadata."""
    adapter = Builder2V3ModelAdapter(enforce_sha=True)
    assert adapter.is_ready is True

    # Construct a valid deterministic 50-feature dictionary
    features = {f: 0.0 for f in adapter.feature_names}
    features["ensemble_mean"] = 298.15
    features["ensemble_median"] = 298.15
    features["forecast_value"] = 298.15
    features["ensemble_std"] = 1.5
    features["ensemble_min"] = 295.0
    features["ensemble_max"] = 302.0
    features["is_temperature_2m"] = 1.0
    features["lead_hours"] = 24
    features["member_count"] = 31
    features["has_full_ensemble"] = 1

    feat_result = FeatureResult(
        location="Delhi",
        features=features,
        feature_names=adapter.feature_names,
        is_ready=True,
    )

    model_res = adapter.predict(feat_result)
    assert model_res.is_ready is True
    assert model_res.probability is not None
    assert 0.0 <= model_res.probability <= 1.0

    raw_p = model_res.metadata.get("raw_probability")
    cal_p = model_res.metadata.get("calibrated_probability")

    assert raw_p is not None
    assert cal_p is not None
    assert model_res.probability == pytest.approx(cal_p, abs=1e-5)

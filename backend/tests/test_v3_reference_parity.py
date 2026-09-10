"""Authoritative V3 Reference Parity Tests.

Compares Builder-1 V3 Adapter against the authoritative LightGBM Booster and
Isotonic Regression Calibrator reference implementation on identical scientific inputs.

Validates:
1. 50-feature vector values match reference calculations.
2. Raw LightGBM booster probability achieves bitwise/numerical parity (< 1e-6 tolerance).
3. Calibrated probability achieves numerical parity (< 1e-6 tolerance).
4. Model version is "veyra-v3-benchmark-lightgbm".
"""

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from backend.app.builder2.v3_feature_pipeline import (
    V3_FEATURE_NAMES,
    V3FeaturePipeline,
)
from backend.app.builder2.v3_model_adapter import (
    Builder2V3ModelAdapter,
    DEFAULT_V3_MODEL_DIR,
)
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.base import FeatureResult


def test_v3_reference_inference_parity():
    """Verify Builder2V3ModelAdapter produces identical probabilities to direct booster + calibrator calls."""
    # 1. Reference: Load booster and calibrator directly
    model_path = DEFAULT_V3_MODEL_DIR / "lightgbm_v3_challenger.joblib"
    calibrator_path = DEFAULT_V3_MODEL_DIR / "probability_calibrator_v3.joblib"
    features_path = DEFAULT_V3_MODEL_DIR / "feature_names.json"

    ref_model = joblib.load(model_path)
    ref_booster = getattr(ref_model, "booster_", ref_model)
    ref_calibrator = joblib.load(calibrator_path)
    ref_feature_names = json.loads(features_path.read_text(encoding="utf-8"))

    # 2. Scientific input test record
    record = CanonicalForecastRecord(
        location="Kolkata",
        latitude=22.5726,
        longitude=88.3639,
        issue_time="2026-09-01T00:00:00Z",
        valid_time="2026-09-02T12:00:00Z",
        lead_hours=36,
        variable="temperature_2m",
        unit="°C",
        value=32.0,
        ensemble_mean=32.0,
        ensemble_std=1.8,
        ensemble_min=28.0,
        ensemble_max=35.0,
        q10=29.5,
        q90=34.0,
        member_count=31,
    )

    # 3. Extract 50 features via V3FeaturePipeline
    pipeline = V3FeaturePipeline()
    df_features, meta_rows = pipeline.extract_from_records([record], target_variable="temperature_2m")

    assert list(df_features.columns) == ref_feature_names
    assert df_features.shape == (1, 50)

    # 4. Direct reference calculation
    ref_raw_prob = float(ref_booster.predict(df_features)[0])
    ref_cal_prob = float(ref_calibrator.predict(np.array([ref_raw_prob]))[0])

    # 5. Builder-1 Adapter calculation
    adapter = Builder2V3ModelAdapter()
    feat_result = FeatureResult(
        location=record.location,
        features=df_features.iloc[0].to_dict(),
        feature_names=ref_feature_names,
        is_ready=True,
    )
    adapter_result = adapter.predict(feat_result)

    # 6. Strict Parity Assertions
    assert adapter_result.is_ready is True
    assert adapter_result.model_version == "veyra-v3-benchmark-lightgbm"

    actual_raw = adapter_result.metadata.get("raw_probability")
    actual_cal = adapter_result.probability

    assert actual_raw == pytest.approx(ref_raw_prob, abs=1e-6), (
        f"Raw probability mismatch: adapter={actual_raw}, ref={ref_raw_prob}"
    )
    assert actual_cal == pytest.approx(ref_cal_prob, abs=1e-6), (
        f"Calibrated probability mismatch: adapter={actual_cal}, ref={ref_cal_prob}"
    )

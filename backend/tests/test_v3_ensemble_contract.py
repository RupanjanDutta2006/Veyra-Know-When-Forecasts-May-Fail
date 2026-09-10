"""Deterministic Ensemble Contract Tests for V3.

Verifies:
1. Exact calculations from a synthetic 31-member ensemble vector:
   - mean
   - median
   - sample std (ddof=1)
   - min
   - max
   - range
   - p10
   - p25
   - p75
   - p90
   - IQR (p90 - p10)
   - MAD (0.6745 * IQR)
   - CV (sample_std / mean)
   - quantile spacing ratio
   - tail asymmetry
2. Real N=31 member count is preserved (never downsampled or faked to N=5).
3. has_full_ensemble evaluates to 1 for N=31.
"""

import numpy as np
import pytest

from backend.app.builder2.v3_feature_pipeline import (
    V3FeaturePipeline,
    compute_ensemble_statistics,
)
from backend.app.schemas.weather import CanonicalForecastRecord


def test_synthetic_31_member_ensemble_dispersion():
    """Verify statistical formulas on a deterministic 31-member synthetic array."""
    # Deterministic sequence: 31 values centered around 300.0 Kelvin
    members = [300.0 + (i - 15) * 0.5 for i in range(31)]
    assert len(members) == 31

    stats = compute_ensemble_statistics(members)

    assert stats["member_count"] == 31
    assert stats["ensemble_mean"] == pytest.approx(300.0, abs=1e-5)
    assert stats["ensemble_median"] == pytest.approx(300.0, abs=1e-5)
    assert stats["ensemble_min"] == pytest.approx(292.5, abs=1e-5)
    assert stats["ensemble_max"] == pytest.approx(307.5, abs=1e-5)
    assert stats["ensemble_range"] == pytest.approx(15.0, abs=1e-5)

    # Sample std (ddof=1)
    expected_sample_std = float(np.std(members, ddof=1))
    assert stats["ensemble_std"] == pytest.approx(expected_sample_std, abs=1e-4)

    # Percentiles
    expected_p10 = float(np.percentile(members, 10))
    expected_p25 = float(np.percentile(members, 25))
    expected_p75 = float(np.percentile(members, 75))
    expected_p90 = float(np.percentile(members, 90))

    assert stats["ensemble_p10"] == pytest.approx(expected_p10, abs=1e-4)
    assert stats["ensemble_p25"] == pytest.approx(expected_p25, abs=1e-4)
    assert stats["ensemble_p75"] == pytest.approx(expected_p75, abs=1e-4)
    assert stats["ensemble_p90"] == pytest.approx(expected_p90, abs=1e-4)

    # IQR & MAD
    expected_iqr = expected_p90 - expected_p10
    assert stats["ensemble_iqr"] == pytest.approx(expected_iqr, abs=1e-4)
    assert stats["robust_mad"] == pytest.approx(0.6745 * expected_iqr, abs=1e-4)

    # CV
    expected_cv = expected_sample_std / 300.0
    assert stats["ensemble_cv"] == pytest.approx(expected_cv, abs=1e-4)

    # Symmetric distribution: quantile spacing ratio should be ~1.0, tail asymmetry for uniform is 0.40
    assert stats["quantile_spacing_ratio"] == pytest.approx(1.0, abs=1e-2)
    assert stats["tail_asymmetry"] == pytest.approx(0.40, abs=1e-2)


def test_v3_pipeline_preserves_real_31_member_count():
    """Verify V3FeaturePipeline preserves member_count=31 and sets has_full_ensemble=1."""
    pipeline = V3FeaturePipeline()
    members = [25.0 + (i - 15) * 0.2 for i in range(31)]

    # Pass raw members list in record
    rec_dict = {
        "location": "Mumbai",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "issue_time": "2026-09-01T00:00:00Z",
        "valid_time": "2026-09-02T00:00:00Z",
        "lead_hours": 24,
        "variable": "temperature_2m",
        "unit": "°C",
        "value": 25.0,
        "members": members,
    }

    df_feats, meta = pipeline.extract_from_records([rec_dict], target_variable="temperature_2m")
    row = df_feats.iloc[0]

    assert row["member_count"] == 31
    assert row["has_full_ensemble"] == 1
    # Verify not downsampled to 5
    assert row["member_count"] != 5


def test_v3_asymmetric_ensemble_tail_features():
    """Verify tail asymmetry and kurtosis proxies on a positively skewed ensemble."""
    # Positively skewed distribution: 20 members between 290 and 295K, 11 members spanning up to 330K
    members = [290.0 + i * 0.25 for i in range(20)] + [300.0 + i * 3.0 for i in range(11)]
    assert len(members) == 31
    stats = compute_ensemble_statistics(members)

    # p90 should be significantly farther from median than p10, yielding quantile spacing ratio > 1.0
    assert stats["quantile_spacing_ratio"] > 1.0
    assert stats["tail_asymmetry"] > 0.0
    assert stats["member_count"] == 31

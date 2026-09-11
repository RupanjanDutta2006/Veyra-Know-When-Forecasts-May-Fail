"""
Tests for Veyra Scientific Verification Engine.
"""

import numpy as np
import pytest

from models.verification_engine import ScientificVerificationEngine


def test_verify_continuous_metrics():
    """Verify continuous MAE, RMSE, Bias, and error quantiles computation."""
    fc = np.array([20.0, 22.0, 25.0, 30.0, 28.0])
    ref = np.array([19.0, 23.0, 25.0, 28.0, 30.0])

    metrics = ScientificVerificationEngine.verify_continuous(fc, ref)

    assert metrics["sample_count"] == 5
    assert metrics["bias"] == pytest.approx(0.0, abs=1e-3)
    assert metrics["mae"] == pytest.approx(1.2, abs=1e-3)
    assert metrics["rmse"] > 0.0
    assert metrics["error_p50_median"] >= 0.0


def test_verify_probabilistic_calibration():
    """Verify Brier Score, ECE, and reliability curve generation."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.15, 0.3, 0.8, 0.85, 0.9, 0.75])

    prob_metrics = ScientificVerificationEngine.verify_probabilistic(y_true, y_prob, n_bins=5)

    assert prob_metrics["sample_count"] == 8
    assert prob_metrics["brier_score"] < 0.10
    assert 0.0 <= prob_metrics["expected_calibration_error"] <= 1.0
    assert len(prob_metrics["reliability_curve"]) == 5


def test_verify_ensemble_spread_skill():
    """Verify spread-skill ratio and dispersion regime classification."""
    # Under-dispersed ensemble case
    stds = np.array([0.5, 0.6, 0.4, 0.5])
    errors = np.array([2.0, 3.0, 2.5, 3.5])

    ens_metrics = ScientificVerificationEngine.verify_ensemble(stds, errors)

    assert ens_metrics["spread_skill_ratio"] < 0.8
    assert ens_metrics["dispersion_regime"] == "UNDER_DISPERSED"


def test_verify_classifier_metrics():
    """Verify ROC-AUC, PR-AUC, Confusion Matrix, and FAR."""
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.15, 0.3, 0.8, 0.85, 0.9, 0.75])

    clf_metrics = ScientificVerificationEngine.verify_classifier(y_true, y_prob, threshold=0.5)

    assert clf_metrics["roc_auc"] == 1.0
    assert clf_metrics["pr_auc"] > 0.9
    assert clf_metrics["recall"] == 1.0
    assert clf_metrics["false_alarm_rate"] == 0.0

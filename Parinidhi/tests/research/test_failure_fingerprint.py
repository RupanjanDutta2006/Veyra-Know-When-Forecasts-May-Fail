"""
Tests for Track 3: Failure Fingerprint Engine
"""
import pytest
import numpy as np
from research.failure_fingerprint.engine import FailureFingerprintEngine, FailureFingerprintResult


def test_fingerprint_ensemble_divergence():
    engine = FailureFingerprintEngine()
    features = {
        "lead_hours": 72,
        "variable": "t2m",
        "mclimate_spread_ratio": 2.8, # Extreme ensemble spread relative to climatology
        "dispersion_growth_rate": 0.05,
        "vintage_drift_abs": 0.5
    }
    res = engine.diagnose(features)
    assert res.primary_fingerprint == "ENSEMBLE_DIVERGENCE"
    assert "ENSEMBLE_DIVERGENCE" in res.detected_fingerprints
    assert "Elevated Ensemble Spread" in res.dominant_drivers
    assert "consistent with" in res.scientific_rationale.lower()


def test_fingerprint_revision_instability():
    engine = FailureFingerprintEngine()
    features = {
        "lead_hours": 48,
        "variable": "t2m",
        "mclimate_spread_ratio": 1.1,
        "vintage_drift_abs": 5.2 # Large run-to-run flipping in temperature (5.2 K delta)
    }
    res = engine.diagnose(features)
    assert res.primary_fingerprint == "REVISION_INSTABILITY"
    assert "REVISION_INSTABILITY" in res.detected_fingerprints
    assert "Cycle-to-Cycle Forecast Flipping" in res.dominant_drivers


def test_fingerprint_long_lead_decay():
    engine = FailureFingerprintEngine()
    features = {
        "lead_hours": 216,
        "variable": "sp",
        "mclimate_spread_ratio": 1.0,
        "vintage_drift_abs": 10.0
    }
    res = engine.diagnose(features)
    assert res.primary_fingerprint == "LONG_LEAD_DECAY"


def test_fingerprint_ood():
    engine = FailureFingerprintEngine()
    features = {
        "lead_hours": 48,
        "variable": "t2m",
        "mahalanobis_dist": 5.8 # Extreme OOD distance
    }
    res = engine.diagnose(features)
    assert res.primary_fingerprint == "OOD_CONDITION"
    assert res.is_ood is True


def test_fingerprint_nominal_state():
    engine = FailureFingerprintEngine()
    features = {
        "lead_hours": 24,
        "variable": "t2m",
        "mclimate_spread_ratio": 0.9,
        "vintage_drift_abs": 0.2
    }
    res = engine.diagnose(features)
    assert res.primary_fingerprint == "NO_DOMINANT_FINGERPRINT"
    assert len(res.detected_fingerprints) == 0

"""
Tests for Track 2: Operational Trust Horizon Engine
"""
import pytest
import numpy as np
from research.trust_horizon.engine import TrustHorizonEngine, TrustHorizonReport


def test_trust_horizon_stable_trajectory():
    engine = TrustHorizonEngine(risk_tolerance=0.35)
    # Low bust probability across entire 10-day range
    leads = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240]
    lead_probs = {l: 0.10 + 0.0005 * l for l in leads} # max prob at +240h is 0.22 < 0.35

    report = engine.evaluate_horizon(lead_probs)
    assert report.is_fully_trustworthy_to_day10 is True
    assert report.h_rel is None
    assert report.dominant_degradation_mechanism == "STABLE_MEDIUM_RANGE_RELIABILITY"
    assert report.confidence_score >= 0.85


def test_trust_horizon_early_degradation():
    engine = TrustHorizonEngine(risk_tolerance=0.35)
    # Rapid degradation by Day 3 (+72h)
    lead_probs = {
        24: 0.15, 48: 0.25, 72: 0.42, 96: 0.55, 120: 0.65,
        144: 0.70, 168: 0.75, 192: 0.80, 216: 0.85, 240: 0.90
    }

    report = engine.evaluate_horizon(lead_probs)
    assert report.is_fully_trustworthy_to_day10 is False
    assert report.h_rel == 72
    assert report.degradation_onset_lead is not None
    assert report.dominant_degradation_mechanism == "EARLY_SHORT_RANGE_INSTABILITY"


def test_trust_horizon_climatology_comparison():
    engine = TrustHorizonEngine(risk_tolerance=0.35)
    lead_probs = {24: 0.10, 48: 0.20, 72: 0.30, 96: 0.50, 120: 0.60}
    clim_probs = {24: 0.25, 48: 0.25, 72: 0.25, 96: 0.25, 120: 0.25}

    report = engine.evaluate_horizon(lead_probs, climatological_probs=clim_probs)
    assert report.h_skill_clim == 96 # Exceeds clim + 0.15 at +96h

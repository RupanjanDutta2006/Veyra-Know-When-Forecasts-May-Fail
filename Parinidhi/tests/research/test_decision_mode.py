"""
Tests for Track 4: Decision Mode Engine
"""
import pytest
import numpy as np
from research.decision.mode_engine import DecisionModeEngine, DecisionMode, DecisionModeResult


def test_decision_mode_normal():
    engine = DecisionModeEngine()
    res = engine.evaluate(calibrated_prob=0.12, lead_hours=48, trust_horizon_lead=144)
    assert res.mode == DecisionMode.NORMAL
    assert res.is_abstain is False
    assert "NOMINAL_DISPERSION" in res.reason_codes
    assert "trustworthy" in res.recommended_action.lower()


def test_decision_mode_caution():
    engine = DecisionModeEngine()
    res = engine.evaluate(calibrated_prob=0.28, lead_hours=72, trust_horizon_lead=144)
    assert res.mode == DecisionMode.CAUTION
    assert res.is_abstain is False
    assert "MODERATE_BUST_PROBABILITY" in res.reason_codes


def test_decision_mode_verify_high_prob():
    engine = DecisionModeEngine()
    res = engine.evaluate(calibrated_prob=0.62, lead_hours=48, trust_horizon_lead=144)
    assert res.mode == DecisionMode.VERIFY
    assert res.is_abstain is False
    assert "HIGH_BUST_PROBABILITY" in res.reason_codes


def test_decision_mode_verify_past_trust_horizon():
    engine = DecisionModeEngine()
    res = engine.evaluate(calibrated_prob=0.15, lead_hours=168, trust_horizon_lead=120)
    assert res.mode == DecisionMode.VERIFY
    assert "LEAD_EXCEEDS_TRUST_HORIZON" in res.reason_codes


def test_decision_mode_abstain_nan():
    engine = DecisionModeEngine()
    res = engine.evaluate(calibrated_prob=np.nan, lead_hours=48)
    assert res.mode == DecisionMode.ABSTAIN
    assert res.is_abstain is True
    assert "MISSING_PROBABILITY" in res.reason_codes


def test_decision_mode_abstain_extreme_ood():
    engine = DecisionModeEngine()
    res = engine.evaluate(calibrated_prob=0.25, lead_hours=48, ood_score=5.2)
    assert res.mode == DecisionMode.ABSTAIN
    assert res.is_abstain is True
    assert "EXTREME_OOD_STATE" in res.reason_codes


def test_decision_mode_abstain_excessive_missingness():
    engine = DecisionModeEngine()
    res = engine.evaluate(calibrated_prob=0.30, lead_hours=48, missing_feature_ratio=0.40)
    assert res.mode == DecisionMode.ABSTAIN
    assert res.is_abstain is True
    assert "EXCESSIVE_FEATURE_MISSINGNESS" in res.reason_codes

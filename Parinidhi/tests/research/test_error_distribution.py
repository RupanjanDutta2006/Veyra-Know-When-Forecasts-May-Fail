"""
Tests for Track 1: Conditional Error Distribution Engine
"""
import pytest
import numpy as np
from research.error_distribution.quantile_mesh import QuantileMeshDistribution, build_synthetic_error_knots
from research.error_distribution.parametric import ParametricErrorDistribution
from research.error_distribution.calibrator import LeadConditionedCalibrator


def test_quantile_mesh_monotonicity():
    mesh = QuantileMeshDistribution()
    # Unsorted knots
    raw_knots = np.array([3.0, 1.0, 4.0, 2.0, 5.0, 0.5, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0])
    sorted_knots = mesh.enforce_monotonicity(raw_knots)
    assert np.all(np.diff(sorted_knots) >= 0), "Monotonic rearrangement failed!"


def test_quantile_mesh_cdf_bounds():
    mesh = QuantileMeshDistribution()
    knots = np.linspace(-5.0, 5.0, len(mesh.quantiles))
    
    # Values far in left and right tails
    cdf_left = mesh.cdf(knots, -100.0)
    cdf_right = mesh.cdf(knots, 100.0)
    cdf_center = mesh.cdf(knots, 0.0)

    assert 0.0 <= cdf_left <= 0.01, f"Left tail CDF out of bounds: {cdf_left}"
    assert 0.99 <= cdf_right <= 1.0, f"Right tail CDF out of bounds: {cdf_right}"
    assert 0.45 <= cdf_center <= 0.55, f"Center CDF out of bounds: {cdf_center}"


def test_quantile_mesh_prob_exceedance_abs():
    mesh = QuantileMeshDistribution()
    knots = build_synthetic_error_knots(mean_bias=0.0, spread=2.0, lead_hours=48)
    
    p_small = mesh.prob_exceedance_abs(knots, tau=0.5)
    p_large = mesh.prob_exceedance_abs(knots, tau=10.0)

    assert 0.0 <= p_small <= 1.0
    assert 0.0 <= p_large <= 1.0
    assert p_small > p_large, "P(|e| >= small_tau) should exceed P(|e| >= large_tau)"


def test_quantile_mesh_nan_propagation():
    mesh = QuantileMeshDistribution()
    nan_knots = np.full(len(mesh.quantiles), np.nan)
    assert np.isnan(mesh.prob_exceedance_abs(nan_knots, tau=3.0))
    assert np.isnan(mesh.cdf(nan_knots, 0.0))


def test_parametric_student_t():
    param = ParametricErrorDistribution(family="student_t")
    fit = param.fit_parameters(np.random.normal(0.0, 2.0, 500))
    assert "loc" in fit and "scale" in fit and "df" in fit
    p_exceed = param.prob_exceedance_abs(fit, tau=3.0)
    assert 0.0 <= p_exceed <= 1.0


def test_lead_conditioned_calibrator():
    cal = LeadConditionedCalibrator(method="isotonic")
    raw_p = np.linspace(0.1, 0.9, 100)
    labels = (raw_p > 0.5).astype(float)
    
    cal.fit(lead_hours=48, raw_probs=raw_p, true_labels=labels)
    p_cal = cal.predict_proba(lead_hours=48, raw_probs=np.array([0.2, 0.8]))
    
    assert len(p_cal) == 2
    assert p_cal[0] <= p_cal[1]
    assert np.all((p_cal >= 0.0) & (p_cal <= 1.0))

"""Unit tests for Bust Labeling Policy Engine."""
import pytest
from backend.app.data.bust_labeling import (
    FixedThresholdBustPolicy,
    QuantileBustPolicy,
)


def test_fixed_threshold_policy_temperature():
    """Test fixed threshold bust classification on temperature."""
    policy = FixedThresholdBustPolicy()
    # Default temperature threshold is 3.0 °C
    res_no_bust = policy.evaluate("temperature_2m", absolute_error=2.4)
    assert res_no_bust.is_bust == 0
    assert res_no_bust.threshold == 3.0

    res_bust = policy.evaluate("temperature_2m", absolute_error=3.8)
    assert res_bust.is_bust == 1
    assert res_bust.threshold == 3.0


def test_fixed_threshold_policy_pressure_and_wind():
    """Test fixed threshold bust classification on pressure and wind."""
    policy = FixedThresholdBustPolicy()
    # Pressure threshold is 4.0 hPa
    assert policy.evaluate("surface_pressure", absolute_error=3.5).is_bust == 0
    assert policy.evaluate("surface_pressure", absolute_error=4.5).is_bust == 1

    # Wind speed threshold is 4.0 m/s
    assert policy.evaluate("wind_speed_10m", absolute_error=2.0).is_bust == 0
    assert policy.evaluate("wind_speed_10m", absolute_error=5.2).is_bust == 1


def test_quantile_bust_policy_fitting():
    """Test that QuantileBustPolicy fits extreme quantile thresholds from training error distributions."""
    policy = QuantileBustPolicy(quantile=0.90, min_samples=10)

    # Generate synthetic training errors for temperature day4-7 (lead_hours = 96)
    # Errors: 1.0, 1.2, ..., 5.0 (90th percentile should be ~ 4.6)
    training_errors = [
        {"variable": "temperature_2m", "lead_hours": 96, "absolute_error": float(i) * 0.5}
        for i in range(1, 15)  # 14 samples: 0.5 to 7.0
    ]
    policy.fit_from_errors(training_errors)

    # Key (temperature_2m, day4-7) should now be fitted
    key = ("temperature_2m", "day4-7")
    assert key in policy.fitted_thresholds
    fitted_thresh = policy.fitted_thresholds[key]

    # Evaluate test error against fitted threshold
    eval_below = policy.evaluate("temperature_2m", absolute_error=fitted_thresh - 0.5, lead_hours=96)
    assert eval_below.is_bust == 0
    assert eval_below.threshold == fitted_thresh

    eval_above = policy.evaluate("temperature_2m", absolute_error=fitted_thresh + 0.5, lead_hours=96)
    assert eval_above.is_bust == 1


def test_quantile_bust_policy_fallback():
    """Test fallback to fixed threshold policy when sample count is insufficient or bin unfitted."""
    policy = QuantileBustPolicy(quantile=0.95, min_samples=20)
    # No training data fitted yet -> falls back to FixedThresholdPolicy
    res = policy.evaluate("temperature_2m", absolute_error=3.5, lead_hours=48)
    assert res.is_bust == 1
    assert "Fallback" in res.policy_name


def test_quantile_policy_invalid_quantile_raises():
    """Test that invalid quantiles outside (0.5, 1.0) raise ValueError."""
    with pytest.raises(ValueError):
        QuantileBustPolicy(quantile=0.3)
    with pytest.raises(ValueError):
        QuantileBustPolicy(quantile=1.2)

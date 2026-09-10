"""Deterministic Unit Transformation Contract Tests for V3.

Verifies:
1. 0°C -> 273.15 K
2. 25°C -> 298.15 K
3. 1000 hPa -> 100000 Pa
4. Wind speed in m/s remains unchanged (SI canonical)
5. Wind speed in km/h converts to m/s correctly (divide by 3.6)
6. Derived V3 features (e.g., CV, IQR, midpoint, skew proxy) operate strictly in the transformed Kelvin/Pascal space.
"""

import numpy as np
import pytest

from backend.app.builder2.v3_feature_pipeline import (
    V3FeaturePipeline,
    convert_units_to_v3,
)
from backend.app.schemas.weather import CanonicalForecastRecord


def test_temperature_zero_celsius_to_kelvin():
    """Verify 0°C converts to exactly 273.15 K."""
    val_k = convert_units_to_v3("temperature_2m", 0.0, "°C")
    assert val_k == 273.15


def test_temperature_twenty_five_celsius_to_kelvin():
    """Verify 25°C converts to exactly 298.15 K."""
    val_k = convert_units_to_v3("temperature_2m", 25.0, "celsius")
    assert val_k == 298.15


def test_surface_pressure_hpa_to_pascal():
    """Verify 1000 hPa converts to exactly 100000 Pa."""
    val_pa = convert_units_to_v3("surface_pressure", 1000.0, "hPa")
    assert val_pa == 100000.0


def test_wind_speed_ms_unchanged():
    """Verify wind speed in m/s remains numerically identical."""
    val_ms = convert_units_to_v3("wind_speed_10m", 12.5, "m/s")
    assert val_ms == 12.5


def test_wind_speed_kmh_to_ms():
    """Verify wind speed in km/h is converted to m/s."""
    val_ms = convert_units_to_v3("wind_speed_10m", 36.0, "km/h")
    assert val_ms == 10.0


def test_derived_features_use_transformed_unit_space():
    """Verify derived statistics like CV and spread_x_lead use transformed units.

    For 25°C with std 2.5°C:
    In Kelvin: mean = 298.15 K, std = 2.5 K
    CV = 2.5 / 298.15 ≈ 0.008385
    In Celsius, CV would have been 2.5 / 25 = 0.100 (which is an order of magnitude difference).
    """
    pipeline = V3FeaturePipeline()
    record = CanonicalForecastRecord(
        location="Delhi",
        latitude=28.6139,
        longitude=77.2090,
        issue_time="2026-09-01T00:00:00Z",
        valid_time="2026-09-02T00:00:00Z",
        lead_hours=24,
        variable="temperature_2m",
        unit="°C",
        value=25.0,
        ensemble_mean=25.0,
        ensemble_std=2.5,
        ensemble_min=20.0,
        ensemble_max=30.0,
        q10=21.0,
        q90=29.0,
        member_count=31,
    )

    df_feats, meta = pipeline.extract_from_records([record], target_variable="temperature_2m")
    assert not df_feats.empty

    row = df_feats.iloc[0]

    # Verify basic units in feature row
    assert row["ensemble_mean"] == pytest.approx(298.15, rel=1e-3)
    assert row["forecast_value"] == pytest.approx(298.15, rel=1e-3)
    assert row["ensemble_min"] == pytest.approx(293.15, rel=1e-3)
    assert row["ensemble_max"] == pytest.approx(303.15, rel=1e-3)
    assert row["ensemble_std"] == pytest.approx(2.5, rel=1e-3)

    # Verify CV is calculated in Kelvin space (< 0.02, NOT 0.10)
    expected_cv = 2.5 / (298.15 + 1e-6)
    assert row["ensemble_cv"] == pytest.approx(expected_cv, rel=1e-3)
    assert row["ensemble_cv"] < 0.02


def test_pressure_spread_scaled_to_pascal():
    """Verify pressure std is scaled by 100 into Pascal."""
    pipeline = V3FeaturePipeline()
    record = CanonicalForecastRecord(
        location="Mumbai",
        latitude=19.0760,
        longitude=72.8777,
        issue_time="2026-09-01T00:00:00Z",
        valid_time="2026-09-02T00:00:00Z",
        lead_hours=24,
        variable="surface_pressure",
        unit="hPa",
        value=1013.25,
        ensemble_mean=1013.25,
        ensemble_std=2.0,  # 2.0 hPa
        ensemble_min=1009.0,
        ensemble_max=1017.0,
        q10=1010.0,
        q90=1016.0,
        member_count=31,
    )

    df_feats, meta = pipeline.extract_from_records([record], target_variable="surface_pressure")
    row = df_feats.iloc[0]

    assert row["ensemble_mean"] == pytest.approx(101325.0, rel=1e-3)
    # std should be 200 Pa, NOT 2.0 Pa
    assert row["ensemble_std"] == pytest.approx(200.0, rel=1e-3)

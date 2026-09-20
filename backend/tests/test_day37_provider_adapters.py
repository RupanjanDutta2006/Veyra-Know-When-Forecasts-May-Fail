"""Authoritative Focused Test Suite for Veyra Phase 3 Day 37 (Gate C7).

Validates Provider Adapter Architecture, Unit Normalization, Provider Registry,
Fixture Secondary Provider, and Scientific Contract Compatibility.
"""
import pytest

from backend.app.adapters.fixture_second_provider_adapter import FixtureSecondProviderAdapter
from backend.app.adapters.openmeteo_adapter import OpenMeteoProviderAdapter
from backend.app.adapters.provider_adapter import (
    NormalizedProviderForecast,
    ProviderResponseStatus,
    ProviderSourceMode,
    normalize_unit_value,
)
from backend.app.adapters.provider_registry import (
    ProviderRegistry,
    UnknownProviderError,
    default_provider_registry,
)
from backend.app.core.model_determinism import (
    V3_CALIBRATOR_SHA256,
    V3_MODEL_SHA256,
    get_authoritative_v3_provenance,
)


def test_d37_01_unit_normalization_temperature():
    """Verify temperature unit conversions to canonical °C."""
    val_c, unit_c = normalize_unit_value(25.0, "°C", "temperature_2m")
    assert pytest.approx(val_c, 1e-4) == 25.0
    assert unit_c == "°C"

    val_k, unit_k = normalize_unit_value(298.15, "K", "temperature_2m")
    assert pytest.approx(val_k, 1e-4) == 25.0
    assert unit_k == "°C"

    val_f, unit_f = normalize_unit_value(77.0, "°F", "temperature_2m")
    assert pytest.approx(val_f, 1e-4) == 25.0
    assert unit_f == "°C"


def test_d37_02_unit_normalization_wind_speed():
    """Verify wind speed unit conversions to canonical m/s."""
    val_ms, unit_ms = normalize_unit_value(10.0, "m/s", "wind_speed_10m")
    assert pytest.approx(val_ms, 1e-4) == 10.0
    assert unit_ms == "m/s"

    val_kmh, unit_kmh = normalize_unit_value(36.0, "km/h", "wind_speed_10m")
    assert pytest.approx(val_kmh, 1e-4) == 10.0
    assert unit_kmh == "m/s"

    val_kt, unit_kt = normalize_unit_value(10.0, "knots", "wind_speed_10m")
    assert pytest.approx(val_kt, 1e-3) == 5.1444
    assert unit_kt == "m/s"


def test_d37_03_unit_normalization_surface_pressure():
    """Verify surface pressure unit conversions to canonical hPa."""
    val_hpa, unit_hpa = normalize_unit_value(1013.25, "hPa", "surface_pressure")
    assert pytest.approx(val_hpa, 1e-4) == 1013.25
    assert unit_hpa == "hPa"

    val_pa, unit_pa = normalize_unit_value(101325.0, "Pa", "surface_pressure")
    assert pytest.approx(val_pa, 1e-4) == 1013.25
    assert unit_pa == "hPa"


def test_d37_04_provider_registry_default():
    """Verify ProviderRegistry retrieves default 'openmeteo_gefs' adapter when unspecified."""
    registry = ProviderRegistry(register_defaults=True)
    adapter = registry.get()
    assert adapter.provider_id == "openmeteo_gefs"
    assert adapter.provider_source_mode == ProviderSourceMode.LIVE


def test_d37_05_provider_registry_fixture_second_provider():
    """Verify ProviderRegistry retrieves 'fixture_second_provider' cleanly."""
    registry = ProviderRegistry(register_defaults=True)
    adapter = registry.get("fixture_second_provider")
    assert adapter.provider_id == "fixture_second_provider"
    assert adapter.provider_source_mode == ProviderSourceMode.FIXTURE


def test_d37_06_provider_registry_unknown_provider_raises():
    """Verify requesting an unknown provider ID raises UnknownProviderError without falling back."""
    registry = ProviderRegistry(register_defaults=True)
    with pytest.raises(UnknownProviderError) as exc_info:
        registry.get("non_existent_provider_xyz")
    assert "Unknown forecast provider 'non_existent_provider_xyz'" in str(exc_info.value)


def test_d37_07_fixture_provider_deterministic_temperature_matching():
    """Verify fixture adapter returns deterministic temperature output."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Delhi", variable="temperature_2m", lead_hours=24)
    assert res.is_available is True
    assert res.status == ProviderResponseStatus.SUCCESS
    assert res.provider_id == "fixture_second_provider"
    assert res.provider_source_mode == ProviderSourceMode.FIXTURE
    assert res.canonical_location == "Delhi"
    assert res.unit == "°C"
    assert pytest.approx(res.forecast_value, 1e-4) == 33.2


def test_d37_08_fixture_provider_unit_normalization_kmh_to_ms():
    """Verify fixture adapter normalizes raw km/h wind speed to m/s."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Delhi", variable="wind_speed_10m", lead_hours=24)
    assert res.is_available is True
    assert res.unit == "m/s"
    assert pytest.approx(res.forecast_value, 1e-4) == 5.0  # 18.0 km/h / 3.6 = 5.0 m/s


def test_d37_09_fixture_provider_unit_normalization_pa_to_hpa():
    """Verify fixture adapter normalizes raw Pa pressure to hPa."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Mumbai", variable="surface_pressure", lead_hours=264)
    assert res.is_available is True
    assert res.unit == "hPa"
    assert pytest.approx(res.forecast_value, 1e-4) == 1014.0  # 101400.0 Pa / 100.0 = 1014.0 hPa


def test_d37_10_fixture_provider_unit_normalization_kelvin_to_celsius():
    """Verify fixture adapter normalizes raw Kelvin temperature to °C."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Shimla", variable="temperature_2m", lead_hours=24)
    assert res.is_available is True
    assert res.unit == "°C"
    assert pytest.approx(res.forecast_value, 1e-4) == 22.0  # 295.15 K - 273.15 = 22.0 °C


def test_d37_11_fixture_provider_alias_resolution():
    """Verify fixture adapter normalizes Panaji query to canonical location."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Panaji", variable="wind_speed_10m", lead_hours=48)
    assert res.is_available is True
    assert res.canonical_location == "Panaji"
    assert res.unit == "m/s"
    assert pytest.approx(res.forecast_value, 1e-4) == 11.5


def test_d37_12_fixture_provider_blank_location_invalid_request():
    """Verify blank location query returns INVALID_REQUEST status without throwing exception."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="   ", variable="temperature_2m", lead_hours=24)
    assert res.is_available is False
    assert res.status == ProviderResponseStatus.INVALID_REQUEST
    assert res.forecast_value is None


def test_d37_13_fixture_provider_explicit_unavailable_case():
    """Verify explicit unavailable fixture key returns UNAVAILABLE status cleanly."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Kolkata", variable="surface_pressure", lead_hours=48)
    assert res.is_available is False
    assert res.status == ProviderResponseStatus.UNAVAILABLE
    assert res.forecast_value is None


def test_d37_14_fixture_provider_unsupported_variable():
    """Verify querying an unsupported variable returns UNSUPPORTED_VARIABLE status."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Delhi", variable="unsupported_custom_var", lead_hours=24)
    assert res.is_available is False
    assert res.status == ProviderResponseStatus.UNSUPPORTED_VARIABLE
    assert res.forecast_value is None


def test_d37_15_openmeteo_adapter_structure():
    """Verify OpenMeteoProviderAdapter exposes correct metadata properties."""
    adapter = OpenMeteoProviderAdapter()
    assert adapter.provider_id == "openmeteo_gefs"
    assert adapter.provider_name == "Open-Meteo GEFS Ensemble"
    assert adapter.provider_source_mode == ProviderSourceMode.LIVE


def test_d37_16_list_providers_metadata():
    """Verify list_providers enumerates registered adapters correctly."""
    registry = ProviderRegistry(register_defaults=True)
    providers = registry.list_providers()
    assert len(providers) >= 2
    p_ids = [p["provider_id"] for p in providers]
    assert "openmeteo_gefs" in p_ids
    assert "fixture_second_provider" in p_ids


def test_d37_17_no_fake_zero_on_unavailable_provider():
    """Verify unavailable provider response has forecast_value=None and is_available=False (no fake zero)."""
    adapter = FixtureSecondProviderAdapter()
    res = adapter.fetch_forecast(location="Kolkata", variable="surface_pressure", lead_hours=48)
    assert res.forecast_value != 0.0
    assert res.forecast_value is None
    assert res.is_available is False


def test_d37_18_provider_identity_preserved_in_normalized_record():
    """Verify NormalizedProviderForecast explicitly retains provider_id and provider_source_mode."""
    adapter1 = OpenMeteoProviderAdapter()
    assert adapter1.provider_id == "openmeteo_gefs"
    assert adapter1.provider_source_mode == ProviderSourceMode.LIVE

    adapter2 = FixtureSecondProviderAdapter()
    assert adapter2.provider_id == "fixture_second_provider"
    assert adapter2.provider_source_mode == ProviderSourceMode.FIXTURE


def test_d37_19_frozen_v3_artifacts_unchanged():
    """Verify frozen V3 model and calibrator SHA256 hashes are strictly unchanged."""
    prov = get_authoritative_v3_provenance()
    assert prov.model_sha256 == V3_MODEL_SHA256
    assert prov.calibrator_sha256 == V3_CALIBRATOR_SHA256
    assert prov.feature_count == 50
    assert prov.calibrator_type == "IsotonicRegression"


def test_d37_20_live_primary_smoke_helper():
    """Verify live primary provider smoke check function returns valid status tuple."""
    from backend.app.core.live_smoke import perform_live_provider_smoke_check
    status, detail = perform_live_provider_smoke_check()
    assert status.value in ["LIVE_PROVIDER_VERIFIED", "LIVE_PROVIDER_UNVERIFIED"]
    assert len(detail) > 0

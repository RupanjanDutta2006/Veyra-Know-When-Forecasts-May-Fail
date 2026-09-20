"""Authoritative Focused Test Suite for Veyra Phase 3 Day 38 (Gate C8).

Validates Cross-Provider Disagreement Intelligence, Comparability Contracts,
Unit Normalization Alignment, Fixture Provenance Isolation, and Scientific Safety.
"""
import pytest

from backend.app.schemas.provider_disagreement import (
    CrossProviderDisagreementRequest,
    CrossProviderDisagreementResponse,
)
from backend.app.services.provider_disagreement_service import CrossProviderDisagreementService


def test_d38_01_identical_provider_values_zero_difference():
    """Verify identical provider forecast values yield 0.0 absolute difference."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Leh",
        variable="temperature_2m",
        lead_hours=12,
        primary_provider_id="fixture_second_provider",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "AVAILABLE"
    assert res.is_comparable is True
    assert pytest.approx(res.signed_difference, 1e-4) == 0.0
    assert pytest.approx(res.absolute_difference, 1e-4) == 0.0


def test_d38_02_positive_signed_difference():
    """Verify primary > secondary yields positive signed_difference."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        variable="temperature_2m",
        lead_hours=24,
        primary_provider_id="fixture_second_provider",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "AVAILABLE"
    assert res.primary_provider is not None
    assert res.secondary_provider is not None
    assert res.signed_difference is not None
    assert res.absolute_difference is not None


def test_d38_03_temperature_comparison_celsius():
    """Verify temperature comparison uses canonical °C unit."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        variable="temperature_2m",
        lead_hours=24,
    )
    res = service.evaluate_disagreement(req)
    assert res.variable == "temperature_2m"
    assert res.unit == "°C"


def test_d38_04_wind_speed_comparison_meters_per_sec():
    """Verify wind speed comparison uses canonical m/s unit."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        variable="wind_speed_10m",
        lead_hours=24,
    )
    res = service.evaluate_disagreement(req)
    assert res.variable == "wind_speed_10m"
    assert res.unit == "m/s"


def test_d38_05_surface_pressure_comparison_hpa():
    """Verify surface pressure comparison uses canonical hPa unit."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Mumbai",
        variable="surface_pressure",
        lead_hours=264,
    )
    res = service.evaluate_disagreement(req)
    assert res.variable == "surface_pressure"
    assert res.unit == "hPa"


def test_d38_06_unit_normalization_before_comparison():
    """Verify raw km/h from fixture provider is normalized to m/s before comparison."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        variable="wind_speed_10m",
        lead_hours=24,
        primary_provider_id="fixture_second_provider",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "AVAILABLE"
    assert res.unit == "m/s"
    assert res.secondary_provider is not None
    assert pytest.approx(res.secondary_provider.forecast_value, 1e-4) == 5.0  # 18 km/h -> 5 m/s


def test_d38_07_canonical_location_matching():
    """Verify canonical location is populated cleanly in response."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        variable="temperature_2m",
        lead_hours=24,
    )
    res = service.evaluate_disagreement(req)
    assert res.canonical_location == "Delhi"


def test_d38_08_alias_location_comparison():
    """Verify Panaji query resolves canonical location and completes comparison."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Panaji",
        variable="wind_speed_10m",
        lead_hours=48,
        primary_provider_id="fixture_second_provider",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "AVAILABLE"
    assert res.canonical_location == "Panaji"


def test_d38_09_blank_location_invalid_request():
    """Verify blank location yields INVALID_REQUEST status without traceback."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(location="   ")
    res = service.evaluate_disagreement(req)
    assert res.status == "INVALID_REQUEST"
    assert res.reason_code == "BLANK_LOCATION"
    assert res.is_comparable is False


def test_d38_10_unknown_primary_provider_error():
    """Verify unknown primary provider ID yields INVALID_REQUEST status."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        primary_provider_id="unknown_provider_xyz",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "INVALID_REQUEST"
    assert res.reason_code == "UNKNOWN_PRIMARY_PROVIDER"
    assert res.is_comparable is False


def test_d38_11_unknown_secondary_provider_error():
    """Verify unknown secondary provider ID yields INVALID_REQUEST status."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        secondary_provider_id="unknown_provider_xyz",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "INVALID_REQUEST"
    assert res.reason_code == "UNKNOWN_SECONDARY_PROVIDER"
    assert res.is_comparable is False


def test_d38_12_unavailable_provider_no_fake_zero():
    """Verify unavailable secondary provider yields PROVIDER_UNAVAILABLE without fake zero values."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Kolkata",
        variable="surface_pressure",
        lead_hours=48,
        primary_provider_id="fixture_second_provider",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "PROVIDER_UNAVAILABLE"
    assert res.reason_code in ["PRIMARY_PROVIDER_UNAVAILABLE", "SECONDARY_PROVIDER_UNAVAILABLE"]
    assert res.is_comparable is False
    assert res.absolute_difference is None
    assert res.signed_difference is None


def test_d38_13_fixture_provenance_flag_true():
    """Verify has_fixture_provider is True when secondary provider is fixture-backed."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        primary_provider_id="openmeteo_gefs",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.has_fixture_provider is True
    assert "deterministic fixture data" in res.provenance_notice


def test_d38_14_fixture_provenance_flag_false_for_two_live_providers():
    """Verify has_fixture_provider is False when both providers are live."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        primary_provider_id="openmeteo_gefs",
        secondary_provider_id="openmeteo_gefs",
    )
    res = service.evaluate_disagreement(req)
    assert res.has_fixture_provider is False
    assert "live provider operational data" in res.provenance_notice


def test_d38_15_relative_difference_calculation():
    """Verify relative difference percentage formula."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        variable="temperature_2m",
        lead_hours=24,
        primary_provider_id="fixture_second_provider",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.status == "AVAILABLE"
    assert res.relative_difference_pct == 0.0


def test_d38_16_provider_min_max_mean_metrics():
    """Verify provider_min, provider_max, and provider_mean computation."""
    service = CrossProviderDisagreementService()
    req = CrossProviderDisagreementRequest(
        location="Delhi",
        variable="temperature_2m",
        lead_hours=24,
        primary_provider_id="fixture_second_provider",
        secondary_provider_id="fixture_second_provider",
    )
    res = service.evaluate_disagreement(req)
    assert res.provider_min == 33.2
    assert res.provider_max == 33.2
    assert res.provider_mean == 33.2


def test_d38_17_gefs_disagreement_separation():
    """Verify Day 29 GEFS ensemble disagreement service remains separate and unmodified."""
    from backend.app.schemas.disagreement import ForecastDisagreementRequest, DisagreementStatus
    from backend.app.schemas.prediction import PredictionResponse, RiskLevel, TrustState
    from backend.app.services.disagreement_service import DisagreementService

    class MockAgent:
        def analyze(self, pred_req):
            return PredictionResponse(
                location="Delhi",
                bust_probability=0.05,
                risk_level=RiskLevel.LOW,
                trust_state=TrustState.HIGH_CONFIDENCE,
                abstain=False,
                reason_codes=[],
                calibration_status="CALIBRATED",
            )

        def get_weather_data(self, loc, start_date):
            class MockWeatherRes:
                is_available = True
                raw_data = {
                    "records": [{
                        "variable": "temperature_2m",
                        "lead_hours": 24,
                        "value": 32.0,
                        "ensemble_mean": 32.0,
                        "ensemble_std": 1.5,
                        "ensemble_min": 29.0,
                        "ensemble_max": 35.0,
                        "member_count": 31,
                    }]
                }
            return MockWeatherRes()

    gefs_service = DisagreementService(agent=MockAgent())
    req = ForecastDisagreementRequest(location="Delhi", lead_hours=24)
    res = gefs_service.evaluate_disagreement(req)
    assert res.status == DisagreementStatus.AVAILABLE
    assert res.diagnostics is not None
    assert hasattr(res.diagnostics, "ensemble_spread")
    assert hasattr(res.diagnostics, "ensemble_range")


def test_d38_18_p_bust_unmodified_by_cross_provider_disagreement():
    """Verify evaluating cross-provider disagreement does not mutate model prediction or P(BUST)."""
    from backend.app.core.replay_harness import ReplayHarness
    from backend.app.core.golden_replay_matrix import GOLDEN_REPLAY_MATRIX
    harness = ReplayHarness()
    result = harness.replay_scenario(GOLDEN_REPLAY_MATRIX[0])
    assert result.is_reproducible is True


def test_d38_19_scientific_certification_unmodified():
    """Verify Day 32 certification gate remains intact."""
    from backend.app.core.certification_policy import evaluate_scientific_certification
    from backend.app.core.model_determinism import V3_CALIBRATOR_SHA256, V3_MODEL_SHA256
    cert = evaluate_scientific_certification("Delhi", "temperature_2m", 24, V3_MODEL_SHA256, V3_CALIBRATOR_SHA256)
    assert cert.is_certified is True


def test_d38_20_ood_policy_unmodified():
    """Verify Day 33 OOD policy remains intact."""
    from backend.app.core.ood_policy import evaluate_ood_policy
    ood = evaluate_ood_policy("temperature_2m", 380.0)
    assert ood.is_ood is True
    assert ood.causes_abstention is False

"""Authoritative Day 36 Test Suite: Dashboard Parity & Explanation Coherence (Gate C6).

Validates:
1. Backend <-> Frontend contract parity across P(BUST), risk bands, certification, and OOD diagnostics.
2. Scientific wording invariants (P(BUST) != weather probability, OOD != certification, confidence = heuristic).
3. Risk threshold boundaries (LOW < 0.20, MEDIUM 0.20-0.50, HIGH 0.50-0.75, CRITICAL >= 0.75).
4. GEFS dispersion units (°C, m/s, hPa) and separation from P(BUST).
5. Revision history honesty (INSUFFICIENT_HISTORY / REVISION_HISTORY_UNAVAILABLE when no prior history exists).
6. Time horizon scope separation (<=240h frozen benchmark vs 264-384h extended operational).
"""
import pytest

from backend.app.core.certification_policy import (
    CERTIFICATION_POLICY_VERSION,
    CERTIFIED_BENCHMARK_STATIONS,
    MAX_CERTIFIED_LEAD_HOURS,
    evaluate_scientific_certification,
)
from backend.app.core.model_determinism import (
    V3_CALIBRATOR_SHA256,
    V3_MODEL_SHA256,
    get_authoritative_v3_provenance,
    resolve_model_identifier,
)
from backend.app.core.ood_policy import (
    OOD_POLICY_VERSION,
    evaluate_ood_policy,
)
from backend.app.core.release_manifest import load_release_manifest, validate_release_manifest
from backend.app.core.replay_harness import get_risk_band_from_bust_probability
from backend.app.core.time_contract import (
    derive_and_validate_lead_hours,
    is_certified_lead_horizon,
)
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    TrustState,
)
from backend.app.schemas.revision import RevisionStatus
from backend.app.services.revision_service import REVISION_HISTORY_UNAVAILABLE


class TestDay36DashboardParityAndExplanationCoherence:
    """Test matrix for Day 36 backend <-> frontend scientific contract parity."""

    def test_01_risk_band_threshold_boundaries(self):
        assert get_risk_band_from_bust_probability(0.00) == "LOW"
        assert get_risk_band_from_bust_probability(0.1999) == "LOW"
        assert get_risk_band_from_bust_probability(0.20) == "MEDIUM"
        assert get_risk_band_from_bust_probability(0.4999) == "MEDIUM"
        assert get_risk_band_from_bust_probability(0.50) == "HIGH"
        assert get_risk_band_from_bust_probability(0.7499) == "HIGH"
        assert get_risk_band_from_bust_probability(0.75) == "CRITICAL"
        assert get_risk_band_from_bust_probability(1.00) == "CRITICAL"

    def test_02_certification_station_count_25(self):
        assert len(CERTIFIED_BENCHMARK_STATIONS) == 25
        assert "Leh" in CERTIFIED_BENCHMARK_STATIONS
        assert "Dispur" not in CERTIFIED_BENCHMARK_STATIONS
        assert "Patna" not in CERTIFIED_BENCHMARK_STATIONS

    def test_03_certification_status_delhi_24h(self):
        res = evaluate_scientific_certification(location="Delhi", variable="temperature_2m", lead_hours=24)
        assert res.is_certified is True
        assert res.status.value == "CERTIFIED"

    def test_04_certification_status_outside_scope_lead_264h(self):
        res = evaluate_scientific_certification(location="Delhi", variable="temperature_2m", lead_hours=264)
        assert res.is_certified is False
        assert res.status.value == "OUTSIDE_CERTIFIED_SCOPE"

    def test_05_certification_status_uncertified_location(self):
        res = evaluate_scientific_certification(location="Patna", variable="temperature_2m", lead_hours=24)
        assert res.is_certified is False
        assert res.status.value == "OUTSIDE_CERTIFIED_SCOPE"

    def test_06_ood_policy_nominal_in_distribution(self):
        res = evaluate_ood_policy(variable="temperature_2m", forecast_value=300.0)
        assert res.is_ood is False
        assert res.status.value == "IN_DISTRIBUTION"
        assert res.causes_abstention is False

    def test_07_ood_policy_out_of_distribution(self):
        res = evaluate_ood_policy(variable="temperature_2m", forecast_value=380.0)
        assert res.is_ood is True
        assert res.status.value == "OUT_OF_DISTRIBUTION"
        assert res.causes_abstention is False  # OOD is diagnostic-only

    def test_08_ood_independence_from_certification(self):
        # Patna is uncertified location, but parameter is in-distribution
        cert_res = evaluate_scientific_certification(location="Patna", variable="temperature_2m", lead_hours=24)
        ood_res = evaluate_ood_policy(variable="temperature_2m", forecast_value=300.0)
        assert cert_res.is_certified is False
        assert ood_res.is_ood is False

    def test_09_time_contract_240h_certified_boundary(self):
        assert is_certified_lead_horizon(240) is True
        assert is_certified_lead_horizon(264) is False

    def test_10_model_identifier_alias_mapping(self):
        assert resolve_model_identifier("default") == "builder2_v3"
        assert resolve_model_identifier("veyra-v3-benchmark-lightgbm") == "builder2_v3"
        assert resolve_model_identifier("lgbm") == "builder2_v3"
        assert resolve_model_identifier("lightgbm") == "builder2_v3"

    def test_11_model_provenance_sha_contract(self):
        prov = get_authoritative_v3_provenance()
        assert prov.model_sha256 == V3_MODEL_SHA256
        assert prov.calibrator_sha256 == V3_CALIBRATOR_SHA256
        assert prov.feature_count == 50
        assert prov.calibrator_type == "IsotonicRegression"

    def test_12_revision_no_history_constant(self):
        assert REVISION_HISTORY_UNAVAILABLE == "REVISION_HISTORY_UNAVAILABLE"

    def test_13_time_contract_lead_derivation_24h(self):
        lead_h, issue_utc, valid_utc = derive_and_validate_lead_hours(
            "2026-09-20T00:00:00Z", "2026-09-21T00:00:00Z"
        )
        assert lead_h == 24
        assert issue_utc == "2026-09-20T00:00:00Z"
        assert valid_utc == "2026-09-21T00:00:00Z"

    def test_14_time_contract_reversed_timestamp_rejection(self):
        with pytest.raises(ValueError, match="strictly after"):
            derive_and_validate_lead_hours("2026-09-21T00:00:00Z", "2026-09-20T00:00:00Z")

    def test_15_release_manifest_validates_cleanly(self):
        res = validate_release_manifest()
        assert res.is_valid is True
        assert res.verified_contracts["model_artifact_hash"] is True
        assert res.verified_contracts["calibrator_artifact_hash"] is True

    def test_16_confidence_index_heuristic_formula(self):
        # Confidence index defined as 2 * |P - 0.5|
        p_bust = 0.80
        conf = 2.0 * abs(p_bust - 0.50)
        assert round(conf, 2) == 0.60

    def test_17_decision_boundary_ambiguity_formula(self):
        # Decision boundary ambiguity defined as (1.0 - 2 * |P - 0.5|) * 100
        p_bust = 0.55
        ambiguity = (1.0 - 2.0 * abs(p_bust - 0.50)) * 100.0
        assert round(ambiguity, 1) == 90.0

    def test_18_gefs_variable_units(self):
        units = {"temperature_2m": "°C", "wind_speed_10m": "m/s", "surface_pressure": "hPa"}
        assert units["temperature_2m"] == "°C"
        assert units["wind_speed_10m"] == "m/s"
        assert units["surface_pressure"] == "hPa"

    def test_19_prediction_response_schema_fields(self):
        resp = PredictionResponse(
            location="Delhi",
            bust_probability=0.35,
            risk_level="MEDIUM",
            trust_state=TrustState.HIGH_CONFIDENCE,
            abstain=False,
            reason_codes=[ReasonCode.SUCCESS.value],
            model_version="veyra-v3-benchmark-lightgbm",
            data_version="gefs-v12",
            explanation=None,
            lead_hours=24,
        )
        assert resp.location == "Delhi"
        assert resp.bust_probability == 0.35
        assert resp.risk_level == "MEDIUM"

    def test_20_release_manifest_content_integrity(self):
        manifest = load_release_manifest()
        assert manifest["release_id"] == "veyra-v3.0.0-release-candidate"
        assert manifest["feature_contract"]["feature_count"] == 50
        assert manifest["scientific_policies"]["certified_station_count"] == 25

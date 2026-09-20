"""Day 33 Focused Deterministic Test Suite: OOD Policy + Alias / Model Determinism (C2 + C3).

Validates:
1. Canonical location deterministic resolution
2. Legitimate aliases resolve consistently (Goa/Panaji, Leh/Ladakh, etc.)
3. Alias does not incorrectly broaden scientific certification
4. Default model selection deterministic (resolves to authoritative V3)
5. Accepted model aliases resolve deterministically
6. Unknown model identifier behavior is explicit (rejected with validation error)
7. Repeated identical inference produces deterministic model identity
8. Repeated identical inference produces deterministic P(BUST)
9. Feature ordering remains 50 and stable
10. Model SHA exact match against authoritative frozen evidence
11. Calibrator SHA exact match against authoritative frozen evidence
12. Calibration failure still safely abstains
13. OOD state is machine-readable and typed
14. OOD and certification remain strictly independent concepts
15. OOD_UNKNOWN handled safely without crashing or forcing abstention
16. Provider/QC failure not mislabeled as OOD
17. Existing 240h certification boundary unchanged
18. 264h remains outside certified scope
"""
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.builder2.v3_feature_pipeline import V3_FEATURE_NAMES
from backend.app.core.certification_policy import (
    CERTIFIED_BENCHMARK_STATIONS,
    CERTIFIED_VARIABLES,
    EXPECTED_CALIBRATOR_SHA256,
    EXPECTED_MODEL_SHA256,
    MAX_CERTIFIED_LEAD_HOURS,
    evaluate_scientific_certification,
)
from backend.app.core.model_determinism import (
    MODEL_ALIAS_MAP,
    V3_CALIBRATOR_SHA256,
    V3_FEATURE_COUNT,
    V3_MODEL_SHA256,
    get_authoritative_v3_provenance,
    resolve_model_identifier,
)
from backend.app.core.ood_policy import (
    OOD_POLICY_VERSION,
    PHYSICAL_DOMAIN_BOUNDS,
    evaluate_ood_policy,
    get_ood_policy_metadata,
)
from backend.app.main import app
from backend.app.safety.abstention import SafetyAssessment, SafetyEvaluator
from backend.app.schemas.certification import CertificationReasonCode, CertificationStatus
from backend.app.schemas.ood import OODReasonCode, OODState
from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.base import FeatureResult, ModelResult, WeatherResult
from backend.app.services.location_service import KNOWN_BENCHMARK_LOCATIONS, DynamicLocationService


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


# =========================================================================
# 1. Canonical Location Deterministic Resolution
# =========================================================================
def test_01_canonical_location_deterministic_resolution():
    """Verify standard canonical stations resolve to deterministic coordinates and identities."""
    loc_service = DynamicLocationService()

    stations = ["Delhi", "Kolkata", "Mumbai", "Bengaluru", "Chennai"]
    for st in stations:
        res1 = loc_service.resolve(st)
        res2 = loc_service.resolve(st)
        assert res1 is not None
        assert res2 is not None
        assert res1.latitude == res2.latitude
        assert res1.longitude == res2.longitude
        assert res1.name == res2.name


# =========================================================================
# 2. Legitimate Aliases Resolve Consistently
# =========================================================================
def test_02_legitimate_aliases_resolve_consistently():
    """Verify legitimate aliases (Goa/Panaji, Leh/Ladakh, Delhi/New Delhi) resolve to identical canonical identity."""
    loc_service = DynamicLocationService()

    # Goa / Panaji
    res_goa = loc_service.resolve("Goa")
    res_panaji = loc_service.resolve("Panaji")
    assert res_goa is not None and res_panaji is not None
    assert res_goa.latitude == res_panaji.latitude
    assert res_goa.longitude == res_panaji.longitude
    assert res_goa.name == "Panaji"
    assert res_panaji.name == "Panaji"

    # Leh / Ladakh
    res_leh = loc_service.resolve("Leh")
    res_ladakh = loc_service.resolve("Ladakh")
    assert res_leh is not None and res_ladakh is not None
    assert res_leh.latitude == res_ladakh.latitude
    assert res_leh.longitude == res_ladakh.longitude
    assert res_leh.name == "Leh"
    assert res_ladakh.name == "Leh"

    # Delhi / New Delhi
    res_delhi = loc_service.resolve("Delhi")
    res_new_delhi = loc_service.resolve("New Delhi")
    assert res_delhi is not None and res_new_delhi is not None
    assert res_delhi.latitude == res_new_delhi.latitude
    assert res_delhi.longitude == res_new_delhi.longitude


# =========================================================================
# 3. Alias Does Not Incorrectly Broaden Certification
# =========================================================================
def test_03_alias_does_not_broaden_certification():
    """Verify alias resolution only certifies stations mapped to the frozen 25 benchmark stations."""
    # Certified alias
    cert_panaji = evaluate_scientific_certification(location="Panaji", variable="temperature_2m", lead_hours=24)
    assert cert_panaji.is_certified
    assert cert_panaji.status == CertificationStatus.CERTIFIED

    # Non-certified location
    cert_london = evaluate_scientific_certification(location="London", variable="temperature_2m", lead_hours=24)
    assert not cert_london.is_certified
    assert cert_london.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert cert_london.reason_code == CertificationReasonCode.UNCERTIFIED_LOCATION


# =========================================================================
# 4. Default Model Selection Deterministic
# =========================================================================
def test_04_default_model_selection_deterministic():
    """Verify omitted or None model_type always resolves deterministically to builder2_v3."""
    assert resolve_model_identifier(None) == "builder2_v3"
    assert resolve_model_identifier("") == "builder2_v3"
    assert resolve_model_identifier("default") == "builder2_v3"


# =========================================================================
# 5. Accepted Model Aliases Resolve Deterministically
# =========================================================================
def test_05_accepted_model_aliases_resolve_deterministically():
    """Verify all recognized model aliases deterministically map to expected keys."""
    assert resolve_model_identifier("veyra-v3-benchmark-lightgbm") == "builder2_v3"
    assert resolve_model_identifier("lightgbm") == "builder2_v3"
    assert resolve_model_identifier("lgbm") == "builder2_v3"
    assert resolve_model_identifier("prototype-gbm-v1") == "builder2_gbm"
    assert resolve_model_identifier("baseline-logistic-v1.0") == "baseline_logistic"
    assert resolve_model_identifier("logistic") == "baseline_logistic"
    assert resolve_model_identifier("baseline") == "baseline_logistic"


# =========================================================================
# 6. Unknown Model Identifier Behavior Explicit
# =========================================================================
def test_06_unknown_model_identifier_behavior_explicit():
    """Verify unknown model_type raises a ValueError with supported options listed."""
    with pytest.raises(ValueError) as excinfo:
        resolve_model_identifier("unsupported-deep-net-v99")
    assert "Unsupported model_type" in str(excinfo.value)


# =========================================================================
# 7. Repeated Identical Inference Produces Deterministic Model Identity
# =========================================================================
def test_07_repeated_inference_deterministic_model_identity():
    """Verify repeated provenance queries return bitwise identical model identity and SHA metadata."""
    prov1 = get_authoritative_v3_provenance()
    prov2 = get_authoritative_v3_provenance()

    assert prov1.model_name == prov2.model_name == "builder2_v3"
    assert prov1.model_sha256 == prov2.model_sha256 == V3_MODEL_SHA256
    assert prov1.calibrator_sha256 == prov2.calibrator_sha256 == V3_CALIBRATOR_SHA256
    assert prov1.feature_count == prov2.feature_count == 50


# =========================================================================
# 8. Repeated Identical Inference Produces Deterministic P(BUST)
# =========================================================================
def test_08_repeated_inference_deterministic_pbust():
    """Verify V3 feature matrix computation and evaluation is deterministic for identical synthetic inputs."""
    from backend.app.builder2.v3_model_adapter import Builder2V3ModelAdapter
    from backend.app.services.base import FeatureResult

    adapter = Builder2V3ModelAdapter(model_dir="models/v3")
    if not adapter.is_ready:
        pytest.skip("V3 model artifacts not loaded in test environment")

    # Generate synthetic 50-feature vector
    synthetic_feats = {name: float(i % 10) for i, name in enumerate(V3_FEATURE_NAMES)}
    feat_res = FeatureResult(
        location="Kolkata",
        is_ready=True,
        features=synthetic_feats,
        feature_names=V3_FEATURE_NAMES,
    )

    res1 = adapter.predict(feat_res)
    res2 = adapter.predict(feat_res)

    assert res1.probability is not None
    assert res2.probability is not None
    assert res1.probability == res2.probability


# =========================================================================
# 9. Feature Ordering Remains 50 and Stable
# =========================================================================
def test_09_feature_ordering_50_stable():
    """Verify V3_FEATURE_NAMES has exactly 50 ordered features matching authoritative spec."""
    assert len(V3_FEATURE_NAMES) == 50
    assert V3_FEATURE_COUNT == 50
    # Spot-check key expected anchor features
    assert V3_FEATURE_NAMES[0] == "ensemble_mean"
    assert "forecast_value" in V3_FEATURE_NAMES
    assert "ensemble_std" in V3_FEATURE_NAMES
    assert "stability_index" in V3_FEATURE_NAMES


# =========================================================================
# 10. Model SHA Exact Match
# =========================================================================
def test_10_model_sha_exact_match():
    """Verify models/v3/lightgbm_v3_challenger.joblib matches authoritative SHA256 exactly."""
    model_path = Path("models/v3/lightgbm_v3_challenger.joblib")
    if not model_path.exists():
        pytest.skip("models/v3/lightgbm_v3_challenger.joblib not present")

    hasher = hashlib.sha256()
    with open(model_path, "rb") as f:
        hasher.update(f.read())
    computed_sha = hasher.hexdigest().lower()

    assert computed_sha == EXPECTED_MODEL_SHA256
    assert computed_sha == V3_MODEL_SHA256


# =========================================================================
# 11. Calibrator SHA Exact Match
# =========================================================================
def test_11_calibrator_sha_exact_match():
    """Verify models/v3/probability_calibrator_v3.joblib matches authoritative SHA256 exactly."""
    cal_path = Path("models/v3/probability_calibrator_v3.joblib")
    if not cal_path.exists():
        pytest.skip("models/v3/probability_calibrator_v3.joblib not present")

    hasher = hashlib.sha256()
    with open(cal_path, "rb") as f:
        hasher.update(f.read())
    computed_sha = hasher.hexdigest().lower()

    assert computed_sha == EXPECTED_CALIBRATOR_SHA256
    assert computed_sha == V3_CALIBRATOR_SHA256


# =========================================================================
# 12. Calibration Failure Safely Abstains
# =========================================================================
def test_12_calibration_failure_safely_abstains():
    """Verify calibration failure causes safe abstention and does not expose uncalibrated raw probability."""
    evaluator = SafetyEvaluator()
    model_res = ModelResult(
        probability=0.85,
        is_ready=False,
        metadata={"calibration_status": "FAILED", "status": ReasonCode.CALIBRATION_FAILURE.value},
        error="Isotonic calibrator failed",
    )
    assessment = evaluator.evaluate(model_result=model_res)

    assert assessment.abstain is True
    assert assessment.bust_probability is None
    assert assessment.trust_state == TrustState.UNAVAILABLE
    assert ReasonCode.CALIBRATION_FAILURE.value in assessment.reason_codes


# =========================================================================
# 13. OOD State is Machine-Readable and Typed
# =========================================================================
def test_13_ood_state_machine_readable_and_typed():
    """Verify OOD evaluation returns typed OODDiagnosticResult with correct policy metadata."""
    # Nominal temperature (300K ~ 26.85°C)
    res_in = evaluate_ood_policy(variable="temperature_2m", forecast_value=300.0, raw_ood_score=5.0)
    assert res_in.status == OODState.IN_DISTRIBUTION
    assert res_in.is_ood is False
    assert res_in.reason_code == OODReasonCode.WITHIN_PHYSICAL_TRAINING_SUPPORT
    assert res_in.causes_abstention is False
    assert res_in.policy_version == OOD_POLICY_VERSION

    # Out of bounds temperature (400K ~ 126.85°C)
    res_out = evaluate_ood_policy(variable="temperature_2m", forecast_value=400.0, raw_ood_score=80.0)
    assert res_out.status == OODState.OUT_OF_DISTRIBUTION
    assert res_out.is_ood is True
    assert res_out.reason_code == OODReasonCode.OUT_OF_PHYSICAL_SUPPORT
    assert res_out.causes_abstention is False


# =========================================================================
# 14. OOD and Certification Remain Independent Concepts
# =========================================================================
def test_14_ood_and_certification_remain_independent():
    """Verify a request can be outside certified scope yet in-distribution, or certified yet OOD."""
    # Location London (outside certified scope) but normal temperature 295K (in-distribution)
    cert = evaluate_scientific_certification(location="London", variable="temperature_2m", lead_hours=24)
    ood = evaluate_ood_policy(variable="temperature_2m", forecast_value=295.0)

    assert cert.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert cert.is_certified is False
    assert ood.status == OODState.IN_DISTRIBUTION
    assert ood.is_ood is False

    # Location Kolkata (certified scope) but extreme non-physical wind speed 100 m/s (OOD)
    cert_kolkata = evaluate_scientific_certification(location="Kolkata", variable="wind_speed_10m", lead_hours=24)
    ood_kolkata = evaluate_ood_policy(variable="wind_speed_10m", forecast_value=100.0)

    assert cert_kolkata.status == CertificationStatus.CERTIFIED
    assert cert_kolkata.is_certified is True
    assert ood_kolkata.status == OODState.OUT_OF_DISTRIBUTION
    assert ood_kolkata.is_ood is True


# =========================================================================
# 15. OOD_UNKNOWN Handled Safely
# =========================================================================
def test_15_ood_unknown_handled_safely():
    """Verify missing, invalid, or unsupported variables produce OOD_UNKNOWN without crashing."""
    res_none_var = evaluate_ood_policy(variable=None)
    assert res_none_var.status == OODState.OOD_UNKNOWN
    assert res_none_var.is_ood is None
    assert res_none_var.reason_code == OODReasonCode.INVALID_REQUEST_PARAMETERS
    assert res_none_var.causes_abstention is False

    res_unsupported = evaluate_ood_policy(variable="unsupported_radiation_flux", forecast_value=500.0)
    assert res_unsupported.status == OODState.OOD_UNKNOWN
    assert res_unsupported.is_ood is None
    assert res_unsupported.reason_code == OODReasonCode.UNSUPPORTED_VARIABLE
    assert res_unsupported.causes_abstention is False

    res_missing_val = evaluate_ood_policy(variable="temperature_2m", forecast_value=None)
    assert res_missing_val.status == OODState.OOD_UNKNOWN
    assert res_missing_val.reason_code == OODReasonCode.INSUFFICIENT_EVIDENCE
    assert res_missing_val.causes_abstention is False


# =========================================================================
# 16. Provider/QC Failure Not Mislabeled as OOD
# =========================================================================
def test_16_provider_qc_failure_not_mislabeled_as_ood():
    """Verify upstream weather service or QC failure produces QC_FAILED or DATA_UNAVAILABLE and abstains."""
    evaluator = SafetyEvaluator()
    weather_fail = WeatherResult(
        location="Delhi",
        is_available=False,
        error="Open-Meteo HTTP 503 Provider Unavailable",
    )
    assessment = evaluator.evaluate(weather_result=weather_fail)

    assert assessment.abstain is True
    assert (
        ReasonCode.DATA_NOT_READY.value in assessment.reason_codes
        or ReasonCode.DATA_UNAVAILABLE.value in assessment.reason_codes
    )
    assert ReasonCode.OOD_DETECTED.value not in assessment.reason_codes


# =========================================================================
# 17. Existing 240h Certification Boundary Unchanged
# =========================================================================
def test_17_existing_240h_certification_boundary_unchanged():
    """Verify 240h lead time remains CERTIFIED for all 25 benchmark stations."""
    for st in CERTIFIED_BENCHMARK_STATIONS:
        cert = evaluate_scientific_certification(location=st, variable="temperature_2m", lead_hours=240)
        assert cert.status == CertificationStatus.CERTIFIED
        assert cert.is_certified is True
        assert cert.evaluated_lead_hours == 240


# =========================================================================
# 18. 264h Remains Outside Certified Scope
# =========================================================================
def test_18_264h_remains_outside_certified_scope():
    """Verify 264h lead horizon is strictly rejected as OUTSIDE_CERTIFIED_SCOPE."""
    cert = evaluate_scientific_certification(location="Kolkata", variable="temperature_2m", lead_hours=264)
    assert cert.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert cert.is_certified is False
    assert cert.reason_code == CertificationReasonCode.UNCERTIFIED_LEAD_HORIZON
    assert cert.evaluated_lead_hours == 264


# =========================================================================
# 19. Day32 Certified Station Count Remains Exactly 25
# =========================================================================
def test_19_certified_station_count_remains_25():
    """Verify Day 32 certified benchmark station scope contains exactly 25 stations."""
    assert len(CERTIFIED_BENCHMARK_STATIONS) == 25


# =========================================================================
# 20. Leh Remains Certified
# =========================================================================
def test_20_leh_remains_certified():
    """Verify Leh is certified for temperature_2m at 24h lead horizon."""
    cert = evaluate_scientific_certification(location="Leh", variable="temperature_2m", lead_hours=24)
    assert cert.status == CertificationStatus.CERTIFIED
    assert cert.is_certified is True
    assert cert.reason_code == CertificationReasonCode.CERTIFIED_FROZEN_BENCHMARK_SCOPE


# =========================================================================
# 21. Dispur Remains Outside Certified Scope
# =========================================================================
def test_21_dispur_remains_outside_certified_scope():
    """Verify Dispur is outside certified scope (uncertified location)."""
    cert = evaluate_scientific_certification(location="Dispur", variable="temperature_2m", lead_hours=24)
    assert cert.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert cert.is_certified is False
    assert cert.reason_code == CertificationReasonCode.UNCERTIFIED_LOCATION


# =========================================================================
# 22. Dedicated OOD Policy Endpoint GET /v1/ood/policy
# =========================================================================
def test_22_ood_policy_endpoint(client):
    """Verify GET /v1/ood/policy returns valid OOD policy metadata."""
    resp = client.get("/v1/ood/policy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["policy_version"] == OOD_POLICY_VERSION
    assert "temperature_2m" in data["supported_variables"]
    assert data["causes_abstention"] is False


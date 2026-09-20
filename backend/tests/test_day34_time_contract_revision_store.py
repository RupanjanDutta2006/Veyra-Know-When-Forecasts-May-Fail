"""Day 34 Focused Test Suite: Time Contract + Durable Revision Store Foundation (Gate C4 Part 1).

Validates:
1. issue_time / valid_time lead derivation
2. Reversed timestamps rejected safely
3. Zero / non-positive lead rejected safely
4. Timezone-aware timestamp equivalence (UTC offset normalization)
5. Malformed timestamps fail safely
6. Primary PredictionRequest contract preserved
7. <=240h certification boundary preserved
8. 264h remains outside frozen certification (extended operational)
9. Idempotency: same issue cycle inserted twice produces exactly one revision
10. Distinct issue cycles create distinct revisions
11. Persistence: history survives store/service recreation
12. Chronological ordering: previous revision selected strictly by issue_time
13. Delta convention: CURRENT - PREVIOUS
14. No comparable history returns honest INSUFFICIENT_HISTORY
15. Repeated API calls alone do not manufacture revision history
16. Alias canonicalization does not split revision identity
17. Model identity & provenance deterministic in stored records
18. Unavailable store fails safely
19. Corrupted store fails safely
20. Calibration failure remains safe
21. Day 33 OOD semantics intact
22. Day 33 alias determinism intact
23. Day 33 model determinism intact
24. Day 32 certified station count remains exactly 25
25. Leh remains certified
26. Dispur remains outside certified scope
"""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.core.certification_policy import (
    CERTIFIED_BENCHMARK_STATIONS,
    evaluate_scientific_certification,
)
from backend.app.core.model_determinism import (
    V3_CALIBRATOR_SHA256,
    V3_FEATURE_COUNT,
    V3_MODEL_SHA256,
    get_authoritative_v3_provenance,
    resolve_model_identifier,
)
from backend.app.core.ood_policy import (
    OOD_POLICY_VERSION,
    evaluate_ood_policy,
)
from backend.app.core.revision_store import (
    RevisionRecord,
    RevisionStore,
)
from backend.app.core.time_contract import (
    MAX_CERTIFIED_LEAD_HOURS,
    MAX_SUPPORTED_LEAD_HOURS,
    derive_and_validate_lead_hours,
    format_utc_timestamp,
    is_certified_lead_horizon,
    parse_utc_timestamp,
)
from backend.app.main import app
from backend.app.schemas.certification import CertificationReasonCode, CertificationStatus
from backend.app.schemas.ood import OODReasonCode, OODState
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.schemas.revision import (
    ForecastRevisionRequest,
    RevisionDirection,
    RevisionStatus,
)
from backend.app.services.location_service import DynamicLocationService
from backend.app.services.revision_service import (
    REVISION_HISTORY_UNAVAILABLE,
    RevisionService,
    calculate_trajectory_diagnostics,
    get_revision_service,
)


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide an isolated temporary database path for each test."""
    db_file = tmp_path / "test_revisions.db"
    return str(db_file)


@pytest.fixture
def isolated_store(temp_db_path):
    """Provide a clean, isolated RevisionStore instance."""
    return RevisionStore(db_path=temp_db_path)


# =========================================================================
# 1. Valid issue_time / valid_time Lead Derivation
# =========================================================================
def test_01_valid_lead_derivation():
    """Verify lead_hours = valid_time - issue_time with exact integer hour derivation."""
    lead, issue_iso, valid_iso = derive_and_validate_lead_hours(
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
    )
    assert lead == 24
    assert issue_iso == "2026-09-20T00:00:00Z"
    assert valid_iso == "2026-09-21T00:00:00Z"

    lead_48, _, _ = derive_and_validate_lead_hours(
        issue_time="2026-09-20T06:00:00Z",
        valid_time="2026-09-22T06:00:00Z",
    )
    assert lead_48 == 48


# =========================================================================
# 2. Reversed Timestamps Rejected Safely
# =========================================================================
def test_02_reversed_timestamps_rejected():
    """Verify valid_time before or equal to issue_time raises ValueError."""
    with pytest.raises(ValueError) as excinfo:
        derive_and_validate_lead_hours(
            issue_time="2026-09-21T00:00:00Z",
            valid_time="2026-09-20T00:00:00Z",
        )
    assert "must be strictly after issue_time" in str(excinfo.value)

    # Identical timestamps (zero lead)
    with pytest.raises(ValueError) as excinfo_zero:
        derive_and_validate_lead_hours(
            issue_time="2026-09-20T00:00:00Z",
            valid_time="2026-09-20T00:00:00Z",
        )
    assert "must be strictly after issue_time" in str(excinfo_zero.value)


# =========================================================================
# 3. Invalid Lead Bounds and Fractional Hours Rejected
# =========================================================================
def test_03_invalid_lead_bounds_and_fractions():
    """Verify out-of-horizon and non-whole-hour timestamps are rejected."""
    # Exceeding 384h
    with pytest.raises(ValueError) as exc_max:
        derive_and_validate_lead_hours(
            issue_time="2026-09-01T00:00:00Z",
            valid_time="2026-09-20T00:00:00Z",  # 456h > 384h
        )
    assert "exceeds the maximum supported horizon" in str(exc_max.value)

    # Non-whole hour (30 minutes)
    with pytest.raises(ValueError) as exc_frac:
        derive_and_validate_lead_hours(
            issue_time="2026-09-20T00:00:00Z",
            valid_time="2026-09-20T01:30:00Z",
        )
    assert "whole-hour lead horizon" in str(exc_frac.value)


# =========================================================================
# 4. Equivalent Timezone-Aware Timestamps Behave Consistently
# =========================================================================
def test_04_timezone_aware_timestamp_equivalence():
    """Verify +05:30 and Z offsets are correctly normalized to UTC and yield identical lead."""
    # 2026-09-20T05:30:00+05:30 is 2026-09-20T00:00:00Z
    lead1, issue1, valid1 = derive_and_validate_lead_hours(
        issue_time="2026-09-20T05:30:00+05:30",
        valid_time="2026-09-21T05:30:00+05:30",
    )
    lead2, issue2, valid2 = derive_and_validate_lead_hours(
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
    )
    assert lead1 == lead2 == 24
    assert issue1 == issue2 == "2026-09-20T00:00:00Z"
    assert valid1 == valid2 == "2026-09-21T00:00:00Z"


# =========================================================================
# 5. Malformed Timestamps Fail Safely
# =========================================================================
def test_05_malformed_timestamps_fail_safely():
    """Verify malformed strings raise clear ValueErrors."""
    with pytest.raises(ValueError) as exc:
        parse_utc_timestamp("not-a-timestamp", "issue_time")
    assert "Invalid issue_time" in str(exc.value)

    with pytest.raises(ValueError):
        parse_utc_timestamp("", "valid_time")


# =========================================================================
# 6. Primary PredictionRequest Contract Preserved
# =========================================================================
def test_06_prediction_request_contract_preserved():
    """Verify PredictionRequest does not require client-supplied lead_hours."""
    req = PredictionRequest(
        location="Kolkata",
        variable="temperature_2m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
    )
    assert req.location == "Kolkata"
    assert req.variable == "temperature_2m"
    assert req.issue_time == "2026-09-20T00:00:00Z"
    assert req.valid_time == "2026-09-21T00:00:00Z"


# =========================================================================
# 7. <= 240h Certification Boundary Preserved
# =========================================================================
def test_07_certification_boundary_preserved():
    """Verify <= 240h is recognized as certified lead horizon."""
    assert is_certified_lead_horizon(24) is True
    assert is_certified_lead_horizon(240) is True
    assert is_certified_lead_horizon(264) is False
    assert is_certified_lead_horizon(384) is False


# =========================================================================
# 8. 264h Remains Outside Frozen Certification Scope
# =========================================================================
def test_08_264h_remains_outside_certified_scope():
    """Verify 264h lead returns OUTSIDE_CERTIFIED_SCOPE."""
    cert = evaluate_scientific_certification(location="Kolkata", variable="temperature_2m", lead_hours=264)
    assert cert.is_certified is False
    assert cert.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert cert.reason_code == CertificationReasonCode.UNCERTIFIED_LEAD_HORIZON


# =========================================================================
# 9. Idempotency: Same Issue Cycle Inserted Twice Produces Exactly One Record
# =========================================================================
def test_09_revision_store_idempotency(isolated_store):
    """Verify inserting identical issue cycle twice results in one stored record."""
    record = RevisionRecord(
        canonical_location="Kolkata",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        issue_time="2026-09-20T00:00:00Z",
        lead_hours=48,
        forecast_value=28.5,
        ensemble_mean=28.4,
        ensemble_spread=1.2,
        bust_probability=0.15,
        model_version="veyra-v3-benchmark-lightgbm",
        model_sha256=V3_MODEL_SHA256,
        provider_source="noaa_gefs_v12",
    )
    assert isolated_store.record_revision(record) is True
    assert isolated_store.get_revision_count() == 1

    # Insert again (identical identity)
    assert isolated_store.record_revision(record) is True
    assert isolated_store.get_revision_count() == 1


# =========================================================================
# 10. Distinct Issue Cycles Create Distinct Revisions
# =========================================================================
def test_10_distinct_issue_cycles_create_distinct_revisions(isolated_store):
    """Verify successive issue cycles for the same target create distinct revisions."""
    # Issue cycle 1 (48h lead)
    rec1 = RevisionRecord(
        canonical_location="Kolkata",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        issue_time="2026-09-20T00:00:00Z",
        lead_hours=48,
        forecast_value=28.0,
        bust_probability=0.18,
    )
    # Issue cycle 2 (24h lead)
    rec2 = RevisionRecord(
        canonical_location="Kolkata",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        issue_time="2026-09-21T00:00:00Z",
        lead_hours=24,
        forecast_value=29.2,
        bust_probability=0.12,
    )
    isolated_store.record_revision(rec1)
    isolated_store.record_revision(rec2)

    assert isolated_store.get_revision_count() == 2


# =========================================================================
# 11. Persistence Across Store Recreation
# =========================================================================
def test_11_persistence_across_store_recreation(temp_db_path):
    """Verify stored history persists across new RevisionStore instances pointing to same file."""
    store1 = RevisionStore(db_path=temp_db_path)
    rec = RevisionRecord(
        canonical_location="Delhi",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        issue_time="2026-09-20T00:00:00Z",
        lead_hours=48,
        forecast_value=32.0,
        bust_probability=0.22,
    )
    store1.record_revision(rec)

    # Recreate store instance pointing to same file
    store2 = RevisionStore(db_path=temp_db_path)
    assert store2.get_revision_count() == 1
    prev = store2.get_previous_revision(
        canonical_location="Delhi",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        current_issue_time="2026-09-21T00:00:00Z",
    )
    assert prev is not None
    assert prev.forecast_value == 32.0


# =========================================================================
# 12. Chronological Ordering: Previous Selected by issue_time Chronology
# =========================================================================
def test_12_previous_selected_by_issue_chronology(isolated_store):
    """Verify previous revision is selected strictly by issue_time DESC (not insertion order)."""
    # Insert in reverse chronological order
    rec_later = RevisionRecord(
        canonical_location="Mumbai",
        variable="temperature_2m",
        valid_time="2026-09-23T00:00:00Z",
        issue_time="2026-09-21T00:00:00Z",
        lead_hours=48,
        forecast_value=30.5,
    )
    rec_earlier = RevisionRecord(
        canonical_location="Mumbai",
        variable="temperature_2m",
        valid_time="2026-09-23T00:00:00Z",
        issue_time="2026-09-20T00:00:00Z",
        lead_hours=72,
        forecast_value=29.0,
    )
    # Insert later record first
    isolated_store.record_revision(rec_later)
    isolated_store.record_revision(rec_earlier)

    # Query for current issue cycle at 2026-09-22T00:00:00Z -> immediately preceding must be rec_later
    prev = isolated_store.get_previous_revision(
        canonical_location="Mumbai",
        variable="temperature_2m",
        valid_time="2026-09-23T00:00:00Z",
        current_issue_time="2026-09-22T00:00:00Z",
    )
    assert prev is not None
    assert prev.issue_time == "2026-09-21T00:00:00Z"
    assert prev.forecast_value == 30.5


# =========================================================================
# 13. Delta Convention: CURRENT minus PREVIOUS
# =========================================================================
def test_13_delta_convention_current_minus_previous():
    """Verify trajectory delta follows CURRENT - PREVIOUS mathematical convention."""
    diag_inc = calculate_trajectory_diagnostics(current_value=30.0, previous_value=28.0)
    assert diag_inc.revision_delta == 2.0
    assert diag_inc.absolute_revision == 2.0
    assert diag_inc.direction == RevisionDirection.INCREASED

    diag_dec = calculate_trajectory_diagnostics(current_value=25.0, previous_value=28.0)
    assert diag_dec.revision_delta == -3.0
    assert diag_dec.absolute_revision == 3.0
    assert diag_dec.direction == RevisionDirection.DECREASED


# =========================================================================
# 14. No Comparable History Returns Honest INSUFFICIENT_HISTORY
# =========================================================================
def test_14_no_history_returns_insufficient_history(isolated_store):
    """Verify revision service returns INSUFFICIENT_HISTORY when store has no prior comparable run."""
    mock_agent = MagicMock()
    mock_agent.analyze.return_value = PredictionResponse(
        location="Kolkata",
        variable="temperature_2m",
        bust_probability=0.10,
        risk_level=RiskLevel.LOW,
        trust_state=TrustState.HIGH_CONFIDENCE,
        calibration_status=CalibrationStatus.CALIBRATED.value,
        abstain=False,
    )
    service = RevisionService(
        location_service=DynamicLocationService(),
        agent=mock_agent,
        revision_store=isolated_store,
    )
    req = ForecastRevisionRequest(
        location="Kolkata",
        variable="temperature_2m",
        lead_hours=24,
    )
    resp = service.evaluate_revision(req)
    assert resp.status == RevisionStatus.INSUFFICIENT_HISTORY
    assert REVISION_HISTORY_UNAVAILABLE in resp.reason_codes
    assert resp.previous_value is None
    assert resp.revision_delta is None
    assert resp.trajectory is None


# =========================================================================
# 15. Repeated API Calls Alone Do Not Manufacture History
# =========================================================================
def test_15_repeated_api_calls_do_not_manufacture_history(isolated_store):
    """Verify two consecutive evaluation requests without real historical records preserve INSUFFICIENT_HISTORY."""
    mock_agent = MagicMock()
    mock_agent.analyze.return_value = PredictionResponse(
        location="Kolkata",
        variable="temperature_2m",
        bust_probability=0.10,
        risk_level=RiskLevel.LOW,
        trust_state=TrustState.HIGH_CONFIDENCE,
        calibration_status=CalibrationStatus.CALIBRATED.value,
        abstain=False,
    )
    service = RevisionService(
        location_service=DynamicLocationService(),
        agent=mock_agent,
        revision_store=isolated_store,
    )
    req = ForecastRevisionRequest(
        location="Kolkata",
        variable="temperature_2m",
        issue_time="2026-09-20T00:00:00Z",
        valid_time="2026-09-21T00:00:00Z",
    )
    resp1 = service.evaluate_revision(req)
    resp2 = service.evaluate_revision(req)

    assert resp1.status == RevisionStatus.INSUFFICIENT_HISTORY
    assert resp2.status == RevisionStatus.INSUFFICIENT_HISTORY
    assert resp1.trajectory is None
    assert resp2.trajectory is None


# =========================================================================
# 16. Alias Canonicalization Does Not Split Revision Identity
# =========================================================================
def test_16_alias_canonicalization_unifies_history(isolated_store):
    """Verify querying 'Goa' matches prior history recorded under canonical 'Panaji'."""
    # Store record under canonical 'Panaji'
    rec = RevisionRecord(
        canonical_location="Panaji",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        issue_time="2026-09-20T00:00:00Z",
        lead_hours=48,
        forecast_value=29.0,
        bust_probability=0.15,
    )
    isolated_store.record_revision(rec)

    mock_agent = MagicMock()
    mock_agent.analyze.return_value = PredictionResponse(
        location="Panaji",
        variable="temperature_2m",
        bust_probability=0.12,
        risk_level=RiskLevel.LOW,
        trust_state=TrustState.HIGH_CONFIDENCE,
        calibration_status=CalibrationStatus.CALIBRATED.value,
        abstain=False,
        failure_fingerprint={"forecast_value": 30.0},
    )
    service = RevisionService(
        location_service=DynamicLocationService(),
        agent=mock_agent,
        revision_store=isolated_store,
    )

    # Request using alias 'Goa'
    req = ForecastRevisionRequest(
        location="Goa",
        variable="temperature_2m",
        issue_time="2026-09-21T00:00:00Z",
        valid_time="2026-09-22T00:00:00Z",
    )
    resp = service.evaluate_revision(req)

    assert resp.status == RevisionStatus.AVAILABLE
    assert resp.history_is_durable is True
    assert resp.previous_value == 29.0
    assert resp.current_value == 30.0
    assert resp.revision_delta == 1.0


# =========================================================================
# 17. Model Identity and Provenance Deterministic in Stored Records
# =========================================================================
def test_17_model_provenance_deterministic_in_store(isolated_store):
    """Verify stored records maintain exact authoritative V3 SHA256 and model version."""
    rec = RevisionRecord(
        canonical_location="Delhi",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        issue_time="2026-09-20T00:00:00Z",
        lead_hours=48,
        forecast_value=32.0,
        model_version="veyra-v3-benchmark-lightgbm",
        model_sha256=V3_MODEL_SHA256,
    )
    isolated_store.record_revision(rec)
    prev = isolated_store.get_previous_revision("Delhi", "temperature_2m", "2026-09-22T00:00:00Z", "2026-09-21T00:00:00Z")
    assert prev is not None
    assert prev.model_sha256 == V3_MODEL_SHA256
    assert prev.model_version == "veyra-v3-benchmark-lightgbm"


# =========================================================================
# 18. Unavailable / Unwritable Store Fails Safely
# =========================================================================
def test_18_unavailable_store_fails_safely():
    """Verify broken store path does not crash RevisionStore operations."""
    broken_store = RevisionStore(db_path="/non_existent_drive_xyz:/invalid/store.db")
    rec = RevisionRecord(
        canonical_location="Delhi",
        variable="temperature_2m",
        valid_time="2026-09-22T00:00:00Z",
        issue_time="2026-09-20T00:00:00Z",
        lead_hours=48,
        forecast_value=32.0,
    )
    assert broken_store.record_revision(rec) is False
    assert broken_store.get_previous_revision("Delhi", "temperature_2m", "2026-09-22T00:00:00Z", "2026-09-21T00:00:00Z") is None
    assert broken_store.get_revision_count() == 0


# =========================================================================
# 19. Corrupted Store Fails Safely
# =========================================================================
def test_19_corrupted_store_fails_safely(tmp_path):
    """Verify corrupt database file fails safely without raising unhandled errors."""
    corrupt_file = tmp_path / "corrupt.db"
    corrupt_file.write_text("NOT A VALID SQLITE DATABASE HEADER DATA")

    corrupt_store = RevisionStore(db_path=str(corrupt_file))
    assert corrupt_store.get_previous_revision("Delhi", "temperature_2m", "2026-09-22T00:00:00Z", "2026-09-21T00:00:00Z") is None
    assert corrupt_store.get_revision_count() == 0


# =========================================================================
# 20. Calibration Failure Remains Safe
# =========================================================================
def test_20_calibration_failure_remains_safe(isolated_store):
    """Verify calibration failure causes abstention and does not persist invalid probability."""
    mock_agent = MagicMock()
    mock_agent.analyze.return_value = PredictionResponse(
        location="Delhi",
        variable="temperature_2m",
        bust_probability=None,
        risk_level=None,
        trust_state=TrustState.UNAVAILABLE,
        calibration_status=CalibrationStatus.FAILED.value,
        abstain=True,
        reason_codes=[ReasonCode.CALIBRATION_FAILURE],
    )
    service = RevisionService(
        location_service=DynamicLocationService(),
        agent=mock_agent,
        revision_store=isolated_store,
    )
    req = ForecastRevisionRequest(location="Delhi", variable="temperature_2m", lead_hours=24)
    resp = service.evaluate_revision(req)

    assert resp.status == RevisionStatus.ABSTAINED
    assert resp.bust_probability is None
    assert resp.abstain is True
    assert ReasonCode.CALIBRATION_FAILURE.value in resp.reason_codes


# =========================================================================
# 21. Day 33 OOD Semantics Intact
# =========================================================================
def test_21_day33_ood_semantics_intact():
    """Verify Day 33 OOD diagnostic evaluations behave as expected."""
    ood_in = evaluate_ood_policy(variable="temperature_2m", forecast_value=300.0)
    assert ood_in.status == OODState.IN_DISTRIBUTION
    assert ood_in.causes_abstention is False

    ood_out = evaluate_ood_policy(variable="temperature_2m", forecast_value=400.0)
    assert ood_out.status == OODState.OUT_OF_DISTRIBUTION
    assert ood_out.causes_abstention is False


# =========================================================================
# 22. Day 33 Alias Determinism Intact
# =========================================================================
def test_22_day33_alias_determinism_intact():
    """Verify Day 33 location alias resolution remains consistent."""
    loc_service = DynamicLocationService()
    res_goa = loc_service.resolve("Goa")
    res_panaji = loc_service.resolve("Panaji")
    assert res_goa is not None and res_panaji is not None
    assert res_goa.name == "Panaji"
    assert res_panaji.name == "Panaji"


# =========================================================================
# 23. Day 33 Model Determinism Intact
# =========================================================================
def test_23_day33_model_determinism_intact():
    """Verify model alias resolution maps deterministically to builder2_v3."""
    assert resolve_model_identifier(None) == "builder2_v3"
    assert resolve_model_identifier("default") == "builder2_v3"
    assert resolve_model_identifier("veyra-v3-benchmark-lightgbm") == "builder2_v3"


# =========================================================================
# 24. Day 32 Certified Station Count Remains Exactly 25
# =========================================================================
def test_24_day32_station_count_remains_25():
    """Verify exactly 25 stations in certified benchmark scope."""
    assert len(CERTIFIED_BENCHMARK_STATIONS) == 25


# =========================================================================
# 25. Leh Remains Certified
# =========================================================================
def test_25_leh_remains_certified():
    """Verify Leh is certified at 24h lead for temperature_2m."""
    cert = evaluate_scientific_certification(location="Leh", variable="temperature_2m", lead_hours=24)
    assert cert.status == CertificationStatus.CERTIFIED
    assert cert.is_certified is True


# =========================================================================
# 26. Dispur Remains Outside Certified Scope
# =========================================================================
def test_26_dispur_remains_outside_certified_scope():
    """Verify Dispur is outside certified scope."""
    cert = evaluate_scientific_certification(location="Dispur", variable="temperature_2m", lead_hours=24)
    assert cert.status == CertificationStatus.OUTSIDE_CERTIFIED_SCOPE
    assert cert.is_certified is False
    assert cert.reason_code == CertificationReasonCode.UNCERTIFIED_LOCATION

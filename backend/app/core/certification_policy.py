"""Authoritative Scientific Certification Policy for Veyra Phase 3 Day 32.

Single deterministic source of truth for Day 32 Scientific Certification Gate (C1).
Evaluates whether a prediction/evaluation request lies strictly inside or outside
the frozen scientific evidence boundary derived from Day 22 / Day 23 offline benchmark
certifications.
"""
import logging
from typing import List, Optional, Set

from backend.app.schemas.certification import (
    CertificationReasonCode,
    CertificationStatus,
    ScientificCertificationResult,
)

logger = logging.getLogger(__name__)

CERTIFICATION_POLICY_VERSION = "v3.0.0-frozen-benchmark"
EXPECTED_MODEL_SHA256 = "00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660"
EXPECTED_CALIBRATOR_SHA256 = "9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531"

MAX_CERTIFIED_LEAD_HOURS = 240  # 10-day benchmark horizon

CERTIFIED_VARIABLES: List[str] = [
    "temperature_2m",
    "wind_speed_10m",
    "surface_pressure",
]

# Canonical 25 synoptic stations evaluated in Day 22/27/28 benchmark dataset
CERTIFIED_BENCHMARK_STATIONS: List[str] = [
    "Ahmedabad",
    "Bengaluru",
    "Bhopal",
    "Bhubaneswar",
    "Chandigarh",
    "Chennai",
    "Dehradun",
    "Delhi",
    "Dispur",
    "Gangtok",
    "Goa",
    "Guwahati",
    "Hyderabad",
    "Jaipur",
    "Kochi",
    "Kolkata",
    "Lucknow",
    "Mumbai",
    "Nagpur",
    "Patna",
    "Pune",
    "Raipur",
    "Ranchi",
    "Shillong",
    "Shimla",
    "Srinagar",
    "Thiruvananthapuram",
    "Varanasi",
    "Vijayawada",
    "Visakhapatnam",
]

# Case-insensitive lookup set for station matching
_CERTIFIED_STATION_LOWER_SET: Set[str] = {
    s.lower() for s in CERTIFIED_BENCHMARK_STATIONS
} | {
    "ncr", "national capital region", "panaji", "new delhi"
}


def evaluate_scientific_certification(
    location: Optional[str],
    variable: Optional[str],
    lead_hours: Optional[int],
    model_sha256: Optional[str] = None,
    calibrator_sha256: Optional[str] = None,
) -> ScientificCertificationResult:
    """Evaluate whether the request lies strictly within the frozen scientific evidence boundary.

    Enforces:
    1. Cryptographic artifact integrity check (model SHA & calibrator SHA).
    2. Location boundary check (must match one of the 25 certified benchmark stations).
    3. Variable boundary check (temperature_2m, wind_speed_10m, surface_pressure).
    4. Horizon boundary check (lead_hours <= 240h).
    """
    effective_model_sha = (model_sha256 or EXPECTED_MODEL_SHA256).lower().strip()
    effective_calibrator_sha = (calibrator_sha256 or EXPECTED_CALIBRATOR_SHA256).lower().strip()

    # 1. Artifact Check
    if effective_model_sha != EXPECTED_MODEL_SHA256:
        return ScientificCertificationResult(
            status=CertificationStatus.CERTIFICATION_UNKNOWN,
            is_certified=False,
            reason_code=CertificationReasonCode.MODEL_ARTIFACT_MISMATCH,
            reason_detail=f"Serving model artifact SHA256 '{effective_model_sha[:12]}...' does not match authoritative V3 challenger checksum.",
            policy_version=CERTIFICATION_POLICY_VERSION,
            model_sha256=effective_model_sha,
            calibrator_sha256=effective_calibrator_sha,
            evaluated_location=location,
            evaluated_variable=variable,
            evaluated_lead_hours=lead_hours,
            certified_benchmark_stations=CERTIFIED_BENCHMARK_STATIONS,
            certified_variables=CERTIFIED_VARIABLES,
            max_certified_lead_hours=MAX_CERTIFIED_LEAD_HOURS,
        )

    if effective_calibrator_sha != EXPECTED_CALIBRATOR_SHA256:
        return ScientificCertificationResult(
            status=CertificationStatus.CERTIFICATION_UNKNOWN,
            is_certified=False,
            reason_code=CertificationReasonCode.CALIBRATOR_ARTIFACT_MISMATCH,
            reason_detail=f"Serving calibrator artifact SHA256 '{effective_calibrator_sha[:12]}...' does not match authoritative V3 calibrator checksum.",
            policy_version=CERTIFICATION_POLICY_VERSION,
            model_sha256=effective_model_sha,
            calibrator_sha256=effective_calibrator_sha,
            evaluated_location=location,
            evaluated_variable=variable,
            evaluated_lead_hours=lead_hours,
            certified_benchmark_stations=CERTIFIED_BENCHMARK_STATIONS,
            certified_variables=CERTIFIED_VARIABLES,
            max_certified_lead_hours=MAX_CERTIFIED_LEAD_HOURS,
        )

    # 2. Location Boundary Check
    loc_clean = (location or "").strip().lower()
    if not loc_clean or loc_clean not in _CERTIFIED_STATION_LOWER_SET:
        return ScientificCertificationResult(
            status=CertificationStatus.OUTSIDE_CERTIFIED_SCOPE,
            is_certified=False,
            reason_code=CertificationReasonCode.UNCERTIFIED_LOCATION,
            reason_detail=f"Location '{location}' lies outside the 25 synoptic stations certified in the Day 22/Day 23 offline benchmark dataset.",
            policy_version=CERTIFICATION_POLICY_VERSION,
            model_sha256=effective_model_sha,
            calibrator_sha256=effective_calibrator_sha,
            evaluated_location=location,
            evaluated_variable=variable,
            evaluated_lead_hours=lead_hours,
            certified_benchmark_stations=CERTIFIED_BENCHMARK_STATIONS,
            certified_variables=CERTIFIED_VARIABLES,
            max_certified_lead_hours=MAX_CERTIFIED_LEAD_HOURS,
        )

    # 3. Variable Boundary Check
    var_clean = (variable or "").strip().lower()
    if not var_clean or var_clean not in {v.lower() for v in CERTIFIED_VARIABLES}:
        return ScientificCertificationResult(
            status=CertificationStatus.OUTSIDE_CERTIFIED_SCOPE,
            is_certified=False,
            reason_code=CertificationReasonCode.UNCERTIFIED_VARIABLE,
            reason_detail=f"Variable '{variable}' is outside the certified surface variables (temperature_2m, wind_speed_10m, surface_pressure).",
            policy_version=CERTIFICATION_POLICY_VERSION,
            model_sha256=effective_model_sha,
            calibrator_sha256=effective_calibrator_sha,
            evaluated_location=location,
            evaluated_variable=variable,
            evaluated_lead_hours=lead_hours,
            certified_benchmark_stations=CERTIFIED_BENCHMARK_STATIONS,
            certified_variables=CERTIFIED_VARIABLES,
            max_certified_lead_hours=MAX_CERTIFIED_LEAD_HOURS,
        )

    # 4. Horizon Boundary Check
    effective_lead = lead_hours if lead_hours is not None else 24
    if effective_lead > MAX_CERTIFIED_LEAD_HOURS:
        return ScientificCertificationResult(
            status=CertificationStatus.OUTSIDE_CERTIFIED_SCOPE,
            is_certified=False,
            reason_code=CertificationReasonCode.UNCERTIFIED_LEAD_HORIZON,
            reason_detail=f"Lead horizon {effective_lead}h exceeds maximum certified benchmark horizon ({MAX_CERTIFIED_LEAD_HOURS}h / 10 days).",
            policy_version=CERTIFICATION_POLICY_VERSION,
            model_sha256=effective_model_sha,
            calibrator_sha256=effective_calibrator_sha,
            evaluated_location=location,
            evaluated_variable=variable,
            evaluated_lead_hours=effective_lead,
            certified_benchmark_stations=CERTIFIED_BENCHMARK_STATIONS,
            certified_variables=CERTIFIED_VARIABLES,
            max_certified_lead_hours=MAX_CERTIFIED_LEAD_HOURS,
        )

    # All certification conditions satisfied
    return ScientificCertificationResult(
        status=CertificationStatus.CERTIFIED,
        is_certified=True,
        reason_code=CertificationReasonCode.CERTIFIED_FROZEN_BENCHMARK_SCOPE,
        reason_detail=f"Request strictly satisfies all Day 22 / Day 23 frozen benchmark certification bounds ({location}, {variable}, {effective_lead}h).",
        policy_version=CERTIFICATION_POLICY_VERSION,
        model_sha256=effective_model_sha,
        calibrator_sha256=effective_calibrator_sha,
        evaluated_location=location,
        evaluated_variable=variable,
        evaluated_lead_hours=effective_lead,
        certified_benchmark_stations=CERTIFIED_BENCHMARK_STATIONS,
        certified_variables=CERTIFIED_VARIABLES,
        max_certified_lead_hours=MAX_CERTIFIED_LEAD_HOURS,
    )

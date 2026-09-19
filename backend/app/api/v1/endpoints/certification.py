"""Scientific Certification API Endpoint for Veyra Phase 3 Day 32.

Exposes read-only endpoints for evaluating scientific certification decisions
and retrieving authoritative certification policy metadata.
"""
import logging
from fastapi import APIRouter, HTTPException, status

from backend.app.core.certification_policy import (
    CERTIFICATION_POLICY_VERSION,
    CERTIFIED_BENCHMARK_STATIONS,
    CERTIFIED_VARIABLES,
    EXPECTED_CALIBRATOR_SHA256,
    EXPECTED_MODEL_SHA256,
    MAX_CERTIFIED_LEAD_HOURS,
    evaluate_scientific_certification,
)
from backend.app.schemas.certification import (
    CertificationEvaluationRequest,
    ScientificCertificationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/certification", tags=["Scientific Certification"])


@router.post(
    "/evaluate",
    response_model=ScientificCertificationResult,
    summary="Evaluate Scientific Certification Gate",
    description="Evaluates whether a forecast prediction or evaluation request lies strictly inside or outside the frozen Day 22 / Day 23 scientific evidence boundary.",
)
def evaluate_certification_gate(
    request: CertificationEvaluationRequest,
) -> ScientificCertificationResult:
    """Evaluate scientific certification decision for given parameters."""
    try:
        return evaluate_scientific_certification(
            location=request.location,
            variable=request.variable,
            lead_hours=request.lead_hours,
        )
    except Exception as exc:
        logger.error("Error evaluating scientific certification gate: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate scientific certification gate: {exc}",
        )


@router.get(
    "/policy",
    summary="Get Scientific Certification Policy Metadata",
    description="Retrieves authoritative scientific certification boundaries, certified station registry, and artifact checksums.",
)
def get_certification_policy() -> dict:
    """Retrieve authoritative scientific certification policy boundaries."""
    return {
        "policy_version": CERTIFICATION_POLICY_VERSION,
        "model_sha256": EXPECTED_MODEL_SHA256,
        "calibrator_sha256": EXPECTED_CALIBRATOR_SHA256,
        "max_certified_lead_hours": MAX_CERTIFIED_LEAD_HOURS,
        "certified_variables": CERTIFIED_VARIABLES,
        "certified_benchmark_stations": CERTIFIED_BENCHMARK_STATIONS,
        "certified_station_count": len(CERTIFIED_BENCHMARK_STATIONS),
        "certified_evaluation_period": "2017-2019 (Test Holdout)",
    }

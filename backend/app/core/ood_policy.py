"""Authoritative Out-of-Distribution (OOD) Policy Engine for Veyra Phase 3 Day 33 (Gate C2).

Deterministic evaluation of whether weather forecast inputs lie within or outside
the physical domain support of the 20-year NOAA GEFSv12 benchmark training distribution.

SCIENTIFIC GOVERNANCE PRINCIPLES:
1. Diagnostic-Only: OOD evaluation is a diagnostic heuristic assessing physical parameter plausibility.
   It does NOT modify model output probabilities, calculate formal prediction intervals, or force model abstention.
2. Independent Concept: OOD status is strictly distinct from:
   - Scientific Certification (Gate C1, Day 32)
   - Calibrated P(BUST) (Isotonic calibration, Day 24)
   - Operational Risk Level (LOW, MEDIUM, HIGH, CRITICAL)
   - Provider Quality / Pipeline Health (QC_FAILED, DATA_UNAVAILABLE)
3. No Coverage Claims: This policy makes no claim of formal conformal statistical coverage or calibrated epistemic uncertainty.
"""
import logging
import math
from typing import Any, Dict, Optional

from backend.app.schemas.ood import (
    OODDiagnosticResult,
    OODPolicyMetadata,
    OODReasonCode,
    OODState,
)

logger = logging.getLogger(__name__)

OOD_POLICY_VERSION = "v3.0.0-physical-support"

# Physical domain nominal bounding ranges (derived from 2000-2019 NOAA GEFSv12 benchmark)
PHYSICAL_DOMAIN_BOUNDS: Dict[str, Dict[str, Any]] = {
    "temperature_2m": {
        "min": 200.0,      # ~ -73.15 °C
        "max": 350.0,      # ~ +76.85 °C
        "unit": "K",
        "description": "200.0 K (-73.15°C) to 350.0 K (+76.85°C)",
    },
    "wind_speed_10m": {
        "min": 0.0,
        "max": 60.0,       # 60 m/s (~ 216 km/h, Cat 4/5 hurricane threshold)
        "unit": "m/s",
        "description": "0.0 m/s to 60.0 m/s",
    },
    "surface_pressure": {
        "min": 50000.0,    # 500 hPa (high-altitude synoptic extreme)
        "max": 110000.0,   # 1100 hPa (extreme surface high pressure)
        "unit": "Pa",
        "description": "50,000 Pa (500 hPa) to 110,000 Pa (1100 hPa)",
    },
}

SUPPORTED_OOD_VARIABLES = list(PHYSICAL_DOMAIN_BOUNDS.keys())


def evaluate_ood_policy(
    variable: Optional[str],
    forecast_value: Optional[float] = None,
    raw_ood_score: Optional[float] = None,
    quality_flags: Optional[Dict[str, Any]] = None,
) -> OODDiagnosticResult:
    """Evaluate OOD diagnostic state for given forecast parameters.

    Args:
        variable: Atmospheric variable identifier (e.g. 'temperature_2m').
        forecast_value: Numerical forecast value in canonical V3 units (K, m/s, Pa).
        raw_ood_score: Precomputed physical novelty score (0.0 to 100.0) from feature pipeline.
        quality_flags: Upstream data provider quality flags.

    Returns:
        Structured OODDiagnosticResult with deterministic status and reason code.
    """
    # 1. Check for invalid or missing variable
    if not variable or not str(variable).strip():
        return OODDiagnosticResult(
            status=OODState.OOD_UNKNOWN,
            is_ood=None,
            reason_code=OODReasonCode.INVALID_REQUEST_PARAMETERS,
            reason_detail="Forecast variable is missing or empty.",
            ood_score=None,
            policy_version=OOD_POLICY_VERSION,
            causes_abstention=False,
            diagnostic_inputs={"variable": variable},
        )

    var_clean = str(variable).strip().lower()
    if var_clean not in PHYSICAL_DOMAIN_BOUNDS:
        return OODDiagnosticResult(
            status=OODState.OOD_UNKNOWN,
            is_ood=None,
            reason_code=OODReasonCode.UNSUPPORTED_VARIABLE,
            reason_detail=f"Variable '{variable}' has no established physical domain bounds in OOD policy.",
            ood_score=None,
            policy_version=OOD_POLICY_VERSION,
            causes_abstention=False,
            diagnostic_inputs={"variable": variable},
        )

    bounds = PHYSICAL_DOMAIN_BOUNDS[var_clean]

    # 2. Check for missing or non-finite forecast value
    if forecast_value is None:
        return OODDiagnosticResult(
            status=OODState.OOD_UNKNOWN,
            is_ood=None,
            reason_code=OODReasonCode.INSUFFICIENT_EVIDENCE,
            reason_detail=f"No numerical forecast value available to evaluate physical domain for '{variable}'.",
            ood_score=raw_ood_score,
            policy_version=OOD_POLICY_VERSION,
            causes_abstention=False,
            diagnostic_inputs={"variable": var_clean, "raw_ood_score": raw_ood_score},
        )

    try:
        val_f = float(forecast_value)
    except (ValueError, TypeError):
        return OODDiagnosticResult(
            status=OODState.OOD_UNKNOWN,
            is_ood=None,
            reason_code=OODReasonCode.INSUFFICIENT_EVIDENCE,
            reason_detail=f"Non-numeric forecast value '{forecast_value}' for '{variable}'.",
            ood_score=raw_ood_score,
            policy_version=OOD_POLICY_VERSION,
            causes_abstention=False,
            diagnostic_inputs={"variable": var_clean, "forecast_value": str(forecast_value)},
        )

    if math.isnan(val_f) or math.isinf(val_f):
        return OODDiagnosticResult(
            status=OODState.OOD_UNKNOWN,
            is_ood=None,
            reason_code=OODReasonCode.INSUFFICIENT_EVIDENCE,
            reason_detail=f"Non-finite forecast value ({val_f}) for '{variable}'.",
            ood_score=raw_ood_score,
            policy_version=OOD_POLICY_VERSION,
            causes_abstention=False,
            diagnostic_inputs={"variable": var_clean, "forecast_value": str(val_f)},
        )

    # 3. Evaluate physical bounding ranges
    min_val = bounds["min"]
    max_val = bounds["max"]
    unit_str = bounds["unit"]

    effective_ood_score = raw_ood_score if raw_ood_score is not None else 0.0

    is_outside_bounds = (val_f < min_val) or (val_f > max_val)
    is_high_ood_score = effective_ood_score >= 45.0

    if is_outside_bounds or is_high_ood_score:
        return OODDiagnosticResult(
            status=OODState.OUT_OF_DISTRIBUTION,
            is_ood=True,
            reason_code=OODReasonCode.OUT_OF_PHYSICAL_SUPPORT,
            reason_detail=(
                f"Observed {var_clean}={val_f:.2f} {unit_str} lies outside nominal physical training bounds "
                f"[{min_val}, {max_val}] {unit_str} (diagnostic OOD score: {effective_ood_score:.1f})."
            ),
            ood_score=effective_ood_score,
            policy_version=OOD_POLICY_VERSION,
            causes_abstention=False,
            diagnostic_inputs={
                "variable": var_clean,
                "forecast_value": val_f,
                "unit": unit_str,
                "nominal_min": min_val,
                "nominal_max": max_val,
                "raw_ood_score": effective_ood_score,
            },
        )

    # 4. In-distribution nominal condition
    return OODDiagnosticResult(
        status=OODState.IN_DISTRIBUTION,
        is_ood=False,
        reason_code=OODReasonCode.WITHIN_PHYSICAL_TRAINING_SUPPORT,
        reason_detail=(
            f"Forecast value {val_f:.2f} {unit_str} strictly satisfies nominal physical training bounds "
            f"[{min_val}, {max_val}] {unit_str} for {var_clean}."
        ),
        ood_score=effective_ood_score,
        policy_version=OOD_POLICY_VERSION,
        causes_abstention=False,
        diagnostic_inputs={
            "variable": var_clean,
            "forecast_value": val_f,
            "unit": unit_str,
            "nominal_min": min_val,
            "nominal_max": max_val,
            "raw_ood_score": effective_ood_score,
        },
    )


def get_ood_policy_metadata() -> OODPolicyMetadata:
    """Retrieve authoritative OOD policy metadata."""
    return OODPolicyMetadata(
        policy_version=OOD_POLICY_VERSION,
        description=(
            "Deterministic physical domain bounding policy assessing whether weather forecast inputs "
            "fall within the empirical parameter envelope of the 2000-2019 NOAA GEFS benchmark."
        ),
        supported_variables=SUPPORTED_OOD_VARIABLES,
        physical_bounding_ranges=PHYSICAL_DOMAIN_BOUNDS,
        causes_abstention=False,
        governance_note=(
            "OOD diagnostics assess physical parameter plausibility only. They do NOT modify model "
            "probabilities, compute formal statistical coverage intervals, or supersede Day 32 scientific certification."
        ),
    )

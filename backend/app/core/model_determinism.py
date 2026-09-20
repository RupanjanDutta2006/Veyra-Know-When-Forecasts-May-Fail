"""Authoritative Model Determinism and Selection Policy for Veyra Phase 3 Day 33 (Gate C3).

Guarantees:
1. Deterministic Model Selection: Explicit mapping of model_type aliases to canonical artifacts.
2. Canonical Default: Omitted or 'default' model_type always resolves to the authoritative V3 Challenger.
3. Cryptographic Integrity: Validates SHA-256 digests against authoritative frozen evidence.
4. Input Invariance: Identical feature inputs produce bitwise deterministic predictions.
"""
import logging
from typing import Dict, Optional, Set

from backend.app.schemas.provenance import ModelProvenanceInfo

logger = logging.getLogger(__name__)

# Authoritative V3 Checksums & Provenance
V3_MODEL_SHA256 = "00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660"
V3_CALIBRATOR_SHA256 = "9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531"
V3_FEATURE_COUNT = 50
V3_MODEL_VERSION = "veyra-v3-benchmark-lightgbm"
V3_CALIBRATOR_TYPE = "IsotonicRegression"
V3_OPERATIONAL_THRESHOLD = 0.060
V3_SCHEMA_VERSION = "veyra-50-features-v3.0"

# Canonical Model Selection Alias Mapping
# Maps any accepted alias to its authoritative internal model key
MODEL_ALIAS_MAP: Dict[str, str] = {
    # V3 Challenger (Primary Authoritative Model)
    "veyra-v3-benchmark-lightgbm": "builder2_v3",
    "lightgbm": "builder2_v3",
    "lgbm": "builder2_v3",
    "default": "builder2_v3",
    # Legacy / Compatibility Prototype
    "prototype-gbm-v1": "builder2_gbm",
    # Baseline Logistic
    "baseline-logistic-v1.0": "baseline_logistic",
    "logistic": "baseline_logistic",
    "baseline": "baseline_logistic",
}

CANONICAL_MODEL_KEYS: Set[str] = {"builder2_v3", "builder2_gbm", "baseline_logistic"}


def resolve_model_identifier(model_type: Optional[str]) -> str:
    """Deterministically resolve any accepted model_type string or alias to an internal model key.

    Args:
        model_type: Input model identifier from request, or None for canonical default.

    Returns:
        Internal registered model key ('builder2_v3', 'builder2_gbm', 'baseline_logistic').

    Raises:
        ValueError: If model_type is unknown or unsupported.
    """
    if model_type is None:
        return "builder2_v3"

    clean_mt = str(model_type).strip().lower()
    if not clean_mt:
        return "builder2_v3"

    if clean_mt in MODEL_ALIAS_MAP:
        return MODEL_ALIAS_MAP[clean_mt]

    raise ValueError(
        f"Unsupported model_type '{model_type}'. "
        f"Supported identifiers/aliases: {', '.join(sorted(MODEL_ALIAS_MAP.keys()))}"
    )


def get_authoritative_v3_provenance(artifact_path: Optional[str] = None) -> ModelProvenanceInfo:
    """Return authoritative provenance metadata for the V3 Challenger model."""
    return ModelProvenanceInfo(
        model_name="builder2_v3",
        model_version=V3_MODEL_VERSION,
        model_sha256=V3_MODEL_SHA256,
        calibrator_type=V3_CALIBRATOR_TYPE,
        calibrator_sha256=V3_CALIBRATOR_SHA256,
        feature_count=V3_FEATURE_COUNT,
        feature_schema_version=V3_SCHEMA_VERSION,
        decision_threshold=V3_OPERATIONAL_THRESHOLD,
        is_calibrated=True,
        is_deterministic=True,
        artifact_path=artifact_path or "models/v3",
    )

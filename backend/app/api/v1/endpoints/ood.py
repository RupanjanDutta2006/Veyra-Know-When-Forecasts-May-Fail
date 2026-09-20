"""Out-of-Distribution (OOD) Policy API Endpoint for Veyra Phase 3 Day 33.

Exposes read-only metadata on physical bounding ranges, policy version, and diagnostic governance.
"""
import logging
from fastapi import APIRouter

from backend.app.core.ood_policy import get_ood_policy_metadata
from backend.app.schemas.ood import OODPolicyMetadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ood", tags=["OOD Diagnostic Policy"])


@router.get(
    "/policy",
    response_model=OODPolicyMetadata,
    summary="Get OOD Diagnostic Policy Metadata",
    description=(
        "Retrieves authoritative OOD policy version, physical bounding ranges per variable, "
        "and governance contracts distinguishing physical diagnostics from formal statistical coverage."
    ),
)
def get_ood_policy() -> OODPolicyMetadata:
    """Retrieve authoritative OOD diagnostic policy metadata."""
    return get_ood_policy_metadata()

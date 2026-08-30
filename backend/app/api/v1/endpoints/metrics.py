"""Process-local lightweight metrics endpoint for operational observability."""
from typing import Any, Dict
from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.core.metrics import default_metrics

router = APIRouter()


@router.get(
    "/metrics",
    summary="Process-Local Operational Metrics",
    description="Returns in-process operational counters and performance telemetry. Does not make external network requests.",
)
async def get_metrics() -> Dict[str, Any]:
    """Retrieve process-local observability snapshot."""
    if not settings.METRICS_ENABLED:
        return {"enabled": False, "message": "In-process metrics collection is disabled."}
    return default_metrics.snapshot()

"""Live Provider Smoke Check Engine for Veyra Phase 3 Day 35 (Gate C5).

Performs a minimal live Open-Meteo API query to verify network connectivity and schema compatibility,
reporting `LIVE_PROVIDER_VERIFIED` or `LIVE_PROVIDER_UNVERIFIED` without impacting offline replay gates.
"""
from enum import Enum
import logging
from typing import Tuple

from backend.app.services.openmeteo_service import OpenMeteoGEFSWeatherService

logger = logging.getLogger(__name__)


class LiveProviderStatus(str, Enum):
    """Enumeration of live provider smoke status outcomes."""

    LIVE_PROVIDER_VERIFIED = "LIVE_PROVIDER_VERIFIED"
    LIVE_PROVIDER_UNVERIFIED = "LIVE_PROVIDER_UNVERIFIED"


def perform_live_provider_smoke_check() -> Tuple[LiveProviderStatus, str]:
    """Execute a minimal, low-overhead live provider query (Delhi, 24h lead).

    Returns:
        Tuple of (status: LiveProviderStatus, detail: str).
    """
    try:
        service = OpenMeteoGEFSWeatherService()
        res = service.get_forecast(
            location="Delhi",
            variable="temperature_2m",
            lead_hours=24,
        )
        if res and res.record and res.record.forecast_value is not None:
            return (
                LiveProviderStatus.LIVE_PROVIDER_VERIFIED,
                f"Successfully retrieved live GEFS forecast value ({res.record.forecast_value:.2f} {res.record.unit or ''}) from Open-Meteo API.",
            )
        else:
            return (
                LiveProviderStatus.LIVE_PROVIDER_UNVERIFIED,
                "Live Open-Meteo API returned empty or invalid payload.",
            )
    except Exception as exc:
        logger.warning("Live provider smoke check unverified: %s", exc)
        return (
            LiveProviderStatus.LIVE_PROVIDER_UNVERIFIED,
            f"Live provider query failed or rate-limited: {str(exc)}",
        )

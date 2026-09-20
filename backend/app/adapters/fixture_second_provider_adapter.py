"""Fixture Second Provider Adapter for Veyra Phase 3 Day 37 (Gate C7).

Implements a deterministic, test/demo-only second provider adapter (`fixture_second_provider`).
Used to validate multi-provider architecture, normalization, unit conversions, and cross-provider
disagreement intelligence without making external network calls.

CRITICAL SCIENTIFIC GOVERNANCE:
1. FIXTURE ONLY: This adapter is explicitly identified as `provider_source_mode = ProviderSourceMode.FIXTURE`.
2. NEVER LIVE: Must never be labeled or presented as a live operational provider.
3. DETERMINISTIC: Provides repeatable, versioned fixture outputs for contract testing.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.app.adapters.provider_adapter import (
    BaseProviderAdapter,
    NormalizedProviderForecast,
    ProviderResponseStatus,
    ProviderSourceMode,
    normalize_unit_value,
)
from backend.app.services.location_service import DynamicLocationService

logger = logging.getLogger(__name__)


# Deterministic fixture dataset for scientific contract testing
# Key: (canonical_location, variable, lead_hours)
FIXTURE_DATASET: Dict[Tuple[str, str, int], Dict[str, Any]] = {
    # 1. Delhi temperature_2m 24h (Small disagreement: +1.2 °C compared to Open-Meteo baseline 32.0 °C)
    ("Delhi", "temperature_2m", 24): {
        "raw_value": 33.2,
        "source_unit": "°C",
        "ensemble_mean": 33.0,
        "ensemble_std": 1.4,
        "member_values": [33.0 + (i * 0.1 - 1.5) for i in range(21)],
        "status": ProviderResponseStatus.SUCCESS,
    },
    # 2. Delhi wind_speed_10m 24h (Non-normalized unit input: 18.0 km/h -> 5.0 m/s)
    ("Delhi", "wind_speed_10m", 24): {
        "raw_value": 18.0,
        "source_unit": "km/h",
        "ensemble_mean": 18.0,
        "ensemble_std": 2.0,
        "member_values": [18.0 + (i * 0.2 - 2.0) for i in range(21)],
        "status": ProviderResponseStatus.SUCCESS,
    },
    # 3. Bengaluru wind_speed_10m 240h (Larger disagreement: +3.5 m/s)
    ("Bengaluru", "wind_speed_10m", 240): {
        "raw_value": 12.0,
        "source_unit": "m/s",
        "ensemble_mean": 11.8,
        "ensemble_std": 2.5,
        "member_values": [12.0 + (i * 0.2 - 2.0) for i in range(21)],
        "status": ProviderResponseStatus.SUCCESS,
    },
    # 4. Mumbai surface_pressure 264h (Non-normalized unit input: 101400 Pa -> 1014.0 hPa)
    ("Mumbai", "surface_pressure", 264): {
        "raw_value": 101400.0,
        "source_unit": "Pa",
        "ensemble_mean": 101400.0,
        "ensemble_std": 300.0,
        "member_values": [101400.0 + (i * 20.0 - 200.0) for i in range(21)],
        "status": ProviderResponseStatus.SUCCESS,
    },
    # 5. Panaji wind_speed_10m 48h (Location normalization case)
    ("Panaji", "wind_speed_10m", 48): {
        "raw_value": 11.5,
        "source_unit": "m/s",
        "ensemble_mean": 11.2,
        "ensemble_std": 1.8,
        "member_values": [11.5 + (i * 0.1 - 1.0) for i in range(21)],
        "status": ProviderResponseStatus.SUCCESS,
    },
    # 6. Shimla temperature_2m 24h (Non-normalized Kelvin input: 295.15 K -> 22.0 °C)
    ("Shimla", "temperature_2m", 24): {
        "raw_value": 295.15,
        "source_unit": "K",
        "ensemble_mean": 295.0,
        "ensemble_std": 1.2,
        "member_values": [295.0 + (i * 0.1 - 1.0) for i in range(21)],
        "status": ProviderResponseStatus.SUCCESS,
    },
    # 7. Leh temperature_2m 12h (Matching value case)
    ("Leh", "temperature_2m", 12): {
        "raw_value": 2.0,
        "source_unit": "°C",
        "ensemble_mean": 2.0,
        "ensemble_std": 1.0,
        "member_values": [2.0 + (i * 0.1 - 1.0) for i in range(21)],
        "status": ProviderResponseStatus.SUCCESS,
    },
    # 8. Kolkata surface_pressure 48h (Explicit unavailable fixture case)
    ("Kolkata", "surface_pressure", 48): {
        "raw_value": None,
        "source_unit": "hPa",
        "status": ProviderResponseStatus.UNAVAILABLE,
        "error_detail": "Fixture dataset missing provider value for Kolkata 48h pressure",
    },
}


class FixtureSecondProviderAdapter(BaseProviderAdapter):
    """Deterministic fixture-backed second provider adapter for contract testing."""

    def __init__(self, location_service: Optional[DynamicLocationService] = None):
        self.location_service = location_service or DynamicLocationService()

    @property
    def provider_id(self) -> str:
        return "fixture_second_provider"

    @property
    def provider_name(self) -> str:
        return "Fixture Secondary Provider (Deterministic Test-Only)"

    @property
    def provider_source_mode(self) -> ProviderSourceMode:
        return ProviderSourceMode.FIXTURE

    def fetch_forecast(
        self,
        location: str,
        variable: str,
        lead_hours: int = 24,
        issue_time: Optional[str] = None,
        valid_time: Optional[str] = None,
    ) -> NormalizedProviderForecast:
        """Retrieve deterministic fixture forecast and apply unit and temporal normalization."""
        if not location or not location.strip():
            return NormalizedProviderForecast(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                provider_source_mode=self.provider_source_mode,
                canonical_location="",
                latitude=0.0,
                longitude=0.0,
                issue_time=issue_time or "",
                valid_time=valid_time or "",
                lead_hours=lead_hours,
                variable=variable,
                forecast_value=None,
                unit="",
                is_available=False,
                status=ProviderResponseStatus.INVALID_REQUEST,
                error_detail="Location query string cannot be blank",
            )

        # Resolve location alias
        resolved = self.location_service.resolve(location)
        canonical_loc = resolved.name if resolved else location
        lat = resolved.latitude if resolved else 0.0
        lon = resolved.longitude if resolved else 0.0

        # Query fixture lookup table
        key = (canonical_loc, variable, lead_hours)
        fixture = FIXTURE_DATASET.get(key)

        if not fixture:
            # Generate deterministic fallback for uncatalogued valid location combinations
            if resolved:
                # Generate safe synthetic fixture value based on variable defaults
                if variable == "temperature_2m":
                    raw_val, s_unit = 25.0, "°C"
                elif variable == "wind_speed_10m":
                    raw_val, s_unit = 5.0, "m/s"
                elif variable == "surface_pressure":
                    raw_val, s_unit = 1013.25, "hPa"
                else:
                    return NormalizedProviderForecast(
                        provider_id=self.provider_id,
                        provider_name=self.provider_name,
                        provider_source_mode=self.provider_source_mode,
                        canonical_location=canonical_loc,
                        latitude=lat,
                        longitude=lon,
                        issue_time=issue_time or "",
                        valid_time=valid_time or "",
                        lead_hours=lead_hours,
                        variable=variable,
                        forecast_value=None,
                        unit="",
                        is_available=False,
                        status=ProviderResponseStatus.UNSUPPORTED_VARIABLE,
                        error_detail=f"Unsupported variable '{variable}'",
                    )

                norm_val, norm_unit = normalize_unit_value(raw_val, s_unit, variable)
                return NormalizedProviderForecast(
                    provider_id=self.provider_id,
                    provider_name=self.provider_name,
                    provider_source_mode=self.provider_source_mode,
                    canonical_location=canonical_loc,
                    latitude=lat,
                    longitude=lon,
                    issue_time=issue_time or "2026-09-20T00:00:00Z",
                    valid_time=valid_time or f"2026-09-21T{lead_hours:02d}:00:00Z",
                    lead_hours=lead_hours,
                    variable=variable,
                    forecast_value=round(norm_val, 4),
                    unit=norm_unit,
                    ensemble_mean=round(norm_val, 4),
                    ensemble_std=1.0,
                    member_values=[norm_val for _ in range(21)],
                    is_available=True,
                    status=ProviderResponseStatus.SUCCESS,
                    metadata={"fixture_type": "generated_synthetic_fallback"},
                )

            return NormalizedProviderForecast(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                provider_source_mode=self.provider_source_mode,
                canonical_location=canonical_loc,
                latitude=lat,
                longitude=lon,
                issue_time=issue_time or "",
                valid_time=valid_time or "",
                lead_hours=lead_hours,
                variable=variable,
                forecast_value=None,
                unit="",
                is_available=False,
                status=ProviderResponseStatus.UNAVAILABLE,
                error_detail=f"No fixture data available for key {key}",
            )

        status = fixture.get("status", ProviderResponseStatus.SUCCESS)
        if status != ProviderResponseStatus.SUCCESS or fixture.get("raw_value") is None:
            return NormalizedProviderForecast(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                provider_source_mode=self.provider_source_mode,
                canonical_location=canonical_loc,
                latitude=lat,
                longitude=lon,
                issue_time=issue_time or "",
                valid_time=valid_time or "",
                lead_hours=lead_hours,
                variable=variable,
                forecast_value=None,
                unit="",
                is_available=False,
                status=status,
                error_detail=fixture.get("error_detail", "Fixture unavailable"),
            )

        norm_val, norm_unit = normalize_unit_value(
            value=fixture["raw_value"],
            source_unit=fixture.get("source_unit", ""),
            target_variable=variable,
        )

        return NormalizedProviderForecast(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            provider_source_mode=self.provider_source_mode,
            canonical_location=canonical_loc,
            latitude=lat,
            longitude=lon,
            issue_time=issue_time or "2026-09-20T00:00:00Z",
            valid_time=valid_time or "2026-09-21T00:00:00Z",
            lead_hours=lead_hours,
            variable=variable,
            forecast_value=round(norm_val, 4),
            unit=norm_unit,
            ensemble_mean=fixture.get("ensemble_mean"),
            ensemble_std=fixture.get("ensemble_std"),
            member_values=fixture.get("member_values"),
            is_available=True,
            status=ProviderResponseStatus.SUCCESS,
            metadata={"fixture_key": str(key)},
        )

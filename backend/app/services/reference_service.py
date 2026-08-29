"""Reference Weather Service for Historical Ground Truth & Verification (ERA5 / Observations)."""
import json
import logging
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from backend.app.core.config import settings
from backend.app.core.http_retry import execute_with_retry
from backend.app.schemas.reference import ReferenceWeatherDataset, ReferenceWeatherRecord
from backend.app.services.location_service import (
    BaseLocationService,
    DynamicLocationService,
)

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"


class BaseReferenceWeatherService(ABC):
    """Abstract interface for historical observation / reanalysis verification providers."""

    @abstractmethod
    def get_reference_data(
        self,
        location: str,
        start_date: str,
        end_date: str,
    ) -> list[ReferenceWeatherRecord]:
        """Fetch historical reference observations across a date range."""
        pass


class OpenMeteoArchiveReferenceService(BaseReferenceWeatherService):
    """Reference weather provider querying Open-Meteo Historical Archive / ERA5 Reanalysis.

    Used strictly for historical verification, error calculation, and training label generation.
    Never used in live inference feature pathways.
    """

    def __init__(
        self,
        api_url: str = DEFAULT_ARCHIVE_API_URL,
        http_client: Optional[Callable[[str], dict[str, Any]]] = None,
        timeout_seconds: Optional[int] = None,
        location_service: Optional[BaseLocationService] = None,
        max_retries: Optional[int] = None,
        retry_backoff_factor: Optional[float] = None,
    ):
        self.api_url = api_url
        self.http_client = http_client or self._default_http_client
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.REFERENCE_TIMEOUT_SECONDS
        )
        self.location_service = location_service or DynamicLocationService()
        self.max_retries = (
            max_retries
            if max_retries is not None
            else settings.MAX_HTTP_RETRIES
        )
        self.retry_backoff_factor = (
            retry_backoff_factor
            if retry_backoff_factor is not None
            else settings.RETRY_BACKOFF_FACTOR
        )

    def _default_http_client(self, url: str) -> dict[str, Any]:
        """Fetch JSON data from URL using standard library urllib with bounded retry and backoff."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Veyra-Historical-Verification/0.1.0"},
        )

        def _do_fetch() -> dict[str, Any]:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP error {response.status} fetching reference data")
                payload = response.read().decode("utf-8")
                return json.loads(payload)

        return execute_with_retry(
            _do_fetch,
            max_retries=self.max_retries,
            backoff_factor=self.retry_backoff_factor,
            operation_name="OpenMeteo Archive reference fetch",
        )

    def resolve_coordinates(self, location: str) -> Optional[tuple[float, float]]:
        """Resolve location name or coordinate string."""
        return self.location_service.resolve_coordinates(location)

    def build_query_url(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
    ) -> str:
        """Construct historical archive query URL."""
        params = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,surface_pressure,wind_speed_10m,relative_humidity_2m,precipitation",
            "timezone": "UTC",
            "wind_speed_unit": "ms",
        }
        return f"{self.api_url}?{urllib.parse.urlencode(params)}"

    def parse_reference_records(
        self,
        raw_response: dict[str, Any],
        location: str,
        latitude: float,
        longitude: float,
    ) -> list[ReferenceWeatherRecord]:
        """Convert raw archive response into standardized ReferenceWeatherRecords."""
        records: list[ReferenceWeatherRecord] = []
        hourly = raw_response.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return []

        var_mapping = {
            "temperature_2m": ("temperature_2m", "celsius"),
            "surface_pressure": ("surface_pressure", "hPa"),
            "wind_speed_10m": ("wind_speed_10m", "m/s"),
            "relative_humidity_2m": ("relative_humidity_2m", "%"),
            "precipitation": ("precipitation", "mm"),
        }

        for i, time_str in enumerate(times):
            try:
                valid_dt = datetime.fromisoformat(time_str)
                valid_time_iso = valid_dt.isoformat() + "Z"
            except Exception:
                valid_time_iso = time_str

            for src_var, (canon_var, canon_unit) in var_mapping.items():
                if src_var in hourly:
                    vals = hourly[src_var]
                    if i < len(vals):
                        val_raw = vals[i]
                        if val_raw is not None:
                            rec = ReferenceWeatherRecord(
                                location=location,
                                latitude=latitude,
                                longitude=longitude,
                                variable=canon_var,
                                unit=canon_unit,
                                valid_time=valid_time_iso,
                                observed_value=float(val_raw),
                                source="ERA5_REANALYSIS",
                                is_ground_truth_label=True,
                            )
                            records.append(rec)

        return records

    def get_reference_data(
        self,
        location: str,
        start_date: str,
        end_date: str,
    ) -> list[ReferenceWeatherRecord]:
        """Fetch and parse reference observations across date range."""
        coords = self.resolve_coordinates(location)
        if coords is None:
            logger.warning("Could not resolve coordinates for location '%s'", location)
            return []

        latitude, longitude = coords
        url = self.build_query_url(latitude, longitude, start_date, end_date)

        try:
            raw_data = self.http_client(url)
            return self.parse_reference_records(raw_data, location, latitude, longitude)
        except Exception as exc:
            logger.error("Failed to fetch historical reference data for '%s': %s", location, exc)
            return []

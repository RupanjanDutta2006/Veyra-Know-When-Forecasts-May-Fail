"""Reference Weather Service for Historical Ground Truth & Verification (ERA5 / Observations)."""
import json
import logging
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from backend.app.schemas.reference import ReferenceWeatherDataset, ReferenceWeatherRecord
from backend.app.services.openmeteo_service import KNOWN_LOCATIONS

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
        timeout_seconds: int = 10,
    ):
        self.api_url = api_url
        self.http_client = http_client or self._default_http_client
        self.timeout_seconds = timeout_seconds

    def _default_http_client(self, url: str) -> dict[str, Any]:
        """Fetch JSON data from URL using standard library urllib."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Veyra-Historical-Verification/0.1.0"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP error {response.status} fetching reference data")
            payload = response.read().decode("utf-8")
            return json.loads(payload)

    def resolve_coordinates(self, location: str) -> Optional[tuple[float, float]]:
        """Resolve location name or coordinate string."""
        loc_clean = location.strip().lower()
        if loc_clean in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[loc_clean]
        if "," in location:
            parts = location.split(",")
            if len(parts) == 2:
                try:
                    lat, lon = float(parts[0].strip()), float(parts[1].strip())
                    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                        return lat, lon
                except ValueError:
                    pass
        return None

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

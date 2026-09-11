"""Open-Meteo GFS Ensemble ingestion service.

The service preserves actual ensemble members and provider grid provenance.
It does not infer or fabricate ensemble statistics.
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable, Optional

from backend.app.data.qc import ForecastQualityControl
from backend.app.schemas.prediction import ReasonCode
from backend.app.schemas.weather import (
    CanonicalForecastDataset,
    CanonicalForecastRecord,
)
from backend.app.services.base import BaseWeatherService, WeatherResult

logger = logging.getLogger(__name__)


KNOWN_LOCATIONS: dict[str, tuple[float, float]] = {
    "london": (51.5074, -0.1278),
    "tokyo": (35.6762, 139.6503),
    "new york": (40.7128, -74.0060),
    "delhi": (28.6139, 77.2090),
    "kolkata": (22.5726, 88.3639),
    "mumbai": (19.0760, 72.8777),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "berlin": (52.5200, 13.4050),
    "paris": (48.8566, 2.3522),
    "singapore": (1.3521, 103.8198),
    "sydney": (-33.8688, 151.2093),
    "dubai": (25.2048, 55.2708),
    "geneva": (46.2044, 6.1432),
}


DEFAULT_ENSEMBLE_API_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

MODEL_NAME = "gfs_seamless"
SOURCE_NAME = "OPEN_METEO_GFS_ENSEMBLE"

VARIABLE_MAPPING = {
    "temperature_2m": ("temperature_2m", "celsius"),
    "surface_pressure": ("surface_pressure", "hPa"),
    "wind_speed_10m": ("wind_speed_10m", "m/s"),
    "relative_humidity_2m": ("relative_humidity_2m", "%"),
    "precipitation": ("precipitation", "mm"),
}


class OpenMeteoGEFSWeatherService(BaseWeatherService):
    """Fetch and validate Open-Meteo GFS ensemble forecasts."""

    def __init__(
        self,
        api_url: str = DEFAULT_ENSEMBLE_API_URL,
        qc_validator: Optional[ForecastQualityControl] = None,
        http_client: Optional[Callable[[str], dict[str, Any]]] = None,
        data_version: str = "gfs-ensemble-openmeteo-v2.0",
        timeout_seconds: int = 25,
    ):
        self.api_url = api_url
        self.qc = qc_validator or ForecastQualityControl()
        self.http_client = http_client or self._default_http_client
        self.data_version = data_version
        self.timeout_seconds = timeout_seconds

    def _default_http_client(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Veyra-Forecast-Bust-Sentinel/0.2.0"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP error {response.status}")
            return json.loads(response.read().decode("utf-8"))

    def resolve_coordinates(self, location: str) -> Optional[tuple[float, float]]:
        clean = location.strip().lower()

        try:
            from backend.app.services.location_service import get_location_registry
            coords = get_location_registry().resolve_coordinates(clean)
            if coords is not None:
                return (round(coords[0], 4), round(coords[1], 4))
        except Exception:
            pass

        if clean in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[clean]

        if "," in location:
            parts = location.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())

                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return lat, lon
                except ValueError:
                    pass

        return None

    def build_query_url(
        self,
        latitude: float,
        longitude: float,
        target_date: Optional[str] = None,
    ) -> str:
        params: dict[str, str] = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "hourly": ",".join(VARIABLE_MAPPING.keys()),
            "models": MODEL_NAME,
            "timezone": "UTC",
        }

        if target_date:
            params["start_date"] = target_date
            params["end_date"] = target_date

        return f"{self.api_url}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _iso(value: str) -> str:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _member_keys(hourly: dict[str, Any], variable: str) -> list[str]:
        """Return actual member fields present in the payload."""
        pattern = re.compile(rf"^{re.escape(variable)}_member(\d+)$")

        members = []

        for key in hourly:
            match = pattern.match(key)
            if match:
                members.append((int(match.group(1)), key))

        members.sort()
        return [key for _, key in members]

    @staticmethod
    def _stats(
        hourly: dict[str, Any],
        member_keys: list[str],
        index: int,
    ) -> tuple[Optional[int], Optional[float], Optional[float],
               Optional[float], Optional[float], Optional[float],
               Optional[float]]:
        """Calculate statistics from actual ensemble member values."""

        values: list[float] = []

        for key in member_keys:
            arr = hourly.get(key, [])

            if index >= len(arr):
                continue

            value = arr[index]

            if value is None:
                continue

            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue

        if not values:
            return None, None, None, None, None, None, None

        values.sort()
        n = len(values)

        mean = sum(values) / n

        if n > 1:
            variance = sum((x - mean) ** 2 for x in values) / (n - 1)
            std = variance ** 0.5
        else:
            std = 0.0

        def percentile(p: float) -> float:
            if n == 1:
                return values[0]

            position = (n - 1) * p
            lower = int(position)
            upper = min(lower + 1, n - 1)
            fraction = position - lower

            return values[lower] + fraction * (values[upper] - values[lower])

        return (
            n,
            mean,
            std,
            values[0],
            values[-1],
            percentile(0.10),
            percentile(0.90),
        )

    def parse_canonical_records(
        self,
        raw_response: dict[str, Any],
        location: str,
        latitude: float,
        longitude: float,
    ) -> list[CanonicalForecastRecord]:
        records: list[CanonicalForecastRecord] = []

        hourly = raw_response.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return []

        # Preserve provider-resolved coordinates.
        provider_lat = raw_response.get("latitude")
        provider_lon = raw_response.get("longitude")

        try:
            grid_lat = float(provider_lat) if provider_lat is not None else None
        except (TypeError, ValueError):
            grid_lat = None

        try:
            grid_lon = float(provider_lon) if provider_lon is not None else None
        except (TypeError, ValueError):
            grid_lon = None

        # IMPORTANT:
        # Do not pretend that the first valid timestamp is a model run.
        # The seamless endpoint does not give us enough information here to
        # establish exact historical run provenance.
        issue_time = None

        # Preserve explicit metadata if provider supplies it.
        for key in ("model_run", "run_time", "initialization_time", "init_time"):
            if raw_response.get(key):
                try:
                    issue_time = self._iso(str(raw_response[key]))
                    break
                except Exception:
                    pass

        # For live serving only, retain the old operational fallback.
        # Historical dataset construction must use an exact-run endpoint.
        if issue_time is None:
            first_time = str(times[0])
            try:
                first_dt = datetime.fromisoformat(
                    first_time.replace("Z", "+00:00")
                )
                issue_dt = first_dt.replace(
                    hour=(first_dt.hour // 6) * 6,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                issue_time = issue_dt.isoformat().replace("+00:00", "Z")
                inferred_issue = True
            except Exception:
                return []
        else:
            inferred_issue = False

        for i, valid_time_raw in enumerate(times):
            try:
                valid_time = self._iso(str(valid_time_raw))
                dt_issue = datetime.fromisoformat(
                    issue_time.replace("Z", "+00:00")
                )
                dt_valid = datetime.fromisoformat(
                    valid_time.replace("Z", "+00:00")
                )

                delta_hours = (
                    dt_valid - dt_issue
                ).total_seconds() / 3600.0

                if delta_hours < 0 or delta_hours != int(delta_hours):
                    continue

                lead_hours = int(delta_hours)

            except Exception:
                continue

            for src_var, (canonical_var, canonical_unit) in VARIABLE_MAPPING.items():
                values = hourly.get(src_var)

                if not isinstance(values, list) or i >= len(values):
                    continue

                raw_value = values[i]

                if raw_value is None:
                    continue

                try:
                    control_value = float(raw_value)
                except (TypeError, ValueError):
                    continue

                member_keys = self._member_keys(hourly, src_var)

                (
                    member_count,
                    ensemble_mean,
                    ensemble_std,
                    ensemble_min,
                    ensemble_max,
                    q10,
                    q90,
                ) = self._stats(hourly, member_keys, i)

                quality_flags = {
                    "ensemble_members_extracted": member_count is not None,
                    "ensemble_member_count": member_count,
                    "issue_time_inferred": inferred_issue,
                    "provider_grid_coordinates_present": (
                        grid_lat is not None and grid_lon is not None
                    ),
                }

                record = CanonicalForecastRecord(
                    location=location,
                    latitude=latitude,
                    longitude=longitude,
                    grid_latitude=grid_lat,
                    grid_longitude=grid_lon,
                    issue_time=issue_time,
                    valid_time=valid_time,
                    lead_hours=lead_hours,
                    variable=canonical_var,
                    unit=canonical_unit,
                    value=control_value,
                    source=SOURCE_NAME,
                    model=MODEL_NAME,
                    model_run=issue_time if not inferred_issue else None,
                    member_count=member_count,
                    ensemble_mean=ensemble_mean,
                    ensemble_std=ensemble_std,
                    ensemble_min=ensemble_min,
                    ensemble_max=ensemble_max,
                    q10=q10,
                    q90=q90,
                    quality_flags=quality_flags,
                    metadata={
                        "provider": "open-meteo",
                        "api_model": MODEL_NAME,
                        "requested_latitude": latitude,
                        "requested_longitude": longitude,
                        "provider_grid_latitude": grid_lat,
                        "provider_grid_longitude": grid_lon,
                        "data_version": self.data_version,
                    },
                )

                records.append(record)

        return records

    def get_forecast(
        self,
        location: str,
        target_date: Optional[str] = None,
    ) -> WeatherResult:

        coords = self.resolve_coordinates(location)

        if coords is None:
            return WeatherResult(
                location=location,
                target_date=target_date,
                is_available=False,
                quality_flags={"qc_passed": False, "invalid_location": True},
                metadata={"status": ReasonCode.INVALID_LOCATION.value},
                error=f"Location '{location}' could not be resolved",
            )

        latitude, longitude = coords
        query_url = self.build_query_url(latitude, longitude, target_date)

        try:
            raw_data = self.http_client(query_url)
        except Exception as exc:
            logger.error("Weather API failure: %s", exc)
            return WeatherResult(
                location=location,
                target_date=target_date,
                is_available=False,
                quality_flags={"qc_passed": False, "network_error": True},
                metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
                error=f"Weather ingestion failed: {exc}",
            )

        records = self.parse_canonical_records(
            raw_data,
            location,
            latitude,
            longitude,
        )

        if not records:
            return WeatherResult(
                location=location,
                target_date=target_date,
                is_available=False,
                quality_flags={"qc_passed": False, "empty_records": True},
                metadata={"status": ReasonCode.DATA_NOT_READY.value},
                error="Vendor API returned zero parseable records",
            )

        qc_result = self.qc.validate_records(records)

        if not qc_result.passed:
            return WeatherResult(
                location=location,
                target_date=target_date,
                raw_data={
                    "record_count": len(records),
                    "sample_records": [
                        r.model_dump() for r in records[:3]
                    ],
                },
                data_version=self.data_version,
                is_available=False,
                quality_flags=qc_result.flags,
                metadata={
                    "status": (
                        qc_result.reason_code.value
                        if qc_result.reason_code
                        else ReasonCode.QC_FAILED.value
                    ),
                    "violations": qc_result.violations,
                },
                error=(
                    "Quality control failed: "
                    + "; ".join(qc_result.violations[:3])
                ),
            )

        first = records[0]

        dataset = CanonicalForecastDataset(
            location=location,
            latitude=latitude,
            longitude=longitude,
            grid_latitude=first.grid_latitude,
            grid_longitude=first.grid_longitude,
            issue_time=first.issue_time,
            source=SOURCE_NAME,
            model=MODEL_NAME,
            model_run=first.model_run,
            records=records,
            metadata={
                "record_count": len(records),
                "data_version": self.data_version,
                "requested_coordinates": [latitude, longitude],
                "provider_grid_coordinates": [
                    first.grid_latitude,
                    first.grid_longitude,
                ],
            },
        )

        return WeatherResult(
            location=location,
            target_date=target_date,
            raw_data=dataset.model_dump(),
            data_version=self.data_version,
            is_available=True,
            quality_flags=qc_result.flags,
            metadata={
                "status": ReasonCode.SUCCESS.value,
                "record_count": len(records),
                "issue_time": first.issue_time,
                "lead_hours_range": [
                    min(r.lead_hours for r in records),
                    max(r.lead_hours for r in records),
                ],
                "ensemble_members_extracted": first.member_count,
                "provider_grid_coordinates": [
                    first.grid_latitude,
                    first.grid_longitude,
                ],
            },
        )
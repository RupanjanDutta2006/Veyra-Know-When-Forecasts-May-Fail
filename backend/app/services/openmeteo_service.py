"""Real Weather Ingestion Service using Open-Meteo GEFS / GFS public ensemble API."""
import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from backend.app.data.qc import ForecastQualityControl, QualityControlResult
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
    "berlin": (52.5200, 13.4050),
    "paris": (48.8566, 2.3522),
    "singapore": (1.3521, 103.8198),
    "sydney": (-33.8688, 151.2093),
    "dubai": (25.2048, 55.2708),
    "geneva": (46.2044, 6.1432),
}



DEFAULT_ENSEMBLE_API_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"


class OpenMeteoGEFSWeatherService(BaseWeatherService):
    """Production-grade weather ingestion service querying public GFS/GEFS ensemble data.

    Implements BaseWeatherService. Strictly converts raw vendor responses
    into CanonicalForecastRecord structures and runs rigorous Quality Control.
    """

    def __init__(
        self,
        api_url: str = DEFAULT_ENSEMBLE_API_URL,
        qc_validator: Optional[ForecastQualityControl] = None,
        http_client: Optional[Callable[[str], dict[str, Any]]] = None,
        data_version: str = "gefs-openmeteo-v1.0",
        timeout_seconds: int = 25,
    ):
        self.api_url = api_url
        self.qc = qc_validator or ForecastQualityControl()
        self.http_client = http_client or self._default_http_client
        self.data_version = data_version
        self.timeout_seconds = timeout_seconds

    def _default_http_client(self, url: str) -> dict[str, Any]:
        """Perform HTTP GET request using standard library urllib with transient retry."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Veyra-Forecast-Bust-Sentinel/0.1.0"},
        )
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP error {response.status} fetching forecast data")
                    payload = response.read().decode("utf-8")
                    return json.loads(payload)
            except Exception as exc:
                if attempt == max_attempts - 1:
                    raise exc


    def resolve_coordinates(self, location: str) -> Optional[tuple[float, float]]:
        """Resolve location name or coordinate string to (latitude, longitude)."""
        loc_clean = location.strip().lower()
        if loc_clean in KNOWN_LOCATIONS:
            return KNOWN_LOCATIONS[loc_clean]

        # Check if provided as 'lat,lon'
        if "," in location:
            parts = location.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
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
        """Construct the Open-Meteo GEFS ensemble query URL."""
        params: dict[str, str] = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "hourly": "temperature_2m,surface_pressure,wind_speed_10m,relative_humidity_2m,precipitation",
            "models": "gfs_seamless",
            "timezone": "UTC",
        }
        if target_date:
            params["start_date"] = target_date
            params["end_date"] = target_date

        return f"{self.api_url}?{urllib.parse.urlencode(params)}"

    def parse_canonical_records(
        self,
        raw_response: dict[str, Any],
        location: str,
        latitude: float,
        longitude: float,
    ) -> list[CanonicalForecastRecord]:
        """Parse vendor JSON payload into standardized CanonicalForecastRecords."""
        records: list[CanonicalForecastRecord] = []
        hourly = raw_response.get("hourly", {})
        hourly_units = raw_response.get("hourly_units", {})
        times = hourly.get("time", [])

        if not times:
            return []

        # Determine model issue time (first timestamp truncated to day cycle or current cycle)
        # In Open-Meteo, issue cycle is standard 00Z / 06Z / 12Z / 18Z run
        first_time = times[0]
        try:
            first_dt = datetime.fromisoformat(first_time)
            issue_dt = first_dt.replace(hour=(first_dt.hour // 6) * 6, minute=0, second=0)
            issue_time_iso = issue_dt.isoformat() + "Z"
        except Exception:
            issue_time_iso = datetime.now(timezone.utc).isoformat()

        # Variable mapping: Open-Meteo key -> (canonical name, canonical unit)
        var_mapping = {
            "temperature_2m": ("temperature_2m", "celsius"),
            "surface_pressure": ("surface_pressure", "hPa"),
            "wind_speed_10m": ("wind_speed_10m", "m/s"),
            "relative_humidity_2m": ("relative_humidity_2m", "%"),
            "precipitation": ("precipitation", "mm"),
        }

        for i, valid_time_str in enumerate(times):
            try:
                valid_dt = datetime.fromisoformat(valid_time_str)
                valid_time_iso = valid_dt.isoformat() + "Z"
            except Exception:
                valid_time_iso = valid_time_str

            # Strict lead hours calculation
            try:
                dt_issue = datetime.fromisoformat(issue_time_iso.replace("Z", "+00:00"))
                dt_valid = datetime.fromisoformat(valid_time_iso.replace("Z", "+00:00"))
                lead_hours = max(0, int((dt_valid - dt_issue).total_seconds() / 3600))
            except Exception:
                lead_hours = i

            for src_var, (canon_var, canon_unit) in var_mapping.items():
                if src_var in hourly:
                    vals = hourly[src_var]
                    if i < len(vals):
                        raw_val = vals[i]
                        val_float = float(raw_val) if raw_val is not None else None

                        record = CanonicalForecastRecord(
                            location=location,
                            latitude=latitude,
                            longitude=longitude,
                            issue_time=issue_time_iso,
                            valid_time=valid_time_iso,
                            lead_hours=lead_hours,
                            variable=canon_var,
                            unit=canon_unit,
                            value=val_float,
                            source="NOAA_GEFS_OPENMETEO",
                            member_count=31,  # Standard GEFS member count
                            ensemble_mean=val_float,
                        )
                        records.append(record)

        return records

    def get_forecast(
        self, location: str, target_date: Optional[str] = None
    ) -> WeatherResult:
        """Fetch live or mocked forecast data, validate QC, and return standardized WeatherResult."""
        coords = self.resolve_coordinates(location)
        if coords is None:
            return WeatherResult(
                location=location,
                target_date=target_date,
                is_available=False,
                quality_flags={"qc_passed": False, "invalid_location": True},
                metadata={"status": ReasonCode.INVALID_LOCATION.value},
                error=f"Location '{location}' could not be resolved to coordinates",
            )

        latitude, longitude = coords
        query_url = self.build_query_url(latitude, longitude, target_date)

        try:
            raw_data = self.http_client(query_url)
        except Exception as exc:
            logger.error("Failed to query weather API for location '%s': %s", location, exc)
            return WeatherResult(
                location=location,
                target_date=target_date,
                is_available=False,
                quality_flags={"qc_passed": False, "network_error": True},
                metadata={"status": ReasonCode.DATA_UNAVAILABLE.value},
                error=f"Weather ingestion failed: {exc}",
            )

        # Parse canonical records
        records = self.parse_canonical_records(raw_data, location, latitude, longitude)
        if not records:
            return WeatherResult(
                location=location,
                target_date=target_date,
                is_available=False,
                quality_flags={"qc_passed": False, "empty_records": True},
                metadata={"status": ReasonCode.DATA_NOT_READY.value},
                error="Vendor API returned zero parseable time-step records",
            )

        # Execute Quality Control checks
        qc_result = self.qc.validate_records(records)
        if not qc_result.passed:
            logger.warning("Quality control failed for location '%s': %s", location, qc_result.violations)
            return WeatherResult(
                location=location,
                target_date=target_date,
                raw_data={"record_count": len(records), "sample_records": [r.model_dump() for r in records[:3]]},
                data_version=self.data_version,
                is_available=False,
                quality_flags=qc_result.flags,
                metadata={
                    "status": qc_result.reason_code.value if qc_result.reason_code else ReasonCode.QC_FAILED.value,
                    "violations": qc_result.violations,
                },
                error=f"Quality control checks failed: {'; '.join(qc_result.violations[:3])}",
            )

        # QC Succeeded
        dataset = CanonicalForecastDataset(
            location=location,
            latitude=latitude,
            longitude=longitude,
            issue_time=records[0].issue_time,
            source="NOAA_GEFS_OPENMETEO",
            records=records,
            metadata={"record_count": len(records), "data_version": self.data_version},
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
                "issue_time": records[0].issue_time,
                "lead_hours_range": [records[0].lead_hours, records[-1].lead_hours],
            },
        )

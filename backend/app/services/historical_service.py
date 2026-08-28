"""Historical Weather and Forecast Data Collection Infrastructure Service.

Handles fetching, normalization, deduplication, quality control,
and dataset serialization for historical meteorological data.
"""
import json
import logging
import os
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from backend.app.data.historical_qc import (
    HistoricalDeduplicator,
    HistoricalQualityControl,
)
from backend.app.schemas.historical import (
    VARIABLE_CANONICAL_NAMES,
    VARIABLE_CANONICAL_UNITS,
    CanonicalHistoricalRecord,
    HistoricalCollectionResult,
    HistoricalDataRequest,
)
from backend.app.schemas.reference import ReferenceWeatherRecord
from backend.app.services.location_service import (
    BaseLocationService,
    DynamicLocationService,
)

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"


class BaseHistoricalDataService(ABC):
    """Abstract interface for historical meteorological data collection."""

    @abstractmethod
    def collect(self, request: HistoricalDataRequest) -> HistoricalCollectionResult:
        """Collect and normalize historical records for the given request."""
        pass


class HistoricalDataService(BaseHistoricalDataService):
    """Production historical weather data collector and validator.

    Integrates Day 8 Dynamic Location Resolution, deterministic deduplication,
    meteorological quality control, and Builder 2 dataset interfaces.
    """

    def __init__(
        self,
        api_url: str = DEFAULT_ARCHIVE_API_URL,
        location_service: Optional[BaseLocationService] = None,
        qc_validator: Optional[HistoricalQualityControl] = None,
        deduplicator: Optional[HistoricalDeduplicator] = None,
        http_client: Optional[Callable[[str], dict[str, Any]]] = None,
        timeout_seconds: int = 15,
    ):
        self.api_url = api_url
        self.location_service = location_service or DynamicLocationService()
        self.qc = qc_validator or HistoricalQualityControl()
        self.deduplicator = deduplicator or HistoricalDeduplicator()
        self.http_client = http_client or self._default_http_client
        self.timeout_seconds = timeout_seconds

    def _default_http_client(self, url: str) -> dict[str, Any]:
        """Perform HTTP GET with standard library urllib and transient retry."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Veyra-Historical-Collector/0.2.0"},
        )
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP error {response.status} from historical provider")
                    payload = response.read().decode("utf-8")
                    return json.loads(payload)
            except Exception as exc:
                if attempt == max_attempts - 1:
                    raise exc

    def build_query_url(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        variables: list[str],
        timezone_str: str = "UTC",
    ) -> str:
        """Construct historical archive query URL."""
        # Convert canonical variable names to provider hourly keys
        hourly_vars = ",".join(variables)
        params = {
            "latitude": str(latitude),
            "longitude": str(longitude),
            "start_date": start_date,
            "end_date": end_date,
            "hourly": hourly_vars,
            "timezone": timezone_str,
        }
        return f"{self.api_url}?{urllib.parse.urlencode(params)}"

    def parse_provider_response(
        self,
        raw_response: dict[str, Any],
        location: str,
        latitude: float,
        longitude: float,
        requested_variables: list[str],
        source: str = "OPENMETEO_ARCHIVE",
    ) -> list[CanonicalHistoricalRecord]:
        """Parse raw provider JSON into standardized CanonicalHistoricalRecord items."""
        records: list[CanonicalHistoricalRecord] = []
        hourly = raw_response.get("hourly", {})
        times = hourly.get("time", [])

        if not times:
            return []

        for i, time_str in enumerate(times):
            try:
                valid_dt = datetime.fromisoformat(time_str)
                valid_time_iso = valid_dt.isoformat() + "Z"
            except Exception:
                valid_time_iso = time_str

            for var_name in requested_variables:
                canon_var = VARIABLE_CANONICAL_NAMES.get(var_name, var_name)
                canon_unit = VARIABLE_CANONICAL_UNITS.get(canon_var, "unknown")

                # The provider response may contain the raw var name or canonical name
                val_raw = None
                if canon_var in hourly:
                    vals = hourly[canon_var]
                    if i < len(vals):
                        val_raw = vals[i]
                elif var_name in hourly:
                    vals = hourly[var_name]
                    if i < len(vals):
                        val_raw = vals[i]

                if val_raw is not None:
                    try:
                        val_float = float(val_raw)
                        rec = CanonicalHistoricalRecord.create(
                            location=location,
                            latitude=latitude,
                            longitude=longitude,
                            valid_time=valid_time_iso,
                            variable=canon_var,
                            unit=canon_unit,
                            value=val_float,
                            source=source,
                            record_type="OBSERVATION",
                            is_ground_truth_label=True,
                        )
                        records.append(rec)
                    except (ValueError, TypeError):
                        continue

        return records

    def collect(self, request: HistoricalDataRequest) -> HistoricalCollectionResult:
        """Collect, deduplicate, validate, and return canonical historical records."""
        # 1. Resolve location dynamically using Day 8 Location Service
        resolved = self.location_service.resolve(request.location)
        if resolved is None:
            logger.warning("Historical collection rejected: unresolvable location '%s'", request.location)
            return HistoricalCollectionResult(
                is_success=False,
                location=request.location,
                start_date=request.start_date,
                end_date=request.end_date,
                records=[],
                total_records=0,
                duplicates_removed=0,
                qc_passed=False,
                qc_violations=["Unresolvable or invalid location"],
                error_message="INVALID_LOCATION",
                source=request.source,
            )

        latitude = resolved.latitude
        longitude = resolved.longitude

        # 2. Coordinate boundary safety check
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            return HistoricalCollectionResult(
                is_success=False,
                location=request.location,
                latitude=latitude,
                longitude=longitude,
                start_date=request.start_date,
                end_date=request.end_date,
                records=[],
                total_records=0,
                duplicates_removed=0,
                qc_passed=False,
                qc_violations=["Coordinates out of geographical bounds"],
                error_message="INVALID_COORDINATES",
                source=request.source,
            )

        # 3. Construct URL & query provider
        url = self.build_query_url(
            latitude=latitude,
            longitude=longitude,
            start_date=request.start_date,
            end_date=request.end_date,
            variables=request.variables,
            timezone_str=request.timezone,
        )

        try:
            raw_data = self.http_client(url)
            if not isinstance(raw_data, dict):
                return HistoricalCollectionResult(
                    is_success=False,
                    location=request.location,
                    latitude=latitude,
                    longitude=longitude,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    records=[],
                    total_records=0,
                    duplicates_removed=0,
                    qc_passed=False,
                    qc_violations=["Provider returned non-dictionary JSON payload"],
                    error_message="MALFORMED_PROVIDER_RESPONSE",
                    source=request.source,
                )
        except Exception as exc:
            logger.error("Historical collection provider failed for '%s': %s", request.location, exc)
            return HistoricalCollectionResult(
                is_success=False,
                location=request.location,
                latitude=latitude,
                longitude=longitude,
                start_date=request.start_date,
                end_date=request.end_date,
                records=[],
                total_records=0,
                duplicates_removed=0,
                qc_passed=False,
                qc_violations=[f"Provider error: {str(exc)}"],
                error_message="PROVIDER_ERROR",
                source=request.source,
            )

        # 4. Standardize raw records
        raw_records = self.parse_provider_response(
            raw_response=raw_data,
            location=resolved.name or request.location,
            latitude=latitude,
            longitude=longitude,
            requested_variables=request.variables,
            source=request.source,
        )

        # 5. Deterministic Deduplication
        deduped_records, duplicates_count = self.deduplicator.deduplicate(raw_records)

        # 6. Quality Control Evaluation
        qc_res = self.qc.validate_records(deduped_records)

        return HistoricalCollectionResult(
            is_success=qc_res.passed,
            location=resolved.name or request.location,
            latitude=latitude,
            longitude=longitude,
            start_date=request.start_date,
            end_date=request.end_date,
            records=deduped_records,
            total_records=len(deduped_records),
            duplicates_removed=duplicates_count,
            qc_passed=qc_res.passed,
            qc_violations=qc_res.violations,
            error_message=None if qc_res.passed else "QC_FAILED",
            source=request.source,
            metadata={
                "location_source": resolved.source,
                "country": resolved.country,
                "raw_count_before_dedup": len(raw_records),
            },
        )

    # -------------------------------------------------------------------------
    # Builder 2 Dataset Interface & Serialization Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def export_to_jsonl(records: list[CanonicalHistoricalRecord], filepath: str) -> int:
        """Export canonical historical records to JSON Lines format."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        count = 0
        with open(filepath, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(rec.model_dump_json() + "\n")
                count += 1
        return count

    @staticmethod
    def load_from_jsonl(filepath: str) -> list[CanonicalHistoricalRecord]:
        """Load canonical historical records from JSON Lines format."""
        records: list[CanonicalHistoricalRecord] = []
        if not os.path.exists(filepath):
            return records
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(CanonicalHistoricalRecord.model_validate_json(line.strip()))
        return records

    @staticmethod
    def to_reference_records(
        records: list[CanonicalHistoricalRecord],
    ) -> list[ReferenceWeatherRecord]:
        """Convert CanonicalHistoricalRecords to ReferenceWeatherRecords for alignment pipeline."""
        ref_records: list[ReferenceWeatherRecord] = []
        for r in records:
            ref_records.append(
                ReferenceWeatherRecord(
                    location=r.location,
                    latitude=r.latitude,
                    longitude=r.longitude,
                    variable=r.variable,
                    unit=r.unit,
                    valid_time=r.valid_time,
                    observed_value=r.value,
                    source=r.source,
                    is_ground_truth_label=True,
                    quality_flags=r.quality_flags,
                )
            )
        return ref_records

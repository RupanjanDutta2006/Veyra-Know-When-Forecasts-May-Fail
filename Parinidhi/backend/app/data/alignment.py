"""Historical Alignment and Forecast Error Engine.

Aligns historical medium-range forecast records with reference/observed weather records,
handles explicit unit conversions, computes scalar/absolute forecast errors, and preserves
all temporal coordinates (issue_time, valid_time, lead_hours).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from backend.app.data.unit_conversion import UnitConverter, UnitMismatchError
from backend.app.schemas.reference import ReferenceWeatherRecord
from backend.app.schemas.weather import CanonicalForecastRecord


@dataclass
class AlignedVerificationRecord:
    """Standardized paired observation representing forecast vs reference truth."""

    location: str
    latitude: float
    longitude: float
    variable: str
    unit: str  # Standard canonical unit

    issue_time: str
    valid_time: str
    lead_hours: int

    forecast_value: float
    reference_value: float  # Converted to canonical unit if needed
    original_reference_value: float
    original_reference_unit: str

    forecast_error: float = 0.0  # forecast_value - reference_value
    absolute_error: float = 0.0  # abs(forecast_error)

    forecast_source: str = "NOAA_GEFS_OPENMETEO"
    reference_source: str = "ERA5_REANALYSIS"

    is_aligned: bool = True
    alignment_status: str = "SUCCESS"
    is_ground_truth_label: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class HistoricalAlignmentEngine:
    """Rigorous aligner matching forecast records to ground-truth reference records."""

    def __init__(self, spatial_tolerance_deg: float = 0.5):
        self.spatial_tolerance_deg = spatial_tolerance_deg
        self.unit_converter = UnitConverter()

    @staticmethod
    def _normalize_iso_time(iso_str: str) -> str:
        """Normalize ISO timestamp to comparable UTC format."""
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.isoformat()

    def align_single(
        self,
        forecast: CanonicalForecastRecord,
        reference: ReferenceWeatherRecord,
    ) -> Optional[AlignedVerificationRecord]:
        """Align a single forecast record with a single reference record."""
        # 1. Variable check
        if forecast.variable.lower() != reference.variable.lower():
            return None

        # 2. Spatial check
        lat_diff = abs(forecast.latitude - reference.latitude)
        lon_diff = abs(forecast.longitude - reference.longitude)
        if lat_diff > self.spatial_tolerance_deg or lon_diff > self.spatial_tolerance_deg:
            return None

        # 3. Valid time match
        try:
            fc_valid = self._normalize_iso_time(forecast.valid_time)
            ref_valid = self._normalize_iso_time(reference.valid_time)
            if fc_valid != ref_valid:
                return None
        except Exception:
            return None

        # 4. Anti-Leakage Temporal Invariant Check
        # A forecast cannot verify against a reference timestamp before its issue cycle
        try:
            fc_issue = datetime.fromisoformat(forecast.issue_time.replace("Z", "+00:00"))
            ref_dt = datetime.fromisoformat(reference.valid_time.replace("Z", "+00:00"))
            if ref_dt < fc_issue:
                # Violation: reference observation is dated in the past relative to forecast issuance
                return None
        except Exception:
            return None

        # 5. Forecast value check
        val_forecast = forecast.value if forecast.value is not None else forecast.ensemble_mean
        if val_forecast is None:
            return None

        # 6. Unit Conversion & Error Calculation
        try:
            ref_val_converted = self.unit_converter.convert(
                reference.observed_value,
                reference.unit,
                forecast.unit,
            )
            alignment_status = "SUCCESS" if reference.unit.lower() == forecast.unit.lower() else "UNIT_CONVERTED"
        except UnitMismatchError:
            return None

        fc_error = round(val_forecast - ref_val_converted, 4)
        abs_error = round(abs(fc_error), 4)

        return AlignedVerificationRecord(
            location=forecast.location,
            latitude=forecast.latitude,
            longitude=forecast.longitude,
            variable=forecast.variable,
            unit=forecast.unit,
            issue_time=forecast.issue_time,
            valid_time=forecast.valid_time,
            lead_hours=forecast.lead_hours,
            forecast_value=val_forecast,
            reference_value=ref_val_converted,
            original_reference_value=reference.observed_value,
            original_reference_unit=reference.unit,
            forecast_error=fc_error,
            absolute_error=abs_error,
            forecast_source=forecast.source,
            reference_source=reference.source,
            is_aligned=True,
            alignment_status=alignment_status,
            is_ground_truth_label=True,
        )
    def align_datasets(
        self,
        forecast_records: list[CanonicalForecastRecord],
        reference_records: list[ReferenceWeatherRecord],
    ) -> list[AlignedVerificationRecord]:
        """Bulk-align forecasts with references without cross-location collisions."""

        # Reference identity MUST include location and coordinates.
        ref_index: dict[
            tuple[str, str, str, float, float],
            ReferenceWeatherRecord,
        ] = {}

        for ref in reference_records:
            try:
                norm_time = self._normalize_iso_time(ref.valid_time)

                key = (
                    ref.location.strip().lower(),
                    ref.variable.lower(),
                    norm_time,
                    round(ref.latitude, 4),
                    round(ref.longitude, 4),
                )

                ref_index[key] = ref

            except Exception:
                continue

        aligned_records: list[AlignedVerificationRecord] = []

        for fc in forecast_records:
            try:
                norm_time = self._normalize_iso_time(fc.valid_time)

                # Prefer the actual provider grid coordinates when available.
                match_lat = (
                    fc.grid_latitude
                    if fc.grid_latitude is not None
                    else fc.latitude
                )
                match_lon = (
                    fc.grid_longitude
                    if fc.grid_longitude is not None
                    else fc.longitude
                )

                key = (
                    fc.location.strip().lower(),
                    fc.variable.lower(),
                    norm_time,
                    round(match_lat, 4),
                    round(match_lon, 4),
                )

                ref = ref_index.get(key)

                # Backward-compatible fallback for references that use
                # requested coordinates instead of provider grid coordinates.
                if ref is None:
                    fallback_key = (
                        fc.location.strip().lower(),
                        fc.variable.lower(),
                        norm_time,
                        round(fc.latitude, 4),
                        round(fc.longitude, 4),
                    )
                    ref = ref_index.get(fallback_key)

                if ref is None:
                    continue

                aligned = self.align_single(fc, ref)

                if aligned is not None:
                    aligned_records.append(aligned)

            except Exception:
                continue

        return aligned_records

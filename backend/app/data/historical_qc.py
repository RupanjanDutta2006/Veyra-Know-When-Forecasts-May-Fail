"""Historical Quality Control (QC) & Deterministic Deduplication Engine.

Provides rigorous meteorological boundary checks, timestamp validation,
and deterministic duplicate elimination for historical weather records.
"""
import math
from datetime import datetime
from typing import Any, Optional
from backend.app.data.qc import PHYSICAL_BOUNDS, QualityControlResult
from backend.app.schemas.historical import CanonicalHistoricalRecord
from backend.app.schemas.prediction import ReasonCode


class HistoricalDeduplicator:
    """Deterministic deduplication engine for historical weather records.

    Eliminates identical duplicate records while strictly preserving
    legitimate distinct forecasts and observations across time steps and variables.
    """

    @staticmethod
    def _compute_dedup_key(record: CanonicalHistoricalRecord) -> tuple[str, float, float, str, str, str, str, Optional[int]]:
        """Construct deterministic identification tuple for deduplication."""
        return (
            record.location.strip().lower(),
            round(record.latitude, 4),
            round(record.longitude, 4),
            record.valid_time,
            record.variable.strip().lower(),
            record.source.strip().upper(),
            record.record_type.strip().upper(),
            record.lead_hours,
        )

    def deduplicate(
        self, records: list[CanonicalHistoricalRecord]
    ) -> tuple[list[CanonicalHistoricalRecord], int]:
        """Deduplicate records deterministically.

        Returns:
            tuple of (deduplicated_records_list, duplicates_removed_count)
        """
        seen_keys: set[tuple[str, float, float, str, str, str, str, Optional[int]]] = set()
        deduped: list[CanonicalHistoricalRecord] = []
        duplicates_count = 0

        for record in records:
            key = self._compute_dedup_key(record)
            if key in seen_keys:
                duplicates_count += 1
                continue
            seen_keys.add(key)
            deduped.append(record)

        return deduped, duplicates_count


class HistoricalQualityControl:
    """Quality Control and Validation Engine for Historical Weather Datasets."""

    def __init__(self, physical_bounds: Optional[dict[str, tuple[float, float, str]]] = None):
        self.physical_bounds = physical_bounds or PHYSICAL_BOUNDS

    def validate_records(
        self, records: list[CanonicalHistoricalRecord]
    ) -> QualityControlResult:
        """Run validation and physical limit checks on historical records."""
        if not records:
            return QualityControlResult(
                passed=False,
                flags={"empty_dataset": True, "qc_passed": False},
                violations=["Historical dataset contains zero records"],
                reason_code=ReasonCode.DATA_UNAVAILABLE,
            )

        violations: list[str] = []
        flags: dict[str, bool] = {
            "qc_passed": True,
            "has_missing_values": False,
            "has_invalid_coordinates": False,
            "has_invalid_timestamps": False,
            "has_inconsistent_units": False,
            "has_out_of_bounds": False,
            "has_non_finite_values": False,
        }

        for idx, rec in enumerate(records):
            # 1. Required fields
            if not rec.location or not rec.valid_time or not rec.variable or not rec.unit:
                flags["has_missing_values"] = True
                violations.append(f"Record #{idx} has missing critical identification fields")

            # 2. Coordinates validity
            if not (-90.0 <= rec.latitude <= 90.0) or not (-180.0 <= rec.longitude <= 180.0):
                flags["has_invalid_coordinates"] = True
                violations.append(
                    f"Record #{idx} has invalid coordinates: ({rec.latitude}, {rec.longitude})"
                )

            # 3. Timestamp validity
            try:
                datetime.fromisoformat(rec.valid_time.replace("Z", "+00:00"))
            except ValueError as err:
                flags["has_invalid_timestamps"] = True
                violations.append(f"Record #{idx} has invalid ISO timestamp '{rec.valid_time}': {err}")

            # 4. Numeric validity & finite check
            if rec.value is None or not math.isfinite(rec.value):
                flags["has_non_finite_values"] = True
                violations.append(f"Record #{idx} has non-finite value: {rec.value}")
                continue

            # 5. Physical bounds & unit consistency
            var_name = rec.variable
            if var_name in self.physical_bounds:
                min_val, max_val, expected_unit = self.physical_bounds[var_name]

                if rec.unit.lower() != expected_unit.lower():
                    flags["has_inconsistent_units"] = True
                    violations.append(
                        f"Record #{idx} unit mismatch for {var_name}: expected '{expected_unit}', got '{rec.unit}'"
                    )

                if not (min_val <= rec.value <= max_val):
                    flags["has_out_of_bounds"] = True
                    violations.append(
                        f"Record #{idx} {var_name} value {rec.value} exceeds physical limits [{min_val}, {max_val}] {expected_unit}"
                    )

        passed = (
            not flags["has_missing_values"]
            and not flags["has_invalid_coordinates"]
            and not flags["has_invalid_timestamps"]
            and not flags["has_inconsistent_units"]
            and not flags["has_out_of_bounds"]
            and not flags["has_non_finite_values"]
        )

        flags["qc_passed"] = passed
        reason_code = ReasonCode.SUCCESS if passed else ReasonCode.QC_FAILED

        return QualityControlResult(
            passed=passed,
            flags=flags,
            violations=violations,
            reason_code=reason_code,
            metadata={"record_count": len(records), "violation_count": len(violations)},
        )

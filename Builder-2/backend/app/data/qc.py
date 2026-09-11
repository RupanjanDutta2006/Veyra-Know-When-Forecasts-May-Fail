"""Quality Control (QC) & Validation Engine for Weather Forecast Data."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from backend.app.schemas.prediction import ReasonCode
from backend.app.schemas.weather import CanonicalForecastRecord


@dataclass
class QualityControlResult:
    """Structured output from QC evaluation of forecast records."""

    passed: bool
    flags: dict[str, bool] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)
    reason_code: Optional[ReasonCode] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Physical bounds dictionary for meteorological parameters
PHYSICAL_BOUNDS: dict[str, tuple[float, float, str]] = {
    "temperature_2m": (-90.0, 60.0, "celsius"),
    "surface_pressure": (800.0, 1100.0, "hPa"),
    "wind_speed_10m": (0.0, 150.0, "m/s"),
    "relative_humidity_2m": (0.0, 100.0, "%"),
    "precipitation": (0.0, 1000.0, "mm"),
    "geopotential_height_500hPa": (4500.0, 6200.0, "m"),
}


class ForecastQualityControl:
    """Rigorous scientific QC validator for medium-range forecast data."""

    def __init__(
        self,
        min_ensemble_members: int = 1,
        max_stale_hours: int = 48,
    ):
        self.min_ensemble_members = min_ensemble_members
        self.max_stale_hours = max_stale_hours

    def validate_records(
        self, records: list[CanonicalForecastRecord]
    ) -> QualityControlResult:
        """Run comprehensive QC checks on a collection of forecast records.

        Never invents or interpolates replacement values upon failure.
        """
        if not records:
            return QualityControlResult(
                passed=False,
                flags={"empty_dataset": True, "qc_passed": False},
                violations=["Dataset contains zero forecast records"],
                reason_code=ReasonCode.DATA_UNAVAILABLE,
            )

        violations: list[str] = []
        flags: dict[str, bool] = {
            "qc_passed": True,
            "has_missing_values": False,
            "has_duplicates": False,
            "has_invalid_timestamps": False,
            "has_invalid_lead_times": False,
            "has_inconsistent_units": False,
            "has_missing_members": False,
            "has_out_of_bounds": False,
            "is_stale": False,
        }

        seen_keys: set[tuple[str, str, str]] = set()

        for idx, rec in enumerate(records):
            # 1. Check required fields & null values
            if not rec.location or not rec.issue_time or not rec.valid_time:
                flags["has_missing_values"] = True
                violations.append(f"Record #{idx} has missing critical identification fields")

            # 2. Check for duplicate variable timestamps
            key = (rec.valid_time, rec.variable, rec.member_id or "default")
            if key in seen_keys:
                flags["has_duplicates"] = True
                violations.append(f"Duplicate timestamp record detected: {key}")
            seen_keys.add(key)

            # 3. Check timestamp validity & chronological consistency
            try:
                issue_dt = datetime.fromisoformat(rec.issue_time.replace("Z", "+00:00"))
                valid_dt = datetime.fromisoformat(rec.valid_time.replace("Z", "+00:00"))
            except ValueError as err:
                flags["has_invalid_timestamps"] = True
                violations.append(f"Record #{idx} has unparseable ISO timestamp: {err}")
                continue

            # 4. Check lead hours calculation
            diff_hours = int((valid_dt - issue_dt).total_seconds() / 3600)
            if rec.lead_hours < 0 or diff_hours < 0:
                flags["has_invalid_lead_times"] = True
                violations.append(f"Record #{idx} has negative lead time: {rec.lead_hours}h")
            elif rec.lead_hours != diff_hours:
                flags["has_invalid_lead_times"] = True
                violations.append(
                    f"Record #{idx} lead_hours mismatch: record states {rec.lead_hours}h but (valid - issue) is {diff_hours}h"
                )

            # 5. Check physical range bounds and unit consistency
            var_name = rec.variable
            if var_name in PHYSICAL_BOUNDS:
                min_val, max_val, expected_unit = PHYSICAL_BOUNDS[var_name]

                # Check unit
                if rec.unit.lower() != expected_unit.lower():
                    flags["has_inconsistent_units"] = True
                    violations.append(
                        f"Record #{idx} unit mismatch for {var_name}: expected '{expected_unit}', got '{rec.unit}'"
                    )

                # Check deterministic / mean value
                val_to_check = rec.value if rec.value is not None else rec.ensemble_mean
                if val_to_check is not None:
                    if not (min_val <= val_to_check <= max_val):
                        flags["has_out_of_bounds"] = True
                        violations.append(
                            f"Record #{idx} {var_name} value {val_to_check} exceeds physical limits [{min_val}, {max_val}] {expected_unit}"
                        )

                # Check ensemble bounds if provided
                if rec.ensemble_min is not None and rec.ensemble_max is not None:
                    if rec.ensemble_min > rec.ensemble_max:
                        flags["has_out_of_bounds"] = True
                        violations.append(
                            f"Record #{idx} ensemble_min ({rec.ensemble_min}) > ensemble_max ({rec.ensemble_max})"
                        )

            # 6. Check ensemble member count
            if rec.member_count is not None and rec.member_count < self.min_ensemble_members:
                flags["has_missing_members"] = True
                violations.append(
                    f"Record #{idx} member count {rec.member_count} is below threshold {self.min_ensemble_members}"
                )

        # Determine overall pass status
        passed = (
            not flags["has_missing_values"]
            and not flags["has_duplicates"]
            and not flags["has_invalid_timestamps"]
            and not flags["has_invalid_lead_times"]
            and not flags["has_inconsistent_units"]
            and not flags["has_missing_members"]
            and not flags["has_out_of_bounds"]
        )

        flags["qc_passed"] = passed
        reason_code = ReasonCode.SUCCESS if passed else ReasonCode.QC_FAILED

        return QualityControlResult(
            passed=passed,
            flags=flags,
            violations=violations,
            reason_code=reason_code,
            metadata={"record_count": len(records), "unique_timestamps": len(seen_keys)},
        )

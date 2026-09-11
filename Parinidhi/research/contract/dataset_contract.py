"""
Veyra Research — Dataset-Ready Benchmark Contract
Defines the authoritative schema, dimensions, splits, and physical constraints
for the 1,040-cycle NOAA GEFSv12 reforecast dataset (2000-2019).

SCIENTIFIC CONSTRAINTS:
- Total Cycles: 1,040 weekly cycles (2000-2019)
- Canonical Stations: 25 representative Indian meteorological stations
- Variables: temperature_2m, surface_pressure, wind_speed_10m
- Forecast Leads: +24h, +48h, +72h, +96h, +120h, +144h, +168h, +192h, +216h, +240h (10 leads)
- Total Expected Rows: 1,040 * 25 * 3 * 10 = 780,000 rows
- Split Partitions:
    TRAIN: 730 cycles
    VALIDATION: 155 cycles
    TEST: 155 cycles
- Ground Truth Reference: ECMWF ERA5 reanalysis verification/reference (NOT station ground truth).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Set
import numpy as np
import pandas as pd


# 25 Canonical Stations
CANONICAL_STATIONS: List[str] = [
    "delhi", "srinagar", "chandigarh", "jaipur", "lucknow", "shimla", "dehradun", "leh",
    "mumbai", "pune", "ahmedabad", "goa",
    "kolkata", "bhubaneswar", "ranchi", "guwahati",
    "bengaluru", "chennai", "hyderabad", "kochi", "visakhapatnam", "thiruvananthapuram",
    "bhopal", "nagpur", "raipur"
]

CANONICAL_VARIABLES: List[str] = [
    "temperature_2m",
    "surface_pressure",
    "wind_speed_10m"
]

CANONICAL_LEADS: List[int] = [
    24, 48, 72, 96, 120, 144, 168, 192, 216, 240
]

CANONICAL_VARIABLE_UNITS: Dict[str, str] = {
    "temperature_2m": "K",
    "surface_pressure": "Pa",
    "wind_speed_10m": "m/s"
}

# Physical Domain Valid Ranges (Strict Bounds)
PHYSICAL_VALUE_BOUNDS: Dict[str, Tuple[float, float]] = {
    "temperature_2m": (180.0, 340.0),        # 180K (-93C) to 340K (+67C)
    "surface_pressure": (50000.0, 110000.0), # 500 hPa (high altitude) to 1100 hPa (dead sea)
    "wind_speed_10m": (0.0, 120.0),          # 0 to 120 m/s (Category 5 hurricane max gusts)
}

EXPECTED_CYCLE_COUNT: int = 1040
EXPECTED_TRAIN_CYCLES: int = 730
EXPECTED_VAL_CYCLES: int = 155
EXPECTED_TEST_CYCLES: int = 155
EXPECTED_TOTAL_ROWS: int = 780000


class DatasetDimensions:
    """Canonical dimensions for the 1,040-cycle historical dataset."""
    EXPECTED_CYCLES: int = 1040
    EXPECTED_STATIONS: int = 25
    EXPECTED_VARIABLES: int = 3
    EXPECTED_LEADS: int = 10
    EXPECTED_TOTAL_ROWS: int = 780000
    TRAIN_CYCLES: int = 730
    VAL_CYCLES: int = 155
    TEST_CYCLES: int = 155


class DatasetContract:
    """Contract specification and validation rules."""
    ERA5_PROVENANCE_DESCRIPTION: str = "ECMWF ERA5 reanalysis verification/reference (not station ground truth)"
    PHYSICAL_BOUNDS: Dict[str, Tuple[float, float]] = PHYSICAL_VALUE_BOUNDS

    @classmethod
    def is_physically_valid(cls, variable: str, value: float) -> bool:
        if variable not in cls.PHYSICAL_BOUNDS:
            return True
        low, high = cls.PHYSICAL_BOUNDS[variable]
        return low <= value <= high


REQUIRED_DATASET_COLUMNS: List[str] = [
    "cycle_idx",
    "issue_time_utc",
    "valid_time_utc",
    "lead_hours",
    "location_id",
    "variable",
    "unit",
    "ensemble_mean",
    "ensemble_std",
    "ensemble_p10",
    "ensemble_p90",
    "member_count",
    "truth_value",
    "forecast_abs_error",
    "bust_label",
    "split_partition",
    "truth_source"
]


@dataclass
class DatasetContractValidationResult:
    """Structured validation report against the Dataset Contract."""
    is_valid: bool
    total_rows: int
    cycle_count: int
    station_count: int
    variable_count: int
    lead_count: int
    split_counts: Dict[str, int]
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_rows": self.total_rows,
            "cycle_count": self.cycle_count,
            "station_count": self.station_count,
            "variable_count": self.variable_count,
            "lead_count": self.lead_count,
            "split_counts": self.split_counts,
            "violations": self.violations,
            "warnings": self.warnings,
            "summary": self.summary
        }


def validate_dataset_contract(df: pd.DataFrame, strict_full_size: bool = True) -> DatasetContractValidationResult:
    """
    Validates a dataset DataFrame strictly against the Veyra Dataset Contract.

    Args:
        df: DataFrame loaded from Parquet / Drive extraction.
        strict_full_size: If True, asserts full 780,000 rows (for complete benchmark).
                          If False, validates schema, ranges, and consistency for subsets/dry-runs.

    Returns:
        DatasetContractValidationResult
    """
    violations: List[str] = []
    warnings: List[str] = []

    if df.empty:
        return DatasetContractValidationResult(
            is_valid=False,
            total_rows=0,
            cycle_count=0,
            station_count=0,
            variable_count=0,
            lead_count=0,
            split_counts={},
            violations=["Dataset is empty."],
            summary="FAIL: Empty DataFrame provided."
        )

    # 1. Required Columns Check
    missing_cols = [c for c in REQUIRED_DATASET_COLUMNS if c not in df.columns]
    if missing_cols:
        violations.append(f"Missing required columns: {missing_cols}")

    # 2. Dimensions and Granularities
    cycles = df["cycle_idx"].nunique() if "cycle_idx" in df.columns else 0
    stations = df["location_id"].nunique() if "location_id" in df.columns else 0
    variables = df["variable"].nunique() if "variable" in df.columns else 0
    leads = df["lead_hours"].nunique() if "lead_hours" in df.columns else 0
    total_rows = len(df)

    if strict_full_size:
        if total_rows != EXPECTED_TOTAL_ROWS:
            violations.append(f"Row count mismatch: expected {EXPECTED_TOTAL_ROWS}, found {total_rows}")
        if cycles != EXPECTED_CYCLE_COUNT:
            violations.append(f"Cycle count mismatch: expected {EXPECTED_CYCLE_COUNT}, found {cycles}")
        if stations != len(CANONICAL_STATIONS):
            violations.append(f"Station count mismatch: expected {len(CANONICAL_STATIONS)}, found {stations}")
        if variables != len(CANONICAL_VARIABLES):
            violations.append(f"Variable count mismatch: expected {len(CANONICAL_VARIABLES)}, found {variables}")
        if leads != len(CANONICAL_LEADS):
            violations.append(f"Lead count mismatch: expected {len(CANONICAL_LEADS)}, found {leads}")

    # 3. Canonical Set Memberships
    if "location_id" in df.columns:
        invalid_locs = set(df["location_id"].unique()) - set(CANONICAL_STATIONS)
        if invalid_locs:
            violations.append(f"Found non-canonical location IDs: {sorted(list(invalid_locs))}")

    if "variable" in df.columns:
        invalid_vars = set(df["variable"].unique()) - set(CANONICAL_VARIABLES)
        if invalid_vars:
            violations.append(f"Found non-canonical variables: {sorted(list(invalid_vars))}")

    if "lead_hours" in df.columns:
        invalid_leads = set(df["lead_hours"].unique()) - set(CANONICAL_LEADS)
        if invalid_leads:
            violations.append(f"Found non-canonical lead hours: {sorted(list(invalid_leads))}")

    # 4. Split Partition Integrity
    split_counts: Dict[str, int] = {}
    if "split_partition" in df.columns:
        split_counts = df["split_partition"].value_counts().to_dict()
        invalid_splits = set(df["split_partition"].unique()) - {"train", "val", "test"}
        if invalid_splits:
            violations.append(f"Invalid split partition tags: {invalid_splits}")

        if strict_full_size:
            train_cycles = df[df["split_partition"] == "train"]["cycle_idx"].nunique()
            val_cycles = df[df["split_partition"] == "val"]["cycle_idx"].nunique()
            test_cycles = df[df["split_partition"] == "test"]["cycle_idx"].nunique()
            if train_cycles != EXPECTED_TRAIN_CYCLES:
                violations.append(f"Train cycle count mismatch: expected {EXPECTED_TRAIN_CYCLES}, found {train_cycles}")
            if val_cycles != EXPECTED_VAL_CYCLES:
                violations.append(f"Validation cycle count mismatch: expected {EXPECTED_VAL_CYCLES}, found {val_cycles}")
            if test_cycles != EXPECTED_TEST_CYCLES:
                violations.append(f"Test cycle count mismatch: expected {EXPECTED_TEST_CYCLES}, found {test_cycles}")

    # 5. Missing Values & Duplicate Primary Keys
    key_cols = ["cycle_idx", "location_id", "variable", "lead_hours"]
    if all(c in df.columns for c in key_cols):
        dups = df.duplicated(subset=key_cols).sum()
        if dups > 0:
            violations.append(f"Found {dups} duplicate primary key records on ({key_cols})")

    # 6. Physical Domain Range Checks
    if "variable" in df.columns and "ensemble_mean" in df.columns:
        for var, (low, high) in PHYSICAL_VALUE_BOUNDS.items():
            sub = df[df["variable"] == var]
            if not sub.empty:
                out_of_bounds = sub[(sub["ensemble_mean"] < low) | (sub["ensemble_mean"] > high)]
                if len(out_of_bounds) > 0:
                    violations.append(
                        f"Physical range violation for {var}: {len(out_of_bounds)} rows outside [{low}, {high}]"
                    )

    # 7. Issue & Valid Time Consistency
    if "issue_time_utc" in df.columns and "valid_time_utc" in df.columns and "lead_hours" in df.columns:
        t_issue = pd.to_datetime(df["issue_time_utc"], utc=True)
        t_valid = pd.to_datetime(df["valid_time_utc"], utc=True)
        expected_diff_hours = (t_valid - t_issue).dt.total_seconds() / 3600.0
        time_mismatches = np.abs(expected_diff_hours - df["lead_hours"]) > 0.01
        if time_mismatches.sum() > 0:
            violations.append(f"Found {time_mismatches.sum()} rows where valid_time != issue_time + lead_hours")

    # 8. ERA5 Provenance Description Check
    if "truth_source" in df.columns:
        non_era5 = df[df["truth_source"] != "ECMWF_ERA5_REANALYSIS"]
        if len(non_era5) > 0:
            warnings.append(f"{len(non_era5)} rows have truth_source other than ECMWF_ERA5_REANALYSIS")

    is_valid = (len(violations) == 0)
    summary = "PASS: Dataset contract fully satisfied." if is_valid else f"FAIL: {len(violations)} contract violation(s) detected."

    return DatasetContractValidationResult(
        is_valid=is_valid,
        total_rows=total_rows,
        cycle_count=cycles,
        station_count=stations,
        variable_count=variables,
        lead_count=leads,
        split_counts=split_counts,
        violations=violations,
        warnings=warnings,
        summary=summary
    )

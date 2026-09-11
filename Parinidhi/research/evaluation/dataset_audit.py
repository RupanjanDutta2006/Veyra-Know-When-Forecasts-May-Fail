"""
Veyra Research — Dataset Integrity Auditor
Comprehensive, fail-loud auditing tool for the Phase 5B.2 1,040-cycle extraction.

SCIENTIFIC PRINCIPLE:
Never silently repair corrupted or leaked benchmark data.
Any violation of physical bounds, temporal buffers, split isolation,
or future-lead leakage raises an immediate hard failure.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Set
import json
import numpy as np
import pandas as pd

from research.contract.dataset_contract import (
    CANONICAL_STATIONS,
    CANONICAL_VARIABLES,
    CANONICAL_LEADS,
    CANONICAL_VARIABLE_UNITS,
    PHYSICAL_VALUE_BOUNDS,
    EXPECTED_TOTAL_ROWS,
    EXPECTED_CYCLE_COUNT,
    EXPECTED_TRAIN_CYCLES,
    EXPECTED_VAL_CYCLES,
    EXPECTED_TEST_CYCLES,
    validate_dataset_contract,
)


@dataclass
class IntegrityAuditReport:
    """Complete machine-readable scientific audit report."""
    audit_timestamp_utc: str
    dataset_row_count: int
    cycle_count: int
    station_count: int
    variable_count: int
    lead_count: int
    date_range_start: str
    date_range_end: str
    split_cycle_distribution: Dict[str, int]
    split_row_distribution: Dict[str, int]
    missing_value_summary: Dict[str, int]
    duplicate_key_count: int
    missing_combinations_count: int
    physical_range_violations: Dict[str, int]
    temporal_buffer_status: str
    future_lead_leakage_status: str
    era5_provenance_status: str
    split_contamination_status: str
    audit_passed: bool
    critical_errors: List[str] = field(default_factory=list)
    audit_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_json(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


class DatasetIntegrityAuditor:
    """
    Executes deep forensic integrity checks on the raw/processed historical dataset.
    """

    def __init__(self, strict_full_size: bool = True):
        self.strict_full_size = strict_full_size

    def audit(self, df: pd.DataFrame) -> IntegrityAuditReport:
        critical_errors: List[str] = []
        audit_warnings: List[str] = []

        if df.empty:
            return IntegrityAuditReport(
                audit_timestamp_utc=datetime.utcnow().isoformat(),
                dataset_row_count=0,
                cycle_count=0,
                station_count=0,
                variable_count=0,
                lead_count=0,
                date_range_start="N/A",
                date_range_end="N/A",
                split_cycle_distribution={},
                split_row_distribution={},
                missing_value_summary={},
                duplicate_key_count=0,
                missing_combinations_count=0,
                physical_range_violations={},
                temporal_buffer_status="FAIL",
                future_lead_leakage_status="FAIL",
                era5_provenance_status="FAIL",
                split_contamination_status="FAIL",
                audit_passed=False,
                critical_errors=["Dataset DataFrame is completely empty."],
                audit_warnings=[]
            )

        # 1. Base Contract Validation
        contract_res = validate_dataset_contract(df, strict_full_size=self.strict_full_size)
        if not contract_res.is_valid:
            critical_errors.extend(contract_res.violations)
        audit_warnings.extend(contract_res.warnings)

        # 2. Dimensions & Date Range
        total_rows = len(df)
        cycles = df["cycle_idx"].nunique() if "cycle_idx" in df.columns else 0
        stations = df["location_id"].nunique() if "location_id" in df.columns else 0
        vars_count = df["variable"].nunique() if "variable" in df.columns else 0
        leads_count = df["lead_hours"].nunique() if "lead_hours" in df.columns else 0

        date_start = "N/A"
        date_end = "N/A"
        if "issue_time_utc" in df.columns:
            t_issue = pd.to_datetime(df["issue_time_utc"], utc=True)
            date_start = str(t_issue.min())
            date_end = str(t_issue.max())

        # 3. Missing Value Summary
        missing_summary: Dict[str, int] = {}
        for col in df.columns:
            n_miss = int(df[col].isna().sum())
            if n_miss > 0:
                missing_summary[col] = n_miss
                critical_errors.append(f"Column '{col}' contains {n_miss} missing/NaN values.")

        # 4. Duplicate Key Checks
        key_cols = ["cycle_idx", "location_id", "variable", "lead_hours"]
        dup_count = 0
        if all(k in df.columns for k in key_cols):
            dup_count = int(df.duplicated(subset=key_cols).sum())
            if dup_count > 0:
                critical_errors.append(f"Found {dup_count} duplicate primary key tuples on {key_cols}.")

        # 5. Missing Combinations Check (Combinatorial Grid Completeness)
        missing_combos = 0
        if cycles > 0 and stations > 0 and vars_count > 0 and leads_count > 0:
            expected_combos = cycles * len(CANONICAL_STATIONS) * len(CANONICAL_VARIABLES) * len(CANONICAL_LEADS)
            if total_rows < expected_combos:
                missing_combos = expected_combos - total_rows
                if self.strict_full_size:
                    critical_errors.append(f"Missing {missing_combos} expected station-variable-lead combinations.")
                else:
                    audit_warnings.append(f"Sub-dataset missing {missing_combos} combinations relative to full grid.")

        # 6. Physical Domain Range Checks
        phys_violations: Dict[str, int] = {}
        if "variable" in df.columns and "ensemble_mean" in df.columns:
            for var, (low, high) in PHYSICAL_VALUE_BOUNDS.items():
                sub = df[df["variable"] == var]
                if not sub.empty:
                    bad = int(((sub["ensemble_mean"] < low) | (sub["ensemble_mean"] > high)).sum())
                    if bad > 0:
                        phys_violations[var] = bad
                        critical_errors.append(f"{bad} values for {var} violate physical limits [{low}, {high}].")

        # 7. Split Partitions & Temporal Isolation
        split_cycle_dist: Dict[str, int] = {}
        split_row_dist: Dict[str, int] = {}
        split_contamination_status = "PASS"
        temporal_buffer_status = "PASS"

        if "split_partition" in df.columns and "cycle_idx" in df.columns and "issue_time_utc" in df.columns:
            for sp, g in df.groupby("split_partition"):
                split_cycle_dist[str(sp)] = int(g["cycle_idx"].nunique())
                split_row_dist[str(sp)] = int(len(g))

            train_cycles = set(df[df["split_partition"] == "train"]["cycle_idx"].unique())
            val_cycles = set(df[df["split_partition"] == "val"]["cycle_idx"].unique())
            test_cycles = set(df[df["split_partition"] == "test"]["cycle_idx"].unique())

            # Contamination checks
            train_val_overlap = train_cycles.intersection(val_cycles)
            train_test_overlap = train_cycles.intersection(test_cycles)
            val_test_overlap = val_cycles.intersection(test_cycles)

            if train_val_overlap:
                split_contamination_status = "FAIL"
                critical_errors.append(f"Train/Val cycle overlap detected: {train_val_overlap}")
            if train_test_overlap:
                split_contamination_status = "FAIL"
                critical_errors.append(f"Train/Test cycle overlap detected: {train_test_overlap}")
            if val_test_overlap:
                split_contamination_status = "FAIL"
                critical_errors.append(f"Val/Test cycle overlap detected: {val_test_overlap}")

            # Temporal Buffer Verification (train max < val min and val max < test min)
            if train_cycles and val_cycles:
                max_train_t = pd.to_datetime(df[df["split_partition"] == "train"]["issue_time_utc"], utc=True).max()
                min_val_t = pd.to_datetime(df[df["split_partition"] == "val"]["issue_time_utc"], utc=True).min()
                if max_train_t >= min_val_t:
                    temporal_buffer_status = "FAIL"
                    critical_errors.append(f"Temporal buffer violation: max train issue ({max_train_t}) >= min val issue ({min_val_t})")

            if val_cycles and test_cycles:
                max_val_t = pd.to_datetime(df[df["split_partition"] == "val"]["issue_time_utc"], utc=True).max()
                min_test_t = pd.to_datetime(df[df["split_partition"] == "test"]["issue_time_utc"], utc=True).min()
                if max_val_t >= min_test_t:
                    temporal_buffer_status = "FAIL"
                    critical_errors.append(f"Temporal buffer violation: max val issue ({max_val_t}) >= min test issue ({min_test_t})")

        # 8. Future Lead Leakage Check
        future_leak_status = "PASS"
        if "issue_time_utc" in df.columns and "valid_time_utc" in df.columns:
            t_issue = pd.to_datetime(df["issue_time_utc"], utc=True)
            t_valid = pd.to_datetime(df["valid_time_utc"], utc=True)
            retro_leads = int((t_valid <= t_issue).sum())
            if retro_leads > 0:
                future_leak_status = "FAIL"
                critical_errors.append(f"Found {retro_leads} rows where valid_time <= issue_time (impossible retro-lead).")

        # 9. ERA5 Provenance Verification
        era5_status = "PASS"
        if "truth_source" in df.columns:
            sources = df["truth_source"].unique()
            if any("ERA5" not in str(s).upper() for s in sources):
                era5_status = "WARNING_NON_ERA5"
                audit_warnings.append(f"Non-ERA5 truth reference detected: {sources}")

        audit_passed = (len(critical_errors) == 0)

        return IntegrityAuditReport(
            audit_timestamp_utc=datetime.utcnow().isoformat(),
            dataset_row_count=total_rows,
            cycle_count=cycles,
            station_count=stations,
            variable_count=vars_count,
            lead_count=leads_count,
            date_range_start=date_start,
            date_range_end=date_end,
            split_cycle_distribution=split_cycle_dist,
            split_row_distribution=split_row_dist,
            missing_value_summary=missing_summary,
            duplicate_key_count=dup_count,
            missing_combinations_count=missing_combos,
            physical_range_violations=phys_violations,
            temporal_buffer_status=temporal_buffer_status,
            future_lead_leakage_status=future_leak_status,
            era5_provenance_status=era5_status,
            split_contamination_status=split_contamination_status,
            audit_passed=audit_passed,
            critical_errors=critical_errors,
            audit_warnings=audit_warnings
        )

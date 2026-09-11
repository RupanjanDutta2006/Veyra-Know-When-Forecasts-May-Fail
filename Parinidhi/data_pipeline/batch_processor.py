"""
Batch Historical Dataset Manager & Scalable Ingestion Pipeline.

Provides configuration-driven batching, coverage validation, partitioned dataset creation,
and provenance tracking for scaling historical weather datasets from benchmark locations (8)
to operational locations (20) and arbitrary coordinate lists (50, 100, 500, 1000+ locations).

Scientific Constraints & Statistical Principles:
- Distinguishes row-level sample count (e.g. 35,040 lead records) from independent forecast-run units (1,200 runs).
- Issue-time features and ground truth / verification errors remain strictly segregated.
- All datasets are validated by an 8-point QC check before partitioning.
- Deterministic dataset-content SHA-256 manifests are generated with bit-for-bit reproducibility.
- Explicitly documents seasonal coverage and statistical limitations.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd

from api.location_service import LocationInfo, LocationRegistry
from data_pipeline.historical_aligner import (
    CANONICAL_HISTORICAL_COLUMNS,
    CANONICAL_TARGET_COLUMNS,
    MultiClimateDatasetBuilder,
)


@dataclass
class DatasetCoverageReport:
    """Structured report on dataset coverage across locations, cycles, variables, runs, and dates."""
    total_records: int
    forecast_run_count: int
    records_per_run_avg: float
    unique_issue_times_count: int
    distinct_locations: int
    locations_list: List[str]
    benchmark_locations_present: List[str]
    benchmark_completeness_pct: float
    start_issue_time_utc: str
    end_issue_time_utc: str
    temporal_span_days: float
    seasonal_scope: str
    cycles_present: List[str]
    variables_present: List[str]
    lead_hours_min: int
    lead_hours_max: int
    lead_hour_count: int
    missing_cells_pct: float
    is_coverage_complete: bool
    coverage_issues: List[str] = field(default_factory=list)
    coverage_limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatasetCoverageValidator:
    """Validates structural and spatiotemporal coverage of multi-location historical datasets."""

    def __init__(self, location_registry: Optional[LocationRegistry] = None):
        self.location_registry = location_registry or LocationRegistry()

    def audit_coverage(
        self,
        df: pd.DataFrame,
        required_variables: Optional[List[str]] = None,
        required_cycles: Optional[List[str]] = None,
        min_lead_hours: int = 0,
        max_lead_hours: int = 72,
        seasonal_scope: str = "August Active Southwest Monsoon",
    ) -> DatasetCoverageReport:
        """
        Audit spatiotemporal completeness and independence structure of canonical historical DataFrame.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty.")

        req_vars = required_variables or ["temperature_2m", "surface_pressure", "wind_speed_10m"]
        req_cycles = required_cycles or ["00z", "06z", "12z", "18z"]
        issues: List[str] = []
        limitations: List[str] = []

        total_recs = len(df)
        locs_present = sorted(list(df["location_id"].str.lower().unique()))
        benchmarks_all = sorted(self.location_registry.get_benchmark_location_ids())
        benchmarks_present = sorted(list(set(locs_present).intersection(set(benchmarks_all))))
        bench_pct = round((len(benchmarks_present) / max(len(benchmarks_all), 1)) * 100.0, 1)

        issue_times = pd.to_datetime(df["issue_time_utc"], utc=True)
        start_t_dt = issue_times.min()
        end_t_dt = issue_times.max()
        start_t = start_t_dt.isoformat()
        end_t = end_t_dt.isoformat()
        span_days = round((end_t_dt - start_t_dt).total_seconds() / 86400.0, 2)

        # 1. Derive and validate canonical forecast cycles
        from data_pipeline.historical_aligner import derive_canonical_cycle
        if "cycle" in df.columns and not df["cycle"].isna().all():
            cycles_series = derive_canonical_cycle(df["issue_time_utc"], df["cycle"])
        else:
            cycles_series = derive_canonical_cycle(df["issue_time_utc"])

        # Count forecast initialization / run units: (location_id, variable, issue_time_utc, cycle)
        # Note: Lead records within the same forecast run share initial atmospheric conditions and are correlated.
        run_df = pd.DataFrame({
            "location_id": df["location_id"].astype(str).str.lower(),
            "variable": df["variable"].astype(str),
            "issue_time_utc": issue_times.dt.strftime("%Y-%m-%d %H:%M:%S%z"),
            "cycle": cycles_series,
        })
        run_ids = run_df.agg("_".join, axis=1)
        forecast_run_count = int(run_ids.nunique())

        records_per_run = round(total_recs / max(forecast_run_count, 1), 2)
        unique_issue_times = int(issue_times.nunique())

        cycles_present = sorted(list(cycles_series.dropna().unique()))
        missing_cycles = set(req_cycles) - set(cycles_present)
        if missing_cycles:
            issues.append(f"Missing required forecast cycles: {sorted(list(missing_cycles))}")

        vars_present = sorted(list(df["variable"].dropna().unique()))
        missing_vars = set(req_vars) - set(vars_present)
        if missing_vars:
            issues.append(f"Missing required meteorological variables: {sorted(list(missing_vars))}")

        lead_min = int(df["lead_hours"].min())
        lead_max = int(df["lead_hours"].max())
        lead_count = int(df["lead_hours"].nunique())
        if lead_min > min_lead_hours:
            issues.append(f"Lead hours start at {lead_min}h, expected <= {min_lead_hours}h.")
        if lead_max < max_lead_hours:
            issues.append(f"Lead hours end at {lead_max}h, expected >= {max_lead_hours}h.")

        # Missing values check
        total_cells = df.size
        missing_cells = df.isna().sum().sum()
        missing_pct = round(float(missing_cells / total_cells) * 100.0, 3)

        # Document honest scientific limitations
        if span_days < 30.0:
            limitations.append(
                f"Short temporal span ({span_days} days): Represents active monsoonal synoptic state; "
                "does not capture winter radiation fog, post-monsoon cyclone transitions, or pre-monsoon heatwaves."
            )
        if records_per_run > 1.0:
            limitations.append(
                f"Multi-lead dependence: {total_recs} lead records originate from {forecast_run_count} "
                f"independent forecast runs ({records_per_run} lead hours per run). Lead records within the same run share synoptic initial conditions."
            )

        is_complete = len(issues) == 0

        return DatasetCoverageReport(
            total_records=total_recs,
            forecast_run_count=forecast_run_count,
            records_per_run_avg=records_per_run,
            unique_issue_times_count=unique_issue_times,
            distinct_locations=len(locs_present),
            locations_list=locs_present,
            benchmark_locations_present=benchmarks_present,
            benchmark_completeness_pct=bench_pct,
            start_issue_time_utc=start_t,
            end_issue_time_utc=end_t,
            temporal_span_days=span_days,
            seasonal_scope=seasonal_scope,
            cycles_present=cycles_present,
            variables_present=vars_present,
            lead_hours_min=lead_min,
            lead_hours_max=lead_max,
            lead_hour_count=lead_count,
            missing_cells_pct=missing_pct,
            is_coverage_complete=is_complete,
            coverage_issues=issues,
            coverage_limitations=limitations,
        )


class HistoricalBatchManager:
    """
    Configuration-driven batch manager for large-scale multi-location historical datasets.
    Supports memory-safe streaming/chunked processing, partitioned dataset persistence,
    and deterministic provenance generation.
    """

    def __init__(
        self,
        output_dir: str = "data/historical",
        location_registry: Optional[LocationRegistry] = None,
        dataset_builder: Optional[MultiClimateDatasetBuilder] = None,
        coverage_validator: Optional[DatasetCoverageValidator] = None,
    ):
        self.output_dir = Path(output_dir)
        self.location_registry = location_registry or LocationRegistry()
        self.dataset_builder = dataset_builder or MultiClimateDatasetBuilder(
            historical_dir=str(self.output_dir),
            location_registry=self.location_registry,
        )
        self.coverage_validator = coverage_validator or DatasetCoverageValidator(self.location_registry)

    def process_batch(
        self,
        df_paired: pd.DataFrame,
        dataset_id: str,
        seasonal_scope: str = "August Active Southwest Monsoon",
        save_local_files: bool = True,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Standardize, validate, hash, and optionally write a multi-location historical dataset.

        Args:
            df_paired: Raw or semi-standardized paired forecast/truth DataFrame.
            dataset_id: Unique identifier for dataset.
            seasonal_scope: Descriptive tag for seasonal regime coverage.
            save_local_files: Whether to save Parquet and manifest to output_dir.

        Returns:
            Tuple of (standardized_canonical_df, dataset_manifest_dict).
        """
        # 1. Standardize into canonical 32-column schema
        std_df = self.dataset_builder.standardize_paired_slice(df_paired)

        # 2. Run 8-point QC validation
        qc_report = self.dataset_builder.validate_dataset(std_df, strict=True)

        # 3. Audit spatiotemporal coverage and run-level independence structure
        cov_report = self.coverage_validator.audit_coverage(std_df, seasonal_scope=seasonal_scope)

        # 4. Compute deterministic dataset-content SHA-256 hash
        sort_cols = [c for c in ["location_id", "variable", "issue_time_utc", "valid_time_utc"] if c in std_df.columns]
        content_cols = [
            c for c in ["location_id", "variable", "issue_time_utc", "valid_time_utc", "forecast_value", "truth_value", "forecast_error"]
            if c in std_df.columns
        ]
        df_sorted = std_df.sort_values(by=sort_cols).reset_index(drop=True)
        csv_bytes = df_sorted[content_cols].to_csv(index=False, float_format="%.4f").encode("utf-8")
        content_sha256 = hashlib.sha256(csv_bytes).hexdigest()

        # 5. Build full provenance manifest
        manifest = {
            "schema_version": "2.0.0-canonical-historical",
            "dataset_id": dataset_id,
            "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "content_sha256": content_sha256,
            "total_records": len(std_df),
            "forecast_run_count": cov_report.forecast_run_count,
            "records_per_run_avg": cov_report.records_per_run_avg,
            "unique_issue_times_count": cov_report.unique_issue_times_count,
            "column_count": len(std_df.columns),
            "canonical_columns": list(std_df.columns),
            "qc_validation": qc_report,
            "coverage_audit": cov_report.to_dict(),
        }

        # 6. Save locally if requested
        if save_local_files:
            target_dir = self.output_dir / dataset_id
            target_dir.mkdir(parents=True, exist_ok=True)

            parquet_path = target_dir / f"{dataset_id}.parquet"
            manifest_path = target_dir / f"{dataset_id}_manifest.json"

            std_df.to_parquet(parquet_path, index=False)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            manifest["storage"] = {
                "parquet_file": str(parquet_path),
                "manifest_file": str(manifest_path),
            }

        return std_df, manifest

    def create_batch_chunks(
        self,
        locations: List[Union[str, LocationInfo, Dict[str, Any]]],
        chunk_size: int = 50,
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Chunk a large location list (e.g. 50, 100, 500, 1000+ coordinates) into manageable execution batches.
        """
        if chunk_size <= 0:
            raise ValueError(f"Invalid chunk_size '{chunk_size}'. Must be a positive integer >= 1.")

        resolved_locs: List[Dict[str, Any]] = []
        for loc in locations:
            if isinstance(loc, str):
                if self.location_registry.has_location(loc):
                    info = self.location_registry.get_location(loc)
                    resolved_locs.append({
                        "location_id": info.location_id,
                        "latitude": info.requested_coordinates.latitude,
                        "longitude": info.requested_coordinates.longitude,
                        "climate_zone": info.climate_zone,
                        "meteorological_regime": info.meteorological_regime,
                    })
                else:
                    resolved_locs.append({
                        "location_id": loc,
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "climate_zone": "UNKNOWN",
                        "meteorological_regime": "UNKNOWN",
                    })
            elif isinstance(loc, LocationInfo):
                resolved_locs.append({
                    "location_id": loc.location_id,
                    "latitude": loc.requested_coordinates.latitude,
                    "longitude": loc.requested_coordinates.longitude,
                    "climate_zone": loc.climate_zone,
                    "meteorological_regime": loc.meteorological_regime,
                })
            elif isinstance(loc, dict):
                loc_id = loc.get("location_id") or loc.get("name") or "custom_loc"
                lat = float(loc.get("latitude") or loc.get("lat", 0.0))
                lon = float(loc.get("longitude") or loc.get("lon", 0.0))
                info = self.location_registry.resolve_location(loc_id, latitude=lat, longitude=lon)
                resolved_locs.append({
                    "location_id": info.location_id,
                    "latitude": info.requested_coordinates.latitude,
                    "longitude": info.requested_coordinates.longitude,
                    "climate_zone": info.climate_zone,
                    "meteorological_regime": info.meteorological_regime,
                })

        for i in range(0, len(resolved_locs), chunk_size):
            yield resolved_locs[i : i + chunk_size]

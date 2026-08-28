"""Multi-Location Platform Service for Veyra Phase 2 Day 10.

Coordinates batch location resolution, parallel/sequential historical collection,
deduplication, quality control isolation, and batch prediction workflows.
"""
import copy
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Union

from backend.app.schemas.historical import (
    CanonicalHistoricalRecord,
    HistoricalCollectionResult,
    HistoricalDataRequest,
)
from backend.app.schemas.multi_location import (
    MAX_MULTI_LOCATION_BATCH_SIZE,
    MultiLocationHistoricalItemResult,
    MultiLocationHistoricalResult,
    MultiLocationHistoricalRequest,
    MultiLocationPredictionItemResult,
    MultiLocationPredictionRequest,
    MultiLocationPredictionResult,
)
from backend.app.schemas.prediction import PredictionRequest, PredictionResponse
from backend.app.schemas.reference import ReferenceWeatherRecord
from backend.app.services.historical_service import (
    BaseHistoricalDataService,
    HistoricalDataService,
)
from backend.app.services.location_service import (
    BaseLocationService,
    DynamicLocationService,
)

logger = logging.getLogger(__name__)


class BaseMultiLocationService(ABC):
    """Abstract contract for multi-location operations in Veyra."""

    @abstractmethod
    def collect_historical(
        self, request: MultiLocationHistoricalRequest
    ) -> MultiLocationHistoricalResult:
        """Collect historical weather/reanalysis data across multiple locations."""
        pass

    @abstractmethod
    def predict_batch(
        self, request: MultiLocationPredictionRequest
    ) -> MultiLocationPredictionResult:
        """Execute forecast bust prediction across multiple locations."""
        pass


class MultiLocationService(BaseMultiLocationService):
    """Production multi-location orchestration service.

    Composes Day 8 DynamicLocationService and Day 9 HistoricalDataService,
    providing failure isolation, deduplication, deterministic result mapping,
    and Builder 2 dataset serialization bridges.
    """

    def __init__(
        self,
        historical_service: Optional[BaseHistoricalDataService] = None,
        location_service: Optional[BaseLocationService] = None,
        agent_factory: Optional[Callable[[], Any]] = None,
        max_batch_size: int = MAX_MULTI_LOCATION_BATCH_SIZE,
    ):
        self.location_service = location_service or DynamicLocationService()
        self.historical_service = historical_service or HistoricalDataService(
            location_service=self.location_service
        )
        self.agent_factory = agent_factory
        self.max_batch_size = max_batch_size

    def collect_historical(
        self, request: MultiLocationHistoricalRequest
    ) -> MultiLocationHistoricalResult:
        """Collect historical data for a batch of locations with failure isolation and deduplication."""
        start_time = time.time()
        raw_locations = request.locations
        batch_size = len(raw_locations)

        if batch_size == 0:
            raise ValueError("locations list cannot be empty")
        if batch_size > self.max_batch_size:
            raise ValueError(
                f"Batch size {batch_size} exceeds configured maximum limit of {self.max_batch_size}"
            )

        # 1. Deduplicate identical queries in the batch to avoid redundant remote provider calls
        # Map normalized key -> list of original indices: e.g. "kolkata" -> [0, 1]
        unique_queries: dict[str, list[int]] = {}
        for idx, loc_str in enumerate(raw_locations):
            norm_key = loc_str.strip().lower()
            unique_queries.setdefault(norm_key, []).append(idx)

        # 2. Process each unique location independently with isolated exception handling
        intermediate_results: dict[str, MultiLocationHistoricalItemResult] = {}
        for norm_key, indices in unique_queries.items():
            sample_raw = raw_locations[indices[0]]
            item_result = self._process_single_historical_location(
                raw_location=sample_raw,
                start_date=request.start_date,
                end_date=request.end_date,
                variables=request.variables,
                data_version=request.data_version,
                source=request.source,
                timezone_str=request.timezone,
            )
            intermediate_results[norm_key] = item_result

        # 3. Reassemble deterministic results matching input order 1:1
        ordered_results: list[MultiLocationHistoricalItemResult] = []
        all_canonical_records: list[CanonicalHistoricalRecord] = []
        successful_count = 0
        failed_count = 0

        for loc_str in raw_locations:
            norm_key = loc_str.strip().lower()
            base_result = intermediate_results[norm_key]
            # Deepcopy to ensure each item in the ordered list is an independent instance with exact raw input
            cloned_item = copy.deepcopy(base_result)
            cloned_item.input_location = loc_str
            ordered_results.append(cloned_item)

            if cloned_item.is_success:
                successful_count += 1
                all_canonical_records.extend(cloned_item.records)
            else:
                failed_count += 1

        elapsed = round(time.time() - start_time, 4)
        return MultiLocationHistoricalResult(
            is_success=successful_count > 0 or batch_size == 0,
            batch_size=batch_size,
            successful_locations=successful_count,
            failed_locations=failed_count,
            results=ordered_results,
            all_records=all_canonical_records,
            total_records=len(all_canonical_records),
            start_date=request.start_date,
            end_date=request.end_date,
            variables=request.variables,
            metadata={
                "execution_time_seconds": elapsed,
                "unique_locations_processed": len(unique_queries),
                "source": request.source,
                "data_version": request.data_version,
            },
        )

    def _process_single_historical_location(
        self,
        raw_location: str,
        start_date: str,
        end_date: str,
        variables: list[str],
        data_version: str,
        source: str,
        timezone_str: str,
    ) -> MultiLocationHistoricalItemResult:
        """Process a single historical location with strict isolation of all failure modes."""
        try:
            req = HistoricalDataRequest(
                location=raw_location,
                start_date=start_date,
                end_date=end_date,
                variables=variables,
                data_version=data_version,
                source=source,
                timezone=timezone_str,
            )
            col_result: HistoricalCollectionResult = self.historical_service.collect(req)

            if not col_result.is_success:
                detail_err = "; ".join(col_result.qc_violations) if col_result.qc_violations else (col_result.error_message or "Historical collection failed")
                return MultiLocationHistoricalItemResult(
                    input_location=raw_location,
                    is_success=False,
                    status=col_result.error_message or "FAILED",
                    resolved_name=None,
                    latitude=col_result.latitude,
                    longitude=col_result.longitude,
                    records=[],
                    total_records=0,
                    duplicates_removed=col_result.duplicates_removed,
                    qc_passed=col_result.qc_passed,
                    qc_violations=col_result.qc_violations,
                    error_message=detail_err,
                )

            # Collection succeeded
            status = "SUCCESS" if col_result.qc_passed else "QC_FAILED"
            is_success = col_result.qc_passed

            return MultiLocationHistoricalItemResult(
                input_location=raw_location,
                is_success=is_success,
                status=status,
                resolved_name=raw_location,
                latitude=col_result.latitude,
                longitude=col_result.longitude,
                records=col_result.records,
                total_records=col_result.total_records,
                duplicates_removed=col_result.duplicates_removed,
                qc_passed=col_result.qc_passed,
                qc_violations=col_result.qc_violations,
                error_message=None if is_success else "Dataset failed quality control checks",
            )

        except Exception as exc:
            logger.error("Unexpected error processing location '%s' in batch: %s", raw_location, exc)
            return MultiLocationHistoricalItemResult(
                input_location=raw_location,
                is_success=False,
                status="INTERNAL_ERROR",
                resolved_name=None,
                latitude=None,
                longitude=None,
                records=[],
                total_records=0,
                duplicates_removed=0,
                qc_passed=False,
                qc_violations=[str(exc)],
                error_message=f"Internal processing error: {str(exc)}",
            )

    def predict_batch(
        self, request: MultiLocationPredictionRequest
    ) -> MultiLocationPredictionResult:
        """Execute forecast bust prediction across multiple locations with failure isolation."""
        start_time = time.time()
        raw_locations = request.locations
        batch_size = len(raw_locations)

        if batch_size == 0:
            raise ValueError("locations list cannot be empty")
        if batch_size > self.max_batch_size:
            raise ValueError(
                f"Batch size {batch_size} exceeds configured maximum limit of {self.max_batch_size}"
            )

        # Resolve agent instance
        agent = self._get_agent()

        # Deduplicate predictions across identical locations
        unique_queries: dict[str, list[int]] = {}
        for idx, loc_str in enumerate(raw_locations):
            norm_key = loc_str.strip().lower()
            unique_queries.setdefault(norm_key, []).append(idx)

        intermediate_preds: dict[str, PredictionResponse] = {}
        for norm_key, indices in unique_queries.items():
            sample_raw = raw_locations[indices[0]]
            pred_req = PredictionRequest(
                location=sample_raw,
                target_date=request.target_date,
                variable=request.variable,
                issue_time=request.issue_time,
                valid_time=request.valid_time,
                model_type=request.model_type,
            )
            resp = agent.analyze(pred_req)
            intermediate_preds[norm_key] = resp

        # Reassemble ordered outputs matching input 1:1
        ordered_results: list[MultiLocationPredictionItemResult] = []
        confident_count = 0
        abstained_count = 0

        for loc_str in raw_locations:
            norm_key = loc_str.strip().lower()
            resp = intermediate_preds[norm_key]
            # Clone response to ensure clean per-item output with exact location query
            cloned_resp = copy.deepcopy(resp)
            cloned_resp.location = loc_str
            is_success = not cloned_resp.abstain

            if is_success:
                confident_count += 1
            else:
                abstained_count += 1

            ordered_results.append(
                MultiLocationPredictionItemResult(
                    input_location=loc_str,
                    is_success=is_success,
                    response=cloned_resp,
                )
            )

        elapsed = round(time.time() - start_time, 4)
        return MultiLocationPredictionResult(
            batch_size=batch_size,
            successful_predictions=confident_count,
            abstained_predictions=abstained_count,
            results=ordered_results,
            metadata={
                "execution_time_seconds": elapsed,
                "unique_locations_processed": len(unique_queries),
            },
        )

    def _get_agent(self) -> Any:
        """Instantiate or retrieve the ForecastBustAgent."""
        if self.agent_factory:
            return self.agent_factory()
        # Import lazily to avoid circular dependencies
        from backend.app.api.v1.endpoints.predict import create_forecast_bust_agent

        return create_forecast_bust_agent()

    @staticmethod
    def export_to_jsonl(
        data: Union[MultiLocationHistoricalResult, list[CanonicalHistoricalRecord]],
        filepath: str,
    ) -> int:
        """Export canonical records to a JSON Lines (.jsonl) file for Builder 2."""
        records: list[CanonicalHistoricalRecord] = []
        if isinstance(data, MultiLocationHistoricalResult):
            records = data.all_records
        elif isinstance(data, list):
            records = data

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        count = 0
        with open(filepath, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(rec.model_dump_json() + "\n")
                count += 1
        logger.info("Exported %d canonical historical records to %s", count, filepath)
        return count

    @staticmethod
    def load_from_jsonl(filepath: str) -> list[CanonicalHistoricalRecord]:
        """Load canonical historical records from a JSON Lines (.jsonl) file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"JSONL file not found at '{filepath}'")

        records: list[CanonicalHistoricalRecord] = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    payload = json.loads(clean_line)
                    records.append(CanonicalHistoricalRecord.model_validate(payload))
                except Exception as exc:
                    logger.warning("Failed to parse JSONL line %d in %s: %s", line_num, filepath, exc)
        logger.info("Loaded %d canonical historical records from %s", len(records), filepath)
        return records

    @staticmethod
    def to_reference_records(
        data: Union[MultiLocationHistoricalResult, list[CanonicalHistoricalRecord]],
    ) -> list[ReferenceWeatherRecord]:
        """Bridge CanonicalHistoricalRecords into ReferenceWeatherRecords for Builder 2."""
        records: list[CanonicalHistoricalRecord] = []
        if isinstance(data, MultiLocationHistoricalResult):
            records = data.all_records
        elif isinstance(data, list):
            records = data

        ref_records: list[ReferenceWeatherRecord] = []
        for rec in records:
            ref_records.append(
                ReferenceWeatherRecord(
                    location=rec.location,
                    latitude=rec.latitude,
                    longitude=rec.longitude,
                    valid_time=rec.valid_time,
                    variable=rec.variable,
                    unit=rec.unit,
                    observed_value=rec.value,
                    source=rec.source,
                    quality_flags=rec.quality_flags,
                    is_ground_truth_label=rec.is_ground_truth_label,
                )
            )
        return ref_records

# Veyra — Phase 2 / Builder 1 / Day 10

## Feature
Multi-location Platform Support

## Objective
Evolve Veyra from single-location infrastructure into a resilient, reusable multi-location platform capable of handling mixed batch queries (registered cities, dynamic places, raw coordinates, and invalid locations) with deterministic 1:1 result mapping, strict per-location failure isolation, batch deduplication, quality-control isolation, and Builder 2 dataset export bridges.

## Starting Baseline
- **Starting Branch:** `phase2/builder1-development`
- **Starting Commit:** `6faa167 docs: add navigable Veyra development overview`
- **Initial Automated Test Suite:** 142 passed in 13.70s
- **Day 8 Dynamic Location Resolution:** Verified & operational (`DynamicLocationService`)
- **Day 9 Historical Data Infrastructure:** Verified & operational (`HistoricalDataService`)
- **Active Serving Model:** `prototype-gbm-v1` (LightGBM) with Platt Sigmoid calibration

## Architecture
```text
Multiple Location Inputs (e.g., ["Kolkata", "51.5074, -0.1278", "Atlantis", "Tokyo"])
        ↓
MultiLocationHistoricalRequest / MultiLocationPredictionRequest
        ↓
Batch Size & Input Validation (1 <= N <= 50)
        ↓
Batch Deduplication (Unique key aggregation to prevent duplicate provider fetches)
        ↓
Day 8 DynamicLocationService (Resolution & coordinate boundary validation)
        ↓
Day 9 HistoricalDataService / ForecastBustAgent (Isolated execution per location)
        ↓
Per-Location Quality Control (Physical bounds, monotonicity, timestamp checks)
        ↓
Failure Isolation Guard (Invalid locations/timeouts recorded per item without batch abort)
        ↓
Deterministic Ordering Reassembly (1:1 matching original request index)
        ↓
MultiLocationHistoricalResult / MultiLocationPredictionResult
        ↓
Builder 2 Serialization Bridge (JSONL export & ReferenceWeatherRecord conversion)
```

## Multi-location Request Contract
- Schema: `MultiLocationHistoricalRequest`
  - `locations: list[str]` (Enforces $1 \le N \le 50$, non-empty whitespace-trimmed strings)
  - `start_date: str`, `end_date: str` (ISO 8601 YYYY-MM-DD format with chronological ordering)
  - `variables: list[str]` (Normalized against canonical meteorological variables)
  - `source: str = "OPENMETEO_ARCHIVE"`, `data_version: str = "gefs-openmeteo-v1.0"`, `timezone: str = "UTC"`
- Schema: `MultiLocationPredictionRequest`
  - `locations: list[str]` ($1 \le N \le 50$)
  - `target_date: Optional[str]`, `variable: Optional[str]`, `issue_time: Optional[str]`, `valid_time: Optional[str]`

## Day 8 Location Integration
- Directly reuses `DynamicLocationService` without creating redundant geocoders.
- Resolves registered cities (`"Kolkata"`, `"London"`), dynamic places (`"Siliguri"`, `"Paris"`), and direct coordinate strings (`"51.5074, -0.1278"`).
- Automatically enforces latitude $[-90.0, 90.0]$ and longitude $[-180.0, 180.0]$ boundary constraints.

## Day 9 Historical Integration
- Composes `HistoricalDataService`, `HistoricalQualityControl`, and `HistoricalDeduplicator`.
- Translates multi-location batch requests into isolated single-location historical collection queries.
- Aggregates canonical historical records (`CanonicalHistoricalRecord`) into batch-level containers.

## Mixed Location Support
- Seamlessly handles heterogeneous batches containing:
  1. Registered regional cities (e.g., `"Delhi"`, `"Kolkata"`)
  2. Dynamic global cities (e.g., `"Tokyo"`, `"Paris"`)
  3. Direct geographic coordinate pairs (e.g., `"22.5726, 88.3639"`)
  4. Unresolvable / invalid locations (e.g., `"Atlantis"`, `"999.0, 999.0"`)

## Batch Safety
- Enforces configurable maximum batch limit `MAX_MULTI_LOCATION_BATCH_SIZE = 50`.
- Rejects empty location lists (`locations: []`) with clear validation errors.
- Rejects lists exceeding 50 items before invoking external providers.

## Failure Isolation
- **Strict Per-Location Isolation:** If one location fails (e.g., unresolvable name, out-of-bounds coordinates, provider timeout, or HTTP 502), the remaining locations in the batch execute normally and return full valid data.
- Structured per-location status codes: `SUCCESS`, `INVALID_LOCATION`, `INVALID_COORDINATES`, `QC_FAILED`, `PROVIDER_ERROR`, `INTERNAL_ERROR`.
- Failed inputs are never silently dropped; they are preserved in `results` with explicit error descriptions.

## Deduplication
- Identifies duplicate location strings within a batch (e.g., `["Kolkata", "London", "Kolkata"]`).
- Executes provider requests exactly once per unique location key (`"kolkata"`), eliminating redundant network calls.
- Re-maps resolved records back to all matching input positions, preserving input cardinality and exact ordering.

## QC Isolation
- Meteorological Quality Control operates independently per location.
- If data for Location B fails QC (e.g., unphysical temperature), Location B is marked with `status="QC_FAILED"` and `is_success=False`, while Location A and Location C remain completely valid and available for downstream use.

## Provider Failure Handling
- Catches network timeouts, upstream HTTP errors, and malformed provider payloads on a per-location basis.
- Never fabricates synthetic weather data for failed locations.
- Surfaces informative error diagnostics in `error_message` and `qc_violations`.

## Builder 2 Interface
- `MultiLocationService.export_to_jsonl(result, filepath)`: Exports aggregated canonical records to JSON Lines for ML dataset engineering.
- `MultiLocationService.load_from_jsonl(filepath)`: Loads canonical records from JSON Lines.
- `MultiLocationService.to_reference_records(result)`: Converts canonical records into `ReferenceWeatherRecord` instances for verification and bust-label alignment.

## Leakage Safety
- All collected historical records maintain `is_ground_truth_label=True` and `record_type="OBSERVATION"`.
- Reference observations and historical verification values are strictly quarantined from live feature extraction pipelines.

## API Changes
- **`POST /v1/predict/batch`**: Evaluates forecast bust risk across a batch of locations simultaneously.
- **`POST /v1/historical/batch`**: Collects and normalizes historical weather records across multiple locations in a single call.
- **Backward Compatibility:** Existing `POST /v1/predict` and `GET /v1/health` endpoints remain completely unmodified.

## Files Added
- `backend/app/schemas/multi_location.py`: Request/response schemas, item result containers, and batch constraints.
- `backend/app/services/multi_location_service.py`: Multi-location orchestration service with deduplication, failure isolation, and Builder 2 bridges.
- `backend/app/api/v1/endpoints/multi_location.py`: FastAPI endpoints for batch prediction and historical collection.
- `backend/tests/test_multi_location.py`: Dedicated automated unit and integration test suite (22 tests).
- `Overview/Phase-2/Builder-1/Day-10.md`: Authoritative Day 10 technical documentation.

## Files Modified
- `backend/app/schemas/__init__.py`: Exported multi-location schemas.
- `backend/app/services/__init__.py`: Exported `BaseMultiLocationService` and `MultiLocationService`.
- `backend/app/api/v1/router.py`: Mounted `multi_location.router` under tag `Multi-Location`.
- `Overview/README.md`: Added Day 10 to Phase 2 Builder 1 development index.
- `Overview/Phase-2/Builder-1/Day-9.md`: Updated next-day navigation link to Day 10.

## Dedicated Day 10 Tests
- File: `backend/tests/test_multi_location.py`
- Dedicated Tests: 22 passed in 6.39s (0 failed, 0 errors)
  - `test_single_location_in_multi_location_request`: PASS
  - `test_multiple_valid_cities_request`: PASS
  - `test_mixed_city_and_direct_coordinates`: PASS
  - `test_empty_location_list_validation_error`: PASS
  - `test_whitespace_location_entry_validation_error`: PASS
  - `test_batch_above_maximum_limit_error`: PASS
  - `test_invalid_date_order_in_multi_location_request`: PASS
  - `test_valid_plus_invalid_location_failure_isolation`: PASS
  - `test_all_invalid_batch_handling`: PASS
  - `test_provider_failure_isolation`: PASS
  - `test_provider_timeout_isolation`: PASS
  - `test_deterministic_result_mapping_order`: PASS
  - `test_duplicate_locations_deduplication_and_mapping`: PASS
  - `test_qc_isolation_across_locations`: PASS
  - `test_reference_prediction_data_isolation`: PASS
  - `test_builder2_jsonl_export_and_load`: PASS
  - `test_builder2_to_reference_records_bridge`: PASS
  - `test_batch_prediction_execution`: PASS
  - `test_http_batch_historical_endpoint`: PASS
  - `test_http_batch_prediction_endpoint`: PASS
  - `test_http_batch_empty_locations_rejected`: PASS
  - `test_http_single_location_prediction_unaffected`: PASS

## Full Regression
- Command: `python -m pytest -q`
- Total Tests: **164 passed** in 21.28s (0 failed, 0 errors, 0 skipped)
- Baseline: 142 passed $\rightarrow$ Current: 164 passed (+22 new tests)

## Smoke Verification
- `scripts/smoke_test_weather.py`: PASS (Real GEFS weather ingestion)
- `scripts/smoke_test_historical.py`: PASS (ERA5 alignment & bust labeling)
- `scripts/smoke_test_ml.py`: PASS (ML pipeline & baseline model)
- `scripts/smoke_test_serving.py`: PASS (Live model serving)
- `scripts/smoke_test_final.py`: PASS (End-to-end 10-phase readiness)
- `scripts/smoke_test_builder2.py`: PASS (Builder 2 standalone stages A through O)

## Live Verification
- **Test Query:** Locations `["Kolkata", "London"]`, Date `2026-08-01` to `2026-08-01`, Variable `temperature_2m`
- **Provider:** Open-Meteo Archive API
- **Execution Result:**
  - Batch Size: 2
  - Successful Locations: 2 (Kolkata: 24 records, London: 24 records)
  - Total Canonical Records: 48
  - QC Status: 100% PASS (0 violations)
  - Failure Rate: 0.0%

## Known Limitations
1. **Sequential Collection by Default:** Historical provider queries for unique locations run sequentially to respect upstream rate limits.
2. **Provider Archive Latency:** Real historical archive fetches take $\sim 1.5\text{s}$ to $3\text{s}$ per unique city depending on network latency.

## Final Day 10 Status
Multi-location Platform Support is **COMPLETE**, verified across unit, integration, regression, smoke, and live environments, and fully documented in the central Overview structure.

---

Previous: [Day 9](./Day-9.md)

Next: Day 11 — Not yet implemented

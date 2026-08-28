# Veyra — Phase 2 / Builder 1 / Day 9

## Historical Data Infrastructure

---

### 1. Day 9 Overview

The primary objective of **Day 9 (Historical Data Infrastructure)** in Phase 2 is to construct a safe, modular, and validated data collection foundation for historical meteorological and reanalysis data. In numerical weather prediction and forecast bust detection, evaluating forecast skill and training statistical/machine-learning bust predictors requires access to historical weather observations (e.g., ground truth reanalysis such as ERA5).

Day 9 establishes Builder 1's infrastructure layer to:
- Accept structured historical collection requests.
- Transparently reuse Day 8 Dynamic Location Resolution to translate city names and coordinate pairs into geographic coordinates.
- Ingest historical observations from weather data providers.
- Normalize heterogeneous provider payloads into Veyra's canonical historical data representations.
- Execute structural and meteorological Quality Control (QC).
- Prevent duplicate records deterministically while preserving valid distinct time series.
- Isolate provider connection drops, HTTP errors, and timeouts gracefully without application crashes.
- Provide a clean, typed programmatic dataset interface for downstream Builder 2 dataset engineering, alignment, and model calibration.

**Builder Scope Boundary**: Day 9 represents core Builder 1 infrastructure. Builder 2 will later own deeper dataset engineering, bust label policy calibration, feature engineering, and model training.

---

### 2. Starting Baseline

- **Day 8 Baseline**: Day 8 Dynamic Location Resolution completed, verified, pushed, reviewed, and merged into `main` via PR #10.
- **Starting Commit**: `721f16c Merge pull request #10 from RupanjanDutta2006/phase2/builder1-development`
- **Development Branch**: `phase2/builder1-development` (synchronized with `main`)
- **Working-Tree State Before Implementation**: Clean working tree.
- **Baseline Tests**: 126 passed, 0 failed, 0 errors in 34.51s.
- **Baseline Status**: 100% healthy baseline across all Phase 1 and Day 8 components.

---

### 3. Day 9 Objectives

| Objective | Status | Notes |
| :--- | :---: | :--- |
| Historical data request contract | **COMPLETE** | Typed Pydantic schema supporting location/coords, date ranges, and validated meteorological variables |
| Day 8 dynamic-location reuse | **COMPLETE** | Integrated with `DynamicLocationService` to resolve city names and direct coordinates transparently |
| Historical data collector | **COMPLETE** | `HistoricalDataService` orchestrating retrieval, normalization, deduplication, and QC |
| Provider integration | **COMPLETE** | Provider adapter querying Open-Meteo Historical Archive REST API |
| Canonical record normalization | **COMPLETE** | Standardized `CanonicalHistoricalRecord` with deterministic SHA-256 record IDs |
| Validation | **COMPLETE** | Strict date range, coordinate boundaries, variable aliases, and data type validation |
| Quality control | **COMPLETE** | Meteorological physical range limits, non-finite checks, and timestamp validation via `HistoricalQualityControl` |
| Duplicate prevention | **COMPLETE** | Deterministic duplicate detection and elimination via `HistoricalDeduplicator` |
| Provider failure handling | **COMPLETE** | Isolated exception handling for network drops, timeouts, and malformed provider responses |
| Timeout handling | **COMPLETE** | Explicit HTTP timeouts and transient retry policies |
| Builder 2 dataset interface | **COMPLETE** | Programmatic dataset interface with JSONL export/load and `ReferenceWeatherRecord` bridging |
| Reference/prediction separation | **COMPLETE** | Historical ground-truth records marked with `is_ground_truth_label=True` and isolated from feature extractors |
| Automated testing | **COMPLETE** | 16 dedicated unit/integration tests added covering all required failure and edge scenarios |

---

### 4. Architecture

```
User / Builder 2 Request (Location, Date Range, Variables)
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ HistoricalDataRequest                                       │
│ (location, start_date, end_date, variables, timezone, etc.) │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ HistoricalDataService.collect(...)                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Dynamic Location Resolution (Day 8 DynamicLocationService)│
│    ├── Place Name (e.g., 'Kolkata', 'London', 'Siliguri')   │
│    ├── Direct Coordinates (e.g., '22.5726, 88.3639')        │
│    └── Invalid Location/Coords ──► Safe Controlled Result   │
│                                                             │
│ 2. Query Construction & Provider Adapter (Open-Meteo API)   │
│    ├── Standard Library urllib.request                      │
│    ├── Configurable Timeout (15s) & Transient Retries       │
│    └── Network Failure / Timeout ──► Safe Isolated Error    │
│                                                             │
│ 3. Canonical Normalization                                  │
│    └── Provider Raw JSON ──► CanonicalHistoricalRecords     │
│                                                             │
│ 4. Deterministic Deduplication (HistoricalDeduplicator)     │
│    └── Stable Tuple Hashing ──► Duplicate Elimination       │
│                                                             │
│ 5. Quality Control Engine (HistoricalQualityControl)        │
│    └── Physical Limits, NaN/Inf Checks, Time Format Checks  │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ HistoricalCollectionResult                                  │
│ (is_success, records, total_records, duplicates_removed,    │
│  qc_passed, qc_violations, error_message, metadata)         │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼ (Downstream Builder 2 Dataset Interface)
┌─────────────────────────────────────────────────────────────┐
│ JSONL Serialization & Aligned Verification Bridge           │
│  - HistoricalDataService.export_to_jsonl(records, path)     │
│  - HistoricalDataService.load_from_jsonl(path)              │
│  - HistoricalDataService.to_reference_records(records)      │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. Day 8 Integration

Day 9 directly incorporates Day 8's `DynamicLocationService`:
- **City-Name Handling**: Place names such as `"Kolkata"`, `"London"`, `"Tokyo"`, or dynamic unseeded locations like `"Siliguri"` are resolved via the Day 8 `DynamicLocationService` to obtain precise decimal latitude and longitude coordinates.
- **Direct Coordinate Handling**: Direct coordinate strings such as `"22.5726, 88.3639"` are parsed and validated immediately, bypassing redundant geocoding API calls.
- **Avoidance of Duplicate Resolvers**: Day 9 does not create a separate city dictionary or coordinate parser; it injects `BaseLocationService` directly into `HistoricalDataService`.
- **Handoff**: Successfully resolved coordinates (`latitude`, `longitude`) are formatted into the provider query URL. If a location is unresolvable or invalid (e.g., `"Atlantis"`, `"999.0, 999.0"`), `HistoricalDataService` returns a safe controlled result (`is_success=False`, `error_message="INVALID_LOCATION"`).

---

### 6. Historical Data Request Contract

Implemented in `backend/app/schemas/historical.py` as `HistoricalDataRequest`:

```python
class HistoricalDataRequest(BaseModel):
    location: str
    start_date: str  # YYYY-MM-DD or ISO timestamp
    end_date: str    # YYYY-MM-DD or ISO timestamp
    variables: list[str] = ["temperature_2m", "surface_pressure", "wind_speed_10m", "relative_humidity_2m", "precipitation"]
    data_version: str = "gefs-openmeteo-v1.0"
    source: str = "OPENMETEO_ARCHIVE"
    timezone: str = "UTC"
```

**Validation Rules**:
- `location`: Stripped and non-empty.
- `start_date` and `end_date`: Verified as parseable ISO dates; strictly requires `start_date <= end_date`.
- `variables`: Validated against supported meteorological variables and standardized to canonical aliases (e.g., `"temperature"` -> `"temperature_2m"`, `"wind_speed"` -> `"wind_speed_10m"`).

---

### 7. Historical Data Collection Service

Implemented in `backend/app/services/historical_service.py` as `HistoricalDataService`:
- **Interface**: Implements `BaseHistoricalDataService` abstract contract.
- **Input**: Validated `HistoricalDataRequest`.
- **Output**: Structured `HistoricalCollectionResult`.
- **Responsibilities**:
  1. Coordinate resolution via `DynamicLocationService`.
  2. Geographic boundary validation (`-90 <= lat <= 90`, `-180 <= lon <= 180`).
  3. URL construction with standardized hourly parameters.
  4. HTTP execution with retry and timeout isolation.
  5. JSON payload parsing and conversion into `CanonicalHistoricalRecord` items.
  6. Deduplication via `HistoricalDeduplicator`.
  7. Quality Control evaluation via `HistoricalQualityControl`.

---

### 8. Canonical Historical Record

Implemented in `backend/app/schemas/historical.py` as `CanonicalHistoricalRecord`:

| Field | Type | Description |
| :--- | :--- | :--- |
| `record_id` | `str` | Deterministic 16-character SHA-256 hash |
| `location` | `str` | Requested location name or identifier |
| `latitude` | `float` | Decimal latitude (-90.0 to 90.0) |
| `longitude` | `float` | Decimal longitude (-180.0 to 180.0) |
| `valid_time` | `str` | ISO 8601 UTC timestamp of observation |
| `variable` | `str` | Canonical meteorological variable name |
| `unit` | `str` | Canonical unit (`celsius`, `hPa`, `m/s`, `%`, `mm`) |
| `value` | `float` | Observed or reanalyzed numerical value |
| `source` | `str` | Provider source (`OPENMETEO_ARCHIVE`) |
| `record_type` | `str` | Discriminator (`OBSERVATION`, `FORECAST`, `REANALYSIS`) |
| `issue_time` | `Optional[str]` | Issue cycle timestamp (populated for forecast records) |
| `lead_hours` | `Optional[int]` | Forecast lead hours (populated for forecast records) |
| `is_ground_truth_label` | `bool` | Strict anti-leakage flag (`True` for ground-truth observations) |
| `quality_flags` | `dict[str, Any]`| QC evaluation flags |

---

### 9. Automated Testing (16 Tests Passing)

```text
backend/tests/test_historical_infrastructure.py: 16 passed
Complete Regression Suite: 142 passed
```

---

### 10. Day Status

**STATUS: COMPLETE**

---

**Previous:** [Day 8](./Day-8.md) | **Next:** Day 10 (Planned)

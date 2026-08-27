# Veyra Phase 1 — Builder 1

## 1. Builder 1 Objective

The primary objective of **Builder 1** in Phase 1 was to design and implement the production-grade software engineering foundation for the **Veyra Forecast-Bust Sentinel** system.

Builder 1 was responsible for:
1. Establishing a clean, modular, and decoupled backend architecture based on modern Python and FastAPI.
2. Formulating strict abstract service interfaces (`BaseWeatherService`, `BaseFeatureService`, `BaseModelService`, `BaseSafetyService`) and typed dataclass exchange containers (`WeatherResult`, `FeatureResult`, `ModelResult`, `SafetyAssessment`).
3. Designing and enforcing Pydantic API schemas with robust validation (`PredictionRequest`, `PredictionResponse`, `HealthResponse`) and categorical enums (`RiskLevel`, `TrustState`, `ReasonCode`).
4. Building the central fail-safe orchestration engine (`ForecastBustAgent`) implementing sequential pipeline execution and fail-safe short-circuiting.
5. Implementing the safety evaluation and abstention engine (`SafetyEvaluator`) ensuring zero probability hallucination when upstream dependencies or models fail.
6. Providing meteorological data utilities, including unit conversion (`UnitConverter`), physical quality control (`ForecastQualityControl`), and historical dataset alignment (`HistoricalDatasetAligner`).
7. Delivering a baseline machine learning pipeline (`BaselineLogisticBustModel`, `TabularFeaturePipeline`, `TemporalSplitter`, `ModelArtifactManager`) as an initial proof of concept and verification harness.
8. Constructing an automated unit and integration test suite covering schemas, QC, ML splitting, unit conversions, live endpoints, and failure-mode recovery.

---

## 2. Architecture Implemented

Builder 1 implemented a **Hexagonal / Clean Architecture** pattern where domain logic and orchestration are strictly separated from external infrastructure, web protocols, and machine learning model implementations.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           API LAYER (FastAPI)                           │
│     GET /v1/health                             POST /v1/predict         │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER (Agent)                        │
│                          ForecastBustAgent                              │
│                                                                         │
│   1. Request Resolution & Geocoding                                     │
│   2. Weather Ingestion (BaseWeatherService)                             │
│   3. Quality Control (ForecastQualityControl)                           │
│   4. Feature Engineering (BaseFeatureService)                           │
│   5. Model Inference (BaseModelService)                                 │
│   6. Safety Assessment (BaseSafetyService / SafetyEvaluator)            │
│   7. Response Construction & Serialization                              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       ▼                             ▼                             ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│ DATA LAYER   │             │ ML LAYER     │             │ SAFETY LAYER │
│ - Ingestion  │             │ - Features   │             │ - TrustState │
│ - QC Checks  │             │ - Baseline ML│             │ - Abstention │
│ - Unit Conv  │             │ - Evaluation │             │ - ReasonCodes│
│ - Alignment  │             │ - Artifacts  │             │ - Fail-Safe  │
└──────────────┘             └──────────────┘             └──────────────┘
```

### Architectural Principles:
- **Dependency Inversion**: High-level modules (the agent and API routes) depend on abstract interfaces in `backend/app/services/base.py`, never on concrete third-party ML or weather APIs.
- **Fail-Safe Short-Circuiting**: If any stage (e.g., weather fetch or feature extraction) fails or returns invalid data, the agent halts further execution and passes the context to the safety evaluator to generate a safe abstention response.
- **Zero Probability Hallucination**: When a model is unready or abstaining, the system explicitly returns `bust_probability = None` with `abstain = True` and appropriate `ReasonCode` values.

---

## 3. Folder/File Structure

The Builder 1 backend codebase is organized under `backend/app/` and `backend/tests/`:

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── prediction.py
│   │   └── weather.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── live_serving.py
│   │   ├── openmeteo_service.py
│   │   └── weather_service.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── dataset.py
│   │   ├── historical_alignment.py
│   │   ├── qc.py
│   │   └── units.py
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── artifacts.py
│   │   ├── evaluate.py
│   │   ├── features.py
│   │   ├── models.py
│   │   └── splitting.py
│   ├── safety/
│   │   ├── __init__.py
│   │   └── abstention.py
│   ├── agents/
│   │   ├── __init__.py
│   │   └── forecast_bust_agent.py
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── router.py
│           └── endpoints/
│               ├── __init__.py
│               ├── health.py
│               └── predict.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_agent.py
    ├── test_bust_labeling.py
    ├── test_final_readiness.py
    ├── test_health.py
    ├── test_historical_alignment.py
    ├── test_historical_dataset.py
    ├── test_live_serving.py
    ├── test_ml_features.py
    ├── test_ml_model_and_eval.py
    ├── test_ml_splitting.py
    ├── test_predict.py
    ├── test_qc.py
    ├── test_schemas.py
    ├── test_services.py
    ├── test_unit_conversion.py
    └── test_weather_ingestion.py
```

### Key File Breakdown

| File Path | Purpose | Key Responsibilities |
|---|---|---|
| `backend/app/main.py` | Application Entry Point | Initializes FastAPI application, configures CORS middleware, registers routers, and sets up lifespan handlers. |
| `backend/app/core/config.py` | Environment & System Settings | Defines `Settings` using Pydantic `BaseSettings`, managing project names, API keys, thresholds, timeouts, and artifact paths. |
| `backend/app/schemas/prediction.py` | API Data Contracts | Defines `PredictionRequest`, `PredictionResponse`, and enums `RiskLevel`, `TrustState`, `ReasonCode`. |
| `backend/app/schemas/health.py` | Health Check Contract | Defines `HealthResponse` schema returning service status, service name, and version. |
| `backend/app/schemas/weather.py` | Meteorological Data Schemas | Defines `CanonicalForecastRecord`, `ForecastQCResult`, and `WeatherQuery` models. |
| `backend/app/services/base.py` | Abstract Service Interfaces | Defines `BaseWeatherService`, `BaseFeatureService`, `BaseModelService`, `BaseSafetyService` and typed containers `WeatherResult`, `FeatureResult`, `ModelResult`, `SafetyAssessment`. |
| `backend/app/services/weather_service.py` | Fallback Weather Implementations | Implements `UnavailableWeatherService` for offline, uninitialized, or fallback environments. |
| `backend/app/services/openmeteo_service.py` | Live Weather Ingestion Client | Implements `OpenMeteoGEFSWeatherService`, fetching 31-member GEFS ensemble forecasts from Open-Meteo API with retry loops and timeouts. |
| `backend/app/services/live_serving.py` | Baseline Serving Wrappers | Implements `LiveFeatureService` and `LiveLogisticModelService` for Day 5–6 baseline ML serving. |
| `backend/app/data/qc.py` | Meteorological Quality Control | Implements `ForecastQualityControl` checking physical range boundaries, timestamp monotonicity, duplicate timestamps, and missing values. |
| `backend/app/data/units.py` | Standardized Unit Conversion | Implements `UnitConverter` supporting bidirectional conversions for temperature (°C, K, °F), pressure (hPa, Pa), wind speed (m/s, km/h, knots), and precipitation (mm, m, inches). |
| `backend/app/data/historical_alignment.py` | Historical Dataset Alignment | Implements `HistoricalDatasetAligner` performing exact valid-time matching between forecasts and reference reanalysis with anti-leakage checks. |
| `backend/app/data/dataset.py` | Training Dataset Builder | Implements `HistoricalDatasetBuilder` and `HistoricalTrainingRow` serializing paired records into JSON Lines format. |
| `backend/app/ml/features.py` | Baseline Feature Pipeline | Implements `TabularFeaturePipeline` with cyclic trigonometric encodings (`sin_hour`, `cos_month`), one-hot encodings, and anti-leakage exclusion. |
| `backend/app/ml/models.py` | Baseline Machine Learning Model | Implements `BaselineLogisticBustModel` wrapping scikit-learn `LogisticRegression` with balanced class weights and probability clipping. |
| `backend/app/ml/evaluate.py` | Evaluation Metrics | Implements `ModelEvaluator` computing ROC-AUC, Brier score, False Negative Rate, and classification reports. |
| `backend/app/ml/splitting.py` | Strict Temporal Splitting | Implements `TemporalSplitter` executing chronological train/validation/test dataset splits without future-data lookahead. |
| `backend/app/ml/artifacts.py` | Artifact Persistence | Implements `ModelArtifactManager` and `ModelMetadata` saving and loading `.joblib` and `.json` artifacts with path fallback resolution. |
| `backend/app/safety/abstention.py` | Safety & Abstention Engine | Implements `SafetyEvaluator` mapping model predictions and failure signals to `TrustState`, `RiskLevel`, and `ReasonCode`. |
| `backend/app/agents/forecast_bust_agent.py` | Central Orchestration Agent | Implements `ForecastBustAgent` managing the 7-step pipeline from request validation to response serialization. |
| `backend/app/api/v1/router.py` | V1 API Router | Aggregates sub-routers for health and prediction endpoints. |
| `backend/app/api/v1/endpoints/health.py` | Health Check Route | Implements `GET /v1/health` returning service health status. |
| `backend/app/api/v1/endpoints/predict.py` | Bust Prediction Route | Implements `POST /v1/predict` validating payloads and invoking the agent. |

---

## 4. Backend Components

### A. ForecastBustAgent (`backend/app/agents/forecast_bust_agent.py`)
The orchestrator coordinates the end-to-end inference flow:
1. `resolve_request(request)`: Normalizes location strings, trims whitespace, and sets target horizons.
2. `get_weather_data(location, target_date)`: Invokes the injected `BaseWeatherService`.
3. `get_features(weather_result)`: Invokes `BaseFeatureService` only if weather data is available.
4. `run_model(feature_result)`: Invokes `BaseModelService` only if features are ready.
5. `apply_safety(weather_result, feature_result, model_result)`: Evaluates safety boundaries and trust state.
6. `build_response(location, safety_assessment, model_result, weather_result)`: Assembles `PredictionResponse`.

### B. SafetyEvaluator (`backend/app/safety/abstention.py`)
Applies deterministic safety rules:
- **Upstream Failures**: If weather, feature, or model service indicates `is_available=False` or `is_ready=False`, returns `abstain=True`, `trust_state=UNAVAILABLE`, `probability=None`, and logs the corresponding reason code (`DATA_NOT_READY`, `FEATURES_NOT_READY`, or `MODEL_NOT_READY`).
- **Probability Boundary Guard**: If model returns $P < 0.0$ or $P > 1.0$, treats it as an invalid calculation, setting `abstain=True`, `trust_state=UNAVAILABLE`, and `reason_codes=[QC_FAILED]`.
- **Risk Level Mapping**:
  - $P(\text{bust}) \ge 0.70 \implies \text{HIGH}$
  - $0.30 \le P(\text{bust}) < 0.70 \implies \text{MEDIUM}$
  - $P(\text{bust}) < 0.30 \implies \text{LOW}$
- **Trust State Mapping**:
  - $P(\text{bust}) \le 0.15$ or $P(\text{bust}) \ge 0.85 \implies \text{HIGH\_CONFIDENCE}$
  - $0.15 < P(\text{bust}) < 0.85 \implies \text{MODERATE\_CONFIDENCE}$

### C. ForecastQualityControl (`backend/app/data/qc.py`)
Ensures meteorological integrity:
- Validates physical bounds (e.g., temperature in $[-90^\circ\text{C}, +60^\circ\text{C}]$, surface pressure in $[500\,\text{hPa}, 1100\,\text{hPa}]$, wind speed in $[0\,\text{m/s}, 150\,\text{m/s}]$).
- Ensures non-negative precipitation.
- Checks timestamp monotonicity and rejects duplicate forecasts for the same valid time.
- Validates ensemble consistency ($\text{ensemble\_min} \le \text{ensemble\_mean} \le \text{ensemble\_max}$).

### D. UnitConverter (`backend/app/data/units.py`)
Performs validated conversions across 4 physical dimensions:
- Temperature: Celsius, Kelvin, Fahrenheit.
- Pressure: hPa, Pa, bar, atm.
- Wind Speed: m/s, km/h, knots, mph.
- Precipitation: mm, m, inches.
- Incompatible conversions (e.g., Celsius to hPa) raise explicit `ValueError`.

---

## 5. API Components

Builder 1 implemented FastAPI REST endpoints conforming to OpenAPI 3.0:

### 1. `GET /v1/health`
- **Location**: `backend/app/api/v1/endpoints/health.py`
- **Purpose**: System liveness check and runtime version inspection.
- **Response**: HTTP 200 OK
  ```json
  {
    "status": "ok",
    "service": "forecast-bust-sentinel",
    "version": "0.1.0"
  }
  ```

### 2. `POST /v1/predict`
- **Location**: `backend/app/api/v1/endpoints/predict.py`
- **Purpose**: Real-time forecast bust risk prediction for a location and forecast horizon.
- **Request Payload**: `PredictionRequest`
- **Response Payload**: `PredictionResponse`

---

## 6. Request/Response Contracts

### `PredictionRequest` (`backend/app/schemas/prediction.py`)
```python
class PredictionRequest(BaseModel):
    location: str                    # City name or "lat,lon" (Required, non-empty)
    region_id: Optional[str] = None  # Optional regional alias
    issue_time: Optional[str] = None # ISO 8601 UTC timestamp
    valid_time: Optional[str] = None # ISO 8601 UTC timestamp
    variable: Optional[str] = None   # Target meteorological variable
    model_type: Optional[str] = None # Optional model identifier
    target_date: Optional[str] = None# ISO date YYYY-MM-DD
```

**Validation Guards:**
- Rejects empty, whitespace-only, or null `location` strings with HTTP 422.
- Rejects invalid lead times (`valid_time <= issue_time` or $\text{lead\_hours} \le 0$) with HTTP 422.
- Rejects excessive lead times ($\text{lead\_hours} > 384\,\text{h}$) with HTTP 422.
- Rejects unsupported variables not in whitelist (`temperature_2m`, `surface_pressure`, `wind_speed_10m`, `relative_humidity_2m`, `precipitation`) with HTTP 422.
- Rejects non-ISO 8601 timestamps with HTTP 422.

### `PredictionResponse` (`backend/app/schemas/prediction.py`)
```python
class PredictionResponse(BaseModel):
    location: str
    bust_probability: Optional[float] = None
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    trust_state: TrustState = TrustState.UNAVAILABLE
    abstain: bool = False
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    model_version: Optional[str] = None
    data_version: Optional[str] = None
```

---

## 7. Prediction Pipeline Components

The complete sequence within Builder 1's orchestrator operates as follows:

```text
PredictionRequest
  │
  ├─► [1] Validation & Normalization (Location, Lead Hours, Variable)
  │
  ├─► [2] OpenMeteoGEFSWeatherService.get_forecast()
  │     └─► Fetches 31-member ensemble records
  │
  ├─► [3] ForecastQualityControl.validate_records()
  │     └─► Enforces physical ranges & timestamp monotonicity
  │
  ├─► [4] BaseFeatureService.build_features()
  │     └─► Extracts tabular features
  │
  ├─► [5] BaseModelService.predict()
  │     └─► Computes calibrated bust probability
  │
  ├─► [6] SafetyEvaluator.evaluate()
  │     └─► Determines RiskLevel, TrustState, and ReasonCodes
  │
  └─► [7] PredictionResponse
```

---

## 8. Safety / Abstention Logic

Builder 1 established three core safety principles:
1. **Never Panic**: Unhandled external API exceptions or network dropouts are caught and translated into structured `ReasonCode.DATA_UNAVAILABLE` or `ReasonCode.MODEL_NOT_READY` assessments rather than unhandled 500 crashes.
2. **Never Hallucinate**: If any upstream stage fails, the prediction probability is strictly `None`. The system never invents a placeholder probability (such as `0.0`, `0.5`, or random values).
3. **Traceability**: Every response includes `model_version`, `data_version`, and a list of `reason_codes` documenting why the system reached its conclusion or why it chose to abstain.

---

## 9. Error Handling

- **Client Input Errors**: Malformed JSON, empty fields, negative lead times, or invalid dates trigger HTTP 422 Unprocessable Entity with descriptive error messages.
- **Geographic Abstentions**: Unresolvable city names or out-of-bounds coordinates return HTTP 200 with `abstain = True`, `trust_state = UNAVAILABLE`, and `reason_codes = ["INVALID_LOCATION"]`.
- **Upstream Service Outages**: External weather provider timeouts or network drops return HTTP 200 with `abstain = True`, `trust_state = UNAVAILABLE`, and `reason_codes = ["MODEL_NOT_READY"]` or `["DATA_UNAVAILABLE"]`.

---

## 10. Tests Implemented

Builder 1 created 18 unit and integration test modules in `backend/tests/`:

1. `test_agent.py`: ForecastBustAgent sequential orchestration and short-circuit tests.
2. `test_bust_labeling.py`: Threshold-based bust labeling logic.
3. `test_final_readiness.py`: System readiness, multi-location serving, and failure recovery.
4. `test_health.py`: Health check endpoint schema and status verification.
5. `test_historical_alignment.py`: Forecast-to-reanalysis alignment and anti-leakage assertions.
6. `test_historical_dataset.py`: Historical JSONL dataset builder and serialization.
7. `test_live_serving.py`: Baseline live serving, artifact loading, and agent integration.
8. `test_ml_features.py`: Feature extraction, cyclic transforms, and leakage prevention.
9. `test_ml_model_and_eval.py`: Baseline Logistic Regression training, evaluation, and serialization.
10. `test_ml_splitting.py`: Temporal chronological split ratios and order preservation.
11. `test_predict.py`: `/v1/predict` endpoint validation, lead-time checks, and dependency injection.
12. `test_qc.py`: Quality control boundary checks, duplicate detection, and unit consistency.
13. `test_schemas.py`: Pydantic schema validation, defaults, and serialization.
14. `test_services.py`: Abstract service contracts, unavailable mocks, and safety evaluator boundaries.
15. `test_unit_conversion.py`: Physical unit conversions and incompatible dimension rejections.
16. `test_weather_ingestion.py`: Open-Meteo coordinate resolution, query building, and parsing.

---

## 11. Configuration

Configuration is managed via `backend/app/core/config.py`:
- `PROJECT_NAME`: `"Forecast-Bust Sentinel API"`
- `API_V1_STR`: `"/v1"`
- `WEATHER_API_TIMEOUT_SECONDS`: `25`
- `DECISION_THRESHOLD`: `0.280`
- `BUILDER2_MODEL_DIR`: Path to production model artifacts.

---

## 12. Builder 1 Outputs

1. **Production Code**: Core application framework, agent orchestrator, safety evaluator, QC suite, unit converter, schemas, and API endpoints.
2. **Baseline Artifacts**:
   - `models/baseline_logistic_v1.joblib`: Proof-of-concept Logistic Regression model.
   - `models/baseline_logistic_v1_metadata.json`: Provenance metadata for baseline model.
3. **Verification Scripts**:
   - `scripts/smoke_test_weather.py`: Ingestion smoke test.
   - `scripts/smoke_test_historical.py`: Historical pipeline smoke test.
   - `scripts/smoke_test_ml.py`: Baseline ML smoke test.
   - `scripts/smoke_test_serving.py`: Live serving smoke test.
   - `scripts/smoke_test_final.py`: Day 7 final readiness smoke test.

---

## 13. Known Limitations

- **Baseline ML Model**: The baseline model was a standard Logistic Regression model fit on 62 proof-of-concept rows, intended strictly as an integration scaffold rather than a production-grade meteorological classifier.
- **Baseline Feature Pipeline**: The 18-feature baseline pipeline lacked multi-cycle revision tracking (e.g., 6h/24h run-to-run forecast deltas) and advanced ensemble dispersion metrics.

---

## 14. Builder 1 Final Phase-1 Status

**STATUS: COMPLETE & PRODUCTION READY**
Builder 1 successfully delivered the architectural skeleton, orchestration engine, API endpoints, safety layer, and abstract interfaces necessary for Builder 2 to plug in production-grade meteorological ML models.

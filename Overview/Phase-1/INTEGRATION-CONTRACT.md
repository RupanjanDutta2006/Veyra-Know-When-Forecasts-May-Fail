# Veyra — Builder 1 ↔ Builder 2 Integration Contract

**Document Version:** 1.0.0  
**Status:** ACTIVE / BASELINE ESTABLISHED  
**Date:** August 25, 2026  
**Authors:** Builder 1 (Backend, Orchestration, API & Safety Architecture) & Builder 2 (Weather Ingestion, Feature Pipeline, Calibrated ML Models)

---

## 1. Executive Summary & Architecture

The Veyra Forecast-Bust Sentinel is strictly partitioned into two decoupled modules to enable concurrent development without merge conflicts or code blocking:

```
[ User / Frontend Client ]
           │
           │ HTTP POST /v1/predict (PredictionRequest)
           ▼
[ FastAPI Web Service (backend/app/main.py) ]
           │
           ▼
[ ForecastBustAgent (Orchestration Engine) ]
           │
           ├───────────────────────────────┐
           ▼                               │
┌──────────────────────────────┐           │
│      BUILDER 2 DOMAIN        │           │
├──────────────────────────────┤           │
│ 1. WeatherService            │           │
│    (GEFS/ERA5 Ingestion)     │           │
│    └──► WeatherResult        │           │
│                              │           │
│ 2. FeatureService            │           │
│    (Atmospheric Preprocessing│           │
│    └──► FeatureResult        │           │
│                              │           │
│ 3. ModelService              │           │
│    (Calibrated LightGBM/XGB) │           │
│    └──► ModelResult          │           │
└──────────────────────────────┘           │
           │                               │
           ▼                               ▼
[ SafetyService / SafetyEvaluator (Abstention Engine) ]
           │
           ▼
[ PredictionResponse (JSON Payload) ]
```

---

## 2. Builder 1 Provides to Builder 2

Builder 1 provides the production backend infrastructure:
1. **FastAPI Web Framework & Routes:**
   - Interactive OpenAPI/Swagger UI at `http://localhost:8000/docs`
   - Health check endpoint: `GET /v1/health`
   - Prediction endpoint: `POST /v1/predict`
2. **Pydantic API Data Contracts:**
   - Strict request validation (`PredictionRequest`) rejecting null/empty locations with HTTP 422.
   - Standard response serialization (`PredictionResponse`) with calibrated probabilities, categorical risk levels, and reason codes.
3. **Abstract Base Interfaces & Result Types:**
   - `BaseWeatherService`, `BaseFeatureService`, `BaseModelService`, `BaseSafetyService` in `backend/app/services/base.py`.
   - Typed data containers: `WeatherResult`, `FeatureResult`, `ModelResult`, `SafetyAssessment`.
4. **Safety & Abstention Orchestration:**
   - Centralized `ForecastBustAgent` implementing sequential short-circuiting.
   - Out-of-Distribution (OOD) and failsafe abstention engine (`SafetyEvaluator`).
   - Guarantees that **no hallucinated/fake probabilities** are returned when ML or weather data is unavailable.

---

## 3. Builder 2 Implements for Builder 1

Builder 2 fulfills the abstract base classes in `backend/app/services/base.py`.

### A. Weather Ingestion Service Contract (`BaseWeatherService`)

```python
from abc import ABC, abstractmethod
from typing import Optional
from backend.app.services.base import BaseWeatherService, WeatherResult

class RealWeatherService(BaseWeatherService):
    def get_forecast(
        self, location: str, target_date: Optional[str] = None
    ) -> WeatherResult:
        ...
```

#### `WeatherResult` Specification:
| Field | Type | Required | Description | Example |
|---|---|:---:|---|---|
| `location` | `str` | Yes | Target geographical location/coordinates | `"London"` |
| `target_date` | `Optional[str]` | No | ISO format date (YYYY-MM-DD) | `"2026-09-01"` |
| `raw_data` | `dict[str, Any]` | Yes | Dictionary containing numerical weather grids, ensemble members, or observation parameters | `{"ensemble_temp": [18.2, 19.1, ...], "gefs_spread": 2.4}` |
| `data_version` | `Optional[str]` | Yes | Pipeline & data source version identifier | `"gefs-reforecast-v1.0"` |
| `is_available` | `bool` | Yes | `True` if data was successfully collected; `False` if offline/missing | `True` |
| `quality_flags` | `dict[str, Any]` | Yes | Quality control status flags | `{"qc_passed": True, "missing_members": 0}` |
| `metadata` | `dict[str, Any]` | No | Additional metadata (latency, provider, run cycle) | `{"cycle": "00Z", "lead_time_hours": 72}` |
| `error` | `Optional[str]` | No | Error message if collection failed (or `None`) | `None` |

---

### B. Feature Engineering Service Contract (`BaseFeatureService`)

```python
from backend.app.services.base import BaseFeatureService, FeatureResult, WeatherResult

class RealFeatureService(BaseFeatureService):
    def build_features(self, weather_result: WeatherResult) -> FeatureResult:
        ...
```

#### `FeatureResult` Specification:
| Field | Type | Required | Description | Example |
|---|---|:---:|---|---|
| `location` | `str` | Yes | Target geographical location | `"London"` |
| `features` | `dict[str, float]` | Yes | Dictionary mapping feature names to numerical floats (standardized/normalized) | `{"ensemble_spread": 2.34, "thermal_gradient": 1.12, "cape_index": 450.0}` |
| `feature_names` | `list[str]` | Yes | Ordered list of feature names matching model input | `["ensemble_spread", "thermal_gradient", "cape_index"]` |
| `is_ready` | `bool` | Yes | `True` if features are valid and non-NaN; `False` otherwise | `True` |
| `metadata` | `dict[str, Any]` | No | Preprocessing metadata (scaler version, imputation status) | `{"scaler": "standard_scaler_v1", "imputed": False}` |
| `error` | `Optional[str]` | No | Error message if feature calculation failed | `None` |

---

### C. ML Model Service Contract (`BaseModelService`)

```python
from backend.app.services.base import BaseModelService, FeatureResult, ModelResult

class RealCalibratedModelService(BaseModelService):
    def predict(self, feature_result: FeatureResult) -> ModelResult:
        ...
```

#### `ModelResult` Specification:
| Field | Type | Required | Description | Example |
|---|---|:---:|---|---|
| `probability` | `Optional[float]` | Yes | **Strictly calibrated probability (0.0 to 1.0)** of forecast bust. `None` if unready or abstaining. | `0.38` |
| `model_version` | `Optional[str]` | Yes | Model artifact identifier | `"lgbm-bust-calibrated-v1.0"` |
| `is_ready` | `bool` | Yes | `True` if model artifact is loaded and prediction succeeded | `True` |
| `metadata` | `dict[str, Any]` | No | Training metrics, calibration method, feature importance | `{"calibration_method": "isotonic", "brier_score": 0.078}` |
| `error` | `Optional[str]` | No | Error description if inference failed | `None` |

---

## 4. Reason Codes & Status Handling

Builder 2 modules should leverage centralized `ReasonCode` values defined in `backend/app/schemas/prediction.py`:

```python
from backend.app.schemas.prediction import ReasonCode
```

| Reason Code | When to Use |
|---|---|
| `DATA_NOT_READY` | Weather data pipeline is initializing or missing historical baseline. |
| `DATA_UNAVAILABLE` | External weather API / GEFS feed is down or network timeout occurred. |
| `QC_FAILED` | Ingested weather data failed physical range checks (e.g. negative Kelvin). |
| `FEATURES_NOT_READY` | Feature preprocessing encountered unresolvable NaNs or missing members. |
| `MODEL_NOT_READY` | Model weights/artifacts are not yet downloaded or compiled. |
| `MODEL_UNAVAILABLE` | Inference runtime failure or memory exhaustion. |
| `OOD_DETECTED` | Extreme atmospheric anomalies outside training distribution. |
| `SUCCESS` | Successful calibrated prediction with high/moderate confidence. |

---

## 5. Plug-and-Play Injection Example

Builder 2 can instantiate and test the full pipeline in Python without modifying `ForecastBustAgent` or `main.py`:

```python
from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.schemas.prediction import PredictionRequest
from my_ml_module import GEFSWeatherService, AtmosphereFeatureService, CalibratedLightGBMService

# 1. Instantiate Builder 2 services
weather_service = GEFSWeatherService(api_key="...", cycle="00Z")
feature_service = AtmosphereFeatureService(scaler_path="scaler.pkl")
model_service = CalibratedLightGBMService(model_path="lgbm_v1.bin")

# 2. Inject into ForecastBustAgent
agent = ForecastBustAgent(
    weather_service=weather_service,
    feature_service=feature_service,
    model_service=model_service,
)

# 3. Execute evaluation
request = PredictionRequest(location="London", target_date="2026-09-01")
response = agent.analyze(request)

print("Bust Probability:", response.bust_probability)
print("Risk Level:", response.risk_level)
print("Trust State:", response.trust_state)
```

---

## 6. Testing & Quality Rules for Builder 2

1. **Zero Fake Probabilities:** Never return placeholder numbers (e.g., `0.5`, `random()`) in production classes. Return `None` with `is_ready=False` when unready.
2. **Probability Calibration:** Raw model logits or uncalibrated tree outputs must pass through Platt scaling or Isotonic regression before returning in `ModelResult.probability`.
3. **Short-Circuit Awareness:** If `WeatherResult.is_available` is `False`, `FeatureService` and `ModelService` will never be called by the agent.
4. **Unit Tests:** Builder 2 tests should live in `backend/tests/` or a dedicated `ml_tests/` folder and pass under `python -m pytest`.

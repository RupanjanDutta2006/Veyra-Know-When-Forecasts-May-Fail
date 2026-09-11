# Veyra — Know When Forecasts May Fail
## Day-2 Builder 1 Development Overview

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 1 (Backend API, Modular Orchestration, Dependency Injection, Safety & Abstention)  
**Date:** August 25, 2026  
**Git Branch:** `rupanjan/backend-agent`  
**Test Status:** 35/35 Automated Tests Passing (100%)  

---

## 1. Executive Summary

Today marked **Day 2** of development for Veyra. The primary objective for Builder 1 was to transition the initial Day-1 backend foundation into a **modular, plug-and-play architecture** ready for seamless integration with Builder 2's data science, weather pipeline, and machine learning components.

- **What we achieved today:**
  1. Formalized strict, typed service contracts (`BaseWeatherService`, `BaseFeatureService`, `BaseModelService`, `BaseSafetyService`) and standard result containers (`WeatherResult`, `FeatureResult`, `ModelResult`, `SafetyAssessment`).
  2. Implemented comprehensive **Dependency Injection** in `ForecastBustAgent` so all sub-services can be swapped or injected dynamically without modifying core orchestrator code.
  3. Built a resilient, **sequential short-circuiting pipeline** in `ForecastBustAgent.analyze()`:
     - Weather failure immediately short-circuits and prevents unnecessary Feature/Model execution.
     - Feature failure immediately short-circuits and prevents Model execution.
     - Missing or uncalibrated models trigger safe abstention without hallucinating fake probabilities.
  4. Centralized pipeline status codes and reason taxonomy in `ReasonCode` enum.
  5. Implemented robust service-level exception handling that catches unexpected errors without leaking system paths, secrets, or crashing the server.
  6. Added 16 new automated unit and integration tests (bringing the suite from 19 to 35 tests, all passing in 0.10s).
  7. Authored [BUILDER_1_BUILDER_2_INTEGRATION_CONTRACT.md](file:///BUILDER_1_BUILDER_2_INTEGRATION_CONTRACT.md) to provide Builder 2 with complete specifications, data formats, and plug-in examples.

---

## 2. Day-2 Objectives & Status

| Objective | Status | Proof in Repository |
|---|:---:|---|
| **Preserve Day-1 Working Baseline** | **COMPLETED** | `/v1/health`, `/v1/predict`, and `/docs` verified intact |
| **Typed Service Contracts** | **COMPLETED** | [backend/app/services/base.py](file:///backend/app/services/base.py) |
| **WeatherService Contract** | **COMPLETED** | [backend/app/services/weather_service.py](file:///backend/app/services/weather_service.py) |
| **FeatureService Contract** | **COMPLETED** | [backend/app/services/feature_service.py](file:///backend/app/services/feature_service.py) |
| **ModelService Contract** | **COMPLETED** | [backend/app/services/model_service.py](file:///backend/app/services/model_service.py) |
| **SafetyService Contract & Evaluator** | **COMPLETED** | [backend/app/safety/abstention.py](file:///backend/app/safety/abstention.py) |
| **Dependency Injection in Agent** | **COMPLETED** | [backend/app/agents/forecast_bust_agent.py](file:///backend/app/agents/forecast_bust_agent.py) |
| **Sequential Short-Circuiting Pipeline** | **COMPLETED** | Validated in [backend/tests/test_agent.py](file:///backend/tests/test_agent.py) |
| **Centralized Reason Code Taxonomy** | **COMPLETED** | [backend/app/schemas/prediction.py](file:///backend/app/schemas/prediction.py) |
| **Builder 1 ↔ Builder 2 Contract Doc** | **COMPLETED** | [BUILDER_1_BUILDER_2_INTEGRATION_CONTRACT.md](file:///BUILDER_1_BUILDER_2_INTEGRATION_CONTRACT.md) |
| **Comprehensive Test Suite (35 tests)** | **COMPLETED** | 35 passed in [backend/tests/](file:///backend/tests/) |

---

## 3. Architecture & Pipeline Flow

```
[ User / Web Dashboard ]
           │
           │ POST /v1/predict (PredictionRequest: {"location": "London", "target_date": "2026-09-01"})
           ▼
[ FastAPI App (backend/app/main.py) ]
           │
           ▼
[ ForecastBustAgent (Dependency Injected) ]
           │
           ├───────────────────────────────┐
           ▼                               │
[ 1. WeatherService.get_forecast() ]       │
   ├── Succeeded ────────────────────────┐ │
   └── Failed / Unavailable ──────────┐  │ │
                                      │  │ │
                                      │  ▼ │
[ 2. FeatureService.build_features() ]│    │
   ├── Succeeded ───────────────────┐ │    │
   └── Failed / Unavailable ─────┐  │ │    │
                                 │  │ │    │
                                 │  ▼ │    │
[ 3. ModelService.predict() ]    │    │    │
   ├── Calibrated Probability ─┐ │    │    │
   └── Unready / Null ──────┐  │ │    │    │
                            │  │ │    │    │
                            ▼  ▼ ▼    │    │
[ 4. SafetyService.evaluate() ] ◄─────┘    │
   ├── Valid Model ──► HIGH_CONFIDENCE / SUCCESS
   └── Any Stage Unready ──► UNAVAILABLE / ABSTAIN (bust_probability: null)
                            │
                            ▼
[ 5. PredictionResponse (JSON Payload) ]
```

---

## 4. Reason Code Taxonomy

The reason codes in `backend/app/schemas/prediction.py` categorize all outcomes:

```python
class ReasonCode(str, Enum):
    DATA_NOT_READY = "DATA_NOT_READY"        # Weather ingestion baseline initializing
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"    # Weather API or GEFS feed offline
    FEATURES_NOT_READY = "FEATURES_NOT_READY"# Feature calculations failed or NaNs detected
    MODEL_NOT_READY = "MODEL_NOT_READY"      # Model weights not integrated
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"  # Inference runtime failure
    INVALID_LOCATION = "INVALID_LOCATION"    # Location string rejected by geocoding
    QC_FAILED = "QC_FAILED"                  # Weather data failed quality controls
    OOD_ABSTAIN = "OOD_ABSTAIN"              # Atmospheric state outside training distribution
    OOD_DETECTED = "OOD_DETECTED"            # Severe anomaly detected
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Incomplete member ensemble
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"# Volatility beyond safe estimation bounds
    INTERNAL_ERROR = "INTERNAL_ERROR"        # Unexpected server-side exception caught safely
    SUCCESS = "SUCCESS"                      # Confident calibrated prediction returned
```

---

## 5. Automated Verification Results

Running `python -m pytest` executes the complete 35-test suite across 5 test modules:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail
configfile: pytest.ini
testpaths: backend/tests
plugins: anyio-4.14.2
collected 35 items

backend\tests\test_agent.py ........                                     [ 22%]
backend\tests\test_health.py ..                                          [ 28%]
backend\tests\test_predict.py ...........                                [ 60%]
backend\tests\test_schemas.py ......                                     [ 77%]
backend\tests\test_services.py ........                                  [100%]

============================= 35 passed in 0.13s ==============================
```

---

## 6. What Was Intentionally NOT Done Today (Scope Boundary Guardrails)

In strict adherence to project boundaries:
- ❌ **No Weather Downloaders:** GEFS/ERA5 downloaders were not implemented (Builder 2 domain).
- ❌ **No Machine Learning Models:** LightGBM, XGBoost, and neural networks were not trained (Builder 2 domain).
- ❌ **No Fake Probabilities:** Never returned random or hardcoded probabilities; `bust_probability` remains `null` when real models are unready.
- ❌ **No Database or Microservices:** Kept architecture lean, simple, and clean.
- ❌ **No Ollama / LLM Weather Predictors:** Retained sentinel focus as an ML decision-support service.

---

## 7. Next Steps for Day 3

1. **Model Calibration & Verification Hooks:** Integrate metrics tracking (Brier scores, Expected Calibration Error) in the safety assessment layer.
2. **Out-of-Distribution (OOD) Scoring Module:** Expand `SafetyEvaluator` with Mahalanobis distance / ensemble dispersion checks when Builder 2 features arrive.
3. **Builder 2 Staging & Integration Testing:** Connect Builder 2's `builder2/weather-ml` branch when ready and run joint end-to-end integration tests.

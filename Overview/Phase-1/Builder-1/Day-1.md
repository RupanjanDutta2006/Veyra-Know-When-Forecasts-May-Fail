# Veyra — Phase 1 / Builder 1 / Day 1

## Initial Backend Architecture, FastAPI Setup & Abstention Framework

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 1 (Backend API, Orchestration, Integration Architecture, Safety & Abstention)  
**Date:** August 25, 2026  
**Git Branch:** `rupanjan/backend-agent`  
**Latest Commit:** `8948b4d` (*feat: initialize backend API and forecast bust agent*)  

---

## 1. Executive Summary

Today marked **Day 1** of development for Veyra. The goal for Builder 1 was to construct a robust, production-grade backend foundation that serves as the backbone for the entire system.

- **What we worked on today:** Built the core FastAPI web service, standard Pydantic data schemas, versioned routing (`/v1`), the `ForecastBustAgent` orchestration pipeline, safety evaluation protocols, and service interface contracts for Builder 2.
- **Why this work was necessary:** Forecast-Bust Sentinel is an AI-assisted decision-support system. Before integrating complex machine learning models or atmospheric data pipelines, we need strict API contracts, clean decoupling between backend and data science, and a failsafe abstention engine so the system never outputs invalid or uncalibrated data.
- **What is now functional:** The backend web server starts cleanly, serves interactive OpenAPI/Swagger documentation at `/docs`, provides an independent health endpoint (`GET /v1/health`), validates user requests, and executes an end-to-end evaluation flow via `POST /v1/predict` with 19 automated tests passing.
- **What is intentionally NOT functional yet:** The real machine learning model and weather data ingestion pipelines (Builder 2's domain) are not yet integrated. While these modules are being built, the API safely returns an explicit `UNAVAILABLE` abstention response with `bust_probability: null`. **No fake or hallucinated probabilities are generated.**

---

## 2. Day-1 Objectives

| Objective | Status | Proof in Repository |
|---|:---:|---|
| **Repository Inspection & Clean Environment** | **COMPLETED** | Inspected repo, configured `.gitignore` & `requirements.txt` |
| **FastAPI Application Setup & Versioning** | **COMPLETED** | `backend/app/main.py` and `backend/app/api/v1/router.py` |
| **Health Check API (`GET /v1/health`)** | **COMPLETED** | `backend/app/api/v1/endpoints/health.py` |
| **Pydantic API Schemas & Data Contracts** | **COMPLETED** | `backend/app/schemas/prediction.py` |
| **`ForecastBustAgent` Orchestrator Skeleton** | **COMPLETED** | `backend/app/agents/forecast_bust_agent.py` |
| **Builder 2 Service Interface Contracts** | **COMPLETED** | `backend/app/services/base.py` & `backend/app/services/model_service.py` |
| **Safe `UNAVAILABLE` Abstention Engine** | **COMPLETED** | `backend/app/safety/abstention.py` |
| **Prediction Endpoint (`POST /v1/predict`)** | **COMPLETED** | `backend/app/api/v1/endpoints/predict.py` |
| **Automated Backend Test Suite** | **COMPLETED** | 19 automated tests in `backend/tests/` |

---

## 3. What Was Actually Implemented

### A. FastAPI Application & Configuration (`backend/app/main.py`, `backend/app/core/config.py`)
- **What it is:** The central application factory and configuration manager.
- **Why it exists:** Configures CORS, sets service metadata, enables Swagger (`/docs`) and ReDoc (`/redoc`), and mounts versioned API routes.
- **What it currently does:** Starts the web server and serves root metadata and `/v1` routes.
- **What will connect to it later:** Production deployment servers, monitoring middleware, and the frontend client.

### B. Schemas & Data Contracts (`backend/app/schemas/prediction.py`, `backend/app/schemas/health.py`)
- **What it is:** Strict Pydantic models: `PredictionRequest`, `PredictionResponse`, `HealthResponse`, and enums (`TrustState`, `RiskLevel`, `ReasonCode`).
- **Why it exists:** Enforces clean data validation at the API boundary and guarantees consistent JSON shapes for frontend consumers and team integrations.
- **What it currently does:** Validates that `location` is non-empty (rejects blank strings, whitespace, nulls with HTTP 422) and serializes metadata.
- **What will connect to it later:** Frontend UI forms and dashboard displays.

### C. `ForecastBustAgent` Orchestrator (`backend/app/agents/forecast_bust_agent.py`)
- **What it is:** The central workflow orchestrator coordinating data ingestion, feature generation, model inference, safety evaluation, and response construction.
- **Why it exists:** Prevents API route handlers from being tightly coupled to data processing or ML inference logic.
- **What it currently does:** Executes a modular 6-stage pipeline (`resolve_request` -> `get_weather_data` -> `get_features` -> `run_model` -> `apply_safety` -> `build_response`).
- **What will connect to it later:** Builder 2's live weather collectors, feature extractors, and calibrated LightGBM/XGBoost models.

### D. Service Interfaces & Builder 2 Decoupling (`backend/app/services/base.py`, `model_service.py`, `weather_service.py`, `feature_service.py`)
- **What it is:** Abstract base classes (`BaseWeatherService`, `BaseFeatureService`, `BaseModelService`) and default unavailable implementations.
- **Why it exists:** Allows Builder 1 and Builder 2 to work concurrently without merge conflicts or code blocking.
- **What it currently does:** Provides safe fallback implementations that return explicit `is_ready=False` and `probability=None`.
- **What will connect to it later:** Builder 2's real model classes implementing `BaseModelService.predict()`.

### E. Safety & Abstention Engine (`backend/app/safety/abstention.py`)
- **What it is:** A safety decision engine (`SafetyEvaluator`) evaluating model readiness, data quality, and confidence bounds.
- **Why it exists:** Implements Veyra's core safety principle: **"Know when forecasts may fail, and know when the AI itself should abstain."**
- **What it currently does:** Catches missing/unready models and immediately triggers safe abstention (`abstain=True`, `trust_state="UNAVAILABLE"`, `reason_codes=["MODEL_NOT_READY"]`).
- **What will connect to it later:** Statistical out-of-distribution (OOD) detectors, ensemble spread thresholds, and data latency checks.

### F. API Endpoints (`backend/app/api/v1/endpoints/health.py`, `predict.py`)
- **What it is:** Versioned HTTP route handlers.
- **Why it exists:** Exposes RESTful endpoints for health monitoring and prediction queries.
- **What it currently does:** `GET /v1/health` returns status `ok`; `POST /v1/predict` runs `ForecastBustAgent.analyze()`.
- **What will connect to it later:** Web dashboard, CLI clients, and alert notification systems.

---

## 4. Current Architecture

```
                       +-----------------------------------+
                       |         User / Frontend           |
                       +-----------------------------------+
                                         |
                                         | HTTP (JSON)
                                         v
                       +-----------------------------------+
                       |        FastAPI Application        |
                       |       (backend/app/main.py)       |
                       +-----------------------------------+
                                         |
                        +----------------+----------------+
                        |                                 |
                        v                                 v
               GET /v1/health                     POST /v1/predict
             (Independent Status)             (Pydantic Validation)
                                                          |
                                                          v
                                              +-----------------------+
                                              |   ForecastBustAgent   |
                                              |    (Orchestrator)     |
                                              +-----------------------+
                                                          |
                      +-------------------+---------------+-------------------+
                      |                   |                                   |
                      v                   v                                   v
             +-----------------+ +-----------------+                 +-----------------+
             | BaseWeather     | | BaseFeature     |                 | BaseModel       |
             | Service         | | Service         |                 | Service         |
             | (Interface)     | | (Interface)     |                 | (Interface)     |
             +-----------------+ +-----------------+                 +-----------------+
                      |                   |                                   |
                      +-------------------+-----------------+                 |
                                                            |                 |
                                                            v                 v
                                                    +---------------------------------+
                                                    |         SafetyEvaluator         |
                                                    |  (Abstention / Trust Decisions) |
                                                    +---------------------------------+
                                                                    |
                                                                    v
                                                    +---------------------------------+
                                                    |       PredictionResponse        |
                                                    | (bust_probability: null,        |
                                                    |  trust_state: UNAVAILABLE,      |
                                                    |  abstain: true)                 |
                                                    +---------------------------------+
```

---

## 5. API Endpoints

| Endpoint | HTTP Method | Purpose | Current Status |
|---|:---:|---|:---:|
| `/v1/health` | `GET` | Service operational health check | **Active (HTTP 200)** |
| `/v1/predict` | `POST` | Evaluate forecast bust likelihood | **Active (Safe Abstain HTTP 200 / Validation HTTP 422)** |
| `/docs` | `GET` | Interactive Swagger UI API documentation | **Active (HTTP 200)** |
| `/redoc` | `GET` | ReDoc API documentation | **Active (HTTP 200)** |
| `/openapi.json` | `GET` | Raw OpenAPI schema | **Active (HTTP 200)** |

### Example Request (`POST /v1/predict`):
```json
{
  "location": "London",
  "target_date": "2026-09-01"
}
```

### Current Response (Safe Abstention State):
```json
{
  "location": "London",
  "bust_probability": null,
  "risk_level": null,
  "trust_state": "UNAVAILABLE",
  "abstain": true,
  "reason_codes": [
    "MODEL_NOT_READY"
  ],
  "model_version": null,
  "data_version": null
}
```

---

## 6. Current Prediction Behavior

The prediction endpoint currently returns `bust_probability: null`, `risk_level: null`, `trust_state: "UNAVAILABLE"`, and `abstain: true`.

### Why this is critical:
1. **Model Not Ready:** Builder 2's trained and calibrated machine learning model is currently in development.
2. **Strict "No Fake Predictions" Rule:** Veyra explicitly prohibits generating mock probabilities (e.g., hardcoding `0.72` or using `random.random()`).
3. **Semantic Distinction:**
   - `null` = Unknown / model unavailable / system abstaining.
   - `0.0` = The model asserts with 100% confidence that the forecast will NOT bust.
   - Returning `0.0` or fake numbers would deceive users and risk dangerous real-world misjudgments.

---

## 7. ForecastBustAgent

### What it is:
`ForecastBustAgent` is the core workflow coordinator for Veyra. It acts as the pipeline controller that receives incoming requests, invokes appropriate data extraction services, calls ML inference engines, routes the raw output through safety checks, and formats the response.

### Why we need an orchestration layer:
- **Separation of Concerns:** Keeps API endpoints thin and declarative.
- **Testability:** Each stage can be mocked, tested, or benchmarked independently.
- **Extensibility:** When Builder 2 completes the model or data collectors, they plug in without modifying route logic.

### What it currently does:
- Validates location and target date.
- Coordinates calls across `BaseWeatherService`, `BaseFeatureService`, `BaseModelService`, and `SafetyEvaluator`.
- Constructs a compliant `PredictionResponse`.

### What it does NOT do:
- It does not train ML models.
- It does not perform raw numerical array crunching.
- It does not invent or estimate probabilities on its own.

---

## 8. Builder 1 vs Builder 2 Boundary

| Area | Builder 1 (Current Role) | Builder 2 (Separate Role) |
|---|---|---|
| **API & Routing** | FastAPI endpoints, versioning, CORS, `/docs` | None |
| **Contracts & Schemas** | Pydantic Request/Response models | Follows Pydantic schemas |
| **Pipeline Control** | `ForecastBustAgent` orchestrator | None |
| **Data Collection** | Abstract `BaseWeatherService` interface | GEFS, ERA5, ECMWF live/historical collectors |
| **Feature Engineering** | Abstract `BaseFeatureService` interface | Atmospheric stability, ensemble spread vectors |
| **Bust Modeling** | Abstract `BaseModelService` interface | LightGBM / XGBoost model training & artifacts |
| **Probability Calibration**| Enforces calibrated output contract | Isotonic Regression / Platt Scaling |
| **Safety & Abstention** | `SafetyEvaluator` rules & abstention logic | OOD statistical metrics & thresholds |
| **Testing** | Endpoint, schema, and agent test suite | ML model validation & Brier score evaluation |

---

## 9. Testing Report

A test suite was developed and executed using `pytest`.

- **Total Tests:** 19
- **Tests Passed:** 19
- **Tests Failed:** 0
- **Execution Time:** ~0.11s

### Behaviors Verified:
1. `GET /v1/health` returns HTTP 200 with `status="ok"` and service name.
2. `POST /v1/predict` accepts valid locations and returns HTTP 200.
3. `bust_probability` is strictly `null` (`None`) while model is unready.
4. `abstain` is `true` and `trust_state` is `"UNAVAILABLE"`.
5. `"MODEL_NOT_READY"` is included in `reason_codes`.
6. Empty string, whitespace-only, and null locations are rejected with HTTP 422.
7. `ForecastBustAgent` unit tests verify both default unavailable state and mock model injection.
8. Pydantic schemas enforce type safety and JSON serialization.

---

## 10. Day Status

**STATUS: COMPLETE**

---

**Next:** [Day 2](./Day-2.md)

# Phase 2 — Builder 1 — Day 13
## Explainability Integration

---

## 1. Objective

The primary objective of Day 13 is to integrate the existing Builder 2 deterministic physical feature attribution capability into Builder 1's production application and API through a typed, safe, and stable integration boundary.

This layer serves as the authoritative explainability bridge that:
- Reuses and wraps the verified Builder 2 physical attribution engine (`ForecastBustExplainer`).
- Converts raw physical feature attributions into strongly typed Pydantic contracts (`ExplanationItem`, `ContributingFactor`).
- Enforces strict anti-data-leakage verification (ensuring zero observation, reference, or ground-truth features enter live explanations).
- Enforces numerical finiteness on feature values and contribution factors (rejecting / sanitizing NaN, $+ \infty$, $- \infty$).
- Preserves full backward compatibility with existing single (`POST /v1/predict`) and batch (`POST /v1/predict/batch`) prediction workflows.
- Implements fail-safe degradation: when predictions abstain or when explanations are unavailable, `explanation` safely degrades to `null` without fabricating explanations or throwing unhandled exceptions.
- Guarantees probability invariance: computing or enriching explanations does not alter the calibrated bust probability, trust state, or risk level.

---

## 2. Starting Baseline

- **Baseline Test Suite**: 203 passing tests (Day 12 Checkpoint).
- **Active ML Model**: `prototype-gbm-v1` (LightGBM Bust Classifier + Platt Sigmoid Calibrator).
- **Feature Schema**: `builder2-canonical-26-v1.0` (26 canonical issue-time features).
- **Decision Threshold**: $0.280$.

---

## 3. Architecture Overview

### Explainability Integration Pipeline
```
Forecast Request (Single or Batch)
        ↓
Dynamic Location Resolution (Day 8 DynamicLocationService)
        ↓
Resilient Weather Ingestion (Day 1 OpenMeteoGEFSWeatherService)
        ↓
Canonical Feature Extraction (Day 11 Builder2FeatureAdapter - 26 Canonical Features)
        ↓
Model Integration Gateway (Day 11 ModelIntegrationService)
        ↓
Active LightGBM Inference + Platt Sigmoid Calibration (Decision Threshold: 0.280)
        ↓
Explainability Integration Boundary (Day 13 ExplainabilityIntegrationService)
        ├── Anti-Leakage Audit (Strict rejection of ground-truth / ERA5 fields)
        ├── Numerical Finiteness Check (Sanitization of NaN / Inf values)
        ├── Deterministic Feature Signal Mapping (ForecastBustExplainer)
        ├── Standardized Typed Representation (ExplanationItem / ContributingFactor)
        └── Fail-Safe Error Isolation (Null on abstention / failure)
        ↓
Enriched Production Prediction Response (PredictionResponse with explanation)
```

---

## 4. Explainability Contracts and Schemas

Created in `backend/app/schemas/explainability.py`:

### `ContributingFactor` (Pydantic Model)
Represents individual canonical feature contributions:
- `factor` (`str`): Canonical feature identifier (e.g. `forecast_delta_24h`, `ensemble_std`, `lead_hours`, `ensemble_spread_delta_24h`).
- `value` (`Optional[float]`): Physical numerical value of the feature (strictly validated for finiteness; rounded to 4 decimal places).
- `signal` (`str`): Standardized physical signal category or interpretation code (e.g. `HIGH_REVISION_DRIFT`, `HIGH_ENSEMBLE_SPREAD`, `EXTENDED_RANGE_DEGRADATION`, `NO_PRIOR_CYCLE_BASELINE`).

### `ExplanationItem` (Pydantic Model)
Structured explanation container:
- `primary_driver` (`str`): Dominant physical risk driver identifier (e.g. `stable_ensemble_agreement`, `rapid_inter_cycle_revision`, `high_ensemble_uncertainty`, `extended_horizon_uncertainty`, `multi_factor_risk`).
- `driver_summary` (`str`): Model-grounded human-readable summary narrative explaining physical attribution signals.
- `top_contributing_factors` (`list[ContributingFactor]`): Ranked list of contributing factors and signals.

### `ExplainabilityStatus` (Enum)
- `AVAILABLE`: Valid physical attribution produced for active model prediction.
- `UNAVAILABLE`: Prediction abstained, features missing, or explainer unconfigured.
- `INCOMPATIBLE`: Features incompatible with canonical 26-feature schema.
- `INVALID`: Explainer output contains malformed or non-finite values.

### `ModelExplanationResponse` (Pydantic Model)
Standardized container packaging model metadata, explainability status, explanation item, and diagnostic reason codes.

---

## 5. Physical Contribution & Attribution Semantics

The explainability integration engine operates deterministically based on physical atmospheric dynamics at issue time:

| Feature Factor | Threshold / Condition | Signal Code | Physical Interpretation |
| :--- | :--- | :--- | :--- |
| `forecast_delta_24h` | $\| \Delta \| \ge 2.0$ unit | `HIGH_REVISION_DRIFT` | Rapid inter-cycle forecast revision indicating forecast volatility |
| `forecast_delta_24h` | $0.75 \le \| \Delta \| < 2.0$ | `MODERATE_REVISION_DRIFT` | Moderate run-to-run forecast adjustment |
| `forecast_delta_24h` | $\| \Delta \| < 0.75$ | `LOW_REVISION_DRIFT` | Stable run-to-run forecast consistency |
| `forecast_delta_24h` | `None` / `NaN` | `NO_PRIOR_CYCLE_BASELINE` | First cycle initialization (no prior 24h cycle available) |
| `ensemble_std` | $\sigma \ge 3.0$ unit | `HIGH_ENSEMBLE_SPREAD` | Severe physical ensemble dispersion among GEFS members |
| `ensemble_std` | $1.5 \le \sigma < 3.0$ | `ELEVATED_ENSEMBLE_SPREAD` | Moderate ensemble uncertainty |
| `ensemble_std` | $\sigma < 1.5$ | `LOW_ENSEMBLE_SPREAD` | Strong ensemble member clustering and consensus |
| `lead_hours` | $t \ge 168\text{h}$ (7+ days) | `EXTENDED_RANGE_DEGRADATION` | Predictability decay over extended horizon |
| `lead_hours` | $72\text{h} \le t < 168\text{h}$ | `MEDIUM_RANGE_HORIZON` | Medium-range horizon uncertainty |
| `lead_hours` | $t < 72\text{h}$ | `SHORT_RANGE_HORIZON` | High-skill short-range forecast window |
| `ensemble_spread_delta_24h` | $\Delta \sigma > 1.0$ | `SPREAD_GROWTH` | Rapid dispersion expansion over previous 24h |

---

## 6. Single and Batch Prediction Integration

### Single Prediction (`POST /v1/predict`)
- Successful predictions (`abstain=False`) return populated `explanation` object alongside `bust_probability`, `risk_level`, `trust_state`, and `reason_codes`.
- Abstained predictions (e.g. invalid location `'Atlantis'`) return `explanation=null` and `abstain=true` without fabricating explanations.

### Batch Prediction (`POST /v1/predict/batch`)
- Processes multiple locations with strict per-location failure isolation and deduplication.
- Valid locations (e.g. `London`, `Kolkata`) receive populated `explanation` objects.
- Invalid locations receive `explanation=null`.
- Input ordering and results alignment are preserved 1:1.

---

## 7. Anti-Leakage & Safety Verification

The Day 13 integration strictly enforces:
- **Zero Reference / Ground-Truth Leakage**: Rejects feature dictionaries containing forbidden fields (`observed_value`, `is_ground_truth_label`, `reference_val`, `reference_value`, `bust_label`, `actual_value`, `ground_truth`, `reference_records`, `era5`, `observation`, `forecast_error`, `absolute_error`).
- **Zero Traceback / Filesystem Path Leakage**: Internal explainer errors safely degrade to `explanation=null` with structured diagnostic reason codes.
- **Strict Finiteness**: Non-finite numerical feature values (NaN, $+ \infty$, $- \infty$) are sanitized or rejected before factor creation.
- **Model Invariance**: Probability calculation is completely decoupled from explanation generation; probabilities remain identical to 4 decimal places.

---

## 8. Files Created and Modified

### Created Files
- `backend/app/schemas/explainability.py`: Typed explainability contracts (`ContributingFactor`, `ExplanationItem`, `ExplainabilityStatus`, `ModelExplanationResponse`).
- `backend/app/services/explainability_service.py`: `ExplainabilityIntegrationService` providing feature validation, anti-leakage audit, and fail-safe explainer wrapping.
- `backend/tests/test_explainability_integration.py`: 20 comprehensive unit and integration tests.
- `Overview/Phase-2/Builder-1/Day-13.md`: This authoritative development log.

### Modified Files
- `backend/app/schemas/prediction.py`: Added `explanation: Optional[ExplanationItem] = None` to `PredictionResponse`.
- `backend/app/schemas/__init__.py`: Exported explainability schemas.
- `backend/app/services/__init__.py`: Exported explainability services.
- `backend/app/schemas/model_integration.py`: Expanded `FORBIDDEN_GROUND_TRUTH_FIELDS` security set.
- `backend/app/agents/forecast_bust_agent.py`: Integrated `ExplainabilityIntegrationService` into `build_response()` and `analyze()`.
- `backend/app/api/v1/endpoints/predict.py`: Updated `create_forecast_bust_agent` factory with optional explainability service injection.
- `Overview/Phase-2/Builder-1/Day-12.md`: Updated navigation forward link to Day 13.
- `Overview/README.md`: Added Day 13 to Phase 2 Builder 1 hierarchy and link list.
- `README.md`: Added Day 13 to project development documentation index.

---

## 9. Automated Verification Summary

| Suite / Test Category | Tests | Result | Execution Time |
| :--- | :---: | :---: | :---: |
| **Day 13 Dedicated Tests** (`test_explainability_integration.py`) | 20 | **PASS** | 33.52s |
| **Day 12 Evaluation Integration Tests** (`test_evaluation_integration.py`) | 19 | **PASS** | 0.22s |
| **Day 11 Model Integration Tests** (`test_model_integration.py`) | 20 | **PASS** | 5.25s |
| **Day 10 Multi-Location Tests** (`test_multi_location.py`) | 22 | **PASS** | 2.10s |
| **Day 9 Historical Data Tests** (`test_historical_data.py`) | 16 | **PASS** | 3.40s |
| **Day 8 Dynamic Location Tests** (`test_location_resolution.py`) | 15 | **PASS** | 1.80s |
| **Full Pytest Regression Suite** | **223** | **PASS** | **49.10s** |
| **Builder 2 Standalone Smoke Test** (`smoke_test_builder2.py`) | 16 Stages | **PASS** | 100% Operational |
| **Final System Readiness Smoke Test** (`smoke_test_final.py`) | 10 Phases | **PASS** | 100% Operational |
| **Historical Ingestion Smoke Test** (`smoke_test_historical.py`) | 6 Phases | **PASS** | 100% Operational |

---

## 10. Navigation

- **Previous**: [Day 12 — Evaluation Integration](./Day-12.md)
- **Next**: [Day 14 — Production API Hardening](./Day-14.md)

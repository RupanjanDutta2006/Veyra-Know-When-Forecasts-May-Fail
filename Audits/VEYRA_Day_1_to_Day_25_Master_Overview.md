# Veyra --- Day 1 to Day 25 Master Overview

## Project Purpose

**Veyra --- Know When Forecasts May Fail**

Veyra does **not** generate a new weather forecast. It analyzes an
existing forecast and estimates the **calibrated probability that the
forecast may fail unusually badly (a forecast bust)**.

### Core System Flow

``` text
Location
   ↓
Weather Forecast + Ensemble
   ↓
Standardization / Quality Control
   ↓
Feature Engineering
   ↓
V3 LightGBM
   ↓
Isotonic Calibration
   ↓
P(BUST)
   ↓
Risk + Trust + Abstention
   ↓
Explanation
   ↓
Dashboard Intelligence
   ↓
Frontend
```

------------------------------------------------------------------------

# Phase 1 --- Foundation (Day 1--7)

> **Note:** Day 1--7 are summarized as the early foundation/pipeline
> phase based on the available project history. Day 8--25 have more
> detailed verified day-specific records.

## Day 1 --- Problem Definition & Backend Foundation

**Purpose:** Define what Veyra predicts.

Normal weather forecasting asks **what the weather may be**. Veyra asks
**how likely an existing forecast is to fail unusually badly**.

``` text
Existing Forecast → Forecast Reliability Analysis → Bust Probability
```

## Day 2 --- Data Pipeline Foundation

**Purpose:** Establish the weather/ML data flow.

``` text
Forecast Data → Standardization → Historical Forecast + Reference → Forecast Error
```

Historical reference data is used for labeling/evaluation, not as future
information during live inference.

## Day 3 --- Canonical Data + Quality Control

Different source formats are standardized into a canonical Veyra
representation, followed by quality checks.

``` text
Provider Data → Standardization → Canonical Data → QC
```

## Day 4 --- Forecast Error & Bust Label Foundation

Historical forecast error is calculated from forecast and later
reference truth. Large errors form the BUST target.

Later Day 22 certification verified:

``` text
forecast_abs_error >= applied_threshold
```

## Day 5 --- Feature Engineering Foundation

Raw forecast, lead-time, ensemble, temporal, and derived information is
transformed into model features. This later evolved into the V3
**50-feature** contract.

## Day 6 --- Baseline ML / Evaluation Foundation

A Logistic Regression baseline established a simple comparison point
before advanced modeling.

## Day 7 --- Initial Pipeline Verification

Initial data → features → model → probability → API flow was smoke/unit
verified before productization.

------------------------------------------------------------------------

# Phase 2 --- Backend Productization (Day 8--20)

## Day 8 --- Dynamic Location Resolution

Removed hard-coded location dependence.

``` text
"Kolkata" → Location Resolver → Latitude/Longitude → Forecast Pipeline
```

**Verification:** focused 15/15; full suite 126.

## Day 9 --- Historical Data Infrastructure

Built infrastructure for larger historical forecast/reference workflows.

``` text
Historical Forecast + Historical Reference → Canonical Historical Records
```

**Verification:** focused 16/16; full 142.

## Day 10 --- Multi-Location Support

Added batch/multi-location processing.

``` text
Location A ─┐
Location B ─┼→ Multi-location Pipeline
Location C ─┘
```

**Verification:** focused 22/22; full 164.

## Day 11 --- ML Model Integration

Integrated the model into the backend service.

``` text
API Request → Features → Model Adapter → Prediction → API Response
```

**Verification:** focused 20; full 184.

## Day 12 --- Model Evaluation API

Added model-evaluation API support, including metrics such as Precision,
Recall, F1, ROC-AUC, PR-AUC, Brier Score, and calibration information.

``` text
GET /v1/model/evaluation
```

**Key lesson:** accuracy alone is insufficient for rare-event bust
prediction.

**Verification:** focused 19; full 203.

## Day 13 --- Explainability Integration

Added rule-based reason codes and explanations around prediction
results. The current explanation layer should **not** be described as
SHAP.

**Verification:** focused 20; full 223.

## Day 14 --- Production API Hardening

Added/strengthened: - Centralized error handling - Retry behavior -
Caching - Logging - Rate limiting - Configuration - Security/request
handling

**Verification:** focused 31; full 254; smoke suites passed.

## Day 15 --- Frontend Dashboard Foundation

Connected a React + TypeScript + Vite dashboard to backend APIs, with
location/variable/prediction/risk/explanation/evaluation handling.

Configuration includes:

``` text
VITE_API_BASE_URL
```

422/429, loading/error, and stale-result behavior were addressed.

**Verification:** frontend 27/27; backend 255/255; build PASS.

## Day 16 --- Forecast Risk Timeline

Added horizon-wise risk visualization.

``` text
24h → 48h → 72h → ... → horizon-wise risk
```

Wind-unit and abstention/safety-precedence issues were also fixed.

**Verification:** frontend 51/51; backend 208/208 deterministic suite.

## Day 17 --- Cache + SingleFlight

Reduced duplicate upstream requests.

``` text
First request → Provider → Cache
Later related request → Cache
```

SingleFlight coalesces concurrent requests for the same underlying data
into one upstream fetch. Retry-After behavior was improved.

**Verification:** backend 278/278; dedicated 16/16; frontend 51/51.

## Day 18 --- Production / Deployment Readiness

Prepared HOST, PORT, CORS, environment variables, same-origin `/v1/*`,
`/dashboard/`, portable paths, and deployment configuration.

This was deployment readiness, not a claim of external production
deployment.

**Verification:** backend 292/292; deployment 14/14; frontend 51/51.

## Day 19 --- Observability

Added:

``` text
GET /v1/metrics
```

Metrics cover operational areas such as HTTP activity, errors,
predictions, abstentions, upstream failures/429s, cache activity,
SingleFlight, and retries.

## Day 20 --- Cross-Phase Verification

Verified health, predictions, dashboard behavior, invalid locations,
temperature/wind flows, 7-day/16-day modes, metrics, and abstention.

**Verification:** targeted 9/9; backend 319/319; frontend 51/51;
build/smokes/manual checks passed.

------------------------------------------------------------------------

# Phase 3 --- Scientific V3 Integration (Day 21--25)

## Day 21 --- V3 Model Integration

Integrated Builder 2's frozen V3 model into Builder 1's live backend.

``` text
Live Weather
→ 31-member Ensemble
→ V3 Feature Adapter
→ 50 Features
→ LightGBM V3
→ Isotonic Calibration
→ Calibrated P(BUST)
```

### Unit compatibility

-   Temperature → Kelvin
-   Wind → m/s
-   Pressure → Pa

If the V3/calibration path cannot produce a trustworthy normal result,
the system safely abstains instead of silently serving an inappropriate
fallback/raw output.

A post-merge repair corrected the default Single Target to a positive
canonical **24h** lead.

**Meaning:** **Day 21 = Integrate V3.**

## Day 22 --- Dataset, Label & Leakage Certification

Scientifically audited the frozen dataset and methodology without
retraining.

### Dataset

-   780,000 canonical rows
-   1040 forecast cycles
-   25 stations
-   3 variables
-   10 lead horizons

### Chronological split

-   2000--2013 → Train
-   2014--2016 → Validation
-   2017--2019 → Test

### Label

``` text
forecast_abs_error >= applied_threshold
```

The audit found **no mechanical leakage in the frozen authoritative
pipeline**, with documented generalization limitations.

**Meaning:** **Day 22 = Certify the data.**

## Day 23 --- Model Championship & Retraining Decision

Compared V3 against eligible alternatives on the frozen Test benchmark.

### V3 headline results

-   Average Precision ≈ 0.2047
-   PR-AUC ≈ 0.2124
-   ROC-AUC ≈ 0.7698
-   Brier Score ≈ 0.0538
-   ECE ≈ 0.0064

Paired cycle-block bootstrap analysis was also used.

### Decision

``` text
RETAIN_WITH_TARGETED_FOLLOWUP
```

V3 was retained with no immediate retraining.

### Limitations

-   Historical ensemble N=5 vs live N=31 remains uncertified operational
    equivalence.
-   Post-2019 performance is not certified by the frozen benchmark.
-   Unseen-station/general geographic performance is not fully
    certified.

**Meaning:** **Day 23 = Compare and retain V3.**

## Day 24 --- Probabilistic Intelligence

Hardened probability serving and safety semantics.

``` text
GET /v1/model/evaluation/v3
```

``` text
LightGBM Raw Output → Isotonic Calibration → Calibrated P(BUST)
```

If calibration fails, raw output is not silently presented as calibrated
probability; the system safely abstains.

### Operational Risk Tiers

-   P \< 0.20 → LOW
-   0.20 ≤ P \< 0.50 → MEDIUM
-   0.50 ≤ P \< 0.75 → HIGH
-   P ≥ 0.75 → CRITICAL

OOD semantics and explanation consistency were clarified/repaired.

**Verification:** backend 398/398; frontend 55/55; build PASS.

**Meaning:** **Day 24 = Trust the probability.**

## Day 25 --- Intelligence Dashboard Backend

Created the centralized frontend intelligence contract:

``` text
POST /v1/dashboard/intelligence
```

### Modes

-   `single` → 24h
-   `standard_7d` → 24, 48, 72, 96, 120, 144, 168h
-   `full_16d` → 24-hour increments through 384h

### Response concept

-   Selected prediction
-   Timeline
-   Summary
-   Bust probability
-   Risk
-   Calibration status
-   Trust state
-   Abstention
-   Reason codes
-   Explanation
-   Decision guidance
-   Model/data version
-   Scientific context

### Invalid-location safety

``` text
Atlantis → ABSTAINED / UNAVAILABLE
Probability = null
Risk = null
```

No fake `0%` or `LOW`.

### Horizon scope

``` text
≤240h → within frozen historical benchmark lead scope
264–384h → operational-only extension
```

**Verification at Day 25 freeze:** backend 428 tests PASS; frontend 55
tests PASS; production build PASS.

**Meaning:** **Day 25 = Deliver intelligence to the frontend.**

------------------------------------------------------------------------

# New Frontend Integration After Day 25

The newer standalone frontend was integrated with the authoritative
Veyra backend.

``` text
New Veyra Frontend
       ↓
Dashboard Intelligence API
       ↓
Current V3 Backend
```

The integrated frontend represents areas such as: - Reliability
Sentinel - Batch Evaluation - Model Registry - Location/station
selection - Coordinate support where allowed - Meteorological variable
selection - Horizon modes - Forecast map - Forecast-bust risk timeline -
Bust probability - Risk tier - Stability/diagnostics - Trust state -
Explainability - Calibration - Scientific information - Safe abstention

The backend remains the scientific/API source of truth.

------------------------------------------------------------------------

# Day 1--25 Quick Revision Table

  Day   Main Work                        Easy Memory
  ----- -------------------------------- --------------------------
  1     Problem/backend foundation       Define Veyra
  2     Data pipeline foundation         Forecast data flow
  3     Canonical data + QC              Standardize/check data
  4     Error + bust-label foundation    Define failure target
  5     Feature foundation               Build ML inputs
  6     Baseline/evaluation foundation   Establish comparison
  7     Initial pipeline verification    Test foundation
  8     Dynamic location                 Resolve locations
  9     Historical infrastructure        Historical data
  10    Multi-location                   Batch locations
  11    ML integration                   Model → Backend
  12    Evaluation API                   Measure model
  13    Explainability                   Explain result
  14    API hardening                    Production safety
  15    Dashboard                        Backend → UI
  16    Risk timeline                    Horizon-wise risk
  17    Cache + SingleFlight             Efficient upstream use
  18    Deployment readiness             Production configuration
  19    Metrics                          Observe backend
  20    Cross-phase verification         Verify Phase 2
  21    V3 integration                   Integrate ML brain
  22    Dataset/leakage audit            Trust the data
  23    Model championship               Compare/trust model
  24    Probabilistic intelligence       Trust probability
  25    Intelligence Dashboard API       Deliver intelligence

------------------------------------------------------------------------

# Day 21--25 Memory Shortcut

``` text
DAY 21 → INTEGRATE
DAY 22 → CERTIFY
DAY 23 → COMPARE
DAY 24 → CALIBRATE + TRUST
DAY 25 → DELIVER
```

------------------------------------------------------------------------

# Complete Backend Runtime Story

``` text
User selects location + variable + mode
              ↓
        Request Validation
              ↓
       Location Resolution
              ↓
   Live Forecast + Ensemble Data
              ↓
     Standardization + QC
              ↓
       Feature Engineering
              ↓
         50 V3 Features
              ↓
          LightGBM V3
              ↓
        Raw Model Output
              ↓
      Isotonic Calibration
              ↓
       Calibrated P(BUST)
              ↓
       Risk Classification
              ↓
      Trust / Safety Checks
              ↓
   Normal Result OR Safe Abstention
              ↓
     Explanation + Reason Codes
              ↓
      Dashboard Intelligence
              ↓
            Frontend
```

------------------------------------------------------------------------

# Main Algorithms

## 1. LightGBM

Veyra's main prediction algorithm. It is a gradient-boosted
decision-tree model that processes the V3 50-feature vector and learns
nonlinear relationships associated with historical forecast busts.

## 2. Isotonic Calibration

Applied after LightGBM to convert/model-map its output into a
better-calibrated probability.

  LightGBM                    Isotonic Calibration
  --------------------------- ------------------------------------
  Main predictor              Probability calibrator
  Uses V3 features            Uses model output
  Learns bust-risk patterns   Adjusts probability interpretation
  Produces model output       Produces calibrated probability

------------------------------------------------------------------------

# Important Scientific Meanings

**Weather Value:** forecasted meteorological quantity.

**Forecast Error:** difference between a historical forecast and later
reference truth.

**Bust Label:** whether historical absolute error met/exceeded the
defined threshold.

**P(BUST):** model-estimated calibrated probability of a bust under
Veyra's defined semantics.

**Risk Level:** operational product tier derived from P(BUST).

**Trust / Abstention:** whether Veyra is willing to issue normal
reliability intelligence.

A `70% P(BUST)` does **not** mean 70% chance of rain, 70% chance of a
weather event, or 70% forecast accuracy.

------------------------------------------------------------------------

# Project in One Paragraph

Veyra began by defining forecast-bust prediction and building the
foundations for historical forecast/reference data, error labels,
feature engineering, baseline modeling, and backend inference. The
backend was then productized through dynamic location resolution,
multi-location processing, model integration, evaluation,
explainability, production hardening, caching, SingleFlight, deployment
readiness, observability, and cross-phase verification. In the
scientific V3 phase, the frozen V3 LightGBM model and isotonic
calibrator were integrated into the live backend, the
dataset/label/leakage methodology was audited, V3 was benchmarked
against eligible alternatives, calibrated-probability and
safe-abstention contracts were hardened, and a centralized Dashboard
Intelligence API was created. The frontend can consume this intelligence
to present forecast-bust probability, operational risk, horizon
timelines, trust/abstention states, explanations, and scientific context
without recreating scientific logic in the client.

------------------------------------------------------------------------

# Four-Layer Memory Model

``` text
FOUNDATION / DATA
Day 1–10
      ↓
BACKEND + PRODUCT
Day 11–20
      ↓
SCIENTIFIC V3
Day 21–24
      ↓
INTELLIGENCE DELIVERY
Day 25 + Integrated Frontend
```

------------------------------------------------------------------------

## Judge/Team One-Line Summary

> **Veyra is a forecast-reliability intelligence system that uses a V3
> LightGBM model with isotonic probability calibration to estimate the
> probability that an existing weather forecast may fail unusually
> badly, while adding operational risk classification, safe abstention,
> explanations, horizon-wise intelligence, and a centralized backend
> contract for frontend delivery.**

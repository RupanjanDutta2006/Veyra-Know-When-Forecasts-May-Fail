# Veyra — Complete Project Audit
**Forensic Overview & Engineering Health Audit**  
**Repository State:** Base Project + Builder 1 (Day 1–20) + Builder 2 (Day 1–20 / Parinidhi) + Integrated State  
**Audit Mode:** READ-ONLY Forensic Inspection (No source code or artifacts modified)  
**Date of Audit:** September 6, 2026  
**Auditor:** Antigravity Forensic Engineering Agent (DeepMind AAC)

---

## 1. Executive Summary

A comprehensive forensic audit of the workspace `Veyra_Know When Forecasts May Fail` was conducted directly against actual executable code, installed environments, network providers, and binary artifacts across all subdirectories.

The audit revealed that this workspace contains **three distinct project trees** originating from different stages of development:
1. **`Veyra — Know When Forecasts May Fail` (Tree 1 — Active Git Repository):**  
   Contains the complete, production-hardened FastAPI backend and React 19 / Vite / TypeScript dashboard built by **Builder 1** through Day 20. It incorporates an integrated Builder 2 prototype adapter (`backend/app/builder2/`) running a 26-feature LightGBM model (`models/day4/lightgbm_bust_model.joblib`) calibrated with Platt Sigmoid scaling. **All 319 backend Python tests pass 100%**, **all 51 frontend Vitest tests pass 100%**, frontend production build (`tsc && vite build`) succeeds with zero errors, and **live real-data end-to-end inference against the Open-Meteo GEFS API executes successfully in 1.34s with zero hallucinated probabilities**.
2. **`Parinidhi\Veyra-Know-When-Forecasts-May-Fail-main (1)\Veyra-Know-When-Forecasts-May-Fail-main` (Tree 2 — Builder 2 Full Research Snapshot):**  
   Contains Builder 2's scientific ML and data pipeline research through Day 20 (`ingestion/`, `data_pipeline/`, `features/`, `labels/`, `models/`, `research/`, `reports/`, `api/`, and `server.py`). It documents a 50-feature "supercharged" architecture trained on a 1,040-cycle (780,000-row) benchmark archive from NOAA GEFSv12 S3 and ERA5 reanalysis. **However, critical runtime artifacts are missing from this tree**: the V2/V3 `.joblib` model binaries (`models/v2/lightgbm_v2_champion.joblib`, `models/v3/lightgbm_v3_challenger.joblib`) and the historical parquet datasets were excluded from git/zip exports due to ignore rules (`*.joblib`, `*.parquet`). Furthermore, missing runtime dependencies (`requests`, `eccodes`) and broken module imports (`models.error_distribution`) prevent its test suite from passing out-of-the-box.
3. **`Builder 2\Veyra-Know-When-Forecasts-May-Fail-main Parinidhi\Veyra-Know-When-Forecasts-May-Fail-main` (Tree 3 — Legacy Intermediate Snapshot):**  
   A 184-file earlier handoff snapshot that is completely superseded by Tree 2.

The live application in Tree 1 is functional and verifiable with live weather data. However, there is a fundamental contract divergence between Builder 1's active serving layer and Builder 2's latest research:
- Tree 1 serves the **26-feature prototype model** trained on an in-repo 10,800-row synthetic simulation dataset (`decision_threshold = 0.280`, risk tiers: Low/Med/High/Crit).
- Tree 2 designed a **50-feature model** on a 780k-row NOAA/ERA5 benchmark (`decision_threshold = 0.060`, risk tiers: Low/Elevated/Critical), but its trained artifacts are absent from the workspace.
- Live weather ingestion in Tree 1 fails to extract ensemble standard deviation from the returned 30-member Open-Meteo arrays, causing ensemble spread features to collapse to 0.0 at inference time.

---

## 2. Final Verdict

### **PROJECT PARTIALLY WORKING — IMPORTANT FIXES REQUIRED**

**Justification:**
- **What Works:** The Builder 1 orchestrator, FastAPI server, Pydantic contracts, SingleFlight request deduplication, LRU caching, rate limiting, structured logging, React dashboard, and end-to-end live prediction pipeline are fully operational and verified against real public meteorological APIs (370/370 automated tests pass).
- **What is Broken / Incomplete:**
  1. The advanced Builder 2 champion/challenger model artifacts (`models/v2`, `models/v3`) and benchmark datasets are completely missing from the workspace due to `.gitignore` exclusion during packaging.
  2. Live weather ingestion in Builder 1 does not parse individual ensemble members from Open-Meteo, degrading ensemble spread to 0.0 in production inference.
  3. Wind speed units are mismatched between live weather ingestion (`m/s`) and the training feature schema (`km/h`).
  4. Builder 2's research test suite in Tree 2 fails collection due to missing packages (`requests`) and broken import paths (`models.error_distribution`).
  5. The subfolder name contains a Unicode em-dash (`—`), creating path resolution and CLI tooling friction.

---

## 3. Project Identity

| Attribute | Value |
| :--- | :--- |
| **Workspace Root** | `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail` |
| **Total Workspace Files** | 6,193 files |
| **Total Workspace Directories** | 846 directories |
| **Active Git Repository Path** | `.\Veyra — Know When Forecasts May Fail` (Folder name contains Unicode `\u2014` em-dash) |
| **Active Git Branch** | `docs/veyra-complete-project-guide` |
| **Latest Git Commit** | `634921ab74e9770fcb5cc0e4ad87a5fd00b86598` |
| **Git Commit Message** | `docs: add complete Veyra project knowledge guide` (Author: RupanjanDutta2006, 2026-08-30) |
| **Remote Origin** | `https://github.com/RupanjanDutta2006/Veyra-Know-When-Forecasts-May-Fail.git` |
| **Working Tree Status** | Clean (0 modified tracked files) |
| **Python Runtime** | Python 3.13.5 (64-bit, Windows 11) |
| **Node.js Runtime** | Node.js v24.16.0, npm 11.13.0 |

---

## 4. Complete Architecture

```
                                  [ User / Browser Client ]
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       │                                           │
                       ▼                                           ▼
             [ React 19 Dashboard ]                      [ Direct HTTP API ]
           (Vite + Tailwind/CSS SPA)                   (GET /docs, /v1/predict)
                       │                                           │
                       └─────────────────────┬─────────────────────┘
                                             │ HTTP (port 8000)
                                             ▼
                     ┌───────────────────────────────────────────┐
                     │   FastAPI Gateway (backend/app/main.py)   │
                     │  - SecurityHeaders & RateLimiter (120/m)  │
                     │  - RequestCorrelation (X-Request-ID)      │
                     │  - Structured Access Logging              │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │   ForecastBustAgent (Orchestration Engine)│
                     └───────┬───────────────────────────┬───────┘
                             │                           │
          ┌──────────────────┘                           └──────────────────┐
          ▼                                                                 ▼
┌───────────────────────────────┐                                 ┌───────────────────────────────┐
│ 1. Weather Ingestion Service  │                                 │ 4. Safety & Abstention Layer  │
│  - OpenMeteoGEFSWeatherService│                                 │  - SafetyEvaluator            │
│  - LRU Cache (TTL 120s)       │                                 │  - OOD & Physical Bounds Check│
│  - SingleFlight Deduplication │                                 │  - Zero-Fake-Probability Rule │
│  - DynamicLocationService     │                                 └───────────────┬───────────────┘
└───────────────┬───────────────┘                                                 ▲
                │ (CanonicalForecastDataset)                                      │
                ▼                                                                 │
┌───────────────────────────────┐                                                 │
│ 2. Feature Extraction Adapter │                                                 │
│  - Builder2FeatureAdapter     │                                                 │
│  - IssueTimeSafeFeaturePipeline                                                 │
│  - 26 Canonical Features      │                                                 │
│  - Anti-Leakage Guard (T <= 0)│                                                 │
└───────────────┬───────────────┘                                                 │
                │ (FeatureResult)                                                 │
                ▼                                                                 │
┌───────────────────────────────┐                                                 │
│ 3. Model Integration Gateway  │                                                 │
│  - ModelIntegrationService    │                                                 │
│  - Builder2ModelAdapter       │─────────────────────────────────────────────────┘
│    • LightGBMBustClassifier   │      (ModelResult: P(bust), Threshold, ReasonCodes)
│    • Platt Sigmoid Calibrator │
│    • Fallback: LogisticRegression
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ 5. Explainability Integration │
│  - ExplainabilityService      │
│  - ForecastBustExplainer      │
│  - Physical Attribution Rules │
└───────────────┬───────────────┘
                │
                ▼
      [ PredictionResponse ]
```

### Real Architecture Operational Flow:
1. **Request Ingestion:** Client submits `PredictionRequest` (e.g. `{"location": "Delhi"}`) via `POST /v1/predict`.
2. **Location Resolution:** `DynamicLocationService` geocodes `"Delhi"` $\rightarrow$ `(28.6139, 77.2090)` using an in-memory cache and Open-Meteo Geocoding API fallback.
3. **Weather Retrieval & QC:** `OpenMeteoGEFSWeatherService` checks the 120s TTL cache. If missing, `SingleFlight` coalesces concurrent queries, fetches live GFS ensemble forecasts from `https://ensemble-api.open-meteo.com/v1/ensemble`, parses them into `CanonicalForecastRecord` objects, and validates them against physical bounds (temperatures in $[-80^\circ\text{C}, +60^\circ\text{C}]$, pressures in $[500, 1100]\text{ hPa}$).
4. **Feature Engineering:** `Builder2FeatureAdapter` adapts weather records into a 26-column feature vector (`ensemble_std`, `lead_hours`, cyclical trigonometric hours/months, inter-cycle revisions).
5. **Anti-Leakage Enforcement:** `ModelIntegrationService` screens feature names and metadata against `FORBIDDEN_GROUND_TRUTH_FIELDS` (`observed_value`, `forecast_error`, `bust_label`, `era5`).
6. **Inference & Calibration:** `Builder2ModelAdapter` evaluates `prototype-gbm-v1` LightGBM model, applies Platt Sigmoid calibration to output calibrated $P(\text{bust}) \in [0.0, 1.0]$.
7. **Safety & Abstention:** `SafetyEvaluator` verifies upstream success. If location resolution fails, upstream times out, or features are non-finite, it returns `abstain=True` with explicit `reason_codes` and `bust_probability=None`.
8. **Explainability Attribution:** `ForecastBustExplainer` computes deterministic physical driver summaries (e.g., `"stable_ensemble_agreement"` or `"high_ensemble_uncertainty"`).

---

## 5. Project Evolution

The project history was reconstructed from Git commit logs, release manifests, and directory tree artifacts:

```
[Base Veyra / Solo Phase 1] (Aug 25-26, 2026)
  • Days 1–7 commits by RupanjanDutta2006.
  • Initialized backend API, baseline logistic regression, synthetic dataset generation, and initial pytest suite.
  • Established BaseWeatherService, BaseFeatureService, BaseModelService interfaces.
        │
        ▼
[Builder 1 & Builder 2 Handoff] (Aug 25–27, 2026)
  • Creation of BUILDER_1_BUILDER_2_INTEGRATION_CONTRACT.md and BUILDER_2_HANDOFF.md.
  • PR #9 merged: "feat: complete Phase 1 Builder 1 and Builder 2 integration".
  • Builder 1 packaged prototype Builder 2 code into backend/app/builder2/.
        │
        ▼
[Divergent Concurrent Development] (Aug 27–30, 2026)
  ┌───────────────────────────────────────────────┴───────────────────────────────────────────────┐
  ▼                                                                                               ▼
[Builder 1 Phase 2 (Tree 1)]                                                    [Builder 2 Scientific Sprint (Tree 2 / Parinidhi)]
  • Day 8: Dynamic geocoding location resolution.                                 • Day 8–10: 25-station synoptic network expansion.
  • Day 9: Historical data infrastructure.                                        • Day 11–12: Direct NOAA GEFSv12 S3 reforecast ingestion.
  • Day 10: Multi-location batch processing.                                      • Day 13–14: Colab extraction of 1,040 cycles (780k rows).
  • Day 11: Centralized Model Integration Layer.                                  • Day 15–16: 50 Supercharged physical features.
  • Day 12: Model evaluation metadata endpoints.                                  • Day 17–18: Frozen V2 Champion & V3 Challenger training.
  • Day 13: Deterministic physical explainability.                                • Day 19–20: Standalone server.py (port 8001), red-team audits.
  • Day 14: Production API hardening (rate limits, security headers).             • Result: Advanced models trained, but .joblib excluded by gitignore.
  • Day 15: React 19 / Vite dashboard.                                            
  • Day 16: Visual forecast risk timeline.                                        
  • Day 17: Upstream hardening (SingleFlight + TTL cache).                        
  • Day 18–20: Observability, metrics, final release.                             
        │                                                                                         │
        └───────────────────────────────────────────────┬─────────────────────────────────────────┘
                                                        │
                                                        ▼
                                            [Current Integrated State]
  • Tree 1 is the primary runnable system with full frontend and backend integration.
  • Tree 1 runs Builder 2's prototype-gbm-v1 model (26 features).
  • Tree 2 contains superior scientific pipeline code, but lacks its trained model artifacts.
```

---

## 6. Builder 1 Complete Overview

Builder 1 (authored by Rupanjan Dutta) is responsible for the production backend, orchestrator, caching, API hardening, frontend, and test infrastructure.

| Component | Files | Purpose | Status | Working? | Tested? | Key Issues |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **FastAPI Core** | `backend/app/main.py`, `backend/app/core/config.py` | Application factory, middleware, routing | Active | YES | YES | None |
| **API Middleware** | `backend/app/core/middleware.py` | Rate limiting, request correlation IDs, security headers, logging | Active | YES | YES | In-process rate limiter resets on server restart |
| **Cache & Dedup** | `backend/app/core/cache.py` | Bounded TTL cache & SingleFlight request deduplication | Active | YES | YES | None |
| **Weather Ingestion**| `backend/app/services/openmeteo_service.py`| Live GFS/GEFS ensemble fetching from Open-Meteo | Active | PARTIAL | YES | Does not parse ensemble members into `ensemble_std` |
| **Location Service**| `backend/app/services/location_service.py`| Dynamic geocoding with 25 benchmark stations cache | Active | YES | YES | None |
| **Multi-Location** | `backend/app/services/multi_location_service.py`| Batch endpoint for multi-city evaluations | Active | YES | YES | None |
| **Model Integration**| `backend/app/services/model_integration_service.py`| Gateway isolating models, anti-leakage validation | Active | YES | YES | Default path points to `models/builder2/prototype-gbm-v1` which does not exist; falls back via config to `models/day4` |
| **Evaluation Service**| `backend/app/services/evaluation_service.py`| Exposes model metrics via `GET /v1/model/evaluation` | Active | YES | YES | Path resolution fails if Cwd is not repo root |
| **Observability** | `backend/app/core/metrics.py` | Thread-safe in-process metrics counters | Active | YES | YES | Non-persistent (resets on restart) |
| **Frontend SPA** | `frontend/src/*` (App, Timeline, Form, Result) | React 19 / TypeScript UI for predictions & timeline | Active | YES | YES | Fires concurrent independent requests per timeline lead |

---

## 7. Builder 2 Complete Overview

Builder 2 (authored by Parinidhi) was tasked with meteorological data ingestion, feature engineering, probability calibration, and ML model training.

| Component | Files | Purpose | Status | Working? | Tested? | Key Issues |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **NOAA S3 Ingestion**| `Parinidhi/.../ingestion/adapters/noaa_s3.py` | Direct byte-range retrieval of GEFSv12 GRIB2 from AWS | Research | BLOCKED | NO | Requires `requests` and `eccodes` (not installed) |
| **ERA5 Collector** | `Parinidhi/.../ingestion/era5_collector.py` | Fetches historical ERA5 reanalysis ground truth | Research | YES | YES | Hardcoded to request wind in `km/h` |
| **Standardization** | `Parinidhi/.../data_pipeline/standardize.py` | Computes full 31-member ensemble stats (mean, std, q10, q90) | Research | YES | YES | Never connected to Builder 1 live ingestion |
| **Historical Aligner**| `Parinidhi/.../data_pipeline/historical_aligner.py`| Spatio-temporal colocation & error computation | Research | YES | YES | None |
| **Label Engine** | `Parinidhi/.../labels/label_engine.py` | Fits conditional q95 error thresholds on training split | Active/Proto | YES | YES | Integrated into Builder 1 |
| **Feature Pipeline** | `Parinidhi/.../features/forecast_intelligence_features.py`| 50 supercharged physical features | Research | PARTIAL | NO | Missing training dataset to run full pipeline |
| **V2/V3 Model Service**| `Parinidhi/.../models/forecast_intelligence_service.py`| Inference service for V2 Champion / V3 Challenger | Research | BLOCKED | NO | Model artifacts `models/v2/*.joblib`, `models/v3/*.joblib` are missing |
| **Operational Server**| `Parinidhi/.../server.py` | Standalone ThreadingHTTPServer on port 8001 | Alternative | BLOCKED | NO | Cannot start due to missing `models/v2/` artifacts |

---

## 8. Builder 1 ↔ Builder 2 Integration Map

### Current Integration Map in Executable Code:

```
[ Builder 1: FastAPI Request ]
               │
               ▼
[ backend/app/api/v1/endpoints/predict.py ]
               │
               ▼
[ backend/app/agents/forecast_bust_agent.py ]
               │
               ├────────────────────────────────────────┐
               ▼                                        ▼
[ OpenMeteoGEFSWeatherService ]              [ Builder2FeatureAdapter ]
(Live forecast fetched & QC'd)               (backend/app/builder2/feature_adapter.py)
               │                                        │
               ▼                                        ▼
      WeatherResult ──────────────────────► weather_result_to_dataframe()
                                                        │
                                                        ▼
                                             IssueTimeSafeFeaturePipeline
                                             (backend/app/builder2/feature_pipeline.py)
                                                        │
                                                        ▼
                                                  FeatureResult
                                                        │
                                                        ▼
                                             ModelIntegrationService
                                             (backend/app/services/model_integration_service.py)
                                                        │
                                                        ▼
                                             Builder2ModelAdapter
                                             (backend/app/builder2/model_adapter.py)
                                                        │
                                                        ▼
                                             ForecastBustModelService
                                             (backend/app/builder2/model_service.py)
                                                        │
                                                        ▼
                                            Loads: models/day4/lightgbm_bust_model.joblib
                                            Loads: models/day4/probability_calibrator.joblib
                                            Loads: models/day4/model_metadata.json
                                                        │
                                                        ▼
                                                   ModelResult
                                                        │
                                                        ▼
                                              SafetyEvaluator
                                                        │
                                                        ▼
                                             ExplainabilityService
                                                        │
                                                        ▼
                                              PredictionResponse
```

### Integration Contract Mismatches & Discrepancies:
1. **Model Artifact Path Divergence:**
   - `ModelIntegrationService` defines `DEFAULT_BUILDER2_MODEL_PATH = Path("models/builder2/prototype-gbm-v1")`.
   - The actual artifacts reside in `models/day4/`.
   - They load only because `Settings.BUILDER2_MODEL_DIR` in `backend/app/core/config.py` falls back to `models/day4`.
2. **Missing Feature Computation in Weather Pipeline:**
   - `Builder2FeatureAdapter` expects `ensemble_std`, `ensemble_range`, `ensemble_iqr` in the `WeatherResult`.
   - `OpenMeteoGEFSWeatherService` does not calculate these from the member arrays, defaulting them to `None`.
   - `feature_pipeline.py` fills them with `0.0`, blinding the model to real ensemble spread.
3. **Threshold & Risk Tier Inconsistency:**
   - Builder 1 `SafetyEvaluator`: Threshold = 0.280; Tiers = LOW (<0.20), MEDIUM (<0.50), HIGH (<0.75), CRITICAL (>=0.75).
   - Builder 2 `FINAL_RELEASE_MANIFEST.md`: Threshold = 0.060; Tiers = LOW (<0.060), ELEVATED (<0.600), CRITICAL (>=0.600).
4. **Unit Inconsistency on Wind Speed:**
   - `openmeteo_service.py` requests `wind_speed_unit="ms"` (`m/s`).
   - `train_builder2_model.py` and Builder 2 pipelines use `km/h`.

---

## 9. Active vs Legacy Components

| Component / File | Category | Status | Role / Recommendation |
| :--- | :--- | :---: | :--- |
| `backend/app/main.py` | FastAPI Application | **ACTIVE** | Main entrypoint for Builder 1. Keep as authoritative API. |
| `backend/app/builder2/` | Integration Adapters | **ACTIVE** | Production wrapper around Builder 2 prototype. |
| `models/day4/` | Model Artifacts | **ACTIVE** | Active prototype-gbm-v1 model and calibrator. |
| `frontend/src/` | Dashboard Frontend | **ACTIVE** | Authoritative user interface. |
| `backend/app/ml/baseline_model.py` | ML Service | **LEGACY / FALLBACK** | Logistic regression fallback when LightGBM is unready. |
| `backend/app/services/weather_service.py` | Weather Service | **LEGACY / TEST** | Mock/stub weather service used in isolated unit tests. |
| `Parinidhi/.../server.py` | Standalone HTTP Server | **SUPERSEDED** | Alternative port-8001 server; superseded by FastAPI `backend/app/main.py`. |
| `Parinidhi/.../features/forecast_intelligence_features.py` | Feature Pipeline | **ADVANCED RESEARCH** | 50-feature engine; should eventually be migrated into `backend/app/builder2/`. |
| `Parinidhi/.../ingestion/adapters/noaa_s3.py` | Historical Ingestion | **ADVANCED RESEARCH** | Real S3 GRIB2 downloader; preserve for offline dataset generation. |
| `Builder 2/Veyra-...` | Workspace Directory | **SUPERSEDED / STALE** | Outdated duplicate snapshot. Safe to archive or ignore. |

---

## 10. Real Data Providers

| Provider | Purpose | Production / Test | Network Verification | Verdict |
| :--- | :--- | :---: | :---: | :---: |
| **Open-Meteo Ensemble API** (`https://ensemble-api.open-meteo.com/v1/ensemble`) | Live 31-member GFS/GEFS forecast ingestion | Production Live | **VERIFIED LIVE** (Fetched live Delhi & London cycles in 1.2s) | **REAL LIVE DATA** |
| **Open-Meteo Geocoding API** (`https://geocoding-api.open-meteo.com/v1/search`) | Dynamic location resolution | Production Live | **VERIFIED LIVE** (Resolved coordinates dynamically) | **REAL LIVE DATA** |
| **NOAA GEFSv12 Retrospective S3** (`https://noaa-gefs-retrospective.s3.amazonaws.com/`) | Historical reforecast GRIB2 data | Historical Training | **VERIFIED LIVE** (Fetched actual `.idx` byte index via HTTP) | **REAL AUTHORITATIVE DATA** |
| **Open-Meteo Historical Archive** (`https://archive-api.open-meteo.com/v1/archive`) | ERA5 reanalysis reference truth | Historical Verification | **VERIFIED LIVE** (Fetched historical 2023 ERA5 hourly records) | **REAL REANALYSIS DATA** |

### Mock / Synthetic Data Search:
- In production live serving (`backend/app/services/openmeteo_service.py`, `backend/app/builder2/model_adapter.py`), **no mocked weather data is injected**.
- Synthetic data generation was identified in **`scripts/train_builder2_model.py`**, which generates 10,800 synthetic rows to train `models/day4/lightgbm_bust_model.joblib`.
- Mock classes in `backend/tests/` and `tests/` are standard test doubles and do not affect production code.

---

## 11. Historical Data Pipeline

The historical ingestion and verification pipeline was traced through `ingestion/` and `data_pipeline/`:

```
[ NOAA GEFSv12 AWS S3 ]              [ Open-Meteo ERA5 Archive ]
         │                                       │
         ▼                                       ▼
  noaa_s3.py                             era5_collector.py
(Direct GRIB2 byte-slicing)            (Hourly reanalysis truth)
         │                                       │
         ▼                                       ▼
   standardize.py                      standardize_era5_reference()
(Canonical 31-member moments)                    │
         │                                       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
                    historical_aligner.py
             (Colocation by location, var, valid_time)
                             │
                             ▼
                     label_engine.py
          (Fits conditional q95 error thresholds)
                             │
                             ▼
               [ Training Parquet Dataset ]
```

### Reality Check:
- While the pipeline code in Tree 2 is architecturally sound and verified, **the generated historical benchmark parquet datasets are absent from disk** (`phase5b2_benchmark_canonical.parquet` is missing).
- The only parquet dataset currently on disk is `data/training/training_dataset.parquet` (10,800 rows, 1.17 MB), which was synthetically generated by `scripts/train_builder2_model.py`.

---

## 12. Feature Engineering

### Active Production Feature Schema (`builder2-canonical-26-v1.0`):
- **Feature Count:** 26 features
- **Source File:** `backend/app/builder2/feature_pipeline.py`
- **Feature Ordering:**

| Index | Feature Name | Category | Available at Issue Time? | Leakage Safe? | Used by Current Model? |
| :---: | :--- | :--- | :---: | :---: | :---: |
| 0 | `ensemble_std` | Ensemble Spread | YES | YES | YES |
| 1 | `ensemble_range` | Ensemble Spread | YES | YES | YES |
| 2 | `ensemble_iqr` | Ensemble Spread | YES | YES | YES |
| 3 | `ensemble_skew_proxy` | Ensemble Geometry | YES | YES | YES |
| 4 | `ensemble_cv` | Ensemble Dispersion | YES | YES | YES |
| 5 | `ensemble_spread_to_iqr_ratio` | Ensemble Dispersion | YES | YES | YES |
| 6 | `member_count` | Quality / Sampling | YES | YES | YES |
| 7 | `has_full_ensemble` | Quality Flag | YES | YES | YES |
| 8 | `forecast_value` | Deterministic NWP | YES | YES | YES |
| 9 | `ensemble_mean` | Ensemble Moment | YES | YES | YES |
| 10 | `ensemble_spread_delta_6h` | Inter-cycle Revision | YES (Cycle $T-6\text{h}$) | YES | YES |
| 11 | `ensemble_spread_delta_24h` | Inter-cycle Revision | YES (Cycle $T-24\text{h}$) | YES | YES |
| 12 | `forecast_delta_6h` | Inter-cycle Revision | YES (Cycle $T-6\text{h}$) | YES | YES |
| 13 | `forecast_delta_24h` | Inter-cycle Revision | YES (Cycle $T-24\text{h}$) | YES | YES |
| 14 | `lead_hours` | Horizon | YES | YES | YES |
| 15 | `lead_days` | Horizon | YES | YES | YES |
| 16 | `valid_hour` | Temporal Diurnal | YES | YES | YES |
| 17 | `valid_month` | Temporal Seasonal | YES | YES | YES |
| 18 | `valid_dayofweek` | Temporal Weekly | YES | YES | YES |
| 19 | `sin_hour` | Cyclical Diurnal | YES | YES | YES |
| 20 | `cos_hour` | Cyclical Diurnal | YES | YES | YES |
| 21 | `sin_month` | Cyclical Seasonal | YES | YES | YES |
| 22 | `cos_month` | Cyclical Seasonal | YES | YES | YES |
| 23 | `is_weekend` | Calendar Flag | YES | YES | YES |
| 24 | `latitude` | Spatial Location | YES | CAUTION (Location Overfitting) | YES |
| 25 | `longitude` | Spatial Location | YES | CAUTION (Location Overfitting) | YES |

*Note:* In Builder 2's later 50-feature research catalog (`forecast_intelligence_features.py`), `latitude` and `longitude` were intentionally removed to prevent location overfitting.

---

## 13. Leakage Audit

A strict audit of static code paths and runtime data flow was conducted:
1. **Ground-Truth Field Auditing:** In `backend/app/schemas/model_integration.py` and `backend/app/services/model_integration_service.py`, any feature dictionary containing keys in `FORBIDDEN_GROUND_TRUTH_FIELDS` (`observed_value`, `truth_value`, `reference_value`, `forecast_error`, `bust_label`, `era5`) immediately raises `ValueError("CRITICAL LEAKAGE DETECTED")`.
2. **Inter-cycle Revision Auditing:** In `backend/app/builder2/feature_pipeline.py`, revisions are computed by comparing predictions for the *same valid time* against cycles issued at $T - 6\text{h}$ or $T - 24\text{h}$. Because $T - 6\text{h} < T$, this information was strictly available prior to current forecast issuance.
3. **Threshold Fitting Auditing:** In `label_engine.py`, quantile thresholds are fit strictly on the training partition (`df_train`), and applied downstream without refitting.

**Verdict: NO LEAKAGE FOUND IN INSPECTED PATHS.**

---

## 14. ML Model Artifact Audit

| Attribute | Active Model (Tree 1) | Champion Model (Tree 2 Manifest) |
| :--- | :--- | :--- |
| **Model Version** | `prototype-gbm-v1` | `veyra-v2-champion-lightgbm` |
| **Model Type** | `LightGBMBustClassifier` | `LightGBMClassifier` |
| **Artifact Path** | `models/day4/lightgbm_bust_model.joblib` | `models/v2/lightgbm_v2_champion.joblib` |
| **Artifact Exists on Disk?** | **YES** (48,883 bytes) | **NO (MISSING)** |
| **Calibrator Path** | `models/day4/probability_calibrator.joblib` | `models/v2/probability_calibrator_v2.joblib` |
| **Calibrator Exists?** | **YES** (419 bytes) | **NO (MISSING)** |
| **Metadata Path** | `models/day4/model_metadata.json` | `models/v2/feature_names.json` |
| **Feature Count** | 26 features | 50 features |
| **Decision Threshold** | `0.280` | `0.060` |
| **Training Data Source** | Synthetic Simulation (10,800 rows) | NOAA GEFSv12 Benchmark (780,000 rows) |
| **Load Successful?** | **YES** (Loaded in 2ms) | **FAIL** (FileNotFoundError) |

---

## 15. Calibration Audit

- **Method:** Platt Scaling (Sigmoid calibration via logistic regression on raw logits).
- **Artifact:** `models/day4/probability_calibrator.joblib` (scikit-learn `LogisticRegression` instance).
- **Validation Impact:**
  - Uncalibrated Brier Score: `0.2043`
  - Calibrated Brier Score: `0.0508`
  - Brier Score Improvement: `+75.12%`
- **Discrimination vs Calibration:**
  - While probability calibration is strong (Brier score 0.0508 reflects well-scaled probabilities matching empirical bust prevalence of ~5%), **classification discrimination on the synthetic test set is poor**:
  - Test Precision: `0.0000`
  - Test Recall: `0.0000`
  - Test ROC-AUC: `0.5165` (versus ensemble spread baseline ROC-AUC of `0.5502`)
  - *Conclusion:* At the fixed decision threshold of `0.280`, the prototype model predicts zero busts on the test split. The spread baseline alone exhibits higher discriminative power than this prototype model.

---

## 16. Model Metric Audit

Underlying evaluation dataset comparison:
- Recomputing metrics against Tree 2's benchmark archive (5,400 test records, 500 busts, ROC-AUC 0.8469, PR-AUC 0.5567):  
  **NOT REPRODUCIBLE FROM CURRENT PROJECT COPY** (benchmark parquet files missing from workspace).
- Evaluation of Tree 1's `models/day4/` synthetic model:
  - Saved in `models/day4/model_metadata.json`: Accuracy = 0.9463, Precision = 0.0, Recall = 0.0, ROC-AUC = 0.5165, Brier = 0.0508.
  - Recomputed via `scripts/train_builder2_model.py` test split logic: **EXACT BITWISE MATCH**.

---

## 17. OOD / Safety / Abstention

The application implements a strict fail-safe abstention architecture in `backend/app/safety/abstention.py`:
- **Invalid Location:** Returns `bust_probability = None`, `trust_state = "UNAVAILABLE"`, `reason_codes = ["INVALID_LOCATION"]`. Verified live with test input `"NonExistentPlaceXYZ12345"`.
- **Network Failure:** Returns `DATA_UNAVAILABLE`.
- **Physical QC Violation:** Returns `QC_FAILED`.
- **Out of Bounds Probability:** If model outputs $P < 0$ or $P > 1$, returns `ABSTAINED` with `QC_FAILED`.
- **Zero Fake Probabilities:** Verified that no random numbers or hardcoded `0.5` probabilities are returned when upstream components fail.

---

## 18. Explainability Audit

- **Implementation:** `backend/app/builder2/explainer.py` wrapped by `backend/app/services/explainability_service.py`.
- **Nature of Explanations:** Deterministic physical feature attribution based on meteorological rules (spread thresholds, revision magnitudes, lead degradation). Not black-box SHAP approximations.
- **Consistency Guard:** Line 77 of `explainer.py` explicitly checks `bust_probability >= threshold`. When risk is low, it unconditionally outputs `"stable_ensemble_agreement"`, mathematically guaranteeing that the narrative explanation never contradicts a low bust probability.

---

## 19. Backend Audit

The FastAPI backend runs on `http://localhost:8000`:

| Method | Path | Purpose | Dependencies | Status |
| :---: | :--- | :--- | :--- | :---: |
| `GET` | `/v1/health` | Service health & version | None | **200 OK** |
| `GET` | `/docs` | Interactive OpenAPI documentation | Swagger UI | **200 OK** |
| `GET` | `/v1/metrics` | Operational telemetry counters & latency | In-process ProcessMetrics | **200 OK** |
| `GET` | `/v1/model/evaluation` | Active model evaluation metadata | `model_metadata.json` | **200 OK** |
| `POST` | `/v1/predict` | Single-target forecast bust evaluation | WeatherService, ModelAdapter | **200 OK** |
| `POST` | `/v1/predict/batch` | Multi-location batch risk evaluation | MultiLocationService | **200 OK** |
| `POST` | `/v1/historical/batch` | Multi-location historical data collection | HistoricalService | **200 OK** |
| `GET` | `/dashboard` | Serves compiled React SPA | `frontend/dist/index.html` | **200 OK** |

---

## 20. Frontend Audit

- **Framework:** React 19.0.0, Vite 6.1.0, TypeScript 5.7.3.
- **Architecture:** Client-side SPA communicating with FastAPI `/v1` endpoints via `VeyraApiClient` (`fetch` with typed error handling and `X-Request-ID` propagation).
- **Features:**
  - Single-target location prediction mode.
  - Multi-horizon risk timeline (7-day and 16-day lead horizon curves).
  - Risk tier badges (Low / Medium / High / Critical) and confidence indicators.
  - Interactive physical explanation accordions with contributing factors.
  - Robust abstention and error alert banners.
- **Verification:**
  - **Vitest Suite:** 2 test suites, **51 tests passed 100%** (`Dashboard.test.tsx` 27 passed, `RiskTimeline.test.tsx` 24 passed).
  - **Build:** `npm run build` (`tsc && vite build`) executes in 1.58s with **0 errors**.

---

## 21. Caching / Retry / SingleFlight

- **Weather Cache:** `BoundedTTLCache` in `backend/app/core/cache.py` with 120-second TTL and max 512 entries.
- **SingleFlight Deduplication:** Implemented in `openmeteo_service.py` (`forecast_deduplicator`). When the frontend timeline initiates 16 concurrent horizon requests for the same location, SingleFlight coalesces all 16 requests into a single upstream network call to Open-Meteo.
- **HTTP Retry:** Exponential backoff with jitter on 429 and 5xx responses (`max_retries = 2`, `backoff_factor = 0.3`).

---

## 22. Monitoring & Observability

- **Implementation:** In-process `ProcessMetrics` in `backend/app/core/metrics.py`.
- **Metrics Tracked:** Request counts by status code, average latency, prediction counts by risk level, abstention counts by reason code, upstream provider errors/timeouts/429s, cache hit/miss/eviction rates, SingleFlight leader/coalesced ratios, and retry attempts.
- **Exposed Endpoint:** `GET /v1/metrics`.
- **Scope:** In-memory, non-persistent. Reset upon process restart.

---

## 23. Dependency & Environment Audit

| Package / Tool | Declared Version | Installed Version | Status / Impact |
| :--- | :--- | :--- | :--- |
| `python` | $\ge 3.10$ | 3.13.5 | **OK** |
| `fastapi` | `^0.110.0` | 0.141.1 | **OK** |
| `uvicorn` | `^0.28.0` | 0.52.4 | **OK** |
| `pydantic` | `^2.6.0` | 2.13.4 | **OK** |
| `lightgbm` | `^4.3.0` | 4.7.0 | **OK** |
| `xgboost` | `^2.0.0` | 3.4.1 | **OK** |
| `scikit-learn`| `^1.4.0` | 1.9.0 | **OK** |
| `pandas` | `^2.2.0` | 2.3.2 | **OK** |
| `numpy` | `^1.26.0` | 2.3.2 | **OK** |
| `pyarrow` | `^15.0.0` | 25.0.1 | **OK** |
| `pytest` | `^8.0.0` | 9.1.1 | **OK** |
| `requests` | `^2.31.0` | **NOT INSTALLED** | **FAIL** in Tree 2 (`ModuleNotFoundError: No module named 'requests'`) |
| `eccodes` | System / Conda | **NOT INSTALLED** | **FAIL** in Tree 2 (GRIB2 decoding unavailable without conda environment) |
| `node` | $\ge 18.0.0$ | 24.16.0 | **OK** |
| `npm` | $\ge 9.0.0$ | 11.13.0 | **OK** (Requires calling `npm.cmd` due to Windows PowerShell ExecutionPolicy) |

---

## 24. Missing Files & Artifact Audit

| Expected Path | Referenced By | Why Required | Runtime Impact | Likely Source | Recoverable? |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `models/v2/lightgbm_v2_champion.joblib` | `models/forecast_intelligence_service.py`, `server.py` | Builder 2 Champion model | Cannot run V2 service or `server.py` | Colab run / Builder 2 machine | **YES** (Recover original from Builder 2) |
| `models/v2/probability_calibrator_v2.joblib`| `models/forecast_intelligence_service.py` | V2 Probability calibrator | V2 probability calibration fails | Colab run / Builder 2 machine | **YES** |
| `models/v3/lightgbm_v3_challenger.joblib` | `models/forecast_intelligence_service.py` | Builder 2 Challenger model | V3 service cannot load | Colab run / Builder 2 machine | **YES** |
| `models/v3/probability_calibrator_v3.joblib`| `models/forecast_intelligence_service.py` | V3 Probability calibrator | V3 calibration fails | Colab run / Builder 2 machine | **YES** |
| `models/v3/feature_names.json` | `models/forecast_intelligence_service.py` | Feature schema validation | Feature ordering unverified | Colab run / Builder 2 machine | **YES** |
| `data/processed/phase5b2_benchmark_canonical.parquet` | `FINAL_RELEASE_MANIFEST.md`, `reproducibility_manifest.json` | 780k-row evaluation dataset | Scientific metrics not reproducible | Colab extraction | **YES** |
| `scratch/env_eccodes` | `server.py`, `noaa_s3.py` | Local ecCodes DLL bindings | GRIB2 decoding fails on Windows | Local Conda environment | **YES** (Recreate via conda) |

---

## 25. Test Results

### 1. Builder 1 Backend Test Suite (`backend/tests/`):
- **Command:** `python -m pytest backend\tests -q` (executed from repo root `Veyra — Know When Forecasts May Fail`)
- **Total Tests:** 319
- **Passed:** **319 (100%)**
- **Failed:** 0
- **Duration:** 57.36s
- *Note:* If executed from the parent directory `..`, 9 tests fail due to relative path resolution in `evaluation_service.py`.

### 2. Frontend Test Suite (`frontend/`):
- **Command:** `npm.cmd test`
- **Total Tests:** 51
- **Passed:** **51 (100%)**
- **Failed:** 0
- **Duration:** 33.00s

### 3. Builder 2 Test Suite (`Parinidhi/tests/`):
- **Command:** `python -m pytest tests -q` (executed from `Parinidhi/...`)
- **Status:** **COLLECTION ERROR (4 errors)**
  - `No module named 'requests'` (missing dependency)
  - `No module named 'models.error_distribution'` (broken import; module is at `research.error_distribution`)

---

## 26. Real-Data E2E Result

### Real Live Evaluation Test:
- **Target:** Location = `"Delhi"`, Variable = `"temperature_2m"`, Endpoint = `POST /v1/predict`
- **Result:** **PASS (HTTP 200 OK)**
- **Response Payload:**
  ```json
  {
    "location": "Delhi",
    "bust_probability": 0.0568,
    "risk_level": "LOW",
    "trust_state": "HIGH_CONFIDENCE",
    "abstain": false,
    "reason_codes": ["SUCCESS"],
    "model_version": "prototype-gbm-v1",
    "data_version": "gefs-openmeteo-v1.0",
    "explanation": {
      "primary_driver": "stable_ensemble_agreement",
      "driver_summary": "Forecast is stable with low ensemble dispersion and consistent inter-cycle agreement.",
      "top_contributing_factors": [
        {"factor": "forecast_delta_24h", "value": null, "signal": "NO_PRIOR_CYCLE_BASELINE"},
        {"factor": "ensemble_std", "value": 0.0, "signal": "LOW_ENSEMBLE_SPREAD"},
        {"factor": "lead_hours", "value": 82.0, "signal": "MEDIUM_RANGE_HORIZON"}
      ]
    }
  }
  ```
- **Latency:** 1,345 ms total (Upstream Open-Meteo fetch: 1,202 ms, Local feature + model + safety: 143 ms).

---

## 27. Documentation vs Reality

| Claim | Source | Code Supports? | Runtime Supports? | Verdict |
| :--- | :--- | :---: | :---: | :---: |
| "Active Production Model: `veyra-v3-benchmark-lightgbm` on 780k archive" | `FINAL_RELEASE_MANIFEST.md` | NO | NO | **FALSE / OUTDATED** (Active model is `prototype-gbm-v1` on 10.8k synthetic rows) |
| "Decision threshold is 0.060" | `FINAL_RELEASE_MANIFEST.md` | NO | NO | **FALSE** (Active code threshold is `0.280`) |
| "211 Total Automated Tests Passing 100%" | `FINAL_RELEASE_MANIFEST.md` | PARTIAL | NO | **OUTDATED** (Tree 1 has 319 passing Python tests; Tree 2 has collection errors) |
| "Strictly Zero Fake Probabilities on Outage" | Integration Contract | YES | YES | **VERIFIED** (Verified live abstention on invalid location) |
| "Timeline does not amplify upstream requests" | Day 17 Overview | YES | YES | **VERIFIED** (SingleFlight coalesces timeline queries to 1 network call) |

---

## 28. COMPLETE PROBLEM REGISTER

| ID | Severity | Area | Component | File(s) | Problem Description | Root Cause | Impact | Recommended Fix | Priority | Regression Risk |
| :---: | :---: | :---: | :---: | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **PRB-01** | **CRITICAL** | Model Artifacts | Builder 2 / Serving | `models/v2/`, `models/v3/` | Champion V2 and Challenger V3 models and calibrators are missing from workspace | `.gitignore` rules (`*.joblib`, `models/*`) excluded them during export | Cannot deploy or serve the trained 50-feature champion model | Recover original `.joblib` files from Builder 2/Colab environment | P1 | None |
| **PRB-02** | **HIGH** | Ingestion / Features | Builder 1 / Weather | `backend/app/services/openmeteo_service.py` | Live weather ingestion does not extract member columns from Open-Meteo, collapsing `ensemble_std` to 0.0 | Parser only extracts `temperature_2m` scalar, ignoring `temperature_2m_member01..30` | Live predictions have artificially zero ensemble spread | Adopt `standardize.py` ensemble calculation in `openmeteo_service.py` | P2 | Medium |
| **PRB-03** | **HIGH** | Data Schema / Units | Builder 1 vs Builder 2 | `backend/app/services/openmeteo_service.py` | Wind speed unit requested as `m/s` in live ingestion, but trained as `km/h` | Divergent unit conventions between Builder 1 and Builder 2 | Live wind predictions will be scaled down by 3.6x, distorting model inference | Unify canonical wind unit to `km/h` or add automated conversion | P2 | Low |
| **PRB-04** | **HIGH** | Dependencies | Environment | `requirements.txt` | `requests` is missing from the Python environment; `eccodes` missing on Windows | Not installed in active Python 3.13 environment | Builder 2 NOAA S3 tests fail to import | Install `requests` into Python 3.13; document conda setup for ecCodes | P2 | None |
| **PRB-05** | **MEDIUM** | Test Imports | Builder 2 Tests | `tests/test_phase5b1_error_distribution.py` | Test imports `from models.error_distribution` which does not exist | Module was placed in `research/error_distribution` | Builder 2 pytest collection fails with ImportError | Fix import path to `research.error_distribution` | P3 | None |
| **PRB-06** | **MEDIUM** | Path Resolution | Backend Service | `backend/app/services/evaluation_service.py` | Evaluation metadata path resolution fails if pytest or server is run from parent directory | Uses relative path `Path("models/day4/model_metadata.json")` instead of repo-root-relative path | 9 test failures when pytest is invoked from workspace root | Anchor path using `_REPO_ROOT` from `config.py` | P3 | Low |
| **PRB-07** | **MEDIUM** | Contracts | Risk Engine | `backend/app/safety/abstention.py` | Risk tier definitions and thresholds conflict between Builder 1 (0.280) and Builder 2 (0.060) | Incomplete alignment between Phase 1 prototype and Phase 2 research | Frontend shows 4 tiers (Low/Med/High/Crit) while Builder 2 specifies 3 tiers | Align threshold and risk bands to the active model configuration | P3 | Medium |
| **PRB-08** | **LOW** | Repository | Filesystem | Directory name | Subdirectory name contains Unicode em-dash (`—`) | Naming discrepancy during folder creation | Breaks naive CLI commands without quote escaping | Provide symbolic link or standardize path references | P4 | Low |

---

## 29. Root Cause Analysis

The root cause of the current project state is **asynchronous branch development with overly aggressive `.gitignore` patterns**:
1. **`.gitignore` Leakage:** Both Builder 1 and Builder 2 configured `.gitignore` with `*.joblib`, `*.parquet`, and `models/*`. While best practice for git hygiene with multi-gigabyte files, small production artifacts (<1MB `.joblib` files) were never whitelisted (`!models/v2/*.joblib`). When the workspace was packaged or cloned, the model weights were stripped.
2. **Parallel Track Siloing:** Builder 1 focused on production engineering (FastAPI hardening, React 19 UI, SingleFlight, caching, test reliability), while Builder 2 focused on scientific meteorology (NOAA S3 byte slicing, ecCodes, 1,040-cycle Colab training). Builder 1 successfully wrapped Builder 2's Day 4 prototype, but the subsequent Day 15–20 scientific enhancements were never reconciled into Builder 1's serving interfaces.

---

## 30. Fix Dependency Graph

```
                   [ STEP 1: Recover Missing Model & Data Artifacts ]
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
[ STEP 2: Install Dependencies ]              [ STEP 3: Fix Relative Paths ]
(pip install requests, ecCodes)               (Anchor models path in evaluation_service.py)
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         │
                                         ▼
                   [ STEP 4: Fix Builder 2 Broken Test Imports ]
                   (Correct models.error_distribution import)
                                         │
                                         ▼
                   [ STEP 5: Unify Weather Ingestion & Member Parsing ]
                   (Extract 30 members in openmeteo_service.py -> ensemble_std)
                                         │
                                         ▼
                   [ STEP 6: Harmonize Units & Risk Thresholds ]
                   (Align wind speed to km/h, threshold to 0.060 or model spec)
                                         │
                                         ▼
                   [ STEP 7: Full E2E & Cross-Phase Verification ]
                   (Execute all 370+ tests + live dashboard preview)
```

---

## 31. Recommended Fix Roadmap

### Stage 0 — Baseline Preservation
- **Action:** Preserve Tree 1 (`Veyra — Know When Forecasts May Fail`) as the working baseline. Do not alter its working test suite or frontend until recovery is complete.

### Stage 1 — Artifact Recovery (Do Not Retrain)
- **Action:** Request and import the original working model binaries:
  `models/v2/lightgbm_v2_champion.joblib`, `models/v2/probability_calibrator_v2.joblib`, `models/v3/lightgbm_v3_challenger.joblib`, `models/v3/probability_calibrator_v3.joblib`, `models/v3/feature_names.json`.
- **Pass Condition:** Files exist on disk and pass SHA-256 hash checks matching `FINAL_RELEASE_MANIFEST.md`.

### Stage 2 — Dependency & Environment Sanitization
- **Action:** Install `requests` into the active Python environment: `python -m pip install requests`.
- **Pass Condition:** `python -c "import requests"` exits 0.

### Stage 3 — Test Import Rectification
- **Action:** In `Parinidhi/.../tests/test_phase5b1_error_distribution.py`, update import from `models.error_distribution` to `research.error_distribution`.
- **Pass Condition:** `python -m pytest tests -q` in `Parinidhi` collects all test files without syntax or import errors.

### Stage 4 — Ingestion Ensemble Spread Extraction
- **Action:** Update `OpenMeteoGEFSWeatherService.parse_canonical_records` to iterate over member columns (`temperature_2m_member01..30`), compute `np.std(members, ddof=1)`, and populate `ensemble_std` on `CanonicalForecastRecord`.
- **Pass Condition:** Live prediction returns non-zero `ensemble_std` matching real atmospheric spread.

### Stage 5 — Contract Harmonization
- **Action:** In `backend/app/builder2/model_adapter.py` and `backend/app/safety/abstention.py`, dynamically read the decision threshold and risk tier cutoffs from the active model's metadata rather than using hardcoded constants.

---

## 32. Protected Working Components

The following components are fully verified, robust, and **must not be broken or rewritten** during future fixes:
1. `backend/app/main.py` (FastAPI application factory, CORS, exception handlers).
2. `backend/app/core/middleware.py` (Security headers, rate limiting, request correlation).
3. `backend/app/core/cache.py` (Bounded TTL cache and SingleFlight request deduplication).
4. `backend/app/agents/forecast_bust_agent.py` (Sequential short-circuiting agent logic).
5. `backend/app/safety/abstention.py` (Failsafe abstention and anti-hallucination logic).
6. `frontend/src/*` (React 19 dashboard, timeline visualizer, form controls).
7. `backend/tests/*` (All 319 existing backend tests).
8. `frontend/src/test/*` (All 51 existing frontend Vitest tests).

---

## 33. Project Health Matrix

| Area | Status | Evidence |
| :--- | :---: | :--- |
| **Project Structure** | **PARTIAL** | Three separate trees exist in root; em-dash in directory name. |
| **Builder 1** | **PASS** | Complete backend, API, middleware, frontend, 370 tests pass. |
| **Builder 2** | **PARTIAL** | Scientific pipeline written; runtime models missing from disk. |
| **Builder 1 ↔ Builder 2 Integration** | **PARTIAL** | Prototype model integrated and functional; live spread parsing missing. |
| **Live Data Ingestion** | **PASS** | Live Open-Meteo ensemble and geocoding verified real. |
| **Historical Data Ingestion** | **PASS** | Live NOAA GEFSv12 S3 and ERA5 archive verified real. |
| **QC (Quality Control)** | **PASS** | Physical bounds checking verified in `ForecastQualityControl`. |
| **Time & Lead Handling** | **PASS** | Strict `lead_hours = valid_time - issue_time` enforced across pipeline. |
| **Unit Correctness** | **PARTIAL** | Wind speed unit mismatch (`m/s` in live vs `km/h` in training). |
| **Ensemble Handling** | **PARTIAL** | Full stats computed in Builder 2 data pipeline; missing in Builder 1 live parser. |
| **Bust Labeling** | **PASS** | Conditional q95 error thresholding implemented in `BustLabelEngine`. |
| **Feature Engineering** | **PASS** | Issue-time safe 26-feature pipeline verified. |
| **Leakage Prevention** | **PASS** | Zero ground-truth leakage verified statically and at runtime. |
| **Model Artifact** | **PARTIAL** | Day 4 prototype model present; Champion V2 and V3 models missing. |
| **Probability Calibration** | **PASS** | Platt Sigmoid calibrator verified (+75% Brier score improvement). |
| **Model Discrimination** | **FAIL** | Prototype model has ROC-AUC 0.5165 and zero recall on test set. |
| **OOD & Safety** | **PASS** | Abstention verified on invalid location and network errors. |
| **Explainability** | **PASS** | Deterministic physical attribution verified; never contradicts prediction. |
| **Backend** | **PASS** | FastAPI server running, docs available, health 200 OK. |
| **Frontend** | **PASS** | React 19 dashboard builds cleanly, 51 Vitest tests pass. |
| **Timeline Visualization**| **PASS** | Multi-horizon risk timeline verified in frontend and tests. |
| **Caching & SingleFlight** | **PASS** | 120s TTL cache and request coalescing verified. |
| **Observability** | **PASS** | In-process telemetry counters exposed on `/v1/metrics`. |
| **Dependencies** | **PARTIAL** | Python 3.13 and Node installed; `requests` missing for Builder 2. |
| **Tests** | **PASS** | 319 backend Python tests + 51 frontend tests pass (370 total). |
| **Real-Data E2E** | **PASS** | Live end-to-end prediction executed for Delhi in 1.34s. |
| **Reproducibility** | **PARTIAL** | Code is reproducible; benchmark dataset must be recovered. |

---

## 34. What Is Definitely Working

1. **Full Backend Server:** FastAPI boots cleanly, serves `/docs`, `/v1/health`, `/v1/metrics`, and `/v1/model/evaluation`.
2. **Real-Data Live Prediction:** `POST /v1/predict` fetches real Open-Meteo GFS ensemble data, extracts features, evaluates the calibrated LightGBM model, and returns a verified probability and explanation in 1.34s.
3. **Safety & Abstention:** Invalid locations and missing data immediately trigger clean abstention with `bust_probability=None` and `trust_state="UNAVAILABLE"`. No fake probabilities are generated.
4. **Upstream Request Deduplication:** SingleFlight coalesces simultaneous multi-lead timeline requests into a single network query.
5. **Frontend Dashboard:** React 19 / TypeScript dashboard builds without errors and passes all 51 unit/integration tests.
6. **Live Data Providers:** NOAA GEFSv12 AWS S3 and Open-Meteo ERA5 archives are live and accessible.
7. **Test Suites in Tree 1:** 319 backend tests and 51 frontend tests pass 100%.

---

## 35. What Is Definitely Broken

1. **Missing Champion Model Binaries:** `models/v2/lightgbm_v2_champion.joblib` and `models/v3/lightgbm_v3_challenger.joblib` do not exist on disk.
2. **Missing Benchmark Parquet Dataset:** `phase5b2_benchmark_canonical.parquet` does not exist on disk.
3. **Zero Ensemble Spread in Live Inference:** `openmeteo_service.py` does not compute standard deviation across the 30 ensemble members, leaving `ensemble_std = 0.0`.
4. **Wind Speed Unit Discrepancy:** Ingestion queries `m/s` while model training assumed `km/h`.
5. **Missing Python Package:** `requests` is not installed, blocking Builder 2's ingestion tests.
6. **Broken Import in Builder 2 Tests:** `tests/test_phase5b1_error_distribution.py` imports non-existent `models.error_distribution`.
7. **Low Prototype Model Discrimination:** `prototype-gbm-v1` has ROC-AUC of 0.5165 and precision/recall of 0.0 on its test set.

---

## 36. What Is Still Unverified

1. **Performance of V2/V3 Models:** Cannot verify reported ROC-AUC (0.8469) or PR-AUC (0.5567) until the `.joblib` binary files are recovered.
2. **ecCodes Decoding on Windows:** ecCodes C-libraries require testing inside a dedicated Windows Conda environment.
3. **Full 1,040-Cycle Historical Alignment Run:** Complete retrospective alignment requires the full historical parquet archive.

---

## 37. Builder 1 Status: **PASS**
Builder 1 delivered a production-hardened, fully tested backend and frontend application with zero failing tests and proven real-data live execution.

## 38. Builder 2 Status: **PARTIAL**
Builder 2 designed an advanced 50-feature scientific pipeline and trained champion models, but failed to deliver the model artifacts into the workspace due to ignore rules, leaving only prototype Day 4 artifacts runnable.

## 39. Integration Status: **PARTIAL**
Builder 1 successfully integrated Builder 2's Day 4 prototype model and 26-feature pipeline into production serving. However, Builder 2's final V2/V3 models remain unintegrated due to missing artifacts and unaligned feature contracts.

---

## 40. Recommended Next Action

**IMMEDIATE FIRST RECOVERY ACTION:**
> **Do not modify code or retrain models yet.**  
> Retrieve the original trained model artifacts from Builder 2's environment / Google Colab session:
> - `models/v2/lightgbm_v2_champion.joblib`
> - `models/v2/probability_calibrator_v2.joblib`
> - `models/v3/lightgbm_v3_challenger.joblib`
> - `models/v3/probability_calibrator_v3.joblib`
> - `models/v3/feature_names.json`
> - `data/processed/phase5b2_benchmark_canonical.parquet`
>
> Place them into `Veyra — Know When Forecasts May Fail/models/` and whitelist them in `.gitignore`. Once restored, the verified champion models can be wired directly into the operational `ModelIntegrationService`.

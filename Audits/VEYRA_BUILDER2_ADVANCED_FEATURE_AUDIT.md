# Veyra — Builder 2 Advanced Feature Audit

**Forensic Investigation of Pre-Existing Builder 2 Capabilities, Code Completeness, Integration Gaps, and Phase 3 Roadmap Reconciliation**  
**Date of Audit:** September 7, 2026  
**Auditor:** Antigravity Forensic Engineering Agent (DeepMind AAC)  
**Audit Mode:** READ-ONLY Forensic Inspection (No source code, tests, configs, or models modified)  
**Scope:** Entire workspace across Tree 1 (Integrated Production), Tree 2 (Builder 2 Research Repository / Parinidhi), Tree 3 (Handoff Snapshot), and Historical Artifacts.

---

## 1. Executive Summary

### How Much Advanced Work Has Builder 2 Already Done?
**Builder 2 has already performed a massive amount of high-level scientific machine learning, verification, and evaluation work (approximately 60–70% of the proposed Phase 3 scientific and ML roadmap is already designed, coded, and tested in research).**

However, there is a **sharp structural disconnect** between Builder 2's research codebase and the active integrated production application:
1. **Extensive Research & Algorithmic Foundations:** Builder 2 has already designed and implemented Historical Trajectory Analogs, Monotonic Quantile Meshes, Continuous Ranked Probability Score (CRPS), Expected Calibration Error (ECE) curves, Platt & Isotonic calibration, 4 baseline models (Climatology, Persistence, Spread Heuristic, Majority), 6 Mathematical Failure Fingerprints, 5 Operational Decision Modes, an Operational Trust Horizon Engine ($H_{\text{rel}}$ / $H_{\text{skill}}$), Epistemic Mahalanobis OOD Detection ($D_M$), and Walk-Forward / Leave-One-Region-Out cross-validation.
2. **Missing Production Connection:** Almost NONE of Builder 2's advanced Day 11–20 intelligence is connected to the production FastAPI gateway or the React 19 frontend. The production backend in Tree 1 still serves Builder 2's early Day 4 26-feature prototype model (`models/day4/lightgbm_bust_model.joblib`), while Builder 2's 50-feature champion booster (`models/v2/lightgbm_v2_champion.joblib`) was excluded from the repository packaging by `.gitignore` rules.
3. **Broken Live Scientific Inputs:** Live Open-Meteo ingestion in production fails to unpack ensemble members, causing live ensemble spread (`ensemble_std`) to collapse to `0.0`. Furthermore, a severe wind-speed unit mismatch exists ($m/s$ ingested vs $km/h$ expected).
4. **Conclusion:** **We must NOT build Phase 3 from scratch.** Doing so would duplicate hundreds of hours of already-written, mathematically rigorous Python code. Instead, the focus must be: **(1) Fix live scientific inputs, (2) Recover/retrain the missing 50-feature champion artifact, and (3) Productize Builder 2's existing research modules into the production FastAPI API and React dashboard.**

---

## 2. Builder 2 Advanced Capability Map

```
                                  [ BUILDER 2 WORKSPACE CAPABILITIES ]
                                                    │
         ┌───────────────────────────┬──────────────┴──────────────┬───────────────────────────┐
         ▼                           ▼                             ▼                           ▼
[ 1. Ingestion & Data ]    [ 2. Feature Pipeline ]       [ 3. Modeling & Calib ]      [ 4. Evaluation & Research ]
 • AWS S3 Byte-Range NOAA   • 50 Features (V2/V3)         • LightGBM Booster (V2/V3)   • CRPS Empirical Quadrature
   GEFSv12 GRIB2 Extractor    - Ensemble Moments            (Excluded by .gitignore)   • ECE / Reliability Curves
 • ERA5 Reanalysis Truth      - Vintage Revisions         • Platt Sigmoid Calibrator   • Walk-Forward Backtesting
 • Hierarchical QC Filters    - Physical Interactions     • Isotonic PAV Calibrator    • Leave-One-Region-Out CV
 • Stratified Quantile        - Cyclical Time & Space     • 4 Baselines (Climatology,  • Bootstrap 500 CIs
   Bust Labels (Loc×Var×Lead) • Mahalanobis OOD Centroid    Persistence, Spread, Maj)  • Red Team Leakage Audits
                                                    │
                                                    ▼
                               [ 5. Decision & Operational Intelligence ]
                                • Operational Trust Horizon Engine (H_rel, H_skill)
                                • 6 Mathematical Failure Fingerprints (Archetypes)
                                • 5-Level Decision Modes (HIGH_TRUST -> ABSTAIN)
                                • Historical Trajectory Analogue Retrieval (k-NN)
                                • Composite Confidence Index (0-100 Heuristic)
                                • Standalone Dashboard Prototype (static/index.html)
```

---

## 3. Proposed Feature Comparison Table

| Feature | Builder 2 Status | Builder 1 Status | Prod Connected | Tested | Real-Data Verified | Frontend Exposed | Evidence (File & Symbol) | Recommended Action |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Historical Backtesting** | RESEARCH / EXP. | PARTIALLY IMPL. | NO | YES | YES | NO | `BACKTEST_REPORT_V2.md`, `evaluation/generalization.py` | EXTEND EXISTING IMPLEMENTATION |
| **B. Reliability Diagram** | PARTIALLY IMPL. | NOT IMPL. | PARTIAL | YES | YES | NO | `evaluation/calibration.py::compute_reliability_curve` | EXTEND EXISTING IMPLEMENTATION |
| **C. CRPS** | FULLY IMPL. (Research) | NOT IMPL. | NO | YES | YES | NO | `research/evaluation/metrics.py::calculate_crps_empirical` | DO NOT REBUILD — EXTEND |
| **D. Spread / Skill** | BLOCKED / BROKEN (Prod) | PARTIALLY IMPL. | BLOCKED | YES | BROKEN (Prod) | NO | `models/verification_engine.py::verify_ensemble` | FIX EXISTING IMPLEMENTATION FIRST |
| **E. Adaptive Bust Thresholds** | FULLY IMPL. | FULLY IMPL. | YES | YES | YES | YES | `configs/bust_thresholds.json`, `labels/label_engine.py` | DO NOT REBUILD — ALREADY DONE |
| **F. Model Benchmark Arena** | RESEARCH / EXP. | NOT IMPL. | NO | YES | YES | NO | `models/benchmark_runner.py::ModelBenchmarkRunner` | EXTEND EXISTING IMPLEMENTATION |
| **G. Forecast Revision Tracker** | PARTIALLY IMPL. | PARTIALLY IMPL. | PARTIAL | YES | YES | PARTIAL | `features/feature_pipeline.py`, `api/risk_engine.py` | EXTEND EXISTING IMPLEMENTATION |
| **H. Multi-Model Disagreement** | NOT IMPL. (Doc only) | NOT IMPL. | NO | NO | NO | NO | `research/COMPETITIVE_SCIENTIFIC_RESEARCH.md:L86` | BUILD NEW |
| **I. Geographic Bust-Risk Map** | PARTIALLY IMPL. | PARTIALLY IMPL. | PARTIAL | YES | YES | NO | `api/regional_aggregator.py`, `services/multi_location_service.py` | BUILD NEW FRONTEND MAP |
| **J. Extreme-Weather Mode** | PARTIALLY IMPL. | NOT IMPL. | PARTIAL | YES | YES | PARTIAL | `api/risk_engine.py:L281`, `features/instability_fingerprint.py` | EXTEND EXISTING IMPLEMENTATION |
| **K. Probability Uncertainty Interval** | RESEARCH / EXP. | NOT IMPL. | NO | YES | YES | NO | `research/error_distribution/quantile_mesh.py` | DO NOT REBUILD — EXTEND |
| **L. Calibration Drift** | NOT IMPL. (Doc only) | NOT IMPL. | NO | NO | NO | NO | `research/evaluation/lead_evaluation.py:L8` | BUILD NEW |
| **M. Data / Feature / Model Drift** | PARTIALLY IMPL. (OOD) | PARTIALLY IMPL. | YES (OOD) | YES | YES | YES (Badge) | `evaluation/novelty.py::FeatureNoveltyDetector` | EXTEND EXISTING IMPLEMENTATION |
| **N. Climatology/Persistence Baselines**| FULLY IMPL. (Research) | NOT IMPL. | NO | YES | YES | NO | `models/baselines.py::PersistenceBaseline,ClimatologyBaseline`| DO NOT REBUILD — ALREADY DONE |
| **O. Analog Ensemble** | RESEARCH / EXP. | NOT IMPL. | NO | YES | YES | NO | `evaluation/trajectory_analogues.py::HistoricalTrajectoryRetriever`| DO NOT REBUILD — EXTEND |
| **P. Reliability Score** | FULLY IMPL. (Heuristic) | PARTIALLY IMPL. | YES | YES | YES | PARTIAL | `models/forecast_intelligence_service.py:L188-194` | EXTEND EXISTING IMPLEMENTATION |
| **Q. Reliability Alerts** | PARTIALLY IMPL. | PARTIALLY IMPL. | PARTIAL | YES | YES | PARTIAL | `backend/app/schemas/prediction.py:L21` | BUILD NEW NOTIFICATIONS |
| **R. Saved Locations** | NOT IMPL. | NOT IMPL. | NO | NO | NO | NO | None (LocationRegistry has static 25 canonical stations) | BUILD NEW |
| **S. Simple / Advanced UI** | PARTIALLY IMPL. | NOT IMPL. | NO | NO | N/A | YES (Tree 2) | `static/index.html:L230-246, L750-779` | EXTEND EXISTING IMPLEMENTATION |
| **T. Model / Data Version Center** | PARTIALLY IMPL. | PARTIALLY IMPL. | YES (API) | YES | YES | MINIMAL | `reproducibility_manifest.json`, `models/day4/model_metadata.json` | EXTEND EXISTING IMPLEMENTATION |
| **U. Public API / API Key System** | NOT IMPL. | NOT IMPL. | NO | NO | NO | NO | None (All endpoints currently unauthenticated) | BUILD NEW |
| **V. PWA / Installable App** | NOT IMPL. | NOT IMPL. | NO | NO | NO | NO | None | BUILD NEW |
| **W. Exportable Reports** | PARTIALLY IMPL. | PARTIALLY IMPL. | NO | YES | YES | NO | `research/evaluation/final_report_generator.py` | EXTEND EXISTING IMPLEMENTATION |
| **X. Research Benchmark Suite** | FULLY IMPL. (Research) | NOT IMPL. | NO | YES | YES | NO | `research/evaluation/validation_schemes.py` | DO NOT REBUILD — ALREADY DONE |
| **Y. Rank Histogram** | DOCUMENTATION ONLY | NOT IMPL. | NO | NO | NO | NO | `research/COMPETITIVE_SCIENTIFIC_RESEARCH.md:L49` | BUILD NEW |
| **Z. Variable-Specific Verification** | PARTIALLY IMPL. | PARTIALLY IMPL. | NO | YES | YES | NO | `reports/day4/variable_metrics.json`, `models/verification_engine.py`| EXTEND EXISTING IMPLEMENTATION |

---

## 4. Scientific Reliability Features

### Feature A: Historical Backtesting
- **Status:** RESEARCH / EXPERIMENTAL
- **Evidence:**  
  - Document: `Parinidhi/Veyra-Know-When-Forecasts-May-Fail-main (1)/Veyra-Know-When-Forecasts-May-Fail-main/BACKTEST_REPORT_V2.md`
  - Engine: `evaluation/generalization.py::GeneralizationEngine`
  - Metrics: `reports/backtest_v2_metrics.json`
- **Capabilities Verified:**  
  Evaluated 4,320 held-out test records across 20 Indian stations and 2 distinct seasons (Monsoon and Post-Monsoon). Computes actual busts, predicted busts, correct warnings ($TP$), missed busts ($FN$), false alarms ($FP$), Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC, Brier Score, and Expected Calibration Error (ECE).
- **Missing for Production:**  
  The backtesting engine runs as an offline batch research script (`scratch/run_expanded_backtest_pipeline.py`); it is not wired into the Builder 1 live API as an on-demand endpoint.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Do not rewrite metric or alignment logic.

### Feature B: Reliability / Calibration Diagram
- **Status:** PARTIALLY IMPLEMENTED
- **Distinction:**
  - **MODEL CALIBRATION:** FULLY IMPLEMENTED. Platt scaling (Sigmoid via Newton-Raphson logistic regression) and Isotonic regression (via Pair Adjacent Violators algorithm) are implemented with zero scipy/sklearn dependencies in `evaluation/calibration.py::ProbabilityCalibrator` and `backend/app/builder2/calibrator.py`.
  - **RELIABILITY DIAGRAM:** PARTIALLY IMPLEMENTED. `evaluation/calibration.py::ReliabilityAnalyzer.compute_reliability_curve()` computes 5-to-10 probability bins with mean predicted probability, observed frequency, sample count, and calibration gap. Furthermore, `research/visualization/visualizers.py::ResearchVisualizer.build_reliability_diagram_spec()` produces the exact JSON chart specification.
  - **FRONTEND VISUALIZATION:** NOT IMPLEMENTED. Neither the React dashboard nor the static HTML renders an SVG/Canvas calibration curve.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Add an interactive calibration curve component to the React UI fed by the existing backend spec generator.

### Feature C: Continuous Ranked Probability Score (CRPS)
- **Status:** FULLY IMPLEMENTED IN RESEARCH
- **Evidence:**  
  - `research/evaluation/metrics.py::calculate_crps_empirical(error_knots, quantile_levels, true_error)` (L97–106)
  - `training/run_phase5b1_experiment.py::compute_crps_quantile_mesh` (L212)
  - `tests/test_phase5b1_error_distribution.py::test_crps_exact_quadrature_calculation` (L194–203)
  - `reports/final_scientific_report/05_error_distribution.md`
- **Capabilities Verified:**  
  Approximates exact CRPS via trapezoidal numerical quadrature of pinball loss across the quantile knots. Tested and strictly positive ($p > 0.0, \text{non-NaN}$). Used as the formal model promotion gate criterion in `research/evaluation/error_distribution_evaluation.py`.
- **Missing for Production:**  
  Calculated only in the offline Phase 5B.1 quantile mesh research script; not stored in the production sqlite/in-memory evaluation service or displayed on the frontend.
- **Recommended Action:** DO NOT REBUILD. EXTEND EXISTING IMPLEMENTATION by importing `calculate_crps_empirical` into `backend/app/services/evaluation_service.py`.

### Feature D: Ensemble Spread / Skill
- **Status:** BLOCKED / BROKEN IN PRODUCTION; FULLY IMPLEMENTED IN VERIFICATION ENGINE
- **Evidence:**  
  - Engine: `models/verification_engine.py::ScientificVerificationEngine.verify_ensemble()` (L177–216)
  - Live Ingestion: `backend/app/services/openmeteo_service.py:L224-226`
- **Capabilities Verified:**  
  `verify_ensemble()` calculates $\text{Spread-Skill Ratio} = \frac{\text{mean}(\text{ensemble\_std})}{\text{RMSE}}$, Pearson correlation between spread and absolute error, and classifies dispersion regimes (`UNDER_DISPERSED` for $<0.8$, `OVER_DISPERSED` for $>1.2$, and `CALIBRATED_DISPERSION`).
- **Critical Production Flaw:**  
  In training, Builder 2 parsed individual ensemble members p01–p30 from NOAA S3 GRIB2 reforecasts. However, in live production, `OpenMeteoGEFSWeatherService` requests only single aggregate arrays (`models=gfs_seamless`), populating `ensemble_mean = value` and leaving `ensemble_std = None`. Consequently, in `backend/app/builder2/feature_pipeline.py:L106`, `ensemble_std` defaults to `0.0`. Live production spread features completely collapse to zero!
- **Recommended Action:** FIX EXISTING IMPLEMENTATION FIRST. Modify `openmeteo_service.py` to query ensemble members from Open-Meteo or parse ensemble arrays so that real member dispersion is fed to the model.

### Feature E: Adaptive Bust Thresholds
- **Status:** FULLY IMPLEMENTED
- **Evidence:**  
  - Configuration: `configs/bust_thresholds.json`
  - Engine: `labels/label_engine.py::BustLabelEngine`
  - Backend: `backend/app/builder2/label_engine.py`, `backend/app/data/bust_labeling.py`
- **Actual Implementation Details:**  
  - Metric: $95^{\text{th}}$ percentile ($q_{95}$) of absolute forecast error $|forecast - truth|$.
  - Stratification Hierarchy: **$\text{LOCATION} \times \text{VARIABLE} \times \text{LEAD\_BIN}$** (e.g. `delhi__surface_pressure__day1` = 4.35 hPa; `delhi__surface_pressure__day4_6` = 6.13 hPa).
  - Lead Bins: `day1` (0–24h), `day2_3` (25–72h), `day4_6` (73–144h), `day7_10` (145–240h), `day10_plus` (>240h).
  - Fallback Safeguards: Falls back to variable-level thresholds (e.g. `surface_pressure` = 5.85 hPa, `temperature_2m` = 8.12°C, `wind_speed_10m` = 13.05 km/h) if stratum count $< 10$, and to global threshold (10.29) if variable count $< 10$.
- **Recommended Action:** DO NOT REBUILD. ALREADY DONE.

### Feature N: Climatology / Persistence Baselines
- **Status:** FULLY IMPLEMENTED IN RESEARCH
- **Evidence:**  
  - `models/baselines.py`:
    - `MajorityClassBaseline`: Always predicts non-bust ($P=0.0$).
    - `ClimatologyBaseline`: Predicts training-set empirical bust rate prior ($P = \bar{y}$).
    - `PersistenceBaseline`: Maps absolute 24h forecast revision $|forecast\_delta\_24h|$ via univariate logistic regression.
    - `SpreadHeuristicBaseline`: Maps `ensemble_std` via univariate logistic regression.
  - Tested: `tests/test_day4_models.py`, `tests/research/test_evaluation.py`.
- **Recommended Action:** DO NOT REBUILD. ALREADY DONE.

### Feature Y: Rank Histogram (Talagrand Diagram)
- **Status:** DOCUMENTATION ONLY
- **Evidence:**  
  - Mentioned in `research/COMPETITIVE_SCIENTIFIC_RESEARCH.md:L49` as a desirable ensemble dispersion diagnostic.
  - Code search for `rank_histogram` or `talagrand` returned 0 matches across all Python files.
- **Recommended Action:** BUILD NEW. Implement ensemble rank calculation and Talagrand histogram generator in `models/verification_engine.py`.

### Feature Z: Variable-Specific Verification
- **Status:** PARTIALLY IMPLEMENTED
- **Evidence:**  
  - Stratified metrics: `reports/day4/variable_metrics.json`
  - Engine: `models/verification_engine.py`
- **Findings:**  
  Evaluation metrics are grouped by variable (`temperature_2m`, `surface_pressure`, `wind_speed_10m`), but the mathematical formulas used are identical general scalar metrics (MAE, RMSE, Bias, Brier, ROC-AUC). There are NO precipitation-specific threat scores (Critical Success Index / CSI, Equitable Threat Score / ETS) or wind vector error metrics.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION by adding CSI/ETS for precipitation and vector RMSE for wind speed/direction.

---

## 5. Advanced ML Features

### Feature F: Model Benchmark Arena
- **Status:** RESEARCH / EXPERIMENTAL
- **Distinction:**
  - **RESEARCH BENCHMARK:** FULLY IMPLEMENTED. `models/benchmark_runner.py::ModelBenchmarkRunner` benchmarks Logistic Regression, HistGradientBoosting, and LightGBM across 5 ablation feature sets (`1_BASELINE_CANONICAL_26` through `5_ALL_INTEGRATED_FEATURES`). Further, `research/evaluation/model_comparison.py` compares V1 Logistic vs V2 LightGBM Champion vs V3 Quantile Mesh Challenger on Brier Skill Score (BSS), ECE, and CRPS.
  - **PRODUCTION MODEL COMPARISON:** NOT IMPLEMENTED. The production API only loads and executes a single model (`lightgbm_bust_model.joblib`). No live side-by-side champion/challenger inference exists.
  - **FRONTEND MODEL ARENA:** NOT IMPLEMENTED. No interactive leaderboard or model comparison UI exists.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Expose existing benchmark metrics via a `/v1/arena` API endpoint and render a comparison table in the frontend.

### Feature K: Probability Uncertainty Interval
- **Status:** RESEARCH / EXPERIMENTAL
- **Evidence:**  
  - Quantile Mesh: `research/error_distribution/quantile_mesh.py::QuantileMeshDistribution`
  - Chernozhukov Rearrangement: Enforces non-crossing quantile monotonicity ($q_{01} \le q_{05} \le \dots \le q_{99}$).
  - Coverage Metrics: Calculates Prediction Interval Coverage Probability (PICP90 = 91.2%) and Mean Prediction Interval Width (MPIW90) in `training/run_phase5b1_experiment.py:L229`.
  - Bootstrap CIs: `research/evaluation/metrics.py::bootstrap_metric_ci()` computes 500-iteration empirical confidence intervals.
- **Statistical Validity:**  
  This is a **statistically rigorous, mathematically derived uncertainty interval** based on conditional quantile regression and empirical bootstrap, NOT an arbitrary `prob ± 0.05` constant.
- **Recommended Action:** DO NOT REBUILD FROM SCRATCH. Productionize the Quantile Mesh model and serve the 90% uncertainty envelope through the API.

---

## 6. Forecast Revision / Ensemble Intelligence

### Feature G: Forecast Revision Intelligence
- **Status:** PARTIALLY IMPLEMENTED
- **Classification across Layers:**
  - **ML FEATURE ONLY:** FULLY IMPLEMENTED. `forecast_delta_6h`, `forecast_delta_24h`, `ensemble_spread_delta_6h`, `ensemble_spread_delta_24h`, `revision_accel_6h`, and `stability_index` are implemented in `features/feature_pipeline.py:L35-38` and `features/forecast_intelligence_features.py`.
  - **BACKEND EXPOSED:** PARTIAL. Present in internal feature dictionaries, but stripped from Builder 1's `PredictionResponse` schema.
  - **API EXPOSED:** PARTIAL. Exposed in Tree 2's `server.py` `/api/scenarios/`, but not in Tree 1's `/v1/predict`.
  - **FRONTEND EXPOSED:** PARTIAL. Displayed in Tree 2 `static/index.html` (Demo Scenario C, stability index badge, revision drawer), but absent from Builder 1 React dashboard.
  - **USER-FACING TRACKER:** NOT IMPLEMENTED. No interactive run-to-run cycle comparison tool exists for users.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Add `forecast_delta_24h` and `stability_index` to `PredictionResponse`, and render a "Forecast Stability & Cycle Revisions" widget in the React UI.

### Feature H: Multi-Model Disagreement
- **Status:** NOT IMPLEMENTED (Documentation only)
- **Clarification:**  
  Builder 2 evaluated multiple ensemble members of a **single weather model** (NOAA GEFSv12). Builder 2 did **NOT** ingest or compare forecasts across **different weather models** (e.g. GEFS vs ECMWF IFS vs DWD ICON vs UKMO).
- **Recommended Action:** BUILD NEW. Implement a multi-model ingestion service fetching Open-Meteo ECMWF and ICON feeds, and compute inter-model variance as an explicit disagreement feature.

---

## 7. Calibration, Drift, and OOD

### Feature L: Calibration Drift
- **Status:** NOT IMPLEMENTED
- **Findings:**  
  While lead-dependent calibration changes are analyzed in research (`reports/final_scientific_report/06_calibration.md`), there is NO system monitoring live operational prediction calibration over time (e.g. tracking rolling 30-day Brier score or ECE drift as real observations arrive).
- **Recommended Action:** BUILD NEW. Create a rolling calibration drift monitoring worker that re-evaluates Brier scores weekly against delayed ERA5/IMD verification data.

### Feature M: Data / Feature / Model Drift (vs OOD Detection)
- **Status:** PARTIALLY IMPLEMENTED
- **Crucial Distinction:**
  - **OOD DETECTION:** FULLY IMPLEMENTED. `evaluation/novelty.py::FeatureNoveltyDetector` computes the Mahalanobis distance $D_M(x) = \sqrt{(x - \mu)^T \Sigma^{-1} (x - \mu)}$ relative to the training distribution centroid and covariance. If $D_M \ge 40.0$, it triggers `OOD_ABSTAIN` in `backend/app/safety/abstention.py`.
  - **LONG-TERM DRIFT MONITORING:** NOT IMPLEMENTED. There is NO continuous statistical drift calculation (such as Population Stability Index / PSI, Kolmogorov-Smirnov / KS tests, or Wasserstein distance) tracking feature or prediction distribution drift over time.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Preserve the existing Mahalanobis OOD detector; add background PSI / Wasserstein drift calculation for data pipeline observability.

---

## 8. User-Facing Advanced Features

### Feature I: Geographic Bust-Risk Map
- **Status:** PARTIALLY IMPLEMENTED (Spatial backend complete; Map UI not implemented)
- **Evidence:**  
  - Builder 2: `api/regional_aggregator.py::RegionalRiskAggregator`
  - Builder 1: `backend/app/services/multi_location_service.py`, `backend/app/api/v1/endpoints/multi_location.py` (`POST /v1/multi-location/predict`, `GET /v1/multi-location/regions`)
- **Findings:**  
  The backend already aggregates bust risk across 25 Indian stations into 6 geographic regions (North, South, East, West, Central, Northeast) and computes regional peak probability, alert fraction, and worst-risk lead time. However, neither frontend contains a Leaflet, Mapbox, or GeoJSON spatial map.
- **Recommended Action:** BUILD NEW FRONTEND MAP. Connect the working `/v1/multi-location` endpoint to an interactive Leaflet/MapLibre India risk map.

### Feature J: Extreme-Weather Reliability Mode
- **Status:** PARTIALLY IMPLEMENTED
- **Findings:**  
  Extreme atmospheric regimes (convective diurnal heating, passing frontal waves, wind shear) are detected via physical failure fingerprints (`DIURNAL_CONVECTIVE_MISMATCH`, `SYNOPTIC_TRANSITION`, `WIND_GRADIENT_SHEAR`, `RAPID_REVISION_SHOCK`) in `features/instability_fingerprint.py`. When detected, `api/risk_engine.py:L281` automatically sets the operational decision mode to `RECHECK_SOON` or `DO_NOT_RELY_SOLELY`. However, there is no specialized ML model retrained solely on extreme tail events.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Port the failure fingerprint detection and decision mode logic from `api/risk_engine.py` into the production React UI.

### Feature P: Reliability Score
- **Status:** FULLY IMPLEMENTED (Operational Composite Heuristic)
- **Evidence:**  
  `models/forecast_intelligence_service.py:L188-194`, `api/risk_engine.py:L513`.
- **Exact Mathematical Formula:**
  $$\text{Confidence Index} = \text{clip}\left(100.0 \times (1.0 - P_{\text{bust}}) \times \left(\frac{\text{stability\_index}}{100.0}\right) \times \left(1.0 - 0.005 \times \min(\text{overconfidence\_risk}, 100.0)\right), 0.0, 100.0\right)$$
- **Scientific Nature:**  
  It is an **operational heuristic** combining non-bust probability ($1 - P_{\text{bust}}$), inter-cycle forecast revision stability ($\text{stability\_index} / 100$), and structural overconfidence penalties. It is NOT a formally calibrated probability, and is explicitly documented as a non-probabilistic operational score.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Display the Confidence Index alongside $P(\text{bust})$ in the production React dashboard with its documented operational meaning.

### Feature Q: Reliability Alerts
- **Status:** PARTIALLY IMPLEMENTED
- **Findings:**  
  Binary threshold crossing (`bust_alert = (bust_probability >= threshold)`) is implemented in the schema. However, there is no user alert engine (no email notifications, webhooks, watchlist subscriptions, or background threshold monitoring).
- **Recommended Action:** BUILD NEW. Implement a watchlist alert subscription system with configurable threshold triggers.

### Feature R: Saved Locations
- **Status:** NOT IMPLEMENTED
- **Findings:**  
  25 pre-configured Indian stations exist in `configs/canonical_locations.json` and `backend/app/services/location_service.py`, but neither backend nor frontend has user persistence, favorites, or `localStorage` saving.
- **Recommended Action:** BUILD NEW. Implement client-side `localStorage` saved locations and recent query history in the React dashboard.

### Feature S: Simple / Advanced UI
- **Status:** PARTIALLY IMPLEMENTED
- **Findings:**  
  In Tree 2's prototype dashboard (`static/index.html`), Builder 2 implemented progressive disclosure:
  1. **Simple Mode:** 15-Second Hero Decision Card displaying the primary decision badge (`HIGH_TRUST`, `CAUTION`, `RECHECK_SOON`, `DEGRADING`, `OUT OF DOMAIN`), calibrated bust risk %, and a plain-language operational recommendation.
  2. **Advanced Mode:** An expandable technical drawer (`🔬 Technical ML Telemetry & Atmospheric Moments`) displaying ensemble dispersion moments (mean, std, P10-P90 range, CV), stability score, structural overconfidence, and Mahalanobis $D_M$ distance.
  In Builder 1's React 19 app, only a single fixed view exists.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Replicate Builder 2's 15-Second Hero Card and Expandable Technical Drawer in the React 19 application.

### Feature T: Model / Data Version Center
- **Status:** PARTIALLY IMPLEMENTED
- **Findings:**  
  Rich cryptographic metadata exists internally (`reports/final_scientific_report/reproducibility_manifest.json`, `models/day4/model_metadata.json`) locking dataset hashes, git commits, feature schemas, and training hyperparameters. The backend exposes this via `/v1/health` and `/v1/metrics/evaluation`. The frontend only renders a small static version string in the footer.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Build an interactive "Model & Data Provenance" modal in the React dashboard showing active model hash, training dataset size, decision threshold, and calibrator status.

### Feature U: Public API / API Key System
- **Status:** NOT IMPLEMENTED
- **Findings:**  
  FastAPI endpoints exist, but have zero authentication, no API key middleware, no rate tiering by key, and no developer documentation portal.
- **Recommended Action:** BUILD NEW. Add standard API key authentication middleware (`X-API-Key`) and an automated developer documentation page.

### Feature V: PWA / Installable App
- **Status:** NOT IMPLEMENTED
- **Findings:**  
  No `manifest.json`, service worker, or Workbox offline caching exists in `frontend/`.
- **Recommended Action:** BUILD NEW. Add `vite-plugin-pwa`, web app manifest, and offline shell caching.

### Feature W: Exportable Reports
- **Status:** PARTIALLY IMPLEMENTED
- **Findings:**  
  `research/evaluation/final_report_generator.py` generates comprehensive Markdown and JSON evaluation reports. However, there is no user-facing download button in either the React app or static dashboard to export prediction results as CSV or PDF.
- **Recommended Action:** EXTEND EXISTING IMPLEMENTATION. Add a client-side CSV/JSON report export button in the React dashboard.

---

## 9. Research & Evaluation Features

### Feature O: Analog Ensemble (Historical Trajectory Analogue Retrieval)
- **Status:** RESEARCH / EXPERIMENTAL
- **Evidence:**  
  - Engine: `evaluation/trajectory_analogues.py::HistoricalTrajectoryRetriever` (L13–60)
  - Memory: `evaluation/event_memory.py::HistoricalEventMemory`
  - Integration: `evaluation/event_intelligence.py:L110-142`
  - Tests: `tests/test_day16_temporal_early_warning.py:L366-390`, `tests/test_day18_event_intelligence.py:L394-428`
- **Capabilities Verified:**  
  Performs $k$-nearest-neighbor matching ($k=15$) across trajectory evolution feature vectors:
  `["current_risk", "risk_slope", "risk_acceleration", "spread_slope", "revision_velocity", "current_lead_hours"]`.
  Computes empirical failure rates and similarity scores for matched historical forecast sequences. Returns `INSUFFICIENT_HISTORICAL_SUPPORT` when no analogues match.
- **Recommended Action:** DO NOT REBUILD FROM SCRATCH. EXTEND EXISTING IMPLEMENTATION by importing `HistoricalTrajectoryRetriever` into the backend prediction pipeline.

### Feature X: Research Benchmark Suite
- **Status:** FULLY IMPLEMENTED (Highly mature research framework)
- **Evidence:**  
  - Validation Schemes: `research/evaluation/validation_schemes.py`
    - Walk-Forward rolling temporal evaluation
    - Leave-One-Region-Out (LORO) spatial cross-validation
    - 500-sample Stratified Bootstrap confidence intervals
  - Model Selection Gate: `research/evaluation/model_selection_gate.py` (strict gates on Brier Skill Score, ECE $\le 0.05$, and PR-AUC)
  - Red Team Adversarial Suite: `research/redteam/redteam_scientific_audit.py`, `research/redteam/test_suite.py` (checks for leakage, coordinate memorization, single-class collapse, and boundary violations)
- **Recommended Action:** DO NOT REBUILD. ALREADY DONE.

---

## 10. Additional Builder 2 Features Discovered (Unlisted Work)

Builder 2 implemented several sophisticated capabilities that were **NOT included in the proposed feature list**:

### 1. Mathematical Failure Fingerprint / Archetype Engine
- **Files:** `research/failure_fingerprint/engine.py`, `features/instability_fingerprint.py`, `api/risk_engine.py`, `backend/app/builder2/instability_fingerprint.py`
- **What it is:** Classifies incoming forecast anomalies into 6 non-causal physical failure archetypes:
  1. `STABLE_SYNOPTIC_CONSENSUS`: Coherent multi-member agreement under quiescent synoptic flow.
  2. `TIGHT_CLUSTER_BREAKDOWN` / `ENSEMBLE_BIFURCATION`: Under-dispersed ensemble failing to span the outcome space.
  3. `RAPID_REVISION_SHOCK`: Run-to-run flipping exceeding inter-cycle tolerance.
  4. `DIURNAL_CONVECTIVE_MISMATCH`: Diurnal phase mismatch during boundary-layer heating.
  5. `WIND_GRADIENT_SHEAR`: High surface wind divergence / frontal timing uncertainty.
  6. `LONG_LEAD_DECAY`: Unavoidable loss of atmospheric predictability at extended horizons ($>120\text{h}$).
- **Value:** Gives users an instant physical explanation of *why* the forecast is at risk of failing.

### 2. Operational Trust Horizon Engine ($H_{\text{rel}}$ & $H_{\text{skill}}$)
- **Files:** `research/trust_horizon/engine.py`, `evaluation/trust_horizon.py`
- **What it is:** Calculates the exact lead-time hour at which forecast trust terminates:
  - $H_{\text{rel}}$: The lead hour where calibrated bust probability crosses the critical decision threshold ($P_{\text{crit}} = 0.35$ or $0.06$).
  - $H_{\text{skill}}$: The lead hour where the model's predictive skill drops below climatological reference skill.
- **Value:** Directly answers the operational question: *"Up to how many hours into the future can I trust this weather forecast?"*

### 3. 5-Level Operational Decision Mode & Safety Arbitration Engine
- **Files:** `research/decision/mode_engine.py`, `evaluation/decision_engine.py`, `api/risk_engine.py`
- **What it is:** Translates abstract ML probabilities into five standardized operational decision modes:
  1. `HIGH_TRUST`: Forecast is within the reliable trust envelope; proceed with standard workflows.
  2. `CAUTION`: Moderate risk detected; exercise operational vigilance and monitor intermediate cycles.
  3. `RECHECK_SOON`: High inter-cycle volatility or revision shock; recheck before committing to irreversible actions.
  4. `DO_NOT_RELY_SOLELY`: Extended lead predictability decay; supplement with alternative guidance.
  5. `ABSTAIN`: Out-of-distribution atmospheric state ($D_M \ge 40.0$) or corrupted inputs; manual meteorological consultation required.
- **Value:** Bridges the gap between data science and operational decision-making.

### 4. AWS S3 Direct Byte-Range GRIB2 Extraction Pipeline
- **Files:** `ingestion/adapters/noaa_s3.py`, `ingestion/historical_gefs_collector.py`, `scripts/extract_phase5b2_atomic.py`
- **What it is:** Uses ecCodes and HTTP byte-range requests directly against the public `s3://noaa-gefs-retrospective` bucket to extract only the grid points covering India, without downloading full terabyte-scale global GRIB2 files.
- **Value:** Allows cost-effective, reproducible historical reforecast data mining.

### 5. XAI Counterfactual Analysis Engine
- **Files:** `evaluation/xai_engine.py`, `evaluation/xai_counterfactual.py`
- **What it is:** Generates counterfactual explanations answering: *"What is the minimum atmospheric change that would bring this high-risk forecast back into the HIGH_TRUST envelope?"* (e.g. "If ensemble spread decreased by 0.8 m/s and 24h revision was under 1.2°C, forecast would enter HIGH_TRUST").
- **Value:** Provides actionable transparency for power grid operators and emergency managers.

---

## 11. Features Already Complete (Must NOT Be Rebuilt)

The following capabilities have been fully coded, tested, and validated by Builder 2. **Rebuilding them from scratch would be redundant and wasteful:**

1. **Adaptive Bust Threshold Engine** (`labels/label_engine.py`): Stratified $q_{95}$ thresholding across Location $\times$ Variable $\times$ Lead Bin with hierarchical fallbacks.
2. **Probability Calibrator** (`evaluation/calibration.py`): Zero-dependency Platt Sigmoid and Isotonic PAV calibrators.
3. **Continuous Ranked Probability Score (CRPS)** (`research/evaluation/metrics.py`): Exact trapezoidal quadrature integration of quantile mesh pinball loss.
4. **4-Tier Benchmark Baselines** (`models/baselines.py`): Climatology, 24h Persistence, Spread Heuristic, and Majority Class baselines.
5. **Research Benchmark & Validation Suite** (`research/evaluation/validation_schemes.py`): Walk-Forward, Leave-One-Region-Out, and 500-sample Stratified Bootstrap cross-validation.
6. **Mathematical Failure Fingerprint Catalog** (`research/failure_fingerprint/engine.py`): 6 atmospheric failure archetypes.
7. **Operational Trust Horizon Calculation** (`research/trust_horizon/engine.py`): $H_{\text{rel}}$ and $H_{\text{skill}}$ horizon boundary algorithms.
8. **5-Level Operational Decision Mode Engine** (`research/decision/mode_engine.py`): Operational decision mode derivation logic.

---

## 12. Features Partially Complete (What Remains)

| Feature | What Builder 2 Completed | What Remains to Complete |
| :--- | :--- | :--- |
| **Reliability Diagram** | ECE metric calculation, 5–10 probability bin generators, JSON chart specification | Frontend SVG/Canvas chart component rendering the curve |
| **Forecast Revision Tracker** | $\Delta_{6h}, \Delta_{24h}$, spread deltas, stability index computed in feature pipeline | Expose in FastAPI `PredictionResponse`, build interactive UI widget |
| **Geographic Bust-Risk Map** | Spatial aggregation across 25 stations into 6 regional summaries | Leaflet/MapLibre interactive India risk map on frontend |
| **Simple / Advanced UI** | Progressive disclosure implemented in static HTML prototype (`static/index.html`) | Replicate 15-Second Hero Card and Telemetry Drawer in React 19 SPA |
| **Exportable Reports** | Comprehensive JSON and Markdown report generators in `final_report_generator.py` | Add client-side CSV / JSON download button in React UI |
| **Model / Data Version Center** | Cryptographic provenance manifests locking git commit, data hash, model params | Create dedicated "Model Card & Data Provenance" UI modal/tab |
| **Reliability Score** | Composite Confidence Index (0–100 heuristic) implemented and documented | Display prominently in React dashboard alongside bust probability |
| **Extreme Weather Mode** | Failure fingerprints detect convective/extreme regimes; triggers `RECHECK_SOON` | Wire fingerprint and decision mode into production React UI |
| **Variable-Specific Verification** | Stratified metric reports per variable generated | Add CSI/ETS for precipitation and vector RMSE for wind speed |

---

## 13. Features Existing Only as Research (Path to Production)

The following features exist as working, tested Python research code in Tree 2, but are completely disconnected from the active Tree 1 application:

1. **Monotonic Quantile Mesh Prediction Intervals (`research/error_distribution/quantile_mesh.py`):**  
   *Path to Production:* Move `QuantileMeshDistribution` into `backend/app/ml/`, train/load the quantile booster, and output the $[q_{05}, q_{95}]$ uncertainty band in `PredictionResponse`.
2. **Historical Trajectory Analogue Retrieval (`evaluation/trajectory_analogues.py`):**  
   *Path to Production:* Index historical training trajectories into an in-memory KD-Tree/k-NN store inside `backend/app/services/reference_service.py`, and return top 3 matching historical analogues during live prediction.
3. **CRPS Probabilistic Evaluation Metric (`research/evaluation/metrics.py`):**  
   *Path to Production:* Import `calculate_crps_empirical` into `backend/app/services/evaluation_service.py` to evaluate incoming predictions against delayed ERA5 truth.
4. **Adversarial Red Team Audit Suite (`research/redteam/test_suite.py`):**  
   *Path to Production:* Add `test_redteam.py` to the main CI test runner (`backend/tests/`) to permanently prevent target leakage or coordinate memorization.

---

## 14. Features Genuinely Not Started

The following proposed features have **zero code implementation** in either Builder 1 or Builder 2:

1. **Multi-Model Disagreement:** Ingesting other NWP models (ECMWF IFS, DWD ICON, UKMO) and calculating multi-model variance.
2. **Rolling Calibration Drift Monitoring:** Automated background pipeline re-evaluating calibration curves on rolling 30-day windows as observations arrive.
3. **Public Developer API & API Key System:** Authentication middleware, quota management, and developer documentation portal.
4. **Saved Locations / Favorites:** Persistent user watchlists stored via browser `localStorage`.
5. **Proactive Reliability Alerting:** Webhook, email, or browser push notifications triggered by threshold crossings.
6. **Progressive Web App (PWA):** Service worker, installable web manifest, and offline shell caching.
7. **Talagrand Rank Histogram:** Ensemble rank distribution generator.

---

## 15. Builder 1 vs Builder 2 Overlap & Synthesis

| Area | Builder 1 Implementation | Builder 2 Implementation | Overlap & Conflict | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Framework** | Production FastAPI gateway with rate limiting, logging, SingleFlight, LRU cache | Standard library `http.server` in `server.py` | Conflicting server implementations | **KEEP BUILDER 1 FASTAPI.** Discard Builder 2 `server.py`. |
| **Model Adapter** | `backend/app/builder2/` adapter running Day 4 26-feature prototype | 50-feature V2 Champion architecture | Contract mismatch: 26 features vs 50 features | **UPGRADE ADAPTER.** Train/load the 50-feature champion model into Builder 1 adapter. |
| **Weather Ingestion** | `openmeteo_service.py` live GEFS HTTP client | AWS S3 GRIB2 reforecast collector with ecCodes | Live vs historical reforecast | **KEEP BUILDER 1 FOR LIVE, BUILDER 2 FOR HISTORICAL.** Fix Builder 1 to query ensemble members. |
| **Explainability** | Rule-based top 3 driver extraction | Tree SHAP + 6 Failure Fingerprints + Counterfactuals | Builder 2 explainability is vastly superior | **ADOPT BUILDER 2 EXPLAINABILITY.** Integrate failure fingerprints into Builder 1 response schema. |
| **Frontend UI** | React 19 + Vite + Tailwind/CSS SPA | Single-file HTML/CSS/JS in `static/index.html` | Technology divergence | **KEEP BUILDER 1 REACT 19.** Port Builder 2's UI concepts (Hero Card, Fingerprint Card, Telemetry Drawer) into React. |

---

## 16. Existing Problems Blocking Advanced Features

Before building any advanced features, the following **critical bugs and blockers** identified in the audit must be addressed:

1. **Live Ensemble Spread Collapse to 0.0:**  
   `backend/app/services/openmeteo_service.py` does not request or parse ensemble member arrays from Open-Meteo. In `backend/app/builder2/feature_pipeline.py:L106`, `ensemble_std` defaults to `0.0`. Every spread-based feature and the Spread/Skill ratio are broken in live production.
2. **Wind Speed Unit Inconsistency:**  
   `openmeteo_service.py` fetches wind speed in $m/s$, while the training feature pipeline (`configs/bust_thresholds.json`, `data_pipeline/standardize.py`) expects $km/h$. ($10\text{ m/s} = 36\text{ km/h}$; the threshold of $13.04\text{ km/h}$ corresponds to only $3.6\text{ m/s}$).
3. **Missing V2/V3 Model Binaries:**  
   `models/v2/lightgbm_v2_champion.joblib` and `models/v3/lightgbm_v3_challenger.joblib` are completely missing from the workspace because `.gitignore` excluded `*.joblib`. The active server falls back to the Day 4 prototype model.
4. **Broken Import in Research Test Suite:**  
   `training/run_phase5b1_experiment.py` and `tests/test_phase5b1_error_distribution.py` attempt to import from `models.error_distribution`, but the actual directory was placed at `research/error_distribution/`.

---

## 17. Revised Phase 3 Roadmap (De-Duplicated)

By recognizing Builder 2's existing research, the Phase 3 roadmap is streamlined to eliminate redundant work:

### Phase 3A: Scientific Reliability Foundation
- [ ] **Fix P0 Input Bugs:** Add ensemble member parsing to `openmeteo_service.py` (spread $> 0$) and standardize wind units ($m/s \rightarrow km/h$).
- [ ] **Wire CRPS:** Connect Builder 2's existing `calculate_crps_empirical` into `backend/app/services/evaluation_service.py`.
- [ ] **Expose Reliability Diagram:** Add a FastAPI endpoint returning `ReliabilityAnalyzer.compute_reliability_curve()` bins, and render an interactive SVG/Canvas calibration curve in React.
- [ ] **Build Rank Histogram:** Implement Talagrand rank histogram calculation in `models/verification_engine.py`.

### Phase 3B: Advanced Intelligence & Explainability
- [ ] **Port Failure Fingerprints & Decision Modes:** Integrate Builder 2's 6 Failure Archetypes and 5 Decision Modes into Builder 1's `ForecastBustAgent` and React dashboard.
- [ ] **Expose Forecast Revision & Stability:** Add `stability_index` and 24h revision metrics to `PredictionResponse` and render a Forecast Stability widget.
- [ ] **Wire Historical Trajectory Analogues:** Connect Builder 2's `HistoricalTrajectoryRetriever` into the prediction pipeline to show top 3 matching historical forecast paths.
- [ ] **Multi-Model Disagreement:** Build an ingestion adapter for ECMWF/ICON and compute cross-model variance.

### Phase 3C: User Product Experience
- [ ] **15-Second Hero Decision Card:** Implement Builder 2's high-impact operational decision card in React 19.
- [ ] **Simple / Advanced Mode Toggle:** Add a toggle in the React UI to switch between the 15-Second Summary and the Deep-Dive Telemetry Drawer.
- [ ] **Geographic Bust-Risk Map:** Connect existing `/v1/multi-location` backend data to a Leaflet/MapLibre India risk map.
- [ ] **Saved Locations:** Persist favorite locations via browser `localStorage`.
- [ ] **Exportable Reports:** Add client-side CSV and JSON export buttons.

### Phase 3D: Platform & Developer Infrastructure
- [ ] **Model & Data Version Center:** Create a UI modal displaying model card provenance, artifact hash, and training metadata.
- [ ] **Public Developer API:** Implement API key authentication middleware (`X-API-Key`) and interactive API docs.
- [ ] **PWA Support:** Add service worker and web app manifest for installable offline capability.

---

## 18. Top 10 Genuinely New Features Worth Building

1. **Multi-Model Disagreement Engine:** Ingest ECMWF IFS and DWD ICON alongside NOAA GEFS to compute true inter-model forecast divergence.
2. **Interactive Geographic Bust-Risk Map (India):** Leaflet/MapLibre map visualizing spatial risk tiers across the 25 IMD canonical stations.
3. **Interactive Reliability Diagram Component:** High-chart / SVG calibration curve with observed frequency vs predicted probability bins and ECE scores.
4. **Proactive Reliability Watchlist & Alert System:** User-configured webhook/email alerts triggered when bust probability or revision shock exceeds threshold.
5. **Saved Locations / Station Favorites:** Browser-persisted station bookmarks with quick-access tabs.
6. **Simple / Advanced UI Switcher:** Operational toggle between the 15-Second Hero Decision Card and the Deep-Dive Atmospheric Telemetry Drawer.
7. **Talagrand Rank Histogram Generator:** Probabilistic verification histogram evaluating ensemble dispersion reliability.
8. **Client-Side CSV/JSON Report Exporter:** One-click export of forecast risk timelines and explainability traces.
9. **Developer API Key & Rate-Tier Management:** Secure token-based access control for programmatic enterprise users.
10. **Progressive Web App (PWA) Deployment:** Installable mobile/desktop experience with offline shell caching.

---

## 19. Highest-Value Existing Builder 2 Work to Productize

1. **Failure Fingerprint / Archetype Engine (`research/failure_fingerprint/`):** Immediately gives users human-understandable meteorological reasons for risk (`CONVECTIVE_MISMATCH`, `REVISION_SHOCK`, `LEAD_DECAY`).
2. **5-Level Operational Decision Modes (`research/decision/mode_engine.py`):** Turns abstract probabilities into actionable pre-execution guidance (`HIGH_TRUST`, `CAUTION`, `RECHECK_SOON`, `DO_NOT_RELY_SOLELY`, `ABSTAIN`).
3. **Operational Trust Horizon ($H_{\text{rel}}$ & $H_{\text{skill}}$) (`research/trust_horizon/`):** Defines the exact future hour where forecast reliability breaks down.
4. **Monotonic Quantile Mesh Uncertainty Envelopes (`research/error_distribution/`):** Provides statistically valid 90% error bounds $[q_{05}, q_{95}]$ with Chernozhukov sorting.
5. **Historical Trajectory Analogue Retrieval (`evaluation/trajectory_analogues.py`):** Surfaces real historical precedents matching current forecast evolution paths.

---

## 20. Final Recommendation

### WHAT SHOULD WE FIX?
1. **Fix live ensemble spread extraction in `openmeteo_service.py`:** Request individual ensemble members from Open-Meteo so `ensemble_std` is real ($> 0.0$).
2. **Fix wind speed unit conversion:** Convert live Open-Meteo $m/s$ to $km/h$ to match the training feature schema.
3. **Fix broken research test import:** Update `models.error_distribution` to `research.error_distribution` in `tests/test_phase5b1_error_distribution.py`.

### WHAT SHOULD WE EXTEND?
1. **Extend Builder 2's Reliability Diagram spec:** Connect `ReliabilityAnalyzer.compute_reliability_curve()` to an interactive React calibration curve.
2. **Extend Forecast Revision features:** Expose `stability_index` and $\Delta_{24h}$ in `PredictionResponse` and the React UI.
3. **Extend Regional Risk Aggregator:** Connect the existing `/v1/multi-location` endpoint to a new frontend Leaflet map.
4. **Extend Quantile Mesh research:** Productionize the 90% uncertainty envelope into live API responses.

### WHAT SHOULD WE NOT REBUILD?
1. **DO NOT rebuild Bust Labeling:** The Location $\times$ Variable $\times$ Lead Bin $q_{95}$ engine is mathematically complete.
2. **DO NOT rebuild Calibration:** Platt Sigmoid and Isotonic PAV calibrators are already implemented with zero external dependencies.
3. **DO NOT rebuild Baselines:** Climatology, Persistence, and Spread Heuristic baselines are fully implemented.
4. **DO NOT rebuild CRPS calculation:** `calculate_crps_empirical` is already written and tested.
5. **DO NOT rebuild Research Validation:** Walk-Forward, Leave-One-Region-Out, and Bootstrap validation are complete.

### WHAT SHOULD WE BUILD NEW?
1. **Multi-model comparison:** Ingest ECMWF / ICON alongside GEFS.
2. **Interactive Geographic Map:** Leaflet/MapLibre visualization of Indian station risks.
3. **Interactive Calibration UI:** Canvas/SVG reliability diagram.
4. **User-facing product features:** Saved locations (`localStorage`), CSV export, and API key authentication.

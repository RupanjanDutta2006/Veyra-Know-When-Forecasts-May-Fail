# Veyra — Know When Forecasts May Fail
## Day-5 Builder 1 Development Overview: Feature Engineering & Baseline ML Pipeline

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 1 (Backend API, Leakage-Safe Feature Engineering, Chronological Splitting, Baseline Logistic ML & Evaluation)  
**Date:** August 26, 2026  
**Git Branch:** `rupanjan/historical-labels` (Working branch for Day 4 & Day 5 ML Foundations)  
**Test Status:** 81/81 Automated Tests Passing (100%)  

---

## 1. Executive Summary

On **Day 5**, Builder 1 implemented the **Leakage-Safe Feature Engineering and Baseline ML Training & Evaluation Pipeline** on top of the Day-4 historical verification and bust-labeling foundation.

- **Key Achievements:**
  1. Built an **Inference-Safe Feature Engineering Pipeline** (`InferenceSafeFeatureExtractor`, `FeaturePipeline`, `FeatureSchema`) extracting 18 deterministic predictors available strictly at forecast issue time.
  2. Implemented strict **Anti-Data-Leakage Validation**: Explicitly prohibits ground-truth reference values (ERA5), forecast errors, absolute errors, and bust labels from feature matrix $X$.
  3. Created a **Chronological Time-Aware Data Splitter** (`TemporalDataSplitter`, `DatasetSplits`) enforcing $\text{Train} \prec \text{Validation} \prec \text{Test}$ strictly by issue timestamp with zero future overlap.
  4. Enforced **Training-Only Parameter Fitting**: Normalization scalers and model parameters are fitted exclusively on the `train` partition and applied deterministically to `val` and `test`.
  5. Implemented an interpretable **Baseline Classifier** (`LogisticRegressionBustModel`) with balanced class weighting (`class_weight='balanced'`) outputting true continuous probabilities $P(\text{bust}) \in [0.0, 1.0]$.
  6. Implemented a comprehensive **Model Evaluator** (`ModelEvaluator`, `EvaluationReport`) computing Precision, Recall, F1 Score, Accuracy, ROC-AUC, Brier score, and Confusion Matrix with explicit reporting of **False Negatives** (missed busts).
  7. Created a **Model Artifact & Metadata Manager** (`ModelArtifactManager`, `ModelMetadata`) serializing model bundles and human-readable metadata (`models/baseline_logistic_v1_metadata.json`).
  8. Maintained **Safe Production Invariants**: `/v1/predict` strictly preserves safe `MODEL_NOT_READY` abstention (`bust_probability: null`, `abstain: true`). Live inference is not activated until full offline verification is confirmed.
  9. Added 11 new automated unit tests, bringing the test suite to **81 tests (100% passing in 2.85s)**.
  10. Verified an end-to-end ML smoke test (`scripts/smoke_test_ml.py`).

---

## 2. Feature Schema & Inference-Time Safety

### Features Included in $X$ (18 Features):
| Feature Name | Type | Description | Why It Is Inference-Safe |
|---|:---:|---|---|
| `lead_hours` | Continuous | Forecast lead time in hours | Determined at issue time by target forecast horizon |
| `forecast_value` | Continuous | Numerical forecasted meteorologic value | Produced by the forecast model at issue time |
| `latitude` | Continuous | Target geographical latitude | Known static location coordinate |
| `longitude` | Continuous | Target geographical longitude | Known static location coordinate |
| `month` | Integer (1–12) | Forecast validity month | Known calendar date at issue time |
| `sin_month`, `cos_month` | Continuous | Cyclic trigonometric month encoding | Periodic representations of seasonality |
| `sin_hour`, `cos_hour` | Continuous | Cyclic trigonometric issue-hour encoding | Diurnal initialization cycle (00Z, 06Z, 12Z, 18Z) |
| `var_*` (5 One-Hot Columns) | Binary | `temperature_2m`, `surface_pressure`, `wind_speed_10m`, `relative_humidity_2m`, `precipitation` | Standard meteorological variable identifiers |
| `season_*` (4 One-Hot Columns) | Binary | `winter`, `spring`, `summer`, `autumn` | Calendar meteorological season |

### Forbidden Leakage Fields (Strictly Excluded from $X$):
- `reference_value` / `observed_value` (ERA5 / station truth)
- `error` / `forecast_error` / `absolute_error`
- `bust_label` / `bust_threshold` (Ground truth label)
- `reference_source` / `availability_time`

---

## 3. Chronological Dataset Splitting Strategy

Implemented in [backend/app/ml/splitting.py](file:///backend/app/ml/splitting.py):

$$\text{Sort by } (\text{issue\_time}, \text{valid\_time}) \quad \Longrightarrow \quad \text{Train (70\%)} \;\longrightarrow\; \text{Validation (15\%)} \;\longrightarrow\; \text{Test (15\%)}$$

### Temporal Invariant:
$$\max(\text{Train.issue\_time}) \le \min(\text{Val.issue\_time}) \le \max(\text{Val.issue\_time}) \le \min(\text{Test.issue\_time})$$

Violations raise a `TemporalLeakageError` immediately.

---

## 4. Training-Only Preprocessing & Threshold Fitting

1. **Standard Scaler ($\mu, \sigma$):** Calculated exclusively on $X_{\text{train}}$. Features in validation, test, and live inference are transformed using the fixed training parameters:
   $$x_{\text{norm}} = \frac{x - \mu_{\text{train}}}{\sigma_{\text{train}}}$$
2. **Quantile Bust Thresholds ($q95$):** When statistical thresholds are used, `QuantileBustPolicy.fit_from_errors()` is called exclusively on training errors before labeling and training.

---

## 5. Baseline Logistic Regression Model

Implemented in [backend/app/ml/baseline_model.py](file:///backend/app/ml/baseline_model.py):
- **Model:** `LogisticRegression(C=1.0, class_weight='balanced', random_state=42)`
- **Class Imbalance:** Handled conservatively via inverse-frequency class weighting to penalize false negatives on rare bust events.
- **Probability Output:** Real model output $P(\text{bust} = 1 \mid X) \in [0.0, 1.0]$.

---

## 6. Evaluation Metrics & Confusion Matrix

Implemented in [backend/app/ml/evaluation.py](file:///backend/app/ml/evaluation.py):

| Metric | Purpose |
|---|---|
| **Precision** | $\frac{\text{TP}}{\text{TP} + \text{FP}}$ — Reliability of bust alarms |
| **Recall** | $\frac{\text{TP}}{\text{TP} + \text{FN}}$ — Coverage of actual forecast busts |
| **F1 Score** | $2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$ — Harmonic balance |
| **ROC-AUC** | Area under the ROC curve (discrimination capacity) |
| **Brier Score Loss** | Mean squared difference between predicted $P(\text{bust})$ and binary ground truth |
| **False Negatives (FN)** | **Primary Safety Metric:** Actual forecast busts that the system failed to flag |

---

## 7. How to Run the Smoke Test

```bash
python scripts/smoke_test_ml.py
```

**Smoke Test Output:**
```text
=================================================================
 VEYRA DAY 5 — ML PIPELINE & BASELINE MODEL SMOKE TEST
=================================================================
[1/9] Historical labeled rows loaded: 90 samples
[2/9] Temporal split created successfully:
      - Train: 62 samples | Time Range: 2026-07-01T00:00:00Z to 2026-07-19T00:00:00Z
      - Val:   13 samples | Time Range: 2026-07-19T00:00:00Z to 2026-07-23T00:00:00Z
      - Test:  15 samples | Time Range: 2026-07-24T00:00:00Z to 2026-07-28T00:00:00Z
[3/9] Train class distribution: 19 BUST (30.6%), 43 NON-BUST
[4/9] Training-only feature pipeline fitted: 18 features
[5/9] Feature matrices transformed: X_train shape=(62, 18), X_val shape=(13, 18), X_test shape=(15, 18)
[6/9] Baseline Logistic Regression model trained with class_weight='balanced'
[7/9] Validation evaluation completed:
      - Accuracy:  0.6923
      - Precision: 0.4000
      - Recall:    0.6667
      - F1 Score:  0.5000
      - Brier Loss:0.2383
      - Confusion: TP=2, FP=3, TN=7, FN=1 (False Negatives)
[8/9] Test evaluation completed:
      - Accuracy:  0.6000
      - F1 Score:  0.5000
      - Sample P(bust): 0.3538 (range [0.3538, 0.6856])
[9/9] Model artifact persisted safely:
      - Binary Bundle: models/baseline_logistic_v1.joblib
      - Metadata JSON: models/baseline_logistic_v1_metadata.json

--- ANTI-DATA-LEAKAGE AUDIT ---
  ERA5 / Reference values in features:  NO (PASS)
  Forecast error in features:          NO (PASS)
  Absolute error in features:          NO (PASS)
  Bust label in features:              NO (PASS)
  Temporal split boundary check:       PASS (train_max <= val_min <= test_min)
  Training-only scaler & weights:      PASS (fitted exclusively on train split)
--------------------------------

[+] DAY 5 ML PIPELINE SMOKE TEST COMPLETED SUCCESSFULLY.
```

---

## 8. Test Execution Results (81 Tests Passing)

```bash
python -m pytest
```

```text
Platform: win32 | Python: 3.13.5 | Pytest: 9.1.1
Root Directory: C:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail

Results Breakdown:
  - backend/tests/test_agent.py                 8 PASSED (Day 1-2 Pipeline suite)
  - backend/tests/test_bust_labeling.py         5 PASSED (Day 4 Bust Labeling suite)
  - backend/tests/test_health.py                2 PASSED (Day 1 Health suite)
  - backend/tests/test_historical_alignment.py  6 PASSED (Day 4 Alignment suite)
  - backend/tests/test_historical_dataset.py    4 PASSED (Day 4 Dataset suite)
  - backend/tests/test_ml_features.py           4 PASSED (Day 5 Feature Engineering suite)
  - backend/tests/test_ml_model_and_eval.py     4 PASSED (Day 5 Baseline ML & Eval suite)
  - backend/tests/test_ml_splitting.py          3 PASSED (Day 5 Temporal Splitting suite)
  - backend/tests/test_predict.py              11 PASSED (Day 1-2 Predict API suite)
  - backend/tests/test_qc.py                    7 PASSED (Day 3 Quality Control suite)
  - backend/tests/test_schemas.py               6 PASSED (Day 1-3 Schemas suite)
  - backend/tests/test_services.py              8 PASSED (Day 2 Base Services suite)
  - backend/tests/test_unit_conversion.py       5 PASSED (Day 4 Unit Conversion suite)
  - backend/tests/test_weather_ingestion.py     8 PASSED (Day 3 Ingestion suite)
  ============================= 81 passed in 2.85s =============================
```

---

## 9. Future Integration with `ModelService` & Builder 2

When Builder 2 or subsequent development activates live inference:
1. `FeatureService` will consume live `CanonicalForecastRecord`s and call `FeaturePipeline.transform_inference(records)`.
2. `ModelService` will load `baseline_logistic_v1.joblib` via `ModelArtifactManager.load_artifact()` and invoke `predict_proba(X)`.
3. `SafetyEvaluator` will calibrate/assess the output probability, and `ForecastBustAgent` will return `bust_probability`.

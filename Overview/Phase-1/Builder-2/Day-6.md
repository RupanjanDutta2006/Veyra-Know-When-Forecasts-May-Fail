# Veyra — Phase 1 / Builder 2 / Day 6

## Conservative LightGBM Classifier & Platt Sigmoid Probability Calibration

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 2 (Scientific Meteorological Intelligence & ML Subsystem)  
**Components:** `backend/app/builder2/tree_classifier.py`, `calibrator.py`, `model_service.py`  

---

## 1. Objective

The objective of Builder 2 on Day 6 was to train a conservative, anti-overfitting LightGBM decision tree classifier and implement post-hoc Platt Sigmoid probability calibration in pure NumPy to guarantee reliable, calibrated forecast bust probabilities.

---

## 2. Work Completed

1. **LightGBM Bust Classifier:**
   - Model Version: `prototype-gbm-v1`
   - Decision Threshold: `0.280`
   - Hyperparameters configured to strictly prevent overfitting on rare bust events:
     - `n_estimators`: 50
     - `max_depth`: 3
     - `num_leaves`: 7
     - `learning_rate`: 0.05
     - `min_child_samples`: 15
     - `subsample`: 0.8
     - `colsample_bytree`: 0.8
     - `scale_pos_weight`: Empirically computed ($N_{\text{neg}} / N_{\text{pos}}$)
   - Artifact: `models/day4/lightgbm_bust_model.joblib`
2. **Platt Sigmoid Probability Calibrator:**
   - Implemented in pure NumPy (`backend/app/builder2/calibrator.py`)
   - Fitted Parameters:
     - Slope $w = 0.034347$
     - Intercept $b = -2.778305$
   - Performance Impact:
     - Uncalibrated Brier Score: $0.2043$
     - Calibrated Brier Score: $0.0508$
     - **Brier Score Improvement: 75.12%**
   - Artifact: `models/day4/probability_calibrator.joblib`
3. **Model Service Wrapper:** Built `ForecastBustModelService` managing feature preparation, LightGBM inference, probability calibration, and clipping $P(\text{bust}) \in [0.0, 1.0]$.

---

## 3. Architecture & Inference Flow

```text
Raw Features (26 columns) ─► [ LightGBM Tree Ensemble ] ─► Raw Logits / Probs
                                                                   │
                                                                   ▼
Calibrated Prob P(bust) ◄── [ np.clip(0.0, 1.0) ] ◄── [ Platt Sigmoid Calibrator ]
```

---

## 4. Verification

- Verified model artifact loading and inference latency (< 5ms).
- Confirmed calibrated probability output bounds $P \in [0.0, 1.0]$.
- Verified 75.12% Brier score improvement on holdout test set.

---

## 5. Day Status

**STATUS: COMPLETE**

---

**Previous:** [Day 5](./Day-5.md) | **Next:** [Day 7](./Day-7.md)

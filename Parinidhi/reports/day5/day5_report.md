# Day 5 Final Report — Calibration, Model Packaging & Stable Inference Contract

**Generated:** 2026-08-26
**Model Version:** `prototype-gbm-v1`
**Decision Threshold:** `0.280`

---

## 1. Executive Summary

Day 5 established the production-ready inference packaging layer for Forecast-Bust Sentinel:
* **Service Module:** [`models/model_service.py`](file:///c:/Users/parin/OneDrive/Desktop/forecast-bust-sentinel/models/model_service.py) exposing `ForecastBustModelService`.
* **Public Prediction Interface:** `service.predict(features: pd.DataFrame) -> list[dict]` and `service.predict_single(features: dict) -> dict`.
* **Inference Pipeline:** Schema validation $\to$ Canonical 26-feature ordering $\to$ LightGBM inference $\to$ Platt Sigmoid calibration $\to$ Threshold decision ($P \ge 0.280 \implies \text{bust\_alert} = \text{true}$).
* **Parity Guarantee:** Exact floating-point parity with direct Day 4 LightGBM + calibrator execution (max absolute difference $< 10^{-12}$).

---

## 2. Public Prediction API Contract

### Response Format
```json
{
  "probability": 0.004834669133828389,
  "bust_alert": false,
  "model_version": "prototype-gbm-v1"
}
```

* **`probability`:** Continuous calibrated probability float in $[0.0, 1.0]$ (unrounded).
* **`bust_alert`:** Boolean flag strictly evaluated as `probability >= 0.280`.
* **`model_version`:** `"prototype-gbm-v1"`.

---

## 3. Test Suite & Dependency Telemetry Status

* **Test Suite Result:** 64 tests passed, 0 failed, 0 warnings in 15.89s.
* **Compatibility:** All existing Day 4 / Day 5 model checkpoints deserialize and evaluate with exact parity.

### Current Verified Main Environment
```
Python:   3.14.7
NumPy:    2.4.6
joblib:   1.5.3
LightGBM: 4.7.0
pandas:   3.0.5
pytest:   9.1.1
```

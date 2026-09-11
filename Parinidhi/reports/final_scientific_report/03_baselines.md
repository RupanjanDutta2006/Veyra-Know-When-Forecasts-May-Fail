# Chapter 3: Baseline Hierarchy Performance (E0, E1b, E2, E3)

**Scientific Status:** `VALIDATED`

## 1. Evaluated Baseline Hierarchy
- **E0 (Climatology Baseline):** Empirical historical bust frequency computed per station and variable strictly on historical training split (2000–2013).
- **E1b (Fair Ensemble Baseline):** Logistic regression fit on core physical ensemble moments (`ensemble_std`, `lead_hours`, `ensemble_mean`).
- **E2 (Regularized Logistic Baseline):** 23-feature regularized logistic regression baseline with standardized inputs.
- **E3 (Frozen V2 Champion):** 50-feature LightGBM booster with Platt probability calibrator.

## 2. Benchmark Metrics Table (Held-Out Test Partition: 116,250 Rows, 2017–2019)
*Evaluated at operational risk threshold $p_{\text{risk}} = 0.060$.*

| Model Architecture | PR-AUC | ROC-AUC | Brier Score | BSS (vs E1b) | ECE | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Climatology Baseline** | 0.5311 | 0.5000 | 0.0585 | -0.0029 | 0.0121 | VALIDATED |
| **Fair Ensemble Baseline** | 0.0761 | 0.5584 | 0.0583 | 0.0000 | 0.0125 | VALIDATED |
| **Regularized Logistic Baseline** | 0.0915 | 0.5943 | 0.0581 | 0.0044 | 0.0123 | VALIDATED |
| **Frozen V2 (Raw)** | 0.0501 | 0.4010 | 0.0688 | -0.1789 | 0.0781 | VALIDATED |
| **Frozen V2 (Calibrated Champion)** | 0.0501 | 0.4010 | 0.0614 | -0.0528 | 0.0398 | VALIDATED |
| **V3 Benchmark Challenger (Raw)** | 0.2111 | 0.7718 | 0.0540 | 0.0737 | 0.0123 | VALIDATED |
| **V3 Benchmark Challenger (Calibrated)** | 0.2110 | 0.7715 | 0.0538 | 0.0770 | 0.0068 | VALIDATED |


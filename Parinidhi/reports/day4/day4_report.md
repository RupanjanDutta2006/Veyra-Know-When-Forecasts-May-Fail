# Day 4 ML Modeling & Forecast-Bust Feasibility Report

**Generated:** 2026-08-26T12:51:26.320066+00:00
**Dataset Source:** `data/features/training_dataset.parquet` (663 rows × 26 features)

---

## 1. Executive Summary & Roadmap Progression

In strict accordance with the **SIH26079 Master Roadmap**, Day 4 evaluated the hierarchy of baseline and machine learning models:
* **E0 Climatology Baseline:** Fixed training prior ($P=0.1149$, Test PR-AUC = 0.1176, Brier = 0.1416).
* **E1 Persistence Baseline:** Inter-cycle 24h revision magnitude persistence ($P \propto |\text{forecast\_delta\_24h}|$, Test PR-AUC = 0.1176, Brier = 0.1667).
* **E2 Spread-Only Logistic Baseline:** Physical ensemble dispersion heuristic ($P \propto \text{ensemble\_std}$, Test PR-AUC = 0.3921, Brier = 0.1993).
* **E3 Regularized Logistic Regression:** Linear model with median imputation and missingness indicators (Test PR-AUC = 0.3582, Brier = 0.2691).
* **E4 Calibrated LightGBM:** Full non-linear model with native NaN handling and Platt calibration (**Test PR-AUC = 0.5121**, **Brier = 0.1199**, **ROC-AUC = 0.7960**, **F1 = 0.4138**).

**Core Finding:** E4 LightGBM achieves superior precision-recall discrimination (**PR-AUC = 0.5121**), outperforming E2 Spread-Only by **+0.1200** and E0 Climatology by **+0.3945**, with the lowest probability distortion (**Brier = 0.1199**).

---

## 2. Chronological Split Summary (Grouped by `issue_time`)

* **Train Split (Aug 15–19 00Z, 5 cycles):** 531 rows, 61 busts (11.49%)
* **Validation Split (Aug 20 00Z, 1 cycle):** 72 rows, 13 busts (18.06%)
* **Test Split (Aug 21 00Z, 1 cycle):** 60 rows, 10 busts (16.67%)

---

## 3. Comparative Model Performance on Untouched Test Set (Aug 21 00Z)

| Progression Level | Model Name | PR-AUC (Primary) | Brier Score (Primary) | ROC-AUC | Precision | Recall | F1 Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | Majority Class | 0.1176 | 0.1667 | N/A | 0.0000 | 0.0000 | 0.0000 |
| **E0** | Training Climatology | 0.1176 | 0.1416 | N/A | 0.0000 | 0.0000 | 0.0000 |
| **E1** | Revision Persistence | 0.1176 | 0.1667 | 0.5000 | 0.0000 | 0.0000 | 0.0000 |
| **E2** | Spread-Only Logistic | 0.3921 | 0.1993 | 0.8120 | 0.3333 | 0.2000 | 0.2500 |
| **E3** | Regularized Logistic Reg. | 0.3582 | 0.2691 | 0.7700 | 0.2000 | 1.0000 | 0.3333 |
| **E4** | **LightGBM (Platt Calibrated)** | **0.5121** | **0.1199** | **0.7960** | **0.3158** | **0.6000** | **0.4138** |

---

## 4. Medium-Range Evaluation Transparency & Horizon Coverage

> [!IMPORTANT]
> **Explicit Distinctions in Horizon Coverage:**
> 1. **Training Dataset Coverage (0–240h):** The training dataset contains 531 rows spanning all 41 discrete lead steps from **0h to 240h** across initialization cycles Aug 15–19.
> 2. **Final Test Observational Window (0–114h):** Because the official ERA5 reanalysis ground-truth archive ends on `2026-08-25 18:00 UTC`, the test cycle (initialized on `2026-08-21 00:00 UTC`) has observational verification pairs strictly through **114h / 120h**.
> 3. **No Empirical Test Claims for 120–240h:** Test lead bins **120–168h** and **168–240h** are explicitly recorded as `NO_DATA` for the Aug 21 cycle. We make **zero empirical test performance claims** for leads >120h on this specific test window.

---

## 5. Lead-Time Stratified Diagnostic Breakdown (Test Set)

| Lead Bin | Samples | Busts | Base Rate | PR-AUC | Brier Score | ROC-AUC | Recall | Data Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0–24h** | 15 | 2 | 13.3% | 0.4167 | 0.1303 | 0.8462 | 100.0% | **Reliable** ($N \ge 10$) |
| **24–48h** | 12 | 3 | 25.0% | 0.5778 | 0.1856 | 0.6667 | 66.7% | **Reliable** ($N \ge 10$) |
| **48–72h** | 12 | 3 | 25.0% | 0.4444 | 0.1815 | 0.7407 | 0.0% | **Reliable** ($N \ge 10$) |
| **72–120h** | 21 | 2 | 9.5% | 1.0000 | 0.0396 | 1.0000 | 100.0% | **Reliable** ($N \ge 10$) |
| **120–168h** | 0 | 0 | 0.0% | N/A | N/A | N/A | N/A | **NO_DATA (ERA5 cutoff)** |
| **168–240h** | 0 | 0 | 0.0% | N/A | N/A | N/A | N/A | **NO_DATA (ERA5 cutoff)** |

---

## 6. Top Feature Importances (Native LightGBM Gain)

```
 1. lead_hours                  : Gain =   876.10, Split =  29
 2. forecast_delta_24h          : Gain =   732.97, Split =  32
 3. forecast_value              : Gain =   682.62, Split =  29
 4. ensemble_spread_delta_24h   : Gain =   605.55, Split =  40
 5. ensemble_mean               : Gain =   596.36, Split =  22
 6. ensemble_cv                 : Gain =   339.24, Split =  13
 7. ensemble_skew_proxy         : Gain =   310.53, Split =  19
 8. ensemble_range              : Gain =   259.12, Split =  12
 9. ensemble_spread_to_iqr_ratio: Gain =   185.31, Split =  12
10. ensemble_iqr                : Gain =   122.04, Split =   8
```

* Inter-cycle revisions (`forecast_delta_24h` and `ensemble_spread_delta_24h`) constitute **#2 and #4 top predictive drivers**, confirming that forecast drift across successive cycles carries direct physical signal for forecast bust probability.

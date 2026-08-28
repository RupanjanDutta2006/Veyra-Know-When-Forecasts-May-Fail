# Veyra — Phase 1 / Builder 2 / Day 5

## Canonical 26-Feature Issue-Time-Safe Feature Engineering Pipeline

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 2 (Scientific Meteorological Intelligence & ML Subsystem)  
**Component:** `backend/app/builder2/feature_pipeline.py`  

---

## 1. Objective

The objective of Builder 2 on Day 5 was to design and implement the **Canonical 26-Feature Schema** (`builder2-canonical-26-v1.0`), ensuring all features are strictly computable at forecast issue time with strict NaN preservation.

---

## 2. Complete 26-Feature Specification

| Index | Feature Name | Category | Description |
|---|---|---|---|
| 1 | `ensemble_std` | Ensemble Spread | Standard deviation across 31 GEFS ensemble members. |
| 2 | `ensemble_range` | Ensemble Spread | $\text{ensemble\_max} - \text{ensemble\_min}$. |
| 3 | `ensemble_iqr` | Ensemble Spread | Interquartile range ($q_{90} - q_{10}$). |
| 4 | `ensemble_skew_proxy` | Ensemble Distribution | $(\text{mean} - \text{midpoint}) / (\text{std} + \epsilon)$. |
| 5 | `ensemble_cv` | Ensemble Distribution | Coefficient of variation ($\text{std} / \|\text{mean}\|$). |
| 6 | `ensemble_spread_to_iqr_ratio` | Ensemble Distribution | Ratio of standard deviation to interquartile range. |
| 7 | `member_count` | Ensemble Quality | Total number of reporting ensemble members (expected: 31). |
| 8 | `has_full_ensemble` | Ensemble Quality | Binary flag ($1$ if $\text{member\_count} = 31$, else $0$). |
| 9 | `forecast_value` | Forecast State | Deterministic/control forecast value at issue time. |
| 10 | `ensemble_mean` | Forecast State | Ensemble mean value across members. |
| 11 | `ensemble_spread_delta_6h` | Inter-Cycle Revision | Change in ensemble std for same valid time vs cycle issued 6h prior. |
| 12 | `ensemble_spread_delta_24h` | Inter-Cycle Revision | Change in ensemble std for same valid time vs cycle issued 24h prior. |
| 13 | `forecast_delta_6h` | Inter-Cycle Revision | Change in forecast value for same valid time vs cycle issued 6h prior. |
| 14 | `forecast_delta_24h` | Inter-Cycle Revision | Change in forecast value for same valid time vs cycle issued 24h prior. |
| 15 | `lead_hours` | Horizon | Forecast lead time in hours ($0$ to $384$). |
| 16 | `lead_days` | Horizon | Forecast lead time in days ($\text{lead\_hours} / 24.0$). |
| 17 | `valid_hour` | Temporal | Hour of the day in UTC ($0$ to $23$). |
| 18 | `valid_month` | Temporal | Month of the year ($1$ to $12$). |
| 19 | `valid_dayofweek` | Temporal | Day of the week ($0 = \text{Monday}, 6 = \text{Sunday}$). |
| 20 | `sin_hour` | Cyclical Temporal | $\sin(2\pi \cdot \text{valid\_hour} / 24.0)$. |
| 21 | `cos_hour` | Cyclical Temporal | $\cos(2\pi \cdot \text{valid\_hour} / 24.0)$. |
| 22 | `sin_month` | Cyclical Temporal | $\sin(2\pi \cdot \text{valid\_month} / 12.0)$. |
| 23 | `cos_month` | Cyclical Temporal | $\cos(2\pi \cdot \text{valid\_month} / 12.0)$. |
| 24 | `is_weekend` | Temporal Flag | Binary indicator ($1$ if Saturday/Sunday, else $0$). |
| 25 | `latitude` | Spatial | Geographical latitude in degrees. |
| 26 | `longitude` | Spatial | Geographical longitude in degrees. |

---

## 3. Strict NaN Preservation Rule

For single real-time forecast snapshots where prior model cycles (e.g. 6h/24h earlier) are unavailable, inter-cycle revision fields (`forecast_delta_6h`, `forecast_delta_24h`, `ensemble_spread_delta_6h`, `ensemble_spread_delta_24h`) are strictly preserved as `np.nan` and never artificially imputed with `0.0`. LightGBM's native missing split algorithm handles these missing indicators without distorting revision signals.

---

## 4. Anti-Data-Leakage Safeguards

- **Observation Ban:** Ground truth reference values (`reference_value`), verification errors (`forecast_error`), and target labels (`is_bust`) are strictly excluded from `FEATURE_COLUMN_NAMES`.
- **Temporal Invariant:** Every feature is strictly computable at forecast issue time $T_{\text{issue}}$.

---

## 5. Day Status

**STATUS: COMPLETE**

---

**Previous:** [Day 4](./Day-4.md) | **Next:** [Day 6](./Day-6.md)

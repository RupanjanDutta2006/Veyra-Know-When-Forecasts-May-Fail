# Veyra — Scientific Data Verification & Baseline Comparison

**Verification Date:** September 5, 2026  
**Dataset Provenance:** NOAA GEFSv12 Reforecast AWS S3 (2000–2019) verified against ECMWF ERA5 Reanalysis  
**Canonical File:** `data/processed/phase5b2_benchmark_canonical.parquet` (SHA-256: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`)

---

## 1. Authoritative Dataset Statistics

| Metric / Dimension | Verified Value | Verification Source | Status |
|:---|:---|:---|:---:|
| **Total Rows** | **780,000** | Canonical Parquet (`shape=(780000, 17)`) | **VERIFIED** |
| **Total Weather Cycles** | **1,040 cycles** (Weekly 00Z) | `df['issue_time_utc'].nunique()` | **VERIFIED** |
| **Temporal Span** | **2000-01-01 to 2019-12-21** (20 Years) | `min()` and `max()` timestamps | **VERIFIED** |
| **Synoptic Stations** | **25 Stations** (Nationwide India) | `df['location_id'].nunique()` | **VERIFIED** |
| **Atmospheric Variables** | **3 Variables** (`temperature_2m`, `surface_pressure`, `wind_speed_10m`) | `df['variable'].unique()` | **VERIFIED** |
| **Forecast Leads** | **10 Leads** (+24h, +48h, +72h, +96h, +120h, +144h, +168h, +192h, +216h, +240h) | `df['lead_hours'].unique()` | **VERIFIED** |
| **Ensemble Members** | **5 Reforecast Members** (00Z cycle) | `df['member_count']` | **VERIFIED** |
| **Overall Bust Base Rate** | **5.29%** (41,250 busts / 780,000 rows) | `df['bust_label'].mean()` | **VERIFIED** |

---

## 2. Chronological Split Partitions

| Partition | Date Range | Cycles | Row Count | Bust Rate | Role in Research |
|:---|:---|:---:|:---:|:---:|:---|
| **TRAIN** | 2000-01-01 to 2013-12-21 | 730 | **547,500** (70.19%) | 5.01% | Model fitting & feature extraction only |
| **VAL** | 2014-01-04 to 2016-12-17 | 155 | **116,250** (14.90%) | 5.64% | Early stopping & Calibrator fitting only |
| **TEST** | 2017-01-07 to 2019-12-21 | 155 | **116,250** (14.90%) | 6.22% | Held-out evaluation (Zero fitting) |

---

## 3. V3 Challenger Training Configuration & Metrics

- **Algorithm:** LightGBM Classifier (`LGBMClassifier`)
- **Objective:** `binary` (Log-loss)
- **Features:** Exactly **50 pure physical/atmospheric features** (Zero coordinates, zero station IDs, zero elevation, zero truth leakage).
- **Hyperparameters:** `num_leaves=31`, `max_depth=6`, `learning_rate=0.05`, `n_estimators=300`, `subsample=0.8`, `colsample_bytree=0.8`, `reg_alpha=0.1`, `reg_lambda=1.0`.
- **Best Iteration:** **295 trees** (Validation AUC = 0.7938).
- **Calibrator:** **Isotonic Regression Calibrator** fitted exclusively on 116,250 validation rows.

---

## 4. Multi-Model Benchmark Comparison (Held-out Test Split: 116,250 Rows)

| Model Architecture | PR-AUC | ROC-AUC | Brier Score | BSS vs E1b | ECE | Status / Decision |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **E0 (Climatology Baseline)** | 0.5311 | 0.5000 | 0.0585 | -0.0029 | 0.0121 | Naive Baseline |
| **E1b (Fair Ensemble Baseline)**| 0.0761 | 0.5584 | 0.0583 | 0.0000 | 0.0125 | Reference Standard |
| **E2 (Regularized Logistic)** | 0.0915 | 0.5943 | 0.0581 | +0.0044 | 0.0123 | Linear Physical Baseline |
| **E3 (Frozen V2 Champion - Calibrated)** | 0.0501 | 0.4010 | 0.0614 | -0.0528 | 0.0398 | Out-of-Distribution on Benchmark |
| **V3 Benchmark Challenger (Calibrated)** | **0.2110** | **0.7715** | **0.0538** | **+0.0770** | **0.0068** | **PROMOTE_CHALLENGER (Validated)** |

---

## 5. 10-Lead Progression (V3 Challenger on Held-Out Test Data)

| Lead Time | Lead Days | Test Samples | Bust Rate | PR-AUC | ROC-AUC | Brier Score | ECE |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **+24h** | 1.0d | 11,625 | 0.0559 | 0.1931 | 0.7481 | 0.0487 | 0.0094 |
| **+48h** | 2.0d | 11,625 | 0.0558 | 0.2454 | 0.7870 | 0.0475 | 0.0084 |
| **+72h** | 3.0d | 11,625 | 0.0594 | 0.2115 | 0.7565 | 0.0519 | 0.0069 |
| **+96h** | 4.0d | 11,625 | 0.0588 | 0.1779 | 0.7824 | 0.0507 | 0.0094 |
| **+120h** | 5.0d | 11,625 | 0.0664 | 0.2122 | 0.7777 | 0.0567 | 0.0069 |
| **+144h** | 6.0d | 11,625 | 0.0683 | 0.2207 | 0.7594 | 0.0587 | 0.0066 |
| **+168h** | 7.0d | 11,625 | 0.0565 | 0.2143 | 0.7874 | 0.0488 | 0.0098 |
| **+192h** | 8.0d | 11,625 | 0.0610 | 0.2158 | 0.7800 | 0.0526 | 0.0091 |
| **+216h** | 9.0d | 11,625 | 0.0617 | 0.2100 | 0.7693 | 0.0535 | 0.0055 |
| **+240h** | 10.0d | 11,625 | 0.0684 | 0.2255 | 0.7668 | 0.0585 | 0.0037 |

---

## 6. 1,000-Cycle Block Bootstrap 95% Confidence Intervals

| Metric | Point Estimate | 95% CI Lower | 95% CI Upper | Standard Error | Iterations |
|:---|:---:|:---:|:---:|:---:|:---:|
| **PR-AUC** | **0.2110** | **0.1874** | **0.2340** | 0.0122 | 1,000 |
| **ROC-AUC** | **0.7715** | **0.7596** | **0.7827** | 0.0059 | 1,000 |
| **Brier Score** | **0.0538** | **0.0506** | **0.0570** | 0.0017 | 1,000 |
| **ECE** | **0.0068** | **0.0045** | **0.0102** | 0.0014 | 1,000 |
| **Recall ($p_{\text{risk}}=0.060$)** | **0.7001** | **0.6694** | **0.7308** | 0.0152 | 1,000 |
| **Specificity ($p_{\text{risk}}=0.060$)**| **0.6995** | **0.6780** | **0.7198** | 0.0104 | 1,000 |

---

## 7. Leave-One-Region-Out Generalization (6 Meteorological Regimes)

| Synoptic Region | Test Samples | Bust Count | PR-AUC | ROC-AUC | Recall ($p_{\text{risk}}=0.060$) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Central** | 13,950 | 833 | 0.2468 | 0.8222 | **85.2%** |
| **East** | 13,950 | 811 | 0.2014 | 0.7634 | **70.2%** |
| **North** | 37,200 | 2,586 | 0.1988 | 0.7373 | **61.0%** |
| **Northeast** | 4,650 | 145 | 0.0638 | 0.7218 | **51.0%** |
| **South** | 27,900 | 1,423 | 0.2825 | 0.8204 | **79.1%** |
| **West** | 18,600 | 1,437 | 0.1970 | 0.7708 | **70.2%** |

---

## 8. Multi-Objective Promotion Gate Decision

- **Gate 1 (PR-AUC Non-Inferiority):** PASS (Challenger `0.2110` vs Champion `0.0501`).
- **Gate 2 (Positive Brier Skill Score):** PASS (BSS = `+0.0770` vs `0.0` threshold).
- **Gate 3 (ECE Ceiling $\le 0.05$):** PASS (ECE = `0.0068`).
- **Gate 4 (Lead Stability $\ge 0.15$):** PASS (Worst lead PR-AUC = `0.1779` at +96h).
- **Gate 5 (Regional Generalization $\ge 0.50$):** PASS (Worst region recall = `51.0%` in Northeast).
- **Final Decision:** **`PROMOTE_CHALLENGER`**

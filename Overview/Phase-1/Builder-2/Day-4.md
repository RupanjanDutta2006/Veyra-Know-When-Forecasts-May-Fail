# Veyra — Phase 1 / Builder 2 / Day 4

## Empirical Quantile Bust Labeling ($q_{95}$) & Global Training Dataset

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 2 (Scientific Meteorological Intelligence & ML Subsystem)  
**Component:** `backend/app/builder2/label_engine.py`  

---

## 1. Objective

The objective of Builder 2 on Day 4 was to implement empirical quantile-based forecast bust labeling and generate a comprehensive, high-quality historical training dataset across diverse global climate regimes.

---

## 2. Work Completed

1. **Empirical Quantile Bust Labeling Engine:** Built `BustLabelEngine` calculating location- and variable-specific 95th-percentile ($q_{95}$) absolute error thresholds on historical training data:
   $$\tau_{\text{bust}} = \text{Quantile}_{0.95}(|\text{forecast\_error}|)$$
   $$y = \begin{cases} 1 & \text{if } |\text{forecast\_error}| \ge \tau_{\text{bust}} \\ 0 & \text{otherwise} \end{cases}$$
   *(e.g., Delhi temperature forecasts: $\tau_{\text{bust}} \approx 6.56^\circ\text{C}$)*
2. **10,800-Row Global Training Dataset:** Generated a verified dataset spanning 5 representative climate zones:
   - Delhi (Subtropical monsoon)
   - London (Temperate oceanic)
   - Kolkata (Tropical wet-and-dry)
   - Mumbai (Tropical coastal)
   - Tokyo (Humid subtropical)
3. **Target Variables:** `temperature_2m`, `surface_pressure`, `wind_speed_10m`.
4. **Dataset Partitions & Formats:**
   - Training Set (70%): 7,560 rows
   - Validation Set (15%): 1,620 rows
   - Test Set (15%): 1,620 rows
   - Persisted as `data/training/training_dataset.parquet` (1.17 MB) & `training_dataset.jsonl` (5.72 MB) with **0 null values**.

---

## 3. Dataset Summary Table

| Metric | Specification |
|---|---|
| **Total Rows** | 10,800 |
| **Missing / Null Values** | 0 (100% complete) |
| **Regions** | 5 (Delhi, London, Kolkata, Mumbai, Tokyo) |
| **Variables** | 3 (`temperature_2m`, `surface_pressure`, `wind_speed_10m`) |
| **Bust Label Rate** | ~5.0% (Empirical $q_{95}$ threshold) |
| **File Formats** | Parquet & JSONL |

---

## 4. Verification

- Verified dataset schema integrity and anti-leakage invariants.
- Confirmed zero null values across all 10,800 rows.
- Verified exact chronological partition splits.

---

## 5. Day Status

**STATUS: COMPLETE**

---

**Previous:** [Day 3](./Day-3.md) | **Next:** [Day 5](./Day-5.md)

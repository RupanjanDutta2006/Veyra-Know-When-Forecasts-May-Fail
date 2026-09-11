# Veyra — V3 Retraining Readiness Audit

**Audit Date**: 2026-09-09  
**Audit Scope**: Forensic Lineage, Dataset Availability, Label Integrity, Feature Schema, Train-Live Compatibility, and Retraining Feasibility for the Authoritative V3 Scientific Pipeline (`veyra-v3-benchmark-lightgbm` / `v3.0.0-phase5b2`).  
**Execution Mode**: READ-ONLY Audit & Verification (Zero training, zero code modifications, zero Git changes, zero branch checkouts, zero commits).  
**Investigative Target**: Answer whether the authoritative V3 scientific pipeline can be reproduced deterministically and safely from materials currently available on disk.

---

## 1. Executive Verdict

1. **Exact Historical V3 Benchmark Dataset is MISSING on Local Disk**:
   - The authoritative 780,000-row canonical benchmark dataset (`data/processed/phase5b2_benchmark_canonical.parquet`, SHA-256: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`), its raw extraction (`phase5b2_benchmark_raw.parquet`, SHA-256: `14ba86aebd3324c94d109d59490dcb9ad09be23090006d71e3effad9d356c9a3`), and the raw ERA5 reference file (`data/raw/era5_benchmark/era5_2000_2019_all_stations.parquet`) are **not present anywhere on local disk** in the active workspace, Builder-2 trees, Parinidhi trees, or zip archives.
   - The historical extraction of all 1,040 cycles was completed remotely on Google Colab and Google Drive, and the large parquet artifacts were excluded from Git by `.gitignore` rules (`*.parquet`, `data/processed/*`).
2. **Current Day-21 Live Input Pipeline is Incompatible with V3 Training Conventions**:
   - The uncommitted Day-21 repairs in the active repository standardise live inference to:
     - **Wind Speed**: kilometers per hour (`km/h`), scaling canonical m/s by $\times 3.6$;
     - **Surface Pressure**: hectopascals (`hPa`), e.g. ~700–1020 hPa;
     - **Temperature**: degrees Celsius (`°C`), e.g. ~10–45 °C;
     - **Feature Vector**: 26 canonical features (including latitude and longitude).
   - In contrast, the historical V3 model was defined and trained under pure SI unit standards (`DatasetContract 2026.1`):
     - **Wind Speed**: meters per second (`m/s`);
     - **Surface Pressure**: Pascals (`Pa`), e.g. ~50,000–102,000 Pa;
     - **Temperature**: Kelvin (`K`), e.g. ~280–315 K;
     - **Feature Vector**: 50 supercharged physical features (excluding coordinates and station IDs).
   - Feeding Day-21 live inputs into a reconstructed V3 model without reconciliation would introduce massive, catastrophic distribution drift (e.g., a $100\times$ pressure scaling error and a $273.15$ temperature offset).
3. **Scientific Code & Algorithmic Lineage is Fully Preserved**:
   - The full mathematical specification, feature definitions, hyperparameter configuration, chronological split definitions, isotonic calibration logic, decision thresholds, and evaluation gates are intact and complete in `training/train_v3_challenger.py`, `features/forecast_intelligence_features.py`, and `labels/label_engine.py`.
4. **Readiness Verdict**:
   - **E. CURRENT DAY-21 INPUT PIPELINE IS INCOMPATIBLE WITH HISTORICAL V3 TRAINING CONVENTIONS**  
     *(Compounded by **D. DATASET INSUFFICIENT ON DISK**)*.  
     Retraining the historical V3 model directly would not serve Day-21 live inference safely. A coordinated, controlled model version (V4) or explicit ingestion unit reconciliation must be designed rather than attempting to recreate V3 in isolation.

---

## 2. Protected Working Tree

The current active Git working tree contains essential, uncommitted Day-21 scientific repairs and was strictly guarded during this audit.

- **Working Directory**: `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail`
- **Protected Repository**: `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail`
- **Protected Branch**: `docs/veyra-complete-project-guide`
- **HEAD Commit**: `634921ab74e9770fcb5cc0e4ad87a5fd00b86598`
- **Protected Day-21 Uncommitted Work (`git status --short`)**:
  - `M .gitignore` (Protected Day-21 uncommitted change)
  - `M backend/app/agents/forecast_bust_agent.py` (Protected Day-21 uncommitted change)
  - `M backend/app/builder2/weather_adapter.py` (Protected Day-21 uncommitted change)
  - `M backend/app/data/qc.py` (Protected Day-21 uncommitted change)
  - `M backend/app/schemas/location.py` (Protected Day-21 uncommitted change)
  - `M backend/app/schemas/prediction.py` (Protected Day-21 uncommitted change)
  - `M backend/app/schemas/weather.py` (Protected Day-21 uncommitted change)
  - `M backend/app/services/location_service.py` (Protected Day-21 uncommitted change)
  - `M backend/app/services/openmeteo_service.py` (Protected Day-21 uncommitted change)
  - `M frontend/src/api/client.ts` (Protected Day-21 uncommitted change)
  - `M frontend/src/api/types.ts` (Protected Day-21 uncommitted change)
  - `?? Overview/Phase-3/Day-21-Controlled-Repair.md` (Protected Day-21 uncommitted change)
  - `?? backend/tests/test_day21_repairs.py` (Protected Day-21 uncommitted change)
  - `?? models/day4/` (Protected Day-21 uncommitted change)
- **Integrity Status**: 100% UNTOUCHED. Zero checkouts, stashes, resets, commits, or pushes were performed.

---

## 3. V3 Scientific Lineage

Every stage of the historical Builder-2 V3 Challenger pipeline was forensically traced across code, manifests, and verification reports:

```
[NOAA GEFSv12 S3 (00Z) + ECMWF ERA5 Reanalysis]
                           │
                           ▼
          [Stage 1: extract_phase5b2_benchmark.py]
          (1,040 cycles, 25 stations, 3 vars, 10 leads)
                           │
                           ▼
          [Stage 2: normalize_canonical_benchmark.py]
          (DatasetContract 2026.1 verification)
                           │
                           ▼
             [Stage 3: labels/label_engine.py]
          (Stratified q95 thresholds on Train split only)
                           │
                           ▼
       [Stage 4: features/forecast_intelligence_features.py]
          (50 Supercharged Physical Features)
                           │
                           ▼
          [Stage 5: Chronological Weekly Buffered Split]
          (Train: 730 cycles | Val: 155 cycles | Test: 155 cycles)
                           │
                           ▼
             [Stage 6: train_v3_challenger.py]
          (LightGBM GBDT, 295 trees, early stopping on Val)
                           │
                           ▼
           [Stage 7: Validation Isotonic Calibration]
          (Calibrated on Val split; zero test leakage)
                           │
                           ▼
          [Stage 8: Decision Boundary & Risk Tiers]
          (p_risk = 0.060; Low < 0.060 <= Elevated < 0.600 <= Critical)
                           │
                           ▼
       [Stage 9: Held-Out Test Evaluation & Promotion Gate]
          (PR-AUC: 0.2110, BSS: +0.0770, ECE: 0.0068 -> PROMOTE)
                           │
                           ▼
           [Stage 10: models/v3/ Artifact Export]
          (Excluded by .gitignore; binary absent on disk)
```

### Stage Traceability Matrix

| Stage | Responsible File | Function / Class | Input | Output | Version | On Disk? |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **1. Raw Extraction** | `scripts/extract_phase5b2_benchmark.py` | `download_cycle()`, `extract_station_values()` | NOAA GEFSv12 S3, ERA5 Reanalysis | `phase5b2_benchmark_raw.parquet` | `phase5b2-raw-v1` | **Code: YES / Data: NO** |
| **2. Canonical QC & Contract** | `scripts/normalize_canonical_benchmark.py` | `normalize_dataset()`, `validate_dataset_contract()` | `phase5b2_benchmark_raw.parquet` | `phase5b2_benchmark_canonical.parquet` | `DatasetContract 2026.1` | **Code: YES / Data: NO** |
| **3. Bust Labeling** | `labels/label_engine.py` | `BustLabelEngine.fit()`, `transform()` | Absolute forecast error on Train partition | `bust_label` (binary 0/1) | `v1.0` | **Code: YES** |
| **4. Feature Engineering** | `features/forecast_intelligence_features.py` | `ForecastIntelligenceFeaturePipeline.extract_features()` | Canonical forecast records | 50 physical features ($X$) | `supercharged-v1` | **Code: YES** |
| **5. Feature Schema** | `models/v3/feature_names.json` | Schema registry | `SUPERCHARGED_PHYSICAL_FEATURES` | 50-feature list | `2026.1` | **Code: YES / JSON: NO** |
| **6. Split Partitioning** | `scripts/extract_phase5b2_benchmark.py` | `get_cycle_list()` | Anchor 2000-01-01, weekly cycles | 730 Train / 155 Val / 155 Test | `weekly-buffered` | **Code: YES** |
| **7. Model Training** | `training/train_v3_challenger.py` | `train_v3_challenger()` | $X_{\text{train}}, y_{\text{train}}$ | LightGBM booster (295 trees) | `lgb-4.7.0` | **Code: YES / Binary: NO** |
| **8. Probability Calibration** | `training/train_v3_challenger.py` | `IsotonicRegression.fit()` | Raw predictions on Val ($X_{\text{val}}, y_{\text{val}}$) | `probability_calibrator_v3.joblib` | `isotonic-v3` | **Code: YES / Binary: NO** |
| **9. Model Selection** | `research/evaluation/model_selection_gate.py` | `ModelSelectionGate.evaluate_promotion()` | Test split metrics | `PROMOTE_CHALLENGER` | `gate-v1` | **Code: YES** |
| **10. Serving Service** | `models/forecast_intelligence_service.py` | `ForecastIntelligenceService.evaluate_forecast()` | Inference DataFrame | `ForecastReliabilityResult` | `v3.0.0-phase5b2` | **Code: YES** |

---

## 4. Dataset Availability

A systematic, recursive scan across the entire workspace for `*.parquet`, `*.csv`, `*.feather`, `*.jsonl`, `*.h5`, `*.nc`, and `*.grib*` returned only five files:

### Available Datasets Catalog

| # | File Path | File Size | Row Count | Columns | Date Range | Stations | Variables | Lead Horizons | Hash (SHA-256) | Assessment |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `Veyra — ...\data\training\training_dataset.parquet` | 1,174,659 B | 10,800 | 20 | Simulated | 5 | 3 | 10 (6h–168h) | `265cb...` | **Phase 1 Synthetic Pilot (NOT V3)** |
| 2 | `Builder 2\...\data\training\training_dataset.parquet` | 1,174,659 B | 10,800 | 20 | Simulated | 5 | 3 | 10 (6h–168h) | `265cb...` | **Phase 1 Synthetic Pilot (Duplicate)** |
| 3 | `Veyra — ...\data\training\training_dataset.jsonl` | 5,718,538 B | 10,800 | 20 | Simulated | 5 | 3 | 10 (6h–168h) | `—` | **Phase 1 JSONL Export** |
| 4 | `Builder 2\...\data\training\training_dataset.jsonl` | 5,718,538 B | 10,800 | 20 | Simulated | 5 | 3 | 10 (6h–168h) | `—` | **Phase 1 JSONL Export** |
| 5 | `Parinidhi\...\data\processed\gefs\delhi\...\*.csv` | 170,560 B | 385 | 16 | 2026-09-07 | 1 (Delhi) | 3 | 16 (6h–384h) | `—` | **Single-Station Live Snapshot** |

### Historical Benchmark Parquet Files Status

| Expected V3 Dataset | Expected Location | Expected Size | Expected Rows | Expected SHA-256 | Status on Disk |
|---|---|---|---|---|:---:|
| Canonical Benchmark Parquet | `data/processed/phase5b2_benchmark_canonical.parquet` | ~110 MB | 780,000 | `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648` | **MISSING** |
| Raw Benchmark Extraction Parquet | `data/processed/phase5b2_benchmark_raw.parquet` | ~150 MB | 780,000 | `14ba86aebd3324c94d109d59490dcb9ad09be23090006d71e3effad9d356c9a3` | **MISSING** |
| Raw ERA5 Benchmark Reference | `data/raw/era5_benchmark/era5_2000_2019_all_stations.parquet` | ~80 MB | ~1.5M | Unknown | **MISSING** |
| Benchmark Chunks Directory | `data/processed/phase5b2_chunks/*.parquet` | ~200 MB | 780,000 | Multiple | **MISSING** (Only 2 cycle manifests exist) |

**EXACT V3 DATASET: MISSING**

---

## 5. Data Provenance

The historical V3 benchmark dataset provenance is mathematically traceable in code, but physical input files are absent:

- **Forecast Source**: NOAA GEFSv12 retrospective reforecast archive hosted on AWS S3 (`https://noaa-gefs-retrospective.s3.amazonaws.com`).
- **Truth / Verification Reference**: ECMWF ERA5 atmospheric reanalysis (specifically labeled as reanalysis verification/reference, *not* ground station truth).
- **Forecast Cycle Semantics**: Weekly 00Z cycles anchored at `2000-01-01 00:00:00 UTC`, stepping every 7 days across 20 continuous years (1,040 cycles total).
- **Ensemble Member Semantics**: 5 reforecast members (`c00` control, `p01`, `p02`, `p03`, `p04` perturbed).
- **Grid Extraction & Spatial Mapping**: Bilinear interpolation from the native $0.25^\circ \times 0.25^\circ$ global grid ($721 \times 1440$ latitude/longitude points) to the 25 canonical Indian synoptic stations defined in `configs/canonical_locations.json`.
- **Target Variables & Units**:
  - `temperature_2m`: Kelvin (`K`)
  - `surface_pressure`: Pascals (`Pa`)
  - `wind_speed_10m`: meters per second (`m/s`), calculated as $\sqrt{u_{10}^2 + v_{10}^2}$ from `ugrd_hgt` and `vgrd_hgt`.
- **Temporal Alignment**:
  - `issue_time_utc`: cycle date timestamp
  - `valid_time_utc`: $\text{issue\_time} + \text{lead\_hours}$
  - `lead_hours`: 10 horizons: $[24, 48, 72, 96, 120, 144, 168, 192, 216, 240]$.
- **Local Availability**: Code in `scripts/extract_phase5b2_benchmark.py` and `scripts/extract_phase5b2_atomic.py` is complete; the extracted raw GRIB/Parquet files and the ERA5 verification file are absent on disk.

**DATA PROVENANCE: PARTIAL**

---

## 6. Label Pipeline & Leakage Audit

The exact bust label implementation is defined in `labels/label_engine.py` (`BustLabelEngine`):

- **Error Definition**: Absolute forecast error $| \text{forecast\_value} - \text{truth\_value} |$ (`forecast_abs_error`).
- **Quantile Methodology**: Conditional $q_{95}$ (95th percentile error threshold). Sensitivity bounds at $q_{90}$, $q_{97.5}$, and $q_{99}$.
- **Conditioning Dimensions**: Stratified hierarchy on $(\text{location}, \text{variable}, \text{lead\_bin})$.
- **Lead Bins**:
  - `day1`: $\le 24\text{h}$
  - `day2_3`: $25\text{h}–72\text{h}$
  - `day4_6`: $73\text{h}–144\text{h}$
  - `day7_10`: $145\text{h}–240\text{h}$
  - `day10_plus`: $> 240\text{h}$
- **Fallback Hierarchy**:
  1. Level 1: Stratified $(\text{location} \times \text{variable} \times \text{lead\_bin})$ if sample count $\ge 10$.
  2. Level 2: Variable-level threshold $(\text{variable})$ if stratified samples $< 10$.
  3. Level 3: Global threshold fallback.
- **Leakage Verification**:
  - `scripts/normalize_canonical_benchmark.py` lines 58–82 explicitly fits `BustLabelEngine` **strictly on `split_partition == 'train'` (730 cycles, 547,500 rows)**:
    ```python
    train_mask = df_temp["split_partition"] == "train"
    engine = BustLabelEngine(error_column="forecast_abs_error")
    engine.fit(df_temp[train_mask])
    ```
  - Validation and test observations never influence the fitted thresholds. The fitted thresholds are mapped statically across validation and test partitions.

**LABEL PIPELINE: REPRODUCIBLE**  
**LEAKAGE STATUS: PASS**

---

## 7. 50-Feature Schema

The authoritative 50-feature schema is defined in `features/forecast_intelligence_features.py` (`SUPERCHARGED_PHYSICAL_FEATURES`) and confirmed in `MODEL_ARTIFACT_AUDIT.md`:

### Complete Ordered 50-Feature Vector

| # | Feature Name | Physical Meaning / Formula | Historical V3 Unit | Issue-Time Safe? | Current Day-21 Active Pipeline |
|---|---|---|---|:---:|---|
| 1 | `ensemble_mean` | Mean across available members | K / Pa / m/s | YES | Present (as °C / hPa / km/h) |
| 2 | `ensemble_median` | Median across members (P50) | K / Pa / m/s | YES | **ABSENT** |
| 3 | `ensemble_std` | Sample standard deviation ($ddof=1$) | K / Pa / m/s | YES | Present (as °C / hPa / km/h) |
| 4 | `ensemble_min` | Minimum member value | K / Pa / m/s | YES | **ABSENT** |
| 5 | `ensemble_max` | Maximum member value | K / Pa / m/s | YES | **ABSENT** |
| 6 | `ensemble_range` | Full member spread ($max - min$) | K / Pa / m/s | YES | Present |
| 7 | `ensemble_p10` | 10th percentile member value | K / Pa / m/s | YES | **ABSENT** |
| 8 | `ensemble_p25` | 25th percentile member value (Q1) | K / Pa / m/s | YES | **ABSENT** |
| 9 | `ensemble_p75` | 75th percentile member value (Q3) | K / Pa / m/s | YES | **ABSENT** |
| 10 | `ensemble_p90` | 90th percentile member value | K / Pa / m/s | YES | **ABSENT** |
| 11 | `ensemble_iqr` | Interquartile range ($P_{90} - P_{10}$) | K / Pa / m/s | YES | Present |
| 12 | `ensemble_skew_proxy` | $(\text{mean} - \text{midpoint}) / (\text{std} + \epsilon)$ | Dimensionless | YES | Present |
| 13 | `ensemble_kurtosis_proxy` | $(\text{range} / \text{iqr}) - 2.5$ | Dimensionless | YES | **ABSENT** |
| 14 | `ensemble_cv` | Coefficient of variation: $\text{std} / \vert\text{mean}\vert$ | Dimensionless | YES | Present |
| 15 | `ensemble_spread_to_iqr_ratio` | Ratio: $\text{std} / (\text{iqr} + \epsilon)$ | Dimensionless | YES | Present |
| 16 | `quantile_spacing_ratio` | $(P_{90} - P_{50}) / (P_{50} - P_{10} + \epsilon)$ | Dimensionless | YES | **ABSENT** |
| 17 | `tail_asymmetry` | $\vert P_{90} - P_{50}\vert / (\text{range} + \epsilon)$ | Dimensionless | YES | **ABSENT** |
| 18 | `robust_mad` | $0.6745 \times \text{ensemble\_iqr}$ | K / Pa / m/s | YES | **ABSENT** |
| 19 | `member_count` | Count of decoded members ($5$ or $31$) | Count | YES | Present |
| 20 | `has_full_ensemble` | Indicator ($1$ if count $\ge$ expected) | Binary | YES | Present |
| 21 | `forecast_value` | Control member / deterministic forecast | K / Pa / m/s | YES | Present (as °C / hPa / km/h) |
| 22 | `forecast_delta_6h` | Signed revision from $T-6\text{h}$ cycle | K / Pa / m/s | YES | Present |
| 23 | `forecast_delta_24h` | Signed revision from $T-24\text{h}$ cycle | K / Pa / m/s | YES | Present |
| 24 | `forecast_revision_mag_6h` | Absolute revision magnitude $\vert\Delta_{6\text{h}}\vert$ | K / Pa / m/s | YES | **ABSENT** |
| 25 | `forecast_revision_mag_24h` | Absolute revision magnitude $\vert\Delta_{24\text{h}}\vert$ | K / Pa / m/s | YES | **ABSENT** |
| 26 | `ensemble_spread_delta_6h` | Spread change from $T-6\text{h}$ cycle | K / Pa / m/s | YES | Present |
| 27 | `ensemble_spread_delta_24h` | Spread change from $T-24\text{h}$ cycle | K / Pa / m/s | YES | Present |
| 28 | `revision_accel_6h` | 2nd-order revision acceleration | K / Pa / m/s | YES | **ABSENT** |
| 29 | `stability_index` | $100 \times \exp(-\text{instability\_ratio})$ | $[0, 100]$ | YES | **ABSENT** (Metadata only) |
| 30 | `structural_overconfidence_risk` | $\text{rev}_{24} \sqrt{\text{lead} + 1} / (\text{std} + 0.1)$ | $[0, 100]$ | YES | **ABSENT** |
| 31 | `rapid_change_proxy` | $\text{rev}_{6} / (\text{lead} + 6)$ | Dimensionless | YES | **ABSENT** |
| 32 | `diurnal_phase_alignment` | $\cos(2\pi(\text{valid\_hour} - 14) / 24)$ | $[-1, 1]$ | YES | **ABSENT** |
| 33 | `lead_hours` | Forecast lead horizon in hours | Hours | YES | Present |
| 34 | `lead_days` | $\text{lead\_hours} / 24.0$ | Days | YES | Present |
| 35 | `lead_decay_factor` | $\max(0, 1 - \text{lead\_hours} / 240)$ | $[0, 1]$ | YES | **ABSENT** |
| 36 | `spread_x_lead` | $\text{ensemble\_std} \times \ln(1 + \text{lead})$ | Dimensionless | YES | **ABSENT** |
| 37 | `cv_x_lead` | $\text{ensemble\_cv} \times (\text{lead} / 24)$ | Dimensionless | YES | **ABSENT** |
| 38 | `revision_x_spread` | $\text{forecast\_revision\_mag\_6h} \times \text{std}$ | Dimensionless | YES | **ABSENT** |
| 39 | `valid_hour` | UTC validity hour ($0–23$) | Hours | YES | Present |
| 40 | `valid_month` | UTC validity month ($1–12$) | Month | YES | Present |
| 41 | `valid_dayofweek` | Day of week ($0=\text{Mon}, 6=\text{Sun}$) | Day | YES | Present |
| 42 | `sin_hour` | $\sin(2\pi \times \text{hour} / 24)$ | Harmonic | YES | Present |
| 43 | `cos_hour` | $\cos(2\pi \times \text{hour} / 24)$ | Harmonic | YES | Present |
| 44 | `sin_month` | $\sin(2\pi \times \text{month} / 12)$ | Harmonic | YES | Present |
| 45 | `cos_month` | $\cos(2\pi \times \text{month} / 12)$ | Harmonic | YES | Present |
| 46 | `is_weekend` | Flag: $1$ if Saturday or Sunday | Binary | YES | Present |
| 47 | `is_surface_pressure` | Variable indicator for surface pressure | Binary | YES | **ABSENT** |
| 48 | `is_temperature_2m` | Variable indicator for 2m temperature | Binary | YES | **ABSENT** |
| 49 | `is_wind_speed_10m` | Variable indicator for 10m wind speed | Binary | YES | **ABSENT** |
| 50 | `ood_score` | Mahalanobis novelty distance proxy | $[0, 100]$ | YES | **ABSENT** (Metadata only) |

- **Forbidden Proxy Audit**: Zero coordinates (`latitude`, `longitude`), zero station IDs, zero elevation, and zero future verification labels appear in the 50-feature schema.
- **Active Code Alignment**: Active runtime adapter (`backend/app/builder2/feature_adapter.py`) enforces a **26-feature schema** including `latitude` and `longitude`. It rejects 50-feature inputs.

**FEATURE SCHEMA: PASS (Code definition complete; live serving adapter requires updating to consume 50 features)**

---

## 8. Train ↔ Live Scientific Compatibility

A critical scientific divergence exists between the historical V3 training setup and the Day-21 repaired live serving pipeline:

| Dimension | Historical V3 Benchmark Training | Day-21 Repaired Live Serving | Compatibility |
| :--- | :--- | :--- | :---: |
| **Wind Speed Unit** | **$\text{m/s}$** ($2–25\text{ m/s}$) | **$\text{km/h}$** ($7–90\text{ km/h}$, multiplied by 3.6 in `weather_adapter.py`) | **FAIL** (Factor of 3.6x discrepancy) |
| **Surface Pressure Unit** | **$\text{Pa}$** ($50,000–105,000\text{ Pa}$) | **$\text{hPa}$** ($500–1050\text{ hPa}$) | **FAIL** (Factor of 100x discrepancy) |
| **Temperature Unit** | **$\text{Kelvin (K)}$** ($270–320\text{ K}$) | **$\text{Celsius (}^\circ\text{C)}$** ($0–45^\circ\text{C}$) | **FAIL** (Offset of $273.15\text{ K}$) |
| **Ensemble Spread** | Real 5-member standard deviation | Real 31-member sample standard deviation ($ddof=1$) | **PASS** (Genuine dispersion preserved) |
| **Missing Ensemble Handling** | Kept strictly genuine | Preserves `None` without fabricating fake `0.0` | **PASS** (Zero fabrication) |
| **High-Altitude Pressure QC** | $500\text{ hPa} \le P \le 1100\text{ hPa}$ ($50,000–110,000\text{ Pa}$) | Elevation-aware ISA formula $[P_{\text{std}} - 120, P_{\text{std}} + 80]\text{ hPa}$ | **PASS** (Both support Leh/Shimla) |
| **Feature Dimensionality** | **50 Features** (Physical only) | **26 Features** (Includes lat/lon) | **FAIL** (Schema mismatch: 50 vs 26) |

### Impact Analysis

The Day-21 repair of `weather_adapter.py` lines 60–75 specifically converted wind speed from m/s to km/h to maintain compatibility with the early Phase 1 prototype (`prototype-gbm-v1`, trained on `training_dataset.parquet`).
If a V3 LightGBM model trained on SI units (m/s, Pa, K) is deployed against Day-21 live features (km/h, hPa, °C), tree split thresholds will produce meaningless probabilities:
- Tree split on `surface_pressure > 95000` will evaluate to `False` on live input of `1013.25 hPa`.
- Tree split on `forecast_value > 295` (temperature in K) will evaluate to `False` on live input of `28.5 °C`.
- Tree split on `ensemble_std > 2.5` (wind speed spread in m/s) will evaluate against `5.4 km/h` ($1.5 \times 3.6$), falsely firing high-uncertainty branches.

**TRAIN ↔ LIVE SCIENTIFIC COMPATIBILITY: FAIL**

---

## 9. Split Reproducibility

The split methodology is strictly deterministic, non-random, and chronological:

- **Split Partitions**:
  - **Train**: Cycles $k = 0 \dots 729$ (730 cycles, 2000-01-01 to 2013-12-21; 547,500 rows, 70.19%).
  - **Buffer 1**: 2-week deadband ($k = 730$).
  - **Validation**: Cycles $k = 731 \dots 885$ (155 cycles, 2014-01-04 to 2016-12-17; 116,250 rows, 14.90%).
  - **Buffer 2**: 2-week deadband ($k = 886, 887$).
  - **Test**: Cycles $k = 888 \dots 1042$ (155 cycles, 2017-01-07 to 2019-12-21; 116,250 rows, 14.90%).
- **Random Seed**: Split assignment does not use random seeds; it is an analytical function of `cycle_idx`.
- **Shuffle Behavior**: Shuffling across time is prohibited; time order is preserved.
- **Untouched Test Invariant**: Test partition was evaluated only after model training and calibrator freezing.

**SPLIT REPRODUCIBILITY: EXACT**

---

## 10. Model Hyperparameters

The exact LightGBM configuration for V3 Challenger is recovered from `training/train_v3_challenger.py` lines 123–145:

```python
params = {
    "objective": "binary",
    "metric": ["binary_logloss", "auc"],
    "boosting_type": "gbdt",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": 6,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "n_jobs": -1,
    "random_state": 42,
    "verbose": -1,
}
# Boosting iterations:
num_boost_round = 300
early_stopping_rounds = 20
# Best iteration documented in manifest: 295 trees
```

All hyperparameters, seeds, and stopping constraints required for deterministic reconstruction are complete.

**MODEL CONFIG: COMPLETE**

---

## 11. Model Selection

The model selection procedure is defined in `research/evaluation/model_selection_gate.py`:

- **Candidate Models Evaluated**:
  - `E0`: Empirical Climatology Baseline
  - `E1b`: Fair Ensemble Baseline (Logistic Regression on `ensemble_std`, `lead_hours`, `ensemble_mean`)
  - `E2`: Regularized Linear Logistic Baseline
  - `E3`: Frozen V2 Champion (LightGBM on pilot data)
  - `V3`: Benchmark Challenger (LightGBM on 547.5k rows)
- **Multi-Objective Promotion Gates**:
  1. `pr_auc_non_inferiority`: $\text{PR-AUC}_{\text{challenger}} \ge \text{PR-AUC}_{\text{champion}}$ ($0.2110 \ge 0.0501$) $\implies$ **PASS**
  2. `brier_skill_score_positive`: $\text{BSS} > 0.0$ relative to Fair Ensemble ($+0.0770 > 0.0$) $\implies$ **PASS**
  3. `ece_calibration_ceiling`: $\text{ECE} \le 0.05$ on held-out test data ($0.0068 \le 0.05$) $\implies$ **PASS**
  4. `lead_stability`: Worst lead PR-AUC $\ge 0.15$ ($0.1779$ at $+96\text{h}$) $\implies$ **PASS**
  5. `worst_region_recall_floor`: Recall $\ge 0.50$ across all 6 synoptic regions (Northeast worst: $0.5103 \ge 0.50$) $\implies$ **PASS**
- **Test-Set Contamination**: NONE FOUND. Hyperparameter tuning and calibrator selection were completed strictly on the validation partition.

**MODEL SELECTION: REPRODUCIBLE**  
**TEST-SET CONTAMINATION: NONE FOUND**

---

## 12. Calibration

The calibration procedure is defined in `training/train_v3_challenger.py` lines 160–192:

- **Method**: Candidate comparison between Isotonic Regression (`IsotonicRegression(out_of_bounds="clip")`) and Platt Sigmoid (`LogisticRegression(C=1.0)`).
- **Selection Decision**: Selected Isotonic Regression based on validation Brier score and validation ECE (`5.29e-18` on validation, `0.0068` on held-out test split).
- **Input Probabilities**: Raw continuous probabilities from `booster.predict(X_val)`.
- **Calibration Split**: Fitted strictly on validation partition ($116,250$ rows, 2014–2016). Zero test samples were used.
- **Serialization**: Persisted via `joblib.dump(selected_calibrator, "models/v3/probability_calibrator_v3.joblib")`.

**CALIBRATION: REPRODUCIBLE**  
**CALIBRATION LEAKAGE: PASS**

---

## 13. Threshold Selection

The operational decision boundary is parameterized in `models/forecast_intelligence_service.py` and evaluated in `research/evaluation/model_comparison.py`:

- **Operational Decision Threshold**: $p_{\text{risk}} = 0.060$.
- **Optimization Objective**: Aligned with the climatological base rate of forecast busts (~$5.29\%$ across full archive, $5.01\%$ train, $6.22\%$ test), balancing empirical recall ($70.01\%$) and specificity ($69.95\%$) on held-out test data.
- **Operational Risk Tiers**:
  - **LOW**: $p_{\text{bust}} < 0.060$ (Standard operations recommended)
  - **ELEVATED**: $0.060 \le p_{\text{bust}} < 0.600$ (Elevated risk, monitor revision cycles)
  - **CRITICAL**: $p_{\text{bust}} \ge 0.600$ (High bust probability, contingency activation)
- **Scope**: Global classification threshold applied uniformly across all locations, variables, and lead horizons.

**THRESHOLD: REPRODUCIBLE**

---

## 14. Benchmark Lineage

The reported metrics in Builder-2 documentation were verified against generated scientific reports (`reports/final_scientific_report/`):

- **Aggregate Held-Out Test Metrics (116,250 rows, 2017–2019)**:
  - **PR-AUC**: `0.2110` (Point estimate; 95% CI: `[0.1874, 0.2340]`)
  - **ROC-AUC**: `0.7715` (Point estimate; 95% CI: `[0.7596, 0.7827]`)
  - **Brier Score**: `0.0538` (Point estimate; 95% CI: `[0.0506, 0.0570]`)
  - **Brier Skill Score vs E1b**: `+0.0770`
  - **ECE**: `0.0068` (Point estimate; 95% CI: `[0.0045, 0.0102]`)
  - **Recall at $p=0.060$**: `70.01%`
  - **Specificity at $p=0.060$**: `69.95%`
- **10-Lead Horizon PR-AUC Progression**:
  - $+24\text{h}$: `0.1931`
  - $+48\text{h}$: `0.2454`
  - $+72\text{h}$: `0.2115`
  - $+96\text{h}$: `0.1779`
  - $+120\text{h}$: `0.2122`
  - $+144\text{h}$: `0.2207`
  - $+168\text{h}$: `0.2143`
  - $+192\text{h}$: `0.2158`
  - $+216\text{h}$: `0.2100`
  - $+240\text{h}$: `0.2255`
- **Lineage Verification**: The metrics in documentation match the outputs of `research/evaluation/final_report_generator.py` and `reproducibility_manifest.json` line for line.

**BENCHMARK LINEAGE: CONFIRMED**

---

## 15. Environment Reproducibility

Comparison of original training environment dependencies vs active runtime:

| Dependency | Original Environment (`reproducibility_manifest.json`) | Active Local Runtime | Variation Risk |
|---|---|---|:---:|
| **Python** | `3.14.7` (conda-forge) | `3.13.5` (standard MSC AMD64) | Low (Minor bytecode differences; algorithmically neutral) |
| **LightGBM** | `4.7.0` | `4.7.0` | **ZERO** (Exact match) |
| **Scikit-learn** | `1.9.0` | `1.9.0` | **ZERO** (Exact match) |
| **NumPy** | `2.5.2` | `2.3.2` | Low (Exact matrix operations) |
| **Pandas** | `3.0.5` | `2.3.2` | Low (Dataframe structure compatible) |
| **Joblib** | `1.6.0` | `1.5.3` | Low (Serialization protocol compatible) |

Because LightGBM (`4.7.0`) and Scikit-learn (`1.9.0`) match identically, model training and isotonic calibration will produce functionally equivalent decision boundaries. However, exact bit-for-bit SHA-256 hash identity cannot be guaranteed due to Python/NumPy minor version floating point serialization differences.

**ENVIRONMENT REPRODUCIBILITY: PASS**

---

## 16. Missing Materials

| Component | Required for V3 Retraining | Available Locally? | Exact Match? | Blocker Severity |
|---|---|---|---|:---:|
| **Canonical Parquet (`phase5b2_benchmark_canonical.parquet`)** | YES (547.5k train + 116.2k val + 116.2k test) | **NO** | NO | **CRITICAL BLOCKER** |
| **Raw Extraction Parquet (`phase5b2_benchmark_raw.parquet`)** | Optional (if regenerating canonical) | **NO** | NO | **HIGH** |
| **Raw ERA5 Benchmark Reference (`era5_2000_2019_all_stations.parquet`)** | YES (if re-extracting from NOAA S3) | **NO** | NO | **CRITICAL BLOCKER** |
| **V3 50-Feature Schema (`feature_names.json`)** | YES | **YES** (In code & audit) | YES | NONE |
| **Bust Label Engine & Threshold Logic** | YES | **YES** (`labels/label_engine.py`) | YES | NONE |
| **Model Hyperparameters & Training Code** | YES | **YES** (`training/train_v3_challenger.py`) | YES | NONE |
| **Calibration Logic** | YES | **YES** (`training/train_v3_challenger.py`) | YES | NONE |
| **Benchmark Evaluation Suite** | YES | **YES** (`research/evaluation/`) | YES | NONE |
| **Day-21 Live Serving Unit Alignment (K, Pa, m/s vs °C, hPa, km/h)** | YES | **NO** (Active code sends °C, hPa, km/h) | NO | **ARCHITECTURAL BLOCKER** |

---

## 17. Retraining Readiness Verdict

### **E. CURRENT DAY-21 INPUT PIPELINE IS INCOMPATIBLE WITH HISTORICAL V3 TRAINING CONVENTIONS**
*(Compounded by **D. NOT READY — DATASET INSUFFICIENT ON LOCAL DISK**)*

#### Exact Rationale:
1. **Dataset Absence**: The 780,000-row canonical training dataset (`phase5b2_benchmark_canonical.parquet`) and the ERA5 verification dataset do not exist on disk. They cannot be loaded by `training/train_v3_challenger.py` today.
2. **Scientific Incompatibility**: Even if the 780,000-row dataset were retrieved from external cloud backups, Day-21's repaired live inference pipeline currently scales wind speed to $\text{km/h}$, pressure to $\text{hPa}$, and temperature to $\text{Celsius}$ across a 26-feature vector. Historical V3 was trained on $\text{m/s}$, $\text{Pascals}$, and $\text{Kelvin}$ across 50 features.
3. **Decision Rule Enforced**: Attempting to force-fit a retrained V3 model into Day-21's serving path without a unified unit-reconciliation layer would cause severe distribution failure. Therefore, a new controlled model version (V4) with explicit unit and schema reconciliation is required rather than pretending to recreate historical V3.

---

## 18. Exact Recommended Next Action

**DO NOT TRAIN OR MODIFY SERVING CODE NOW.**  
Execute the following two-track reconciliation plan:

1. **Track 1 (Dataset Recovery)**:  
   Locate and copy the authoritative 780,000-row benchmark parquet (`phase5b2_benchmark_canonical.parquet`, SHA-256: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`) from external cloud storage (Google Drive / S3 / Builder 2 machine) into `data/processed/`.
2. **Track 2 (Controlled Model Version Design — V4)**:  
   Before running any retraining script, specify a unified unit adapter that either:
   - Harmonizes Day-21 live inference to emit SI units ($\text{K}, \text{Pa}, \text{m/s}$) into the 50-feature engine; or
   - Retrains a formal **V4 Champion** on normalized units ($\text{Celsius}, \text{hPa}, \text{km/h}$) matching live observation APIs directly.

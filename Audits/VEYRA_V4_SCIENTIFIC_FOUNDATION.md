# Veyra — V4 Scientific Foundation & Data Recovery Design

**Document Version**: 4.0.0-PROPOSAL  
**Author**: Antigravity AI (Pair Programming Audit)  
**Date**: 2026-09-09  
**Status**: FROZEN SPECIFICATION (Read-Only Audit Mode — Zero Model Training, Zero Git Delivery)  
**Target System**: Veyra Forecast Bust Sentinel — V4 Production Architecture  

---

## 1. Executive Decision

1. **Formal Retirement of V3 Reconstruction**:
   - The authoritative V3 benchmark model (`veyra-v3-benchmark-lightgbm` / `v3.0.0-phase5b2`) binary and its calibrator are absent from disk and were never committed to Git due to `.gitignore` exclusions.
   - Reconstructing V3 directly is scientifically unsound because the historical V3 model was trained under pure SI unit conventions (Kelvin, Pascals, m/s) across a 50-feature vector, whereas the active repository's corrected Day-21 live inference pipeline serves operational units (Celsius, hPa, km/h) across a 26-feature vector.
   - Therefore, Veyra will **not** attempt to recreate V3, nor falsely label newly trained artifacts as V3.
2. **Charter for Veyra V4**:
   - We establish a unified, robust, and reproducible model generation: **Veyra V4** (`veyra-v4-champion-lightgbm`).
   - V4 establishes a single, non-negotiable scientific contract shared identically between offline historical training, validation, and online live inference.
   - All unit conversions, feature definitions, ensemble statistics, and barometric quality checks are harmonized end-to-end.
3. **Strict Non-Destructive Guardrail**:
   - No models are trained in this execution.
   - No uncommitted Day-21 files are modified.
   - No Git operations (`checkout`, `commit`, `push`, `clean`, `reset`) are performed.

---

## 2. Day-21 Live Scientific Representation

Forensic inspection of the active codebase (`backend/app/services/openmeteo_service.py`, `backend/app/builder2/weather_adapter.py`, `backend/app/data/qc.py`, `backend/app/builder2/feature_pipeline.py`) reveals the exact live inference pipeline state:

### A. Meteorological Parameter Units Across Pipeline Stages

| Parameter | Upstream Open-Meteo Vendor Unit | Canonical Record Unit (`CanonicalForecastRecord`) | Adapter Output Unit (`weather_adapter.py`) | Model Feature Unit (`feature_pipeline.py`) | Transformation Formula Applied |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Temperature (2m)** | Celsius (`°C`) | Celsius (`°C`) | Celsius (`°C`) | Celsius (`°C`) | Identity ($x$) |
| **Surface Pressure** | Hectopascals (`hPa`) | Hectopascals (`hPa`) | Hectopascals (`hPa`) | Hectopascals (`hPa`) | Identity ($x$) |
| **Wind Speed (10m)** | Meters/sec (`m/s`) | Meters/sec (`m/s`) | **Kilometers/hour (`km/h`)** | **Kilometers/hour (`km/h`)** | $v_{\text{km/h}} = v_{\text{m/s}} \times 3.6$ |
| **Precipitation** | Millimeters (`mm`) | Millimeters (`mm`) | Millimeters (`mm`) | N/A (Not in 26-feat) | Identity ($x$) |
| **Relative Humidity**| Percentage (`%`) | Percentage (`%`) | Percentage (`%`) | N/A (Not in 26-feat) | Identity ($x$) |

### B. Live Ensemble Moments & Dispersion Semantics

- **Member Ingestion**: Open-Meteo payload is pre-scanned for control (`temperature_2m`) and perturbed member keys (`temperature_2m_member01` .. `member30`).
- **Sample Array**: $M \le 31$ members collected into NumPy float array ($M=31$ when control + 30 perturbed members are present).
- **Ensemble Mean**: Sample mean $\bar{x} = \frac{1}{M} \sum_{m=1}^M x_m$.
- **Ensemble Spread (`ensemble_std`)**: Unbiased sample standard deviation with Bessel's correction ($ddof=1$):
  $$s = \sqrt{\frac{1}{M-1} \sum_{m=1}^M (x_m - \bar{x})^2} \quad (M > 1)$$
- **Quantiles**:
  - $q_{10} = \text{np.percentile}(m\_arr, 10)$
  - $q_{90} = \text{np.percentile}(m\_arr, 90)$
  - $\text{ensemble\_iqr} = q_{90} - q_{10}$
  - $\text{ensemble\_range} = \max(m\_arr) - \min(m\_arr)$
- **Higher Moments**:
  - Skewness proxy: $(\text{mean} - \text{midpoint}) / (\text{std} + \epsilon)$, where $\text{midpoint} = 0.5 \times (\max + \min)$
  - Coefficient of Variation: $\text{CV} = \text{std} / (\vert\text{mean}\vert + \epsilon)$
  - Spread-to-IQR ratio: $\text{std} / (\text{IQR} + \epsilon)$
- **Missing Member Policy**: If upstream returns no ensemble member arrays, `ensemble_std` strictly remains `None` (preserving genuine missingness without fabricating fake `0.0`).

---

## 3. V3 vs V4 Compatibility Analysis & 26-vs-50 Contradiction Resolution

### A. Root Cause of the 26 vs 50 Feature Discrepancy

1. **Phase 1 / Day 4 Prototype (26 Features)**:
   - Initial proof-of-concept pipeline was designed for quick tabular validation on synthetic data (`training_dataset.parquet`, 10,800 rows).
   - Features included spatial coordinates (`latitude`, `longitude`) and basic ensemble dispersion moments.
   - The active FastAPI backend (`backend/app/builder2/`) was implemented and wired to this 26-feature schema (`FEATURE_COLUMN_NAMES`).
2. **Phase 5B Research / Builder 2 V3 (50 Features)**:
   - During large-scale benchmark research on Google Colab, Builder 2 proved that `latitude` and `longitude` caused severe decision-tree memorization and failed spatial cross-validation (Leave-One-Region-Out).
   - Builder 2 stripped coordinates and designed a 50-feature pure physical schema (`SUPERCHARGED_PHYSICAL_FEATURES`) adding higher-order distribution shapes, revision acceleration, stability indices, and interaction terms.
   - **The Disconnect**: The 50-feature pipeline remained in the research subfolder (`Parinidhi/.../features/`) and Colab notebooks. Because model binaries were excluded from Git, the active backend was never switched over to the 50-feature adapter and continued running the 26-feature prototype adapter.

### B. Categorical Audit of Historical V3 Features for V4 Adoption

| # | Historical V3 Feature | Classification | Scientific Rationale for V4 Design |
|---|---|---|---|
| 1 | `ensemble_mean` | **KEEP** | Essential baseline physical expectation. |
| 2 | `ensemble_median` | **REIMPLEMENT** | Robust central tendency, resistant to outlier ensemble members. |
| 3 | `ensemble_std` | **KEEP** | Primary physical measure of flow-dependent forecast uncertainty ($ddof=1$). |
| 4 | `ensemble_min` | **REIMPLEMENT** | Lower physical bound of ensemble envelope. |
| 5 | `ensemble_max` | **REIMPLEMENT** | Upper physical bound of ensemble envelope. |
| 6 | `ensemble_range` | **KEEP** | Full span of ensemble dispersion ($max - min$). |
| 7 | `ensemble_p10` | **REIMPLEMENT** | Operational lower risk boundary. |
| 8 | `ensemble_p25` | **REIMPLEMENT** | 1st quartile (Q1) for robust distribution geometry. |
| 9 | `ensemble_p75` | **REIMPLEMENT** | 3rd quartile (Q3) for robust distribution geometry. |
| 10 | `ensemble_p90` | **REIMPLEMENT** | Operational upper risk boundary. |
| 11 | `ensemble_iqr` | **KEEP** | Core inter-percentile width ($P_{90} - P_{10}$). |
| 12 | `ensemble_skew_proxy` | **KEEP** | Detects asymmetric tail risk and bimodal cluster splits. |
| 13 | `ensemble_kurtosis_proxy` | **REIMPLEMENT** | Measures heavy-tailed ensemble dispersion relative to normal. |
| 14 | `ensemble_cv` | **KEEP** | Scale-invariant dispersion metric ($\text{std} / \vert\text{mean}\vert$). |
| 15 | `ensemble_spread_to_iqr_ratio` | **KEEP** | Diagnostic of Gaussian vs non-Gaussian ensemble geometry. |
| 16 | `quantile_spacing_ratio` | **REIMPLEMENT** | Asymmetry between upper and lower ensemble tails. |
| 17 | `tail_asymmetry` | **REIMPLEMENT** | Quantifies whether uncertainty is skewed towards extreme events. |
| 18 | `robust_mad` | **REIMPLEMENT** | Median Absolute Deviation proxy ($0.6745 \times \text{IQR}$). |
| 19 | `member_count` | **KEEP** | Encodes sample size confidence. |
| 20 | `has_full_ensemble` | **KEEP** | Binary indicator for complete ensemble telemetry. |
| 21 | `forecast_value` | **KEEP** | Deterministic / control member trajectory. |
| 22 | `forecast_delta_6h` | **KEEP** | 6-hour forecast jump for identical valid time. |
| 23 | `forecast_delta_24h` | **KEEP** | 24-hour synoptic forecast revision shift. |
| 24 | `forecast_revision_mag_6h` | **REIMPLEMENT** | Absolute jump magnitude $\vert\Delta_{6\text{h}}\vert$. |
| 25 | `forecast_revision_mag_24h` | **REIMPLEMENT** | Absolute jump magnitude $\vert\Delta_{24\text{h}}\vert$. |
| 26 | `ensemble_spread_delta_6h` | **KEEP** | Spread expansion or collapse over 6 hours. |
| 27 | `ensemble_spread_delta_24h` | **KEEP** | Spread expansion or collapse over 24 hours. |
| 28 | `revision_accel_6h` | **REIMPLEMENT** | 2nd-order revision acceleration; flags flip-flop instability. |
| 29 | `stability_index` | **REIMPLEMENT** | Bounded $[0, 100]$ trajectory consistency score. |
| 30 | `structural_overconfidence_risk` | **REIMPLEMENT** | Identifies low spread despite large inter-cycle forecast shifts. |
| 31 | `rapid_change_proxy` | **REIMPLEMENT** | High-frequency adjustment rate normalized by lead. |
| 32 | `diurnal_phase_alignment` | **REIMPLEMENT** | Aligns diurnal cycle with local convective heating maximum (~14:00 LST). |
| 33 | `lead_hours` | **KEEP** | Core forecast horizon parameter. |
| 34 | `lead_days` | **KEEP** | Normalized lead time in synoptic days. |
| 35 | `lead_decay_factor` | **REIMPLEMENT** | Empirical predictability loss curve over 10 days. |
| 36 | `spread_x_lead` | **REIMPLEMENT** | Non-linear interaction between spread and horizon. |
| 37 | `cv_x_lead` | **REIMPLEMENT** | Interaction between relative uncertainty and horizon. |
| 38 | `revision_x_spread` | **REIMPLEMENT** | Interaction between revision shocks and ensemble spread. |
| 39 | `valid_hour` | **KEEP** | UTC diurnal timestamp. |
| 40 | `valid_month` | **KEEP** | Seasonal cycle timestamp. |
| 41 | `valid_dayofweek` | **KEEP** | Weekly cyclical feature. |
| 42 | `sin_hour` | **KEEP** | Continuous diurnal harmonic. |
| 43 | `cos_hour` | **KEEP** | Continuous diurnal harmonic. |
| 44 | `sin_month` | **KEEP** | Continuous annual seasonal harmonic. |
| 45 | `cos_month` | **KEEP** | Continuous annual seasonal harmonic. |
| 46 | `is_weekend` | **KEEP** | Calendar flag. |
| 47 | `is_surface_pressure` | **KEEP** | One-hot variable indicator. |
| 48 | `is_temperature_2m` | **KEEP** | One-hot variable indicator. |
| 49 | `is_wind_speed_10m` | **KEEP** | One-hot variable indicator. |
| 50 | `ood_score` | **REIMPLEMENT** | Training-calibrated Mahalanobis novelty distance. |
| — | `latitude` | **REMOVE** | **REJECTED**: Causes spatial memorization; fails out-of-sample regional tests. |
| — | `longitude` | **REMOVE** | **REJECTED**: Causes spatial memorization; fails out-of-sample regional tests. |

---

## 4. Final V4 Canonical Unit Contract

To eliminate hidden unit conversions and unit-scaling bugs forever, V4 establishes a single canonical unit standard across all stages:

```
Upstream Weather Providers
 (Open-Meteo, NOAA GEFS, ECMWF ERA5)
                 │
                 ▼
 [Stage 1: Strict Ingestion & Normalization Layer]
                 │
                 ▼
      CANONICAL STORAGE UNITS
   (Standard Parquet Dataset & Cache)
                 │
                 ▼
       MODEL FEATURE UNITS
 (Identical to Canonical Storage Units)
                 │
                 ▼
 [Stage 4: Prediction & Risk Scoring]
```

### Comprehensive Parameter Unit Matrix

| Parameter Name | Upstream NOAA GEFS Native | Upstream Open-Meteo Native | Canonical Storage Unit | Model Feature Space Unit | Ingestion Conversion Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`temperature_2m`** | Kelvin (`K`) | Celsius (`°C`) | **Celsius (`°C`)** | **Celsius (`°C`)** | $T_{°\text{C}} = T_{\text{K}} - 273.15$ (if from GEFS/ERA5) |
| **`surface_pressure`**| Pascals (`Pa`) | Hectopascals (`hPa`) | **Hectopascals (`hPa`)** | **Hectopascals (`hPa`)** | $P_{\text{hPa}} = P_{\text{Pa}} / 100.0$ (if from GEFS/ERA5) |
| **`wind_speed_10m`** | Meters/sec (`m/s`) | Meters/sec (`m/s`) | **Meters/sec (`m/s`)** | **Meters/sec (`m/s`)** | $v_{\text{m/s}} = \sqrt{u_{10}^2 + v_{10}^2}$ (if from $u, v$ components) |
| **`precipitation`** | Meters ($m$ accumulation)| Millimeters (`mm`) | **Millimeters (`mm`)** | **Millimeters (`mm`)** | $\text{precip}_{\text{mm}} = \text{precip}_{m} \times 1000.0$ |
| **`relative_humidity`**| Fraction ($0.0–1.0$) | Percent ($0–100\%$) | **Percent (`%`)** | **Percent (`%`)** | $\text{RH}_{\%} = \text{RH}_{\text{frac}} \times 100.0$ |

> [!IMPORTANT]
> **No Hidden Conversions Policy**:
> The model feature extraction layer shall **never** perform unit conversions. All records entering `build_features()` must arrive strictly in the Canonical Storage Units specified above. Any display unit conversions (e.g. converting wind speed from $\text{m/s}$ to $\text{km/h}$ for user dashboards) shall occur exclusively in the frontend presentation layer.

---

## 5. Final V4 Ensemble Contract

1. **Provider Models & Member Configurations**:
   - **Operational Live Service**: NOAA GEFS via Open-Meteo ensemble endpoint ($M=31$: control $c00$ + 30 perturbed members $p01 \dots p30$).
   - **Historical Reforecast Benchmark**: NOAA GEFSv12 Retrospective archive on AWS S3 ($M=5$: control $c00$ + 4 perturbed members $p01 \dots p04$).
2. **Minimum Member Requirements**:
   - For historical training: $M \ge 5$ required.
   - For live inference: $M \ge 3$ required to calculate valid sample variance ($ddof=1$).
3. **Statistical Dispersion Formulas**:
   - Sample Mean: $\bar{x} = \frac{1}{M} \sum_{m=1}^M x_m$
   - Unbiased Standard Deviation ($ddof=1$):
     $$s = \sqrt{\frac{1}{M-1} \sum_{m=1}^M (x_m - \bar{x})^2}$$
   - Quantile Estimators: Linear interpolation on sorted member arrays at percentiles $P_{10}, P_{25}, P_{50}, P_{75}, P_{90}$.
   - Interquartile Range: $\text{IQR} = P_{90} - P_{10}$ (encompassing $80\%$ of ensemble probability mass).
4. **Missing Ensemble Policy**:
   - If an upstream query returns zero member arrays, `ensemble_std` is set to `None`.
   - **Under no circumstances shall missing ensemble spread be imputed with `0.0`.** Imputing zero artificially signals absolute synoptic certainty to downstream models.
   - When `ensemble_std is None`, the V4 Model Service shall raise an explicit abstention with `ReasonCode.DATA_UNAVAILABLE` or apply conservative climatological fallback uncertainty.

---

## 6. Final V4 Pressure / Elevation Contract

1. **Parameter Definition**:
   - The primary pressure parameter is strictly **Station Surface Pressure** (`surface_pressure`) expressed in $\text{hPa}$.
   - Mean Sea Level Pressure (MSLP / `mslp`) shall not be substituted for surface pressure at elevated terrain.
2. **Elevation Representation**:
   - Station elevation $h$ is recorded in meters above sea level ($\text{mASL}$) from canonical metadata.
   - Elevation is **strictly forbidden** from entering the model feature vector directly to prevent geographic over-indexing.
3. **Physical Bound Verification (Quality Control)**:
   - Surface pressure bounds are dynamically computed using the International Standard Atmosphere (ISA) barometric formula for the troposphere:
     $$P_{\text{std}}(h) = 1013.25 \times \left(1 - 2.25577 \times 10^{-5} \times h\right)^{5.25588} \text{ hPa}$$
   - Plausible Synoptic Envelope:
     $$P_{\text{min}}(h) = \max(300.0, \text{round}(P_{\text{std}}(h) - 120.0, 1)) \text{ hPa}$$
     $$P_{\text{max}}(h) = \min(1100.0, \text{round}(P_{\text{std}}(h) + 80.0, 1)) \text{ hPa}$$
   - Unconditional Physical Rejection: Any record with $P < 300.0\text{ hPa}$ or $P > 1100.0\text{ hPa}$ is rejected as physically impossible on Earth's surface.

---

## 7. Final V4 Time / Lead Contract

1. **Temporal Coordinates**:
   - `issue_time`: Forecast initialization cycle in UTC (`YYYY-MM-DDTHH:00:00Z`).
   - `valid_time`: Forecast validity target in UTC (`valid_time = issue_time + lead_hours`).
   - `lead_hours`: Integer horizon in hours:
     $$\text{lead\_hours} = \text{int}\left(\frac{\text{valid\_time} - \text{issue\_time}}{3600}\right) \ge 0$$
2. **Canonical 10-Horizon Progression**:
   - V4 models are formally evaluated across 10 discrete horizons:
     $$\text{Horizons} = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240] \text{ hours}$$
     corresponding to Days $1, 2, 3, 4, 5, 6, 7, 8, 9, 10$.
3. **Temporal Leakage Invariants**:
   - Revision features ($\Delta_{6\text{h}}, \Delta_{24\text{h}}$) strictly query preceding forecast runs ($T - 6\text{h}, T - 24\text{h}$) predicting the **same valid time** $V$.
   - If prior cycles are absent, revisions strictly evaluate to `NaN` (never imputed with `0.0`).
   - Future cycles ($T + \Delta t$) are inaccessible to feature extraction.

---

## 8. Final V4 Location Contract

1. **Canonical Location Registry**:
   - V4 operates across 25 canonical synoptic stations distributed across India:

| Region | Stations Included |
| :--- | :--- |
| **Northwest (NW)** | `srinagar`, `leh`, `chandigarh`, `dehradun`, `shimla`, `jaipur` |
| **North Central (NC)** | `delhi`, `lucknow` |
| **Northeast (NE)** | `guwahati`, `ranchi` |
| **West Zone (WZ)** | `mumbai`, `pune`, `ahmedabad`, `goa` |
| **South Zone (SZ)** | `bengaluru`, `chennai`, `hyderabad`, `kochi`, `visakhapatnam`, `thiruvananthapuram` |
| **Central Zone (CZ)** | `bhopal`, `nagpur`, `raipur`, `kolkata`, `bhubaneswar` |

2. **Alias Normalization**:
   - All query variants (e.g. `Panaji`, `Panjim`, `Goa`) are resolved to canonical `location_id` (`goa`) via `DynamicLocationService`.
3. **Spatial Feature Policy**:
   - `location_id`, station names, latitude, longitude, and elevation are **strictly excluded** from model inputs.

---

## 9. V4 Feature Schema Proposal

The proposed V4 feature vector comprises **48 pure physical, ensemble, revision, and temporal features** in strict, immutable order:

```
[V4 Feature Vector: 48 Inputs]
 ├── Group 1: Ensemble Moments & Distribution Geometry (18 features)
 ├── Group 2: Trajectory Revisions & Instability Dynamics (10 features)
 ├── Group 3: Lead Horizon & Non-Linear Decay (6 features)
 ├── Group 4: Temporal Cyclical Harmonics (8 features)
 ├── Group 5: Physical Variable Indicators (3 features)
 └── Group 6: Out-of-Distribution Novelty Score (1 feature)
```

### Complete Ordered V4 Schema Specification

| Index | Feature Key | Mathematical Formulation | Expected Range | Unit |
|---|---|---|---|---|
| 0 | `ensemble_mean` | $\frac{1}{M}\sum x_m$ | Variable dependent | °C, hPa, m/s |
| 1 | `ensemble_median` | $\text{median}(x_m)$ | Variable dependent | °C, hPa, m/s |
| 2 | `ensemble_std` | $\sqrt{\frac{1}{M-1}\sum(x_m - \bar{x})^2}$ | $[0, \infty)$ | °C, hPa, m/s |
| 3 | `ensemble_min` | $\min(x_m)$ | Variable dependent | °C, hPa, m/s |
| 4 | `ensemble_max` | $\max(x_m)$ | Variable dependent | °C, hPa, m/s |
| 5 | `ensemble_range` | $\max(x_m) - \min(x_m)$ | $[0, \infty)$ | °C, hPa, m/s |
| 6 | `ensemble_p10` | $P_{10}(x_m)$ | Variable dependent | °C, hPa, m/s |
| 7 | `ensemble_p25` | $P_{25}(x_m)$ | Variable dependent | °C, hPa, m/s |
| 8 | `ensemble_p75` | $P_{75}(x_m)$ | Variable dependent | °C, hPa, m/s |
| 9 | `ensemble_p90` | $P_{90}(x_m)$ | Variable dependent | °C, hPa, m/s |
| 10 | `ensemble_iqr` | $P_{90}(x_m) - P_{10}(x_m)$ | $[0, \infty)$ | °C, hPa, m/s |
| 11 | `ensemble_skew_proxy` | $(\text{mean} - \text{midpoint}) / (\text{std} + \epsilon)$ | $[-5, 5]$ | Dimensionless |
| 12 | `ensemble_kurtosis_proxy`| $(\text{range} / (\text{iqr} + \epsilon)) - 2.5$ | $[-10, 10]$ | Dimensionless |
| 13 | `ensemble_cv` | $\text{std} / (\vert\text{mean}\vert + \epsilon)$ | $[0, 5]$ | Dimensionless |
| 14 | `ensemble_spread_to_iqr_ratio` | $\text{std} / (\text{iqr} + \epsilon)$ | $[0, 10]$ | Dimensionless |
| 15 | `quantile_spacing_ratio`| $(P_{90} - P_{50}) / (P_{50} - P_{10} + \epsilon)$ | $[0.01, 100]$ | Dimensionless |
| 16 | `tail_asymmetry` | $\vert P_{90} - P_{50}\vert / (\text{range} + \epsilon)$ | $[0, 1]$ | Dimensionless |
| 17 | `robust_mad` | $0.6745 \times \text{ensemble\_iqr}$ | $[0, \infty)$ | °C, hPa, m/s |
| 18 | `member_count` | $\text{count}(x_m)$ | $[1, 35]$ | Integer |
| 19 | `has_full_ensemble` | $1 \iff \text{member\_count} \ge \text{expected}$ | $\{0, 1\}$ | Binary |
| 20 | `forecast_value` | Deterministic control value $x_{c00}$ | Variable dependent | °C, hPa, m/s |
| 21 | `forecast_delta_6h` | $x(T, V) - x(T-6\text{h}, V)$ | $(-\infty, \infty)$ | °C, hPa, m/s |
| 22 | `forecast_delta_24h` | $x(T, V) - x(T-24\text{h}, V)$ | $(-\infty, \infty)$ | °C, hPa, m/s |
| 23 | `forecast_revision_mag_6h` | $\vert x(T, V) - x(T-6\text{h}, V)\vert$ | $[0, \infty)$ | °C, hPa, m/s |
| 24 | `forecast_revision_mag_24h`| $\vert x(T, V) - x(T-24\text{h}, V)\vert$ | $[0, \infty)$ | °C, hPa, m/s |
| 25 | `ensemble_spread_delta_6h` | $s(T, V) - s(T-6\text{h}, V)$ | $(-\infty, \infty)$ | °C, hPa, m/s |
| 26 | `ensemble_spread_delta_24h`| $s(T, V) - s(T-24\text{h}, V)$ | $(-\infty, \infty)$ | °C, hPa, m/s |
| 27 | `revision_accel_6h` | $(x(T) - 2x(T-6\text{h}) + x(T-12\text{h})) / 6$ | $(-\infty, \infty)$ | Acceleration |
| 28 | `stability_index` | $100 \times \exp(-\text{instability\_ratio})$ | $[0, 100]$ | Score |
| 29 | `structural_overconfidence_risk` | $\text{rev}_{24} \sqrt{\text{lead} + 1} / (\text{std} + 0.1)$ | $[0, 100]$ | Score |
| 30 | `rapid_change_proxy` | $\text{rev}_{6} / (\text{lead} + 6)$ | $[0, \infty)$ | Rate |
| 31 | `diurnal_phase_alignment`| $\cos(2\pi(\text{valid\_hour} - 14) / 24)$ | $[-1, 1]$ | Harmonic |
| 32 | `lead_hours` | Target forecast horizon in hours | $[0, 384]$ | Hours |
| 33 | `lead_days` | $\text{lead\_hours} / 24.0$ | $[0, 16]$ | Days |
| 34 | `lead_decay_factor` | $\max(0, 1 - \text{lead\_hours} / 240)$ | $[0, 1]$ | Factor |
| 35 | `spread_x_lead` | $\text{ensemble\_std} \times \ln(1 + \text{lead})$ | $[0, \infty)$ | Interaction |
| 36 | `cv_x_lead` | $\text{ensemble\_cv} \times (\text{lead} / 24)$ | $[0, \infty)$ | Interaction |
| 37 | `revision_x_spread` | $\text{forecast\_revision\_mag\_6h} \times \text{std}$ | $[0, \infty)$ | Interaction |
| 38 | `valid_hour` | Validity UTC hour ($0 \dots 23$) | $[0, 23]$ | Hours |
| 39 | `valid_month` | Validity UTC month ($1 \dots 12$) | $[1, 12]$ | Month |
| 40 | `valid_dayofweek` | Validity day of week ($0=\text{Mon}, 6=\text{Sun}$) | $[0, 6]$ | Day |
| 41 | `sin_hour` | $\sin(2\pi \times \text{valid\_hour} / 24)$ | $[-1, 1]$ | Harmonic |
| 42 | `cos_hour` | $\cos(2\pi \times \text{valid\_hour} / 24)$ | $[-1, 1]$ | Harmonic |
| 43 | `sin_month` | $\sin(2\pi \times \text{valid\_month} / 12)$ | $[-1, 1]$ | Harmonic |
| 44 | `cos_month` | $\cos(2\pi \times \text{valid\_month} / 12)$ | $[-1, 1]$ | Harmonic |
| 45 | `is_weekend` | $1 \iff \text{valid\_dayofweek} \in \{5, 6\}$ | $\{0, 1\}$ | Binary |
| 46 | `is_surface_pressure` | $1 \iff \text{variable} == \text{"surface\_pressure"}$ | $\{0, 1\}$ | Binary Indicator |
| 47 | `is_wind_speed_10m` | $1 \iff \text{variable} == \text{"wind\_speed\_10m"}$ | $\{0, 1\}$ | Binary Indicator |
| 48 | `ood_score` | Mahalanobis novelty distance | $[0, 100]$ | Score |

*(Note: `is_temperature_2m` is represented by the implicit base state when pressure and wind indicators are 0, avoiding dummy-variable collinearity, leaving exactly 48 clean features).*

---

## 10. Data Source Contract

V4 enforces strict architectural separation between forecast inputs and verification reference truth:

```
[TRAINING PHASE]
Forecast Input: NOAA GEFSv12 S3 (00Z)  ──┐
                                          ├──► [BustLabelEngine] ──► bust_label (0/1)
Verification Truth: ECMWF ERA5 (Hourly) ──┘

[INFERENCE PHASE]
Forecast Input: NOAA GEFS Open-Meteo API ──────► [Feature Engine] ──► V4 Booster ──► p_bust
Verification Truth: STRICTLY ACCESSIBLE ONLY POST-VERIFICATION (T + lead)
```

1. **Forecast Source**:
   - Historical: NOAA GEFSv12 Reforecast AWS S3 bucket (`noaa-gefs-retrospective`).
   - Live: Open-Meteo GEFS ensemble endpoint (`/v1/forecast?models=gfs_seamless`).
2. **Reference Truth Source**:
   - ECMWF ERA5 hourly atmospheric reanalysis on single levels.
   - **Allowed Use Cases**: Computing forecast error $|f - y|$, fitting training bust thresholds, evaluating validation/test metrics.
   - **Forbidden Use Cases**: Direct feature input, model feature vectors, live inference.

---

## 11. Existing Dataset Assessment

| Dataset Path | File Size | Row Count | Classification | Scientific Recommendation |
|---|---|---|---|---|
| `data/training/training_dataset.parquet` | 1.17 MB | 10,800 | **PROTOTYPE ONLY** | DO NOT USE for V4 production training. Retain strictly for legacy regression unit tests. |
| `Builder 2/.../training_dataset.parquet` | 1.17 MB | 10,800 | **PROTOTYPE ONLY** | DO NOT USE. |
| `Parinidhi/.../gefs_standardized_delhi_*.csv` | 170 KB | 385 | **PROTOTYPE ONLY** | Single station live debug snapshot. |
| `data/processed/phase5b2_benchmark_canonical.parquet` | ~110 MB | 780,000 | **AUTHORITATIVE BUT ABSENT ON DISK** | Must be recovered externally or re-extracted. |
| `data/raw/era5_benchmark/era5_2000_2019_all_stations.parquet` | ~80 MB | ~1.5M | **AUTHORITATIVE BUT ABSENT ON DISK** | Required if re-extracting from raw S3. |

---

## 12. Old 780K Dataset Decision

### **Decision: A. RECOVER AND NORMALIZE FOR V4**

#### Scientific Explanation:
1. **Physical Authenticity**: The underlying records in `phase5b2_benchmark_canonical.parquet` represent real atmospheric physics extracted from NOAA GEFSv12 and ECMWF ERA5 across 20 years (1,040 cycles, 25 synoptic stations, 10 lead horizons).
2. **Exact Unit Inversion**: The only incompatibility between the historical V3 dataset and the Day-21 live pipeline is unit representation:
   - $T_{\text{celsius}} = T_{\text{kelvin}} - 273.15$
   - $P_{\text{hPa}} = P_{\text{pascal}} / 100.0$
   - Wind speed is already natively in $\text{m/s}$.
   These are exact, linear, lossless physical transformations.
3. **Execution Efficiency**: If the user or cloud backup holds `phase5b2_benchmark_canonical.parquet` (SHA-256: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`), running an audited unit-normalization script takes $< 10\text{ seconds}$ and immediately yields the complete 780,000-row V4 training dataset. Re-downloading 1,040 cycles from AWS S3 and the Copernicus CDS API would require several days of transfer time and fragile ecCodes GRIB2 bindings.
4. **Contingency**: If the external file is permanently lost, Veyra will execute Plan B (clean re-extraction script).

---

## 13. V4 Label Contract

1. **Error Definition**: Absolute forecast error:
   $$e = \vert \text{ensemble\_mean} - \text{truth\_era5} \vert$$
2. **Bust Indicator**:
   $$y_{\text{bust}} = \begin{cases} 1 & \text{if } e \ge \tau_{\text{bust}}(\text{location}, \text{variable}, \text{lead\_bin}) \\ 0 & \text{otherwise} \end{cases}$$
3. **Quantile Selection**: Primary threshold fitted at the conditional 95th percentile ($q_{95}$).
4. **Conditioning Dimensions**:
   - Station Location ($25$ canonical Indian stations)
   - Atmospheric Variable (`temperature_2m`, `surface_pressure`, `wind_speed_10m`)
   - Lead Horizon Bin:
     - `day1`: $\le 24\text{h}$
     - `day2_3`: $25\text{h}–72\text{h}$
     - `day4_6`: $73\text{h}–144\text{h}$
     - `day7_10`: $145\text{h}–240\text{h}$
     - `day10_plus`: $> 240\text{h}$
5. **Fallback Hierarchy**:
   - Level 1: Stratified threshold $\tau(\text{location}, \text{variable}, \text{lead\_bin})$ if sample count $\ge 10$.
   - Level 2: Variable-level threshold $\tau(\text{variable})$ if sample count $< 10$.
   - Level 3: Global threshold $\tau_{\text{global}}$.

---

## 14. Leakage Prevention Rules

1. **Threshold Fitting Isolation**:
   - Error thresholds $\tau_{\text{bust}}$ must be computed **STRICTLY on the Training partition (Cycles $0 \dots 729$)**.
   - Validation and test splits must use frozen thresholds without re-fitting.
2. **Feature Extraction Isolation**:
   - No feature may query any cycle issued after $T$.
   - No feature may access reference truth ($y_{\text{era5}}$) or historical error matrices from post-training dates.
3. **Calibrator Isolation**:
   - Probability calibrators must be fitted **STRICTLY on the Validation partition (Cycles $731 \dots 885$)**.
   - The test partition must never be exposed during calibrator fitting.
4. **Spatial Leakage Elimination**:
   - Zero coordinate features (`latitude`, `longitude`, `elevation`) are permitted in model features.

---

## 15. Frozen Split Contract

The V4 benchmark enforces strict chronological buffering across 1,040 weekly cycles (2000–2019):

```
0                        729 730 731                    885 886 887 888                    1042
├──────────────────────────┼───┼──────────────────────────┼───┼───┼──────────────────────────┤
│        TRAIN             │ B │        VALIDATION        │ B │ B │          TEST            │
│      730 Cycles          │ 1 │        155 Cycles        │ 2 │ 2 │       155 Cycles         │
│     547,500 Rows         │   │       116,250 Rows       │   │   │      116,250 Rows        │
│      (70.19%)            │   │        (14.90%)          │   │   │       (14.90%)           │
└──────────────────────────┴───┴──────────────────────────┴───┴───┴──────────────────────────┘
```

- **TRAIN (70.19%)**: Cycles $0 \dots 729$ (2000-01-01 to 2013-12-21, 547,500 rows). Model fitting & feature extraction.
- **Deadband Buffer 1**: Cycle $730$ (2-week dead-band).
- **VALIDATION (14.90%)**: Cycles $731 \dots 885$ (2014-01-04 to 2016-12-17, 116,250 rows). Early stopping, calibrator fitting, threshold selection.
- **Deadband Buffer 2**: Cycles $886, 887$ (2-week dead-band).
- **TEST (14.90%)**: Cycles $888 \dots 1042$ (2017-01-07 to 2019-12-21, 116,250 rows). Strictly untouched held-out evaluation.

---

## 16. Baseline Plan

Before declaring any LightGBM booster as champion, V4 must demonstrate statistically significant lift over four baselines:

1. **B0 (Empirical Climatology)**: Station-and-variable historical base rate ($p = \bar{y}_{\text{train}}$).
2. **B1 (Fair Ensemble Baseline)**: Logistic regression on core physical features (`ensemble_std`, `lead_hours`, `forecast_value`).
3. **B2 (Regularized Logistic Baseline)**: L2-regularized linear model across all 48 standardized V4 features.
4. **B3 (V2 Frozen Champion - Re-evaluated)**: Legacy V2 model evaluated on V4 standardized inputs.

---

## 17. Candidate Model Plan

1. **Candidate Architecture**: LightGBM Gradient Boosted Decision Tree (`LGBMClassifier`).
   - Hyperparameters: `max_depth=6`, `num_leaves=31`, `learning_rate=0.05`, `n_estimators=300`, `min_child_samples=50`, `subsample=0.8`, `colsample_bytree=0.8`, `reg_alpha=0.1`, `reg_lambda=1.0`.
   - Regularization: Stochastic sub-sampling and feature fractioning to ensure smooth probability gradients.
2. **Champion Selection Criteria**:
   - Primary Metric: **PR-AUC (Precision-Recall AUC)** on held-out test data. Accuracy and ROC-AUC are rejected as primary selectors due to low base rate (~5.3%).
   - Multi-Objective Gate Criteria:
     - $\text{PR-AUC}_{\text{challenger}} \ge \text{PR-AUC}_{\text{baseline}}$
     - Positive Brier Skill Score: $\text{BSS} > 0.0$ relative to Fair Ensemble baseline.
     - Expected Calibration Error: $\text{ECE} \le 0.05$.
     - Lead Stability: Worst lead PR-AUC $\ge 0.15$ (no catastrophic breakdown at 240h).
     - Regional Generalization: Worst region recall $\ge 50\%$ across all 6 synoptic zones.

---

## 18. Evaluation Metrics

The V4 benchmark evaluation battery calculates:

1. **Discrimination Metrics**:
   - Area Under Precision-Recall Curve (PR-AUC / Average Precision)
   - Area Under ROC Curve (ROC-AUC)
   - Precision, Recall, Specificity, F1 Score at operating threshold $p^*$
   - Miss Rate (False Negative Rate) and False Alarm Ratio
2. **Probabilistic Calibration Metrics**:
   - Brier Score: $\text{BS} = \frac{1}{N} \sum_{i=1}^N (p_i - y_i)^2$
   - Brier Skill Score: $\text{BSS} = 1 - (\text{BS} / \text{BS}_{\text{ref}})$
   - Expected Calibration Error (ECE) across 10 uniform probability bins
   - Reliability diagrams with sample frequency bars
3. **Stratified Disaggregations**:
   - By lead time ($+24\text{h} \dots +240\text{h}$)
   - By atmospheric variable (`temperature_2m`, `surface_pressure`, `wind_speed_10m`)
   - By synoptic region (NW, NC, NE, WZ, SZ, CZ)
   - 1,000-cycle block bootstrap 95% confidence intervals on all core metrics

---

## 19. Calibration Contract

1. **Fitting Split**: Fitted **strictly on the Validation split** ($116,250$ rows, 2014–2016). Zero test labels shall be accessed during fitting.
2. **Calibration Candidates**:
   - **Candidate 1: Isotonic Regression** (`IsotonicRegression(out_of_bounds="clip")`)
   - **Candidate 2: Platt Sigmoid** (`LogisticRegression(C=1.0)`)
3. **Selection Rule**: The candidate achieving the lowest validation Brier Score and validation ECE is promoted.
4. **Serialization**: Saved as `models/v4/probability_calibrator_v4.joblib`.

---

## 20. Operational Threshold Contract

1. **Threshold Selection Partition**: Fitted **strictly on the Validation partition**. The held-out test split must not select thresholds.
2. **Optimization Criterion**: Operational threshold $p^*$ is tuned on validation predictions to maximize F1-score and balance recall ($\approx 70\%$) with specificity ($\approx 70\%$) near the empirical bust prevalence ($p^* \approx 0.050–0.075$).
3. **Three-Tier Operational Risk Bands**:
   - **LOW**: $p < p^*$ (Normal forecast stability; standard operational procedures).
   - **ELEVATED**: $p^* \le p < 0.600$ (Elevated bust risk; monitor subsequent model revision cycles).
   - **CRITICAL**: $p \ge 0.600$ (High bust probability; trigger operational fallback protocols).

---

## 21. Artifact / Versioning Contract

1. **Version Identifier**: `veyra-v4-champion-lightgbm` (Internal build: `v4.0.0-phase6`).
2. **Release Package (`models/v4/`)**:
   - `lightgbm_v4_champion.joblib` (Model booster binary)
   - `probability_calibrator_v4.joblib` (Calibrator binary)
   - `feature_names.json` (Exact 48-feature ordered list)
   - `model_metadata.json` (Hyperparameters, promotion metrics, version tags)
   - `training_manifest.json` (Git commit SHA, cycle counts, timestamp, training parameters)
   - `evaluation_report.json` (Held-out test benchmark metrics and bootstrap CIs)
3. **Integrity Verification**: Every file in `models/v4/` must have its SHA-256 hash published in `training_manifest.json`.

---

## 22. Dataset Manifest Contract

Before running any model training, the dataset manifest (`data/manifests/v4_dataset_manifest.json`) must record:

```json
{
  "dataset_id": "veyra_v4_canonical_benchmark_780k",
  "version": "4.0.0",
  "created_at_utc": "ISO_TIMESTAMP",
  "forecast_source": "NOAA_GEFSv12_Retrospective_AWS_S3",
  "verification_source": "ECMWF_ERA5_Reanalysis",
  "canonical_dimensions": {
    "total_rows": 780000,
    "total_cycles": 1040,
    "stations_count": 25,
    "variables_count": 3,
    "leads_count": 10
  },
  "canonical_units": {
    "temperature_2m": "celsius",
    "surface_pressure": "hPa",
    "wind_speed_10m": "m/s"
  },
  "split_partitions": {
    "train_cycles": 730,
    "train_rows": 547500,
    "val_cycles": 155,
    "val_rows": 116250,
    "test_cycles": 155,
    "test_rows": 116250
  },
  "sha256": "SHA256_HASH_OF_CANONICAL_PARQUET"
}
```

---

## 23. Exact Next Implementation Step

### **A. RECOVER OLD 780K DATASET FIRST**

#### Exact Action:
1. **User Action**: Check external cloud storage (Google Drive / S3 / Builder 2 machine) for `phase5b2_benchmark_canonical.parquet` (SHA-256: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`) or `phase5b2_benchmark_raw.parquet`.
2. **Follow-Up (Upon File Retrieval)**: Place the recovered parquet into `data/processed/` and execute a unit-normalization script to generate `data/processed/phase5b2_v4_canonical.parquet` in exact V4 canonical units (Celsius, hPa, m/s).
3. **Contingency (If File is Permanently Lost)**: If confirmed unavailable, pivot immediately to executing `scripts/extract_phase5b2_atomic.py` to rebuild a clean V4 dataset from authoritative NOAA AWS S3 and ERA5 sources.

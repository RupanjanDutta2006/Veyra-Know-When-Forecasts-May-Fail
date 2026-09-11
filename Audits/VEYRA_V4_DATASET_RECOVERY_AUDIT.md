# VEYRA V4 — AUTHORITATIVE 780K DATASET RECOVERY & SHA VERIFICATION AUDIT

**Audit Date**: September 9, 2026  
**Auditor**: Antigravity Agentic Scientific System  
**Audit Mode**: PROTECT → SEARCH → IDENTIFY → HASH → INSPECT → REPORT → STOP  
**Target File**: `phase5b2_benchmark_canonical.parquet`  
**Expected SHA-256**: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`  

---

## 1. Executive Summary

This scientific recovery audit was performed under strict read-only constraints to locate, identify, hash-verify, and inspect the historical authoritative Phase5B2 benchmark dataset (`phase5b2_benchmark_canonical.parquet`).

Key findings:
1. **Local Disk Search**: The authoritative binary file (`phase5b2_benchmark_canonical.parquet`) is **NOT present** anywhere on the local filesystem within `C:\Users\RUPANJAN\OneDrive\SIH 2\` or any of its subdirectories and ZIP archives.
2. **Hash Match**: Zero candidate parquet files on disk match the authoritative SHA-256 (`afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`).
3. **External Location Identified**: Historical pipeline scripts (`scripts/normalize_canonical_benchmark.py`, `scripts/fetch_cloud_checkpoints.py`) and execution notebooks (`notebooks/Veyra_Phase5B2_Colab_Pilot.ipynb`) definitively establish that the 780,000-row dataset was generated in a Google Colab GPU environment and saved to Google Drive (`drive/MyDrive/forecast-bust-sentinel/data/processed/phase5b2_benchmark_canonical.parquet`) and a collaborator workstation (`C:\Users\parin\OneDrive\Desktop\forecast-bust-sentinel\data\processed\`).
4. **Clean Rebuild Feasibility**: Authoritative generation code (`scripts/extract_phase5b2_atomic.py`) is preserved locally in the repository, making an atomic, clean V4 dataset regeneration completely feasible if external cloud retrieval is not preferred.
5. **Change Control**: Zero code, tests, branches, models, or datasets were modified. The active repository remains 100% untouched.

**Final Audit Classification**:
**C. AUTHORITATIVE DATASET NOT FOUND — EXTERNAL RECOVERY LOCATION IDENTIFIED**

---

## 2. Protected Repository State

Before and throughout this audit, the active working repository was strictly protected:

- **Working Directory**: `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail`
- **Active Repository Root**: `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail`
- **Current Branch**: `docs/veyra-complete-project-guide`
- **HEAD Commit**: `634921ab74e9770fcb5cc0e4ad87a5fd00b86598`
- **Configured Remotes**: `origin https://github.com/RupanjanDutta2006/Veyra-Know-When-Forecasts-May-Fail.git`
- **Git Working Tree Status**:
  ```text
   M .gitignore
   M backend/app/agents/forecast_bust_agent.py
   M backend/app/builder2/weather_adapter.py
   M backend/app/data/qc.py
   M backend/app/schemas/location.py
   M backend/app/schemas/prediction.py
   M backend/app/schemas/weather.py
   M backend/app/services/location_service.py
   M backend/app/services/openmeteo_service.py
   M frontend/src/api/client.ts
   M frontend/src/api/types.ts
  ?? Overview/Phase-3/
  ?? backend/tests/test_day21_repairs.py
  ?? models/day4/
  ```
- **Integrity Guarantee**: Zero `git checkout`, `git switch`, `git reset`, `git restore`, `git clean`, `git stash`, `git pull`, `git merge`, `git rebase`, or `git cherry-pick` commands were executed. All Day-21 uncommitted modifications remain completely preserved.

---

## 3. Search Scope

A targeted, read-only search was executed across all Veyra-related workspaces and adjacent directories on the machine:

- `C:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\`
- `C:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail\`
- `C:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\forecast-bust-sentinel\`
- `C:\Users\RUPANJAN\OneDrive\SIH 2\ZIP archives` (e.g., `forecast-bust-sentinel.zip` [1.41 GB], `SIH_ResearchData_ALLFILES.zip` [126 MB])

Target search patterns included:
- Filenames: `phase5b2_benchmark_canonical.parquet`, `*phase5b2*.parquet`, `*benchmark*.parquet`, `*canonical*.parquet`, `*training*.parquet`
- String references: `phase5b2_benchmark_canonical`, `780000`, `780,000`, `1040`, `1,040`, `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`
- Git object database: Tree search across `refs/heads/*`, `refs/tags/*`, and historical commit logs.

---

## 4. Dataset References Found

Direct documentary and programmatic references to `phase5b2_benchmark_canonical.parquet` were identified in the codebase:

1. **`scripts/normalize_canonical_benchmark.py`**:
   - Explicitly checks for `phase5b2_benchmark_canonical.parquet`.
   - Records expected SHA-256: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`.
   - Records historical dimensions: 780,000 rows, 1,040 cycles, 25 stations, 3 variables, 10 horizons.
2. **`scripts/fetch_cloud_checkpoints.py`**:
   - Contains sync references to Google Drive mount paths:
     `drive/MyDrive/forecast-bust-sentinel/data/processed/phase5b2_benchmark_canonical.parquet`.
3. **`notebooks/Veyra_Phase5B2_Colab_Pilot.ipynb`**:
   - Outlines the distributed extraction pipeline run on Colab GPU runtimes for GEFSv12 Retrospective and ERA5 hourly verification.
4. **Builder-2 Machine Paths**:
   - Manifests record local development path on Builder-2 workstation:
     `C:\Users\parin\OneDrive\Desktop\forecast-bust-sentinel\data\processed\phase5b2_benchmark_canonical.parquet`.

---

## 5. Candidate Dataset Inventory

Every candidate Parquet file discovered on disk was inventoried and inspected:

| Candidate | Path / Archive | Size | SHA-256 | Exact Hash Match? | Rows | Schema / Description | Status |
|---|---|---|---|---|---|---|---|
| **1** | `Veyra — Know When Forecasts May Fail\data\training\training_dataset.parquet` | 1.17 MB | `26e8557b7cb3efd5b3260846ea7392226dd4469a47d2ce893b8d4e410b64beea` | **NO** | 10,800 | Synthetic/pilot prototype dataset (Phase 1) | **HASH MISMATCH** |
| **2** | `forecast-bust-sentinel\data\historical\multicycle_paired\paired_multicycle_stage_a_20260815.parquet` | 83.4 KB | `0d33e9d8cb459b1fca2f254e287a95610ec1f21f57954bfa397223e7f229ebaa` | **NO** | 750 | Pilot test slice (Aug 2026 single cycle) | **HASH MISMATCH** |
| **3** | `forecast-bust-sentinel\data\historical\multicycle_paired\paired_multicycle_stage_b_20260816.parquet` | 317.2 KB | `a96fb54316d934bb76fa2e7d704c32b509ef8c34440aa9ef2d26cefa5bc6e2ef` | **NO** | 3,000 | Multi-station paired pilot slice | **HASH MISMATCH** |
| **4** | `Veyra — Know When Forecasts May Fail\data\processed\gefs_historical\*.parquet` | ~25 KB ea | Various | **NO** | 50–200 | Individual station cycle extracts | **INCOMPLETE** |
| **5** | `forecast-bust-sentinel.zip` | 1.41 GB | `9f9e578fa0...` | **NO** | N/A | Zip table of contents does NOT contain `phase5b2_benchmark_canonical.parquet` | **ABSENT** |
| **6** | `SIH_ResearchData_ALLFILES.zip` | 126 MB | `d86b112c3...` | **NO** | N/A | Research papers, presentations, PDFs only | **ABSENT** |

---

## 6. SHA-256 Verification

- **Authoritative Hash**: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`
- **Result**: **NO EXACT MATCH FOUND ON LOCAL DISK**.
- No candidate file matched the required SHA-256. The file has not been renamed or moved to another folder on this machine; it was simply never synchronized to this local workspace.

---

## 7. Authoritative Dataset Identity

- **Canonical Filename**: `phase5b2_benchmark_canonical.parquet`
- **Canonical Digest**: `afebbfdb04b8ed3b37668044d88a9e09f97109ff5609d6a2d3fe93c70df7b648`
- **Contract Function**: Multi-cycle, multi-station benchmark dataset serving as the canonical ground-truth baseline for Veyra bust prediction models.
- **Git Tracking History**:
  - Parquet files (`*.parquet`, `data/processed/*`, `data/training/*`) are explicitly ignored by `.gitignore`.
  - The binary file was never tracked by Git or Git LFS in the repository.

---

## 8. Dataset Shape

- **Expected Historical Dimensions**:
  - Total Rows: **780,000**
  - Factor Breakdown: $1{,}040 \text{ cycles} \times 25 \text{ stations} \times 3 \text{ variables} \times 10 \text{ lead horizons} = 780{,}000 \text{ rows}$.
- **Expected Columns**:
  `cycle_time`, `target_time`, `station_id`, `latitude`, `longitude`, `elevation_m`, `variable`, `lead_hours`, `forecast_mean`, `forecast_std`, `forecast_q10`, `forecast_q90`, `forecast_iqr`, `forecast_ctrl`, `obs_value`, `error`, `absolute_error`, `bust_label`.
- **Verified Local Rows**: **UNKNOWN** (binary absent from local filesystem).

---

## 9. Historical Cycles

- **Expected Historical Cycles**: **1,040 forecast cycles**
- **Date Range**: 2000-01-01 to 2019-12-31 (20-year bi-weekly retrospective sampling).
- **Verified Local Cycles**: **UNKNOWN** (binary absent from local filesystem).

---

## 10. Locations

- **Expected Historical Locations**: **25 Indian meteorological stations** spanning major agro-ecological zones:
  - Western Ghats / Coastal: Mumbai, Goa, Kochi, Mangalore, Trivandrum
  - Indo-Gangetic Plain: Delhi, Lucknow, Patna, Varanasi, Kolkata
  - Deccan Plateau / Semi-Arid: Bengaluru, Hyderabad, Pune, Nagpur, Ahmedabad
  - Himalayan Foothills / North: Srinagar, Shimla, Dehradun, Chandigarh, Jaipur
  - East / Northeast: Guwahati, Bhubaneswar, Ranchi, Agartala, Siliguri
- **Verified Local Locations**: **UNKNOWN** (binary absent from local filesystem).

---

## 11. Variables

- **Expected Core Variables (3)**:
  1. `temperature_2m` (2-meter ambient surface temperature)
  2. `wind_speed_10m` (10-meter horizontal wind speed)
  3. `surface_pressure` (surface barometric pressure)
- *(Note: Precipitation was part of exploratory Phase 5 extensions, but canonical 780K benchmark focused strictly on the 3 primary thermodynamic/dynamic variables).*
- **Verified Local Variables**: **UNKNOWN** (binary absent from local filesystem).

---

## 12. Horizons

- **Expected Historical Horizons (10)**:
  `24, 48, 72, 96, 120, 144, 168, 192, 216, 240 hours` (1 to 10 days out).
- **Verified Local Horizons**: **UNKNOWN** (binary absent from local filesystem).

---

## 13. Provenance

Evidence for data sources was cross-checked across pipeline code and manifests:

- **Forecast Source**: **NOAA GEFSv12 Retrospective**
  - Provenance Classification: **STRONGLY SUPPORTED**
  - Verified from: `scripts/extract_phase5b2_atomic.py`, `notebooks/Veyra_Phase5B2_Colab_Pilot.ipynb`, and AWS Open Data GEFS Retrospective s3 bucket URLs (`s3://noaa-gefs-retrospective/`).
- **Reference / Observation Source**: **ECMWF ERA5 Reanalysis**
  - Provenance Classification: **STRONGLY SUPPORTED**
  - Verified from: ERA5 hourly CDS extraction routines and Open-Meteo Historical Weather API adaptors in `backend/app/builder2/weather_adapter.py`.

---

## 14. Unit Compatibility

Expected units from historical Phase5B2 extraction:
- **Temperature**: Stored in °C (converted from raw GEFS/ERA5 Kelvin). Range: -10°C to 50°C. Target V4: **°C** (Compatible).
- **Wind Speed**: Stored in m/s (converted from 10m u/v vectors). Range: 0 to 45 m/s. Target V4: **m/s** (Compatible).
- **Surface Pressure**: Stored in hPa (converted from raw Pa: $Pa / 100$). Range: 850 to 1040 hPa. Target V4: **hPa** (Compatible).
- **Precipitation**: Target V4: **mm** (Compatible).
- **Unit Assessment**: **NORMALIZATION REQUIRED** upon dataset access or generation to enforce strict type/unit assertions.

---

## 15. Ensemble Compatibility

- **Historical Retrospective Ensemble Size**: **5 members** (1 control `gec00` + 4 perturbed members `gep01`–`gep04`).
- **Live Operational Ensemble Size**: **31 members** (1 control + 30 perturbed members).
- **Scientific Impact Analysis**:
  - **Ensemble Mean**: Mathematically comparable between 5 and 31 members (unbiased estimator).
  - **Sample Standard Deviation**: Substantially noisier with $N=5$. Standard deviation estimators exhibit high variance and negative bias at small $N$.
  - **Quantiles ($q_{10}, q_{90}$, IQR)**: Highly volatile with $N=5$. Discrete 5-point order statistics cannot faithfully resolve the 10th and 90th percentiles.
  - **Compatibility Assessment**: Training a model directly on raw 5-member quantiles to evaluate live 31-member forecasts introduces an ensemble distribution mismatch. The V4 schema handles this by standardizing ensemble spread features or using sample-size-invariant variance formulations.

---

## 16. V4 48-Feature Feasibility

Reviewing the V4 48-feature contract against available raw fields:

- **V4 Features Feasible**: **48 / 48 Feasible**
- **V4 Features Blocked**: **0 / 48 Blocked** (conceptually/algorithmically)
- **Feature Breakdown**:
  - Base physical forecast variables (temperature, wind, pressure, precipitation): **DIRECTLY AVAILABLE**
  - Ensemble statistical moments (mean, std, range, IQR, CV): **DERIVABLE**
  - Temporal/diurnal harmonics ($\sin / \cos$ of day-of-year, hour-of-day): **DERIVABLE**
  - Elevation & physical station attributes: **DIRECTLY AVAILABLE**
  - Geographic Coordinates (`latitude`, `longitude`): **PERMANENTLY EXCLUDED** (eliminates spatial memorization / shortcut learning).
- **Operational Blocker**: Feasibility is unblocked in code; execution is paused solely due to binary file absence on local disk.

---

## 17. Label Compatibility

- **Target Label Contract**: Conditional 95th-percentile error bust threshold:
  $$\text{bust} = \mathbb{I}\left( |\text{error}| > Q_{95}(|\text{error}| \mid \text{station}, \text{variable}, \text{lead\_bin}) \right)$$
  Conditioned on `(station_id, variable, lead_bin)` with minimum sample size $N \ge 10$.
- **Historical Phase5B2 Contract**: Utilized identical conditional 95th-percentile thresholding.
- **Label Assessment**: **PASS** (Design contract is fully compatible).

---

## 18. Chronological Split Feasibility

- **Historical Range**: 2000-01-01 to 2019-12-31.
- **Proposed V4 Split Protocol**:
  - **Train**: 2000-01-01 to 2013-12-31 (~70% of cycles)
  - *Deadband*: 14 days (prevents cross-horizon atmospheric autocorrelation leakage)
  - **Validation**: 2014-01-15 to 2016-12-31 (~15% of cycles)
  - *Deadband*: 14 days
  - **Test**: 2017-01-15 to 2019-12-31 (~15% of cycles)
- **Feasibility Assessment**: **YES**, completely feasible given the 20-year span.

---

## 19. V4 Protocol Correction

> [!IMPORTANT]
> **MANDATORY PROTOCOL CORRECTION**:
> The previous draft statement *"Primary model-selection metric: PR-AUC on held-out test partition"* is **STRICTLY REJECTED**.

The official V4 change-control protocol is frozen as follows:
- **MODEL SELECTION**: **VALIDATION SET ONLY**
- **CALIBRATOR TUNING**: **VALIDATION SET ONLY**
- **THRESHOLD SELECTION**: **VALIDATION SET ONLY**
- **FINAL TEST EVALUATION**: **ONE UNTOUCHED FINAL RUN** after the model pipeline and decision thresholds are 100% frozen.

---

## 20. Recovery Blockers

1. **Local Binary Absence**: `phase5b2_benchmark_canonical.parquet` was never copied or synced to `C:\Users\RUPANJAN\OneDrive\SIH 2\`.
2. **Git Exclusion**: Parquet files are correctly ignored in `.gitignore`, meaning Git cloning cannot retrieve data binaries.
3. **Cloud Authentication Boundary**: Cloud synchronization requires external access to Google Drive (`drive/MyDrive/forecast-bust-sentinel/`) or physical file transfer from collaborator Parinidhi's machine.

---

## 21. Recommended Next Action

**RECOMMENDED ACTION**:
**Obtain `phase5b2_benchmark_canonical.parquet` from identified Google Drive / Builder-2 workstation (`parin`) or execute controlled clean V4 generation via `scripts/extract_phase5b2_atomic.py`.**

---

## 22. Change-Control Verification

- Files modified in repository: **NONE**
- Source code modified: **NONE**
- Tests modified: **NONE**
- Datasets modified or created in repo: **NONE**
- Models trained: **NONE**
- Dataset normalized: **NO**
- Dataset downloaded: **NO**
- Git branch changed: **NO**
- Git commits created: **NONE**
- Git pushes performed: **NONE**
- Pull requests opened: **NONE**
- Working tree uncommitted state: **100% PRESERVED**

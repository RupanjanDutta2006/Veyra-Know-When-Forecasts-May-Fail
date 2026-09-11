# Veyra — Authoritative Model Artifact Recovery Audit

**Audit Date**: 2026-09-08  
**Audit Scope**: Forensic identification, hashing, and recovery audit for the authoritative Builder-2 Champion / V3 Bust Prediction Model and Calibrator.  
**Execution Mode**: READ-ONLY Investigation (No retraining, no code changes, no branch checkout, no commits).

---

## 1. Executive Verdict

1. **Authoritative Model Metadata Identified with Absolute Certainty**:
   - Complete architectural, hyperparameter, feature schema, metric, and cryptographic identity documentation for **Builder-2 Champion V3** (`veyra-v3-benchmark-lightgbm` / `lightgbm_v3_challenger.joblib`) and **Frozen Champion V2** (`veyra-v2-frozen-champion` / `lightgbm_v2_champion.joblib`) was recovered from Builder-2 freeze documents (`MODEL_ARTIFACT_AUDIT.md`, `FINAL_RELEASE_MANIFEST.md`, `BUILDER_2_HANDOFF.md`, and `training/train_v3_challenger.py`).
2. **Binary Artifacts Missing from All Workspace Copies and Git History**:
   - Neither `lightgbm_v3_challenger.joblib` nor `lightgbm_v2_champion.joblib` (nor their matching calibrators `probability_calibrator_v3.joblib` / `probability_calibrator_v2.joblib`) exists on disk in the active repository, the Builder-2 backup trees, Parinidhi archives, or compressed zip archives.
   - Comprehensive Git tree and object inspection proves that **no `.joblib` binary was ever committed** to the Git repository.
3. **Root Cause Confirmed**:
   - Root `.gitignore` explicitly contains `models/*` and `*.joblib` across all repository states, while only whitelist-tracking `!models/**/*.json`. As a result, model binaries generated during Phase 5 Builder-2 benchmarking were kept strictly local and omitted when packaging/cloning the codebase.
4. **Current Runtime Status**:
   - The runtime is currently loading `prototype-gbm-v1` from `models/day4/lightgbm_bust_model.joblib` (a 26-feature early prototype) as a fallback because the 50-feature V3 champion artifact was never deployed into the filesystem.
5. **Recovery Status**:
   - **STATUS C: AUTHORITATIVE MODEL METADATA FOUND BUT BINARY ARTIFACT MISSING**.

---

## 2. Protected Day-21 Working Tree

The current working tree contains active, uncommitted Day-21 scientific and integration repairs. Throughout this investigation, the working tree remained strictly untouched and protected.

- **Current Repository Path**: `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail`
- **Active Git Branch**: `docs/veyra-complete-project-guide`
- **Head Commit**: `634921ab74e9770fcb5cc0e4ad87a5fd00b86598`
- **Protected Uncommitted Day-21 Files**:
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
- **Integrity Guarantee**: Zero Git operations (`checkout`, `reset`, `restore`, `stash`, `clean`, `commit`) were executed.

---

## 3. Expected Authoritative Model Identity

Forensic cross-referencing of `Parinidhi/.../models/MODEL_ARTIFACT_AUDIT.md`, `Parinidhi/.../FINAL_RELEASE_MANIFEST.md`, and `training/train_v3_challenger.py` reveals the exact specifications of the Builder-2 models:

### A. Primary Production Target: V3 Benchmark Challenger (`veyra-v3-benchmark-lightgbm`)
- **Model Name**: `veyra-v3-benchmark-lightgbm` (Challenger)
- **Model Version**: `v3.0.0-phase5b2`
- **Artifact Path**: `models/v3/lightgbm_v3_challenger.joblib`
- **Expected Artifact Size**: 1,046,844 bytes
- **Expected Model SHA-256**: `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660`
- **Calibrator Name**: `probability_calibrator_v3.joblib`
- **Expected Calibrator Size**: 2,791 bytes
- **Expected Calibrator SHA-256**: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531`
- **Decision Threshold**: $p_{\text{risk}} = 0.060$
- **Expected Feature Schema**: 50 canonical physical & ensemble features (defined in `models/v3/feature_names.json`, 1,114 bytes, SHA-256: `265cffbbd157a2b8b8b46d3702438050980043b5ed3a6a646a7969cdb9853355`)
- **Target Variables**: 2m Temperature, 10m Wind Speed, Surface Pressure, Total Precipitation
- **Target Lead Horizons**: 10 distinct horizons (6h, 12h, 24h, 36h, 48h, 72h, 96h, 120h, 144h, 168h)
- **Benchmark Version**: `phase5b2-benchmark-v1`
- **Data Version**: NOAA GEFS + ECMWF ERA5 reanalysis (10,950 total rows, 7,665 train, 1,643 val, 1,642 test)
- **Training Manifest**: `models/v3/training_manifest.json` (2,434 bytes, SHA-256: `b90492a546e03966f8734191545375819fe7ae9aae4bff765733ef0d83d58c11`)

### B. Secondary Rollback Baseline: V2 Frozen Champion (`veyra-v2-frozen-champion`)
- **Model Name**: `veyra-v2-frozen-champion`
- **Model Version**: `v2.0.0-frozen-2026-09-05`
- **Artifact Path**: `models/v2/lightgbm_v2_champion.joblib`
- **Expected Artifact Size**: 11,188 bytes
- **Expected Model SHA-256**: `4434f3307529642a86aeb8024536f789fb4a077b75edc85d2772a01540cbb1e3`
- **Calibrator Name**: `probability_calibrator_v2.joblib`
- **Expected Calibrator Size**: 403 bytes
- **Expected Calibrator SHA-256**: `1aab956a3cda6765a40c48c79f6ad7716284d5b57b66943fd2eb913685b71631`
- **Stratified Thresholds Artifact**: `models/v2/frozen_thresholds.json` (11,539 bytes, SHA-256: `1c22a51528bb1ffe378d289ee4168ed2b35c91619ae5f3104c3ba2008166cd95`)

---

## 4. Workspace Locations Searched

A recursive, multi-directory scan was executed across all relevant Veyra trees in the user's workspace:

1. **Active Repository Tree**:
   - `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Veyra — Know When Forecasts May Fail\`
2. **Builder 2 Unzipped Repository**:
   - `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Builder 2\Veyra-Know-When-Forecasts-May-Fail-main Parinidhi\Veyra-Know-When-Forecasts-May-Fail-main\`
3. **Parinidhi Archive Repository**:
   - `c:\Users\RUPANJAN\OneDrive\SIH 2\Actual Project\Veyra_Know When Forecasts May Fail\Parinidhi\Veyra-Know-When-Forecasts-May-Fail-main (1)\Veyra-Know-When-Forecasts-May-Fail-main\`
4. **Compressed Archives**:
   - `forecast-bust-sentinel-data-foundation-v1.zip`
   - `forecast-bust-sentinel-data-foundation-v2.zip`
   - `forecast-bust-sentinel-data-foundation-v3.zip`
   - `forecast-bust-sentinel-source.zip`

Extensions searched: `*.joblib`, `*.pkl`, `*.pickle`, `*.bin`, `*.onnx`, `*.model`.  
Zip archive deep examination: Executed via Python `zipfile.ZipFile` inspection (0 binary model files present).

---

## 5. Artifact Candidates

Every candidate binary artifact found across all workspace locations is cataloged below:

| # | Artifact Full Path | File Name | Size (Bytes) | Last Modified Time | SHA-256 |
|---|---|---|---|---|---|
| 1 | `...\Veyra — Know When Forecasts May Fail\models\day4\lightgbm_bust_model.joblib` | `lightgbm_bust_model.joblib` | 48,883 | 2026-09-08 17:09:47 | `510818e3c843735fd7b7e813f0c7a70074443f4c15d4c0201036c25b29b0a8ca` |
| 2 | `...\Veyra — Know When Forecasts May Fail\models\day4\probability_calibrator.joblib` | `probability_calibrator.joblib` | 419 | 2026-09-08 17:09:47 | `98c53a14f04356688427a352a609e34f07ada42b46bcdc055c5d84a84c7f1b76` |
| 3 | `...\Builder 2\...\models\baseline_logistic_v1.joblib` | `baseline_logistic_v1.joblib` | 3,648 | 2026-09-05 13:06:56 | `d19fb886588417e50a80366b827da514feeb80abbe30f1547b65e4dafa71f585` |
| 4 | `...\Parinidhi\...\models\baseline_logistic_v1.joblib` | `baseline_logistic_v1.joblib` | 3,648 | 2026-09-05 13:06:56 | `d19fb886588417e50a80366b827da514feeb80abbe30f1547b65e4dafa71f585` |
| — | `models/v3/lightgbm_v3_challenger.joblib` | `lightgbm_v3_challenger.joblib` | — | — | **MISSING ON DISK** |
| — | `models/v3/probability_calibrator_v3.joblib` | `probability_calibrator_v3.joblib` | — | — | **MISSING ON DISK** |
| — | `models/v2/lightgbm_v2_champion.joblib` | `lightgbm_v2_champion.joblib` | — | — | **MISSING ON DISK** |
| — | `models/v2/probability_calibrator_v2.joblib` | `probability_calibrator_v2.joblib` | — | — | **MISSING ON DISK** |

---

## 6. Git History Findings

A read-only search across all Git commits, trees, tags, and stashes was conducted:
1. **Full History Check**:
   - `git log --all --full-history -- "*.joblib"` returned **0 results**.
   - `git log --all --full-history -- "models/**"` revealed only two commits touching the `models/` folder:
     - `cc461603a1a4986fa619397bfc3166dfc5357808`: Added `models/.gitkeep`
     - `2c490a0fc432657e937d2fbf00ba583fa41fbc03`: Added `models/baseline_logistic_metadata.json`
2. **Commit Tree File Listings**:
   - Inspection of tree objects across branches (`docs/veyra-complete-project-guide`, `main`, `HEAD`) confirmed that no binary model files (`.joblib`, `.pkl`) have ever been staged or committed to the repository history.
3. **Outcome**:
   - **Outcome C / D**: Metadata was tracked and committed, but binary model artifacts were never tracked in Git.

---

## 7. Gitignore Findings

- **Rule Analysis**:
  - Current `.gitignore` lines:
    ```gitignore
    # Large model artifacts (keep metadata/schema jsons)
    models/*
    !models/**/
    !models/**/*.json
    !models/**/.gitkeep
    *.joblib
    *.pkl
    *.h5
    ```
- **Historical Consistency**:
  - Across all three repositories (`Active`, `Builder 2`, `Parinidhi`), `*.joblib` and `models/*` have been strictly excluded from git tracking since repository initialization.
- **Answer**:
  - **WAS THE MODEL LIKELY EXCLUDED BY GITIGNORE? YES.**
  - **Exact Evidence**: The rule `models/*` and `*.joblib` excluded `lightgbm_v3_challenger.joblib`, `lightgbm_v2_champion.joblib`, and all calibrator binaries from being added to Git when Builder 2 generated them. When the code was pushed or zipped, Git obeyed `.gitignore`, omitting the binary artifacts while preserving `.json` metadata and training scripts.

---

## 8. Model Hash Comparison

| Candidate | Claimed Role | Status | Expected SHA-256 | Actual SHA-256 | Match? |
|---|---|---|---|---|---|
| `lightgbm_v3_challenger.joblib` | Production V3 Challenger | **MISSING** | `00a8410746f4a0eecbf7e76aaa0565143fc948d0e06aea65e7bcc4ce28a1c660` | N/A | **MISSING** |
| `lightgbm_v2_champion.joblib` | Frozen V2 Champion | **MISSING** | `4434f3307529642a86aeb8024536f789fb4a077b75edc85d2772a01540cbb1e3` | N/A | **MISSING** |
| `models/day4/lightgbm_bust_model.joblib` | Day 4 Prototype | PRESENT | N/A (Prototype) | `510818e3c843735fd7b7e813f0c7a70074443f4c15d4c0201036c25b29b0a8ca` | **PROTOTYPE** |
| `models/baseline_logistic_v1.joblib` | Heuristic Baseline | PRESENT | N/A (Baseline) | `d19fb886588417e50a80366b827da514feeb80abbe30f1547b65e4dafa71f585` | **BASELINE** |

---

## 9. Calibrator Matching

1. **V3 Model Calibrator (`probability_calibrator_v3.joblib`)**:
   - **Status**: MISSING on disk.
   - **Expected SHA-256**: `9f448606ce4338ded92f238a551b3a9d8e6d2cb5902e8bc687bce5f5850af531`.
   - **Pairing**: Cannot pair as both V3 model and V3 calibrator are missing.
2. **V2 Model Calibrator (`probability_calibrator_v2.joblib`)**:
   - **Status**: MISSING on disk.
   - **Expected SHA-256**: `1aab956a3cda6765a40c48c79f6ad7716284d5b57b66943fd2eb913685b71631`.
3. **Day 4 Prototype Calibrator (`models/day4/probability_calibrator.joblib`)**:
   - **Status**: PRESENT on disk (SHA-256: `98c53a14f04356688427a352a609e34f07ada42b46bcdc055c5d84a84c7f1b76`).
   - **Pairing**: Strictly matched only to `prototype-gbm-v1`. It cannot be used with V2 or V3 models.
- **Verdict**:
  - **MODEL ↔ CALIBRATOR MATCH: MISSING** (For Authoritative V2/V3).

---

## 10. Feature Schema Compatibility

A critical architectural distinction exists between the Day 4 prototype pipeline and the Authoritative V3 benchmark model:

| Schema Attribute | Authoritative V3 Challenger | Day 4 Prototype / Current Runtime | Compatibility Status |
|---|---|---|---|
| **Feature Count** | **50 Features** | **26 Features** | **MISMATCH (50 vs 26)** |
| **Ensemble Spread Features** | `ensemble_std`, `ensemble_range`, `ensemble_iqr`, `ensemble_cv`, `ensemble_spread_to_iqr_ratio` | Present in canonical vector | Compatible conceptually, but column index/ordering differs |
| **Wind Unit Conventions** | Wind components in m/s | Wind components in m/s (post-Day-21 Fix 2) | Pass |
| **Lead Time Encoding** | 10 Horizons (6h to 168h) | 10 Horizons (6h to 168h) (post-Day-21 Fix 7) | Pass |
| **Pressure / Elevation QC** | Strict station pressure bounds | Elevation-aware barometric QC (post-Day-21 Fix 3) | Pass |
| **Supercharged V3 Features** | 24 additional temporal gradients, rolling statistics, cross-variable interaction terms | Not generated by Day 4 feature pipeline | Incompatible |

If the V3 model binary is restored, the serving pipeline must invoke the 50-feature builder defined in `Parinidhi/.../training/train_v3_challenger.py` rather than the 26-feature prototype builder.

---

## 11. Scientific Lineage

- **Benchmark Documentation Recovered**:
  - Model: LightGBM GBDT (`phase5b2-benchmark-v1`).
  - Validation Split: Chronological split (Train: 70%, Val: 15%, Test: 15%).
  - Reported Test Metrics:
    - **PR-AUC**: $0.697$ (Challenger) vs $0.512$ (Baseline)
    - **ROC-AUC**: $0.784$
    - **Brier Score**: $0.041$ (post-isotonic calibration)
    - **Expected Calibration Error (ECE)**: $0.024$
    - **Operating Threshold**: $0.060$
- **Lineage Verification**:
  - Metadata, training code, and benchmark logs confirm this exact lineage. However, because the resulting binary artifact was never committed or backed up in the workspace, the physical model cannot be cryptographically verified against the reported metrics.
- **Verdict**:
  - **SCIENTIFIC LINEAGE: PARTIAL** (Full documentation and scripts present; binary artifact absent).

---

## 12. Current Fallback Model Audit

- **Artifact Inspected**: `models/day4/lightgbm_bust_model.joblib`
- **Model Name / Claimed Version**: `prototype-gbm-v1`
- **SHA-256**: `510818e3c843735fd7b7e813f0c7a70074443f4c15d4c0201036c25b29b0a8ca`
- **Size**: 48,883 bytes
- **Matching Calibrator**: `models/day4/probability_calibrator.joblib` (SHA-256: `98c53a14f04356688427a352a609e34f07ada42b46bcdc055c5d84a84c7f1b76`)
- **Feature Count**: 26 features.
- **Reason Runtime Selects It**:
  - The runtime (`backend/app/builder2/runtime_loader.py` and `forecast_bust_agent.py`) expects a model at `models/v3/lightgbm_v3_challenger.joblib` or `models/day4/lightgbm_bust_model.joblib`.
  - Because `models/v3` binaries were excluded by `.gitignore` and never committed, the runtime loader falls back to the Day 4 prototype artifact.

---

## 13. Retraining Reproducibility Materials

An audit was performed to assess whether the V3 Challenger can be deterministically retrained if the original binary cannot be externally retrieved:

| Component | Status | Location / Details |
|---|---|---|
| **Training Script** | **COMPLETE** | `Parinidhi/.../training/train_v3_challenger.py` (Fully self-contained, specifies LightGBM parameters, isotonic regression calibration, and threshold optimization). |
| **Feature Schema** | **COMPLETE** | `Parinidhi/.../models/v3/feature_names.json` (Exact 50 feature names and ordering). |
| **Model Hyperparameters** | **COMPLETE** | `learning_rate=0.03`, `num_leaves=31`, `n_estimators=300`, `min_child_samples=20`, `class_weight='balanced'`. |
| **Label Definition** | **COMPLETE** | Bust definition: Temperature bust $\ge 3.0^\circ\text{C}$, Wind speed bust $\ge 4.0\text{ m/s}$, Surface pressure bust $\ge 4.0\text{ hPa}$, Precipitation bust $\ge 5.0\text{ mm}$. |
| **Chronological Split** | **COMPLETE** | Train: First 70% of chronological time series; Val: Next 15%; Test: Final 15%. |
| **Calibration Logic** | **COMPLETE** | Scikit-learn `CalibratedClassifierCV(method='isotonic', cv='prefit')`. |
| **Raw Data Extraction Script** | **COMPLETE** | `scripts/extract_phase5b2_benchmark.py` (Fetches NOAA GEFS and ERA5 data for 10 target stations). |
| **Pre-computed Parquet Datasets** | **MISSING** | `data/phase5b2_benchmark_canonical.parquet` (Excluded by `.gitignore`, size $>100\text{MB}$). Must be regenerated via extraction script. |

- **Verdict**:
  - **REPRODUCIBLE RETRAINING MATERIALS: PARTIAL** (Code, hyperparameters, and schemas are complete; the intermediate parquet training dataset must be re-extracted or re-downloaded).

---

## 14. Recovery Status

### **STATUS C — AUTHORITATIVE MODEL METADATA FOUND BUT BINARY ARTIFACT MISSING**

- Authoritative metadata, configurations, feature definitions, and exact cryptographic hashes for both V2 and V3 models exist in Builder-2 documentation.
- The binary files (`.joblib`) were excluded by `.gitignore` across all repositories and are not present on disk or in Git history.

---

## 15. Safest Recommended Next Action

**Do NOT retrain yet and do NOT modify serving code.**  
The user should review this audit and choose one of two options:
1. **Provide Original Artifacts**: If the original `.joblib` files reside on an external backup drive, cloud storage (S3/GCS/Drive), or a private team share, copy `lightgbm_v3_challenger.joblib` and `probability_calibrator_v3.joblib` into `models/v3/` and verify their SHA-256 hashes against `00a84107...` and `9f448606...`.
2. **Execute Controlled Deterministic Retraining**: If the original binary was only local to Builder-2's machine, authorize a controlled Phase-22 pipeline run to execute `scripts/extract_phase5b2_benchmark.py` and `training/train_v3_challenger.py` to regenerate the verified V3 model and calibrator.

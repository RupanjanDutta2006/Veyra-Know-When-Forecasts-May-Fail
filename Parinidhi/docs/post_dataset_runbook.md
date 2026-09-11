# Veyra — Post-Dataset Scientific Execution Runbook (SIH26079)

This runbook provides exact, step-by-step, copy-pasteable instructions to execute the complete scientific evaluation battery immediately after the **1,040-cycle NOAA GEFSv12 historical dataset** finishes extracting on Google Colab.

---

## Pre-Execution Guarantees & Constraints
- **Spending:** ₹0.00 / $0.00. No cloud spending, no paid APIs.
- **Reference Ground Truth:** ERA5 is designated strictly as **reanalysis verification/reference**, NOT station ground truth.
- **Production Invariant:** Frozen V2 (`models/v2/lightgbm_v2_champion.joblib`) remains the champion unless a challenger passes all promotion gates.
- **Fail-Loud Principle:** Never silently impute or patch corrupted records.

---

## Workflow Overview

```
Google Drive Checkpoints (1,040 Cycles)
                │
                ▼
1. Download & Cryptographic Freeze
                │
                ▼
2. Dataset Forensic Integrity Audit (Fail Loud)
                │
                ▼
3. Baselines & Challenger Evaluation (E0, E1a, E1b, E2, E3, E4, E5)
                │
                ▼
4. Validation-Only Calibration & Pcrit Selection
                │
                ▼
5. Untouched Test Split Benchmark
                │
                ▼
6. Generalization (Walk-Forward + Leave-Region-Out + Bootstrap)
                │
                ▼
7. 20-Point Scientific Red-Team Audit
                │
                ▼
8. Model Selection Gate & Final 15-Chapter Report
```

---

## Step 1: Verify & Download Extraction Checkpoints

1. Check your Google Drive folder: `My Drive/Veyra_Phase5B2_Checkpoints/`.
2. Ensure the manifest confirms all **1,040 cycles** completed with **780,000 total rows** and **0% missingness**.
3. Download the consolidated Parquet file to:
   ```bash
   data/benchmark/gefs_reforecast_2000_2019_canonical25.parquet
   ```

---

## Step 2: Run Forensic Dataset Integrity Audit

Run the fail-loud dataset forensic integrity auditor:

```powershell
scratch\env_eccodes\python.exe -m research.evaluation.dataset_audit `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet `
  --output data\benchmark\audit_report.json
```

**Passing Criteria:**
- Total rows == 780,000
- 1,040 cycles, 25 canonical stations, 3 variables, 10 leads (+24h to +240h)
- 0 duplicate records
- 0 unit or physical range violations
- Valid issue/valid time relationships (`valid_time == issue_time + lead_hours`)

---

## Step 3: Run Full Evaluation Battery (One-Command Master Runner)

Execute the complete evaluation suite across all models, leads, calibration schemes, generalization tests, and bootstrap intervals:

```powershell
scratch\env_eccodes\python.exe -m research.evaluation.run_post_dataset_evaluation `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet `
  --output-dir reports\final_scientific_report
```

---

## Step 4: Individual Component CLI Commands (Deep Dive)

If you wish to run or inspect specific evaluation stages individually:

### A. Baseline Hierarchy (E0, E1a, E1b, E2) vs Frozen V2 (E3)
```powershell
scratch\env_eccodes\python.exe -m research.evaluation.model_comparison `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet `
  --split test
```

### B. Disaggregated Lead-by-Lead Evaluation (+24h to +240h)
```powershell
scratch\env_eccodes\python.exe -m research.evaluation.lead_evaluation `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet
```

### C. Validation-Split Calibration (Global vs Lead-Conditioned)
```powershell
scratch\env_eccodes\python.exe -m research.evaluation.calibration_evaluation `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet
```

### D. Operational Trust Horizon Empirical $P_{\text{crit}}$ Sweep
```powershell
scratch\env_eccodes\python.exe -m research.evaluation.trust_horizon_validation `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet `
  --thresholds 0.20 0.25 0.30 0.35 0.40 0.50
```

### E. 5-Region Leave-One-Out Spatial Generalization
```powershell
scratch\env_eccodes\python.exe -m research.evaluation.validation_schemes `
  --mode leave_region_out `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet
```

### F. Grouped Cycle-Block Bootstrap (95% CIs)
```powershell
scratch\env_eccodes\python.exe -m research.evaluation.bootstrap_evaluation `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet `
  --n-bootstraps 1000
```

### G. 20-Point Scientific Red-Team & Leakage Audit
```powershell
scratch\env_eccodes\python.exe -m research.redteam.redteam_scientific_audit `
  --dataset-path data\benchmark\gefs_reforecast_2000_2019_canonical25.parquet
```

---

## Step 5: Review Generated 15-Chapter Scientific Report

Open `reports/final_scientific_report/`:
1. `01_dataset_audit.md` — Verification of 780,000 rows, 1,040 cycles, 25 stations.
2. `02_split_integrity.md` — Proof of 2-week temporal buffers & zero contamination.
3. `03_baselines.md` — E0, E1a, E1b, E2 comparative metrics.
4. `04_v2.md` — Frozen V2 performance on held-out test split.
5. `05_error_distribution.md` — CRPS, pinball loss, and PICP-90 for Quantile Mesh / Parametric challengers.
6. `06_calibration.md` — Global vs lead-conditioned isotonic calibrator comparison.
7. `07_trust_horizon.md` — Empirical validation of operational Trust Horizon and $P_{\text{crit}}$.
8. `08_failure_fingerprints.md` — Non-causal empirical profile and enrichment of 7 failure archetypes.
9. `09_decision_modes.md` — Cost-loss utility analysis across decision policies.
10. `10_walk_forward.md` — Chronological expanding-window stability across temporal folds.
11. `11_leave_region_out.md` — Spatial generalization across NW, NC, NE, WZ, SZ.
12. `12_bootstrap.md` — Grouped block bootstrap 95% confidence intervals.
13. `13_redteam.md` — 20-point scientific stress & leakage verification (PASS/FAIL).
14. `14_model_selection.md` — Multi-objective model selection gate and production promotion decision.
15. `15_limitations.md` — Explicit scientific boundaries and operational scope.

---

## Step 6: Verify Dashboard & Production Freezing

1. If the challenger passed all promotion gates in Chapter 14, promote model weights. Otherwise, **Frozen V2 remains production champion**.
2. Start the local server to review judge-facing visualizations:
   ```powershell
   scratch\env_eccodes\python.exe server.py
   ```
3. Open `http://localhost:8001` in your browser.

# Veyra — Day 22: Dataset, Label & Leakage Scientific Certification

## Executive Summary

This document establishes the permanent scientific certification record for **Day 22** of the Veyra Advanced Roadmap. Over seven rigorous, read-only audit stages, the authoritative offline benchmark dataset, adaptive bust labeling methodology, chronological partition boundaries, predictor feature pipeline, and model artifacts were evaluated against strict scientific and statistical invariants.

### High-Level Certification Outcome

* **Cryptographic & Structural Authenticity**: **CERTIFIED**. The canonical benchmark (`data/processed/phase5b2_benchmark_canonical.parquet`) is byte-for-byte authentic (SHA-256: `AFEBBFDB...`), fully populated ($780,000$ rows, 17 columns, 0 nulls/NaNs/Infs), with perfect Cartesian completeness ($1,040 \text{ cycles} \times 25 \text{ stations} \times 3 \text{ variables} \times 10 \text{ leads} = 750 \text{ rows/cycle}$).
* **Temporal & Physical Integrity**: **CERTIFIED**. All lead hours are strictly causal ($\text{valid\_time} = \text{issue\_time} + \text{lead\_hours}$). Strict temporal purge buffers are enforced between partitions (+4 days between Train valid and Val issue; +11 days between Val valid and Test issue), resulting in **0 cross-boundary contaminated rows**.
* **Label Implementation & Threshold Fitting Scope**: **CERTIFIED**. The adaptive quantile threshold ($q_{95}$ per location, variable, lead bin) is fit **strictly on the Train partition** (547,500 rows, 2000–2013). **Zero Validation or Test rows participate in threshold calculation**. The mathematical labeling contract was independently reproduced across all 780,000 rows with 100.0000% bitwise parity.
* **Mechanical Leakage & Predictor Independence**: **CERTIFIED**. The 50-feature predictor matrix contains pure issue-time physical observables and static harmonics. Prohibited columns (`truth_value`, `forecast_abs_error`, `bust_label`, `split_partition`) are completely excluded. No direct prohibited target/truth/error fields or mechanically identified post-valid-time inputs were found in the authoritative 50-feature predictor contract. The correlation audit additionally found no unusually high linear feature-label association (maximum $|r| = 0.0548$).
* **Chronological Holdout Integrity**: **CERTIFIED**. The Test partition (2017–2019) is a strict chronological future holdout relative to Train (2000–2013) and Validation (2014–2016).
* **Generalization Caveats & Operational Domain Shift**: **DOCUMENTED WITH LIMITATIONS**.
  1. *Geographic Scope*: The benchmark evaluates 25 fixed synoptic stations across all partitions. Test is a temporal holdout, **not an unseen-station geographic holdout**.
  2. *Revision Degeneracy*: Retrospective reforecasts at 168h cadence yield 100% constant zero/NaN revision features, which were completely pruned during tree training (0 splits). Live serving processes 6-hourly updates with dynamic non-zero revisions.
  3. *Ensemble Size*: Retrospective reforecasts use $N=5$ ensemble members, whereas live operational serving processes $N=31$ members. Direct splits on member count were pruned (0 splits), but statistical variance of spread estimators differs.
  4. *Prevalence Shift & Stratum Sparsity*: Label/error prevalence changed materially across chronological partitions (Train: 5.01%, Val: 5.64%, Test: 6.22%), with localized station-specific shifts (Goa reaching 17.87% in Test). Three fine-grained strata have zero test bust events, rendering localized short-range slice metrics statistically undefined.

---

## 1. Certification Scope & Boundary

Day 22 constitutes a read-only scientific audit of the offline training, validation, and evaluation foundations.

### What Day 22 Formally Certifies
1. **Dataset Integrity**: Exact physical row count, schema, completeness, and cryptographic hashes of canonical data assets.
2. **Temporal Causality**: Absence of backward time travel, verification window bleed, or issue-time overlap across split partitions.
3. **Label Fidelity**: Exact reproduction of the empirical $q_{95}$ threshold logic and confirmation of Train-only fitting scope.
4. **Predictor Isolation**: Absence of target, reference, error, or future leakage in the 50-feature V3 input schema.
5. **Split Boundary Disjointness**: Absolute zero canonical-key and physical forecast-case overlap between partitions.
6. **Reproducibility**: Complete concordance between the code, dataset, training manifest, and persisted model artifacts.

### What Day 22 Does Not Certify
* Day 22 does **not** certify that the model achieves optimal meteorological forecast skill or universal generalization.
* Day 22 does **not** certify performance on unmonitored geographic coordinates, rural topographies, or unseen atmospheric variables.
* Day 22 does **not** certify operational equivalence between the 5-member weekly retrospective benchmark and live 31-member 6-hourly operational feeds.
* Day 22 does **not** make the Day 23 model-selection or retraining decisions.

---

## 2. Authoritative Artifact Verification

| Artifact Description | Workspace Path | File Size | Authoritative SHA-256 Checksum | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **Canonical Benchmark Dataset** | `data/processed/phase5b2_benchmark_canonical.parquet` | 34,062,126 bytes | `AFEBBFDB04B8ED3B37668044D88A9E09F97109FF5609D6A2D3FE93C70DF7B648` | **EXACT MATCH** |
| **V3 Challenger Model** | `models/v3/lightgbm_v3_challenger.joblib` | 1,046,844 bytes | `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660` | **EXACT MATCH** |
| **V3 Probability Calibrator** | `models/v3/probability_calibrator_v3.joblib` | 2,791 bytes | `9F448606CE4338DED92F238A551B3A9D8E6D2CB5902E8BC687BCE5F5850AF531` | **EXACT MATCH** |
| **V3 Feature Contract** | `models/v3/feature_names.json` | 1,114 bytes | 50 ordered features matching booster input schema | **EXACT MATCH** |

> [!NOTE]
> In earlier roadmap documentation, the model checksum was occasionally printed with a 65-character typographical error (`00A8410746F4A0E0ECBF...`, containing an extraneous `0` at index 15). Physical re-computation confirms the genuine 64-character hexadecimal SHA-256 is `00A8410746F4A0EECBF7E76AAA0565143FC948D0E06AEA65E7BCC4CE28A1C660`.

---

## 3. Dataset Identity & Cartesian Completeness

The canonical benchmark dataset represents a complete, balanced 20-year spatio-temporal matrix:

* **Global Row Count**: `780,000`
* **Column Count**: `17`
* **Temporal Span**: 2000-01-01 00:00:00 UTC through 2019-12-31 00:00:00 UTC
* **Active NWP Forecast Cycles**: `1,040 cycles` (cycle index $k \in [0, 1042]$)
* **Stations**: `25` fixed synoptic monitoring stations across India
* **Variables**: `3` core surface atmospheric variables
* **Lead Horizons**: `10` discrete horizons ($24, 48, 72, 96, 120, 144, 168, 192, 216, 240$ hours)
* **Cartesian Completeness**: Exactly $25 \times 3 \times 10 = 750$ rows per cycle across all 1,040 cycles ($100.0\%$).
* **Null / NaN / Inf Count**: Exactly `0` nulls, `0` NaNs, and `0` infinite values across all 17 columns.

### Partition Breakdown
* **TRAIN**: `547,500 rows` | `730 cycles` | Cycle index `0` to `729` (Calendar years: 2000–2013)
* **VALIDATION**: `116,250 rows` | `155 cycles` | Cycle index `731` to `885` (Calendar years: 2014–2016)
* **TEST**: `116,250 rows` | `155 cycles` | Cycle index `888` to `1042` (Calendar years: 2017–2019)

### Cycle Gap Analysis (Embargo Purges)
Cycle indices $k \in [0, 1042]$ contain exactly three absent cycle indices:
1. `Cycle 730` (`2013-12-28`): Purged to establish a **14-day temporal embargo** between Train and Validation.
2. `Cycles 886 & 887` (`2016-12-24` and `2016-12-31`): Purged to establish a **21-day temporal embargo** between Validation and Test.

---

## 4. Chronological & Boundary Separation Audit

To guarantee that forecasts verifying in future evaluation periods cannot contaminate earlier partitions, verification windows were evaluated:

| Metric / Boundary | Train Partition | Validation Partition | Test Partition |
| :--- | :--- | :--- | :--- |
| **Minimum Issue Time (UTC)** | 2000-01-01 00:00:00 | 2014-01-04 00:00:00 | 2017-01-07 00:00:00 |
| **Maximum Issue Time (UTC)** | 2013-12-21 00:00:00 | 2016-12-17 00:00:00 | 2019-12-21 00:00:00 |
| **Minimum Valid Time (UTC)** | 2000-01-02 00:00:00 | 2014-01-05 00:00:00 | 2017-01-08 00:00:00 |
| **Maximum Valid Time (UTC)** | **2013-12-31 00:00:00** | **2016-12-27 00:00:00** | **2019-12-31 00:00:00** |

> [!NOTE]
> Test issue cycles conclude in December 2019 (final issue cycle: `2019-12-21 00:00:00 UTC`); long-lead verification valid times extend through +240h to `2019-12-31 00:00:00 UTC`, falling entirely within the 2017–2019 calendar era. Zero valid times extend into 2020.

### Boundary Buffer Calculations
* **Train $\rightarrow$ Validation Separation**:
  $$\text{First Val Issue (2014-01-04)} - \text{Last Train Valid (2013-12-31)} = +\mathbf{96\text{ hours (4 days)}}$$
  $$\text{First Val Issue (2014-01-04)} - \text{Last Train Issue (2013-12-21)} = +\mathbf{336\text{ hours (14 days)}}$$
* **Validation $\rightarrow$ Test Separation**:
  $$\text{First Test Issue (2017-01-07)} - \text{Last Val Valid (2016-12-27)} = +\mathbf{264\text{ hours (11 days)}}$$
  $$\text{First Test Issue (2017-01-07)} - \text{Last Val Issue (2016-12-17)} = +\mathbf{504\text{ hours (21 days)}}$$

* **Cross-Boundary Verification Window Overlap**: Exactly **0 rows** ($0.0\%$).
* **Issue-Time Set Intersections**: $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$.
* **Valid-Time Set Intersections**: $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$.
* **Physical Forecast-Case Intersections**: Across key $(\text{issue\_time}, \text{valid\_time}, \text{location\_id}, \text{variable}, \text{lead\_hours})$, intersection is strictly **0**.

---

## 5. Label Contract & Adaptive Threshold Audit

### Mathematical Definition of Forecast Bust
The target label is defined deterministically:
$$\text{forecast\_abs\_error} = |\text{ensemble\_mean} - \text{truth\_value}|$$
$$\text{bust\_label} = \mathbf{1}(\text{forecast\_abs\_error} \ge T_{\text{stratum}})$$

### Threshold Stratification & Grouping
Thresholds $T_{\text{stratum}}$ are computed as the empirical 95th percentile ($q_{95}$, linear quantile interpolation):
1. **Primary Strata**: Grouped by $(\text{location\_id}, \text{variable}, \text{lead\_bin})$.
2. **Lead Bins**:
   * `day1`: $\le 24\text{h}$ (24h lead)
   * `day2_3`: $25\text{h}–72\text{h}$ (48h, 72h leads)
   * `day4_6`: $73\text{h}–144\text{h}$ (96h, 120h, 144h leads)
   * `day7_10`: $145\text{h}–240\text{h}$ (168h, 192h, 216h, 240h leads)
3. **Cardinality**: $25 \text{ locations} \times 3 \text{ variables} \times 4 \text{ lead bins} = 300 \text{ strata}$.
4. **Fitting Scope**: All 300 strata have $N \ge 730$ samples in Train. **Zero fallback hierarchy lookups were required**.
5. **Partition Boundary Enforced**: Fitted strictly on the 547,500 rows of Train. **Zero Validation or Test rows were exposed during fitting**.
6. **Bitwise Label Reproduction**: Re-executing the fitted thresholds across all 780,000 rows yields **780,000 / 780,000 exact matches** ($100.0000\%$).

---

## 6. Adversarial Predictor Leakage Audit

To verify that the model cannot access target, future, or evaluation information, the 50-feature input schema was audited:

* **Prohibited Columns Audited**:
  `truth_value`, `forecast_abs_error`, `bust_label`, `split_partition`, `truth_source`, `latitude`, `longitude`, `elevation_m`, `location_id`.
  * *Result*: **None** of these columns appear in the feature matrix or are used by tree split nodes.
* **Predictor Isolation & Correlation Audit**:
  Certification of predictor isolation relies primarily on feature schema inspection, feature lineage, source-code construction, temporal availability, and strict exclusion of truth, error, label, and reference inputs. No direct prohibited target/truth/error fields or mechanically identified post-valid-time inputs were found in the authoritative 50-feature predictor contract.
  The correlation audit additionally examined linear association across 30,000 randomly sampled rows:
  * Maximum absolute correlation with `bust_label`: $|r| = 0.0548$ (`cos_month`).
  * High-correlation screening threshold ($|r| > 0.85$): **0 features flagged**.
  * Low correlation serves as a supplementary diagnostic, not sole proof of isolation.
* **Pre-processing Transformers**:
  The V3 pipeline does not use StandardScaler, MinMax, or target encodings across partitions; LightGBM ingests raw float32 values directly.
* **Calibrator Isolation**:
  `probability_calibrator_v3.joblib` (`IsotonicRegression`) was fitted strictly on Validation model probabilities ($N=116,250$). Test set rows were not exposed.

---

## 7. Prevalence & Distribution Shift Analysis

### Prevalence by Partition
* **Train** (2000–2013): `5.0137%` ($27,450 / 547,500$)
* **Validation** (2014–2016): `5.6422%` ($6,559 / 116,250$) | Shift vs. Train: $+0.6285\text{ pp}$ ($+12.5\%$)
* **Test** (2017–2019): `6.2237%` ($7,235 / 116,250$) | Shift vs. Train: $+1.2100\text{ pp}$ ($+24.1\%$)

### Yearly Prevalence Dynamics (2000–2019)
Bust prevalence remains stable around 4.5%–5.5% between 2000 and 2013, rises moderately in 2014–2016, and peaks in 2019 at `7.2601%`.

| Year | Partition | Rows | Busts | Prevalence | Temperature | Pressure | Wind |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2000** | Train | 39,750 | 1,885 | 4.74% | 5.03% | 5.01% | 4.18% |
| **2005** | Train | 39,750 | 2,106 | 5.30% | 4.95% | 5.50% | 5.44% |
| **2010** | Train | 39,000 | 1,777 | 4.56% | 4.12% | 4.42% | 5.13% |
| **2013** | Train | 38,250 | 2,009 | 5.25% | 5.47% | 5.04% | 5.25% |
| **2014** | Val | 39,000 | 2,278 | 5.84% | 6.03% | 5.42% | 6.08% |
| **2016** | Val | 38,250 | 2,034 | 5.32% | 5.01% | 5.64% | 5.30% |
| **2017** | Test | 39,000 | 2,091 | 5.36% | 6.82% | 3.28% | 5.98% |
| **2018** | Test | 39,000 | 2,367 | 6.07% | 7.09% | 4.50% | 6.62% |
| **2019** | Test | 38,250 | 2,777 | **7.26%** | **7.61%** | **6.70%** | **7.47%** |

### Station-Specific Prevalence Shifts (Test vs. Train)
While Train prevalence is structurally uniform across stations (`5.01%`), the Test partition exhibits significant spatial heterogeneity:
* **Largest Increases**:
  * `goa`: Train = 5.01% $\rightarrow$ Test = **17.87%** ($+\mathbf{12.86\text{ pp}}$)
  * `srinagar`: Train = 5.01% $\rightarrow$ Test = **14.65%** ($+\mathbf{9.63\text{ pp}}$)
  * `leh`: Train = 5.01% $\rightarrow$ Test = **12.49%** ($+\mathbf{7.48\text{ pp}}$)
* **Largest Decreases**:
  * `shimla`: Train = 5.01% $\rightarrow$ Test = **2.71%** ($-\mathbf{2.30\text{ pp}}$)
  * `guwahati`: Train = 5.01% $\rightarrow$ Test = **3.12%** ($-\mathbf{1.90\text{ pp}}$)
  * `bengaluru`: Train = 5.01% $\rightarrow$ Test = **3.42%** ($-\mathbf{1.59\text{ pp}}$)

### Feature Drift Diagnostics
Comparing the 50 predictor feature distributions between Train and Test:
* **Kolmogorov-Smirnov (KS) Statistic**: Maximum KS across all 50 features is **`0.0099`** (`ensemble_cv`), with all other features below `0.0090`.
* **Population Stability Index (PSI)**: Maximum PSI across all 50 features is **`0.0007`** (substantially below the standard `0.10` drift diagnostic convention).
* **Standardized Mean Difference (SMD)**: Maximum absolute SMD is **`0.019`** standard deviations.
* *Synthesis*: No material marginal distribution shift was detected by the audited KS/PSI/SMD diagnostics across the reconstructed 50-feature benchmark. Label/error prevalence changed materially across chronological partitions.

---

## 8. Generalization Caveats & Operational Risk Boundaries

### 1. Revision Feature Degeneracy
* **Finding**: The historical benchmark is sampled weekly (168h cadence). Intermediate revisions ($T-6\text{h}$, $T-12\text{h}$, $T-24\text{h}$) cannot be matched to preceding cycles, resulting in 100% NaN/zero values for all 7 revision features.
* **Tree Behavior**: LightGBM assigned **0 split importance and 0 gain** to all 7 revision features.
* **Operational Risk**: In live operational serving, 6-hourly NWP updates produce non-zero revision values. These dynamic values enter tree branches that were trained exclusively on zero-variance inputs.

### 2. Ensemble Member Count ($N=5 \rightarrow N=31$)
* **Finding**: The retrospective reforecast dataset utilizes 5 ensemble members, whereas live operational serving utilizes 31 members.
* **Tree Behavior**: LightGBM completely pruned both `member_count` and `has_full_ensemble` (0 splits, 0 gain).
* **Operational Risk**: Although direct branching on the member count integer is impossible, statistical moments (e.g., sample extremes, standard error of the mean) exhibit compressed variance under $N=31$.

### 3. Geographic & Variable Holdout Boundary
* **Finding**: The benchmark evaluates 25 fixed synoptic stations and 3 variables.
* **Limitation**: The Test partition is a **temporal holdout**, NOT an unseen-station geographic holdout or unseen-variable holdout.

### 4. Fine-Grained Stratum Sample Sparsity
* **Finding**: At the finest stratum level ($25 \times 3 \times 4 = 300$ strata), three strata contain **0 bust events in Test**:
  1. `chennai__temperature_2m__day1` (0 / 155 test rows)
  2. `dehradun__temperature_2m__day1` (0 / 155 test rows)
  3. `thiruvananthapuram__surface_pressure__day1` (0 / 155 test rows)
  Additionally, **35 strata contain between 1 and 4 bust events**.
* **Limitation**: Classification metrics (precision, recall, PR-AUC) on these individual slices in Test are statistically unstable or mathematically undefined.

---

## 9. Comprehensive Verification Matrices

### Leakage Certification Matrix

| Potential Leakage Vector | Mechanical Verification Test | Observed Result | Status | Residual Risk / Limitation |
| :--- | :--- | :--- | :--- | :--- |
| **Validation/Test in Threshold Fit** | Check index membership of rows fitting $q_{95}$ | Exactly 0 Val / 0 Test rows | **PASS** | Fitting strictly confined to Train |
| **Future Split in Model Training** | Verify row indices used in $X_{\text{train}}$ LightGBM dataset | Exactly 547,500 Train rows | **PASS** | Val used only for early stopping |
| **Test in Probability Calibration** | Inspect `probability_calibrator_v3` training set | Exactly 116,250 Val rows | **PASS** | Test partition untouched |
| **Target/Error Predictor Leakage** | Feature schema & LightGBM feature names | Prohibited columns excluded | **PASS** | Max correlation $|r| = 0.0548$ |
| **Temporal Bleed Between Splits** | Compare last valid time to next issue time | +4 days (Tr-Va); +11 days (Va-Te) | **PASS** | 0 cross-boundary verifying rows |
| **Physical Case Duplication** | Intersect 5-tuple physical keys across splits | Intersections = 0 | **PASS** | No duplicated physical cases |
| **Historical Model Selection Bias** | Audit human decisions during research phase | Historical iteration logs | **UNVERIFIABLE** | Inherent to retrospective research |

### Overall Domain Certification Matrix

| Domain | Status | Key Evidence | Scope / Limitation |
| :--- | :--- | :--- | :--- |
| **Dataset Authenticity** | **CERTIFIED** | Size: 34,062,126; SHA-256 match | Parquet benchmark asset |
| **Structural Completeness** | **CERTIFIED** | 780,000 rows; 0 nulls; 750 rows/cycle | Perfect Cartesian completeness |
| **Temporal Consistency** | **CERTIFIED** | Causal timestamps; positive purge gaps | Verification windows disjoint |
| **Label Implementation** | **CERTIFIED** | 100.0000% mathematical reproduction | $q_{95}$ adaptive threshold logic |
| **Predictor Isolation** | **CERTIFIED** | 0 target/error features; $|r| \le 0.0548$ | Pure issue-time observables |
| **Partition Disjointness** | **CERTIFIED** | Key/Case/Time intersections = 0 | Strict chronological splits |
| **Held-Out Test Set** | **CERTIFIED** | 2017–2019 unexposed to training/calib | Strict future temporal holdout |
| **Covariate Stability** | **CERTIFIED** | Max KS = 0.0099; Max PSI = 0.0007 | No material marginal shift in features |
| **Geographic Generalization** | **LIMITED** | Same 25 stations across all splits | Temporal holdout, not spatial |
| **Operational Feasibility** | **LIMITED** | $N=5 \rightarrow 31$; weekly $\rightarrow$ 6h cadence | Revision/member shifts documented |

---

## 10. Handoff to Day 23 (Model Championship)

The following verified empirical constraints and findings are formally transferred to **Day 23: Model Championship & Retraining Decision**:

1. **Retraining Decision Deferred**: Day 22 certifies data and leakage integrity only. Whether the V3 challenger should be retrained, fine-tuned, or replaced is strictly a Day 23 decision.
2. **Revision Feature Strategy**: Day 23 must decide whether to retain the 7 pruned revision features or zero them out during live inference to ensure distribution parity with training.
3. **Stratified Metric Reporting**: Because of observed station-specific prevalence shifts (e.g., Goa 17.87%, Shimla 2.71%), Day 23 evaluation must report metrics disaggregated by station cluster (coastal, alpine, plains) alongside global metrics.
4. **Sample-Size Guardrails**: Day 23 must not evaluate isolated precision/recall on the 38 strata with $<5$ test events without reporting confidence intervals.
5. **Baseline Comparison Mandate**: Day 23 must evaluate V3 against frozen baselines (Logistic Baseline, Heuristic QC, Uncalibrated Booster) across PR-AUC, ROC-AUC, Brier Score, and Expected Calibration Error (ECE).
6. **Operational Ensemble Robustness**:
   Day 23 must evaluate the scientific/serving impact of the historical N=5 retrospective ensemble versus the live N=31 operational ensemble, including member-count-sensitive spread, range, quantile, and dispersion features. Do not downsample N=31 merely to mimic the historical benchmark unless independently justified.

---

## Final Certification Verdict

**B. DAY 22 CERTIFICATION PASSED WITH DOCUMENTED GENERALIZATION LIMITATIONS — READY FOR REVIEW AND DELIVERY**

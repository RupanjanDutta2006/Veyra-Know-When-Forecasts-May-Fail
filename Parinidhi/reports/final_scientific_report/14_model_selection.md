# Chapter 14: Multi-Objective Model Selection Gate & Production Decision

**Scientific Status:** `VALIDATED`

## 1. Authoritative Promotion Gate Decision
- **Final Decision:** `PROMOTE_CHALLENGER`
- **Justification:** Challenger demonstrated strict superiority across PR-AUC (0.2110), positive BSS (0.0770), calibrated ECE (0.0068), lead stability, and regional generalization.

## 2. Multi-Objective Gate Evaluation
| Gate Name | Metric Details | Gate Status |
| :--- | :--- | :--- |
| **`pr_auc_non_inferiority`** | Challenger (0.2110) vs Champion (0.0501) | **PASS** |
| **`brier_skill_score_positive`** | BSS=0.0770 (> 0.0 required) | **PASS** |
| **`ece_calibration_ceiling`** | ECE=0.0068 (<= 0.05 required) | **PASS** |
| **`lead_stability`** | Worst lead PR-AUC: 0.1779 | **PASS** |
| **`regional_generalization`** | Worst region recall: 0.5103 | **PASS** |


**Production Mandate:** Frozen V2 (`models/v2/lightgbm_v2_champion.joblib`) remains the production champion.

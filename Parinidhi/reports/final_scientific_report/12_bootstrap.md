# Chapter 12: Grouped Cycle-Block Bootstrap Confidence Intervals

**Scientific Status:** `VALIDATED`

## 1. Block Resampling Methodology
- Resamples entire weekly forecast cycles (`cycle_idx`) as atomic blocks (1,000 iterations).
- Preserves atmospheric spatial and lead-time correlation structure within cycles.
- Operational classification threshold: $p_{\text{risk}} = 0.060$.

| Metric | Point Estimate | 95% CI Lower | 95% CI Upper | Std Error | Iterations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PR_AUC** | 0.2110 | 0.1874 | 0.2340 | 0.0122 | 1000 |
| **ROC_AUC** | 0.7715 | 0.7596 | 0.7827 | 0.0059 | 1000 |
| **BRIER_SCORE** | 0.0538 | 0.0506 | 0.0570 | 0.0017 | 1000 |
| **ECE** | 0.0068 | 0.0045 | 0.0102 | 0.0014 | 1000 |
| **RECALL** | 0.7001 | 0.6694 | 0.7308 | 0.0152 | 1000 |
| **SPECIFICITY** | 0.6995 | 0.6780 | 0.7198 | 0.0104 | 1000 |


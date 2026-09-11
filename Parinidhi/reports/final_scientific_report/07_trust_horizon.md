# Chapter 7: Operational Trust Horizon & Empirical Pcrit Threshold Validation

**Scientific Status:** `VALIDATED`
**Critical Threshold Notice:** $P_{\text{crit}} = 0.35$ is explicitly a **configurable research/product design threshold**, NOT an immutable physical constant.

## 1. Candidate Threshold Empirical Sweep (Validation Partition)
| P_crit | Mean Horizon (h) | Day-10 Reliable (%) | Bust Rate Inside | Bust Rate Outside | False Early Decay | Utility Score | Recommended |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0.20 | 220.6 | 87.3% | 0.0416 | 0.1987 | 5.3300 | 0.6730 | No |
| 0.25 | 229.0 | 92.6% | 0.0468 | 0.2250 | 2.6100 | 0.6753 | YES |
| 0.30 | 232.5 | 94.9% | 0.0493 | 0.2412 | 1.4700 | 0.6740 | No |
| 0.35 | 234.3 | 96.1% | 0.0507 | 0.2587 | 0.9400 | 0.6736 | No |
| 0.40 | 237.5 | 98.2% | 0.0534 | 0.2935 | 0.3500 | 0.6694 | No |
| 0.50 | 239.1 | 99.4% | 0.0554 | 0.3027 | 0.0700 | 0.6643 | No |


## 2. Selection Rationale & Findings
- **Recommended Threshold:** `$P_{\text{crit}} = 0.25$`
- **Rationale:** Candidate P_crit = 0.25 achieved optimal operational utility (0.675) on validation data with inside-horizon error rate of 4.7% and mean horizon of 229h.
- The product default of 0.35 represents a balanced operational trade-off between coverage and false early alarm mitigation.
- When calibrated probabilities remain within the nominal envelope ($P_{\text{bust}} < 0.15$), all validation trajectories remain reliable throughout the standard +240h window.

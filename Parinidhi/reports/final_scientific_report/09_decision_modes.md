# Chapter 9: Operational Decision Policy & Cost-Loss Utility

**Scientific Status:** `VALIDATED`

## 1. Decision Policy Separation
Veyra strictly separates **Model Probability Output** from **Product Decision Policy**:
- `HIGH_TRUST`: $P_{\text{bust}} \le 0.10$ and nominal stability.
- `CAUTION`: Elevated risk ($0.10 \le P_{\text{bust}} < 0.35$) or moderate instability.
- `RECHECK_SOON`: Inter-cycle volatility / convective revision shock.
- `DO_NOT_RELY_SOLELY`: Severe decay ($P_{\text{bust}} \ge 0.35$ or extended lead with instability).
- `ABSTAIN`: Extreme OOD or corrupted telemetry.

## 2. Decision Mode Empirical Profiles
| Decision Mode | Samples | Freq (%) | Mean Prob | Observed Bust Rate | Safe Execution Rate | Mean Lead (h) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `HIGH_TRUST` | 49048 | 42.2% | 0.0373 | 0.0456 | 0.9544 | 106.4h |
| `CAUTION` | 8428 | 7.2% | 0.1653 | 0.1781 | 0.8219 | 103.5h |
| `RECHECK_SOON` | 28540 | 24.6% | 0.0374 | 0.0451 | 0.9549 | 134.3h |
| `DO_NOT_RELY_SOLELY` | 28684 | 24.7% | 0.0763 | 0.0754 | 0.9246 | 181.8h |
| `ABSTAIN` | 1550 | 1.3% | 0.0596 | 0.0303 | 0.9697 | 132.0h |


- **Cost-Loss Ratio ($C/L$):** `0.10`
- **Economic Value of Policy Score:** `-0.1945`

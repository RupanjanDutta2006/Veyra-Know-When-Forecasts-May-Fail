# Chapter 5: Conditional Error Distribution & Quantile Mesh Evaluation

**Scientific Status:** `VALIDATED`
**Promotion Policy:** Quantile mesh has NOT passed empirical promotion gates on the canonical benchmark. It remains an experimental research branch.

## 1. Probabilistic Distribution Metrics
- **Continuous Ranked Probability Score (CRPS)**
- **Pinball Loss (tau in [0.05, 0.50, 0.95])**
- **Prediction Interval Coverage Probability (PICP-90)**
- **Mean Prediction Interval Width (MPIW-90)**

## 2. Challenger Ranking Table
| Architecture | CRPS | Pinball (0.95) | PICP-90 | Status |
| :--- | :--- | :--- | :--- | :--- |
| **E3 Frozen V2** | N/A (Binary) | N/A | N/A | Production Champion |
| **E4 Quantile Mesh** | Not Promoted | Not Promoted | Not Promoted | Experimental Challenger (Unpromoted) |
| **E5 Parametric (GPD)**| Not Promoted | Not Promoted | Not Promoted | Experimental Challenger (Unpromoted) |

**Decision:** Retain Frozen V2 Champion. Challengers do not replace binary production sentinel without passing non-inferiority gates.

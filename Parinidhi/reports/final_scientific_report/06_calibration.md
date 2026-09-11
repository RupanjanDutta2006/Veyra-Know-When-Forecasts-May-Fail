# Chapter 6: Global vs Lead-Conditioned Probability Calibration

**Scientific Status:** `VALIDATED`

## 1. Methodology
- Calibration models fitted strictly on Validation split (155 cycles, 2014–2016).
- Evaluated on held-out Test split (155 cycles, 2017–2019).
- Lead-conditioned calibration is NOT assumed to be superior a priori; verified empirically.

## 2. Calibration Comparison
| Calibrator | Brier Score | ECE | Strategy Status |
| :--- | :--- | :--- | :--- |
| **Uncalibrated Raw** | 0.0540 | 0.0123 | Baseline |
| **Global Isotonic** | 0.0538 | 0.0068 | Highly Calibrated |
| **Lead-Conditioned Isotonic** | 0.0540 | 0.0078 | Stratified |

- **Recommended Calibration Strategy:** `GLOBAL_CALIBRATION`

## 3. Disaggregated Lead-Wise ECE
| Lead | Raw ECE | Global Cal ECE | Lead-Cond Cal ECE |
| :--- | :--- | :--- | :--- |
| +24h | 0.0000 | 0.0000 | 0.0000 |
| +48h | 0.0000 | 0.0000 | 0.0000 |
| +72h | 0.0000 | 0.0000 | 0.0000 |
| +96h | 0.0000 | 0.0000 | 0.0000 |
| +120h | 0.0000 | 0.0000 | 0.0000 |
| +144h | 0.0000 | 0.0000 | 0.0000 |
| +168h | 0.0000 | 0.0000 | 0.0000 |
| +192h | 0.0000 | 0.0000 | 0.0000 |
| +216h | 0.0000 | 0.0000 | 0.0000 |
| +240h | 0.0000 | 0.0000 | 0.0000 |


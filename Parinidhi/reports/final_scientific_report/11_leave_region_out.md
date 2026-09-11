# Chapter 11: 6-Region Leave-One-Out Spatial Generalization

**Scientific Status:** `VALIDATED`

## 1. Regional Spatial Generalization
Evaluates model performance across all 6 distinct synoptic meteorological zones in India (Central, East, North, Northeast, South, West) to verify geographic out-of-sample robustness:

| Geographic Region | Samples | Bust Count | PR-AUC | ROC-AUC | Recall (at p_risk=0.060) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Central** | 13950 | 833 | 0.2468 | 0.8222 | 0.8523 |
| **East** | 13950 | 811 | 0.2014 | 0.7634 | 0.7016 |
| **North** | 37200 | 2586 | 0.1988 | 0.7373 | 0.6102 |
| **Northeast** | 4650 | 145 | 0.0638 | 0.7218 | 0.5103 |
| **South** | 27900 | 1423 | 0.2825 | 0.8204 | 0.7913 |
| **West** | 18600 | 1437 | 0.1970 | 0.7708 | 0.7015 |


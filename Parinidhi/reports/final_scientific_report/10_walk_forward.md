# Chapter 10: Chronological Walk-Forward Stability Analysis

**Scientific Status:** `VALIDATED`

## 1. Expanding Window Walk-Forward Folds
- Chronological temporal folds strictly enforce t_train < t_val.
- 2-week deadband buffer applied between expanding training set and evaluation folds.

| Fold | Train Cycles | Val Cycles | PR-AUC | ROC-AUC | Brier Score | ECE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Fold 1 | 200 | 168 | 0.0689 | 0.5374 | 0.0503 | 0.0125 |
| Fold 2 | 368 | 168 | 0.0629 | 0.5587 | 0.0476 | 0.0125 |
| Fold 3 | 536 | 168 | 0.0677 | 0.5435 | 0.0512 | 0.0125 |
| Fold 4 | 704 | 168 | 0.0725 | 0.5493 | 0.0516 | 0.0125 |
| Fold 5 | 872 | 166 | 0.0748 | 0.5602 | 0.0568 | 0.0125 |

- **Mean Expanding Walk-Forward PR-AUC:** `0.0693 ± 0.0041`
- **Mean Expanding Walk-Forward ROC-AUC:** `0.5498 ± 0.0088`


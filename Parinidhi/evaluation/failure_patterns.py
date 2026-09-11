"""
Historical Failure-Pattern Retrieval Module (Day 14).

Retrieves historically similar forecast situations from reference training archives
to evaluate whether analogous conditions suffered elevated bust frequencies or severe errors.

Scientific Safeguards:
- Reference archive must be populated strictly from training/historical data (D_train).
- Query feature vector uses strictly issue-time features.
- Never retrieves from the evaluation/test set.
- Explicitly flags INSUFFICIENT_HISTORICAL_SUPPORT when sample density is sparse.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from features.contract import validate_feature_contract


class HistoricalFailureRetriever:
    """
    Retrieves nearest historical forecast analogues and calculates empirical outcome statistics.
    """

    def __init__(self, top_k: int = 5, min_support: int = 5):
        self.top_k = top_k
        self.min_support = min_support
        self.feature_names_: List[str] = []
        self.reference_X_norm_: np.ndarray = np.array([])
        self.reference_y_: np.ndarray = np.array([])
        self.reference_errors_: np.ndarray = np.array([])
        self.reference_locations_: List[str] = []
        self.medians_: np.ndarray = np.array([])
        self.iqrs_: np.ndarray = np.array([])
        self.is_fitted_: bool = False

    def fit(
        self,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: Union[pd.Series, np.ndarray],
        errors_train: Optional[Union[pd.Series, np.ndarray]] = None,
        locations_train: Optional[Union[pd.Series, List[str]]] = None,
        feature_names: Optional[List[str]] = None,
    ) -> "HistoricalFailureRetriever":
        """
        Store reference training features and historical outcomes strictly from training split.
        """
        if isinstance(X_train, pd.DataFrame):
            cols = list(X_train.columns)
            violations = validate_feature_contract(cols)
            if violations:
                raise ValueError(f"Cannot fit failure retriever on forbidden target columns: {violations}")
            self.feature_names_ = cols
            arr_x = X_train.values.astype(float).copy()
        else:
            arr_x = np.asarray(X_train, dtype=float).copy()
            self.feature_names_ = feature_names or [f"feat_{i}" for i in range(arr_x.shape[1])]

        n_samples, n_features = arr_x.shape
        if n_samples == 0:
            raise ValueError("Cannot fit HistoricalFailureRetriever on empty dataset.")

        # Compute scaling parameters
        self.medians_ = np.zeros(n_features)
        self.iqrs_ = np.zeros(n_features)
        for j in range(n_features):
            col_v = arr_x[:, j]
            valid_v = col_v[~np.isnan(col_v)]
            if len(valid_v) > 0:
                self.medians_[j] = float(np.median(valid_v))
                q75 = float(np.percentile(valid_v, 75))
                q25 = float(np.percentile(valid_v, 25))
                self.iqrs_[j] = max(q75 - q25, 1e-4)
            else:
                self.medians_[j] = 0.0
                self.iqrs_[j] = 1.0

        # Impute and normalize reference X
        imputed_x = arr_x.copy()
        for j in range(n_features):
            imputed_x[np.isnan(imputed_x[:, j]), j] = self.medians_[j]
        self.reference_X_norm_ = (imputed_x - self.medians_) / self.iqrs_

        self.reference_y_ = np.asarray(y_train, dtype=float).copy()
        if errors_train is not None:
            self.reference_errors_ = np.asarray(errors_train, dtype=float).copy()
        else:
            self.reference_errors_ = np.zeros_like(self.reference_y_)

        if locations_train is not None:
            self.reference_locations_ = list(locations_train)
        else:
            self.reference_locations_ = ["unknown"] * n_samples

        self.is_fitted_ = True
        return self

    def retrieve(
        self,
        query_features: Union[pd.Series, pd.DataFrame, Dict[str, Any], np.ndarray],
        filter_location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve nearest historical analogues and compute empirical failure statistics.
        """
        if not self.is_fitted_:
            raise RuntimeError("HistoricalFailureRetriever must be fitted on reference data before retrieval.")

        if isinstance(query_features, dict):
            q_arr = np.array([query_features.get(f, self.medians_[i]) for i, f in enumerate(self.feature_names_)], dtype=float)
        elif isinstance(query_features, pd.Series):
            q_arr = np.array([query_features.get(f, self.medians_[i]) for i, f in enumerate(self.feature_names_)], dtype=float)
        elif isinstance(query_features, pd.DataFrame):
            q_arr = query_features[self.feature_names_].values[0].astype(float)
        else:
            q_arr = np.asarray(query_features, dtype=float).flatten()

        # Handle NaNs in query
        for j in range(len(q_arr)):
            if np.isnan(q_arr[j]):
                q_arr[j] = self.medians_[j]

        q_norm = (q_arr - self.medians_) / self.iqrs_

        # Optional location filtering
        if filter_location and len(self.reference_locations_) == len(self.reference_y_):
            loc_mask = np.array([loc == filter_location for loc in self.reference_locations_])
            if np.sum(loc_mask) >= self.min_support:
                ref_X = self.reference_X_norm_[loc_mask]
                ref_y = self.reference_y_[loc_mask]
                ref_err = self.reference_errors_[loc_mask]
                ref_locs = [self.reference_locations_[i] for i in np.where(loc_mask)[0]]
            else:
                # Fall back to global reference if local support is too sparse
                ref_X = self.reference_X_norm_
                ref_y = self.reference_y_
                ref_err = self.reference_errors_
                ref_locs = self.reference_locations_
        else:
            ref_X = self.reference_X_norm_
            ref_y = self.reference_y_
            ref_err = self.reference_errors_
            ref_locs = self.reference_locations_

        if len(ref_X) < self.min_support:
            return {
                "support_status": "INSUFFICIENT_HISTORICAL_SUPPORT",
                "available_reference_count": len(ref_X),
                "analogue_count": 0,
                "historical_bust_rate": None,
                "mean_historical_error": None,
                "mean_similarity": None,
                "analogues": [],
            }

        # Compute Euclidean distance in normalized feature space
        dists = np.sqrt(np.mean((ref_X - q_norm) ** 2, axis=1))
        # Similarity score in [0, 1]
        sims = 1.0 / (1.0 + dists)

        k = min(self.top_k, len(ref_X))
        top_idx = np.argsort(dists)[:k]

        retrieved_y = ref_y[top_idx]
        retrieved_err = ref_err[top_idx]
        retrieved_sim = sims[top_idx]
        retrieved_loc = [ref_locs[i] for i in top_idx]

        bust_rate = float(np.mean(retrieved_y))
        mean_err = float(np.mean(retrieved_err))
        mean_sim = float(np.mean(retrieved_sim))

        analogues_summary = []
        for i in range(k):
            analogues_summary.append({
                "rank": i + 1,
                "similarity_score": round(float(retrieved_sim[i]), 4),
                "distance": round(float(dists[top_idx[i]]), 4),
                "location": str(retrieved_loc[i]),
                "historical_bust": bool(retrieved_y[i] > 0.5),
                "historical_error": round(float(retrieved_err[i]), 2) if len(retrieved_err) > 0 else 0.0,
            })

        return {
            "support_status": "SUFFICIENT_SUPPORT",
            "available_reference_count": len(ref_X),
            "analogue_count": k,
            "historical_bust_rate": round(bust_rate, 4),
            "mean_historical_error": round(mean_err, 4),
            "mean_similarity": round(mean_sim, 4),
            "analogues": analogues_summary,
            "interpretation": f"Found {k} similar historical situations; {int(bust_rate * 100)}% experienced severe forecast busts.",
        }

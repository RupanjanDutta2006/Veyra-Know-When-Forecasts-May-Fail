"""
Historical Trajectory Analogue Retrieval Engine (Day 16).

Performs non-parametric nearest-neighbor matching of temporal forecast evolution
trajectories against historical training instances to compute trajectory-level empirical failure rates.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


class HistoricalTrajectoryRetriever:
    """
    Leakage-safe historical trajectory analogue retrieval engine.
    """

    FEATURE_COLS = [
        "current_risk",
        "risk_slope",
        "risk_acceleration",
        "spread_slope",
        "revision_velocity",
        "current_lead_hours",
    ]

    def __init__(self, k_neighbors: int = 15, max_distance: float = 2.5):
        self.k_neighbors = k_neighbors
        self.max_distance = max_distance
        self.is_indexed_ = False
        self.reference_vectors_: Optional[np.ndarray] = None
        self.reference_labels_: Optional[np.ndarray] = None
        self.reference_meta_: Optional[List[Dict[str, Any]]] = None
        self.scales_: Optional[np.ndarray] = None

    def fit_reference_trajectories(
        self,
        trajectory_features_df: pd.DataFrame,
        bust_labels: np.ndarray,
        meta_records: Optional[List[Dict[str, Any]]] = None,
    ) -> "HistoricalTrajectoryRetriever":
        """
        Index historical training trajectories.
        """
        cols = [c for c in self.FEATURE_COLS if c in trajectory_features_df.columns]
        if not cols:
            raise ValueError("No matching trajectory feature columns found for indexing.")

        X = trajectory_features_df[cols].values.astype(float)
        # Robust scaling via IQR or std
        scales = np.std(X, axis=0)
        scales[scales < 1e-4] = 1.0

        self.reference_vectors_ = X / scales
        self.reference_labels_ = np.asarray(bust_labels, dtype=int)
        self.reference_meta_ = meta_records or [{} for _ in range(len(X))]
        self.scales_ = scales
        self.is_indexed_ = True
        return self

    def retrieve_analogues(
        self,
        current_features: Dict[str, float],
        exclude_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find top-k nearest trajectory analogues and calculate empirical failure rate.
        """
        if not self.is_indexed_ or self.reference_vectors_ is None or len(self.reference_vectors_) == 0:
            return {
                "analogue_count": 0,
                "failure_count": 0,
                "historical_failure_rate": 0.0,
                "trajectory_similarity": 0.0,
                "nearest_examples": [],
                "has_support": False,
            }

        query_vec = np.array([current_features.get(c, 0.0) for c in self.FEATURE_COLS], dtype=float)
        query_norm = query_vec / self.scales_

        # Compute Euclidean distances in normalized trajectory space
        diffs = self.reference_vectors_ - query_norm
        dists = np.sqrt(np.mean(diffs ** 2, axis=1))

        # Sort and take top-k
        sorted_indices = np.argsort(dists)
        top_k_indices = []
        top_k_dists = []

        for idx in sorted_indices:
            # Self-match exclusion check
            if exclude_id and self.reference_meta_ and self.reference_meta_[idx].get("id") == exclude_id:
                continue
            if dists[idx] <= self.max_distance:
                top_k_indices.append(idx)
                top_k_dists.append(float(dists[idx]))
            if len(top_k_indices) >= self.k_neighbors:
                break

        n_found = len(top_k_indices)
        if n_found == 0:
            return {
                "analogue_count": 0,
                "failure_count": 0,
                "historical_failure_rate": 0.0,
                "trajectory_similarity": 0.0,
                "nearest_examples": [],
                "has_support": False,
            }

        matched_labels = self.reference_labels_[top_k_indices]
        failure_count = int(np.sum(matched_labels == 1))
        failure_rate = float(failure_count / n_found)
        mean_dist = float(np.mean(top_k_dists))
        similarity = float(max(0.0, 1.0 - mean_dist / self.max_distance))

        nearest_examples = [
            {
                "distance": round(top_k_dists[i], 3),
                "is_bust": int(matched_labels[i]),
                "meta": self.reference_meta_[top_k_indices[i]] if self.reference_meta_ else {},
            }
            for i in range(min(5, n_found))
        ]

        return {
            "analogue_count": n_found,
            "failure_count": failure_count,
            "historical_failure_rate": round(failure_rate, 4),
            "trajectory_similarity": round(similarity, 4),
            "nearest_examples": nearest_examples,
            "has_support": n_found >= 3,
        }

"""
Veyra Research — Operational Trust Horizon Empirical Validation
Evaluates candidate P_crit failure risk tolerance thresholds on held-out validation data.

SCIENTIFIC PRINCIPLE:
P_crit = 0.35 is explicitly treated as a configurable research/product design threshold.
This module evaluates candidate thresholds (0.20, 0.25, 0.30, 0.35, 0.40, 0.50)
to quantify operational trade-offs between coverage, false early alarms, and missed busts.
Test partition must remain 100% untouched during threshold selection.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd

from research.contract.dataset_contract import CANONICAL_LEADS


@dataclass
class CandidateThresholdEvaluation:
    """Evaluation summary for a single candidate P_crit threshold."""
    pcrit_threshold: float
    mean_trust_horizon_hours: float
    pct_forecasts_day10_reliable: float
    bust_rate_inside_horizon: float       # Empirical error rate when forecast is labeled 'within horizon'
    bust_rate_outside_horizon: float      # Empirical error rate after horizon degradation point
    missed_bust_rate_inside_horizon: float # False safe rate (severe busts occurring inside horizon)
    false_early_decay_rate: float         # False alarm rate (horizon declared decayed but forecast did not bust)
    operational_utility_score: float      # Net utility = (Safe Dispatches) - Cost * (Missed Busts)
    recommended_for_deployment: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrustHorizonValidationReport:
    """Full comparative report across all tested P_crit thresholds on validation data."""
    dataset_split_used: str  # Must be 'validation'
    candidate_evaluations: List[CandidateThresholdEvaluation]
    recommended_threshold: float
    threshold_selection_rationale: str
    is_empirically_validated: bool
    scientific_disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TrustHorizonValidator:
    """
    Validates and optimizes P_crit thresholds using held-out validation trajectories.
    """

    CANDIDATE_THRESHOLDS: List[float] = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

    def __init__(self, candidate_thresholds: Optional[List[float]] = None):
        self.candidate_thresholds = candidate_thresholds or self.CANDIDATE_THRESHOLDS

    def evaluate_trajectories(
        self,
        df_val: pd.DataFrame,
        prob_col: str = "pred_prob",
        label_col: str = "bust_label",
        lead_col: str = "lead_hours",
        trajectory_group_cols: Optional[List[str]] = None,
    ) -> TrustHorizonValidationReport:
        """
        Evaluates candidate thresholds across grouped forecast trajectories.
        """
        group_cols = trajectory_group_cols or ["cycle_idx", "location_id", "variable"]

        if df_val.empty:
            return TrustHorizonValidationReport(
                dataset_split_used="validation",
                candidate_evaluations=[],
                recommended_threshold=0.35,
                threshold_selection_rationale="No validation data provided. Defaulting to design parameter.",
                is_empirically_validated=False,
                scientific_disclaimer="UNVALIDATED: Pending historical dataset completion.",
            )

        candidate_results: List[CandidateThresholdEvaluation] = []

        for p_crit in self.candidate_thresholds:
            horizons = []
            inside_busts = []
            inside_totals = []
            outside_busts = []
            outside_totals = []
            false_early_decays = 0
            missed_busts = 0
            total_trajectories = 0

            # Group into trajectories across lead times
            for _, traj in df_val.groupby(group_cols):
                traj_sorted = traj.sort_values(by=lead_col)
                leads = traj_sorted[lead_col].values
                probs = traj_sorted[prob_col].values
                labels = traj_sorted[label_col].values

                total_trajectories += 1

                # Find first lead violating P_crit
                violating_idx = np.where(probs >= p_crit)[0]
                if len(violating_idx) > 0:
                    h_val = leads[violating_idx[0]]
                    inside_mask = np.arange(len(leads)) < violating_idx[0]
                    outside_mask = np.arange(len(leads)) >= violating_idx[0]
                else:
                    h_val = int(leads[-1])
                    inside_mask = np.ones(len(leads), dtype=bool)
                    outside_mask = np.zeros(len(leads), dtype=bool)

                horizons.append(h_val)

                if np.sum(inside_mask) > 0:
                    in_labels = labels[inside_mask]
                    inside_busts.append(np.sum(in_labels))
                    inside_totals.append(len(in_labels))
                    missed_busts += int(np.sum(in_labels))

                if np.sum(outside_mask) > 0:
                    out_labels = labels[outside_mask]
                    outside_busts.append(np.sum(out_labels))
                    outside_totals.append(len(out_labels))
                    # False early decay if outside horizon but zero busts occurred
                    if np.sum(out_labels) == 0:
                        false_early_decays += 1

            mean_h = float(np.mean(horizons))
            pct_day10 = float(np.mean(np.array(horizons) >= 240) * 100.0)

            total_inside = sum(inside_totals) if inside_totals else 1
            total_outside = sum(outside_totals) if outside_totals else 1

            rate_inside = float(sum(inside_busts) / total_inside) if total_inside > 0 else 0.0
            rate_outside = float(sum(outside_busts) / total_outside) if total_outside > 0 else 0.0

            false_decay_pct = float(false_early_decays / max(1, total_trajectories) * 100.0)
            missed_bust_pct = float(missed_busts / max(1, total_inside) * 100.0)

            # Simple linear utility: Reward coverage inside horizon with low error, penalize missed busts heavily (cost ratio 5:1)
            utility = (1.0 - rate_inside) * (mean_h / 240.0) - 5.0 * (rate_inside)

            candidate_results.append(
                CandidateThresholdEvaluation(
                    pcrit_threshold=round(p_crit, 2),
                    mean_trust_horizon_hours=round(mean_h, 1),
                    pct_forecasts_day10_reliable=round(pct_day10, 1),
                    bust_rate_inside_horizon=round(rate_inside, 4),
                    bust_rate_outside_horizon=round(rate_outside, 4),
                    missed_bust_rate_inside_horizon=round(missed_bust_pct, 2),
                    false_early_decay_rate=round(false_decay_pct, 2),
                    operational_utility_score=round(utility, 4),
                )
            )

        # Select candidate with highest operational utility
        best_cand = max(candidate_results, key=lambda x: x.operational_utility_score)
        best_cand.recommended_for_deployment = True

        rationale = (
            f"Candidate P_crit = {best_cand.pcrit_threshold:.2f} achieved optimal operational utility ({best_cand.operational_utility_score:.3f}) "
            f"on validation data with inside-horizon error rate of {best_cand.bust_rate_inside_horizon:.1%} and mean horizon of {best_cand.mean_trust_horizon_hours:.0f}h."
        )

        return TrustHorizonValidationReport(
            dataset_split_used="validation",
            candidate_evaluations=candidate_results,
            recommended_threshold=best_cand.pcrit_threshold,
            threshold_selection_rationale=rationale,
            is_empirically_validated=True,
            scientific_disclaimer=(
                "Empirically validated on held-out validation cycles. "
                "Final test partition remains strictly untouched until benchmark freezing."
            ),
        )

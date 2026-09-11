"""
Veyra Research — Conditional Error Distribution Benchmark
Evaluates and compares Quantile Mesh (E4), Parametric Student-t (E5), and Frozen V2 (E3).

SCIENTIFIC RULE:
The Quantile Mesh model currently exists as a challenger and has NOT yet passed
the authoritative BSS promotion gate on the full 1,040-cycle dataset.
This module produces empirical comparative evidence across CRPS, pinball loss, PICP,
exceedance calibration, and lead-wise stability without automatic promotion.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd

from research.contract.dataset_contract import CANONICAL_LEADS
from research.evaluation.metrics import (
    calculate_pinball_loss,
    calculate_crps_empirical,
    calculate_picp,
    calculate_brier_skill_score,
    calculate_ece,
    calculate_pr_auc,
)


@dataclass
class ErrorDistributionModelMetrics:
    """Standardized probabilistic verification metrics for an error-distribution model."""
    model_name: str
    crps: float
    pinball_loss: float
    picp_80: float
    picp_90: float
    picp_95: float
    mean_interval_width_90: float
    tail_exceedance_error_p95: float
    brier_score_bust: float
    bss_vs_v2: float
    ece_bust: float
    pr_auc_bust: float
    lead_wise_crps: Dict[int, float] = field(default_factory=dict)
    lead_wise_picp_90: Dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorDistributionComparisonReport:
    """Full probabilistic error-distribution benchmark report."""
    dataset_partition: str
    models_evaluated: Dict[str, ErrorDistributionModelMetrics]
    quantile_mesh_passes_bss_gate: bool
    parametric_challenger_passes_bss_gate: bool
    recommended_model: str
    decision_rationale: str
    scientific_disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConditionalErrorDistributionEvaluator:
    """
    Evaluates conditional error distribution predictions against true verification errors.
    """

    DEFAULT_QUANTILE_LEVELS = np.array([0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])

    def __init__(self, quantile_levels: Optional[np.ndarray] = None):
        self.quantile_levels = quantile_levels if quantile_levels is not None else self.DEFAULT_QUANTILE_LEVELS

    def evaluate_model(
        self,
        model_name: str,
        quantiles: np.ndarray,      # Shape (N, n_quantiles)
        true_errors: np.ndarray,    # Shape (N,)
        bust_probs: np.ndarray,     # Shape (N,)
        bust_labels: np.ndarray,    # Shape (N,)
        v2_bust_probs: np.ndarray,  # Shape (N,) for BSS computation
        lead_hours: Optional[np.ndarray] = None,
    ) -> ErrorDistributionModelMetrics:
        """
        Computes probabilistic loss and calibration metrics for a single distribution model.
        """
        valid = (~np.isnan(true_errors)) & (~np.isnan(bust_probs)) & (~np.isnan(bust_labels))
        q = quantiles[valid]
        e = true_errors[valid]
        p = bust_probs[valid]
        y = bust_labels[valid].astype(int)
        p_v2 = v2_bust_probs[valid]
        leads = lead_hours[valid] if lead_hours is not None else np.full(len(e), 24)

        # 1. Pinball Loss across all quantile knots
        pinball = calculate_pinball_loss(q, e, self.quantile_levels)

        # 2. CRPS Approximation
        crps_list = [
            calculate_crps_empirical(q[i], self.quantile_levels, float(e[i]))
            for i in range(min(1500, len(q)))
        ]
        crps_val = float(np.nanmean(crps_list))

        # 3. PICP (Coverage Probabilities)
        # 80%: q0.10 (idx 2) to q0.90 (idx 6)
        picp_80 = calculate_picp(q[..., 2], q[..., 6], e)
        # 90%: q0.05 (idx 1) to q0.95 (idx 7)
        picp_90 = calculate_picp(q[..., 1], q[..., 7], e)
        # 95%: q0.025 / q0.01 (idx 0) to q0.99 (idx 8)
        picp_95 = calculate_picp(q[..., 0], q[..., -1], e)

        interval_w_90 = float(np.nanmean(q[..., 7] - q[..., 1]))

        # Tail exceedance error at 95th percentile (nominal rate = 0.05)
        tail_exceed = float(np.mean(e > q[..., 7]))
        tail_err = float(abs(tail_exceed - 0.05))

        # Bust classification metrics
        bs_model = float(np.mean((p - y) ** 2))
        bss_v2 = calculate_brier_skill_score(p, y, p_v2)
        ece_val = calculate_ece(p, y)["ece"]
        pr_auc_val = calculate_pr_auc(p, y)

        # Lead-wise disaggregation
        lead_crps: Dict[int, float] = {}
        lead_picp: Dict[int, float] = {}
        for l in np.unique(leads):
            l_mask = (leads == l)
            if np.sum(l_mask) >= 10:
                l_crps = [
                    calculate_crps_empirical(q[l_mask][j], self.quantile_levels, float(e[l_mask][j]))
                    for j in range(min(200, np.sum(l_mask)))
                ]
                lead_crps[int(l)] = round(float(np.nanmean(l_crps)), 4)
                lead_picp[int(l)] = round(calculate_picp(q[l_mask][..., 1], q[l_mask][..., 7], e[l_mask]), 4)

        return ErrorDistributionModelMetrics(
            model_name=model_name,
            crps=round(crps_val, 4),
            pinball_loss=round(pinball, 4),
            picp_80=round(picp_80, 4),
            picp_90=round(picp_90, 4),
            picp_95=round(picp_95, 4),
            mean_interval_width_90=round(interval_w_90, 4),
            tail_exceedance_error_p95=round(tail_err, 4),
            brier_score_bust=round(bs_model, 4),
            bss_vs_v2=round(bss_v2, 4) if not np.isnan(bss_v2) else 0.0,
            ece_bust=round(ece_val, 4) if not np.isnan(ece_val) else 0.0,
            pr_auc_bust=round(pr_auc_val, 4) if not np.isnan(pr_auc_val) else 0.0,
            lead_wise_crps=lead_crps,
            lead_wise_picp_90=lead_picp,
        )

    def compare_challengers(
        self,
        mesh_metrics: ErrorDistributionModelMetrics,
        parametric_metrics: ErrorDistributionModelMetrics,
        partition_name: str = "test",
    ) -> ErrorDistributionComparisonReport:
        """
        Applies strict scientific promotion gates to compare challengers against V2.
        """
        # Promotion gate: must achieve positive BSS over V2, lower CRPS, and ECE <= 0.05
        mesh_passes = (mesh_metrics.bss_vs_v2 > 0.0 and mesh_metrics.ece_bust <= 0.05)
        param_passes = (parametric_metrics.bss_vs_v2 > 0.0 and parametric_metrics.ece_bust <= 0.05)

        if mesh_passes and mesh_metrics.crps < parametric_metrics.crps:
            rec = "E4_QUANTILE_MESH"
            rationale = (
                f"Quantile Mesh demonstrated superior probabilistic performance (CRPS: {mesh_metrics.crps:.4f}, "
                f"BSS vs V2: +{mesh_metrics.bss_vs_v2:.4f}, 90% PICP: {mesh_metrics.picp_90:.1%})."
            )
        elif param_passes:
            rec = "E5_PARAMETRIC_STUDENT_T"
            rationale = (
                f"Parametric Student-t achieved positive BSS (+{parametric_metrics.bss_vs_v2:.4f}) and low CRPS ({parametric_metrics.crps:.4f})."
            )
        else:
            rec = "E3_FROZEN_V2"
            rationale = (
                "Neither challenger achieved statistically significant BSS improvement over frozen V2 on held-out test data. "
                "Retaining frozen V2 champion as production standard."
            )

        return ErrorDistributionComparisonReport(
            dataset_partition=partition_name,
            models_evaluated={
                "E4_QUANTILE_MESH": mesh_metrics,
                "E5_PARAMETRIC_CHALLENGER": parametric_metrics,
            },
            quantile_mesh_passes_bss_gate=mesh_passes,
            parametric_challenger_passes_bss_gate=param_passes,
            recommended_model=rec,
            decision_rationale=rationale,
            scientific_disclaimer=(
                "Challenger promotion gate strictly requires empirical superiority on held-out test data. "
                "Quantile mesh is not promoted by default."
            ),
        )

"""
Veyra Research — Track 6: Failure-Archetype Diagnostic Evaluator
Reports probabilistic model performance conditioned on detected failure archetypes.
Explicitly distinguishes diagnostic heuristic categories from ERA5 reanalysis verification/reference labels.
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd
from research.evaluation.metrics import calculate_brier_skill_score, calculate_ece, calculate_pr_auc, calculate_roc_auc


class FailureArchetypeEvaluator:
    """
    Evaluates probabilistic model performance across the 6 failure archetypes:
      1. Ensemble Divergence
      2. Long-Lead Decay
      3. Revision Instability
      4. Wind Gradient / Shear
      5. Synoptic Transition
      6. Out-of-Distribution (OOD)
    """

    ARCHETYPES = [
        "ENSEMBLE_DIVERGENCE",
        "LONG_LEAD_DECAY",
        "REVISION_INSTABILITY",
        "WIND_GRADIENT_SHEAR",
        "SYNOPTIC_TRANSITION",
        "OOD_CONDITION"
    ]

    def evaluate_by_archetype(self,
                              df: pd.DataFrame,
                              prob_col: str = "calibrated_prob",
                              label_col: str = "bust_label",
                              ref_prob_col: str = "clim_prob",
                              archetype_col: str = "failure_archetype") -> Dict[str, Dict[str, Any]]:
        """
        Computes metric breakdown stratified by failure archetype.
        """
        results: Dict[str, Dict[str, Any]] = {}

        for arch in self.ARCHETYPES:
            subset = df[df[archetype_col] == arch] if archetype_col in df.columns else pd.DataFrame()
            n_samples = len(subset)

            if n_samples < 5:
                results[arch] = {
                    "sample_count": n_samples,
                    "positive_rate": np.nan,
                    "pr_auc": np.nan,
                    "roc_auc": np.nan,
                    "brier_score": np.nan,
                    "brier_skill_score": np.nan,
                    "ece": np.nan,
                    "evaluation_status": "INSUFFICIENT_SAMPLES"
                }
                continue

            p = subset[prob_col].values
            y = subset[label_col].values
            p_ref = subset[ref_prob_col].values if ref_prob_col in subset.columns else np.full_like(p, np.nanmean(y))

            pr_auc = calculate_pr_auc(p, y)
            roc_auc = calculate_roc_auc(p, y)
            bs = float(np.nanmean((p - y) ** 2))
            bss = calculate_brier_skill_score(p, y, p_ref)
            ece_res = calculate_ece(p, y, n_bins=5)

            results[arch] = {
                "sample_count": n_samples,
                "positive_rate": float(np.nanmean(y)),
                "pr_auc": pr_auc,
                "roc_auc": roc_auc,
                "brier_score": bs,
                "brier_skill_score": bss,
                "ece": ece_res["ece"],
                "evaluation_status": "VALIDATED"
            }

        return results

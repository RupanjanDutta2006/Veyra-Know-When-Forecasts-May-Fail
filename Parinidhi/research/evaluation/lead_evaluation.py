"""
Veyra Research — Lead-Wise Evaluation Framework
Disaggregates forecast verification metrics across the standard 10 lead times:
+24h, +48h, +72h, +96h, +120h, +144h, +168h, +192h, +216h, +240h.

SCIENTIFIC RULE:
Never pool all lead times together and claim the aggregate represents lead-specific skill.
Error dispersion, calibration drift, and failure rates vary non-linearly with forecast lead.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd

from research.contract.dataset_contract import CANONICAL_LEADS
from research.evaluation.metrics import (
    calculate_brier_skill_score,
    calculate_ece,
    calculate_pr_auc,
    calculate_roc_auc,
)


@dataclass
class LeadWiseEvaluationReport:
    """Detailed lead-time disaggregated performance report."""
    model_id: str
    model_name: str
    lead_metrics: Dict[int, Dict[str, Any]]
    lead_brier_scores: Dict[int, float]
    lead_bss_climatology: Dict[int, float]
    lead_pr_aucs: Dict[int, float]
    lead_eces: Dict[int, float]
    lead_sample_counts: Dict[int, int]
    lead_bust_base_rates: Dict[int, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for lead in sorted(self.lead_metrics.keys()):
            m = self.lead_metrics[lead]
            rows.append({
                "lead_hours": lead,
                "lead_days": round(lead / 24.0, 2),
                "n_samples": m.get("n_samples", 0),
                "base_rate": m.get("base_rate", np.nan),
                "brier_score": m.get("brier_score", np.nan),
                "bss_vs_clim": m.get("bss_vs_climatology", np.nan),
                "pr_auc": m.get("pr_auc", np.nan),
                "roc_auc": m.get("roc_auc", np.nan),
                "ece": m.get("ece", np.nan),
            })
        return pd.DataFrame(rows)


class LeadWiseEvaluator:
    """
    Evaluates model performance stratified strictly by forecast lead time.
    """

    def __init__(self, target_leads: Optional[List[int]] = None):
        self.target_leads = target_leads or CANONICAL_LEADS

    def evaluate(
        self,
        model_id: str,
        model_name: str,
        df_eval: pd.DataFrame,
        prob_col: str = "pred_prob",
        label_col: str = "bust_label",
        clim_prob_col: Optional[str] = None,
    ) -> LeadWiseEvaluationReport:
        """
        Computes lead-by-lead metrics on evaluation DataFrame.
        """
        lead_metrics: Dict[int, Dict[str, Any]] = {}
        lead_brier: Dict[int, float] = {}
        lead_bss: Dict[int, float] = {}
        lead_pr_auc: Dict[int, float] = {}
        lead_ece: Dict[int, float] = {}
        lead_samples: Dict[int, int] = {}
        lead_base_rates: Dict[int, float] = {}

        for lead in self.target_leads:
            sub = df_eval[df_eval["lead_hours"] == lead]
            if sub.empty or len(sub) < 5:
                lead_metrics[lead] = {"n_samples": len(sub), "status": "INSUFFICIENT_SAMPLES"}
                continue

            probs = sub[prob_col].values.astype(float)
            labels = sub[label_col].values.astype(int)

            if clim_prob_col and clim_prob_col in sub.columns:
                clim_probs = sub[clim_prob_col].values.astype(float)
            else:
                clim_probs = np.full_like(probs, np.mean(labels))

            valid = (~np.isnan(probs)) & (~np.isnan(labels))
            p, y, p_clim = probs[valid], labels[valid], clim_probs[valid]

            n = len(p)
            base_rate = float(np.mean(y)) if n > 0 else 0.0
            bs = float(np.mean((p - y) ** 2)) if n > 0 else np.nan
            bss = calculate_brier_skill_score(p, y, p_clim)
            pr_auc_val = calculate_pr_auc(p, y)
            roc_auc_val = calculate_roc_auc(p, y)
            ece_dict = calculate_ece(p, y, n_bins=10)

            lead_brier[lead] = round(bs, 4) if not np.isnan(bs) else np.nan
            lead_bss[lead] = round(bss, 4) if not np.isnan(bss) else np.nan
            lead_pr_auc[lead] = round(pr_auc_val, 4) if not np.isnan(pr_auc_val) else np.nan
            lead_ece[lead] = round(ece_dict["ece"], 4) if not np.isnan(ece_dict["ece"]) else np.nan
            lead_samples[lead] = n
            lead_base_rates[lead] = round(base_rate, 4)

            lead_metrics[lead] = {
                "n_samples": n,
                "base_rate": round(base_rate, 4),
                "brier_score": round(bs, 4),
                "bss_vs_climatology": round(bss, 4),
                "pr_auc": round(pr_auc_val, 4),
                "roc_auc": round(roc_auc_val, 4),
                "ece": round(ece_dict["ece"], 4),
            }

        return LeadWiseEvaluationReport(
            model_id=model_id,
            model_name=model_name,
            lead_metrics=lead_metrics,
            lead_brier_scores=lead_brier,
            lead_bss_climatology=lead_bss,
            lead_pr_aucs=lead_pr_auc,
            lead_eces=lead_ece,
            lead_sample_counts=lead_samples,
            lead_bust_base_rates=lead_base_rates,
        )

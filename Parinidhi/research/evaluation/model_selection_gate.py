"""
Veyra — Post-Dataset Model Selection Gate (SIH26079)
Authoritative Decision Engine for Model Promotion & Production Freezing.

Rules:
1. Frozen V2 (E3) remains the production champion by default.
2. A challenger (e.g., E4 Quantile Mesh, E5 Parametric) may ONLY replace V2
   if it passes all multi-objective scientific promotion gates on held-out test data.
3. No single-metric optimization (e.g. optimizing ROC-AUC alone, or one favorable lead/region).
4. Full distinction between VALIDATED, SUPPORTED_BY_CURRENT_EVIDENCE, DESIGN_CHOICE,
   HEURISTIC, DEMO_ONLY, UNVALIDATED, and PENDING_DATASET.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger("veyra.model_selection_gate")


@dataclass
class GateCriterion:
    """Individual quantitative promotion criterion."""
    name: str
    target_metric: str
    operator: str  # '>=', '<=', '>', '<', 'max_drop'
    threshold: float
    actual_value: Optional[float]
    passed: bool
    description: str
    status: str = "PENDING_DATASET"  # VALIDATED, PENDING_DATASET, UNVALIDATED


@dataclass
class ModelSelectionReport:
    """Comprehensive Model Selection & Promotion Audit Report."""
    champion_model_name: str
    challenger_model_name: str
    decision: str  # 'RETAIN_FROZEN_V2', 'PROMOTE_CHALLENGER', 'INSUFFICIENT_EVIDENCE'
    justification: str
    scientific_status: str
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    lead_stability_passed: bool = False
    regional_generalization_passed: bool = False
    calibration_gate_passed: bool = False
    summary_metrics_comparison: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class ModelSelectionGate:
    """
    Evaluates challenger models against frozen V2 and Fair Ensemble baseline.
    Enforces non-negotiable multi-objective promotion thresholds.
    """

    DEFAULT_GATES = {
        "pr_auc_non_inferiority": {
            "metric": "pr_auc",
            "operator": ">=",
            "threshold_delta": 0.0,  # Must be >= champion
            "desc": "PR-AUC must be greater than or equal to Frozen V2 champion."
        },
        "brier_skill_score_positive": {
            "metric": "brier_skill_score",
            "operator": ">",
            "threshold": 0.0,
            "desc": "Brier Skill Score relative to Fair Ensemble baseline must be positive (> 0.0)."
        },
        "ece_calibration_ceiling": {
            "metric": "ece",
            "operator": "<=",
            "threshold": 0.05,
            "desc": "Expected Calibration Error (ECE) must not exceed 0.05 on held-out test data."
        },
        "max_lead_pr_auc_drop": {
            "metric": "lead_pr_auc_min",
            "operator": ">=",
            "threshold": 0.15,
            "desc": "Worst-lead PR-AUC must remain above 0.15 (no catastrophic failure at +240h)."
        },
        "worst_region_recall_floor": {
            "metric": "worst_region_recall",
            "operator": ">=",
            "threshold": 0.50,
            "desc": "Recall in the worst-performing geographic region must be >= 0.50 at operating threshold."
        }
    }

    def __init__(self, gates_config: Optional[Dict[str, Any]] = None):
        self.gates_config = gates_config or self.DEFAULT_GATES

    def evaluate_promotion(
        self,
        champion_metrics: Dict[str, Any],
        challenger_metrics: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]] = None,
        lead_metrics_challenger: Optional[Dict[int, Dict[str, float]]] = None,
        region_metrics_challenger: Optional[Dict[str, Dict[str, float]]] = None,
        is_real_dataset: bool = False
    ) -> ModelSelectionReport:
        """
        Evaluate whether a challenger model can be promoted over Frozen V2.
        
        Args:
            champion_metrics: Performance metrics dict for Frozen V2 (E3).
            challenger_metrics: Performance metrics dict for challenger model (E4 or E5).
            baseline_metrics: Metrics dict for Fair Ensemble (E1b) reference.
            lead_metrics_challenger: Per-lead metrics dict (+24 to +240).
            region_metrics_challenger: Per-region leave-one-out metrics.
            is_real_dataset: If False, status is marked PENDING_DATASET.
        """
        gate_records: List[Dict[str, Any]] = []
        all_passed = True
        
        scientific_status = "VALIDATED" if is_real_dataset else "PENDING_DATASET"

        # 1. PR-AUC Check
        champ_pr_auc = champion_metrics.get("pr_auc", 0.0)
        chall_pr_auc = challenger_metrics.get("pr_auc", 0.0)
        pr_auc_pass = chall_pr_auc >= champ_pr_auc if is_real_dataset else False
        gate_records.append({
            "name": "pr_auc_non_inferiority",
            "champion_val": champ_pr_auc,
            "challenger_val": chall_pr_auc,
            "passed": pr_auc_pass,
            "status": scientific_status,
            "detail": f"Challenger ({chall_pr_auc:.4f}) vs Champion ({champ_pr_auc:.4f})"
        })
        if not pr_auc_pass and is_real_dataset:
            all_passed = False

        # 2. Brier Skill Score vs Baseline
        bss = challenger_metrics.get("brier_skill_score", 0.0)
        bss_pass = bss > 0.0 if is_real_dataset else False
        gate_records.append({
            "name": "brier_skill_score_positive",
            "champion_val": champion_metrics.get("brier_skill_score", 0.0),
            "challenger_val": bss,
            "passed": bss_pass,
            "status": scientific_status,
            "detail": f"BSS={bss:.4f} (> 0.0 required)"
        })
        if not bss_pass and is_real_dataset:
            all_passed = False

        # 3. ECE Calibration
        chall_ece = challenger_metrics.get("ece", 1.0)
        ece_pass = chall_ece <= 0.05 if is_real_dataset else False
        gate_records.append({
            "name": "ece_calibration_ceiling",
            "champion_val": champion_metrics.get("ece", 1.0),
            "challenger_val": chall_ece,
            "passed": ece_pass,
            "status": scientific_status,
            "detail": f"ECE={chall_ece:.4f} (<= 0.05 required)"
        })
        if not ece_pass and is_real_dataset:
            all_passed = False

        # 4. Lead Stability
        lead_stability = True
        min_lead_pr_auc = 1.0
        if lead_metrics_challenger and is_real_dataset:
            for lead, l_metrics in lead_metrics_challenger.items():
                l_pr_auc = l_metrics.get("pr_auc", 0.0)
                if l_pr_auc < min_lead_pr_auc:
                    min_lead_pr_auc = l_pr_auc
                if l_pr_auc < 0.15:
                    lead_stability = False
        else:
            lead_stability = False

        gate_records.append({
            "name": "lead_stability",
            "worst_lead_pr_auc": min_lead_pr_auc if is_real_dataset else None,
            "passed": lead_stability if is_real_dataset else False,
            "status": scientific_status,
            "detail": f"Worst lead PR-AUC: {min_lead_pr_auc:.4f}" if is_real_dataset else "Pending dataset"
        })
        if not lead_stability and is_real_dataset:
            all_passed = False

        # 5. Regional Generalization
        region_pass = True
        worst_region_rec = 1.0
        if region_metrics_challenger and is_real_dataset:
            for reg, r_metrics in region_metrics_challenger.items():
                r_rec = r_metrics.get("recall", 0.0)
                if r_rec < worst_region_rec:
                    worst_region_rec = r_rec
                if r_rec < 0.50:
                    region_pass = False
        else:
            region_pass = False

        gate_records.append({
            "name": "regional_generalization",
            "worst_region_recall": worst_region_rec if is_real_dataset else None,
            "passed": region_pass if is_real_dataset else False,
            "status": scientific_status,
            "detail": f"Worst region recall: {worst_region_rec:.4f}" if is_real_dataset else "Pending dataset"
        })
        if not region_pass and is_real_dataset:
            all_passed = False

        # Final Decision
        if not is_real_dataset:
            decision = "RETAIN_FROZEN_V2"
            justification = (
                "Dataset evaluation is PENDING. Frozen V2 remains production model invariant "
                "until 1,040-cycle historical dataset is fully extracted and audited."
            )
        elif all_passed:
            decision = "PROMOTE_CHALLENGER"
            justification = (
                f"Challenger demonstrated strict superiority across PR-AUC ({chall_pr_auc:.4f}), "
                f"positive BSS ({bss:.4f}), calibrated ECE ({chall_ece:.4f}), lead stability, and regional generalization."
            )
        else:
            decision = "RETAIN_FROZEN_V2"
            justification = (
                "Challenger failed one or more mandatory promotion gates on held-out test data. "
                "Frozen V2 retained as production champion."
            )

        limitations = [
            "Decision rule is strictly non-negotiable and requires multi-objective pass.",
            "ERA5 reference is reanalysis verification, not station truth.",
            "Empirical results will only populate after 1,040-cycle benchmark execution."
        ]

        return ModelSelectionReport(
            champion_model_name=champion_metrics.get("model_name", "Frozen_V2_Champion"),
            challenger_model_name=challenger_metrics.get("model_name", "Challenger_Model"),
            decision=decision,
            justification=justification,
            scientific_status=scientific_status,
            gate_results=gate_records,
            lead_stability_passed=lead_stability if is_real_dataset else False,
            regional_generalization_passed=region_pass if is_real_dataset else False,
            calibration_gate_passed=ece_pass if is_real_dataset else False,
            summary_metrics_comparison={
                "champion": champion_metrics,
                "challenger": challenger_metrics
            },
            limitations=limitations
        )

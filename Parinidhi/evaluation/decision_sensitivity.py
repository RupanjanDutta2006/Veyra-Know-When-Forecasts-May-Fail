"""
Decision Sensitivity & Threshold Robustness Analysis (Day 15 Hardened).

Provides:
1. Decision boundary margin quantification for individual forecast instances.
2. Comprehensive threshold sensitivity analysis under parameter perturbations (+/-10%, +/-20%).
3. Deterministic physical sensitivity guidance ("What evidence would change this decision?").
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from evaluation.decision_policy import RiskDecisionPolicy
from evaluation.decision_schema import OperationalDecision, RiskLevel


class DecisionSensitivityAnalyzer:
    """
    Computes decision boundary margins and deterministic sensitivity counterfactuals.
    """

    def analyze_sensitivity(
        self,
        risk_score: float,
        current_decision: OperationalDecision,
        current_risk_level: RiskLevel,
        drivers: List[Dict[str, Any]],
        policy: RiskDecisionPolicy,
    ) -> Dict[str, Any]:
        """
        Compute boundary margins and counterfactual guidance.
        """
        thresh_crit = policy.critical_threshold
        thresh_high = policy.high_threshold
        thresh_elev = policy.elevated_threshold
        thresh_watch = policy.watch_threshold

        margins: Dict[str, float] = {
            "to_critical": round(float(thresh_crit - risk_score), 4),
            "to_high": round(float(thresh_high - risk_score), 4),
            "to_elevated": round(float(thresh_elev - risk_score), 4),
            "to_watch": round(float(thresh_watch - risk_score), 4),
        }

        all_thresholds = [0.0, thresh_watch, thresh_elev, thresh_high, thresh_crit, 1.0]
        distances = [abs(risk_score - t) for t in all_thresholds]
        min_dist = float(min(distances))

        counterfactuals: List[str] = []
        if current_risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            for d in drivers:
                feat = d.get("feature", "")
                val = d.get("raw_value", 0.0)
                if "std" in feat:
                    counterfactuals.append(f"Reducing ensemble spread from {val:.1f} to below {val * 0.5:.1f} would lower risk level.")
                elif "delta" in feat:
                    counterfactuals.append(f"Stabilizing inter-cycle forecast revisions (currently delta={val:.1f}) would reduce warning priority.")
                elif "lead" in feat:
                    counterfactuals.append("Verifying at a shorter forecast lead time (<24h) would increase model stability.")
        elif current_risk_level in [RiskLevel.LOW, RiskLevel.WATCH]:
            counterfactuals.append("A sudden widening of 24h ensemble spread would push decision into ADVISE_CAUTION.")
            counterfactuals.append("Significant inter-cycle forecast adjustments in the next synoptic run would trigger elevated monitoring.")

        if not counterfactuals:
            counterfactuals.append("Moderate shift in primary ensemble dispersion moments would alter decision level.")

        return {
            "decision_margin_to_boundary": round(min_dist, 4),
            "stability_status": "STABLE" if min_dist >= 0.05 else "NEAR_BOUNDARY",
            "threshold_distances": margins,
            "counterfactual_evidence": counterfactuals[:3],
            "disclaimer": "Deterministic sensitivity analysis; does not represent causal counterfactual inference.",
        }


class ThresholdSensitivityAnalyzer:
    """
    Evaluates policy robustness across parameter perturbations (+/-10%, +/-20%).
    """

    @staticmethod
    def evaluate_perturbations(
        base_policy: RiskDecisionPolicy,
        risk_scores: np.ndarray,
        confidences: np.ndarray,
        perturbation_deltas: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Measure fraction of instances whose operational decision changes under parameter shifts.
        """
        deltas = perturbation_deltas or [-0.20, -0.10, 0.10, 0.20]
        n_samples = len(risk_scores)
        if n_samples == 0:
            return {"status": "NO_SAMPLES", "perturbation_results": {}}

        # Base decisions
        base_decisions = [
            base_policy.determine_decision(
                risk_level=base_policy.evaluate_risk_level(s),
                confidence=confidences[i],
                abstention_required=False,
            )
            for i, s in enumerate(risk_scores)
        ]

        perturbation_results = {}

        for delta in deltas:
            shifted_high = float(np.clip(base_policy.high_threshold * (1.0 + delta), 0.05, 0.95))
            shifted_crit = float(np.clip(base_policy.critical_threshold * (1.0 + delta), 0.10, 0.99))
            shifted_elev = float(np.clip(base_policy.elevated_threshold * (1.0 + delta), 0.03, 0.90))
            shifted_watch = float(np.clip(base_policy.watch_threshold * (1.0 + delta), 0.01, 0.85))

            perturbed_policy = RiskDecisionPolicy(
                high_threshold=shifted_high,
                critical_threshold=shifted_crit,
                elevated_threshold=shifted_elev,
                watch_threshold=shifted_watch,
                fn_cost_weight=base_policy.fn_cost_weight,
                fp_cost_weight=base_policy.fp_cost_weight,
                alert_fatigue_penalty=base_policy.alert_fatigue_penalty,
            )

            perturbed_decisions = [
                perturbed_policy.determine_decision(
                    risk_level=perturbed_policy.evaluate_risk_level(s),
                    confidence=confidences[i],
                    abstention_required=False,
                )
                for i, s in enumerate(risk_scores)
            ]

            switches = sum(1 for b, p in zip(base_decisions, perturbed_decisions) if b != p)
            switch_rate = switches / n_samples

            key = f"shift_{'+' if delta > 0 else ''}{int(delta * 100)}pct"
            perturbation_results[key] = {
                "delta": delta,
                "switched_decisions_count": switches,
                "switch_rate": round(switch_rate, 4),
                "stability_score": round(1.0 - switch_rate, 4),
            }

        # Overall policy robustness score
        mean_stability = float(np.mean([r["stability_score"] for r in perturbation_results.values()]))

        return {
            "sample_count": n_samples,
            "mean_stability_score": round(mean_stability, 4),
            "robustness_status": "ROBUST" if mean_stability >= 0.85 else "SENSITIVE",
            "perturbation_results": perturbation_results,
        }

"""
Evidence Fusion and Conflict Handling Module (Day 15).

Fuses heterogeneous issue-time signals into structured supporting and contradicting
evidence representations, detecting and penalizing severe evidentiary conflicts.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from evaluation.decision_schema import EvidenceItem


class EvidenceFusionEngine:
    """
    Combines model probabilities, ensemble dispersion, novelty, and analogues into a unified evidence matrix.
    """

    def fuse_evidence(
        self,
        raw_prob: float,
        calibrated_prob: float,
        uncertainty_res: Dict[str, Any],
        novelty_res: Dict[str, Any],
        retrieval_res: Dict[str, Any],
        location_profile: Dict[str, Any],
        lead_hours: int = 24,
    ) -> Tuple[List[EvidenceItem], List[EvidenceItem], float, float]:
        """
        Extract supporting and contradicting evidence, compute conflict score and composite risk score.

        Returns:
            Tuple of (supporting_evidence, contradicting_evidence, conflict_score, composite_risk_score)
        """
        supporting: List[EvidenceItem] = []
        contradicting: List[EvidenceItem] = []

        eff_prob = max(raw_prob, calibrated_prob) if np.isfinite(raw_prob) and np.isfinite(calibrated_prob) else 0.15

        # 1. Model Probability Evidence
        if eff_prob >= 0.22:
            supporting.append(EvidenceItem(
                source="PROBABILITY_MODEL",
                direction="INCREASES_RISK",
                strength=min(eff_prob * 1.3, 1.0),
                confidence=0.85,
                summary=f"Model predicts elevated bust likelihood ({int(eff_prob * 100)}% probability).",
                metric_value=round(eff_prob, 4),
            ))
        else:
            contradicting.append(EvidenceItem(
                source="PROBABILITY_MODEL",
                direction="DECREASES_RISK",
                strength=max(1.0 - eff_prob * 3.0, 0.0),
                confidence=0.85,
                summary=f"Model predicts low bust likelihood ({int(eff_prob * 100)}% probability).",
                metric_value=round(eff_prob, 4),
            ))

        # 2. Ensemble Dispersion Evidence
        comps = uncertainty_res.get("components", {})
        aleatoric = comps.get("aleatoric_dispersion", {}).get("score", 0.0)
        ens_std = comps.get("aleatoric_dispersion", {}).get("ensemble_std", 1.0)
        if aleatoric >= 0.40:
            supporting.append(EvidenceItem(
                source="ENSEMBLE_DISPERSION",
                direction="INCREASES_RISK",
                strength=aleatoric,
                confidence=0.90,
                summary=f"High ensemble dispersion (std={ens_std:.1f}) indicates strong NWP member disagreement.",
                metric_value=round(ens_std, 2),
            ))
        else:
            contradicting.append(EvidenceItem(
                source="ENSEMBLE_DISPERSION",
                direction="DECREASES_RISK",
                strength=1.0 - aleatoric,
                confidence=0.90,
                summary=f"Low ensemble dispersion (std={ens_std:.1f}) indicates consistent NWP member consensus.",
                metric_value=round(ens_std, 2),
            ))

        # 3. Dynamic Revision Instability
        instability = comps.get("dynamic_instability", {}).get("score", 0.0)
        delta_24h = comps.get("dynamic_instability", {}).get("abs_delta_24h", 0.0)
        if instability >= 0.35:
            supporting.append(EvidenceItem(
                source="INTER_CYCLE_INSTABILITY",
                direction="INCREASES_RISK",
                strength=instability,
                confidence=0.80,
                summary=f"Recent inter-cycle forecast revisions (24h delta={delta_24h:.1f}) signal initialization volatility.",
                metric_value=round(delta_24h, 2),
            ))

        # 4. Historical Analogue Support
        if retrieval_res.get("support_status") == "SUFFICIENT_SUPPORT":
            hist_bust_rate = retrieval_res.get("historical_bust_rate", 0.0)
            k_analogues = retrieval_res.get("analogue_count", 0)
            sim = retrieval_res.get("mean_similarity", 0.8)
            if hist_bust_rate >= 0.25:
                supporting.append(EvidenceItem(
                    source="HISTORICAL_ANALOGUES",
                    direction="INCREASES_RISK",
                    strength=min(hist_bust_rate * 1.5, 1.0),
                    confidence=min(sim, 0.90),
                    summary=f"{int(hist_bust_rate * 100)}% of {k_analogues} nearest historical analogues experienced verification busts.",
                    metric_value=round(hist_bust_rate, 4),
                ))
            else:
                contradicting.append(EvidenceItem(
                    source="HISTORICAL_ANALOGUES",
                    direction="DECREASES_RISK",
                    strength=1.0 - hist_bust_rate * 2.0,
                    confidence=min(sim, 0.90),
                    summary=f"Historical analogues experienced low failure frequency ({int(hist_bust_rate * 100)}% bust rate).",
                    metric_value=round(hist_bust_rate, 4),
                ))

        # 5. Lead Time Horizon Context
        if lead_hours >= 48:
            supporting.append(EvidenceItem(
                source="LEAD_TIME_HORIZON",
                direction="INCREASES_RISK",
                strength=lead_hours / 72.0,
                confidence=0.95,
                summary=f"Extended lead time ({lead_hours}h) increases physical vulnerability to atmospheric error growth.",
                metric_value=float(lead_hours),
            ))

        # 6. Novelty / OOD Evidence
        nov_state = novelty_res.get("novelty_state", "NORMAL")
        nov_score = novelty_res.get("novelty_score", 1.0)
        if nov_state in ["HIGH", "EXTREME"]:
            supporting.append(EvidenceItem(
                source="FEATURE_NOVELTY",
                direction="INCREASES_RISK",
                strength=0.75 if nov_state == "HIGH" else 0.95,
                confidence=0.70,
                summary=f"Meteorological state exhibits {nov_state} feature novelty (z={nov_score:.2f}) outside training distribution.",
                metric_value=round(nov_score, 2),
            ))

        # 7. Evaluate Evidence Conflict
        conflict_score = self._compute_conflict_score(supporting, contradicting, eff_prob, aleatoric, retrieval_res)

        # 8. Compute Composite Fused Risk Score
        hist_term = retrieval_res.get("historical_bust_rate", eff_prob) if retrieval_res.get("support_status") == "SUFFICIENT_SUPPORT" else eff_prob
        composite_risk = (
            0.50 * eff_prob
            + 0.25 * aleatoric
            + 0.15 * instability
            + 0.10 * float(hist_term)
        )
        fused_score = float(np.clip(composite_risk, 0.0, 1.0))

        return supporting, contradicting, conflict_score, fused_score

    def _compute_conflict_score(
        self,
        supporting: List[EvidenceItem],
        contradicting: List[EvidenceItem],
        eff_prob: float,
        aleatoric: float,
        retrieval_res: Dict[str, Any],
    ) -> float:
        """
        Quantify divergence between supporting and opposing evidence.
        """
        raw_conflict = 0.0

        if supporting and contradicting:
            support_strength = float(np.mean([item.strength for item in supporting]))
            contra_strength = float(np.mean([item.strength for item in contradicting]))
            raw_conflict = float(min(support_strength, contra_strength) * 1.2)

        # Severe specific contradiction: High model risk with extremely tight spread
        if eff_prob >= 0.50 and aleatoric < 0.25:
            raw_conflict = max(raw_conflict, 0.50)

        # Specific severe contradiction: Model is High Risk but Historical Analogues show 0% bust
        if retrieval_res.get("support_status") == "SUFFICIENT_SUPPORT":
            hist_bust = retrieval_res.get("historical_bust_rate", 0.0)
            if eff_prob >= 0.50 and hist_bust == 0.0:
                raw_conflict = max(raw_conflict, 0.65)
            elif eff_prob <= 0.10 and hist_bust >= 0.60:
                raw_conflict = max(raw_conflict, 0.65)

        return float(np.clip(raw_conflict, 0.0, 1.0))

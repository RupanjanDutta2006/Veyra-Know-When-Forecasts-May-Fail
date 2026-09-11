"""
Deterministic Decision Counterfactual Generation Engine (Day 17).

Computes policy-level sensitivity counterfactuals answering:
- 'What would need to change for the operational decision to become less severe?'
- 'What shift would cause the decision to escalate to a higher severity tier?'

Scientific Safeguards:
- Strictly labeled as DECISION_COUNTERFACTUAL (not physical atmospheric causality).
- Grounded directly in Day 15 governed decision policy boundaries and Day 16 temporal thresholds.
"""

from typing import Any, Dict, List, Optional
from evaluation.xai_schema import DecisionCounterfactual


class DecisionCounterfactualGenerator:
    """
    Generates deterministic policy-level counterfactual explanations.
    """

    def __init__(
        self,
        risk_thresholds: tuple = (0.10, 0.22, 0.40, 0.65),
        novelty_abstain_cutoff: float = 2.50,
    ):
        self.t_trust, self.t_monitor, self.t_caution, self.t_warn = risk_thresholds
        self.novelty_abstain_cutoff = novelty_abstain_cutoff

    def generate_counterfactuals(
        self,
        current_decision: str,
        current_risk: float,
        current_confidence: float,
        novelty_score: float = 0.0,
        temporal_slope: float = 0.0,
        ensemble_std: float = 1.0,
        abstention_reason: Optional[str] = None,
    ) -> List[DecisionCounterfactual]:
        """
        Produce deterministic decision counterfactuals.
        """
        counterfactuals: List[DecisionCounterfactual] = []

        # 1. Abstention Counterfactuals
        if current_decision == "ABSTAIN":
            if novelty_score >= self.novelty_abstain_cutoff:
                req_val = round(self.novelty_abstain_cutoff - 0.10, 2)
                shift = round(req_val - novelty_score, 2)
                counterfactuals.append(
                    DecisionCounterfactual(
                        target_decision_direction="LESS_SEVERE",
                        parameter_name="feature_space_novelty",
                        current_value=round(novelty_score, 3),
                        required_value=req_val,
                        required_shift=shift,
                        explanation=(
                            f"If feature novelty dropped from {novelty_score:.2f} to < {self.novelty_abstain_cutoff:.2f}, "
                            f"the system would exit safety abstention and produce an actionable operational decision."
                        ),
                    )
                )
            if current_confidence < 0.30:
                counterfactuals.append(
                    DecisionCounterfactual(
                        target_decision_direction="LESS_SEVERE",
                        parameter_name="risk_confidence",
                        current_value=round(current_confidence, 3),
                        required_value=0.45,
                        required_shift=round(0.45 - current_confidence, 3),
                        explanation=(
                            f"If data quality or ensemble consensus improved confidence from {current_confidence:.2f} to >= 0.45, "
                            f"the safety gate would permit normal decision issuance."
                        ),
                    )
                )
            return counterfactuals

        # 2. De-escalation (Less Severe) Counterfactuals
        if current_decision == "ALERT_CRITICAL_BUST":
            req_risk = round(self.t_warn - 0.01, 3)
            shift = round(req_risk - current_risk, 3)
            counterfactuals.append(
                DecisionCounterfactual(
                    target_decision_direction="LESS_SEVERE",
                    parameter_name="calibrated_bust_probability",
                    current_value=round(current_risk, 3),
                    required_value=req_risk,
                    required_shift=shift,
                    explanation=(
                        f"If calibrated bust probability decreased from {current_risk:.2f} to < {self.t_warn:.2f} "
                        f"(a shift of {shift:+.2f}), the operational action would de-escalate to WARN_POTENTIAL_BUST."
                    ),
                )
            )

        elif current_decision == "WARN_POTENTIAL_BUST":
            req_risk = round(self.t_caution - 0.01, 3)
            shift = round(req_risk - current_risk, 3)
            counterfactuals.append(
                DecisionCounterfactual(
                    target_decision_direction="LESS_SEVERE",
                    parameter_name="calibrated_bust_probability",
                    current_value=round(current_risk, 3),
                    required_value=req_risk,
                    required_shift=shift,
                    explanation=(
                        f"If calibrated bust probability dropped from {current_risk:.2f} to < {self.t_caution:.2f} "
                        f"(a shift of {shift:+.2f}), the action would de-escalate to ADVISE_CAUTION."
                    ),
                )
            )
            if temporal_slope > 0.03:
                counterfactuals.append(
                    DecisionCounterfactual(
                        target_decision_direction="LESS_SEVERE",
                        parameter_name="temporal_risk_velocity",
                        current_value=round(temporal_slope, 3),
                        required_value=0.0,
                        required_shift=round(-temporal_slope, 3),
                        explanation=(
                            f"If the upward risk trend flattened (slope shifting from +{temporal_slope:.3f}/cycle to <= 0.0), "
                            f"the temporal early-warning booster would deactivate."
                        ),
                    )
                )

        elif current_decision == "ADVISE_CAUTION":
            req_risk = round(self.t_monitor - 0.01, 3)
            shift = round(req_risk - current_risk, 3)
            counterfactuals.append(
                DecisionCounterfactual(
                    target_decision_direction="LESS_SEVERE",
                    parameter_name="calibrated_bust_probability",
                    current_value=round(current_risk, 3),
                    required_value=req_risk,
                    required_shift=shift,
                    explanation=(
                        f"If bust probability decreased from {current_risk:.2f} to < {self.t_monitor:.2f}, "
                        f"the system would transition to standard MONITOR status."
                    ),
                )
            )

        elif current_decision == "MONITOR":
            req_risk = round(self.t_trust - 0.01, 3)
            shift = round(req_risk - current_risk, 3)
            counterfactuals.append(
                DecisionCounterfactual(
                    target_decision_direction="LESS_SEVERE",
                    parameter_name="calibrated_bust_probability",
                    current_value=round(current_risk, 3),
                    required_value=req_risk,
                    required_shift=shift,
                    explanation=(
                        f"If bust probability dropped below {self.t_trust:.2f}, "
                        f"the forecast would be designated as fully TRUST_FORECAST."
                    ),
                )
            )

        # 3. Escalation (More Severe) Counterfactuals
        if current_decision in ("TRUST_FORECAST", "MONITOR", "ADVISE_CAUTION"):
            req_warn = round(self.t_warn, 3)
            shift_warn = round(req_warn - current_risk, 3)
            counterfactuals.append(
                DecisionCounterfactual(
                    target_decision_direction="MORE_SEVERE",
                    parameter_name="calibrated_bust_probability",
                    current_value=round(current_risk, 3),
                    required_value=req_warn,
                    required_shift=shift_warn,
                    explanation=(
                        f"If bust probability rose from {current_risk:.2f} to >= {self.t_warn:.2f} "
                        f"(a shift of {shift_warn:+.2f}), the system would escalate to WARN_POTENTIAL_BUST."
                    ),
                )
            )

        return counterfactuals

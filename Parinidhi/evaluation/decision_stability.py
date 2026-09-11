"""
Operational Decision Stability & Cycle-to-Cycle Change Analysis (Day 20).

Provides formal change detection and stability classification between consecutive
NWP issue cycles targeting the same atmospheric hazard event.

Scientific Safeguards:
- 100% Deterministic State Transition Modeling: Formal mathematical differentials on risk,
  confidence, severity, and urgency.
- Explicit INSUFFICIENT_HISTORY Handling: Clear boundaries when $< 2$ cycles are available.
- Multi-Cycle Oscillation Detection: Identifies noisy inter-cycle model jitter vs true persistent escalation.
"""

from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np

from evaluation.decision_schema import OperationalDecision, WarningPriority
from evaluation.event_schema import EventSeverity, OperationalUrgency
from evaluation.operational_trace_schema import CycleChangeSummary, DecisionStabilityState
from evaluation.trajectory_schema import TrajectoryState
from evaluation.unified_schema import UnifiedOperationalAssessment


DECISION_SEVERITY_ORDER = {
    OperationalDecision.ABSTAIN: -1,
    OperationalDecision.TRUST_FORECAST: 0,
    OperationalDecision.MONITOR: 0,
    OperationalDecision.ADVISE_CAUTION: 1,
    OperationalDecision.WARN_POTENTIAL_BUST: 2,
    OperationalDecision.ALERT_CRITICAL_BUST: 3,
}

URGENCY_ORDER = {
    OperationalUrgency.INSUFFICIENT_CONFIDENCE: -1,
    OperationalUrgency.ROUTINE: 0,
    OperationalUrgency.WATCH: 1,
    OperationalUrgency.URGENT: 2,
    OperationalUrgency.IMMEDIATE: 3,
}


class CycleChangeDetector:
    """
    Computes formal delta and state transitions between consecutive operational assessments.
    """

    @staticmethod
    def compute_change(
        current_assessment: UnifiedOperationalAssessment,
        previous_assessment: Optional[UnifiedOperationalAssessment] = None,
        stability_override: Optional[DecisionStabilityState] = None,
    ) -> CycleChangeSummary:
        """
        Evaluate exact cycle-to-cycle transition between previous and current assessment.
        """
        if previous_assessment is None:
            return CycleChangeSummary(
                previous_decision=None,
                current_decision=current_assessment.operational_decision,
                decision_changed=False,
                risk_delta=0.0,
                confidence_delta=0.0,
                severity_changed=False,
                urgency_changed=False,
                trajectory_state_changed=False,
                escalation_detected=False,
                deescalation_detected=False,
                stability_state=DecisionStabilityState.INSUFFICIENT_HISTORY,
                transition_narrative=f"First cycle evaluation for event (decision: {current_assessment.operational_decision.value}).",
            )

        prev_dec = previous_assessment.operational_decision
        curr_dec = current_assessment.operational_decision
        decision_changed = prev_dec != curr_dec

        risk_delta = float(np.round(current_assessment.calibrated_risk - previous_assessment.calibrated_risk, 4))
        conf_delta = float(np.round(current_assessment.confidence_score - previous_assessment.confidence_score, 4))

        sev_changed = previous_assessment.severity != current_assessment.severity
        urg_changed = previous_assessment.urgency != current_assessment.urgency
        traj_changed = previous_assessment.trajectory_state != current_assessment.trajectory_state

        curr_dec_rank = DECISION_SEVERITY_ORDER.get(curr_dec, 0)
        prev_dec_rank = DECISION_SEVERITY_ORDER.get(prev_dec, 0)

        curr_urg_rank = URGENCY_ORDER.get(current_assessment.urgency, 0)
        prev_urg_rank = URGENCY_ORDER.get(previous_assessment.urgency, 0)

        # Escalation: higher decision tier, higher urgency, or rapid risk velocity
        escalation_detected = (
            curr_dec_rank > prev_dec_rank
            or curr_urg_rank > prev_urg_rank
            or risk_delta >= 0.08
            or current_assessment.trajectory_state == TrajectoryState.ACCELERATING_RISK
        )

        # De-escalation: lower decision tier, lower urgency, or negative risk velocity
        deescalation_detected = (
            curr_dec_rank < prev_dec_rank
            or curr_urg_rank < prev_urg_rank
            or risk_delta <= -0.08
            or current_assessment.trajectory_state == TrajectoryState.REVERSING_RISK
        )

        if stability_override is not None:
            stability_state = stability_override
        elif escalation_detected and not deescalation_detected:
            stability_state = DecisionStabilityState.ESCALATING
        elif deescalation_detected and not escalation_detected:
            stability_state = DecisionStabilityState.DE_ESCALATING
        elif decision_changed:
            stability_state = DecisionStabilityState.OSCILLATING
        else:
            stability_state = DecisionStabilityState.STABLE

        # Narrative construction
        if decision_changed:
            narrative = f"Decision changed from {prev_dec.value} -> {curr_dec.value} (risk delta: {risk_delta:+.3f})."
        elif escalation_detected:
            narrative = f"Risk escalation detected within {curr_dec.value} tier (risk delta: {risk_delta:+.3f})."
        elif deescalation_detected:
            narrative = f"Risk de-escalation detected within {curr_dec.value} tier (risk delta: {risk_delta:+.3f})."
        else:
            narrative = f"Decision maintained as {curr_dec.value} with stable risk (delta: {risk_delta:+.3f})."

        return CycleChangeSummary(
            previous_decision=prev_dec,
            current_decision=curr_dec,
            decision_changed=decision_changed,
            risk_delta=risk_delta,
            confidence_delta=conf_delta,
            severity_changed=sev_changed,
            urgency_changed=urg_changed,
            trajectory_state_changed=traj_changed,
            escalation_detected=escalation_detected,
            deescalation_detected=deescalation_detected,
            stability_state=stability_state,
            transition_narrative=narrative,
        )


class DecisionStabilityAnalyzer:
    """
    Evaluates rolling historical decision sequences to classify longitudinal stability.
    """

    @staticmethod
    def analyze_sequence_stability(
        calibrated_risks: Sequence[float],
        decisions: Sequence[OperationalDecision],
    ) -> DecisionStabilityState:
        """
        Classify stability across a chronological sequence of cycles.
        """
        n = len(calibrated_risks)
        if n < 2:
            return DecisionStabilityState.INSUFFICIENT_HISTORY

        deltas = [calibrated_risks[i] - calibrated_risks[i - 1] for i in range(1, n)]

        # Check for systematic escalation (strictly non-negative deltas with at least one significant increase)
        if all(d >= -0.02 for d in deltas) and sum(deltas) >= 0.08:
            return DecisionStabilityState.ESCALATING

        # Check for systematic de-escalation
        if all(d <= 0.02 for d in deltas) and sum(deltas) <= -0.08:
            return DecisionStabilityState.DE_ESCALATING

        # Check for sign reversals (oscillations)
        sign_changes = 0
        for i in range(1, len(deltas)):
            if (deltas[i] > 0.04 and deltas[i - 1] < -0.04) or (deltas[i] < -0.04 and deltas[i - 1] > 0.04):
                sign_changes += 1

        if sign_changes >= 1:
            return DecisionStabilityState.OSCILLATING

        # Check if decisions have changed multiple times
        decision_changes = sum(1 for i in range(1, len(decisions)) if decisions[i] != decisions[i - 1])
        if decision_changes >= 2:
            return DecisionStabilityState.OSCILLATING

        return DecisionStabilityState.STABLE

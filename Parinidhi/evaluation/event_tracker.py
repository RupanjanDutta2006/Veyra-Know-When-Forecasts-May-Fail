"""
Operational Event Lifecycle State Machine & Longitudinal Tracker (Day 18).

Maintains continuous, auditable event lifecycles across successive NWP issue cycles,
preventing event fragmentation, chatter, and duplicate alert generation.

Scientific Safeguards:
- 100% deterministic state transitions and canonical identity generation.
- Strict anti-leakage audit rejecting verification columns at decision time.
- Transparent mathematical definitions for dimensionless severity and operational urgency.
"""

import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from evaluation.event_schema import (
    EventLifecycleState,
    EventSeverity,
    EventStateTransition,
    EventTrajectorySnapshot,
    OperationalEvent,
    OperationalUrgency,
)
from features.contract import UNAVAILABLE_UNTIL_VERIFICATION, validate_feature_contract


class EventLifecycleStateMachine:
    """
    Deterministic finite state machine governing longitudinal event progression.
    Incorporates operational hysteresis and transition rules.
    """

    def __init__(
        self,
        risk_emerging_threshold: float = 0.20,
        risk_escalating_threshold: float = 0.40,
        risk_critical_threshold: float = 0.65,
        velocity_escalating_threshold: float = 0.05,
        cooldown_cycles: int = 1,
    ):
        self.risk_emerging_threshold = risk_emerging_threshold
        self.risk_escalating_threshold = risk_escalating_threshold
        self.risk_critical_threshold = risk_critical_threshold
        self.velocity_escalating_threshold = velocity_escalating_threshold
        self.cooldown_cycles = cooldown_cycles

    def compute_severity(
        self,
        calibrated_risk: float,
        ensemble_std: float,
        novelty_score: float,
        instability_detected: bool,
    ) -> Tuple[EventSeverity, float]:
        """
        Compute dimensionless event severity score in [0, 1] and assign severity tier.

        Formula:
        S = clip(0.40*risk + 0.25*min(1.0, std/4.0) + 0.20*min(1.0, nov/3.0) + 0.15*instab, 0.0, 1.0)
        """
        r = float(np.nan_to_num(calibrated_risk, nan=0.0, posinf=1.0, neginf=0.0))
        r = float(np.clip(r, 0.0, 1.0))

        std_val = float(np.nan_to_num(ensemble_std, nan=0.0, posinf=4.0, neginf=0.0))
        std_norm = float(np.clip(std_val / 4.0, 0.0, 1.0))

        nov_val = float(np.nan_to_num(novelty_score, nan=1.0, posinf=3.0, neginf=0.0))
        nov_norm = float(np.clip(nov_val / 3.0, 0.0, 1.0))

        instab_val = 1.0 if instability_detected else 0.0

        score = float(np.clip(0.40 * r + 0.25 * std_norm + 0.20 * nov_norm + 0.15 * instab_val, 0.0, 1.0))
        score = round(score, 4)

        if score >= 0.75:
            sev = EventSeverity.EXTREME
        elif score >= 0.50:
            sev = EventSeverity.SEVERE
        elif score >= 0.25:
            sev = EventSeverity.MODERATE
        else:
            sev = EventSeverity.LOW

        return sev, score

    def compute_urgency(
        self,
        calibrated_risk: float,
        risk_velocity: float,
        lead_hours: float,
        time_to_critical_hours: Optional[float],
        confidence: float,
        novelty_score: float,
    ) -> OperationalUrgency:
        """
        Determine operational urgency tier based on time-to-critical risk and kinematics.
        """
        # Safety override for OOD / extreme uncertainty
        if confidence < 0.25 or novelty_score >= 2.50:
            return OperationalUrgency.INSUFFICIENT_CONFIDENCE

        # Immediate tier
        if (time_to_critical_hours is not None and time_to_critical_hours <= 12.0 and calibrated_risk >= 0.50) or (lead_hours <= 12.0 and calibrated_risk >= 0.60):
            return OperationalUrgency.IMMEDIATE

        # Urgent tier
        if (time_to_critical_hours is not None and time_to_critical_hours <= 24.0) or (calibrated_risk >= 0.40 and risk_velocity > 0.0) or (lead_hours <= 24.0 and calibrated_risk >= 0.50):
            return OperationalUrgency.URGENT

        # Watch tier
        if (time_to_critical_hours is not None and time_to_critical_hours <= 48.0) or (calibrated_risk >= 0.20):
            return OperationalUrgency.WATCH

        # Routine baseline
        return OperationalUrgency.ROUTINE

    def evaluate_transition(
        self,
        current_state: EventLifecycleState,
        current_risk: float,
        risk_velocity: float,
        lead_hours: float,
        operational_decision: str,
        is_abstained: bool = False,
    ) -> Tuple[EventLifecycleState, str]:
        """
        Evaluate deterministic state transition for the current cycle.
        """
        if is_abstained or operational_decision == "ABSTAIN":
            return EventLifecycleState.ABSTAINED, "Safety constraint / novelty triggered abstention"

        # If previous state was ABSTAINED, allow re-entry if decision is no longer ABSTAIN
        if current_state == EventLifecycleState.ABSTAINED:
            if current_risk >= self.risk_critical_threshold:
                return EventLifecycleState.CRITICAL, "Re-entered from abstention into critical tier"
            elif current_risk >= self.risk_escalating_threshold:
                return EventLifecycleState.ESCALATING, "Re-entered from abstention into escalating tier"
            elif current_risk >= self.risk_emerging_threshold:
                return EventLifecycleState.EMERGING, "Re-entered from abstention into emerging tier"
            else:
                return EventLifecycleState.NORMAL, "Re-entered from abstention into normal surveillance"

        # 1. CRITICAL Tier Evaluation
        if current_risk >= self.risk_critical_threshold or operational_decision in ("ALERT_CRITICAL_BUST", "ALERT"):
            if current_state != EventLifecycleState.CRITICAL:
                return EventLifecycleState.CRITICAL, f"Calibrated risk {current_risk:.2%} crossed critical threshold {self.risk_critical_threshold:.2%}"
            return EventLifecycleState.CRITICAL, "Maintained critical status"

        if current_state == EventLifecycleState.CRITICAL:
            # Hysteresis buffer: de-escalate only if risk drops below 0.55 and velocity <= 0
            if current_risk < 0.55 and risk_velocity <= 0.0:
                return EventLifecycleState.STABILIZING, f"De-escalated from critical (risk={current_risk:.2%})"
            return EventLifecycleState.CRITICAL, "Maintained critical status (anti-chatter buffer)"

        # 2. ESCALATING Tier Evaluation
        if current_risk >= self.risk_escalating_threshold or risk_velocity >= self.velocity_escalating_threshold:
            if current_state in (EventLifecycleState.NORMAL, EventLifecycleState.EMERGING, EventLifecycleState.RESOLVED):
                return EventLifecycleState.ESCALATING, f"Risk {current_risk:.2%} or velocity {risk_velocity:+.3f}/cycle triggered escalation"
            return EventLifecycleState.ESCALATING, "Maintained escalating active state"

        if current_state == EventLifecycleState.ESCALATING:
            # Hysteresis buffer: de-escalate only if risk drops below 0.35 and velocity <= 0
            if current_risk < 0.35 and risk_velocity <= 0.0:
                return EventLifecycleState.STABILIZING, f"De-escalated from escalating (risk={current_risk:.2%})"
            return EventLifecycleState.ESCALATING, "Maintained escalating status (anti-chatter buffer)"

        # 3. EMERGING Tier Evaluation
        if current_risk >= self.risk_emerging_threshold or operational_decision in ("ADVISE_CAUTION", "WARN_POTENTIAL_BUST"):
            if current_state in (EventLifecycleState.NORMAL, EventLifecycleState.RESOLVED):
                return EventLifecycleState.EMERGING, f"Initial risk emergence detected (risk={current_risk:.2%})"
            elif current_state == EventLifecycleState.STABILIZING and risk_velocity > 0.05:
                return EventLifecycleState.ESCALATING, "Re-escalation detected from stabilizing phase"
            return current_state, "Maintained active surveillance"

        # 4. RESOLVED / NORMAL Baseline Evaluation
        if current_risk < self.risk_emerging_threshold:
            if current_state in (EventLifecycleState.CRITICAL, EventLifecycleState.ESCALATING, EventLifecycleState.STABILIZING):
                return EventLifecycleState.RESOLVED, f"Hazard dissipated below threshold (risk={current_risk:.2%})"
            elif current_state == EventLifecycleState.EMERGING:
                return EventLifecycleState.RESOLVED, "Emerging anomaly subsided without escalation"
            return EventLifecycleState.NORMAL, "Normal baseline surveillance"

        return current_state, "No transition condition met"


FORBIDDEN_VERIFICATION_COLUMNS = {
    "truth_value", "truth_unit", "truth_source", "forecast_error", "forecast_abs_error",
    "ensemble_mean_error", "ensemble_mean_abs_error", "bust_label", "is_bust", "bust_label_q95",
    "target", "actual", "realized", "ground_truth", "error", "obs_value"
}


class OperationalEventTracker:
    """
    Longitudinal event tracker maintaining canonical identity and continuity across cycles.
    """

    def __init__(self, state_machine: Optional[EventLifecycleStateMachine] = None):
        self.state_machine = state_machine or EventLifecycleStateMachine()
        self.active_events: Dict[str, OperationalEvent] = {}
        self.duplicate_update_count: int = 0
        self.total_update_count: int = 0

    @staticmethod
    def derive_canonical_event_id(location_id: str, variable: str, valid_time_utc: str) -> str:
        """
        Generate deterministic 16-character SHA-256 canonical event identity.
        """
        raw_key = f"event:{str(location_id).lower().strip()}:{str(variable).lower().strip()}:{str(valid_time_utc).strip()}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]

    def process_cycle_update(
        self,
        location_id: str,
        variable: str,
        valid_time_utc: str,
        issue_time_utc: str,
        lead_hours: float,
        forecast_value: float,
        ensemble_mean: float,
        ensemble_std: float,
        calibrated_risk: float,
        novelty_score: float = 1.0,
        instability_detected: bool = False,
        operational_decision: str = "MONITOR",
        warning_priority: str = "P4_INFORMATIONAL",
        confidence: float = 0.80,
        time_to_critical_hours: Optional[float] = None,
        risk_velocity: Optional[float] = None,
        is_abstained: bool = False,
        raw_features: Optional[Dict[str, Any]] = None,
    ) -> OperationalEvent:
        """
        Ingest a single forecast cycle update and update or create the corresponding OperationalEvent.
        """
        self.total_update_count += 1

        # 1. Anti-leakage validation
        if raw_features is not None:
            violations = [
                k for k in raw_features.keys()
                if k.strip().lower() in FORBIDDEN_VERIFICATION_COLUMNS or any(
                    term in k.strip().lower() for term in ("truth", "error", "bust_label", "is_bust")
                )
            ]
            if violations:
                raise ValueError(f"Target leakage rejected in decision-time event update: {violations}")

        loc_clean = str(location_id).lower().strip()
        var_clean = str(variable).lower().strip()
        v_time_clean = str(valid_time_utc).strip()
        i_time_clean = str(issue_time_utc).strip()

        # Sanitize numerical inputs
        forecast_value = float(np.nan_to_num(forecast_value, nan=0.0, posinf=9999.0, neginf=-9999.0))
        ensemble_mean = float(np.nan_to_num(ensemble_mean, nan=0.0, posinf=9999.0, neginf=-9999.0))
        ensemble_std = float(np.nan_to_num(ensemble_std, nan=0.0, posinf=9999.0, neginf=0.0))
        calibrated_risk = float(np.nan_to_num(calibrated_risk, nan=0.0, posinf=1.0, neginf=0.0))
        calibrated_risk = float(np.clip(calibrated_risk, 0.0, 1.0))
        novelty_score = float(np.nan_to_num(novelty_score, nan=1.0, posinf=99.0, neginf=0.0))
        confidence = float(np.nan_to_num(confidence, nan=0.5, posinf=1.0, neginf=0.0))
        lead_hours = float(np.nan_to_num(lead_hours, nan=0.0, posinf=999.0, neginf=0.0))

        event_id = self.derive_canonical_event_id(loc_clean, var_clean, v_time_clean)

        # 2. Check if event already exists
        if event_id in self.active_events:
            event = self.active_events[event_id]

            # Check for duplicate cycle update
            existing_cycle_times = {s.issue_time_utc for s in event.snapshots}
            if i_time_clean in existing_cycle_times:
                self.duplicate_update_count += 1
                return event  # Deterministic idempotent suppression
        else:
            # Create new initial event
            sev_initial, sev_score_initial = self.state_machine.compute_severity(
                calibrated_risk=calibrated_risk,
                ensemble_std=ensemble_std,
                novelty_score=novelty_score,
                instability_detected=instability_detected,
            )
            urg_initial = self.state_machine.compute_urgency(
                calibrated_risk=calibrated_risk,
                risk_velocity=0.0,
                lead_hours=lead_hours,
                time_to_critical_hours=time_to_critical_hours,
                confidence=confidence,
                novelty_score=novelty_score,
            )
            event = OperationalEvent(
                event_id=event_id,
                location_id=loc_clean,
                variable=var_clean,
                valid_time_utc=v_time_clean,
                first_detection_time_utc=i_time_clean,
                latest_update_time_utc=i_time_clean,
                current_risk=round(calibrated_risk, 4),
                peak_risk=round(calibrated_risk, 4),
                initial_risk=round(calibrated_risk, 4),
                lifecycle_state=EventLifecycleState.NORMAL,
                severity=sev_initial,
                severity_score=sev_score_initial,
                urgency=urg_initial,
                confidence=round(confidence, 4),
                novelty_score=round(novelty_score, 3),
                instability_detected=instability_detected,
                current_decision=operational_decision,
                current_warning_priority=warning_priority,
                cycles_tracked=0,
                warning_cycles_count=0,
            )
            self.active_events[event_id] = event

        # 3. Calculate empirical velocity if not explicitly provided
        if risk_velocity is None:
            if len(event.snapshots) >= 1:
                prev_risk = event.snapshots[-1].calibrated_risk
                risk_velocity = float(calibrated_risk - prev_risk)
            else:
                risk_velocity = 0.0

        # 4. Compute severity & urgency
        severity, severity_score = self.state_machine.compute_severity(
            calibrated_risk=calibrated_risk,
            ensemble_std=ensemble_std,
            novelty_score=novelty_score,
            instability_detected=instability_detected,
        )
        urgency = self.state_machine.compute_urgency(
            calibrated_risk=calibrated_risk,
            risk_velocity=risk_velocity,
            lead_hours=lead_hours,
            time_to_critical_hours=time_to_critical_hours,
            confidence=confidence,
            novelty_score=novelty_score,
        )

        # 5. Evaluate state transition
        next_state, transition_trigger = self.state_machine.evaluate_transition(
            current_state=event.lifecycle_state,
            current_risk=calibrated_risk,
            risk_velocity=risk_velocity,
            lead_hours=lead_hours,
            operational_decision=operational_decision,
            is_abstained=is_abstained,
        )

        # If transition occurred, record state transition object
        if next_state != event.lifecycle_state or len(event.snapshots) == 0:
            transition_obj = EventStateTransition(
                from_state=event.lifecycle_state,
                to_state=next_state,
                trigger=transition_trigger,
                cycle_index=len(event.snapshots) + 1,
                issue_time_utc=i_time_clean,
                risk_at_transition=round(calibrated_risk, 4),
                supporting_metrics={
                    "risk_velocity": round(risk_velocity, 4),
                    "ensemble_std": round(ensemble_std, 3),
                    "lead_hours": round(lead_hours, 1),
                    "severity_score": severity_score,
                },
                provenance_hash=hashlib.sha256(f"{event.event_id}:{next_state.value}:{i_time_clean}".encode("utf-8")).hexdigest()[:16],
            )
            event.state_transitions.append(transition_obj)
            event.lifecycle_state = next_state

        # 6. Append and chronologically sort snapshots
        snapshot_obj = EventTrajectorySnapshot(
            cycle_index=len(event.snapshots) + 1,
            issue_time_utc=i_time_clean,
            lead_hours=round(lead_hours, 1),
            forecast_value=round(forecast_value, 3),
            ensemble_mean=round(ensemble_mean, 3),
            ensemble_std=round(ensemble_std, 3),
            calibrated_risk=round(calibrated_risk, 4),
            novelty_score=round(novelty_score, 3),
            instability_detected=instability_detected,
            operational_decision=operational_decision,
            warning_priority=warning_priority,
            urgency=urgency,
            decision_provenance_hash=hashlib.sha256(f"{event.event_id}:{calibrated_risk:.4f}:{i_time_clean}".encode("utf-8")).hexdigest()[:16],
        )
        event.snapshots.append(snapshot_obj)
        # Chronological sort ensures input reordering invariance
        event.snapshots.sort(key=lambda s: s.issue_time_utc)
        for idx, s in enumerate(event.snapshots):
            s.cycle_index = idx + 1

        # 7. Update aggregate metrics
        event.first_detection_time_utc = event.snapshots[0].issue_time_utc
        event.latest_update_time_utc = event.snapshots[-1].issue_time_utc
        event.current_risk = round(calibrated_risk, 4)
        event.peak_risk = round(max(s.calibrated_risk for s in event.snapshots), 4)
        event.severity = severity
        event.severity_score = severity_score
        event.urgency = urgency
        event.confidence = round(confidence, 4)
        event.novelty_score = round(novelty_score, 3)
        event.instability_detected = instability_detected
        event.current_decision = operational_decision
        event.current_warning_priority = warning_priority
        event.cycles_tracked = len(event.snapshots)
        event.warning_cycles_count = sum(
            1 for s in event.snapshots if "WARN" in s.operational_decision or "ALERT" in s.operational_decision
        )

        # 8. Recompute dual provenance hashes
        event.decision_provenance_hash = event.compute_decision_provenance()
        event.execution_provenance_hash = event.compute_execution_provenance()

        return event

    def get_event(self, event_id: str) -> Optional[OperationalEvent]:
        """Retrieve an operational event by canonical identifier."""
        return self.active_events.get(event_id)

    def get_all_events(self) -> List[OperationalEvent]:
        """Retrieve all currently tracked operational events."""
        return list(self.active_events.values())

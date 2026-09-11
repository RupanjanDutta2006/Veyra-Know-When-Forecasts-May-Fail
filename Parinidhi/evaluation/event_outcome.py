"""
Operational Event Outcome Evaluator & Performance Metrics (Day 18).

Evaluates post-hoc verification outcomes at the event level, computing longitudinal
event detection rates, warning lead-time distributions, lifecycle stability, and
normalized operational utility differences.

Scientific Safeguards:
- Strict structural isolation: outcome evaluation never modifies decision-time event state or decision provenance.
- Small-sample safeguards returning explicit INSUFFICIENT_SAMPLE_SIZE status when N < 5.
- Mathematically defensible event cost accounting based on Day 15 normalized cost parameters.
"""

from decimal import Decimal, ROUND_HALF_UP
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from evaluation.event_schema import (
    EventEvaluationMetrics,
    EventLifecycleState,
    EventOutcome,
    EventOutcomeStatus,
    OperationalEvent,
)


class EventOutcomeEvaluator:
    """
    Orchestrates post-hoc event verification and population-level metric evaluation.
    """

    DEFAULT_BUST_THRESHOLDS = {
        "surface_pressure": 2.0,  # hPa
        "temperature_2m": 2.5,     # K / °C
        "wind_speed_10m": 6.0,     # m/s
    }

    def __init__(
        self,
        cost_bust_direct_loss: float = 0.37,
        cost_mitigation_action: float = 0.08,
        cost_false_alarm_inspection: float = 0.26,
        cost_abstention_contingency: float = 0.15,
    ):
        self.cost_bust_direct_loss = cost_bust_direct_loss
        self.cost_mitigation_action = cost_mitigation_action
        self.cost_false_alarm_inspection = cost_false_alarm_inspection
        self.cost_abstention_contingency = cost_abstention_contingency

    def attach_event_outcome(
        self,
        event: OperationalEvent,
        truth_value: float,
        bust_threshold: Optional[float] = None,
        verification_time_utc: Optional[str] = None,
    ) -> EventOutcome:
        """
        Evaluate and attach post-hoc verification outcome to an event.
        Does NOT alter decision_provenance_hash.
        """
        if bust_threshold is None:
            bust_threshold = self.DEFAULT_BUST_THRESHOLDS.get(event.variable, 2.0)

        v_time = verification_time_utc or event.valid_time_utc

        # Use latest snapshot forecast value
        latest_fcst = event.snapshots[-1].forecast_value if event.snapshots else event.initial_risk
        error = float(latest_fcst - truth_value)
        abs_error = float(abs(error))
        is_bust = bool(abs_error >= bust_threshold)

        total_warnings = event.warning_cycles_count
        was_abstained = (event.lifecycle_state == EventLifecycleState.ABSTAINED)

        # First warning lead time
        lead_time_first_warning: Optional[float] = None
        for s in event.snapshots:
            if "WARN" in s.operational_decision or "ALERT" in s.operational_decision:
                lead_time_first_warning = s.lead_hours
                break

        was_captured = bool(is_bust and total_warnings > 0 and not was_abstained)
        was_false_alarm = bool((not is_bust) and total_warnings > 0 and not was_abstained)
        was_missed = bool(is_bust and total_warnings == 0 and not was_abstained)

        if was_abstained:
            outcome_status = EventOutcomeStatus.ABSTAINED
        elif is_bust:
            outcome_status = EventOutcomeStatus.VERIFIED_BUST
        else:
            outcome_status = EventOutcomeStatus.VERIFIED_ACCURATE

        outcome_hash = hashlib.sha256(
            f"{event.event_id}:{truth_value:.4f}:{abs_error:.4f}:{outcome_status.value}".encode("utf-8")
        ).hexdigest()[:16]

        outcome = EventOutcome(
            event_id=event.event_id,
            valid_time_utc=event.valid_time_utc,
            verified_truth_value=round(truth_value, 4),
            verified_forecast_error=round(error, 4),
            verified_abs_error=round(abs_error, 4),
            is_verified_bust=is_bust,
            outcome_status=outcome_status,
            lead_time_at_first_warning_hours=lead_time_first_warning,
            total_warnings_issued=total_warnings,
            was_captured=was_captured,
            was_false_alarm=was_false_alarm,
            was_missed=was_missed,
            was_abstained=was_abstained,
            verification_time_utc=v_time,
            outcome_provenance_hash=outcome_hash,
        )

        event.retrospective_outcome = outcome
        # Update execution provenance with outcome
        event.execution_provenance_hash = event.compute_execution_provenance()
        return outcome

    def evaluate_events_population(
        self,
        events: List[OperationalEvent],
        total_cycle_updates: Optional[int] = None,
        duplicate_updates: int = 0,
    ) -> EventEvaluationMetrics:
        """
        Compute longitudinal performance and cost metrics across an event population.
        """
        n_events = len(events)
        if n_events == 0:
            return EventEvaluationMetrics(
                total_events=0,
                total_verified_bust_events=0,
                total_accurate_events=0,
                captured_bust_events=0,
                missed_bust_events=0,
                false_alarm_events=0,
                abstained_events=0,
                event_detection_rate=0.0,
                event_warning_precision=0.0,
                event_miss_rate=0.0,
                event_false_alarm_rate=0.0,
                median_lead_time_hours=None,
                p90_lead_time_hours=None,
                event_fragmentation_rate=0.0,
                duplicate_event_rate=0.0,
                mean_state_transitions_per_event=0.0,
                lifecycle_stability_score=1.0,
                event_policy_cost=0.0,
                passive_baseline_cost=0.0,
                utility_difference=0.0,
                sample_size_status="INSUFFICIENT_SAMPLE_SIZE",
            )

        bust_events = 0
        accurate_events = 0
        captured_busts = 0
        missed_busts = 0
        false_alarms = 0
        abstained_events = 0
        lead_times: List[float] = []
        transitions_counts: List[int] = []

        total_policy_cost = Decimal("0.0")
        total_passive_cost = Decimal("0.0")

        c_loss = Decimal(str(self.cost_bust_direct_loss))
        c_action = Decimal(str(self.cost_mitigation_action))
        c_fa = Decimal(str(self.cost_false_alarm_inspection))
        c_abs = Decimal(str(self.cost_abstention_contingency))

        for ev in events:
            transitions_counts.append(len(ev.state_transitions))
            outcome = ev.retrospective_outcome

            if outcome is None:
                continue

            if outcome.was_abstained:
                abstained_events += 1
                total_policy_cost += c_abs
                if outcome.is_verified_bust:
                    bust_events += 1
                    total_passive_cost += c_loss
                else:
                    accurate_events += 1
                continue

            if outcome.is_verified_bust:
                bust_events += 1
                total_passive_cost += c_loss
                if outcome.was_captured:
                    captured_busts += 1
                    total_policy_cost += c_action
                    if outcome.lead_time_at_first_warning_hours is not None:
                        lead_times.append(outcome.lead_time_at_first_warning_hours)
                else:
                    missed_busts += 1
                    total_policy_cost += c_loss
            else:
                accurate_events += 1
                if outcome.was_false_alarm:
                    false_alarms += 1
                    total_policy_cost += c_fa

        # Calculate performance metrics
        detection_rate = float(captured_busts / bust_events) if bust_events > 0 else 0.0
        precision = float(captured_busts / (captured_busts + false_alarms)) if (captured_busts + false_alarms) > 0 else 0.0
        miss_rate = float(missed_busts / bust_events) if bust_events > 0 else 0.0
        fa_rate = float(false_alarms / accurate_events) if accurate_events > 0 else 0.0

        median_lead = float(np.median(lead_times)) if lead_times else None
        p90_lead = float(np.percentile(lead_times, 90)) if lead_times else None

        tot_updates = total_cycle_updates or sum(ev.cycles_tracked for ev in events)
        dup_rate = float(duplicate_updates / tot_updates) if tot_updates > 0 else 0.0

        # Fragmentation check: single-cycle events that should have been connected
        single_cycle_events = sum(1 for ev in events if ev.cycles_tracked == 1)
        fragmentation_rate = float(single_cycle_events / n_events) if n_events > 0 else 0.0

        mean_transitions = float(np.mean(transitions_counts)) if transitions_counts else 0.0
        # Stability score: penalizes excess churn
        stability_score = max(0.0, 1.0 - (mean_transitions / 10.0))

        cost_policy_float = float(total_policy_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        cost_passive_float = float(total_passive_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        utility_diff = round(cost_passive_float - cost_policy_float, 2)

        status_sample = "VALID_SAMPLE"
        if n_events < 5 or bust_events < 2:
            status_sample = "INSUFFICIENT_SAMPLE_SIZE"

        return EventEvaluationMetrics(
            total_events=n_events,
            total_verified_bust_events=bust_events,
            total_accurate_events=accurate_events,
            captured_bust_events=captured_busts,
            missed_bust_events=missed_busts,
            false_alarm_events=false_alarms,
            abstained_events=abstained_events,
            event_detection_rate=round(detection_rate, 4),
            event_warning_precision=round(precision, 4),
            event_miss_rate=round(miss_rate, 4),
            event_false_alarm_rate=round(fa_rate, 4),
            median_lead_time_hours=round(median_lead, 1) if median_lead is not None else None,
            p90_lead_time_hours=round(p90_lead, 1) if p90_lead is not None else None,
            event_fragmentation_rate=round(fragmentation_rate, 4),
            duplicate_event_rate=round(dup_rate, 4),
            mean_state_transitions_per_event=round(mean_transitions, 2),
            lifecycle_stability_score=round(stability_score, 4),
            event_policy_cost=cost_policy_float,
            passive_baseline_cost=cost_passive_float,
            utility_difference=utility_diff,
            sample_size_status=status_sample,
        )

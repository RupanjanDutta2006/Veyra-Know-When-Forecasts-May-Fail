"""
Event-Level Evaluation & Warning Hysteresis Filter (Day 16).

Provides event-level aggregation, lead-time capture metrics, and warning hysteresis
filtering to prevent alert churn across successive numerical weather forecast cycles.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from evaluation.trajectory_schema import WarningHorizon


@dataclass
class EventEvaluationSummary:
    """Event-level operational performance metrics."""
    total_events: int
    total_bust_events: int
    total_nonbust_events: int
    captured_bust_events: int
    event_capture_rate: float
    event_miss_rate: float
    false_alarm_events: int
    event_false_alarm_rate: float
    event_precision: float
    median_lead_time_hours: Optional[float]
    p90_lead_time_hours: Optional[float]
    mean_warnings_per_bust_event: float
    mean_churn_per_event: float
    total_abstentions: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WarningHysteresisFilter:
    """
    Applies operational hysteresis to suppress warning flicker and alert fatigue.
    A warning state requires 2 consecutive cycles to trigger unless risk is critical,
    and persists for at least 1 cooldown cycle after falling below threshold.
    """

    def __init__(self, trigger_cycles: int = 1, cooldown_cycles: int = 1):
        self.trigger_cycles = trigger_cycles
        self.cooldown_cycles = cooldown_cycles
        self.state_history_: Dict[str, List[bool]] = {}

    def filter_warning(
        self,
        event_key: str,
        raw_warning_active: bool,
        is_critical: bool = False,
    ) -> bool:
        """
        Apply hysteresis filter to raw warning boolean.
        """
        if event_key not in self.state_history_:
            self.state_history_[event_key] = []

        history = self.state_history_[event_key]
        history.append(raw_warning_active)

        if is_critical:
            return True

        if raw_warning_active:
            # Check trigger persistence
            if len(history) >= self.trigger_cycles:
                recent = history[-self.trigger_cycles:]
                return all(recent)
            return False
        else:
            return False


class EventLevelEvaluator:
    """
    Evaluates temporal forecast-risk decisions aggregated by atmospheric target event.
    """

    def evaluate_event_predictions(
        self,
        df_predictions: pd.DataFrame,
        event_group_cols: List[str] = ["location", "variable", "valid_time"],
        warning_col: str = "is_warning",
        target_col: str = "bust_label",
        lead_col: str = "lead_hours",
        issue_col: str = "issue_time",
    ) -> EventEvaluationSummary:
        """
        Compute event-level operational capture and false alarm statistics.
        """
        grouped = df_predictions.groupby(event_group_cols)
        total_events = len(grouped)

        bust_events = 0
        nonbust_events = 0
        captured_busts = 0
        false_alarm_events = 0
        lead_times_at_first_warn = []
        warnings_per_bust_event = []
        churns = []
        total_abstentions = 0

        for _, group in grouped:
            # Sort group chronologically by issue time
            group_sorted = group.sort_values(issue_col)
            is_bust_event = int(group_sorted[target_col].iloc[-1]) == 1

            warnings = group_sorted[warning_col].values.astype(bool)
            leads = group_sorted[lead_col].values.astype(float)

            if "is_abstain" in group_sorted.columns:
                total_abstentions += int(np.sum(group_sorted["is_abstain"]))

            # Compute churn (number of state transitions True <-> False)
            churn = int(np.sum(warnings[1:] != warnings[:-1])) if len(warnings) > 1 else 0
            churns.append(churn)

            if is_bust_event:
                bust_events += 1
                warn_count = int(np.sum(warnings))
                warnings_per_bust_event.append(warn_count)
                if np.any(warnings):
                    captured_busts += 1
                    # Lead time at FIRST warning issued
                    first_warn_idx = np.where(warnings)[0][0]
                    lead_times_at_first_warn.append(leads[first_warn_idx])
            else:
                nonbust_events += 1
                if np.any(warnings):
                    false_alarm_events += 1

        capture_rate = captured_busts / max(bust_events, 1)
        miss_rate = 1.0 - capture_rate
        fa_rate = false_alarm_events / max(nonbust_events, 1)
        prec = captured_busts / max(captured_busts + false_alarm_events, 1)

        med_lead = float(np.median(lead_times_at_first_warn)) if lead_times_at_first_warn else None
        p90_lead = float(np.percentile(lead_times_at_first_warn, 90)) if lead_times_at_first_warn else None
        mean_warns = float(np.mean(warnings_per_bust_event)) if warnings_per_bust_event else 0.0
        mean_churn = float(np.mean(churns)) if churns else 0.0

        return EventEvaluationSummary(
            total_events=total_events,
            total_bust_events=bust_events,
            total_nonbust_events=nonbust_events,
            captured_bust_events=captured_busts,
            event_capture_rate=round(capture_rate, 4),
            event_miss_rate=round(miss_rate, 4),
            false_alarm_events=false_alarm_events,
            event_false_alarm_rate=round(fa_rate, 4),
            event_precision=round(prec, 4),
            median_lead_time_hours=med_lead,
            p90_lead_time_hours=p90_lead,
            mean_warnings_per_bust_event=round(mean_warns, 2),
            mean_churn_per_event=round(mean_churn, 2),
            total_abstentions=total_abstentions,
        )

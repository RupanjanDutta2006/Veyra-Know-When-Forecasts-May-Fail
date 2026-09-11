"""
Master Operational Risk Intelligence & Event Orchestration Engine (Day 18).

Orchestrates longitudinal hazard tracking, event memory retrieval, lifecycle state
machines, operational urgency assessment, and post-hoc verification evaluation.

Scientific Architecture:
- Coordinates OperationalEventTracker, EventMemoryStore, and EventOutcomeEvaluator.
- Dual-mode support: DECISION_TIME (strict anti-leakage) vs POST_HOC_EVALUATION.
- Generates structured event summaries and longitudinal audit logs.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from evaluation.event_memory import EventMemoryStore
from evaluation.event_outcome import EventOutcomeEvaluator
from evaluation.event_schema import (
    EventEvaluationMetrics,
    EventLifecycleState,
    EventOutcome,
    EventSeverity,
    EventSimilarityMatch,
    OperationalEvent,
    OperationalUrgency,
)
from evaluation.event_tracker import (
    EventLifecycleStateMachine,
    FORBIDDEN_VERIFICATION_COLUMNS,
    OperationalEventTracker,
)
from evaluation.xai_schema import ExplanationMode
from features.contract import UNAVAILABLE_UNTIL_VERIFICATION, validate_feature_contract


class EventIntelligenceOrchestrator:
    """
    Master operational event intelligence orchestrator.
    """

    def __init__(
        self,
        tracker: Optional[OperationalEventTracker] = None,
        memory_store: Optional[EventMemoryStore] = None,
        outcome_evaluator: Optional[EventOutcomeEvaluator] = None,
    ):
        self.tracker = tracker or OperationalEventTracker()
        self.memory_store = memory_store or EventMemoryStore()
        self.outcome_evaluator = outcome_evaluator or EventOutcomeEvaluator()

    def process_forecast_cycle(
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
        mode: ExplanationMode = ExplanationMode.DECISION_TIME,
        features: Optional[Dict[str, Any]] = None,
        post_hoc_truth: Optional[Dict[str, Any]] = None,
    ) -> OperationalEvent:
        """
        Process a single NWP cycle observation within the longitudinal event tracker.
        """
        # Audit leakage in DECISION_TIME mode
        if mode == ExplanationMode.DECISION_TIME and features is not None:
            violations = [
                k for k in features.keys()
                if k.strip().lower() in FORBIDDEN_VERIFICATION_COLUMNS or any(
                    term in k.strip().lower() for term in ("truth", "error", "bust_label", "is_bust")
                )
            ]
            if violations:
                raise ValueError(f"Target leakage rejected in DECISION_TIME event ingestion: {violations}")

        event = self.tracker.process_cycle_update(
            location_id=location_id,
            variable=variable,
            valid_time_utc=valid_time_utc,
            issue_time_utc=issue_time_utc,
            lead_hours=lead_hours,
            forecast_value=forecast_value,
            ensemble_mean=ensemble_mean,
            ensemble_std=ensemble_std,
            calibrated_risk=calibrated_risk,
            novelty_score=novelty_score,
            instability_detected=instability_detected,
            operational_decision=operational_decision,
            warning_priority=warning_priority,
            confidence=confidence,
            time_to_critical_hours=time_to_critical_hours,
            risk_velocity=risk_velocity,
            is_abstained=is_abstained,
            raw_features=features if mode == ExplanationMode.DECISION_TIME else None,
        )

        # Retrieve analogues from memory store
        analogues = self.memory_store.find_analogous_events(event, top_k=3)
        event.analogue_matches = analogues

        # If post-hoc truth provided in POST_HOC_EVALUATION mode, attach outcome
        if mode == ExplanationMode.POST_HOC_EVALUATION and post_hoc_truth is not None:
            t_val = post_hoc_truth.get("truth_value")
            if t_val is not None:
                self.outcome_evaluator.attach_event_outcome(
                    event=event,
                    truth_value=float(t_val),
                    verification_time_utc=post_hoc_truth.get("verification_time_utc"),
                )

        return event

    def render_event_summary(self, event: OperationalEvent) -> str:
        """
        Produce a concise, human-readable operational event briefing.
        """
        lines = [
            f"=== [VEYRA OPERATIONAL EVENT BRIEFING] ===",
            f"Event ID: {event.event_id} | Location: {event.location_id} | Variable: {event.variable}",
            f"Target Valid Time: {event.valid_time_utc} (Tracking Cycles: {event.cycles_tracked})",
            f"Lifecycle State: {event.lifecycle_state.value} | Severity: {event.severity.value} ({event.severity_score:.2f}) | Urgency: {event.urgency.value}",
            f"Current Risk: {event.current_risk:.1%} (Peak Risk: {event.peak_risk:.1%}) | Decision: {event.current_decision} ({event.current_warning_priority})",
            f"Confidence: {event.confidence:.1%} | Novelty: {event.novelty_score:.2f} | Instability: {event.instability_detected}",
            f"State Transitions: {len(event.state_transitions)} | Warnings Issued: {event.warning_cycles_count} cycles",
            f"Decision Provenance: {event.decision_provenance_hash} | Execution Hash: {event.execution_provenance_hash}",
        ]
        if event.analogue_matches:
            top_m = event.analogue_matches[0]
            lines.append(f"Historical Analogue: {top_m.historical_event_id} (Similarity: {top_m.similarity_score:.1%})")

        if event.retrospective_outcome:
            out = event.retrospective_outcome
            lines.append(f"Post-Hoc Outcome: {out.outcome_status.value} (Error: {out.verified_forecast_error:+.2f}, Captured: {out.was_captured})")

        return "\n".join(lines)

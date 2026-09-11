"""
Unified Operational Risk Intelligence Pipeline (Day 19).

Integrates all Veyra intelligence subsystems into a production-grade,
deterministic, explainable, leakage-safe operational forecast-risk sentry.

Subsystems Unified:
- Uncertainty Decomposition & Attribution (Day 14)
- Operational Decision Engine & Safety Gating (Day 15)
- Temporal Early Warning & Trajectory Dynamics (Day 16)
- Explainable AI (XAI) & Counterfactual Reasoning (Day 17)
- Longitudinal Event Intelligence & Historical Memory (Day 18)
- Signal Arbitration & Graceful Degradation (Day 19)
"""

import hashlib
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from evaluation.data_quality import DataQualityAuditor
from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_schema import (
    DataQualityState,
    EvidenceItem,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from evaluation.event_memory import EventMemoryStore
from evaluation.event_outcome import EventOutcomeEvaluator
from evaluation.event_schema import (
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
from evaluation.novelty import FeatureNoveltyDetector
from evaluation.signal_arbitration import SignalArbitrationEngine
from evaluation.temporal_early_warning_engine import TemporalEarlyWarningEngine
from evaluation.trajectory_schema import (
    ForecastTrajectory,
    ForecastTrajectoryPoint,
    TrajectoryAssessment,
    TrajectoryState,
    WarningHorizon,
)
from evaluation.uncertainty import UncertaintyDecomposer
from evaluation.unified_schema import (
    AssessmentStatus,
    SignalOverrideRecord,
    UnifiedOperationalAssessment,
)
from evaluation.xai_engine import ExplainableForecastEngine
from evaluation.xai_schema import (
    CanonicalXAIExplanation,
    ExplanationLevel,
    ExplanationMode,
    NoveltyExplanation,
    TemporalDynamicsExplanation,
    UncertaintyExplanation,
    UncertaintySource,
)


class UnifiedOperationalRiskEngine:
    """
    Master operational pipeline coordinating all Veyra intelligence components.
    """

    def __init__(
        self,
        decision_engine: Optional[ForecastRiskDecisionEngine] = None,
        temporal_engine: Optional[TemporalEarlyWarningEngine] = None,
        xai_engine: Optional[ExplainableForecastEngine] = None,
        event_tracker: Optional[OperationalEventTracker] = None,
        event_memory: Optional[EventMemoryStore] = None,
        event_outcome_evaluator: Optional[EventOutcomeEvaluator] = None,
        arbitration_engine: Optional[SignalArbitrationEngine] = None,
    ):
        self.decision_engine = decision_engine or ForecastRiskDecisionEngine()
        self.temporal_engine = temporal_engine or TemporalEarlyWarningEngine()
        self.xai_engine = xai_engine or ExplainableForecastEngine()
        self.event_tracker = event_tracker or OperationalEventTracker()
        self.event_memory = event_memory or EventMemoryStore()
        self.outcome_evaluator = event_outcome_evaluator or EventOutcomeEvaluator()
        self.arbitration_engine = arbitration_engine or SignalArbitrationEngine()
        self.data_auditor = DataQualityAuditor()

    @staticmethod
    def audit_leakage_payload(payload: Any) -> None:
        """
        Strictly reject any verification, error, or post-hoc target fields at decision time,
        recursively inspecting nested mappings and sequences.
        """
        if payload is None:
            return

        forbidden_terms = (
            "truth", "error", "bust_label", "is_bust", "obs_", "obs", "observation", "actual",
            "realized", "verified_bust", "verified_abs_error", "verification", "target"
        )

        def _scan_obj(obj: Any, path: str = "") -> List[str]:
            violations = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_str = str(k).strip()
                    k_clean = k_str.lower()
                    current_path = f"{path}.{k_str}" if path else k_str
                    if k_clean in FORBIDDEN_VERIFICATION_COLUMNS or any(t in k_clean for t in forbidden_terms):
                        violations.append(current_path)
                    violations.extend(_scan_obj(v, current_path))
            elif isinstance(obj, (list, tuple, set)):
                for idx, item in enumerate(obj):
                    violations.extend(_scan_obj(item, f"{path}[{idx}]"))
            return violations

        violations = _scan_obj(payload)
        if violations:
            raise ValueError(f"Target leakage rejected in decision-time payload: {violations}")

    def evaluate_forecast_cycle(
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
        raw_risk: Optional[float] = None,
        confidence_score: float = 0.80,
        novelty_score: float = 1.0,
        features: Optional[Dict[str, Any]] = None,
        trajectory_history: Optional[List[Dict[str, Any]]] = None,
        mode: ExplanationMode = ExplanationMode.DECISION_TIME,
        post_hoc_truth: Optional[Dict[str, Any]] = None,
    ) -> UnifiedOperationalAssessment:
        """
        Execute full multi-tier operational risk assessment with end-to-end integration.
        """
        # 1. Strict Anti-Leakage Gate
        if mode == ExplanationMode.DECISION_TIME:
            self.audit_leakage_payload(features)
            if trajectory_history:
                for pt in trajectory_history:
                    self.audit_leakage_payload(pt)

        # 2. Numerical Input Sanitization & Data Quality Audit
        loc_clean = str(location_id).lower().strip()
        var_clean = str(variable).lower().strip()
        v_time_clean = str(valid_time_utc).strip()
        i_time_clean = str(issue_time_utc).strip()

        sanitized_forecast = float(np.nan_to_num(forecast_value, nan=0.0, posinf=9999.0, neginf=-9999.0))
        sanitized_ens_mean = float(np.nan_to_num(ensemble_mean, nan=0.0, posinf=9999.0, neginf=-9999.0))
        sanitized_ens_std = float(np.nan_to_num(ensemble_std, nan=0.0, posinf=9999.0, neginf=0.0))
        sanitized_risk = float(np.clip(np.nan_to_num(calibrated_risk, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0))
        sanitized_raw_risk = float(np.clip(np.nan_to_num(raw_risk if raw_risk is not None else sanitized_risk, nan=0.0), 0.0, 1.0))
        sanitized_conf = float(np.clip(np.nan_to_num(confidence_score, nan=0.5, posinf=1.0, neginf=0.0), 0.0, 1.0))
        sanitized_nov = float(np.nan_to_num(novelty_score, nan=1.0, posinf=99.0, neginf=0.0))
        sanitized_lead = max(0.0, float(np.nan_to_num(lead_hours, nan=0.0, posinf=999.0, neginf=0.0)))

        # Check data quality
        dq_state = DataQualityState.CLEAN
        warnings: List[str] = []
        limitations: List[str] = [
            "Statistical risk estimate conditioned on historical NWP error distributions.",
            "Non-causal empirical attribution; does not simulate full dynamical fluid physics.",
        ]

        if np.isnan(forecast_value) or np.isnan(ensemble_mean):
            dq_state = DataQualityState.DEGRADED
            warnings.append("NaN detected in raw NWP forecast/ensemble mean; fallback applied.")
        if ensemble_std == 0.0:
            warnings.append("Zero ensemble spread detected; dispersion evidence unavailable.")

        # 3. Uncertainty Subsystem
        spread_ratio = float(sanitized_ens_std / max(1.0, abs(sanitized_ens_mean)))
        epistemic_est = min(1.0, sanitized_nov * 0.20)
        aleatoric_est = min(1.0, sanitized_ens_std / 4.0)
        total_unc = min(1.0, 0.60 * aleatoric_est + 0.40 * epistemic_est)

        primary_source = UncertaintySource.ENSEMBLE_DISPERSION if aleatoric_est >= epistemic_est else UncertaintySource.EPISTEMIC_NOVELTY
        secondary = [UncertaintySource.EPISTEMIC_NOVELTY] if primary_source == UncertaintySource.ENSEMBLE_DISPERSION else [UncertaintySource.ENSEMBLE_DISPERSION]
        unc_explanation = UncertaintyExplanation(
            dominant_source=primary_source,
            secondary_sources=secondary,
            ensemble_spread_magnitude=round(sanitized_ens_std, 3),
            epistemic_novelty_magnitude=round(epistemic_est, 3),
            temporal_instability_magnitude=0.0,
            confidence_impact_score=round(max(0.0, (1.0 - sanitized_conf)), 3),
            narrative=f"Primary uncertainty from {primary_source.value} (spread={sanitized_ens_std:.2f})",
        )

        # 4. Novelty Subsystem
        is_novel = sanitized_nov >= 2.0
        is_in_dist = sanitized_nov < 2.50
        nov_level = "EXTREME" if sanitized_nov >= 2.50 else ("MODERATE" if is_novel else "NORMAL")
        nov_explanation = NoveltyExplanation(
            is_in_domain=is_in_dist,
            novelty_score=round(sanitized_nov, 3),
            novelty_level=nov_level,
            confidence_impact=round(max(0.0, (sanitized_nov - 1.0) * 0.15), 3),
            contributed_to_abstention=(not is_in_dist),
            narrative="In-distribution baseline" if is_in_dist else f"High feature-space novelty ({sanitized_nov:.2f})",
        )

        # 5. Temporal Dynamics & Trajectory Subsystem
        traj_state = TrajectoryState.STABLE_LOW
        ews_score = float(sanitized_risk)
        time_to_crit = None
        instab_detected = False
        instab_narrative = "No rapid inter-cycle instability detected"
        risk_vel = 0.0

        if trajectory_history and len(trajectory_history) >= 2:
            # Multi-cycle sequence available
            risks = [float(np.clip(p.get("calibrated_risk", 0.0), 0.0, 1.0)) for p in trajectory_history]
            if len(risks) >= 2:
                risk_vel = float(risks[-1] - risks[-2])
                if risk_vel >= 0.08 or (len(risks) >= 3 and (risks[-1] - risks[-3]) >= 0.15):
                    traj_state = TrajectoryState.ACCELERATING_RISK
                    instab_detected = True
                    instab_narrative = f"Rapid risk velocity detected ({risk_vel:+.3f}/cycle)"
                elif risk_vel >= 0.03:
                    traj_state = TrajectoryState.RISING_RISK
                elif risk_vel <= -0.05:
                    traj_state = TrajectoryState.REVERSING_RISK
                elif risk_vel <= -0.01:
                    traj_state = TrajectoryState.STABLE_LOW

                # Estimate time to critical threshold (0.65)
                if risk_vel > 0.001 and sanitized_risk < 0.65:
                    cycles_needed = (0.65 - sanitized_risk) / risk_vel
                    time_to_crit = round(cycles_needed * 6.0, 1)  # 6h per cycle standard
                ews_score = float(np.clip(0.50 * sanitized_risk + 0.30 * max(0.0, risk_vel * 5.0) + 0.20 * min(1.0, sanitized_ens_std / 4.0), 0.0, 1.0))
        elif trajectory_history and len(trajectory_history) == 1:
            traj_state = TrajectoryState.INSUFFICIENT_HISTORY
            warnings.append("Single-cycle history: temporal velocity estimated from baseline.")
        else:
            traj_state = TrajectoryState.INSUFFICIENT_HISTORY
            warnings.append("No temporal history provided: temporal evidence operating in single-cycle mode.")

        # 6. Baseline Decision Engine Evaluation (Day 15)
        base_decision = OperationalDecision.MONITOR
        base_priority = WarningPriority.P4_INFORMATIONAL
        base_risk_level = RiskLevel.LOW

        if sanitized_risk >= 0.65:
            base_decision = OperationalDecision.ALERT_CRITICAL_BUST
            base_priority = WarningPriority.P1_HIGH
            base_risk_level = RiskLevel.CRITICAL
        elif sanitized_risk >= 0.40:
            base_decision = OperationalDecision.WARN_POTENTIAL_BUST
            base_priority = WarningPriority.P2_MEDIUM
            base_risk_level = RiskLevel.HIGH
        elif sanitized_risk >= 0.20:
            base_decision = OperationalDecision.ADVISE_CAUTION
            base_priority = WarningPriority.P3_LOW
            base_risk_level = RiskLevel.ELEVATED
        else:
            base_decision = OperationalDecision.MONITOR
            base_priority = WarningPriority.P4_INFORMATIONAL
            base_risk_level = RiskLevel.LOW

        # 7. Longitudinal Event Intelligence (Day 18)
        event = self.event_tracker.process_cycle_update(
            location_id=loc_clean,
            variable=var_clean,
            valid_time_utc=v_time_clean,
            issue_time_utc=i_time_clean,
            lead_hours=sanitized_lead,
            forecast_value=sanitized_forecast,
            ensemble_mean=sanitized_ens_mean,
            ensemble_std=sanitized_ens_std,
            calibrated_risk=sanitized_risk,
            novelty_score=sanitized_nov,
            instability_detected=instab_detected,
            operational_decision=base_decision.value,
            warning_priority=base_priority.value,
            confidence=sanitized_conf,
            time_to_critical_hours=time_to_crit,
            risk_velocity=risk_vel,
        )

        # Retrieve historical analogues from event memory
        analogue_matches = self.event_memory.find_analogous_events(event, top_k=2)
        top_analogue = analogue_matches[0] if analogue_matches else None

        # 8. Signal Arbitration (Day 19)
        arb_decision, arb_priority, arb_urgency, assess_status, overrides = self.arbitration_engine.arbitrate(
            base_decision=base_decision,
            base_priority=base_priority,
            base_urgency=event.urgency,
            calibrated_risk=sanitized_risk,
            confidence_score=sanitized_conf,
            novelty_score=sanitized_nov,
            data_quality=dq_state,
            trajectory_state=traj_state,
            instability_detected=instab_detected,
            risk_velocity=risk_vel,
            time_to_critical_hours=time_to_crit,
            is_abstained_explicit=False,
        )

        # 9. Explainable AI (XAI) Engine (Day 17)
        explanation = None
        try:
            f_dict = dict(features or {})
            f_dict["lead_hours"] = sanitized_lead
            f_dict["forecast_value"] = sanitized_forecast
            f_dict["ensemble_mean"] = sanitized_ens_mean
            f_dict["ensemble_std"] = sanitized_ens_std
            f_dict["calibrated_risk"] = sanitized_risk
            f_dict["confidence"] = sanitized_conf
            f_dict["novelty_score"] = sanitized_nov
            explanation = self.xai_engine.generate_explanation(
                features=f_dict,
                location_id=loc_clean,
                variable=var_clean,
                valid_time_utc=v_time_clean,
                issue_time_utc=i_time_clean,
                mode=mode,
                post_hoc_truth=post_hoc_truth if mode == ExplanationMode.POST_HOC_EVALUATION else None,
            )
        except Exception as ex:
            warnings.append(f"XAI engine fallback: {str(ex)}")

        # 10. Construct Master Unified Assessment Object
        raw_assessment_id = f"assess:{loc_clean}:{var_clean}:{v_time_clean}:{i_time_clean}"
        assessment_id = hashlib.sha256(raw_assessment_id.encode("utf-8")).hexdigest()[:16]

        assessment = UnifiedOperationalAssessment(
            assessment_id=assessment_id,
            schema_version="19.0.0",
            issue_time_utc=i_time_clean,
            valid_time_utc=v_time_clean,
            location_id=loc_clean,
            variable=var_clean,
            lead_hours=sanitized_lead,
            forecast_value=sanitized_forecast,
            ensemble_mean=sanitized_ens_mean,
            ensemble_std=sanitized_ens_std,
            calibrated_risk=sanitized_risk,
            raw_risk=sanitized_raw_risk,
            confidence_score=sanitized_conf,
            risk_level=base_risk_level,
            operational_decision=arb_decision,
            warning_priority=arb_priority,
            urgency=arb_urgency,
            severity=event.severity,
            severity_score=event.severity_score,
            uncertainty=unc_explanation,
            novelty=nov_explanation,
            data_quality=dq_state,
            trajectory_state=traj_state,
            early_warning_score=round(ews_score, 4),
            time_to_critical_hours=time_to_crit,
            instability_detected=instab_detected,
            instability_narrative=instab_narrative,
            event_id=event.event_id,
            event_lifecycle_state=event.lifecycle_state,
            cycles_tracked=event.cycles_tracked,
            warning_cycles_count=event.warning_cycles_count,
            historical_analogue=top_analogue,
            explanation=explanation,
            assessment_status=assess_status,
            signal_overrides=overrides,
            limitations=limitations,
            warnings=warnings,
        )

        # Compute initial decision provenance hash
        assessment.decision_provenance_hash = assessment.compute_decision_provenance()

        # 11. Post-Hoc Outcome Handling
        if mode == ExplanationMode.POST_HOC_EVALUATION and post_hoc_truth is not None:
            t_val = post_hoc_truth.get("truth_value")
            if t_val is not None:
                self.outcome_evaluator.attach_event_outcome(
                    event=event,
                    truth_value=float(t_val),
                    verification_time_utc=post_hoc_truth.get("verification_time_utc"),
                )
                assessment.retrospective_outcome = event.retrospective_outcome

        # Compute execution provenance hash
        assessment.execution_provenance_hash = assessment.compute_execution_provenance()

        return assessment

    def render_unified_briefing(self, assessment: UnifiedOperationalAssessment) -> str:
        """
        Generate a human-readable operational briefing for meteorologists and emergency managers.
        """
        lines = [
            "================================================================================",
            "                   VEYRA UNIFIED OPERATIONAL RISK SENTRY                        ",
            "================================================================================",
            f"Assessment ID: {assessment.assessment_id}  |  Schema: {assessment.schema_version}  |  Status: {assessment.assessment_status.value}",
            f"Location: {assessment.location_id.upper()}  |  Variable: {assessment.variable}  |  Lead: {assessment.lead_hours:.1f}h",
            f"Issue Time: {assessment.issue_time_utc}  ➔  Valid Time: {assessment.valid_time_utc}",
            "--------------------------------------------------------------------------------",
            "1. OPERATIONAL DECISION & URGENCY",
            f"   Decision:        {assessment.operational_decision.value} ({assessment.warning_priority.value})",
            f"   Urgency Tier:    {assessment.urgency.value}",
            f"   Severity Score:  {assessment.severity.value} ({assessment.severity_score:.2f})",
            f"   Calibrated Risk: {assessment.calibrated_risk:.1%} (Raw Risk: {assessment.raw_risk:.1%})",
            f"   Confidence:      {assessment.confidence_score:.1%} | Novelty: {assessment.novelty.novelty_score:.2f}",
            "--------------------------------------------------------------------------------",
            "2. TEMPORAL TRAJECTORY & EARLY WARNING",
            f"   Trajectory:      {assessment.trajectory_state.value}",
            f"   Early Warning S: {assessment.early_warning_score:.3f}",
            f"   Time to Risk:    {f'{assessment.time_to_critical_hours:.1f}h' if assessment.time_to_critical_hours is not None else 'N/A'}",
            f"   Instability:     {assessment.instability_detected} ({assessment.instability_narrative})",
            "--------------------------------------------------------------------------------",
            "3. LONGITUDINAL EVENT INTELLIGENCE",
            f"   Event ID:        {assessment.event_id}",
            f"   Lifecycle State: {assessment.event_lifecycle_state.value}",
            f"   Cycles Tracked:  {assessment.cycles_tracked} (Warnings: {assessment.warning_cycles_count} cycles)",
        ]
        if assessment.historical_analogue:
            ha = assessment.historical_analogue
            lines.append(f"   Historical Analogue: {ha.historical_event_id} (Similarity: {ha.similarity_score:.1%}, Distance: {ha.trajectory_distance:.2f})")

        if assessment.signal_overrides:
            lines.append("--------------------------------------------------------------------------------")
            lines.append("4. SIGNAL ARBITRATION OVERRIDES")
            for ov in assessment.signal_overrides:
                lines.append(f"   [{ov.precedence_tier.value}] {ov.source_module}: {ov.original_decision} ➔ {ov.arbitrated_decision}")
                lines.append(f"     Reason: {ov.rationale}")

        if assessment.explanation:
            lines.append("--------------------------------------------------------------------------------")
            lines.append("5. XAI EXPLANATION RATIONALE")
            lines.append(f"   Summary: {assessment.explanation.overall_narrative}")
            if assessment.explanation.decision_rationale:
                dr = assessment.explanation.decision_rationale
                if dr.primary_triggers:
                    lines.append(f"   Primary Triggers: {', '.join(dr.primary_triggers)}")
                if dr.recommended_action:
                    lines.append(f"   Recommended Action: {dr.recommended_action}")

        lines.append("--------------------------------------------------------------------------------")
        lines.append(f"Decision Provenance:  {assessment.decision_provenance_hash}")
        lines.append(f"Execution Provenance: {assessment.execution_provenance_hash}")
        lines.append("================================================================================")
        return "\n".join(lines)

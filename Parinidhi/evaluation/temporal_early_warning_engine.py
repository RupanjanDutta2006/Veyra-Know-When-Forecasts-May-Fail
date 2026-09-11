"""
Temporal Early-Warning & Trajectory Engine Orchestrator (Day 16).

Integrates temporal feature extraction, trajectory state classification, instability detection,
time-to-critical-risk estimation, early-warning scoring, and historical trajectory analogues
into a unified, leakage-safe early-warning engine.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_schema import ForecastRiskDecision, OperationalDecision, WarningPriority
from evaluation.early_warning_score import TemporalEarlyWarningScore
from evaluation.evidence_fusion import EvidenceItem
from evaluation.instability_detector import ForecastInstabilityDetector, InstabilitySignal
from evaluation.temporal_features import TemporalFeatureExtractor
from evaluation.time_to_risk import TimeToCriticalRiskEstimator, TimeToRiskEstimate
from evaluation.trajectory_analogues import HistoricalTrajectoryRetriever
from evaluation.trajectory_schema import (
    ForecastTrajectory,
    ForecastTrajectoryPoint,
    TrajectoryAssessment,
    TrajectoryState,
    WarningHorizon,
)


class TemporalEarlyWarningEngine:
    """
    Master orchestrator for temporal forecast failure trajectory reasoning.
    """

    def __init__(
        self,
        decision_engine: Optional[ForecastRiskDecisionEngine] = None,
        feature_extractor: Optional[TemporalFeatureExtractor] = None,
        state_machine: Optional[Any] = None,
        instability_detector: Optional[ForecastInstabilityDetector] = None,
        time_estimator: Optional[TimeToCriticalRiskEstimator] = None,
        ews_scorer: Optional[TemporalEarlyWarningScore] = None,
        analogue_retriever: Optional[HistoricalTrajectoryRetriever] = None,
    ):
        from evaluation.trajectory_state_machine import TrajectoryStateMachine
        self.decision_engine = decision_engine or ForecastRiskDecisionEngine()
        self.feature_extractor = feature_extractor or TemporalFeatureExtractor()
        self.state_machine = state_machine or TrajectoryStateMachine()
        self.instability_detector = instability_detector or ForecastInstabilityDetector()
        self.time_estimator = time_estimator or TimeToCriticalRiskEstimator()
        self.ews_scorer = ews_scorer or TemporalEarlyWarningScore()
        self.analogue_retriever = analogue_retriever or HistoricalTrajectoryRetriever()

    def assess_trajectory(self, trajectory: ForecastTrajectory) -> TrajectoryAssessment:
        """
        Produce a comprehensive early-warning TrajectoryAssessment from a ForecastTrajectory.
        Validates trajectory integrity across target identity, distinct issue cycles, and ordering.
        """
        # Audit trajectory integrity
        trajectory.validate_integrity(strict_monotonic_leads=False)

        # Ensure chronological ordering
        if not trajectory.is_chronologically_sorted():
            trajectory = trajectory.sort_chronologically()

        pts = trajectory.points
        n = len(pts)
        loc = trajectory.location_id
        var = trajectory.variable
        valid_time = trajectory.valid_time_utc
        latest_issue = pts[-1].issue_time_utc if pts else "UNKNOWN"
        traj_id = f"{loc}:{var}:{valid_time}"

        if n == 0:
            return TrajectoryAssessment(
                trajectory_id=traj_id,
                location_id=loc,
                variable=var,
                valid_time_utc=valid_time,
                latest_issue_time_utc="UNKNOWN",
                sequence_length=0,
                current_risk=0.0,
                risk_slope=0.0,
                risk_acceleration=0.0,
                risk_persistence=0.0,
                spread_slope=0.0,
                revision_velocity=0.0,
                instability_detected=False,
                state=TrajectoryState.INSUFFICIENT_HISTORY,
                early_warning_score=0.0,
                warning_horizon=WarningHorizon.WATCH,
                trajectory_confidence=0.0,
                is_safe_for_decision=False,
                abstention_triggered=True,
                abstention_reason="Empty trajectory sequence.",
            )

        # 1. Extract Temporal Features
        temp_features = self.feature_extractor.extract_trajectory_features(trajectory)

        # 2. Detect Instability
        instability = self.instability_detector.detect_instability(temp_features)

        # 3. Classify Trajectory State
        state = self.state_machine.classify_state(temp_features, instability=instability)

        # 4. Retrieve Historical Trajectory Analogues
        analogue_info = self.analogue_retriever.retrieve_analogues(temp_features, exclude_id=traj_id)

        # 5. Compute Early Warning Score & Horizon
        hist_fail_rate = analogue_info.get("historical_failure_rate", 0.0)
        ews, horizon, breakdown = self.ews_scorer.compute_score(temp_features, historical_failure_rate=hist_fail_rate)

        # 6. Estimate Time to Critical Risk
        time_est = self.time_estimator.estimate_time_to_critical(temp_features, state)

        # 7. Compute Trajectory Confidence
        novelty = temp_features.get("mean_novelty", 1.0)
        missing_frac = temp_features.get("mean_missing_fraction", 0.0)
        conf = 0.90
        if n < 3:
            conf -= 0.15 * (3 - n)
        if novelty > 1.5:
            conf -= min(0.35, (novelty - 1.5) * 0.20)
        if missing_frac > 0.10:
            conf -= missing_frac * 0.40
        if instability.detected:
            conf -= 0.15
        trajectory_conf = float(np.clip(conf, 0.05, 0.98))

        # 8. Explanation Factors
        explanations = []
        if state == TrajectoryState.PERSISTENT_HIGH_RISK:
            explanations.append(f"Persistent high risk (P={temp_features['current_risk']:.2f}) maintained over {int(temp_features['risk_persistence_count'])} consecutive cycles.")
        elif state == TrajectoryState.ACCELERATING_RISK:
            explanations.append(f"Risk trajectory is accelerating (slope=+{temp_features['risk_slope']:.3f}, accel=+{temp_features['risk_acceleration']:.3f}).")
        elif state == TrajectoryState.RISING_RISK:
            explanations.append(f"Risk has risen steadily over recent cycles (+{temp_features['risk_delta']*100:.1f}%).")
        elif state == TrajectoryState.REVERSING_RISK:
            explanations.append(f"Risk signal is reversing after previous elevation ({temp_features['risk_delta']*100:.1f}% drop).")
        elif state == TrajectoryState.STABLE_LOW:
            explanations.append("Forecast evolution is stable with low failure risk.")

        if instability.detected and instability.reason:
            explanations.append(f"Instability signal: {instability.reason}")

        if analogue_info.get("has_support"):
            explanations.append(f"Historical trajectory analogues showed a {hist_fail_rate*100:.1f}% verification bust rate across {analogue_info['analogue_count']} matching runs.")

        if time_est.is_estimable and time_est.estimated_hours_to_critical is not None:
            explanations.append(time_est.reason)

        # 9. Safety & Abstention Check
        abstain = False
        abstain_reason = None
        if state == TrajectoryState.NOVEL_UNTRUSTED:
            abstain = True
            abstain_reason = "Out-of-distribution feature novelty or severe missingness in trajectory sequence."
        elif state == TrajectoryState.INSUFFICIENT_HISTORY and n < 1:
            abstain = True
            abstain_reason = "Insufficient history."

        return TrajectoryAssessment(
            trajectory_id=traj_id,
            location_id=loc,
            variable=var,
            valid_time_utc=valid_time,
            latest_issue_time_utc=latest_issue,
            sequence_length=n,
            current_risk=temp_features["current_risk"],
            risk_slope=temp_features["risk_slope"],
            risk_acceleration=temp_features["risk_acceleration"],
            risk_persistence=temp_features["risk_persistence_count"],
            spread_slope=temp_features["spread_slope"],
            revision_velocity=temp_features["revision_velocity"],
            instability_detected=instability.detected,
            instability_reason=instability.reason,
            state=state,
            early_warning_score=ews,
            warning_horizon=horizon,
            estimated_cycles_to_critical=time_est.estimated_cycles_to_critical,
            estimated_hours_to_critical=time_est.estimated_hours_to_critical,
            trajectory_confidence=round(trajectory_conf, 3),
            explanation_factors=explanations,
            historical_analogue_support=analogue_info,
            is_safe_for_decision=not abstain,
            abstention_triggered=abstain,
            abstention_reason=abstain_reason,
        )

    def generate_operational_decision(self, trajectory: ForecastTrajectory) -> ForecastRiskDecision:
        """
        Integrate trajectory early-warning assessment into the Day 15 ForecastRiskDecision.
        """
        assessment = self.assess_trajectory(trajectory)
        pts = trajectory.points
        latest_pt = pts[-1] if pts else None
        features = latest_pt.features if latest_pt else {}

        # Query base Day 15 decision engine
        base_decision = self.decision_engine.decide_forecast_risk(
            features=features,
            raw_bust_probability=latest_pt.raw_risk if latest_pt else None,
            location_id=trajectory.location_id,
            variable=trajectory.variable,
        )

        # Inject Day 16 Trajectory Evidence into Day 15 Evidence List
        enhanced_supp = list(base_decision.supporting_evidence)
        if assessment.state in [TrajectoryState.ACCELERATING_RISK, TrajectoryState.RISING_RISK, TrajectoryState.PERSISTENT_HIGH_RISK]:
            enhanced_supp.append({
                "source": "trajectory_early_warning",
                "strength": assessment.early_warning_score,
                "direction": "INCREASES_RISK",
                "summary": f"Trajectory state: {assessment.state.value} (EWS={assessment.early_warning_score:.2f}, horizon={assessment.warning_horizon.value})",
            })

        enhanced_contra = list(base_decision.contradicting_evidence)
        if assessment.state == TrajectoryState.REVERSING_RISK:
            enhanced_contra.append({
                "source": "trajectory_early_warning",
                "strength": 0.6,
                "direction": "DECREASES_RISK",
                "summary": f"Risk signal is reversing ({assessment.risk_slope:.3f} slope).",
            })

        # Recompute final risk score blended with EWS
        blended_risk = float(np.clip(0.65 * base_decision.risk_score + 0.35 * assessment.early_warning_score, 0.0, 1.0))
        blended_conf = float(np.clip(min(base_decision.confidence, assessment.trajectory_confidence), 0.05, 0.98))

        # Recommended action updated with trajectory insights
        rec_action = base_decision.recommended_action
        if assessment.state == TrajectoryState.ACCELERATING_RISK:
            rec_action = f"URGENT: Risk is accelerating across issue cycles. {rec_action}"
        elif assessment.state == TrajectoryState.PERSISTENT_HIGH_RISK:
            rec_action = f"PERSISTENT RISK: Sustained high bust likelihood. {rec_action}"

        return ForecastRiskDecision(
            decision_id=base_decision.decision_id,
            decision=base_decision.decision,
            risk_level=base_decision.risk_level,
            risk_score=round(blended_risk, 4),
            raw_bust_probability=base_decision.raw_bust_probability,
            calibrated_bust_probability=base_decision.calibrated_bust_probability,
            confidence=round(blended_conf, 3),
            confidence_level=base_decision.confidence_level,
            uncertainty_level=base_decision.uncertainty_level,
            novelty_level=base_decision.novelty_level,
            data_quality_level=base_decision.data_quality_level,
            lead_time_level=base_decision.lead_time_level,
            warning_priority=base_decision.warning_priority,
            recommended_action=rec_action,
            abstention_required=base_decision.abstention_required or assessment.abstention_triggered,
            abstention_reason=assessment.abstention_reason or base_decision.abstention_reason,
            dominant_risk_drivers=base_decision.dominant_risk_drivers,
            supporting_evidence=enhanced_supp,
            contradicting_evidence=enhanced_contra,
            evidence_conflict_score=base_decision.evidence_conflict_score,
            historical_analogue_support=assessment.historical_analogue_support or base_decision.historical_analogue_support,
            location_reliability=base_decision.location_reliability,
            sensitivity_analysis=base_decision.sensitivity_analysis,
            provenance=base_decision.provenance,
        )

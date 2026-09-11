"""
Signal Arbitration and Conflict Resolution Engine (Day 19).

Provides a mathematically rigorous, deterministic precedence hierarchy when
heterogeneous intelligence signals disagree (e.g., high novelty vs high temporal risk).

Precedence Hierarchy:
1. TIER 1: Safety & Hard Feature Contract / Target Leakage Violations (Fail Closed)
2. TIER 2: Feature-Space Novelty / Out-of-Distribution Gating (Abstention)
3. TIER 3: Data Quality & Missingness Gating (Abstention)
4. TIER 4: Critical Temporal Instability & Rapid Acceleration (Escalation)
5. TIER 5: Calibrated Risk Decision Policy (Cost-Optimal Baseline)
6. TIER 6: Routine Baseline Monitoring
"""

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from evaluation.decision_schema import (
    DataQualityState,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from evaluation.event_schema import OperationalUrgency
from evaluation.trajectory_schema import TrajectoryState
from evaluation.unified_schema import (
    AssessmentStatus,
    SignalOverrideRecord,
    SignalPrecedenceTier,
)


class SignalArbitrationEngine:
    """
    Arbitrates conflicts across uncertainty, novelty, data quality, temporal dynamics,
    and decision policy layers with full provenance tracking.
    """

    def __init__(
        self,
        novelty_abstention_threshold: float = 2.50,
        instability_escalation_velocity: float = 0.08,
        min_confidence_for_action: float = 0.25,
    ):
        self.novelty_abstention_threshold = float(novelty_abstention_threshold)
        self.instability_escalation_velocity = float(instability_escalation_velocity)
        self.min_confidence_for_action = float(min_confidence_for_action)

    def arbitrate(
        self,
        base_decision: OperationalDecision,
        base_priority: WarningPriority,
        base_urgency: OperationalUrgency,
        calibrated_risk: float,
        confidence_score: float,
        novelty_score: float,
        data_quality: DataQualityState,
        trajectory_state: TrajectoryState,
        instability_detected: bool,
        risk_velocity: float,
        time_to_critical_hours: Optional[float] = None,
        is_abstained_explicit: bool = False,
    ) -> Tuple[OperationalDecision, WarningPriority, OperationalUrgency, AssessmentStatus, List[SignalOverrideRecord]]:
        """
        Execute formal signal arbitration across all precedence tiers.

        Returns:
            (arbitrated_decision, arbitrated_priority, arbitrated_urgency, assessment_status, override_records)
        """
        overrides: List[SignalOverrideRecord] = []
        cur_decision = base_decision
        cur_priority = base_priority
        cur_urgency = base_urgency
        status = AssessmentStatus.SUCCESS

        # TIER 1: Explicit Abstention / Hard Safety Override
        if is_abstained_explicit or cur_decision == OperationalDecision.ABSTAIN:
            cur_decision = OperationalDecision.ABSTAIN
            cur_priority = WarningPriority.P4_INFORMATIONAL
            cur_urgency = OperationalUrgency.INSUFFICIENT_CONFIDENCE
            status = AssessmentStatus.SAFETY_ABSTAINED
            overrides.append(
                self._create_override_record(
                    tier=SignalPrecedenceTier.TIER_1_SAFETY_GATE,
                    source="SafetyController",
                    orig_dec=base_decision.value,
                    arb_dec=cur_decision.value,
                    condition="Explicit safety abstention triggered",
                    rationale="Safety-critical controller mandated decision abstention.",
                )
            )
            return cur_decision, cur_priority, cur_urgency, status, overrides

        # TIER 2: Novelty / Out-of-Distribution Gating
        if novelty_score >= self.novelty_abstention_threshold or confidence_score < self.min_confidence_for_action:
            cur_decision = OperationalDecision.ABSTAIN
            cur_priority = WarningPriority.P4_INFORMATIONAL
            cur_urgency = OperationalUrgency.INSUFFICIENT_CONFIDENCE
            status = AssessmentStatus.SAFETY_ABSTAINED
            overrides.append(
                self._create_override_record(
                    tier=SignalPrecedenceTier.TIER_2_NOVELTY_ABSTENTION,
                    source="NoveltyGating",
                    orig_dec=base_decision.value,
                    arb_dec=cur_decision.value,
                    condition=f"Novelty score {novelty_score:.2f} >= {self.novelty_abstention_threshold:.2f} or confidence {confidence_score:.2f} < {self.min_confidence_for_action:.2f}",
                    rationale="Forecast state lies outside empirical training manifold; automated action inhibited.",
                )
            )
            return cur_decision, cur_priority, cur_urgency, status, overrides

        # TIER 3: Data Quality Gating
        if data_quality in (DataQualityState.CORRUPTED, DataQualityState.INSUFFICIENT):
            cur_decision = OperationalDecision.ABSTAIN
            cur_priority = WarningPriority.P4_INFORMATIONAL
            cur_urgency = OperationalUrgency.INSUFFICIENT_CONFIDENCE
            status = AssessmentStatus.DATA_QUALITY_REJECTED
            overrides.append(
                self._create_override_record(
                    tier=SignalPrecedenceTier.TIER_3_DATA_QUALITY_GATE,
                    source="DataQualityAuditor",
                    orig_dec=base_decision.value,
                    arb_dec=cur_decision.value,
                    condition=f"Data quality state is {data_quality.value}",
                    rationale="Corrupted, incomplete, or non-physical input data prevented reliable inference.",
                )
            )
            return cur_decision, cur_priority, cur_urgency, status, overrides

        # TIER 4: Critical Temporal Instability & Acceleration Override
        # If NWP displays rapid divergence/instability but base risk is moderate, escalate priority/urgency
        if instability_detected or risk_velocity >= self.instability_escalation_velocity or trajectory_state in (TrajectoryState.ACCELERATING_RISK, TrajectoryState.UNSTABLE_SIGNAL):
            if cur_decision in (OperationalDecision.MONITOR, OperationalDecision.ADVISE_CAUTION):
                orig_str = cur_decision.value
                cur_decision = OperationalDecision.WARN_POTENTIAL_BUST
                cur_priority = WarningPriority.P2_MEDIUM
                cur_urgency = OperationalUrgency.URGENT if cur_urgency in (OperationalUrgency.ROUTINE, OperationalUrgency.WATCH) else cur_urgency
                overrides.append(
                    self._create_override_record(
                        tier=SignalPrecedenceTier.TIER_4_CRITICAL_TEMPORAL_INSTABILITY,
                        source="TemporalInstabilityDetector",
                        orig_dec=orig_str,
                        arb_dec=cur_decision.value,
                        condition=f"Instability detected (velocity={risk_velocity:+.3f}/cycle, state={trajectory_state.value})",
                        rationale="Rapid inter-cycle NWP revision velocity escalated surveillance status to warning.",
                    )
                )
            elif cur_decision == OperationalDecision.WARN_POTENTIAL_BUST and time_to_critical_hours is not None and time_to_critical_hours <= 12.0:
                cur_urgency = OperationalUrgency.IMMEDIATE

        # TIER 5 & 6: Baseline Decision Policy remains intact
        return cur_decision, cur_priority, cur_urgency, status, overrides

    @staticmethod
    def _create_override_record(
        tier: SignalPrecedenceTier,
        source: str,
        orig_dec: str,
        arb_dec: str,
        condition: str,
        rationale: str,
    ) -> SignalOverrideRecord:
        raw_sig = f"{tier.value}:{source}:{orig_dec}->{arb_dec}:{condition}"
        hash_val = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()[:16]
        return SignalOverrideRecord(
            precedence_tier=tier,
            source_module=source,
            original_decision=orig_dec,
            arbitrated_decision=arb_dec,
            triggering_condition=condition,
            rationale=rationale,
            override_provenance_hash=hash_val,
        )

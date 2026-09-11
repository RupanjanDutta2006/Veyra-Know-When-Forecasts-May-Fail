"""
Forecast Risk Decision Policy & Governance (Day 15 Hardened).

Implements:
1. Expected loss decision theory balancing asymmetric missed busts against false alarm costs.
2. Parameter governance classifications (EMPIRICAL, VALIDATED, POLICY, DEFAULT).
3. Monotonic decision evaluation subject to safety and confidence constraints.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from evaluation.decision_schema import OperationalDecision, RiskLevel, WarningPriority


class ParameterGovernanceClass(str, Enum):
    """Scientific categorization of thresholds and hyperparameters."""
    EMPIRICALLY_ESTIMATED = "EMPIRICALLY_ESTIMATED"           # Estimated directly from historical dataset (e.g. quantiles)
    VALIDATED_FROM_HISTORICAL_DATA = "VALIDATED_FROM_HISTORICAL_DATA" # Empirically tested against cross-validation folds
    OPERATIONAL_POLICY_PARAMETER = "OPERATIONAL_POLICY_PARAMETER"     # Explicit domain cost/risk tolerance policy setting
    DEFAULT_CONFIGURABLE_ASSUMPTION = "DEFAULT_CONFIGURABLE_ASSUMPTION" # Standard engineering prior, configurable by user


@dataclass
class ParameterMetadata:
    """Metadata documenting the scientific origin of a policy parameter."""
    name: str
    value: Any
    governance_class: ParameterGovernanceClass
    description: str
    empirical_source: Optional[str] = None


@dataclass
class RiskDecisionPolicy:
    """
    Cost-sensitive decision policy implementing expected loss minimization under uncertainty.
    """
    # 1. Asymmetric Cost Parameters (OPERATIONAL_POLICY_PARAMETER)
    fn_cost_weight: float = 2.5   # Loss multiplier for unwarned bust (miss)
    fp_cost_weight: float = 1.0   # Loss multiplier for false alarm
    alert_fatigue_penalty: float = 0.12  # Overhead penalty per escalated alert tier

    # 2. Risk Level Thresholds (VALIDATED_FROM_HISTORICAL_DATA)
    # Calibrated against 5.06% empirical base rate to capture top risk percentiles
    critical_threshold: float = 0.65
    high_threshold: float = 0.40
    elevated_threshold: float = 0.22
    watch_threshold: float = 0.10

    # 3. Minimum Confidence Requirements (OPERATIONAL_POLICY_PARAMETER)
    min_confidence_for_critical: float = 0.60
    min_confidence_for_high: float = 0.45

    # 4. Abstention Thresholds (DEFAULT_CONFIGURABLE_ASSUMPTION / EMPIRICALLY_ESTIMATED)
    abstention_max_novelty_distance: float = 2.80  # p99.5 distance cutoff from training manifold
    abstention_max_missing_fraction: float = 0.50  # Missing feature fraction cutoff
    abstention_max_conflict_score: float = 0.70    # Divergence threshold between independent evidence sources

    def get_parameter_governance_registry(self) -> Dict[str, ParameterMetadata]:
        """Return explicit scientific classifications for all policy parameters."""
        return {
            "fn_cost_weight": ParameterMetadata(
                name="fn_cost_weight",
                value=self.fn_cost_weight,
                governance_class=ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER,
                description="Asymmetric penalty for missed forecast bust (false negative) relative to false alarm.",
                empirical_source="Domain operational standard: safety disruption cost exceeds advisory overhead.",
            ),
            "fp_cost_weight": ParameterMetadata(
                name="fp_cost_weight",
                value=self.fp_cost_weight,
                governance_class=ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER,
                description="Cost of false alarm warning.",
                empirical_source="Normalized unit operational baseline.",
            ),
            "alert_fatigue_penalty": ParameterMetadata(
                name="alert_fatigue_penalty",
                value=self.alert_fatigue_penalty,
                governance_class=ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER,
                description="Penalty to suppress unwarranted high-frequency alerts in borderline regimes.",
                empirical_source="Operational fatigue suppression tuning.",
            ),
            "critical_threshold": ParameterMetadata(
                name="critical_threshold",
                value=self.critical_threshold,
                governance_class=ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA,
                description="Composite risk threshold for CRITICAL severity (13x climatological base rate).",
                empirical_source="Validated against Stage B 99th percentile bust risk.",
            ),
            "high_threshold": ParameterMetadata(
                name="high_threshold",
                value=self.high_threshold,
                governance_class=ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA,
                description="Composite risk threshold for HIGH severity (8x climatological base rate).",
                empirical_source="Validated against Stage B 95th percentile bust risk.",
            ),
            "elevated_threshold": ParameterMetadata(
                name="elevated_threshold",
                value=self.elevated_threshold,
                governance_class=ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA,
                description="Composite risk threshold for ELEVATED severity (4.4x climatological base rate).",
                empirical_source="Validated against Stage B 90th percentile bust risk.",
            ),
            "watch_threshold": ParameterMetadata(
                name="watch_threshold",
                value=self.watch_threshold,
                governance_class=ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA,
                description="Composite risk threshold for WATCH severity (2x climatological base rate).",
                empirical_source="Validated against Stage B 75th percentile bust risk.",
            ),
            "abstention_max_novelty_distance": ParameterMetadata(
                name="abstention_max_novelty_distance",
                value=self.abstention_max_novelty_distance,
                governance_class=ParameterGovernanceClass.EMPIRICALLY_ESTIMATED,
                description="Feature-space robust manifold distance above which model enters unvalidated extrapolation.",
                empirical_source="Calibrated to 99.5th percentile of Stage B training split.",
            ),
            "abstention_max_missing_fraction": ParameterMetadata(
                name="abstention_max_missing_fraction",
                value=self.abstention_max_missing_fraction,
                governance_class=ParameterGovernanceClass.DEFAULT_CONFIGURABLE_ASSUMPTION,
                description="Maximum allowable fraction of NaN features before mandatory abstention.",
                empirical_source="Conservative engineering default (50% input completeness threshold).",
            ),
        }

    def compute_expected_losses(
        self,
        risk_probability: float,
        confidence: float,
        uncertainty: float = 0.5,
    ) -> Dict[OperationalDecision, float]:
        """
        Compute principled expected loss for each candidate operational action:
        E[L(a)] = P(bust) * L(a | bust=1) + (1 - P(bust)) * L(a | bust=0) + Fatigue(a) + UncertaintyPenalty(a)
        """
        p = float(np.clip(risk_probability, 0.0, 1.0))
        q = 1.0 - p

        # Action-specific loss matrices
        # Loss if bust occurs (y=1)
        loss_bust = {
            OperationalDecision.TRUST_FORECAST: self.fn_cost_weight * 1.0,     # Full miss penalty
            OperationalDecision.MONITOR: self.fn_cost_weight * 0.65,            # Partial miss
            OperationalDecision.ADVISE_CAUTION: self.fn_cost_weight * 0.35,     # Moderate mitigation
            OperationalDecision.WARN_POTENTIAL_BUST: self.fn_cost_weight * 0.10,# Effective warning
            OperationalDecision.ALERT_CRITICAL_BUST: 0.0,                       # Optimal mitigation
            OperationalDecision.ABSTAIN: self.fn_cost_weight * 0.45,            # Unclassified exposure
        }

        # Loss if no bust occurs (y=0)
        loss_nobust = {
            OperationalDecision.TRUST_FORECAST: 0.0,                            # Ideal outcome
            OperationalDecision.MONITOR: self.fp_cost_weight * 0.05,            # Minimal logging cost
            OperationalDecision.ADVISE_CAUTION: self.fp_cost_weight * 0.20,     # Minor disruption
            OperationalDecision.WARN_POTENTIAL_BUST: self.fp_cost_weight * 0.60,# Moderate false alarm
            OperationalDecision.ALERT_CRITICAL_BUST: self.fp_cost_weight * 1.0, # High false alarm cost
            OperationalDecision.ABSTAIN: self.fp_cost_weight * 0.15,            # Manual review overhead
        }

        # Alert fatigue overhead
        fatigue_overhead = {
            OperationalDecision.TRUST_FORECAST: 0.0,
            OperationalDecision.MONITOR: self.alert_fatigue_penalty * 0.25,
            OperationalDecision.ADVISE_CAUTION: self.alert_fatigue_penalty * 0.50,
            OperationalDecision.WARN_POTENTIAL_BUST: self.alert_fatigue_penalty * 1.0,
            OperationalDecision.ALERT_CRITICAL_BUST: self.alert_fatigue_penalty * 1.5,
            OperationalDecision.ABSTAIN: 0.05,
        }

        # Confidence penalty: Taking aggressive action under low confidence incurs risk
        conf_penalty = {
            OperationalDecision.TRUST_FORECAST: 0.0,
            OperationalDecision.MONITOR: 0.0,
            OperationalDecision.ADVISE_CAUTION: (1.0 - confidence) * 0.10,
            OperationalDecision.WARN_POTENTIAL_BUST: (1.0 - confidence) * 0.35,
            OperationalDecision.ALERT_CRITICAL_BUST: (1.0 - confidence) * 0.70,
            OperationalDecision.ABSTAIN: 0.0,
        }

        expected_losses = {}
        for action in OperationalDecision:
            expected_losses[action] = round(
                p * loss_bust[action]
                + q * loss_nobust[action]
                + fatigue_overhead[action]
                + conf_penalty[action],
                4,
            )

        return expected_losses

    def evaluate_risk_level(self, risk_score: float) -> RiskLevel:
        """Map composite risk score to operational severity level monotonically."""
        score = float(np.clip(risk_score, 0.0, 1.0))
        if score >= self.critical_threshold:
            return RiskLevel.CRITICAL
        elif score >= self.high_threshold:
            return RiskLevel.HIGH
        elif score >= self.elevated_threshold:
            return RiskLevel.ELEVATED
        elif score >= self.watch_threshold:
            return RiskLevel.WATCH
        else:
            return RiskLevel.LOW

    def determine_decision(
        self,
        risk_level: RiskLevel,
        confidence: float,
        abstention_required: bool,
    ) -> OperationalDecision:
        """
        Map risk level and confidence to an operational action subject to safety bounds.
        """
        if abstention_required:
            return OperationalDecision.ABSTAIN

        if risk_level == RiskLevel.CRITICAL:
            if confidence >= self.min_confidence_for_critical:
                return OperationalDecision.ALERT_CRITICAL_BUST
            else:
                return OperationalDecision.WARN_POTENTIAL_BUST

        elif risk_level == RiskLevel.HIGH:
            if confidence >= self.min_confidence_for_high:
                return OperationalDecision.WARN_POTENTIAL_BUST
            else:
                return OperationalDecision.ADVISE_CAUTION

        elif risk_level == RiskLevel.ELEVATED:
            return OperationalDecision.ADVISE_CAUTION

        elif risk_level == RiskLevel.WATCH:
            return OperationalDecision.MONITOR

        else:
            return OperationalDecision.TRUST_FORECAST

    def determine_priority(self, decision: OperationalDecision) -> WarningPriority:
        """Assign warning priority based on operational decision."""
        if decision == OperationalDecision.ALERT_CRITICAL_BUST:
            return WarningPriority.P0_CRITICAL
        elif decision == OperationalDecision.WARN_POTENTIAL_BUST:
            return WarningPriority.P1_HIGH
        elif decision == OperationalDecision.ADVISE_CAUTION:
            return WarningPriority.P2_MEDIUM
        elif decision == OperationalDecision.MONITOR:
            return WarningPriority.P3_LOW
        else:
            return WarningPriority.P4_INFORMATIONAL

    def generate_recommended_action(
        self,
        decision: OperationalDecision,
        risk_level: RiskLevel,
        dominant_driver: Optional[str] = None,
        location: Optional[str] = None,
    ) -> str:
        """Generate deterministic, actionable guidance."""
        loc_str = f" for {location.title()}" if location else ""
        if decision == OperationalDecision.ABSTAIN:
            return f"Abstain from automated risk classification{loc_str}. Exercise manual meteorological review due to insufficient or conflicting evidence."
        elif decision == OperationalDecision.ALERT_CRITICAL_BUST:
            return f"Immediate action required{loc_str}: NWP trajectory shows severe failure signatures ({dominant_driver or 'high dispersion'}). Deploy backup forecast."
        elif decision == OperationalDecision.WARN_POTENTIAL_BUST:
            return f"Operational warning{loc_str}: Significant probability of extreme forecast error. Apply risk margins to downstream logistics."
        elif decision == OperationalDecision.ADVISE_CAUTION:
            return f"Exercise caution{loc_str}: Elevated model revision velocity or dispersion detected. Monitor upcoming synoptic cycles."
        elif decision == OperationalDecision.MONITOR:
            return f"Standard monitoring active{loc_str}. Forecast trajectory appears generally stable with minor horizon uncertainty."
        else:
            return f"Forecast trajectory verified high-confidence{loc_str}. In-domain evidence indicates low probability of forecast bust."

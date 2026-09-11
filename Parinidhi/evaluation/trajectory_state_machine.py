"""
Trajectory State Machine (Day 16).

Deterministic classifier categorizing temporal forecast evolution into discrete,
interpretable operational risk trajectory states.
"""

from typing import Dict, Optional
from evaluation.decision_policy import ParameterGovernanceClass
from evaluation.instability_detector import InstabilitySignal
from evaluation.trajectory_schema import TrajectoryState


class TrajectoryStateMachine:
    """
    Classifies a forecast failure trajectory into standard operational trajectory states.
    """

    GOVERNANCE = {
        "rising_slope_min": (0.03, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "accelerating_accel_min": (0.02, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "persistent_high_threshold": (0.40, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "persistent_min_cycles": (2, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "reversal_drop_threshold": (-0.08, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "novelty_untrusted_threshold": (2.50, ParameterGovernanceClass.DEFAULT_CONFIGURABLE_ASSUMPTION),
    }

    def __init__(
        self,
        rising_slope_min: float = 0.03,
        accelerating_accel_min: float = 0.02,
        persistent_high_threshold: float = 0.40,
        persistent_min_cycles: int = 2,
        reversal_drop_threshold: float = -0.08,
        novelty_untrusted_threshold: float = 2.50,
    ):
        self.rising_slope_min = rising_slope_min
        self.accelerating_accel_min = accelerating_accel_min
        self.persistent_high_threshold = persistent_high_threshold
        self.persistent_min_cycles = persistent_min_cycles
        self.reversal_drop_threshold = reversal_drop_threshold
        self.novelty_untrusted_threshold = novelty_untrusted_threshold

    def classify_state(
        self,
        temporal_features: Dict[str, float],
        instability: Optional[InstabilitySignal] = None,
    ) -> TrajectoryState:
        """
        Determine the TrajectoryState using deterministic hierarchical rules.
        """
        seq_len = int(temporal_features.get("sequence_length", 0))
        if seq_len < 2:
            return TrajectoryState.INSUFFICIENT_HISTORY

        mean_novelty = temporal_features.get("mean_novelty", 1.0)
        missing_frac = temporal_features.get("mean_missing_fraction", 0.0)

        # 1. Novelty or extreme corruption gate
        if mean_novelty >= self.novelty_untrusted_threshold or missing_frac >= 0.40:
            return TrajectoryState.NOVEL_UNTRUSTED

        curr_risk = temporal_features.get("current_risk", 0.0)
        prev_risk = temporal_features.get("prev_risk", 0.0)
        risk_slope = temporal_features.get("risk_slope", 0.0)
        risk_accel = temporal_features.get("risk_acceleration", 0.0)
        persist_count = int(temporal_features.get("risk_persistence_count", 0))
        risk_delta = temporal_features.get("risk_delta", 0.0)

        # 2. Persistent High Risk
        if curr_risk >= self.persistent_high_threshold and persist_count >= self.persistent_min_cycles:
            return TrajectoryState.PERSISTENT_HIGH_RISK

        # 3. Accelerating Risk (Positive slope and positive acceleration into elevated risk)
        if curr_risk >= 0.20 and risk_slope >= self.rising_slope_min and risk_accel >= self.accelerating_accel_min:
            return TrajectoryState.ACCELERATING_RISK

        # 4. Rising Risk (Steady upward trajectory)
        if curr_risk >= 0.15 and risk_slope >= self.rising_slope_min:
            return TrajectoryState.RISING_RISK

        # 5. Reversing Risk (Risk was elevated but now clearly decreasing)
        if prev_risk >= 0.22 and risk_delta <= self.reversal_drop_threshold:
            return TrajectoryState.REVERSING_RISK

        # 6. Unstable Signal (Sudden jumps, spread explosion, or high volatility)
        if instability and instability.detected and curr_risk >= 0.15:
            return TrajectoryState.UNSTABLE_SIGNAL

        # 7. Default baseline
        return TrajectoryState.STABLE_LOW

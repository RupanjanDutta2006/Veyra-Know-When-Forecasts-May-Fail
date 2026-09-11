"""
Time-To-Critical-Risk Estimator (Day 16).

Provides an explicit, mathematically closed-form quadratic kinematic solver to estimate
the projected lead time and cycle horizon before a forecast risk trajectory crosses
the critical operational risk threshold (P_crit = 0.65).
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np

from evaluation.decision_policy import ParameterGovernanceClass
from evaluation.trajectory_schema import TrajectoryState


@dataclass
class TimeToRiskEstimate:
    """Projected time horizon until crossing critical operational risk."""
    estimated_cycles_to_critical: Optional[float]
    estimated_hours_to_critical: Optional[float]
    trajectory_direction: str  # "RISING", "ACCELERATING", "STABLE", "FALLING", "UNKNOWN", "CRITICAL"
    crossing_probability: float
    is_estimable: bool
    reason: str


class TimeToCriticalRiskEstimator:
    """
    Explicit closed-form solver for kinematic forecast risk trajectory extrapolation:
        P(t) = P_0 + v * t + 0.5 * a * t^2
        0.5 * a * t^2 + v * t + (P_0 - P_crit) = 0
    """

    GOVERNANCE = {
        "critical_threshold": (0.65, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "cycle_interval_hours": (6.0, ParameterGovernanceClass.EMPIRICALLY_ESTIMATED),
        "max_extrapolation_cycles": (8.0, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
    }

    def __init__(
        self,
        critical_threshold: float = 0.65,
        cycle_interval_hours: float = 6.0,
        max_extrapolation_cycles: float = 8.0,
    ):
        self.critical_threshold = critical_threshold
        self.cycle_interval_hours = cycle_interval_hours
        self.max_extrapolation_cycles = max_extrapolation_cycles

    def estimate_time_to_critical(
        self,
        temporal_features: Dict[str, float],
        trajectory_state: TrajectoryState,
    ) -> TimeToRiskEstimate:
        """
        Closed-form quadratic solution for smallest positive future crossing time t > 0.
        """
        seq_len = int(temporal_features.get("sequence_length", 0))
        if seq_len < 2 or trajectory_state in [TrajectoryState.INSUFFICIENT_HISTORY, TrajectoryState.NOVEL_UNTRUSTED]:
            return TimeToRiskEstimate(
                estimated_cycles_to_critical=None,
                estimated_hours_to_critical=None,
                trajectory_direction="UNKNOWN",
                crossing_probability=0.0,
                is_estimable=False,
                reason="Insufficient sequence history or out-of-distribution novelty.",
            )

        P0 = float(np.clip(temporal_features.get("current_risk", 0.0), 0.0, 1.0))
        v = float(temporal_features.get("risk_slope", 0.0))
        a = float(temporal_features.get("risk_acceleration", 0.0))

        # Case 1: Already at or above critical threshold
        if P0 >= self.critical_threshold:
            return TimeToRiskEstimate(
                estimated_cycles_to_critical=0.0,
                estimated_hours_to_critical=0.0,
                trajectory_direction="CRITICAL",
                crossing_probability=1.0,
                is_estimable=True,
                reason="Forecast risk is currently at or above critical operational threshold (P >= 0.65).",
            )

        # Quadratic Equation: A * t^2 + B * t + C = 0
        A = 0.5 * a
        B = v
        C = P0 - self.critical_threshold  # Strictly negative since P0 < P_crit

        # Case 2: Linear Regime (|A| < 1e-5)
        if abs(A) < 1e-5:
            if B <= 1e-4:
                direction = "FALLING" if B < -0.01 else "STABLE"
                return TimeToRiskEstimate(
                    estimated_cycles_to_critical=None,
                    estimated_hours_to_critical=None,
                    trajectory_direction=direction,
                    crossing_probability=0.05,
                    is_estimable=False,
                    reason=f"Linear trajectory is {direction.lower()} (slope={B:.4f}) without positive forward crossing.",
                )
            t_star = -C / B

        # Case 3: Quadratic Regime (|A| >= 1e-5)
        else:
            discriminant = B**2 - 4.0 * A * C
            if discriminant < 0.0:
                return TimeToRiskEstimate(
                    estimated_cycles_to_critical=None,
                    estimated_hours_to_critical=None,
                    trajectory_direction="FALLING" if v < 0 else "DECELERATING",
                    crossing_probability=0.10,
                    is_estimable=False,
                    reason="Parabolic trajectory does not reach critical threshold (negative discriminant).",
                )

            sqrt_d = np.sqrt(discriminant)
            t1 = (-B + sqrt_d) / (2.0 * A)
            t2 = (-B - sqrt_d) / (2.0 * A)

            positive_roots = [t for t in [t1, t2] if t > 1e-4]
            if not positive_roots:
                return TimeToRiskEstimate(
                    estimated_cycles_to_critical=None,
                    estimated_hours_to_critical=None,
                    trajectory_direction="FALLING" if v < 0 else "STABLE",
                    crossing_probability=0.05,
                    is_estimable=False,
                    reason="No positive forward crossing roots exist in future timeline.",
                )
            t_star = float(min(positive_roots))

        # Case 4: Operational Horizon Boundary Check
        if t_star > self.max_extrapolation_cycles:
            return TimeToRiskEstimate(
                estimated_cycles_to_critical=None,
                estimated_hours_to_critical=None,
                trajectory_direction="RISING",
                crossing_probability=0.20,
                is_estimable=False,
                reason=f"Projected crossing horizon ({t_star:.1f} cycles) exceeds operational forecast window (max {self.max_extrapolation_cycles:.0f} cycles).",
            )

        est_hours = float(round(t_star * self.cycle_interval_hours, 1))
        crossing_prob = float(np.clip(P0 + (1.0 - P0) * (v / 0.20), 0.15, 0.95))
        direction = "ACCELERATING" if a > 0.015 else ("RISING" if v > 0.03 else "STABLE")

        return TimeToRiskEstimate(
            estimated_cycles_to_critical=round(t_star, 2),
            estimated_hours_to_critical=est_hours,
            trajectory_direction=direction,
            crossing_probability=round(crossing_prob, 3),
            is_estimable=True,
            reason=f"Closed-form kinematic projection: critical crossing in approx {est_hours:.1f} hours ({t_star:.2f} cycles).",
        )

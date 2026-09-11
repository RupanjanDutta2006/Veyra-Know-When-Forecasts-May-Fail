"""
Forecast Instability & Change-Point Detector (Day 16).

Detects sudden risk jumps, explosive ensemble spread expansions, and sharp
forecast revision reversals across successive issue cycles.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from evaluation.decision_policy import ParameterGovernanceClass


@dataclass
class InstabilitySignal:
    """Diagnostic signal produced by the instability detector."""
    detected: bool
    instability_score: float
    reason: Optional[str] = None
    sudden_risk_jump: bool = False
    spread_explosion: bool = False
    revision_shock: bool = False
    reversal_detected: bool = False


class ForecastInstabilityDetector:
    """
    Lightweight robust change-point and instability detector for forecast evolution trajectories.
    """

    # Governance Registry
    GOVERNANCE = {
        "risk_jump_threshold": (0.20, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "spread_expansion_ratio": (1.50, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "revision_shock_threshold": (2.50, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "volatility_ceiling": (0.18, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
    }

    def __init__(
        self,
        risk_jump_threshold: float = 0.20,
        spread_expansion_ratio: float = 1.50,
        revision_shock_threshold: float = 2.50,
        volatility_ceiling: float = 0.18,
    ):
        self.risk_jump_threshold = risk_jump_threshold
        self.spread_expansion_ratio = spread_expansion_ratio
        self.revision_shock_threshold = revision_shock_threshold
        self.volatility_ceiling = volatility_ceiling

    def detect_instability(self, temporal_features: Dict[str, float]) -> InstabilitySignal:
        """
        Evaluate temporal features for change-point and trajectory instability.
        """
        seq_len = int(temporal_features.get("sequence_length", 1))
        if seq_len < 2:
            return InstabilitySignal(detected=False, instability_score=0.0)

        risk_delta = temporal_features.get("risk_delta", 0.0)
        risk_accel = temporal_features.get("risk_acceleration", 0.0)
        spread_delta = temporal_features.get("spread_delta", 0.0)
        curr_spread = temporal_features.get("current_spread", 1.0)
        prev_spread = curr_spread - spread_delta
        rev_vel = temporal_features.get("revision_velocity", 0.0)
        reversal_flag = bool(temporal_features.get("direction_reversal_flag", 0.0))
        volatility = temporal_features.get("risk_volatility", 0.0)

        sudden_risk_jump = False
        spread_explosion = False
        revision_shock = False
        reversal_detected = reversal_flag and (rev_vel >= 1.0)

        reasons = []
        scores = []

        # 1. Sudden probability jump (e.g. +20% risk in single cycle)
        if risk_delta >= self.risk_jump_threshold:
            sudden_risk_jump = True
            jump_score = min(1.0, risk_delta / 0.40)
            scores.append(jump_score)
            reasons.append(f"Sudden probability jump (+{risk_delta*100:.1f}%)")

        # 2. Explosive spread expansion (e.g. ensemble spread surged > 50%)
        if prev_spread > 0.05 and (curr_spread / prev_spread) >= self.spread_expansion_ratio and spread_delta > 0.5:
            spread_explosion = True
            spread_score = min(1.0, (curr_spread / prev_spread - 1.0))
            scores.append(spread_score)
            reasons.append(f"Explosive ensemble spread expansion ({curr_spread/prev_spread:.1f}x)")

        # 3. Revision shock (large trajectory jump between cycles)
        if rev_vel >= self.revision_shock_threshold:
            revision_shock = True
            rev_score = min(1.0, rev_vel / (self.revision_shock_threshold * 2.0))
            scores.append(rev_score)
            reasons.append(f"Abrupt forecast revision shock ({rev_vel:.2f} units)")

        # 4. Volatility or reversal under elevated risk
        if reversal_detected:
            scores.append(0.5)
            reasons.append("Sharp forecast revision direction reversal")

        if volatility >= self.volatility_ceiling and temporal_features.get("current_risk", 0.0) >= 0.20:
            scores.append(min(1.0, volatility / 0.30))
            reasons.append(f"Elevated risk trajectory volatility (sigma={volatility:.3f})")

        detected = sudden_risk_jump or spread_explosion or revision_shock or (reversal_detected and volatility >= 0.10)
        final_score = float(np.max(scores)) if scores else 0.0
        reason_str = "; ".join(reasons) if reasons else None

        return InstabilitySignal(
            detected=detected,
            instability_score=round(final_score, 4),
            reason=reason_str,
            sudden_risk_jump=sudden_risk_jump,
            spread_explosion=spread_explosion,
            revision_shock=revision_shock,
            reversal_detected=reversal_detected,
        )

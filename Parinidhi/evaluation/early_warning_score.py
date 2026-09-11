"""
Temporal Early-Warning Score & Horizon Classification (Day 16).

Integrates current calibrated risk, normalized trajectory momentum, persistence,
dimensionless uncertainty escalation, and analogue support into an interpretable
dimensionless Early-Warning Score (0.0 to 1.0) and assigns operational Warning Horizons.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

from evaluation.decision_policy import ParameterGovernanceClass
from evaluation.trajectory_schema import WarningHorizon


class TemporalEarlyWarningScore:
    """
    Computes a dimensionally consistent, normalized composite Early-Warning Score (EWS)
    in [0.0, 1.0] and maps to the appropriate operational WarningHorizon.

    All heterogeneous physical and derivative terms are normalized by reference scales
    into dimensionless [0.0, 1.0] components before convex combination.
    """

    GOVERNANCE = {
        "w_base": (0.45, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "w_momentum": (0.20, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "w_acceleration": (0.10, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "w_persistence": (0.15, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "w_spread_growth": (0.10, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "scale_risk_slope": (0.15, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "scale_risk_accel": (0.08, ParameterGovernanceClass.VALIDATED_FROM_HISTORICAL_DATA),
        "scale_persistence": (3.0, ParameterGovernanceClass.OPERATIONAL_POLICY_PARAMETER),
        "spread_floor": (0.10, ParameterGovernanceClass.DEFAULT_CONFIGURABLE_ASSUMPTION),
    }

    def __init__(
        self,
        w_base: float = 0.45,
        w_momentum: float = 0.20,
        w_acceleration: float = 0.10,
        w_persistence: float = 0.15,
        w_spread_growth: float = 0.10,
        scale_risk_slope: float = 0.15,
        scale_risk_accel: float = 0.08,
        scale_persistence: float = 3.0,
        spread_floor: float = 0.10,
    ):
        self.w_base = w_base
        self.w_momentum = w_momentum
        self.w_acceleration = w_acceleration
        self.w_persistence = w_persistence
        self.w_spread_growth = w_spread_growth
        self.scale_risk_slope = max(1e-4, scale_risk_slope)
        self.scale_risk_accel = max(1e-4, scale_risk_accel)
        self.scale_persistence = max(1.0, scale_persistence)
        self.spread_floor = max(1e-4, spread_floor)

    def compute_score(
        self,
        temporal_features: Dict[str, float],
        historical_failure_rate: float = 0.0,
    ) -> Tuple[float, WarningHorizon, Dict[str, float]]:
        """
        Compute composite EWS in [0.0, 1.0] from strictly dimensionless components.
        """
        curr_risk = float(np.clip(temporal_features.get("current_risk", 0.0), 0.0, 1.0))
        risk_slope = float(temporal_features.get("risk_slope", 0.0))
        risk_accel = float(temporal_features.get("risk_acceleration", 0.0))
        persist_count = float(temporal_features.get("risk_persistence_count", 0.0))
        spread_delta = float(temporal_features.get("spread_delta", 0.0))
        curr_spread = float(temporal_features.get("current_spread", 1.0))
        prev_spread = max(self.spread_floor, curr_spread - spread_delta)
        lead_hours = float(temporal_features.get("current_lead_hours", 24.0))

        # 1. Dimensionless Normalized Momentum (Positive Risk Velocity)
        norm_momentum = float(np.clip(risk_slope / self.scale_risk_slope, 0.0, 1.0))

        # 2. Dimensionless Normalized Acceleration (Positive Risk Concavity)
        norm_accel = float(np.clip(risk_accel / self.scale_risk_accel, 0.0, 1.0))

        # 3. Dimensionless Normalized Persistence
        norm_persist = float(np.clip(persist_count / self.scale_persistence, 0.0, 1.0))

        # 4. Dimensionless Fractional Spread Expansion
        # Ratio of spread increase relative to baseline spread: delta_sigma / sigma_prev
        frac_spread_growth = float(np.clip(max(0.0, spread_delta) / prev_spread, 0.0, 1.0))

        # Linear combination of strictly dimensionless components in [0.0, 1.0]
        raw_ews = (
            self.w_base * curr_risk
            + self.w_momentum * norm_momentum
            + self.w_acceleration * norm_accel
            + self.w_persistence * norm_persist
            + self.w_spread_growth * frac_spread_growth
        )

        # 5. Historical Trajectory Analogue Boost (if verified empirical failure rate is elevated)
        if historical_failure_rate > 0.30:
            analogue_boost = min(0.10, (historical_failure_rate - 0.30) * 0.20)
            raw_ews += analogue_boost

        # 6. Novelty Penalty (downgrades synthetic alarm confidence in uncalibrated regime)
        novelty = float(temporal_features.get("mean_novelty", 1.0))
        if novelty > 1.5:
            penalty = min(0.15, (novelty - 1.5) * 0.10)
            raw_ews -= penalty

        ews = float(np.clip(raw_ews, 0.0, 1.0))

        # Operational Horizon Assignment based on EWS and lead time urgency
        if ews >= 0.70 or (ews >= 0.55 and lead_hours <= 12.0):
            horizon = WarningHorizon.CRITICAL
        elif ews >= 0.50 or (ews >= 0.35 and lead_hours <= 24.0):
            horizon = WarningHorizon.IMMINENT
        elif ews >= 0.30 or (ews >= 0.20 and lead_hours <= 48.0):
            horizon = WarningHorizon.EARLY_WARNING
        else:
            horizon = WarningHorizon.WATCH

        breakdown = {
            "dimless_base_risk": round(curr_risk, 4),
            "dimless_momentum": round(norm_momentum, 4),
            "dimless_acceleration": round(norm_accel, 4),
            "dimless_persistence": round(norm_persist, 4),
            "dimless_spread_growth": round(frac_spread_growth, 4),
            "raw_ews": round(raw_ews, 4),
            "final_ews": round(ews, 4),
        }

        return round(ews, 4), horizon, breakdown

"""
Temporal Feature Extraction Engine (Day 16).

Extracts scientifically meaningful temporal dynamics across issue cycles for a target valid time:
- Risk velocity and acceleration
- Ensemble dispersion dynamics
- Forecast revision velocity and direction reversals
- Risk persistence and volatility
- Temporal data quality and sequence freshness
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from evaluation.trajectory_schema import ForecastTrajectory, ForecastTrajectoryPoint


class TemporalFeatureExtractor:
    """
    Computes temporal derivatives, rolling statistics, and revision metrics
    from an ordered sequence of issue-time forecast states.
    """

    # Forbidden verification-time columns (Target Leakage Gate)
    FORBIDDEN_TARGET_COLUMNS = {
        "truth_value",
        "forecast_error",
        "forecast_abs_error",
        "ensemble_mean_error",
        "ensemble_mean_abs_error",
        "bust_label",
        "is_bust",
    }

    def __init__(self, min_sequence_length: int = 2):
        self.min_sequence_length = min_sequence_length

    def extract_trajectory_features(self, trajectory: ForecastTrajectory) -> Dict[str, float]:
        """
        Extract complete dictionary of temporal dynamic features from a ForecastTrajectory.
        Guarantees zero future target leakage.
        """
        pts = trajectory.points
        n = len(pts)

        if n == 0:
            return self._default_empty_features()

        # Audit against target leakage in features
        for pt in pts:
            leaked = set(pt.features.keys()) & self.FORBIDDEN_TARGET_COLUMNS
            if leaked:
                raise ValueError(f"Target leakage detected in trajectory point features: {leaked}")

        # Extract primary series
        risks = np.array([p.calibrated_risk for p in pts], dtype=float)
        spreads = np.array([p.ensemble_std for p in pts], dtype=float)
        forecasts = np.array([p.forecast_value for p in pts], dtype=float)
        leads = np.array([p.lead_hours for p in pts], dtype=float)
        novelties = np.array([p.novelty_score for p in pts], dtype=float)
        missing_fracs = np.array([p.missing_fraction for p in pts], dtype=float)

        current_risk = float(risks[-1])
        current_spread = float(spreads[-1])
        current_lead = float(leads[-1])
        current_novelty = float(novelties[-1])

        if n < self.min_sequence_length:
            # Single-point baseline
            return {
                "sequence_length": float(n),
                "current_risk": current_risk,
                "prev_risk": current_risk,
                "risk_delta": 0.0,
                "risk_slope": 0.0,
                "risk_acceleration": 0.0,
                "rolling_max_risk": current_risk,
                "rolling_mean_risk": current_risk,
                "risk_volatility": 0.0,
                "risk_persistence_count": 1.0 if current_risk >= 0.22 else 0.0,
                "consecutive_rising_cycles": 0.0,
                "current_spread": current_spread,
                "spread_delta": 0.0,
                "spread_slope": 0.0,
                "spread_acceleration": 0.0,
                "current_forecast": float(forecasts[-1]),
                "forecast_revision_abs": 0.0,
                "revision_velocity": 0.0,
                "revision_acceleration": 0.0,
                "direction_reversal_flag": 0.0,
                "current_lead_hours": current_lead,
                "lead_reduction_rate": 0.0,
                "mean_novelty": current_novelty,
                "max_novelty": current_novelty,
                "mean_missing_fraction": float(missing_fracs[-1]),
                "is_sufficient_history": 0.0,
            }

        # Temporal deltas (t vs t-1)
        risk_delta = float(risks[-1] - risks[-2])
        prev_risk = float(risks[-2])
        spread_delta = float(spreads[-1] - spreads[-2])
        forecast_rev_abs = float(abs(forecasts[-1] - forecasts[-2]))

        # Approximate slopes per cycle step
        # Risk slope over last 3 points if available
        if n >= 3:
            risk_slope = float((risks[-1] - risks[-3]) / 2.0)
            prev_risk_slope = float((risks[-2] - risks[-4]) / 2.0 if n >= 4 else (risks[-2] - risks[-3]))
            risk_acceleration = float(risk_slope - prev_risk_slope)
            spread_slope = float((spreads[-1] - spreads[-3]) / 2.0)
            prev_spread_slope = float((spreads[-2] - spreads[-4]) / 2.0 if n >= 4 else (spreads[-2] - spreads[-3]))
            spread_acceleration = float(spread_slope - prev_spread_slope)
            rev_velocity = float((abs(forecasts[-1] - forecasts[-2]) + abs(forecasts[-2] - forecasts[-3])) / 2.0)
            prev_rev = float(abs(forecasts[-2] - forecasts[-3]))
            curr_rev = float(abs(forecasts[-1] - forecasts[-2]))
            rev_acceleration = float(curr_rev - prev_rev)
        else:
            risk_slope = risk_delta
            risk_acceleration = 0.0
            spread_slope = spread_delta
            spread_acceleration = 0.0
            rev_velocity = forecast_rev_abs
            rev_acceleration = 0.0

        # Rolling statistics
        rolling_window = min(n, 5)
        recent_risks = risks[-rolling_window:]
        rolling_max_risk = float(np.max(recent_risks))
        rolling_mean_risk = float(np.mean(recent_risks))
        risk_volatility = float(np.std(recent_risks))

        # Risk persistence count (consecutive cycles where risk >= 0.22 elevated threshold)
        persistence_count = 0
        for r in reversed(risks):
            if r >= 0.22:
                persistence_count += 1
            else:
                break

        # Consecutive rising cycles
        rising_count = 0
        for i in range(len(risks) - 1, 0, -1):
            if risks[i] > risks[i-1]:
                rising_count += 1
            else:
                break

        # Direction reversal check in forecast revisions (e.g. F rose then dropped)
        direction_reversal = 0.0
        if n >= 3:
            diff1 = forecasts[-1] - forecasts[-2]
            diff2 = forecasts[-2] - forecasts[-3]
            if (diff1 * diff2) < -1e-5:
                direction_reversal = 1.0

        return {
            "sequence_length": float(n),
            "current_risk": current_risk,
            "prev_risk": prev_risk,
            "risk_delta": risk_delta,
            "risk_slope": risk_slope,
            "risk_acceleration": risk_acceleration,
            "rolling_max_risk": rolling_max_risk,
            "rolling_mean_risk": rolling_mean_risk,
            "risk_volatility": risk_volatility,
            "risk_persistence_count": float(persistence_count),
            "consecutive_rising_cycles": float(rising_count),
            "current_spread": current_spread,
            "spread_delta": spread_delta,
            "spread_slope": spread_slope,
            "spread_acceleration": spread_acceleration,
            "current_forecast": float(forecasts[-1]),
            "forecast_revision_abs": forecast_rev_abs,
            "revision_velocity": rev_velocity,
            "revision_acceleration": rev_acceleration,
            "direction_reversal_flag": direction_reversal,
            "current_lead_hours": current_lead,
            "lead_reduction_rate": float(leads[0] - leads[-1]) if n > 1 else 0.0,
            "mean_novelty": float(np.mean(novelties)),
            "max_novelty": float(np.max(novelties)),
            "mean_missing_fraction": float(np.mean(missing_fracs)),
            "is_sufficient_history": 1.0 if n >= 2 else 0.0,
        }

    def _default_empty_features(self) -> Dict[str, float]:
        return {
            "sequence_length": 0.0,
            "current_risk": 0.0,
            "prev_risk": 0.0,
            "risk_delta": 0.0,
            "risk_slope": 0.0,
            "risk_acceleration": 0.0,
            "rolling_max_risk": 0.0,
            "rolling_mean_risk": 0.0,
            "risk_volatility": 0.0,
            "risk_persistence_count": 0.0,
            "consecutive_rising_cycles": 0.0,
            "current_spread": 0.0,
            "spread_delta": 0.0,
            "spread_slope": 0.0,
            "spread_acceleration": 0.0,
            "current_forecast": 0.0,
            "forecast_revision_abs": 0.0,
            "revision_velocity": 0.0,
            "revision_acceleration": 0.0,
            "direction_reversal_flag": 0.0,
            "current_lead_hours": 0.0,
            "lead_reduction_rate": 0.0,
            "mean_novelty": 1.0,
            "max_novelty": 1.0,
            "mean_missing_fraction": 0.0,
            "is_sufficient_history": 0.0,
        }

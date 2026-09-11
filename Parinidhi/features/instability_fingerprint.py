"""
Forecast Instability Fingerprint Engine.

Constructs an interpretable, structured 6-group evidence fingerprint characterizing
forecast instability, trajectory dynamics, ensemble dispersion, and horizon degradation.

Scientific Integrity & Determinism:
- Does not invent an arbitrary composite score.
- Uses variable-specific physical tolerance thresholds.
- Uses neutral UP/DOWN directional regime indicators.
- Employs strict, deterministic regime precedence rules.
- Computes issue-time safe climatological error growth approximations.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from labels.label_engine import assign_lead_bin

# Variable-specific tolerance defaults for trajectory classification
DEFAULT_VARIABLE_TOLERANCES = {
    "temperature_2m": {"eps": 0.20, "eps_spread": 0.15, "unit": "degC"},
    "surface_pressure": {"eps": 0.50, "eps_spread": 0.30, "unit": "hPa"},
    "wind_speed_10m": {"eps": 1.00, "eps_spread": 0.50, "unit": "km/h"},
}

# Empirical training-period climatological error growth factors by lead bin (fitted strictly on historical pilot data)
DEFAULT_CLIMATOLOGICAL_GROWTH_FACTORS = {
    "day1": 1.00,
    "day2_3": 1.18,
    "day4_6": 1.45,
    "day7_10": 1.82,
    "day10_plus": 2.20,
}


def classify_forecast_trajectory(
    delta_1: Optional[float],
    delta_2: Optional[float],
    spread_curr: Optional[float],
    spread_prev: Optional[float],
    variable: str = "temperature_2m",
    custom_eps: Optional[float] = None,
    custom_eps_spread: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deterministically classify the forecast trajectory regime using variable-specific tolerance
    and unambiguous precedence ordering.

    Args:
        delta_1: Recent revision shift: X(T, V) - X(T-6h, V).
        delta_2: Preceding revision shift: X(T-6h, V) - X(T-12h, V).
        spread_curr: Current ensemble standard deviation: std(T, V).
        spread_prev: Preceding ensemble standard deviation: std(T-6h, V).
        variable: Meteorological variable name.
        custom_eps: Optional override for revision tolerance.
        custom_eps_spread: Optional override for spread expansion tolerance.

    Returns:
        Dict with keys:
            - 'regime': String classification identifier.
            - 'is_oscillating': Boolean flag.
            - 'tolerance_eps': Numerical tolerance applied.
    """
    v_cfg = DEFAULT_VARIABLE_TOLERANCES.get(variable, {"eps": 0.5, "eps_spread": 0.25})
    eps = custom_eps if custom_eps is not None else v_cfg["eps"]
    eps_spread = custom_eps_spread if custom_eps_spread is not None else v_cfg["eps_spread"]

    # 1. Check for missing data / insufficient cycles
    if delta_1 is None or np.isnan(delta_1) or delta_2 is None or np.isnan(delta_2):
        return {
            "regime": "INSUFFICIENT_CYCLES",
            "is_oscillating": False,
            "tolerance_eps": eps,
            "precedence_rule": "Missing prior cycle revisions for identical valid time",
        }

    abs_d1 = abs(delta_1)
    abs_d2 = abs(delta_2)

    # 2. Precedence Rule 1: STABLE (both revision steps within physical tolerance)
    if abs_d1 <= eps and abs_d2 <= eps:
        return {
            "regime": "STABLE",
            "is_oscillating": False,
            "tolerance_eps": eps,
            "precedence_rule": "Both consecutive 6h shifts within tolerance",
        }

    # 3. Precedence Rule 2: OSCILLATING (Flip-Flop: opposite non-zero signs exceeding tolerance)
    sgn_1 = np.sign(delta_1)
    sgn_2 = np.sign(delta_2)
    if (sgn_1 != sgn_2) and (abs_d1 > eps) and (abs_d2 > eps):
        return {
            "regime": "OSCILLATING",
            "is_oscillating": True,
            "tolerance_eps": eps,
            "precedence_rule": "Consecutive revisions changed sign (flip-flop)",
        }

    # 4. Precedence Rule 3: CONVERGING (Revision magnitude shrinking and spread stable/contracting)
    spread_diff = (spread_curr - spread_prev) if (spread_curr is not None and spread_prev is not None and not np.isnan(spread_curr) and not np.isnan(spread_prev)) else 0.0
    if (abs_d1 < 0.5 * abs_d2) and (spread_diff <= eps_spread):
        return {
            "regime": "CONVERGING",
            "is_oscillating": False,
            "tolerance_eps": eps,
            "precedence_rule": "Revision delta decayed by >50% and ensemble spread not expanding",
        }

    # 5. Precedence Rule 4: DIVERGING (Spread expanding significantly)
    if spread_diff > eps_spread:
        return {
            "regime": "DIVERGING",
            "is_oscillating": False,
            "tolerance_eps": eps,
            "precedence_rule": "Ensemble spread expanded across cycles",
        }

    # 6. Precedence Rule 5: MONOTONIC_DRIFT (Same directional shift exceeding tolerance)
    if (sgn_1 == sgn_2) and (abs_d1 > eps or abs_d2 > eps):
        direction_label = "UP" if sgn_1 > 0 else "DOWN"
        # Contextual alias for temperature if desired, but neutral label is primary
        return {
            "regime": f"MONOTONIC_DRIFT_{direction_label}",
            "is_oscillating": False,
            "tolerance_eps": eps,
            "precedence_rule": f"Consistent {direction_label} drift across consecutive cycles",
        }

    # 7. Default fallback
    return {
        "regime": "UNCLASSIFIED_DRIFT",
        "is_oscillating": False,
        "tolerance_eps": eps,
        "precedence_rule": "Indeterminate trajectory shift",
    }


class ForecastInstabilityFingerprintEngine:
    """
    Engine to build the structured 6-group Forecast Instability Fingerprint from feature rows.
    """

    def __init__(
        self,
        tolerances: Optional[Dict[str, Dict[str, float]]] = None,
        growth_factors: Optional[Dict[str, float]] = None,
    ):
        self.tolerances = tolerances or DEFAULT_VARIABLE_TOLERANCES
        self.growth_factors = growth_factors or DEFAULT_CLIMATOLOGICAL_GROWTH_FACTORS

    def build_fingerprint(
        self,
        row: Union[pd.Series, Dict[str, Any]],
        variable: str = "temperature_2m",
    ) -> Dict[str, Any]:
        """
        Build the complete 6-group instability fingerprint for a single forecast record.

        Args:
            row: Series or Dict containing forecast, ensemble, and revision features.
            variable: Meteorological variable identifier.

        Returns:
            Structured fingerprint dict.
        """
        def get_val(k: str, default: float = np.nan) -> Any:
            if k not in row:
                return default
            val = row[k]
            if isinstance(val, (pd.Series, np.ndarray, list)):
                val = val.iloc[0] if isinstance(val, pd.Series) else val[0]
            if val is None or (isinstance(val, (float, np.floating)) and np.isnan(val)):
                return default
            return val

        # 1. Group A: Revision Instability
        d6 = get_val("forecast_delta_6h")
        d12 = get_val("forecast_delta_12h")
        d24 = get_val("forecast_delta_24h")
        mag6 = abs(d6) if not np.isnan(d6) else np.nan
        mag12 = abs(d12) if not np.isnan(d12) else np.nan
        mag24 = abs(d24) if not np.isnan(d24) else np.nan
        accel6 = get_val("revision_accel_6h")

        # Prior revision shift delta_2 for trajectory classification:
        # Since accel6 = (delta_1 - delta_2)/6  => delta_2 = delta_1 - 6 * accel6
        delta_2 = (d6 - 6.0 * accel6) if (not np.isnan(d6) and not np.isnan(accel6)) else np.nan

        # 2. Group B: Ensemble Dispersion
        std = get_val("ensemble_std", 0.0)
        rng = get_val("ensemble_range", 0.0)
        iqr = get_val("ensemble_iqr", 0.0)
        cv = get_val("ensemble_cv", 0.0)

        # 3. Group C: Spread Dynamics
        spread_d6 = get_val("ensemble_spread_delta_6h")
        spread_d24 = get_val("ensemble_spread_delta_24h")
        spread_accel6 = get_val("spread_accel_6h")

        if np.isnan(spread_d6):
            spread_regime = "NO_PRIOR_CYCLE"
        elif spread_d6 > 0.15:
            spread_regime = "EXPANDING_UNCERTAINTY"
        elif spread_d6 < -0.15:
            spread_regime = "COLLAPSING_UNCERTAINTY"
        else:
            spread_regime = "SPREAD_STABLE"

        # 4. Group D: Forecast Trajectory
        traj_res = classify_forecast_trajectory(
            delta_1=d6,
            delta_2=delta_2,
            spread_curr=std,
            spread_prev=(std - spread_d6) if not np.isnan(spread_d6) else None,
            variable=variable,
        )

        # 5. Group E: Ensemble Shape & Skew
        skew = get_val("ensemble_skew_proxy", 0.0)
        spread_to_iqr = get_val("ensemble_spread_to_iqr_ratio", 0.0)
        if skew > 0.3:
            tail_regime = "UPWARD_SKEWED"
        elif skew < -0.3:
            tail_regime = "DOWNWARD_SKEWED"
        else:
            tail_regime = "SYMMETRIC"

        # 6. Group F: Horizon Pressure
        lead_h = int(get_val("lead_hours", 0))
        lead_b = assign_lead_bin(lead_h)
        clim_growth = self.growth_factors.get(lead_b, 1.0)

        fingerprint = {
            "fingerprint_version": "v1-experimental",
            "variable": variable,
            "lead_hours": lead_h,
            "revision_instability": {
                "delta_6h": float(d6) if not np.isnan(d6) else None,
                "delta_12h": float(d12) if not np.isnan(d12) else None,
                "delta_24h": float(d24) if not np.isnan(d24) else None,
                "magnitude_6h": float(mag6) if not np.isnan(mag6) else None,
                "magnitude_12h": float(mag12) if not np.isnan(mag12) else None,
                "magnitude_24h": float(mag24) if not np.isnan(mag24) else None,
                "acceleration_6h": float(accel6) if not np.isnan(accel6) else None,
                "oscillation_detected": bool(traj_res["is_oscillating"]),
            },
            "ensemble_dispersion": {
                "ensemble_std": round(float(std), 4),
                "ensemble_range": round(float(rng), 4),
                "ensemble_iqr": round(float(iqr), 4),
                "ensemble_cv": round(float(cv), 4),
            },
            "spread_dynamics": {
                "spread_delta_6h": float(spread_d6) if not np.isnan(spread_d6) else None,
                "spread_delta_24h": float(spread_d24) if not np.isnan(spread_d24) else None,
                "spread_acceleration_6h": float(spread_accel6) if not np.isnan(spread_accel6) else None,
                "spread_growth_regime": spread_regime,
            },
            "forecast_trajectory": {
                "regime": traj_res["regime"],
                "precedence_applied": traj_res["precedence_rule"],
                "tolerance_applied": traj_res["tolerance_eps"],
            },
            "ensemble_shape": {
                "skew_proxy": round(float(skew), 4),
                "spread_to_iqr_ratio": round(float(spread_to_iqr), 4),
                "distribution_tail": tail_regime,
            },
            "horizon_pressure": {
                "lead_hours": lead_h,
                "lead_bin": lead_b,
                "climatological_error_growth_factor": round(float(clim_growth), 2),
            },
        }

        return fingerprint

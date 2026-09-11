"""
Forecast Uncertainty Decomposition Module (Day 14).

Decomposes issue-time forecast uncertainty into structured operational proxies:
1. Aleatoric / Dispersion Uncertainty: NWP ensemble member divergence, spread, and range.
2. Epistemic / Novelty Uncertainty: Feature-space distance from familiar training distributions.
3. Dynamic Instability Uncertainty: Rapid inter-cycle forecast revision volatility.
4. Horizon Decay Uncertainty: Growth in intrinsic physical unpredictability with forecast lead time.

Scientific Disclaimer:
These represent structured operational proxies for uncertainty decomposition, not
philosophically absolute separations.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from evaluation.novelty import FeatureNoveltyDetector


class UncertaintyDecomposer:
    """
    Decomposes issue-time forecast state into distinct operational uncertainty signals.
    """

    def __init__(self, novelty_detector: Optional[FeatureNoveltyDetector] = None):
        self.novelty_detector = novelty_detector

    def decompose(
        self,
        features: Union[pd.Series, pd.DataFrame, Dict[str, Any]],
        variable: str = "temperature_2m",
    ) -> Dict[str, Any]:
        """
        Decompose uncertainty for a single forecast issue instance.

        Args:
            features: Dictionary or Series of issue-time features.
            variable: Meteorological variable name ('temperature_2m', 'surface_pressure', 'wind_speed_10m').

        Returns:
            Structured dictionary of uncertainty components and dominant source.
        """
        if isinstance(features, pd.DataFrame):
            row = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            row = features.to_dict()
        else:
            row = dict(features)

        # 1. Aleatoric / Physical Dispersion Proxy
        ens_std = float(row.get("ensemble_std", 1.0)) if not pd.isna(row.get("ensemble_std", np.nan)) else 1.0
        ens_range = float(row.get("ensemble_range", 4.0 * ens_std)) if not pd.isna(row.get("ensemble_range", np.nan)) else 4.0 * ens_std
        ens_iqr = float(row.get("ensemble_iqr", 2.56 * ens_std)) if not pd.isna(row.get("ensemble_iqr", np.nan)) else 2.56 * ens_std

        # Normalization factors by physical variable
        if "temp" in variable.lower():
            ref_std_scale = 3.5  # Typical high spread in temperature
        elif "press" in variable.lower():
            ref_std_scale = 4.0  # Typical high spread in surface pressure
        else:
            ref_std_scale = 8.0  # Typical high spread in wind speed

        aleatoric_score = min(ens_std / max(ref_std_scale, 1e-3), 1.0)

        # 2. Dynamic Instability Proxy (Inter-Cycle Revisions)
        delta_6h = abs(float(row.get("forecast_delta_6h", 0.0))) if not pd.isna(row.get("forecast_delta_6h", np.nan)) else 0.0
        delta_24h = abs(float(row.get("forecast_delta_24h", 0.0))) if not pd.isna(row.get("forecast_delta_24h", np.nan)) else 0.0
        spread_delta = abs(float(row.get("ensemble_spread_delta_24h", 0.0))) if not pd.isna(row.get("ensemble_spread_delta_24h", np.nan)) else 0.0

        instability_raw = 0.5 * (delta_6h / max(ref_std_scale * 0.5, 1e-3)) + 0.5 * (delta_24h / max(ref_std_scale, 1e-3))
        instability_score = min(max(instability_raw, 0.0), 1.0)

        # 3. Horizon Decay Proxy
        lead_hours = float(row.get("lead_hours", 24.0)) if not pd.isna(row.get("lead_hours", np.nan)) else 24.0
        horizon_score = min(max(lead_hours / 72.0, 0.0), 1.0)

        # 4. Epistemic / Feature Novelty Proxy
        if self.novelty_detector is not None and self.novelty_detector.is_fitted_:
            nov_eval = self.novelty_detector.evaluate_sample(row)
            raw_nov = nov_eval["novelty_score"]
            # Scale novelty score (1.0 -> 0.25, 2.0 -> 0.60, 3.0+ -> 1.0)
            epistemic_score = min(max((raw_nov - 0.5) / 2.5, 0.0), 1.0)
            novelty_state = nov_eval["novelty_state"]
        else:
            epistemic_score = 0.15  # Baseline default when detector is not fitted
            novelty_state = "UNAUDITED"

        # Determine dominant uncertainty driver
        scores = {
            "ENSEMBLE_DISPERSION": aleatoric_score,
            "RECENT_INSTABILITY": instability_score,
            "LEAD_TIME_HORIZON": horizon_score,
            "FEATURE_SPACE_NOVELTY": epistemic_score,
        }
        dominant_driver = max(scores, key=scores.get)

        # Composite uncertainty index
        composite_index = round(float(0.40 * aleatoric_score + 0.25 * instability_score + 0.20 * horizon_score + 0.15 * epistemic_score), 4)

        return {
            "composite_uncertainty_score": composite_index,
            "dominant_uncertainty_driver": dominant_driver,
            "components": {
                "aleatoric_dispersion": {
                    "score": round(float(aleatoric_score), 4),
                    "ensemble_std": round(float(ens_std), 2),
                    "ensemble_range": round(float(ens_range), 2),
                    "ensemble_iqr": round(float(ens_iqr), 2),
                    "interpretation": "Physical ensemble member disagreement around initialization trajectory.",
                },
                "dynamic_instability": {
                    "score": round(float(instability_score), 4),
                    "abs_delta_6h": round(float(delta_6h), 2),
                    "abs_delta_24h": round(float(delta_24h), 2),
                    "spread_delta_24h": round(float(spread_delta), 2),
                    "interpretation": "Volatility and magnitude of recent inter-cycle model forecast revisions.",
                },
                "horizon_decay": {
                    "score": round(float(horizon_score), 4),
                    "lead_hours": int(lead_hours),
                    "interpretation": "Natural error growth and predictability loss across extended forecast horizons.",
                },
                "epistemic_novelty": {
                    "score": round(float(epistemic_score), 4),
                    "novelty_state": novelty_state,
                    "interpretation": "Distance of current meteorological feature vector from familiar training cases.",
                },
            },
            "scientific_disclaimer": "Operational uncertainty proxies derived strictly from issue-time features.",
        }

"""
Forecast Risk Attribution Engine (Day 14).

Computes deterministic, model-compatible feature attributions to explain
why Veyra predicts elevated or suppressed forecast-bust risk.

Scientific Safeguards:
- Deterministic mathematical attribution (zero LLM in runtime path).
- Ranks feature drivers by signed contribution and normalized magnitude.
- Generates domain-grounded meteorological explanations from verified rule templates.
- Strict anti-leakage audit: Target/verification features are blacklisted.
"""

from typing import Any, Callable, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from features.contract import validate_feature_contract


# Deterministic Domain Meteorological Explanation Templates
METEOROLOGICAL_EXPLANATION_TEMPLATES = {
    "ensemble_std": {
        "INCREASES_RISK": "Elevated ensemble spread indicates substantial uncertainty and member divergence across NWP trajectories.",
        "DECREASES_RISK": "Tightly clustered ensemble members indicate consistent model agreement across initializations.",
    },
    "ensemble_range": {
        "INCREASES_RISK": "Extreme spread between maximum and minimum ensemble members signals outlier scenarios.",
        "DECREASES_RISK": "Narrow range between ensemble extremes indicates bounded forecast uncertainty.",
    },
    "ensemble_iqr": {
        "INCREASES_RISK": "Wide interquartile member spread indicates core distribution dispersion.",
        "DECREASES_RISK": "Compact interquartile member spread indicates central forecast consensus.",
    },
    "forecast_delta_6h": {
        "INCREASES_RISK": "Significant short-term forecast revision over prior 6 hours signals initialization instability.",
        "DECREASES_RISK": "Stable forecast trajectory across recent 6-hour cycle.",
    },
    "forecast_delta_24h": {
        "INCREASES_RISK": "Large cumulative 24-hour forecast adjustment indicates persistent structural model shifts.",
        "DECREASES_RISK": "Consistent multi-cycle forecast trajectory over the past 24 hours.",
    },
    "ensemble_spread_delta_24h": {
        "INCREASES_RISK": "Rapidly widening ensemble spread over 24 hours signals accelerating loss of predictability.",
        "DECREASES_RISK": "Stable or contracting ensemble spread indicates steadying forecast confidence.",
    },
    "lead_hours": {
        "INCREASES_RISK": "Extended forecast horizon increases vulnerability to non-linear atmospheric error growth.",
        "DECREASES_RISK": "Short forecast horizon benefits from recent data assimilation and low error growth.",
    },
    "valid_hour": {
        "INCREASES_RISK": "Verification time coincides with diurnal convective or nocturnal inversion transition windows.",
        "DECREASES_RISK": "Verification time occurs during stable diurnal atmospheric regimes.",
    },
    "latitude": {
        "INCREASES_RISK": "Geographic coordinates correspond to complex regional topography or active monsoonal convergence.",
        "DECREASES_RISK": "Geographic coordinates correspond to well-modelled synoptic plains.",
    },
}


class ForecastRiskAttributionEngine:
    """
    Computes deterministic feature contributions and generates structured risk explanations.
    """

    def __init__(self, model: Optional[Any] = None, feature_names: Optional[List[str]] = None):
        self.model = model
        self.feature_names_ = feature_names or []

    def fit_model_context(self, model: Any, feature_names: List[str]) -> "ForecastRiskAttributionEngine":
        """Store model reference and feature schema."""
        self.model = model
        self.feature_names_ = feature_names
        return self

    def attribute(
        self,
        features: Union[pd.Series, pd.DataFrame, Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Compute ranked feature attributions for a single forecast issue instance.
        """
        if isinstance(features, pd.DataFrame):
            row_dict = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            row_dict = features.to_dict()
        else:
            row_dict = dict(features)

        # Validate feature contract
        violations = validate_feature_contract(list(row_dict.keys()))
        if violations:
            raise ValueError(f"Attribution cannot be run on target/verification columns: {violations}")

        feat_names = self.feature_names_ or [k for k in row_dict.keys() if isinstance(row_dict[k], (int, float))]

        contributions = []

        # If regularized logistic classifier is provided with coefficients
        if self.model is not None and hasattr(self.model, "coef_") and hasattr(self.model, "means_") and hasattr(self.model, "stds_"):
            coefs = self.model.coef_
            means = self.model.means_
            stds = self.model.stds_

            for j, f in enumerate(feat_names):
                val = float(row_dict.get(f, 0.0)) if not pd.isna(row_dict.get(f, np.nan)) else 0.0
                if j < len(coefs) and j < len(means) and j < len(stds):
                    z_val = (val - means[j]) / stds[j]
                    contrib = float(coefs[j] * z_val)
                else:
                    contrib = 0.0

                contributions.append({
                    "feature": f,
                    "raw_value": round(val, 4),
                    "contribution": contrib,
                })
        else:
            # Domain-heuristic fallback based on known physical sensitivities
            for f in feat_names:
                val = float(row_dict.get(f, 0.0)) if not pd.isna(row_dict.get(f, np.nan)) else 0.0
                if "std" in f or "range" in f or "iqr" in f:
                    contrib = val * 0.4
                elif "delta" in f:
                    contrib = abs(val) * 0.3
                elif "lead" in f:
                    contrib = (val / 72.0) * 0.2
                else:
                    contrib = 0.05

                contributions.append({
                    "feature": f,
                    "raw_value": round(val, 4),
                    "contribution": contrib,
                })

        # Calculate normalized importance
        total_abs = sum(abs(c["contribution"]) for c in contributions) or 1.0

        for c in contributions:
            contrib = c["contribution"]
            c["magnitude"] = round(float(abs(contrib)), 4)
            c["normalized_importance"] = round(float(abs(contrib) / total_abs), 4)

            if contrib > 0.05:
                c["direction"] = "INCREASES_RISK"
            elif contrib < -0.05:
                c["direction"] = "DECREASES_RISK"
            else:
                c["direction"] = "NEUTRAL"

            # Domain explanation
            feat_key = next((k for k in METEOROLOGICAL_EXPLANATION_TEMPLATES if k in c["feature"]), None)
            if feat_key and c["direction"] in METEOROLOGICAL_EXPLANATION_TEMPLATES[feat_key]:
                c["explanation"] = METEOROLOGICAL_EXPLANATION_TEMPLATES[feat_key][c["direction"]]
            else:
                if c["direction"] == "INCREASES_RISK":
                    c["explanation"] = f"Feature '{c['feature']}' value ({c['raw_value']}) is associated with elevated bust probability."
                elif c["direction"] == "DECREASES_RISK":
                    c["explanation"] = f"Feature '{c['feature']}' value ({c['raw_value']}) provides stabilizing forecast evidence."
                else:
                    c["explanation"] = f"Feature '{c['feature']}' has negligible marginal impact on forecast risk."

        # Sort by highest magnitude
        contributions.sort(key=lambda c: c["magnitude"], reverse=True)
        return contributions[:top_k]

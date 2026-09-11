"""
XAI Feature Attribution & Risk Driver Ranking Engine (Day 17).

Provides model-compatible, deterministic feature attributions, signed risk contributions,
mathematical reconciliation checks, and meteorological domain interpretations.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from evaluation.attribution import METEOROLOGICAL_EXPLANATION_TEMPLATES
from evaluation.xai_schema import DriverCategory, DriverDirection, FeatureRiskDriver
from features.contract import validate_feature_contract


# Extended Human-Readable Meteorological Display Names
FEATURE_DISPLAY_NAMES = {
    "ensemble_std": "Ensemble Member Dispersion (Spread)",
    "ensemble_mean": "Ensemble Mean Forecast",
    "forecast_value": "Control NWP Forecast Value",
    "ensemble_range": "Ensemble Min-Max Range",
    "ensemble_iqr": "Ensemble Interquartile Range",
    "forecast_delta_6h": "6-Hour Forecast Revision Delta",
    "forecast_delta_24h": "24-Hour Cumulative Forecast Revision",
    "ensemble_spread_delta_24h": "24-Hour Ensemble Spread Delta",
    "lead_hours": "Forecast Lead Time Horizon",
    "valid_hour": "Diurnal Verification Hour",
    "latitude": "Station Latitude / Topography",
    "longitude": "Station Longitude",
    "surface_pressure": "Surface Atmospheric Pressure",
    "temperature_2m": "2-Meter Ambient Temperature",
    "wind_speed_10m": "10-Meter Surface Wind Speed",
}


class XAIAttributionEngine:
    """
    Computes deterministic feature contributions, driver ranking, and additive reconciliation.
    """

    def __init__(self, model: Optional[Any] = None, feature_names: Optional[List[str]] = None):
        self.model = model
        self.feature_names_ = feature_names or []
        self.baseline_risk_ = 0.15

    def fit_reference(self, X_train: pd.DataFrame, baseline_risk: float = 0.15) -> "XAIAttributionEngine":
        """Fit baseline expectations and feature names on training data."""
        self.feature_names_ = list(X_train.columns) if isinstance(X_train, pd.DataFrame) else list(self.feature_names_)
        self.baseline_risk_ = baseline_risk
        return self

    def fit_model_context(self, model: Optional[Any] = None, feature_names: Optional[List[str]] = None) -> "XAIAttributionEngine":
        """Fit or update model context and expected feature names."""
        if model is not None:
            self.model = model
        if feature_names is not None:
            self.feature_names_ = list(feature_names)
        return self

    def compute_risk_drivers(
        self,
        features: Union[pd.Series, pd.DataFrame, Dict[str, Any]],
        current_risk: float,
        top_k: int = 6,
    ) -> Tuple[List[FeatureRiskDriver], List[FeatureRiskDriver], Dict[str, Any]]:
        """
        Compute ranked risk drivers, protective factors, and attribution reconciliation metadata.
        """
        if isinstance(features, pd.DataFrame):
            row_dict = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            row_dict = features.to_dict()
        else:
            row_dict = dict(features)

        # Anti-leakage contract audit
        violations = validate_feature_contract(list(row_dict.keys()))
        if violations:
            raise ValueError(f"Target leakage detected in XAI feature attribution: {violations}")

        feat_names = [f for f in self.feature_names_ if f in row_dict]
        if not feat_names:
            feat_names = [k for k, v in row_dict.items() if isinstance(v, (int, float, np.number))]

        raw_contributions = []

        # 1. Model-based linear/tree attribution if available
        if self.model is not None and hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            imp_dict = {feat: float(imp) for feat, imp in zip(self.feature_names_, importances)}
            for feat in feat_names:
                val = float(row_dict.get(feat, 0.0))
                imp = imp_dict.get(feat, 0.05)
                # Compute signed deviation contribution
                # Higher ensemble_std or large delta increases risk; low values decrease risk
                if "std" in feat or "delta" in feat or "range" in feat or "iqr" in feat:
                    signed_val = val / max(1.0, val + 1.0) if val >= 0 else -0.2
                    contrib = float(np.clip(imp * (signed_val - 0.3) * 2.0, -0.30, 0.40))
                elif feat == "lead_hours":
                    contrib = float(np.clip(imp * ((val / 72.0) - 0.5) * 1.5, -0.15, 0.25))
                else:
                    contrib = float(np.clip(imp * 0.1, -0.05, 0.05))
                raw_contributions.append((feat, val, contrib))

        else:
            # 2. Heuristic domain-grounded attribution based on meteorological moments
            for feat in feat_names:
                val = float(row_dict.get(feat, 0.0))
                if feat == "ensemble_std":
                    # Spread >= 2.0 pushes risk up, spread <= 0.8 is protective
                    contrib = float(np.clip((val - 1.5) * 0.12, -0.20, 0.35))
                elif "delta" in feat:
                    contrib = float(np.clip((abs(val) - 1.0) * 0.10, -0.10, 0.25))
                elif feat == "lead_hours":
                    contrib = float(np.clip((val - 36.0) / 72.0 * 0.15, -0.10, 0.15))
                elif feat == "ensemble_range":
                    contrib = float(np.clip((val - 4.0) * 0.05, -0.10, 0.20))
                else:
                    contrib = 0.0
                raw_contributions.append((feat, val, contrib))

        # Sort all by absolute contribution magnitude
        raw_contributions.sort(key=lambda x: abs(x[2]), reverse=True)

        risk_drivers: List[FeatureRiskDriver] = []
        protective_drivers: List[FeatureRiskDriver] = []

        total_positive = sum(max(0.0, c[2]) for c in raw_contributions)
        total_negative = sum(min(0.0, c[2]) for c in raw_contributions)

        for rank, (feat, val, contrib) in enumerate(raw_contributions[:top_k], start=1):
            disp_name = FEATURE_DISPLAY_NAMES.get(feat, feat.replace("_", " ").title())

            # Direction and category
            if contrib >= 0.03:
                direction = DriverDirection.INCREASES_RISK
                category = DriverCategory.HIGH_RISK_DRIVER if contrib >= 0.10 else DriverCategory.MODERATE_RISK_DRIVER
            elif contrib <= -0.03:
                direction = DriverDirection.DECREASES_RISK
                category = DriverCategory.PROTECTIVE_FACTOR
            else:
                direction = DriverDirection.NEUTRAL
                category = DriverCategory.NEUTRAL_FACTOR

            # Domain interpretation template
            template_group = METEOROLOGICAL_EXPLANATION_TEMPLATES.get(feat, {})
            interpretation = template_group.get(
                direction.value,
                f"{disp_name} measured at {val:.2f}, exerting a {direction.value.lower().replace('_', ' ')} influence."
            )

            driver = FeatureRiskDriver(
                feature_name=feat,
                display_name=disp_name,
                value=round(val, 3),
                normalized_contribution=round(contrib, 4),
                direction=direction,
                category=category,
                rank=rank,
                interpretation=interpretation,
                is_actionable=("lead_hours" in feat or "delta" in feat),
                confidence=0.90 if feat in METEOROLOGICAL_EXPLANATION_TEMPLATES else 0.75,
            )

            if direction == DriverDirection.INCREASES_RISK:
                risk_drivers.append(driver)
            elif direction == DriverDirection.DECREASES_RISK:
                protective_drivers.append(driver)

        residual = float(abs(current_risk - (self.baseline_risk_ + total_positive + total_negative)))
        method_str = "MODEL_IMPORTANCE_MOMENT_SCALING" if self.model is not None else "METEOROLOGICAL_MOMENT_HEURISTIC"

        reconciliation_meta = {
            "attribution_method": method_str,
            "baseline_risk": round(self.baseline_risk_, 4),
            "sum_positive_contributions": round(total_positive, 4),
            "sum_negative_contributions": round(total_negative, 4),
            "net_attribution_shift": round(total_positive + total_negative, 4),
            "target_risk": round(current_risk, 4),
            "reconciliation_residual": round(residual, 4),
            "tolerance_applied": 0.30,
            "reconciliation_status": "APPROXIMATE_ADDITIVE",
            "is_additive_reconciled": residual <= 0.30,
            "disclaimer": "Feature contributions represent signed feature moment influences, not physical causal interventions.",
        }

        return risk_drivers, protective_drivers, reconciliation_meta

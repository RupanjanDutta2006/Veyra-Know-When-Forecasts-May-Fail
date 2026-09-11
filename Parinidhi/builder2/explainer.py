"""
Deterministic Physical Feature Attribution & Explainer Engine.

Identifies and ranks the primary physical drivers of forecast bust risk
(dispersion, inter-cycle revisions, lead degradation) without generating
uncalibrated or hallucinated explanations.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from builder2.schemas import ContributingFactor, ExplanationItem


class ForecastBustExplainer:
    """Extracts deterministic physical explanations for forecast bust risk."""

    @staticmethod
    def explain_row(feature_row: Dict[str, Any], bust_probability: float, threshold: float = 0.280) -> ExplanationItem:
        """
        Produce a structured physical explanation for a single forecast step.

        Args:
            feature_row: Dict containing the 26 canonical feature values.
            bust_probability: Calibrated bust probability float.
            threshold: Decision threshold for active bust alert.

        Returns:
            ExplanationItem dataclass.
        """
        factors: List[ContributingFactor] = []

        # 1. Inspect Inter-Cycle 24h Revision Drift
        f_delta_24h = feature_row.get("forecast_delta_24h")
        if f_delta_24h is not None and not (isinstance(f_delta_24h, float) and np.isnan(f_delta_24h)):
            abs_delta = abs(float(f_delta_24h))
            if abs_delta >= 2.0:
                factors.append(ContributingFactor(factor="forecast_delta_24h", value=float(f_delta_24h), signal="HIGH_REVISION_DRIFT"))
            elif abs_delta >= 0.75:
                factors.append(ContributingFactor(factor="forecast_delta_24h", value=float(f_delta_24h), signal="MODERATE_REVISION_DRIFT"))
            else:
                factors.append(ContributingFactor(factor="forecast_delta_24h", value=float(f_delta_24h), signal="LOW_REVISION_DRIFT"))
        else:
            factors.append(ContributingFactor(factor="forecast_delta_24h", value=None, signal="NO_PRIOR_CYCLE_BASELINE"))

        # 2. Inspect Ensemble Spread & Dispersion
        ens_std = feature_row.get("ensemble_std")
        if ens_std is not None and not (isinstance(ens_std, float) and np.isnan(ens_std)):
            val_std = float(ens_std)
            if val_std >= 3.0:
                factors.append(ContributingFactor(factor="ensemble_std", value=val_std, signal="HIGH_ENSEMBLE_SPREAD"))
            elif val_std >= 1.5:
                factors.append(ContributingFactor(factor="ensemble_std", value=val_std, signal="ELEVATED_ENSEMBLE_SPREAD"))
            else:
                factors.append(ContributingFactor(factor="ensemble_std", value=val_std, signal="LOW_ENSEMBLE_SPREAD"))

        # 3. Inspect Horizon / Lead Time
        lead_hours = feature_row.get("lead_hours")
        if lead_hours is not None:
            val_lead = int(lead_hours)
            if val_lead >= 168:
                factors.append(ContributingFactor(factor="lead_hours", value=float(val_lead), signal="EXTENDED_RANGE_DEGRADATION"))
            elif val_lead >= 72:
                factors.append(ContributingFactor(factor="lead_hours", value=float(val_lead), signal="MEDIUM_RANGE_HORIZON"))
            else:
                factors.append(ContributingFactor(factor="lead_hours", value=float(val_lead), signal="SHORT_RANGE_HORIZON"))

        # 4. Inspect Spread Delta 24h
        spr_delta_24h = feature_row.get("ensemble_spread_delta_24h")
        if spr_delta_24h is not None and not (isinstance(spr_delta_24h, float) and np.isnan(spr_delta_24h)):
            val_spr_delta = float(spr_delta_24h)
            if val_spr_delta > 1.0:
                factors.append(ContributingFactor(factor="ensemble_spread_delta_24h", value=val_spr_delta, signal="SPREAD_GROWTH"))

        # Determine Primary Driver and Summary Narrative
        is_alert = bust_probability >= threshold

        if not is_alert:
            primary_driver = "stable_ensemble_agreement"
            summary = "Forecast is stable with low ensemble dispersion and consistent inter-cycle agreement."
        else:
            # Check highest contributing signal
            signals = [f.signal for f in factors]
            if "HIGH_REVISION_DRIFT" in signals:
                primary_driver = "rapid_inter_cycle_revision"
                delta_val = next((f.value for f in factors if f.factor == "forecast_delta_24h"), 0.0)
                summary = f"High risk driven by rapid 24h run-to-run forecast revision ({delta_val:+.2f} unit drift)."
            elif "HIGH_ENSEMBLE_SPREAD" in signals or "SPREAD_GROWTH" in signals:
                primary_driver = "high_ensemble_uncertainty"
                std_val = next((f.value for f in factors if f.factor == "ensemble_std"), 0.0)
                summary = f"High risk driven by strong physical ensemble dispersion (spread = {std_val:.2f})."
            elif "EXTENDED_RANGE_DEGRADATION" in signals:
                primary_driver = "extended_horizon_uncertainty"
                summary = "Risk elevated due to long lead horizon degradation and accumulated forecast uncertainty."
            else:
                primary_driver = "multi_factor_risk"
                summary = "Elevated risk driven by combination of ensemble spread and lead-time horizon."

        return ExplanationItem(
            primary_driver=primary_driver,
            driver_summary=summary,
            top_contributing_factors=factors,
        )

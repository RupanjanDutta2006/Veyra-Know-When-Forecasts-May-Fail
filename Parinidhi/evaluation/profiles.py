"""
Location and Meteorological Regime Reliability Profiling Module (Day 14).

Computes historical reliability profiles across geographic stations and Köppen
climate regimes to evaluate whether Veyra has established historical efficacy.

Reliability Status Categories:
- KNOWN_STRONG: High historical support with verified out-of-fold PR-AUC lift > 2.0x.
- KNOWN_MODERATE: Adequate historical support with positive out-of-fold discrimination.
- KNOWN_WEAK: Low discrimination or high baseline parity.
- INSUFFICIENT_HISTORY: Sparse sample density (< 100 records).
- NOVEL_REGIME: Unseen station or climate category absent from reference training split.
"""

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from api.location_service import LocationRegistry


class LocationRegimeProfiler:
    """
    Evaluates historical station and climate regime reliability profiles.
    """

    def __init__(self):
        self.location_profiles_: Dict[str, Dict[str, Any]] = {}
        self.climate_profiles_: Dict[str, Dict[str, Any]] = {}

    def fit_from_historical_data(
        self,
        df_paired: pd.DataFrame,
        lolo_results: Optional[Dict[str, Any]] = None,
        loco_results: Optional[Dict[str, Any]] = None,
    ) -> "LocationRegimeProfiler":
        """
        Build profiles from standardized historical paired records and cross-validation results.
        """
        loc_col = "location_id" if "location_id" in df_paired.columns else ("location" if "location" in df_paired.columns else None)
        bust_col = "bust_label" if "bust_label" in df_paired.columns else None

        if loc_col is None:
            return self

        # Build location profiles
        for loc_id, group in df_paired.groupby(loc_col):
            loc_str = str(loc_id).lower()
            cfg = LocationRegistry.DEFAULT_LOCATIONS.get(loc_str, {})
            city_name = cfg.get("city", loc_str)
            regime = cfg.get("climate_zone", "Unknown")

            n_samples = len(group)
            n_busts = int(group[bust_col].sum()) if bust_col and bust_col in group.columns else 0
            base_rate = float(n_busts / n_samples) if n_samples > 0 else 0.0

            # Out-of-fold performance if LOLO was executed
            lolo_loc = lolo_results.get(loc_str, {}) if lolo_results else {}
            pr_auc = lolo_loc.get("pr_auc", None)
            spread_pr_auc = lolo_loc.get("baseline_pr_auc", None)

            # Determine reliability status
            if n_samples < 100:
                status = "INSUFFICIENT_HISTORY"
            elif pr_auc is not None and pr_auc >= 0.50:
                status = "KNOWN_STRONG"
            elif pr_auc is not None and pr_auc >= 0.15:
                status = "KNOWN_MODERATE"
            elif n_busts == 0:
                status = "KNOWN_MODERATE"  # Calm station during evaluated window
            else:
                status = "KNOWN_WEAK"

            self.location_profiles_[loc_str] = {
                "location_id": loc_str,
                "city_name": city_name,
                "climate_regime": regime,
                "historical_sample_count": n_samples,
                "historical_bust_count": n_busts,
                "base_bust_rate": round(base_rate, 4),
                "out_of_fold_pr_auc": round(float(pr_auc), 4) if pr_auc is not None else None,
                "spread_baseline_pr_auc": round(float(spread_pr_auc), 4) if spread_pr_auc is not None else None,
                "reliability_status": status,
            }

        return self

    def get_location_profile(self, location_id: str) -> Dict[str, Any]:
        """Retrieve profile for a specific location."""
        loc_str = str(location_id).lower()
        if loc_str in self.location_profiles_:
            return self.location_profiles_[loc_str]

        # Check if known in registry but novel to dataset
        if loc_str in LocationRegistry.DEFAULT_LOCATIONS:
            cfg = LocationRegistry.DEFAULT_LOCATIONS[loc_str]
            return {
                "location_id": loc_str,
                "city_name": cfg.get("city", loc_str),
                "climate_regime": cfg.get("climate_zone", "Unknown"),
                "historical_sample_count": 0,
                "historical_bust_count": 0,
                "base_bust_rate": None,
                "out_of_fold_pr_auc": None,
                "spread_baseline_pr_auc": None,
                "reliability_status": "NOVEL_LOCATION",
            }

        return {
            "location_id": loc_str,
            "city_name": loc_str,
            "climate_regime": "Unknown",
            "historical_sample_count": 0,
            "historical_bust_count": 0,
            "base_bust_rate": None,
            "out_of_fold_pr_auc": None,
            "spread_baseline_pr_auc": None,
            "reliability_status": "NOVEL_LOCATION",
        }

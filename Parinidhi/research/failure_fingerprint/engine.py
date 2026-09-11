"""
Veyra Research — Track 3: Failure Fingerprint Engine
Identifies 6 distinct analytical forecast-failure mechanisms with explicit mathematical triggers,
supporting signals, confidence scoring, and scientifically grounded non-causal diagnostic framing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import numpy as np


@dataclass
class FailureFingerprintResult:
    """Diagnostic profile of detected forecast-failure mechanisms."""
    primary_fingerprint: str                    # Dominant fingerprint code (or "NO_DOMINANT_FINGERPRINT")
    fingerprint_scores: Dict[str, float]        # {fingerprint_id: score in [0.0, 1.0]}
    detected_fingerprints: List[str]            # List of fingerprints exceeding detection threshold
    dominant_drivers: List[str]                 # Top 3 feature signals driving the classification
    scientific_rationale: str                   # Honest scientific framing (e.g. "Pattern is consistent with...")
    confidence: float                           # Confidence in fingerprint diagnosis [0.0, 1.0]
    is_ood: bool                                # Flag if OOD condition detected


class FailureFingerprintEngine:
    """
    Evaluates 6 analytical failure archetypes:
      1. ENSEMBLE_DIVERGENCE: Severe intra-ensemble spread / bimodal member dispersion
      2. LONG_LEAD_DECAY: Predictability horizon limits at extended leads (>= +168h)
      3. REVISION_INSTABILITY: Run-to-run flipping / large previous-vintage drift
      4. WIND_GRADIENT_SHEAR: High-energy wind field with strong temporal change
      5. SYNOPTIC_TRANSITION: Rapid pressure/temperature gradient indicating passing frontal/convective wave
      6. OOD_CONDITION: Input feature vector in extreme tail / unobserved region of feature space
    """

    FINGERPRINT_NAMES = [
        "ENSEMBLE_DIVERGENCE",
        "LONG_LEAD_DECAY",
        "REVISION_INSTABILITY",
        "WIND_GRADIENT_SHEAR",
        "SYNOPTIC_TRANSITION",
        "OOD_CONDITION"
    ]

    def __init__(self,
                 spread_threshold_z: float = 1.75,
                 revision_threshold_z: float = 1.80,
                 ood_mahalanobis_thresh: float = 3.5,
                 lead_decay_start_hour: int = 168):
        self.spread_threshold_z = spread_threshold_z
        self.revision_threshold_z = revision_threshold_z
        self.ood_thresh = ood_mahalanobis_thresh
        self.lead_decay_start = lead_decay_start_hour

    def diagnose(self, features: Dict[str, Any]) -> FailureFingerprintResult:
        """
        Diagnoses failure fingerprints for a given forecast instance.

        Expected keys in features:
          - 'lead_hours': int
          - 'variable': str ('t2m', 'sp', 'ws10')
          - 'fcst_ens_std': float
          - 'mclimate_spread_ratio': float (std / baseline_mclimate_std)
          - 'vintage_drift_abs': float (|fcst(t0) - prev_fcst(t0-24h)|)
          - 'dispersion_growth_rate': float
          - 'wind_speed_mean': float (for ws10)
          - 'pressure_gradient_24h': float
          - 'mahalanobis_dist': float (or OOD metric)
        """
        lead = int(features.get("lead_hours", 24))
        var = str(features.get("variable", "t2m")).lower()
        ens_std = float(features.get("fcst_ens_std", np.nan))
        mclimate_ratio = float(features.get("mclimate_spread_ratio", 1.0))
        vdrift = float(features.get("vintage_drift_abs", np.nan))
        growth = float(features.get("dispersion_growth_rate", np.nan))
        ws = float(features.get("wind_speed_mean", np.nan))
        p_grad = float(features.get("pressure_gradient_24h", np.nan))
        ood_dist = float(features.get("mahalanobis_dist", 0.0))

        scores: Dict[str, float] = {}
        driver_contributions: Dict[str, float] = {}

        # 1. ENSEMBLE_DIVERGENCE
        # Score driven by high mclimate_ratio and high dispersion growth
        if not np.isnan(mclimate_ratio):
            div_score = min(1.0, max(0.0, (mclimate_ratio - 1.0) / max(self.spread_threshold_z - 1.0, 0.5)))
            if not np.isnan(growth) and growth > 0:
                div_score = min(1.0, div_score + 0.15)
            scores["ENSEMBLE_DIVERGENCE"] = round(div_score, 3)
            driver_contributions["Elevated Ensemble Spread"] = div_score
        else:
            scores["ENSEMBLE_DIVERGENCE"] = 0.0

        # 2. LONG_LEAD_DECAY
        # Score driven by lead >= 168h and natural error accumulation
        if lead >= self.lead_decay_start:
            decay_score = min(1.0, max(0.0, (lead - 144) / 96.0))
            scores["LONG_LEAD_DECAY"] = round(decay_score, 3)
            driver_contributions["Extended Forecast Horizon"] = decay_score
        else:
            scores["LONG_LEAD_DECAY"] = 0.0

        # 3. REVISION_INSTABILITY
        # Score driven by large vintage drift between consecutive cycles
        if not np.isnan(vdrift) and vdrift > 0:
            # Normalized score based on variable-specific scale
            scale = 2.0 if var == "t2m" else (200.0 if var == "sp" else 2.5)
            rev_score = min(1.0, max(0.0, vdrift / (scale * self.revision_threshold_z)))
            scores["REVISION_INSTABILITY"] = round(rev_score, 3)
            driver_contributions["Cycle-to-Cycle Forecast Flipping"] = rev_score
        else:
            scores["REVISION_INSTABILITY"] = 0.0

        # 4. WIND_GRADIENT_SHEAR
        if var == "ws10" or not np.isnan(ws):
            ws_val = ws if not np.isnan(ws) else 0.0
            shear_score = min(1.0, max(0.0, (ws_val - 8.0) / 12.0))
            scores["WIND_GRADIENT_SHEAR"] = round(shear_score, 3)
            if shear_score > 0.3:
                driver_contributions["Strong Surface Wind Energy"] = shear_score
        else:
            scores["WIND_GRADIENT_SHEAR"] = 0.0

        # 5. SYNOPTIC_TRANSITION
        if not np.isnan(p_grad) and abs(p_grad) > 0:
            syn_score = min(1.0, max(0.0, abs(p_grad) / 400.0))
            scores["SYNOPTIC_TRANSITION"] = round(syn_score, 3)
            if syn_score > 0.3:
                driver_contributions["Rapid Surface Pressure Tendency"] = syn_score
        else:
            scores["SYNOPTIC_TRANSITION"] = 0.0

        # 6. OOD_CONDITION
        if not np.isnan(ood_dist):
            ood_score = min(1.0, max(0.0, (ood_dist - 2.0) / max(self.ood_thresh - 2.0, 1.0)))
            scores["OOD_CONDITION"] = round(ood_score, 3)
            if ood_score > 0.5:
                driver_contributions["Unusual Atmospheric State Distance"] = ood_score
        else:
            scores["OOD_CONDITION"] = 0.0

        # Detect active fingerprints (score >= 0.50)
        detected = [fp for fp, s in scores.items() if s >= 0.50]
        
        # Determine primary
        max_fp = max(scores.keys(), key=lambda k: scores[k])
        max_score = scores[max_fp]
        
        primary = max_fp if max_score >= 0.45 else "NO_DOMINANT_FINGERPRINT"
        conf = max(0.5, min(0.95, max_score)) if primary != "NO_DOMINANT_FINGERPRINT" else 0.50
        is_ood = scores.get("OOD_CONDITION", 0.0) >= 0.70

        # Top drivers
        sorted_drivers = sorted(driver_contributions.keys(), key=lambda k: driver_contributions[k], reverse=True)[:3]
        if not sorted_drivers:
            sorted_drivers = ["Baseline State Variance"]

        # Scientific narrative framing
        if primary == "ENSEMBLE_DIVERGENCE":
            rationale = "Elevated intra-ensemble dispersion is consistent with sensitive dynamical divergence among forecast trajectories."
        elif primary == "REVISION_INSTABILITY":
            rationale = "Large previous-vintage displacement is associated with high synoptic uncertainty and model trajectory adjustments."
        elif primary == "LONG_LEAD_DECAY":
            rationale = "Lead time exceeds predictable deterministic range; error distribution aligns with climatological dispersion limits."
        elif primary == "WIND_GRADIENT_SHEAR":
            rationale = "Strong surface wind fields and gradient momentum transfer are associated with high localized gust variability."
        elif primary == "SYNOPTIC_TRANSITION":
            rationale = "Rapid surface pressure tendency is consistent with an active frontal passage or wave transition."
        elif primary == "OOD_CONDITION":
            rationale = "Feature representation falls into an atypical tail of the historical training distribution."
        else:
            rationale = "No singular dominant failure mechanism detected; forecast signals indicate nominal operational dispersion."

        return FailureFingerprintResult(
            primary_fingerprint=primary,
            fingerprint_scores=scores,
            detected_fingerprints=detected,
            dominant_drivers=sorted_drivers,
            scientific_rationale=rationale,
            confidence=round(conf, 3),
            is_ood=is_ood
        )

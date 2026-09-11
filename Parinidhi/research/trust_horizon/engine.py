"""
Veyra Research — Track 2: Operational Trust Horizon Engine
Evaluates lead-conditioned forecast reliability, determines instance-dependent Trust Horizons (H_rel, H_skill_clim, H_incremental),
and quantifies uncertainty around reliability degradation.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
import numpy as np


@dataclass
class TrustHorizonReport:
    """Structured result of Operational Trust Horizon evaluation."""
    h_rel: Optional[int]                  # Reliability Horizon (first lead where P(bust) > P_crit)
    h_skill_clim: Optional[int]           # Horizon where BSS <= 0 vs climatology
    h_incremental: Optional[int]          # Horizon where incremental skill over E1b vanishes
    degradation_onset_lead: Optional[int] # First lead exhibiting rapid reliability decay (dP/dL > threshold)
    risk_tolerance_threshold: float       # P_crit used for H_rel (e.g., 0.35)
    reliability_trajectory: Dict[int, float] # {lead_hours: calibrated_prob}
    horizon_uncertainty_bounds: Tuple[Optional[int], Optional[int]] # (lower_lead, upper_lead)
    is_fully_trustworthy_to_day10: bool   # True if H_rel > 240h
    confidence_score: float               # [0.0, 1.0] confidence in horizon estimation
    dominant_degradation_mechanism: str   # Brief diagnostic reason for degradation


class TrustHorizonEngine:
    """
    Computes the Operational Trust Horizon for a forecast sequence.
    Non-dogmatic, instance-dependent horizon estimation: evaluates empirical risk trajectories
    against configurable risk tolerances and climatological baselines.
    """

    DEFAULT_RISK_TOLERANCE = 0.35  # P_crit: acceptable threshold of forecast failure probability
    DEFAULT_DECAY_RATE_THRESH = 0.005 # dP/dL threshold per hour indicating rapid decay

    def __init__(self,
                 risk_tolerance: float = DEFAULT_RISK_TOLERANCE,
                 decay_rate_threshold: float = DEFAULT_DECAY_RATE_THRESH):
        self.risk_tolerance = float(risk_tolerance)
        self.decay_rate_threshold = float(decay_rate_threshold)

    def evaluate_horizon(self,
                         lead_probs: Dict[int, float],
                         climatological_probs: Optional[Dict[int, float]] = None,
                         spread_uncertainty: Optional[Dict[int, float]] = None) -> TrustHorizonReport:
        """
        Evaluates Trust Horizons across leads (typically [24, 48, 72, ..., 240]).

        Args:
            lead_probs: Mapping {lead_hours: calibrated_bust_probability}
            climatological_probs: Optional baseline climatology probabilities per lead
            spread_uncertainty: Optional ensemble dispersion / prediction variance per lead
        """
        sorted_leads = sorted([int(l) for l in lead_probs.keys()])
        if not sorted_leads:
            return TrustHorizonReport(
                h_rel=None, h_skill_clim=None, h_incremental=None,
                degradation_onset_lead=None, risk_tolerance_threshold=self.risk_tolerance,
                reliability_trajectory={}, horizon_uncertainty_bounds=(None, None),
                is_fully_trustworthy_to_day10=False, confidence_score=0.0,
                dominant_degradation_mechanism="NO_LEADS_PROVIDED"
            )

        trajectory = {l: float(lead_probs[l]) for l in sorted_leads}

        # 1. Compute H_rel (First lead where P(bust) exceeds risk_tolerance)
        h_rel = None
        for l in sorted_leads:
            p = trajectory[l]
            if not np.isnan(p) and p >= self.risk_tolerance:
                h_rel = l
                break

        # 2. Compute Degradation Onset (First lead where derivative dP/dL exceeds decay_rate_threshold)
        degradation_onset = None
        for i in range(1, len(sorted_leads)):
            l_prev, l_curr = sorted_leads[i - 1], sorted_leads[i]
            p_prev, p_curr = trajectory[l_prev], trajectory[l_curr]
            if not np.isnan(p_prev) and not np.isnan(p_curr) and (l_curr > l_prev):
                slope = (p_curr - p_prev) / (l_curr - l_prev)
                if slope >= self.decay_rate_threshold:
                    degradation_onset = l_prev
                    break

        # 3. Compute H_skill_clim (Horizon where forecast probability is worse than or equal to climatology)
        h_skill_clim = None
        if climatological_probs:
            for l in sorted_leads:
                p_fcst = trajectory[l]
                p_clim = climatological_probs.get(l, np.nan)
                if not np.isnan(p_fcst) and not np.isnan(p_clim):
                    # If forecast probability of bust exceeds climatological bust frequency by large margin
                    if p_fcst > (p_clim + 0.15):
                        h_skill_clim = l
                        break

        # 4. Uncertainty Bounds around H_rel
        lower_bound, upper_bound = None, None
        if h_rel is not None:
            # If spread uncertainty is provided, use +/- uncertainty envelope
            # Otherwise use adjacent lead intervals
            idx = sorted_leads.index(h_rel)
            lower_bound = sorted_leads[max(0, idx - 1)]
            upper_bound = sorted_leads[min(len(sorted_leads) - 1, idx + 1)]
        elif all(not np.isnan(trajectory[l]) and trajectory[l] < self.risk_tolerance for l in sorted_leads):
            # Trustworthy past +240h
            lower_bound, upper_bound = 240, 240

        is_trustworthy_day10 = (h_rel is None) and all(
            not np.isnan(trajectory[l]) and trajectory[l] < self.risk_tolerance for l in sorted_leads
        )

        # 5. Diagnostic Mechanism
        if is_trustworthy_day10:
            mechanism = "STABLE_MEDIUM_RANGE_RELIABILITY"
            conf = 0.90
        elif h_rel is not None and h_rel <= 72:
            mechanism = "EARLY_SHORT_RANGE_INSTABILITY"
            conf = 0.85
        elif h_rel is not None and h_rel <= 144:
            mechanism = "MID_RANGE_SYNOPTIC_DECAY"
            conf = 0.80
        elif h_rel is not None:
            mechanism = "EXTENDED_RANGE_PREDICTABILITY_LIMIT"
            conf = 0.75
        else:
            mechanism = "UNCERTAIN_TRAJECTORY_WITH_MISSINGNESS"
            conf = 0.40

        return TrustHorizonReport(
            h_rel=h_rel,
            h_skill_clim=h_skill_clim,
            h_incremental=None, # Set when E1b baseline comparator is evaluated
            degradation_onset_lead=degradation_onset,
            risk_tolerance_threshold=self.risk_tolerance,
            reliability_trajectory=trajectory,
            horizon_uncertainty_bounds=(lower_bound, upper_bound),
            is_fully_trustworthy_to_day10=is_trustworthy_day10,
            confidence_score=conf,
            dominant_degradation_mechanism=mechanism
        )

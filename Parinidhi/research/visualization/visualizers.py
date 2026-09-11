"""
Veyra Research — Track 10: Research Visualization Specifications & Generators
Generates structured JSON chart specifications and matplotlib/static figures for:
  1. Bust Probability vs Lead
  2. Operational Trust Horizon Timeline
  3. Ensemble Spread vs Lead (Spread-Skill Trajectory)
  4. Forecast Revision Trajectory (Run-to-Run Flipping)
  5. Reliability Diagrams (ECE Curves)
  6. Conditional Error Distribution (Quantile Mesh Fan Chart)
  7. Failure Fingerprint Diagnostic Radar
  8. Decision Mode Timeline
"""
from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any
import numpy as np


class ResearchVisualizer:
    """
    Generates structured visualization payloads and specs for Veyra Phase 5B.2 research dashboards.
    """

    @staticmethod
    def build_prob_vs_lead_spec(leads: List[int],
                                probs: List[float],
                                lower_bounds: Optional[List[float]] = None,
                                upper_bounds: Optional[List[float]] = None,
                                risk_threshold: float = 0.35) -> Dict[str, Any]:
        """Chart 1: Bust Probability vs Lead Hours with Uncertainty Envelope."""
        return {
            "chart_type": "line_with_band",
            "title": "Calibrated Bust Probability P(|e| >= tau) vs Forecast Lead",
            "x_axis": {"label": "Forecast Lead (Hours)", "values": leads},
            "y_axis": {"label": "Calibrated Bust Probability", "min": 0.0, "max": 1.0},
            "series": [
                {"name": "Calibrated P(Bust)", "values": probs, "color": "#E53E3E"},
                {"name": "Risk Threshold (P_crit)", "values": [risk_threshold] * len(leads), "color": "#718096", "style": "dashed"}
            ],
            "uncertainty_band": {
                "lower": lower_bounds or probs,
                "upper": upper_bounds or probs,
                "color": "rgba(229, 62, 62, 0.2)"
            }
        }

    @staticmethod
    def build_trust_horizon_timeline_spec(leads: List[int],
                                          probs: List[float],
                                          h_rel: Optional[int],
                                          h_skill_clim: Optional[int]) -> Dict[str, Any]:
        """Chart 2: Trust Horizon Timeline."""
        markers = []
        if h_rel is not None:
            markers.append({"lead": h_rel, "label": f"H_rel: +{h_rel}h (Reliability Limit)", "color": "#DD6B20"})
        if h_skill_clim is not None:
            markers.append({"lead": h_skill_clim, "label": f"H_skill: +{h_skill_clim}h (Climatology Limit)", "color": "#E53E3E"})

        return {
            "chart_type": "horizon_timeline",
            "title": "Operational Trust Horizon Trajectory",
            "leads": leads,
            "reliability_curve": probs,
            "markers": markers,
            "trust_zone": {"start": 24, "end": h_rel if h_rel else 240, "color": "rgba(72, 187, 120, 0.15)"}
        }

    @staticmethod
    def build_spread_vs_lead_spec(leads: List[int],
                                  ens_spreads: List[float],
                                  mclimate_spreads: List[float],
                                  var_name: str = "T2M (K)") -> Dict[str, Any]:
        """Chart 3: Ensemble Spread vs M-Climate Reference."""
        return {
            "chart_type": "multi_line",
            "title": f"Ensemble Dispersion vs M-Climate Reference [{var_name}]",
            "x_axis": {"label": "Forecast Lead (Hours)", "values": leads},
            "y_axis": {"label": f"Standard Deviation [{var_name}]"},
            "series": [
                {"name": "Current Forecast Ensemble Spread", "values": ens_spreads, "color": "#3182CE"},
                {"name": "M-Climate 10-Year Climatological Spread", "values": mclimate_spreads, "color": "#718096", "style": "dashed"}
            ]
        }

    @staticmethod
    def build_revision_trajectory_spec(leads: List[int],
                                       current_fcst: List[float],
                                       prev_vintage_fcst: List[float],
                                       var_name: str = "T2M (K)") -> Dict[str, Any]:
        """Chart 4: Run-to-Run Forecast Revision Trajectory."""
        deltas = [c - p if (not np.isnan(c) and not np.isnan(p)) else np.nan for c, p in zip(current_fcst, prev_vintage_fcst)]
        return {
            "chart_type": "revision_divergence",
            "title": f"Run-to-Run Forecast Revision Displacements [{var_name}]",
            "x_axis": {"label": "Target Lead Hours", "values": leads},
            "series": [
                {"name": "Current Issue (t0)", "values": current_fcst, "color": "#319795"},
                {"name": "Previous Vintage (t0 - 24h)", "values": prev_vintage_fcst, "color": "#D69E2E"},
                {"name": "Revision Delta |t0 - (t0-24h)|", "values": deltas, "type": "bar", "color": "#E53E3E"}
            ]
        }

    @staticmethod
    def build_reliability_diagram_spec(bin_centers: List[float],
                                       bin_accuracies: List[float],
                                       bin_counts: List[int],
                                       ece_score: float) -> Dict[str, Any]:
        """Chart 5: ECE Reliability Diagram."""
        return {
            "chart_type": "reliability_diagram",
            "title": f"Reliability Calibration Curve (ECE: {ece_score:.4f})",
            "x_axis": {"label": "Forecast Probability Bin", "min": 0.0, "max": 1.0},
            "y_axis": {"label": "Observed Empirical Bust Frequency", "min": 0.0, "max": 1.0},
            "perfect_calibration": [0.0, 1.0],
            "points": [{"conf": c, "acc": a, "count": n} for c, a, n in zip(bin_centers, bin_accuracies, bin_counts)]
        }

    @staticmethod
    def build_conditional_fan_spec(leads: List[int],
                                   mean_traj: List[float],
                                   q05: List[float],
                                   q25: List[float],
                                   q75: List[float],
                                   q95: List[float],
                                   var_name: str = "T2M (K)") -> Dict[str, Any]:
        """Chart 6: Conditional Error Distribution Quantile Fan Chart."""
        return {
            "chart_type": "fan_chart",
            "title": f"Conditional Forecast Error Distribution Mesh [{var_name}]",
            "x_axis": {"label": "Lead (Hours)", "values": leads},
            "y_axis": {"label": f"Forecast Error [{var_name}]"},
            "median": mean_traj,
            "bands": [
                {"level": "50% (q25-q75)", "lower": q25, "upper": q75, "color": "rgba(49, 130, 206, 0.4)"},
                {"level": "90% (q05-q95)", "lower": q05, "upper": q95, "color": "rgba(49, 130, 206, 0.15)"}
            ]
        }

    @staticmethod
    def build_failure_fingerprint_radar_spec(scores: Dict[str, float]) -> Dict[str, Any]:
        """Chart 7: Failure Fingerprint Diagnostic Radar."""
        return {
            "chart_type": "radar",
            "title": "Failure Archetype Diagnostic Profile",
            "categories": list(scores.keys()),
            "values": [scores[k] for k in scores.keys()],
            "threshold": 0.50
        }

    @staticmethod
    def build_decision_mode_timeline_spec(leads: List[int], modes: List[str]) -> Dict[str, Any]:
        """Chart 8: Decision Mode Timeline across leads."""
        return {
            "chart_type": "status_strip",
            "title": "Operational Decision Mode Sequence across 10-Day Range",
            "timeline": [{"lead": l, "mode": m} for l, m in zip(leads, modes)]
        }

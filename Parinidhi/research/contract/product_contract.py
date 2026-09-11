"""
Veyra Research — Track 9: Research-to-Product Contract & Compatibility Adapter
Defines the rich Phase 5B.2 research response contract and provides a non-invasive compatibility adapter
for production V2 consumers.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import numpy as np


@dataclass
class ResearchProductResponse:
    """Rich research-grade prediction contract for Phase 5B.2."""
    bust_probability: float               # Calibrated P(|e| >= tau | X, lead) in [0.0, 1.0]
    risk_level: str                       # LOW | MODERATE | HIGH | CRITICAL
    confidence_index: float               # Operational confidence score in [0.0, 1.0]
    uncertainty_pct: float                # Epistemic + aleatoric uncertainty % [0.0, 100.0]
    trust_horizon: Optional[int]          # Operational Trust Horizon in hours (+24h ... >+240h)
    ood_distance: float                   # Atmospheric state Mahalanobis/isolation distance
    stability: float                      # Dynamic trajectory stability metric [0.0, 1.0]
    revision: Optional[float]             # Run-to-run displacement delta |t0 - (t0-24h)|
    structural_overconfidence: float      # Divergence between ensemble spread and empirical error dispersion
    failure_fingerprint: str              # Primary failure archetype diagnosis
    dominant_risk_drivers: List[str]      # Top 3 meteorological drivers of failure risk
    decision_mode: str                    # NORMAL | CAUTION | VERIFY | ABSTAIN
    abstain: bool                         # True if decision mode is ABSTAIN
    reason_codes: List[str]               # Machine-readable operational tags
    model_version: str = "5B.2-RESEARCH"
    data_version: str = "GEFSv12-Phase2-2000-2019"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchToProductAdapter:
    """
    Non-invasive adapter mapping rich ResearchProductResponse objects
    to legacy/current production V2 API contracts without modifying production V2 services.
    """

    @staticmethod
    def to_production_v2_payload(research_resp: ResearchProductResponse) -> Dict[str, Any]:
        """
        Maps research contract into the production V2 API schema.
        """
        # Map risk level
        prob = research_resp.bust_probability
        if np.isnan(prob) or research_resp.abstain:
            prod_risk = "UNKNOWN"
            p_val = None
        elif prob < 0.20:
            prod_risk = "LOW"
            p_val = round(prob, 4)
        elif prob < 0.45:
            prod_risk = "MODERATE"
            p_val = round(prob, 4)
        elif prob < 0.70:
            prod_risk = "HIGH"
            p_val = round(prob, 4)
        else:
            prod_risk = "CRITICAL"
            p_val = round(prob, 4)

        # Map recommendation
        if research_resp.abstain:
            rec = "ABSTAIN: Insufficient or corrupted data. Rely on manual synoptician review."
        elif research_resp.decision_mode == "VERIFY":
            rec = f"VERIFY: Elevated failure probability ({prob:.1%}). Cross-reference secondary ensemble guidance."
        elif research_resp.decision_mode == "CAUTION":
            rec = f"CAUTION: Moderate risk ({prob:.1%}). Track next-cycle revision updates."
        else:
            rec = "NOMINAL: Forecast exhibits high reliability for operational dispatch."

        return {
            "bust_probability": p_val,
            "risk_level": prod_risk,
            "confidence": round(research_resp.confidence_index, 3),
            "recommendation": rec,
            "metadata": {
                "decision_mode": research_resp.decision_mode,
                "trust_horizon_lead": research_resp.trust_horizon,
                "failure_fingerprint": research_resp.failure_fingerprint,
                "dominant_drivers": research_resp.dominant_risk_drivers,
                "ood_distance": round(research_resp.ood_distance, 2),
                "is_abstain": research_resp.abstain,
                "reason_codes": research_resp.reason_codes,
                "model_version": research_resp.model_version,
                "data_version": research_resp.data_version
            }
        }

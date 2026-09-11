"""
Risk Self-Confidence Assessment Engine (Day 14).

Distinguishes 'predicted risk probability' from 'Veyra's confidence in its estimate'.
Evaluates whether a risk score is backed by dense, calibrated historical evidence
versus extrapolated under novel, sparse, or out-of-distribution conditions.

Scientific Safeguards:
- High novelty or sparse historical support strictly lowers risk_confidence.
- Missing input features incur proportional confidence penalties.
- Outputs structured confidence reasons and support metrics.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd


class RiskConfidenceEngine:
    """
    Evaluates self-confidence in Veyra's predicted bust probability.
    """

    def __init__(self, min_dense_samples: int = 500):
        self.min_dense_samples = min_dense_samples

    def evaluate_confidence(
        self,
        risk_probability: float,
        novelty_eval: Optional[Dict[str, Any]] = None,
        retrieval_eval: Optional[Dict[str, Any]] = None,
        location_profile: Optional[Dict[str, Any]] = None,
        missing_feature_fraction: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Evaluate confidence score and confidence reasons for a forecast risk prediction.
        """
        reasons: List[str] = []
        score = 1.0

        # 1. Feature Novelty Penalty
        if novelty_eval is not None:
            nov_state = novelty_eval.get("novelty_state", "NORMAL")
            nov_score = novelty_eval.get("novelty_score", 1.0)
            if nov_state == "EXTREME":
                score -= 0.35
                reasons.append(f"Extreme feature-space novelty (z={nov_score:.2f}) indicates conditions outside training distribution.")
            elif nov_state == "HIGH":
                score -= 0.20
                reasons.append(f"High feature novelty (z={nov_score:.2f}) reflects unusual meteorological conditions.")
            elif nov_state == "ELEVATED":
                score -= 0.08
                reasons.append("Mildly elevated feature dispersion relative to training baseline.")
            else:
                reasons.append("Meteorological features lie well within familiar training distribution.")

        # 2. Historical Sample Support Penalty
        if retrieval_eval is not None:
            support_status = retrieval_eval.get("support_status", "SUFFICIENT_SUPPORT")
            ref_count = retrieval_eval.get("available_reference_count", 0)
            if support_status == "INSUFFICIENT_HISTORICAL_SUPPORT" or ref_count < 10:
                score -= 0.25
                reasons.append(f"Sparse historical analogue support ({ref_count} reference cases available).")
            else:
                sim = retrieval_eval.get("mean_similarity", 0.8)
                reasons.append(f"Identified {retrieval_eval.get('analogue_count', 0)} historical analogues with mean similarity {sim:.2f}.")

        # 3. Location Reliability Status
        if location_profile is not None:
            status = location_profile.get("reliability_status", "KNOWN_MODERATE")
            if status == "NOVEL_LOCATION":
                score -= 0.25
                reasons.append("Target station is novel to historical training records.")
            elif status == "INSUFFICIENT_HISTORY":
                score -= 0.15
                reasons.append("Limited historical verification history for this municipal station.")
            elif status == "KNOWN_STRONG":
                reasons.append("Station has established high out-of-fold generalization performance.")

        # 4. Missingness Penalty
        if missing_feature_fraction > 0.0:
            penalty = min(missing_feature_fraction * 0.8, 0.60)
            score -= penalty
            reasons.append(f"{int(missing_feature_fraction * 100)}% of input features required imputation.")

        # Clamp confidence to [0.05, 0.98]
        final_confidence = round(float(np.clip(score, 0.05, 0.98)), 4)

        if final_confidence >= 0.80:
            conf_level = "HIGH"
        elif final_confidence >= 0.60:
            conf_level = "MODERATE"
        elif final_confidence >= 0.40:
            conf_level = "LOW"
        else:
            conf_level = "VERY_LOW"

        return {
            "risk_probability": round(float(risk_probability), 4),
            "risk_confidence": final_confidence,
            "confidence_level": conf_level,
            "confidence_reasons": reasons,
        }

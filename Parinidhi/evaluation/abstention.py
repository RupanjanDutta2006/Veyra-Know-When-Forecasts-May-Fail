"""
Abstention ('I Don't Know') Decision Controller (Day 15).

Implements explicit, safety-critical abstention logic when issue-time evidence
is insufficient, corrupted, conflicting, or out-of-distribution.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from evaluation.decision_policy import RiskDecisionPolicy
from evaluation.decision_schema import DataQualityState


class AbstentionController:
    """
    Evaluates whether Veyra should abstain from issuing an automated risk classification.
    """

    def evaluate_abstention(
        self,
        raw_prob: float,
        calibrated_prob: float,
        data_quality_state: DataQualityState,
        missing_fraction: float,
        novelty_res: Dict[str, Any],
        retrieval_res: Dict[str, Any],
        location_profile: Dict[str, Any],
        conflict_score: float,
        policy: RiskDecisionPolicy,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine whether abstention is mandatory and return the primary reason.
        """
        # 1. Pathological / non-finite probability checks
        if not np.isfinite(raw_prob) or not np.isfinite(calibrated_prob):
            return True, "Pathological non-finite probability detected."
        if raw_prob < 0.0 or raw_prob > 1.0 or calibrated_prob < 0.0 or calibrated_prob > 1.0:
            return True, f"Out-of-bounds probability value (raw={raw_prob}, cal={calibrated_prob})."

        # 2. Corrupted or insufficient input data
        if data_quality_state == DataQualityState.CORRUPTED:
            return True, "Input feature data is corrupted (contains non-finite values or forbidden target columns)."
        if missing_fraction >= policy.abstention_max_missing_fraction:
            return True, f"Excessive missing features ({int(missing_fraction * 100)}% missing; threshold={int(policy.abstention_max_missing_fraction * 100)}%)."

        # 3. Extreme OOD Novelty with Sparse Historical Support
        nov_state = novelty_res.get("novelty_state", "NORMAL")
        nov_score = novelty_res.get("novelty_score", 1.0)
        analogue_count = retrieval_res.get("analogue_count", 0)
        support_status = retrieval_res.get("support_status", "SUFFICIENT_SUPPORT")

        if nov_score >= policy.abstention_max_novelty_distance:
            return True, f"Extreme feature novelty (z={nov_score:.2f}) indicates conditions far outside familiar training distribution."

        # 4. Severe Evidence Conflict under Low Confidence
        if conflict_score >= policy.abstention_max_conflict_score and (nov_state in ["HIGH", "EXTREME"] or analogue_count < 5):
            return True, f"Severe evidentiary contradiction detected (conflict score={conflict_score:.2f}) with insufficient consensus."

        # 5. Novel Location with Zero Historical Support and High Uncertainty
        loc_status = location_profile.get("reliability_status", "KNOWN_MODERATE")
        if loc_status == "NOVEL_LOCATION" and nov_state in ["HIGH", "EXTREME"]:
            return True, "Unseen geographic monitoring station exhibiting high atmospheric novelty."

        return False, None

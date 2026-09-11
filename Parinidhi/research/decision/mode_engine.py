"""
Veyra Research — Track 4: Decision Mode Engine
Determines operational dispatch status: NORMAL, CAUTION, VERIFY, ABSTAIN
downstream of calibrated bust probability, prediction uncertainty, OOD state, and data quality.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import numpy as np


class DecisionMode:
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    VERIFY = "VERIFY"
    ABSTAIN = "ABSTAIN"


@dataclass
class DecisionModeResult:
    """Output of operational decision mode evaluation."""
    mode: str                          # NORMAL | CAUTION | VERIFY | ABSTAIN
    is_abstain: bool                   # True if prediction should not be used
    primary_reason: str                # Human-interpretable rationale for the mode
    reason_codes: List[str]            # Machine-readable diagnostic tags
    recommended_action: str            # Actionable advisory for downstream operators
    calibrated_probability: float      # Calibrated bust probability used for evaluation
    confidence_index: float            # [0.0, 1.0] operational trust score


class DecisionModeEngine:
    """
    Evaluates operational risk state and assigns a responsible decision mode.
    Prioritizes epistemic honesty: emits ABSTAIN when inputs are corrupted, highly OOD,
    or missing critical features, rather than emitting a misleading prediction.
    """

    def __init__(self,
                 caution_threshold: float = 0.20,
                 verify_threshold: float = 0.50,
                 extreme_ood_threshold: float = 4.5,
                 max_allowed_missing_ratio: float = 0.25):
        self.caution_thresh = float(caution_threshold)
        self.verify_thresh = float(verify_threshold)
        self.extreme_ood_thresh = float(extreme_ood_threshold)
        self.max_missing_ratio = float(max_allowed_missing_ratio)

    def evaluate(self,
                 calibrated_prob: float,
                 lead_hours: int,
                 trust_horizon_lead: Optional[int] = None,
                 ood_score: float = 0.0,
                 data_quality_flags: Optional[List[str]] = None,
                 missing_feature_ratio: float = 0.0) -> DecisionModeResult:
        """
        Determines the operational decision mode.
        """
        reasons: List[str] = []
        flags = data_quality_flags or []

        # 1. Check for ABSTAIN triggers (Data Quality, Extreme OOD, Invalid Probability)
        if np.isnan(calibrated_prob):
            return DecisionModeResult(
                mode=DecisionMode.ABSTAIN,
                is_abstain=True,
                primary_reason="Bust probability could not be reliably calculated due to unresolvable missingness.",
                reason_codes=["MISSING_PROBABILITY", "UNRESOLVABLE_FEATURE_NAN"],
                recommended_action="Abstain from automated decision. Manually inspect raw numerical guidance.",
                calibrated_probability=np.nan,
                confidence_index=0.0
            )

        if missing_feature_ratio > self.max_missing_ratio:
            return DecisionModeResult(
                mode=DecisionMode.ABSTAIN,
                is_abstain=True,
                primary_reason=f"Feature missingness ({missing_feature_ratio:.1%}) exceeds maximum allowable tolerance ({self.max_missing_ratio:.1%}).",
                reason_codes=["EXCESSIVE_FEATURE_MISSINGNESS"],
                recommended_action="Do not use automated alert. Verify data ingestion pipelines.",
                calibrated_probability=float(calibrated_prob),
                confidence_index=0.0
            )

        if ood_score >= self.extreme_ood_thresh:
            return DecisionModeResult(
                mode=DecisionMode.ABSTAIN,
                is_abstain=True,
                primary_reason=f"Input state exhibits extreme atmospheric out-of-distribution distance ({ood_score:.2f} >= {self.extreme_ood_thresh:.2f}).",
                reason_codes=["EXTREME_OOD_STATE", "BEYOND_TRAINING_SUPPORT"],
                recommended_action="Abstain from automated model dispatch. Refer to expert human synoptician review.",
                calibrated_probability=float(calibrated_prob),
                confidence_index=0.10
            )

        if "CORRUPTED_RAW_GRIB" in flags or "UNAUTHORIZED_SOURCE" in flags:
            return DecisionModeResult(
                mode=DecisionMode.ABSTAIN,
                is_abstain=True,
                primary_reason="Severe input data corruption or security policy violation detected.",
                reason_codes=flags,
                recommended_action="Halt downstream processing and investigate data source provenance.",
                calibrated_probability=float(calibrated_prob),
                confidence_index=0.0
            )

        # 2. Check for VERIFY triggers (High Risk, Past Trust Horizon)
        p = float(calibrated_prob)
        past_trust_horizon = (trust_horizon_lead is not None and lead_hours > trust_horizon_lead)

        if p >= self.verify_thresh or past_trust_horizon:
            reasons_list = []
            if p >= self.verify_thresh:
                reasons_list.append("HIGH_BUST_PROBABILITY")
            if past_trust_horizon:
                reasons_list.append("LEAD_EXCEEDS_TRUST_HORIZON")

            return DecisionModeResult(
                mode=DecisionMode.VERIFY,
                is_abstain=False,
                primary_reason=f"Elevated failure probability ({p:.1%}) or lead (+{lead_hours}h) exceeds Trust Horizon (+{trust_horizon_lead}h).",
                reason_codes=reasons_list,
                recommended_action="Require secondary ensemble verification before committing operational resources.",
                calibrated_probability=p,
                confidence_index=max(0.20, 1.0 - p)
            )

        # 3. Check for CAUTION triggers (Moderate Risk, Approaching Horizon)
        approaching_horizon = (trust_horizon_lead is not None and lead_hours == trust_horizon_lead)
        if p >= self.caution_thresh or approaching_horizon or ood_score >= 2.5:
            reasons_list = []
            if p >= self.caution_thresh:
                reasons_list.append("MODERATE_BUST_PROBABILITY")
            if approaching_horizon:
                reasons_list.append("APPROACHING_TRUST_HORIZON")
            if ood_score >= 2.5:
                reasons_list.append("MODERATE_OOD_DISTANCE")

            return DecisionModeResult(
                mode=DecisionMode.CAUTION,
                is_abstain=False,
                primary_reason=f"Moderate failure risk ({p:.1%}); forecast remains usable under active monitoring.",
                reason_codes=reasons_list,
                recommended_action="Proceed with forecast guidance while tracking next-cycle revision updates.",
                calibrated_probability=p,
                confidence_index=round(1.0 - p, 2)
            )

        # 4. NORMAL Mode
        return DecisionModeResult(
            mode=DecisionMode.NORMAL,
            is_abstain=False,
            primary_reason=f"Nominal forecast state: low failure probability ({p:.1%}) within valid Trust Horizon.",
            reason_codes=["NOMINAL_DISPERSION", "WITHIN_TRUST_HORIZON"],
            recommended_action="Forecast is operationally trustworthy for standard planning.",
            calibrated_probability=p,
            confidence_index=round(1.0 - p, 2)
        )

"""
Forecast Risk Decision Master Engine (Day 15).

Orchestrates multi-source evidence fusion, data quality auditing, abstention gating,
cost-aware policy evaluation, and decision sensitivity analysis to produce actionable
ForecastRiskDecision payloads.
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from evaluation.abstention import AbstentionController
from evaluation.attribution import ForecastRiskAttributionEngine
from evaluation.calibration import ProbabilityCalibrator
from evaluation.data_quality import DataQualityAuditor
from evaluation.decision_policy import RiskDecisionPolicy
from evaluation.decision_schema import (
    DataQualityState,
    ForecastRiskDecision,
    OperationalDecision,
    RiskLevel,
    WarningPriority,
)
from evaluation.decision_sensitivity import DecisionSensitivityAnalyzer
from evaluation.evidence_fusion import EvidenceFusionEngine
from evaluation.explanation_engine import ForecastFailureExplainer
from evaluation.failure_patterns import HistoricalFailureRetriever
from evaluation.novelty import FeatureNoveltyDetector
from evaluation.profiles import LocationRegimeProfiler
from evaluation.risk_confidence import RiskConfidenceEngine
from evaluation.uncertainty import UncertaintyDecomposer
from features.contract import validate_feature_contract


class ForecastRiskDecisionEngine:
    """
    Master operational decision engine for Veyra forecast-bust intelligence.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        calibrator: Optional[ProbabilityCalibrator] = None,
        policy: Optional[RiskDecisionPolicy] = None,
        feature_names: Optional[List[str]] = None,
    ):
        self.model = model
        self.calibrator = calibrator
        self.policy = policy or RiskDecisionPolicy()
        self.feature_names = feature_names or []

        # Sub-engines
        self.explainer = ForecastFailureExplainer(model=model, feature_names=feature_names)
        self.data_auditor = DataQualityAuditor()
        self.evidence_fuser = EvidenceFusionEngine()
        self.abstention_ctrl = AbstentionController()
        self.sensitivity_analyzer = DecisionSensitivityAnalyzer()

        self.is_fitted_ = False

    def fit_reference_context(
        self,
        df_train: pd.DataFrame,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model: Any,
        calibrator: Optional[ProbabilityCalibrator] = None,
        lolo_results: Optional[Dict[str, Any]] = None,
    ) -> "ForecastRiskDecisionEngine":
        """
        Fit all reference sub-engines strictly on training split data.
        """
        self.model = model
        self.calibrator = calibrator
        self.feature_names = list(X_train.columns)

        # Fit explainer reference context
        self.explainer.fit_reference_context(
            df_train=df_train,
            X_train=X_train,
            y_train=y_train,
            model=model,
            lolo_results=lolo_results,
        )

        self.is_fitted_ = True
        return self

    def decide_forecast_risk(
        self,
        features: Union[pd.Series, pd.DataFrame, Dict[str, Any]],
        raw_bust_probability: Optional[float] = None,
        location_id: Optional[str] = None,
        variable: str = "temperature_2m",
        policy_override: Optional[RiskDecisionPolicy] = None,
    ) -> ForecastRiskDecision:
        """
        Produce a comprehensive ForecastRiskDecision for an issue-time forecast instance.
        """
        active_policy = policy_override or self.policy

        if isinstance(features, pd.DataFrame):
            row_dict = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            row_dict = features.to_dict()
        else:
            row_dict = dict(features)

        # 1. Data Quality Audit
        dq_state, missing_frac, dq_issues = self.data_auditor.audit_features(
            row_dict,
            expected_features=self.feature_names if self.feature_names else None,
        )

        loc_str = str(location_id or row_dict.get("location_id", row_dict.get("location", ""))).lower()
        lead_h = int(row_dict.get("lead_hours", 24)) if not pd.isna(row_dict.get("lead_hours", np.nan)) else 24

        # 2. Probability Computation & Calibration
        if raw_bust_probability is not None:
            raw_prob = float(raw_bust_probability)
        elif self.model is not None and hasattr(self.model, "predict_proba"):
            feat_names = self.feature_names or list(row_dict.keys())
            input_df = pd.DataFrame([[row_dict.get(f, np.nan) for f in feat_names]], columns=feat_names)
            probs = self.model.predict_proba(input_df)
            raw_prob = float(probs[0, 1]) if probs.ndim == 2 and probs.shape[1] > 1 else float(probs[0])
        else:
            raw_prob = 0.15

        # Early sanity check on probability
        prob_valid = np.isfinite(raw_prob) and (0.0 <= raw_prob <= 1.0)
        if not prob_valid:
            cal_prob = np.nan
        elif self.calibrator is not None and self.calibrator.is_fitted_:
            cal_prob = float(self.calibrator.predict_proba(np.array([raw_prob]))[0])
        else:
            cal_prob = raw_prob

        # 3. Check for early mandatory abstention (corrupted data, non-finite values, excessive missingness)
        early_abstain = False
        early_reason = None

        if not prob_valid:
            early_abstain = True
            early_reason = f"Out-of-bounds or non-finite probability value ({raw_prob})."
        elif dq_state == DataQualityState.CORRUPTED:
            early_abstain = True
            early_reason = f"Input data corrupted: {'; '.join(dq_issues)}"
        elif missing_frac >= active_policy.abstention_max_missing_fraction:
            early_abstain = True
            early_reason = f"Excessive missing features ({int(missing_frac * 100)}% missing; threshold={int(active_policy.abstention_max_missing_fraction * 100)}%)."

        if early_abstain:
            decision_id = f"dec_{hashlib.sha256(f'abstained_{loc_str}_{datetime.now(timezone.utc)}'.encode('utf-8')).hexdigest()[:12]}"
            return ForecastRiskDecision(
                decision_id=decision_id,
                decision=OperationalDecision.ABSTAIN,
                risk_level=RiskLevel.LOW,
                risk_score=0.0,
                raw_bust_probability=round(raw_prob, 4) if np.isfinite(raw_prob) else 0.0,
                calibrated_bust_probability=round(cal_prob, 4) if np.isfinite(cal_prob) else 0.0,
                confidence=0.05,
                confidence_level="VERY_LOW",
                uncertainty_level="EXTREME",
                novelty_level="EXTREME" if dq_state == DataQualityState.CORRUPTED else "NORMAL",
                data_quality_level=dq_state,
                lead_time_level="SHORT" if lead_h <= 24 else ("MEDIUM" if lead_h <= 48 else "EXTENDED"),
                warning_priority=WarningPriority.P4_INFORMATIONAL,
                recommended_action=active_policy.generate_recommended_action(OperationalDecision.ABSTAIN, RiskLevel.LOW, location=loc_str),
                abstention_required=True,
                abstention_reason=early_reason,
                dominant_risk_drivers=[],
                supporting_evidence=[],
                contradicting_evidence=[],
                evidence_conflict_score=0.0,
                historical_analogue_support={},
                location_reliability={},
                sensitivity_analysis={},
                provenance={
                    "engine_version": "15.0.0",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "data_quality_issues": dq_issues,
                },
            )

        # 4. Generate Diagnostic Explanations
        # Filter out non-feature keys if present
        clean_row = {k: v for k, v in row_dict.items() if k not in ["location_id", "location", "variable", "bust_label", "truth_value", "forecast_error"]}
        explanation = self.explainer.explain_forecast(
            features=clean_row,
            risk_probability=cal_prob,
            location_id=loc_str if loc_str else None,
            variable=variable,
        )

        uncertainty_res = explanation.uncertainty_components
        novelty_res = explanation.novelty
        retrieval_res = explanation.historical_analogues
        location_profile = explanation.location_profile
        drivers = explanation.primary_drivers

        # 5. Evidence Fusion & Conflict Handling
        supporting_ev, contradicting_ev, conflict_score, fused_risk_score = self.evidence_fuser.fuse_evidence(
            raw_prob=raw_prob,
            calibrated_prob=cal_prob,
            uncertainty_res=uncertainty_res,
            novelty_res=novelty_res,
            retrieval_res=retrieval_res,
            location_profile=location_profile,
            lead_hours=lead_h,
        )

        # 6. Secondary Abstention Evaluation
        abstention_req, abstention_reason = self.abstention_ctrl.evaluate_abstention(
            raw_prob=raw_prob,
            calibrated_prob=cal_prob,
            data_quality_state=dq_state,
            missing_fraction=missing_frac,
            novelty_res=novelty_res,
            retrieval_res=retrieval_res,
            location_profile=location_profile,
            conflict_score=conflict_score,
            policy=active_policy,
        )

        # 7. Policy Decision
        risk_level = active_policy.evaluate_risk_level(fused_risk_score)

        # Adjust confidence for evidence conflict
        base_confidence = explanation.risk_confidence
        adjusted_confidence = float(np.clip(base_confidence - conflict_score * 0.25, 0.05, 0.98))

        decision = active_policy.determine_decision(
            risk_level=risk_level,
            confidence=adjusted_confidence,
            abstention_required=abstention_req,
        )
        priority = active_policy.determine_priority(decision)

        dominant_driver_name = drivers[0]["feature"] if drivers else None
        recommended_action = active_policy.generate_recommended_action(
            decision=decision,
            risk_level=risk_level,
            dominant_driver=dominant_driver_name,
            location=loc_str if loc_str else None,
        )

        # 8. Decision Sensitivity & Counterfactuals
        sensitivity = self.sensitivity_analyzer.analyze_sensitivity(
            risk_score=fused_risk_score,
            current_decision=decision,
            current_risk_level=risk_level,
            drivers=drivers,
            policy=active_policy,
        )

        # 9. Deterministic Decision Hash ID
        hash_input = f"{loc_str}_{variable}_{lead_h}_{fused_risk_score:.4f}_{raw_prob:.4f}_{cal_prob:.4f}"
        decision_id = f"dec_{hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:12]}"

        # Levels
        if adjusted_confidence >= 0.80:
            conf_level_str = "HIGH"
        elif adjusted_confidence >= 0.60:
            conf_level_str = "MODERATE"
        elif adjusted_confidence >= 0.40:
            conf_level_str = "LOW"
        else:
            conf_level_str = "VERY_LOW"

        u_score = uncertainty_res.get("composite_uncertainty_score", 0.5)
        if u_score >= 0.75:
            u_level_str = "EXTREME"
        elif u_score >= 0.50:
            u_level_str = "HIGH"
        elif u_score >= 0.25:
            u_level_str = "MODERATE"
        else:
            u_level_str = "LOW"

        lead_level_str = "SHORT" if lead_h <= 24 else ("MEDIUM" if lead_h <= 48 else "EXTENDED")

        provenance = {
            "engine_version": "15.0.0",
            "policy_version": "1.0",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_type": type(self.model).__name__ if self.model else "Heuristic",
            "calibrator_type": type(self.calibrator).__name__ if self.calibrator else "None",
            "feature_count": len(self.feature_names) or len(row_dict),
            "data_quality_issues": dq_issues,
        }

        return ForecastRiskDecision(
            decision_id=decision_id,
            decision=decision,
            risk_level=risk_level,
            risk_score=round(fused_risk_score, 4),
            raw_bust_probability=round(raw_prob, 4),
            calibrated_bust_probability=round(cal_prob, 4),
            confidence=round(adjusted_confidence, 4),
            confidence_level=conf_level_str,
            uncertainty_level=u_level_str,
            novelty_level=novelty_res.get("novelty_state", "NORMAL"),
            data_quality_level=dq_state,
            lead_time_level=lead_level_str,
            warning_priority=priority,
            recommended_action=recommended_action,
            abstention_required=abstention_req,
            abstention_reason=abstention_reason,
            dominant_risk_drivers=drivers,
            supporting_evidence=[item.__dict__ for item in supporting_ev],
            contradicting_evidence=[item.__dict__ for item in contradicting_ev],
            evidence_conflict_score=round(conflict_score, 4),
            historical_analogue_support=retrieval_res,
            location_reliability=location_profile,
            sensitivity_analysis=sensitivity,
            provenance=provenance,
        )

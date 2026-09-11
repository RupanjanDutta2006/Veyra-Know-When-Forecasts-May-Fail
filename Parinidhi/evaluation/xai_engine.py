"""
Master Explainable Forecast-Bust Intelligence Engine (Day 17).

Unifies and orchestrates the complete Veyra reasoning pipeline:
- Feature Attribution & Drivers (Day 14)
- Uncertainty Decomposition & Novelty (Day 14)
- Historical Analogue Patterns (Day 14)
- Governed Operational Decisions & Abstention (Day 15)
- Temporal Failure Trajectories & Time-to-Risk (Day 16)
- Deterministic Decision Counterfactuals (Day 17)
- Multi-Level Explanation Rendering & Provenance (Day 17)

Scientific Safeguards:
- 100% deterministic mathematical execution.
- Strict anti-leakage audit between DECISION_TIME and POST_HOC_EVALUATION.
- Independent Explanation Confidence calculation.
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_schema import ForecastRiskDecision
from evaluation.explanation_engine import ForecastFailureExplainer
from evaluation.temporal_early_warning_engine import TemporalEarlyWarningEngine
from evaluation.trajectory_schema import ForecastTrajectory, TrajectoryAssessment
from evaluation.xai_attribution import XAIAttributionEngine
from evaluation.xai_counterfactual import DecisionCounterfactualGenerator
from evaluation.xai_renderer import XAIRenderer
from evaluation.xai_schema import (
    CanonicalXAIExplanation,
    DecisionRationale,
    EvidenceConflictItem,
    ExplanationLevel,
    ExplanationMode,
    HistoricalEvidenceAlignment,
    HistoricalEvidenceExplanation,
    NoveltyExplanation,
    TemporalDynamicsExplanation,
    UncertaintyExplanation,
    UncertaintySource,
)
from features.contract import UNAVAILABLE_UNTIL_VERIFICATION, validate_feature_contract


# Authorized forbidden verification columns
FORBIDDEN_VERIFICATION_COLUMNS = set(UNAVAILABLE_UNTIL_VERIFICATION).union({
    "truth_value",
    "forecast_error",
    "forecast_abs_error",
    "ensemble_mean_error",
    "ensemble_mean_abs_error",
    "bust_label",
    "is_bust",
    "bust_label_q9",
    "bust_label_q95",
    "bust_label_q975",
    "bust_label_q99",
})


class ExplainableForecastEngine:
    """
    Unified master engine for generating canonical, deterministic forecast failure explanations.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        feature_names: Optional[List[str]] = None,
        decision_engine: Optional[ForecastRiskDecisionEngine] = None,
        temporal_engine: Optional[TemporalEarlyWarningEngine] = None,
        explainer_day14: Optional[ForecastFailureExplainer] = None,
        attribution_engine: Optional[XAIAttributionEngine] = None,
        counterfactual_gen: Optional[DecisionCounterfactualGenerator] = None,
    ):
        self.model = model
        self.feature_names_ = feature_names or []
        self.decision_engine = decision_engine or ForecastRiskDecisionEngine()
        self.temporal_engine = temporal_engine or TemporalEarlyWarningEngine()
        self.explainer_day14 = explainer_day14 or ForecastFailureExplainer()
        self.attribution_engine = attribution_engine or XAIAttributionEngine(model=model, feature_names=feature_names)
        self.counterfactual_gen = counterfactual_gen or DecisionCounterfactualGenerator()
        self.is_fitted_ = False

    def fit_reference_context(
        self,
        df_train: pd.DataFrame,
        X_train: Union[pd.DataFrame, np.ndarray],
        y_train: pd.Series,
    ) -> "ExplainableForecastEngine":
        """
        Fit all underlying explainability, novelty, and retrieval subsystems strictly on training data.
        """
        if isinstance(X_train, pd.DataFrame):
            self.feature_names_ = list(X_train.columns)
            X_df = X_train
        else:
            self.feature_names_ = [f"f_{i}" for i in range(X_train.shape[1])]
            X_df = pd.DataFrame(X_train, columns=self.feature_names_)

        self.explainer_day14.fit_reference_context(
            df_train=df_train,
            X_train=X_df,
            y_train=y_train,
            model=self.model,
        )
        self.attribution_engine.fit_model_context(self.model, self.feature_names_)
        self.is_fitted_ = True
        return self

    def generate_explanation(
        self,
        features: Union[pd.Series, pd.DataFrame, Dict[str, Any]],
        trajectory: Optional[ForecastTrajectory] = None,
        trajectory_assessment: Optional[TrajectoryAssessment] = None,
        location_id: str = "unknown",
        variable: str = "surface_pressure",
        valid_time_utc: str = "2026-08-23T00:00:00Z",
        issue_time_utc: str = "2026-08-20T00:00:00Z",
        mode: ExplanationMode = ExplanationMode.DECISION_TIME,
        post_hoc_truth: Optional[Dict[str, Any]] = None,
    ) -> CanonicalXAIExplanation:
        """
        Generate a complete CanonicalXAIExplanation from structured evidence.

        Anti-Leakage Governance:
        - DECISION_TIME: Strictly rejects all verification/target columns (truth_value, forecast_error, bust_label).
        - POST_HOC_EVALUATION: Structurally isolates verification columns into post_hoc_verification.
          Sanitized features are strictly provided to model inference, attribution, uncertainty, and decisions.
        """
        if isinstance(features, pd.DataFrame):
            row_dict = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            row_dict = features.to_dict()
        else:
            row_dict = dict(features)

        # 1. Anti-leakage audit and structural separation
        forbidden_in_input = [
            k for k in row_dict.keys()
            if k in FORBIDDEN_VERIFICATION_COLUMNS or k in UNAVAILABLE_UNTIL_VERIFICATION
        ]

        if mode == ExplanationMode.DECISION_TIME:
            if forbidden_in_input:
                raise ValueError(
                    f"Target leakage rejected in DECISION_TIME explanation mode: {forbidden_in_input}"
                )
            sanitized_features = dict(row_dict)
            retrospective_payload = None
        elif mode == ExplanationMode.POST_HOC_EVALUATION:
            # Structurally isolate scientific features from retrospective verification payload
            sanitized_features = {
                k: v for k, v in row_dict.items()
                if k not in FORBIDDEN_VERIFICATION_COLUMNS and k not in UNAVAILABLE_UNTIL_VERIFICATION
            }
            retrospective_extracted = {
                k: v for k, v in row_dict.items()
                if k in FORBIDDEN_VERIFICATION_COLUMNS or k in UNAVAILABLE_UNTIL_VERIFICATION
            }
            retrospective_payload = dict(retrospective_extracted)
            if post_hoc_truth:
                retrospective_payload.update(post_hoc_truth)
        else:
            raise ValueError(f"Unsupported explanation mode: {mode}")

        # 2. Extract base features safely from sanitized feature vector
        ens_std = float(sanitized_features.get("ensemble_std", 1.0))
        ens_mean = float(sanitized_features.get("ensemble_mean", sanitized_features.get("forecast_value", 0.0)))
        lead_h = float(sanitized_features.get("lead_hours", 72.0))

        # Base risk computation / proxy
        if self.model is not None and hasattr(self.model, "predict_proba") and self.feature_names_:
            # Format feature vector
            X_df = pd.DataFrame([{col: sanitized_features.get(col, 0.0) for col in self.feature_names_}])
            risk_score = float(self.model.predict_proba(X_df)[0, 1])
        else:
            # Fallback heuristic risk proxy for prototype/unfitted scenarios
            risk_score = float(np.clip((ens_std / 2.5) * (1.0 + lead_h / 120.0), 0.05, 0.95))

        calibrated_risk = risk_score

        # 3. Assess Trajectory if provided
        t_assessment = trajectory_assessment
        if t_assessment is None and trajectory is not None:
            t_assessment = self.temporal_engine.assess_trajectory(trajectory)

        # 4. Compute Day 14 Components strictly from sanitized features
        comp_exp = self.explainer_day14.explain_forecast(
            features=sanitized_features,
            risk_probability=calibrated_risk,
            location_id=location_id,
            variable=variable,
        )

        risk_conf = comp_exp.risk_confidence
        novelty_data = comp_exp.novelty
        nov_score = float(novelty_data.get("novelty_score", novelty_data.get("score", 0.0)))

        # 5. Compute Day 15 Operational Decision strictly from sanitized features
        decision_obj: ForecastRiskDecision = self.decision_engine.decide_forecast_risk(
            features=sanitized_features,
            raw_bust_probability=calibrated_risk,
            location_id=location_id,
            variable=variable,
        )

        # 6. Feature Attribution & Drivers strictly from sanitized features (Day 17)
        risk_drivers, protective_drivers, reconcil_meta = self.attribution_engine.compute_risk_drivers(
            features=sanitized_features,
            current_risk=calibrated_risk,
        )

        # 7. Uncertainty Decomposition (Day 17 structured)
        unc_data = comp_exp.uncertainty_components
        spread_mag = float(unc_data.get("ensemble_spread", ens_std))
        nov_mag = float(unc_data.get("novelty_score", nov_score))
        instab_mag = 0.5 if (t_assessment and t_assessment.instability_detected) else 0.0

        # Determine dominant uncertainty source
        if nov_mag >= 2.0:
            dom_unc = UncertaintySource.EPISTEMIC_NOVELTY
        elif spread_mag >= 2.5:
            dom_unc = UncertaintySource.ENSEMBLE_DISPERSION
        elif instab_mag > 0.0:
            dom_unc = UncertaintySource.TEMPORAL_INSTABILITY
        elif lead_h >= 60.0:
            dom_unc = UncertaintySource.FORECAST_HORIZON
        else:
            dom_unc = UncertaintySource.ENSEMBLE_DISPERSION

        sec_unc = []
        if lead_h >= 48.0 and dom_unc != UncertaintySource.FORECAST_HORIZON:
            sec_unc.append(UncertaintySource.FORECAST_HORIZON)
        if spread_mag >= 1.5 and dom_unc != UncertaintySource.ENSEMBLE_DISPERSION:
            sec_unc.append(UncertaintySource.ENSEMBLE_DISPERSION)

        uncertainty_exp = UncertaintyExplanation(
            dominant_source=dom_unc,
            secondary_sources=sec_unc,
            ensemble_spread_magnitude=round(spread_mag, 3),
            epistemic_novelty_magnitude=round(nov_mag, 3),
            temporal_instability_magnitude=round(instab_mag, 3),
            confidence_impact_score=round(1.0 - risk_conf, 3),
            narrative=(
                f"Uncertainty is dominated by {dom_unc.value.replace('_', ' ').lower()} "
                f"(spread={spread_mag:.2f}, novelty={nov_mag:.2f}), resulting in a confidence impact of -{(1.0 - risk_conf):.2f}."
            ),
        )

        # 8. Novelty Explanation (Day 17)
        is_in_dom = bool(novelty_data.get("is_in_domain", nov_score < 2.0))
        nov_level = str(novelty_data.get("novelty_state", novelty_data.get("level", "NORMAL")))
        nov_exp = NoveltyExplanation(
            is_in_domain=is_in_dom,
            novelty_score=round(nov_score, 3),
            novelty_level=nov_level,
            confidence_impact=round(float(novelty_data.get("confidence_penalty", 0.0)), 3),
            contributed_to_abstention=(decision_obj.decision.value == "ABSTAIN" and nov_score >= 2.50),
            narrative=(
                f"Feature vector resides in {nov_level} regime (distance={nov_score:.2f}). "
                f"{'Input manifold is well supported by historical training data.' if is_in_dom else 'Novel atmospheric state reduces confidence.'}"
            ),
        )

        # 9. Historical Analogue Explanation (Day 17)
        hist_data = comp_exp.historical_analogues
        an_count = int(hist_data.get("count", 0))
        fail_rate = float(hist_data.get("failure_rate", 0.0))
        sim_score = float(hist_data.get("mean_similarity", 0.8))

        if an_count < 3:
            alignment = HistoricalEvidenceAlignment.INSUFFICIENT_EVIDENCE
            hist_narr = "Insufficient historical failure analogues to establish statistical precedence."
        elif abs(fail_rate - calibrated_risk) < 0.25:
            alignment = HistoricalEvidenceAlignment.SUPPORTING
            hist_narr = f"Historical analogues with similar dynamics exhibited a {fail_rate:.1%} failure frequency, supporting the current risk assessment."
        else:
            alignment = HistoricalEvidenceAlignment.CONTRADICTING
            hist_narr = f"Historical failure frequency ({fail_rate:.1%}) diverges from instantaneous model risk ({calibrated_risk:.1%})."

        hist_exp = HistoricalEvidenceExplanation(
            alignment=alignment,
            analogue_count=an_count,
            historical_failure_rate=round(fail_rate, 3),
            trajectory_similarity=round(sim_score, 3),
            has_sufficient_support=(an_count >= 3),
            narrative=hist_narr,
            sample_analogue_ids=list(hist_data.get("sample_ids", [])),
        )

        # 10. Temporal Dynamics Explanation (Day 17)
        temp_exp = None
        if t_assessment is not None:
            t_str = "CRITICAL" if t_assessment.estimated_hours_to_critical == 0.0 else (
                f"{t_assessment.estimated_hours_to_critical:.1f} hours ({t_assessment.estimated_cycles_to_critical:.1f} cycles)"
                if t_assessment.estimated_hours_to_critical is not None else "No projected crossing"
            )
            temp_exp = TemporalDynamicsExplanation(
                sequence_length=t_assessment.sequence_length,
                risk_trend=t_assessment.state.value,
                risk_velocity=round(t_assessment.risk_slope, 4),
                risk_acceleration=round(t_assessment.risk_acceleration, 4),
                persistence_cycles=int(t_assessment.risk_persistence),
                spread_growth_fraction=round(t_assessment.spread_slope, 3),
                forecast_revision_velocity=round(t_assessment.revision_velocity, 3),
                instability_detected=t_assessment.instability_detected,
                trajectory_state=t_assessment.state.value,
                warning_horizon=t_assessment.warning_horizon.value,
                time_to_critical_risk_str=t_str,
                time_to_risk_estimable=(t_assessment.estimated_hours_to_critical is not None),
                narrative=(
                    f"Forecast trajectory is in {t_assessment.state.value} state across {t_assessment.sequence_length} cycles. "
                    f"Early Warning Score = {t_assessment.early_warning_score:.2f} ({t_assessment.warning_horizon.value}). "
                    f"Time-to-critical risk estimate: {t_str}."
                ),
            )

        # 11. Evidence Conflicts (Day 17)
        conflicts: List[EvidenceConflictItem] = []
        if hist_exp.alignment == HistoricalEvidenceAlignment.CONTRADICTING:
            conflicts.append(
                EvidenceConflictItem(
                    source_a="CALIBRATED_ML_RISK",
                    source_b="HISTORICAL_ANALOGUES",
                    conflict_category="MODEL_ANALOGUE_DISAGREEMENT",
                    disagreement_magnitude=round(abs(calibrated_risk - fail_rate), 3),
                    effect_on_confidence=0.15,
                    effect_on_decision="Degraded confidence; triggered conservative monitoring.",
                    resolution_status="UNRESOLVED_DEGRADED",
                )
            )
        if t_assessment and t_assessment.state.value == "STABLE_LOW" and calibrated_risk >= 0.40:
            conflicts.append(
                EvidenceConflictItem(
                    source_a="INSTANTANEOUS_RISK",
                    source_b="TEMPORAL_TRAJECTORY",
                    conflict_category="TEMPORAL_STATIC_DISCREPANCY",
                    disagreement_magnitude=0.30,
                    effect_on_confidence=0.10,
                    effect_on_decision="Suppressed premature warning escalation until multi-cycle confirmation.",
                    resolution_status="RESOLVED",
                )
            )

        # 12. Decision Rationale (Day 17)
        safety_constraints = []
        if decision_obj.abstention_required:
            safety_constraints.append(f"Abstention required: {decision_obj.abstention_reason}")
        if decision_obj.data_quality_level.value != "CLEAN":
            safety_constraints.append(f"Data quality state: {decision_obj.data_quality_level.value}")

        dec_rat = DecisionRationale(
            decision=decision_obj.decision.value,
            risk_level=decision_obj.risk_level.value,
            warning_priority=decision_obj.warning_priority.value,
            primary_triggers=[f"Calibrated risk {calibrated_risk:.2%}", f"Confidence {risk_conf:.2%}"],
            governing_threshold_applied=f"Threshold >= {0.40 if 'WARN' in decision_obj.decision.value else 0.22}",
            safety_constraints_applied=safety_constraints,
            abstention_triggered=decision_obj.abstention_required,
            abstention_reason=decision_obj.abstention_reason,
            recommended_action=decision_obj.recommended_action,
        )

        # 13. Decision Counterfactuals (Day 17)
        slope_val = t_assessment.risk_slope if t_assessment else 0.0
        cfs = self.counterfactual_gen.generate_counterfactuals(
            current_decision=decision_obj.decision.value,
            current_risk=calibrated_risk,
            current_confidence=risk_conf,
            novelty_score=nov_score,
            temporal_slope=slope_val,
            ensemble_std=ens_std,
            abstention_reason=decision_obj.abstention_reason,
        )

        # 14. Explanation Confidence Score (Independent metric)
        # Combines attribution completeness (0.25), novelty support (0.25), analogue support (0.25), evidence agreement (0.25)
        attr_comp = 1.0 if len(risk_drivers) + len(protective_drivers) >= 3 else 0.70
        nov_sup = float(np.clip(1.0 - (nov_score / 3.0), 0.20, 1.0))
        hist_sup = 0.90 if hist_exp.has_sufficient_support else 0.50
        conf_agr = 0.95 if len(conflicts) == 0 else 0.65
        explanation_confidence = float(np.clip(0.25 * attr_comp + 0.25 * nov_sup + 0.25 * hist_sup + 0.25 * conf_agr, 0.10, 0.99))

        # 15. Operator Attention & Limitations
        op_attention = [
            f"Review NWP initialization trends for {variable} at {location_id}.",
            f"Monitor ensemble spread expansion across next 6-hour cycle.",
        ]
        if decision_obj.decision.value in ("WARN_POTENTIAL_BUST", "ALERT_CRITICAL_BUST"):
            op_attention.insert(0, "Prepare operational contingency and consult alternative deterministic guidance.")

        limitations = [
            "Explanation reflects NWP ensemble dispersion and feature moments; not physical meteorological causality.",
            "Counterfactuals represent policy threshold sensitivities (DECISION_COUNTERFACTUAL), not atmospheric intervention forecasts.",
        ]

        # 16. Overall Assessment Narrative
        overall_narrative = (
            f"Forecast for {variable} at {location_id} has a calibrated bust risk of {calibrated_risk:.1%} "
            f"({decision_obj.risk_level.value}) with {risk_conf:.1%} confidence. "
            f"Veyra selected operational action `{decision_obj.decision.value}` ({decision_obj.warning_priority.value}). "
            f"Primary risk driver is {risk_drivers[0].display_name if risk_drivers else 'synoptic regime'}."
        )

        explanation_id = f"xai:{location_id}:{variable}:{valid_time_utc}"

        thresh_tuple = (
            self.counterfactual_gen.t_trust,
            self.counterfactual_gen.t_monitor,
            self.counterfactual_gen.t_caution,
            self.counterfactual_gen.t_warn,
        )

        explanation = CanonicalXAIExplanation(
            explanation_id=explanation_id,
            schema_version="17.0.0",
            mode=mode,
            location_id=location_id,
            variable=variable,
            valid_time_utc=valid_time_utc,
            issue_time_utc=issue_time_utc,
            risk_score=round(risk_score, 4),
            calibrated_bust_probability=round(calibrated_risk, 4),
            risk_confidence=round(risk_conf, 4),
            explanation_confidence=round(explanation_confidence, 4),
            operational_decision=decision_obj.decision.value,
            warning_priority=decision_obj.warning_priority.value,
            overall_narrative=overall_narrative,
            risk_drivers=risk_drivers,
            protective_drivers=protective_drivers,
            uncertainty=uncertainty_exp,
            novelty=nov_exp,
            historical_evidence=hist_exp,
            temporal_dynamics=temp_exp,
            evidence_conflicts=conflicts,
            decision_rationale=dec_rat,
            counterfactuals=cfs,
            recommended_operator_attention=op_attention,
            limitations=limitations,
            post_hoc_verification=retrospective_payload if mode == ExplanationMode.POST_HOC_EVALUATION else None,
        )

        explanation.decision_provenance_hash = explanation.compute_decision_provenance_hash(governing_thresholds=thresh_tuple)
        explanation.provenance_hash = explanation.compute_provenance_hash(governing_thresholds=thresh_tuple)
        return explanation

    def render_explanation(
        self,
        explanation: CanonicalXAIExplanation,
        level: ExplanationLevel = ExplanationLevel.TECHNICAL_EXPLANATION,
    ) -> str:
        """Render explanation using XAIRenderer."""
        return XAIRenderer.render(explanation, level=level)

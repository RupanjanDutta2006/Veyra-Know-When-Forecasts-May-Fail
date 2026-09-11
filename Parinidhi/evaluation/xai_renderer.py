"""
Deterministic Multi-Level XAI Explanation Renderer (Day 17).

Provides three deterministic presentation levels:
- Level 1: Operator Summary (executive brief)
- Level 2: Technical Explanation (structured diagnostic report)
- Level 3: Forensic Trace (full mathematical breakdown and provenance)

Scientific Safeguards:
- 100% deterministic template generation from structured schema.
- Zero LLM calls in rendering pipeline.
- Strictly ground all claims in underlying mathematical evidence.
"""

from typing import Any, Dict
from evaluation.xai_schema import CanonicalXAIExplanation, ExplanationLevel


class XAIRenderer:
    """
    Renders CanonicalXAIExplanation into multi-level human-readable markdown formats.
    """

    @classmethod
    def render(cls, explanation: CanonicalXAIExplanation, level: ExplanationLevel = ExplanationLevel.TECHNICAL_EXPLANATION) -> str:
        """Render explanation at requested granularity level."""
        if level == ExplanationLevel.OPERATOR_SUMMARY:
            return cls.render_operator_summary(explanation)
        elif level == ExplanationLevel.FORENSIC_TRACE:
            return cls.render_forensic_trace(explanation)
        else:
            return cls.render_technical_explanation(explanation)

    @classmethod
    def render_operator_summary(cls, exp: CanonicalXAIExplanation) -> str:
        """Level 1: Concise 3-4 line operational summary for decision makers."""
        top_driver = exp.risk_drivers[0].display_name if exp.risk_drivers else "Atmospheric persistence"
        temp_state = exp.temporal_dynamics.trajectory_state if exp.temporal_dynamics else "STABLE"
        time_to_risk = exp.temporal_dynamics.time_to_critical_risk_str if exp.temporal_dynamics else "N/A"

        summary = (
            f"**[VEYRA XAI SUMMARY] {exp.location_id.upper()} ({exp.variable})**\n"
            f"- **Operational Action**: `{exp.operational_decision}` (Priority: `{exp.warning_priority}`)\n"
            f"- **Risk & Confidence**: Bust Probability = {exp.calibrated_bust_probability:.1%}, Confidence = {exp.risk_confidence:.1%}\n"
            f"- **Primary Driver**: {top_driver} | **Temporal State**: {temp_state} (Time-to-Critical: {time_to_risk})\n"
            f"- **Recommended Operator Action**: {exp.recommended_operator_attention[0] if exp.recommended_operator_attention else 'Continue standard surveillance.'}"
        )
        return summary

    @classmethod
    def render_technical_explanation(cls, exp: CanonicalXAIExplanation) -> str:
        """Level 2: Comprehensive technical diagnostic report for meteorologists & risk engineers."""
        lines = [
            f"# Veyra Forecast-Bust Diagnostic Explanation",
            f"**Target**: `{exp.location_id}` | `{exp.variable}` | Valid: `{exp.valid_time_utc}` (Issue: `{exp.issue_time_utc}`)",
            f"**Decision**: `{exp.operational_decision}` (Warning Priority: `{exp.warning_priority}`)",
            f"**Calibrated Bust Probability**: `{exp.calibrated_bust_probability:.2%}` | **Risk Confidence**: `{exp.risk_confidence:.2%}` | **XAI Confidence**: `{exp.explanation_confidence:.2%}`",
            "",
            "## 1. Overall Assessment Narrative",
            exp.overall_narrative,
            "",
            "## 2. Feature Risk Drivers & Protective Factors",
        ]

        if exp.risk_drivers:
            lines.append("### Primary Risk Drivers (Pushed Risk Upward):")
            for d in exp.risk_drivers:
                lines.append(f"- **{d.display_name}** (`{d.feature_name}` = {d.value:.2f}): Contribution `{d.normalized_contribution:+.3f}` [{d.category.value}] — {d.interpretation}")
        else:
            lines.append("- *No dominant positive risk drivers identified.*")

        if exp.protective_drivers:
            lines.append("\n### Protective Factors (Suppressed Risk):")
            for d in exp.protective_drivers:
                lines.append(f"- **{d.display_name}** (`{d.feature_name}` = {d.value:.2f}): Contribution `{d.normalized_contribution:+.3f}` [{d.category.value}] — {d.interpretation}")

        if exp.uncertainty:
            lines.append("\n## 3. Uncertainty & Novelty Analysis")
            lines.append(f"- **Dominant Uncertainty Source**: `{exp.uncertainty.dominant_source.value}`")
            if exp.uncertainty.secondary_sources:
                sec_str = ", ".join(f"`{s.value}`" for s in exp.uncertainty.secondary_sources)
                lines.append(f"- **Secondary Sources**: {sec_str}")
            lines.append(f"- **Diagnostics**: {exp.uncertainty.narrative}")

        if exp.novelty:
            lines.append(f"- **Feature-Space Novelty**: `{exp.novelty.novelty_level}` (Score = {exp.novelty.novelty_score:.2f}) — {exp.novelty.narrative}")

        if exp.temporal_dynamics:
            lines.append("\n## 4. Multi-Cycle Temporal Trajectory Dynamics")
            t = exp.temporal_dynamics
            lines.append(f"- **Trajectory State**: `{t.trajectory_state}` | **Warning Horizon**: `{t.warning_horizon}`")
            lines.append(f"- **Kinematics**: Velocity = `{t.risk_velocity:+.3f}/cycle`, Acceleration = `{t.risk_acceleration:+.3f}/cycle²`, Persistence = `{t.persistence_cycles} cycles`")
            lines.append(f"- **Time to Critical Risk (P >= 0.65)**: `{t.time_to_critical_risk_str}`")
            lines.append(f"- **Trajectory Narrative**: {t.narrative}")

        if exp.historical_evidence:
            lines.append("\n## 5. Historical Analogue Evidence")
            h = exp.historical_evidence
            lines.append(f"- **Alignment**: `{h.alignment.value}` ({h.analogue_count} nearest historical trajectories retrieved)")
            lines.append(f"- **Historical Failure Frequency**: `{h.historical_failure_rate:.1%}`")
            lines.append(f"- **Analogue Evidence**: {h.narrative}")

        if exp.evidence_conflicts:
            lines.append("\n## 6. Evidence Channel Disagreements")
            for c in exp.evidence_conflicts:
                lines.append(f"- **Conflict [{c.conflict_category}]**: `{c.source_a}` vs `{c.source_b}` (Disagreement = {c.disagreement_magnitude:.2f}) -> {c.resolution_status}")

        if exp.counterfactuals:
            lines.append("\n## 7. Policy Sensitivity Counterfactuals (`DECISION_COUNTERFACTUAL`)")
            for cf in exp.counterfactuals:
                lines.append(f"- **[{cf.target_decision_direction}]**: {cf.explanation}")

        if exp.recommended_operator_attention:
            lines.append("\n## 8. Recommended Operator Attention")
            for rec in exp.recommended_operator_attention:
                lines.append(f"- {rec}")

        if exp.limitations:
            lines.append("\n## 9. Scientific & Operational Limitations")
            for lim in exp.limitations:
                lines.append(f"- {lim}")

        if exp.post_hoc_verification:
            lines.append("\n## 10. Retrospective Post-Hoc Verification & Evaluation")
            lines.append("- **Verification Context**: Retrospective observation data audited for post-hoc analysis (isolated from decision-time inference).")
            for k, v in sorted(exp.post_hoc_verification.items()):
                lines.append(f"- **`{k}`**: `{v}`")

        lines.append(f"\n*Decision Provenance: `{exp.decision_provenance_hash}` | Execution Hash: `{exp.provenance_hash}` | Schema: `{exp.schema_version}`*")
        return "\n".join(lines)

    @classmethod
    def render_forensic_trace(cls, exp: CanonicalXAIExplanation) -> str:
        """Level 3: Full forensic trace with serialized JSON dump and parameter configuration."""
        lines = [
            f"# Veyra Forensic XAI Trace & Execution Audit",
            f"**Decision Provenance**: `{exp.decision_provenance_hash}`",
            f"**Execution Provenance Hash**: `{exp.provenance_hash}`",
            f"**Schema Version**: `{exp.schema_version}` | **Mode**: `{exp.mode.value}`",
            "",
            "## Mathematical Trace Parameters:",
            f"- `risk_score`: {exp.risk_score:.6f}",
            f"- `calibrated_bust_probability`: {exp.calibrated_bust_probability:.6f}",
            f"- `risk_confidence`: {exp.risk_confidence:.6f}",
            f"- `explanation_confidence`: {exp.explanation_confidence:.6f}",
            f"- `operational_decision`: {exp.operational_decision}",
            f"- `warning_priority`: {exp.warning_priority}",
            "",
            "## Structured JSON Representation:",
            "```json",
            exp.to_json(indent=2),
            "```",
        ]
        return "\n".join(lines)

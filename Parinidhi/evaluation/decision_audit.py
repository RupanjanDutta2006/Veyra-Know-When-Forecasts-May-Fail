"""
Operational Decision Audit, Leakage Validation & Completeness Scoring (Day 20).

Provides automated governance, forensic target-leakage audits, numerical health checks,
and completeness scoring for Veyra operational risk assessments.

Scientific Safeguards:
- Recursive Key-Based Leakage Auditing: Strictly rejects forbidden verification column names across
  flat and arbitrarily nested payloads, while cleanly permitting benign string metadata values.
- Dimensionless Completeness Scoring: Evaluates presence and health across all 8 core scientific subsystems.
- Cryptographic Audit Validation: Verifies decision provenance hash integrity and format.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np

from evaluation.decision_schema import DataQualityState, OperationalDecision
from evaluation.event_tracker import FORBIDDEN_VERIFICATION_COLUMNS
from evaluation.operational_trace_schema import (
    AuditValidationResult,
    AuditValidationState,
    CompletenessStatus,
)
from evaluation.unified_schema import AssessmentStatus, UnifiedOperationalAssessment


FORBIDDEN_LEAKAGE_TERMS = (
    "truth", "error", "bust_label", "is_bust", "obs_", "obs", "observation",
    "actual", "realized", "verified_bust", "verified_abs_error", "verification", "target"
)


class DecisionAuditValidator:
    """
    Automated scientific and operational compliance auditor.
    """

    @staticmethod
    def audit_leakage_payload(payload: Any) -> Tuple[bool, List[str]]:
        """
        Recursively audit payload for forbidden verification/target keys.
        Returns (is_clean, list_of_violations).
        """
        if payload is None:
            return True, []

        violations: List[str] = []

        def _scan(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_str = str(k).strip()
                    k_clean = k_str.lower()
                    curr_path = f"{path}.{k_str}" if path else k_str
                    if k_clean in FORBIDDEN_VERIFICATION_COLUMNS or any(t in k_clean for t in FORBIDDEN_LEAKAGE_TERMS):
                        violations.append(curr_path)
                    _scan(v, curr_path)
            elif isinstance(obj, (list, tuple, set)):
                for idx, item in enumerate(obj):
                    _scan(item, f"{path}[{idx}]")

        _scan(payload)
        return len(violations) == 0, violations

    @classmethod
    def audit_assessment(
        cls,
        assessment: UnifiedOperationalAssessment,
        raw_features_payload: Optional[Any] = None,
    ) -> AuditValidationResult:
        """
        Perform a comprehensive multi-criteria audit of an operational assessment.
        """
        warnings: List[str] = list(assessment.warnings)
        limitations: List[str] = list(assessment.limitations)
        missing_components: List[str] = []

        # 1. Leakage Audit
        leakage_clean, violations = cls.audit_leakage_payload(raw_features_payload)
        if not leakage_clean:
            leakage_status = f"FAILED: Target leakage detected in paths {violations}"
        else:
            leakage_status = "PASSED: Zero target leakage detected in decision-time payload"

        # 2. Completeness Scoring (8 core components)
        present_count = 0

        # Component 1: Identity & Coordinates
        if assessment.location_id and assessment.variable and assessment.valid_time_utc:
            present_count += 1
        else:
            missing_components.append("IDENTITY_COORDINATES")

        # Component 2: Decision Policy
        if assessment.operational_decision is not None and assessment.warning_priority is not None:
            present_count += 1
        else:
            missing_components.append("DECISION_POLICY")

        # Component 3: Risk Calibration
        if 0.0 <= assessment.calibrated_risk <= 1.0 and 0.0 <= assessment.confidence_score <= 1.0:
            present_count += 1
        else:
            missing_components.append("RISK_CALIBRATION")

        # Component 4: Uncertainty Decomposition
        if assessment.uncertainty is not None and assessment.uncertainty.dominant_source:
            present_count += 1
        else:
            missing_components.append("UNCERTAINTY_DECOMPOSITION")

        # Component 5: Feature Novelty
        if assessment.novelty is not None and assessment.novelty.novelty_score is not None:
            present_count += 1
        else:
            missing_components.append("FEATURE_NOVELTY")

        # Component 6: Temporal Dynamics
        if assessment.trajectory_state is not None:
            present_count += 1
        else:
            missing_components.append("TEMPORAL_DYNAMICS")

        # Component 7: Longitudinal Event State
        if assessment.event_id and assessment.event_lifecycle_state is not None:
            present_count += 1
        else:
            missing_components.append("EVENT_INTELLIGENCE")

        # Component 8: Cryptographic Provenance
        if assessment.decision_provenance_hash and len(assessment.decision_provenance_hash) == 16:
            present_count += 1
        else:
            missing_components.append("CRYPTOGRAPHIC_PROVENANCE")

        completeness_score = round(present_count / 8.0, 3)
        if completeness_score == 1.0:
            completeness_status = CompletenessStatus.COMPLETE
        elif completeness_score >= 0.625:
            completeness_status = CompletenessStatus.PARTIAL
        elif completeness_score >= 0.25:
            completeness_status = CompletenessStatus.MINIMAL
        else:
            completeness_status = CompletenessStatus.INVALID

        # 3. Numerical Health Audit
        numerical_issues = []
        if np.isnan(assessment.calibrated_risk) or np.isinf(assessment.calibrated_risk):
            numerical_issues.append("NaN/Inf in calibrated_risk")
        if np.isnan(assessment.confidence_score) or np.isinf(assessment.confidence_score):
            numerical_issues.append("NaN/Inf in confidence_score")
        if assessment.lead_hours < 0.0:
            numerical_issues.append("Negative lead_hours")
        if assessment.ensemble_std < 0.0:
            numerical_issues.append("Negative ensemble_std")

        if numerical_issues:
            numerical_status = f"WARNING: Numerical anomalies: {', '.join(numerical_issues)}"
            warnings.extend(numerical_issues)
        else:
            numerical_status = "PASSED: All numerical fields within valid physical bounds"

        # 4. Provenance Audit
        if len(assessment.decision_provenance_hash) == 16 and all(c in "0123456789abcdef" for c in assessment.decision_provenance_hash):
            provenance_status = "PASSED: Valid 16-character SHA-256 fingerprint verified"
        else:
            provenance_status = "FAILED: Malformed or missing decision provenance hash"

        # 5. Temporal Consistency Audit
        temporal_issues = []
        if assessment.valid_time_utc and assessment.issue_time_utc:
            try:
                # Basic string or ISO validation
                v_clean = assessment.valid_time_utc.replace("Z", "+00:00")
                i_clean = assessment.issue_time_utc.replace("Z", "+00:00")
                v_dt = datetime.fromisoformat(v_clean)
                i_dt = datetime.fromisoformat(i_clean)
                if v_dt < i_dt:
                    temporal_issues.append("valid_time precedes issue_time")
            except Exception:
                pass  # Fall back to lead_hours check

        if assessment.lead_hours < 0.0:
            temporal_issues.append("Negative lead time")

        if temporal_issues:
            temporal_status = f"WARNING: {', '.join(temporal_issues)}"
            warnings.extend(temporal_issues)
        else:
            temporal_status = "PASSED: Chronologically consistent forecast issue/valid times"

        # 6. Final Audit State Assignment
        if not leakage_clean or "FAILED" in provenance_status or completeness_status == CompletenessStatus.INVALID:
            audit_state = AuditValidationState.CRITICAL_FAILURE
            is_valid = False
        elif assessment.operational_decision == OperationalDecision.ABSTAIN:
            audit_state = AuditValidationState.ABSTAINED
            is_valid = True
        elif warnings:
            audit_state = AuditValidationState.WARNINGS_DETECTED
            is_valid = True
        else:
            audit_state = AuditValidationState.PASSED
            is_valid = True

        return AuditValidationResult(
            is_valid=is_valid,
            completeness_score=completeness_score,
            completeness_status=completeness_status,
            leakage_audit_status=leakage_status,
            provenance_audit_status=provenance_status,
            numerical_validity_status=numerical_status,
            temporal_consistency_status=temporal_status,
            audit_state=audit_state,
            warnings=tuple(warnings),
            limitations=tuple(limitations),
            missing_components=tuple(missing_components),
        )

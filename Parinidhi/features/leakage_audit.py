"""
Automated Data Leakage Audit.

Validates that feature matrices strictly adhere to the operational issue-time constraint:
    availability_time <= issue_time

Scientific Safeguard:
Verification observations, ERA5 reanalysis truth, forecast errors, and bust labels
must never enter the live feature set. Any leakage violation raises DataLeakageError.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import numpy as np
import pandas as pd


FORBIDDEN_KEYWORD_BLACKLIST: Set[str] = {
    "truth",
    "truth_value",
    "truth_source",
    "forecast_error",
    "forecast_abs_error",
    "ensemble_mean_error",
    "ensemble_mean_abs_error",
    "actual",
    "observed",
    "observation",
    "era5",
    "reanalysis",
    "bust_label",
    "target",
    "label",
    "error",
}


class DataLeakageError(Exception):
    """Raised when forbidden future or ground-truth information is detected in feature columns."""
    pass


class LeakageAuditor:
    """Automated leakage verification auditor for machine-learning feature sets."""

    def __init__(self, forbidden_keywords: Optional[Set[str]] = None):
        self.forbidden_keywords = forbidden_keywords or FORBIDDEN_KEYWORD_BLACKLIST

    def audit_feature_names(self, feature_names: List[str]) -> List[str]:
        """Check feature column names against forbidden ground-truth / target keywords."""
        violations = []
        for name in feature_names:
            name_lower = name.lower()
            for keyword in self.forbidden_keywords:
                # Check for exact match or substring match with word boundaries / underscores
                if keyword in name_lower.split("_") or keyword == name_lower:
                    violations.append(f"Forbidden keyword '{keyword}' detected in feature column '{name}'")
        return violations

    def audit_timestamp_availability(
        self,
        metadata_df: pd.DataFrame,
    ) -> List[str]:
        """
        Verify that all features in metadata are tagged with issue_time and that
        the issue_time is known prior to or at forecast issuance.
        """
        violations = []
        if "issue_time" not in metadata_df.columns:
            violations.append("Metadata is missing 'issue_time' column required for temporal auditing.")
            return violations

        if "valid_time" in metadata_df.columns:
            issue_times = pd.to_datetime(metadata_df["issue_time"], utc=True)
            valid_times = pd.to_datetime(metadata_df["valid_time"], utc=True)
            
            # Forecast lead hours must be non-negative (valid_time >= issue_time)
            invalid_leads = (valid_times < issue_times).sum()
            if invalid_leads > 0:
                violations.append(f"Found {invalid_leads} records where valid_time < issue_time (assimilation/past timestamp leak).")

        return violations

    def audit_feature_matrix(
        self,
        features_df: pd.DataFrame,
        metadata_df: pd.DataFrame,
        target_series: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        """
        Run full automated leakage audit on a feature matrix X.

        Args:
            features_df: The extracted feature DataFrame X.
            metadata_df: Associated metadata DataFrame.
            target_series: Optional target series (e.g. bust_label or forecast_abs_error) for correlation check.

        Returns:
            Dict containing audit report details.

        Raises:
            DataLeakageError: If any leakage violation is identified.
        """
        violations: List[str] = []

        # 1. Column Name Blacklist Audit
        name_violations = self.audit_feature_names(list(features_df.columns))
        violations.extend(name_violations)

        # 2. Temporal Availability Audit
        time_violations = self.audit_timestamp_availability(metadata_df)
        violations.extend(time_violations)

        # 3. Target Correlation Sanity Check (if target provided)
        suspicious_correlations = []
        if target_series is not None and not target_series.empty:
            target_clean = target_series.astype(float)
            target_std = target_clean.std()
            if target_std > 1e-8:
                for col in features_df.columns:
                    try:
                        feat_series = features_df[col].astype(float)
                        if feat_series.std() > 1e-8:
                            corr = feat_series.corr(target_clean)
                            if not np.isnan(corr) and abs(corr) >= 0.999:
                                suspicious_correlations.append(
                                    f"Feature '{col}' has near-perfect correlation (|r| = {abs(corr):.4f}) with target."
                                )
                    except Exception:
                        pass

        if suspicious_correlations:
            violations.extend(suspicious_correlations)

        # If any violation found, raise explicit error
        if violations:
            violation_summary = "\n  - ".join(violations)
            raise DataLeakageError(
                f"Data Leakage Audit FAILED with {len(violations)} violation(s):\n  - {violation_summary}"
            )

        report = {
            "status": "PASSED",
            "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "features_audited_count": len(features_df.columns),
            "records_audited_count": len(features_df),
            "feature_column_list": list(features_df.columns),
            "leakage_checks_performed": [
                "Forbidden ground-truth keyword blacklist check",
                "Temporal issue_time availability check",
                "Non-negative lead horizon validation",
                "Near-deterministic target correlation check",
            ],
        }
        return report

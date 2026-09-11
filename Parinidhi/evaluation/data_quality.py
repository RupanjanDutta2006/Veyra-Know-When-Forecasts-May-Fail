"""
Data Quality Auditing and Gating Module (Day 15).

Verifies the physical completeness, sanity, and reliability of issue-time forecast inputs
prior to operational decision-making.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from evaluation.decision_schema import DataQualityState
from features.contract import validate_feature_contract


class DataQualityAuditor:
    """
    Evaluates input data quality, flags corrupted/insufficient inputs, and enforces sanity gates.
    """

    def audit_features(
        self,
        features: Union[pd.Series, pd.DataFrame, Dict[str, Any]],
        expected_features: Optional[List[str]] = None,
    ) -> Tuple[DataQualityState, float, List[str]]:
        """
        Audit issue-time feature dictionary or dataframe.

        Returns:
            Tuple of (quality_state, missing_fraction, quality_issues)
        """
        if isinstance(features, pd.DataFrame):
            row_dict = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            row_dict = features.to_dict()
        else:
            row_dict = dict(features)

        issues: List[str] = []

        # 1. Check for verification/target leakage
        violations = validate_feature_contract(list(row_dict.keys()))
        if violations:
            issues.append(f"Security violation: Forbidden verification columns present: {violations}")
            return DataQualityState.CORRUPTED, 1.0, issues

        # 2. Check expected features and missingness
        req_features = expected_features or list(row_dict.keys())
        total_req = max(len(req_features), 1)
        missing_count = 0
        non_finite_count = 0

        for f in req_features:
            val = row_dict.get(f, np.nan)
            if pd.isna(val):
                missing_count += 1
            elif isinstance(val, (int, float)):
                if np.isinf(val):
                    non_finite_count += 1
                    issues.append(f"Non-finite value (+/-inf) detected in feature '{f}'.")

        missing_fraction = missing_count / total_req

        # 3. Check ensemble member count
        member_count = row_dict.get("member_count", 31)
        if not pd.isna(member_count) and isinstance(member_count, (int, float)):
            if member_count < 10:
                issues.append(f"Severely degraded ensemble: only {int(member_count)} members available (expected 31).")
            elif member_count < 20:
                issues.append(f"Incomplete ensemble: {int(member_count)} members available (expected 31).")

        # 4. Check negative dispersion moments (impossible physically)
        ens_std = row_dict.get("ensemble_std", 1.0)
        if not pd.isna(ens_std) and isinstance(ens_std, (int, float)) and ens_std < 0.0:
            issues.append(f"Physically impossible negative ensemble std ({ens_std}).")
            non_finite_count += 1

        # Determine DataQualityState
        if non_finite_count > 0:
            quality_state = DataQualityState.CORRUPTED
        elif missing_fraction >= 0.50:
            quality_state = DataQualityState.INSUFFICIENT
            issues.append(f"Insufficient feature completeness: {int(missing_fraction * 100)}% of features missing.")
        elif missing_fraction > 0.15 or len(issues) > 0:
            quality_state = DataQualityState.DEGRADED
        else:
            quality_state = DataQualityState.CLEAN

        return quality_state, missing_fraction, issues

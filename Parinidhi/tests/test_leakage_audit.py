"""
Unit tests for Automated Data Leakage Audit.

Tests:
1. Clean pass on valid issue-time feature matrix
2. Detection and rejection of blacklisted truth / error / observation keywords
3. Detection and rejection of past / assimilation timestamps (valid_time < issue_time)
4. Detection and rejection of near-deterministic target correlations
"""

from datetime import datetime, timezone
import pandas as pd
import pytest

from features.leakage_audit import LeakageAuditor, DataLeakageError
from features.feature_pipeline import FEATURE_COLUMN_NAMES


@pytest.fixture
def clean_feature_and_metadata():
    """Fixture returning clean feature matrix and metadata."""
    now = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    n = 20
    meta = pd.DataFrame({
        "location": ["delhi"] * n,
        "variable": ["temperature_2m"] * n,
        "issue_time": [now] * n,
        "valid_time": [now + pd.Timedelta(hours=i) for i in range(n)],
        "lead_hours": list(range(n)),
    })
    feat_dict = {col: [1.0] * n for col in FEATURE_COLUMN_NAMES}
    X = pd.DataFrame(feat_dict)
    return X, meta


def test_leakage_audit_clean_pass(clean_feature_and_metadata):
    """Test that valid feature matrix passes audit cleanly."""
    X, meta = clean_feature_and_metadata
    auditor = LeakageAuditor()
    report = auditor.audit_feature_matrix(X, meta)

    assert report["status"] == "PASSED"
    assert report["features_audited_count"] == len(FEATURE_COLUMN_NAMES)


def test_leakage_audit_rejects_forbidden_truth_keyword(clean_feature_and_metadata):
    """Test that columns containing forbidden ground-truth / error terms cause DataLeakageError."""
    X, meta = clean_feature_and_metadata

    # Inject forbidden truth column into feature matrix
    X_leaked = X.copy()
    X_leaked["era5_truth_temperature"] = 28.5

    auditor = LeakageAuditor()
    with pytest.raises(DataLeakageError) as excinfo:
        auditor.audit_feature_matrix(X_leaked, meta)

    assert "Forbidden keyword" in str(excinfo.value)
    assert "era5_truth_temperature" in str(excinfo.value)


def test_leakage_audit_rejects_past_timestamps():
    """Test that timestamps with valid_time < issue_time are flagged as leakage."""
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    meta = pd.DataFrame({
        "issue_time": [now, now],
        "valid_time": [now - pd.Timedelta(hours=2), now + pd.Timedelta(hours=2)],
    })
    X = pd.DataFrame({"forecast_value": [30.0, 31.0]})

    auditor = LeakageAuditor()
    with pytest.raises(DataLeakageError) as excinfo:
        auditor.audit_feature_matrix(X, meta)

    assert "valid_time < issue_time" in str(excinfo.value)


def test_leakage_audit_rejects_perfect_target_correlation(clean_feature_and_metadata):
    """Test that features with near-perfect correlation (|r| >= 0.999) with target trigger leakage error."""
    X, meta = clean_feature_and_metadata

    target = pd.Series([float(i) for i in range(len(X))])
    # Make a feature perfectly identical to the target
    X_leaked = X.copy()
    X_leaked["forecast_value"] = target.values

    auditor = LeakageAuditor()
    with pytest.raises(DataLeakageError) as excinfo:
        auditor.audit_feature_matrix(X_leaked, meta, target_series=target)

    assert "near-perfect correlation" in str(excinfo.value)

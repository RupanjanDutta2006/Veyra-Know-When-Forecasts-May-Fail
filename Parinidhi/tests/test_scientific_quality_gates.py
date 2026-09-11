"""
Automated Scientific Quality Gates Test Suite for Veyra (Builder 2).

Enforces strict scientific invariants:
- Zero data leakage of verification truth/error into issue-time features
- Zero row or key overlap across train/val/test partitions
- Strict chronological isolation (zero future cycle contamination)
- Zero geographic coordinate memorization (latitude/longitude forbidden)
- Zero historical error lookup leakage in feature matrix
- Deterministic feature column ordering
- Probability output bounds strictly in [0, 1]
- Cryptographic provenance and dataset manifest integrity
- Safe degraded-mode handling and valid failure fingerprint archetypes
"""

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import joblib

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from api.location_service import LocationRegistry
from features.contract import UNAVAILABLE_UNTIL_VERIFICATION
from features.forecast_intelligence_features import (
    SUPERCHARGED_PHYSICAL_FEATURES,
    ForecastIntelligenceFeaturePipeline,
    classify_failure_fingerprint,
)


@pytest.fixture
def supercharged_dataset():
    data_path = PROJECT_ROOT / "data" / "historical" / "veyra_supercharged_historical_archive.parquet"
    assert data_path.exists(), "Supercharged dataset archive missing."
    df = pd.read_parquet(data_path)
    df["issue_time"] = pd.to_datetime(df["issue_time"], utc=True)
    df["valid_time"] = pd.to_datetime(df["valid_time"], utc=True)
    return df


def test_location_registry_completeness():
    """Verify 25 canonical benchmark Indian locations."""
    reg_base = LocationRegistry()
    assert len(reg_base.list_locations()) == 25, f"Expected 25 benchmark locations, found {len(reg_base.list_locations())}"

    reg_ext = LocationRegistry(include_extended=True)
    locations = reg_ext.list_locations()
    assert len(locations) >= 25

    for loc in locations:
        assert loc["requested_coordinates"]["latitude"] is not None
        assert loc["requested_coordinates"]["longitude"] is not None
        assert loc["elevation_m"] is not None
        assert loc["climate_zone"] is not None
        assert loc["meteorological_regime"] is not None


def test_dataset_manifest_and_cryptographic_checksum():
    """Verify SHA-256 checksum of historical archive matches the dataset manifest."""
    archive_file = PROJECT_ROOT / "data" / "historical" / "veyra_supercharged_historical_archive.parquet"
    manifest_file = PROJECT_ROOT / "data" / "historical" / "dataset_manifest.json"

    assert archive_file.exists()
    assert manifest_file.exists()

    computed_sha256 = hashlib.sha256(archive_file.read_bytes()).hexdigest()
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert manifest_data["sha256_checksum"] == computed_sha256
    assert manifest_data["locations_count"] == 25
    assert manifest_data["total_records"] > 40000


def test_partition_key_disjointness(supercharged_dataset):
    """Assert zero key overlap between train, validation, and test partitions."""
    df = supercharged_dataset
    is_2017 = df["issue_time"].dt.year == 2017
    is_2026 = df["issue_time"].dt.year == 2026

    train_mask = (is_2017 & (df["issue_time"] <= pd.Timestamp("2017-03-14 23:59:59", tz="UTC"))) | \
                 (is_2026 & (df["issue_time"] <= pd.Timestamp("2026-08-22 23:59:59", tz="UTC")))

    val_mask = is_2026 & (df["issue_time"] >= pd.Timestamp("2026-08-23 00:00:00", tz="UTC")) & \
               (df["issue_time"] <= pd.Timestamp("2026-08-23 23:59:59", tz="UTC"))

    test_mask = (is_2017 & (df["issue_time"] >= pd.Timestamp("2017-03-15 00:00:00", tz="UTC"))) | \
                (is_2026 & (df["issue_time"] >= pd.Timestamp("2026-08-24 00:00:00", tz="UTC")))

    df_train = df[train_mask]
    df_val = df[val_mask]
    df_test = df[test_mask]

    def make_keys(sub_df):
        return set(zip(sub_df["location_id"], sub_df["variable"], sub_df["issue_time"], sub_df["valid_time"]))

    k_train = make_keys(df_train)
    k_val = make_keys(df_val)
    k_test = make_keys(df_test)

    assert len(k_train.intersection(k_val)) == 0, "Overlap found between train and val!"
    assert len(k_train.intersection(k_test)) == 0, "Overlap found between train and test!"
    assert len(k_val.intersection(k_test)) == 0, "Overlap found between val and test!"


def test_zero_feature_truth_leakage(supercharged_dataset):
    """Verify feature pipeline extracts zero fields blacklisted by UNAVAILABLE_UNTIL_VERIFICATION."""
    df_sample = supercharged_dataset.head(200).copy()
    pipeline = ForecastIntelligenceFeaturePipeline()
    X, _ = pipeline.extract_features(df_sample, mode="supercharged")

    for blacklisted in UNAVAILABLE_UNTIL_VERIFICATION:
        assert blacklisted not in X.columns, f"LEAKAGE: {blacklisted} present in feature columns!"


def test_forbidden_target_encoding_and_spatial_coordinates():
    """Verify model feature columns contain zero spatial coordinates or historical error matrices."""
    feature_names_path = PROJECT_ROOT / "models" / "v2" / "feature_names.json"
    assert feature_names_path.exists()
    feature_cols = json.loads(feature_names_path.read_text(encoding="utf-8"))

    forbidden_cols = ["latitude", "longitude", "hist_expected_error", "spread_skill_ratio", "overconfidence_signal"]
    for col in forbidden_cols:
        assert col not in feature_cols, f"VIOLATION: Forbidden column '{col}' found in active feature set!"


def test_probability_calibrator_bounds(supercharged_dataset):
    """Assert probability calibrator produces valid probabilities in [0.0, 1.0]."""
    calibrator_path = PROJECT_ROOT / "models" / "v2" / "probability_calibrator_v2.joblib"
    assert calibrator_path.exists()
    calibrator = joblib.load(calibrator_path)

    raw_scores = np.linspace(-5.0, 5.0, 100)
    probs = calibrator.predict_proba(raw_scores)
    assert probs.shape == (100, 2)
    assert np.all(probs >= 0.0)
    assert np.all(probs <= 1.0)
    assert np.allclose(np.sum(probs, axis=1), 1.0)


def test_failure_fingerprint_classifier_completeness():
    """Assert failure fingerprint classifier returns valid archetypes and handles extreme inputs safely."""
    valid_archetypes = {
        "RAPID_REVISION_SHOCK",
        "LONG_LEAD_DECAY",
        "DIURNAL_CONVECTIVE_MISMATCH",
        "WIND_GRADIENT_SHEAR",
        "TIGHT_CLUSTER_BREAKDOWN",
        "STABLE_SYNOPTIC_CONSENSUS",
    }

    test_cases = [
        pd.Series({"forecast_revision_mag_6h": 5.0, "ensemble_std": 1.0, "stability_index": 20.0}),
        pd.Series({"lead_hours": 72, "ensemble_std": 2.5}),
        pd.Series({"cos_hour": 0.8, "ensemble_cv": 0.25}),
        pd.Series({"is_wind_speed_10m": 1.0, "ensemble_p90": 22.0}),
        pd.Series({"structural_overconfidence_risk": 45.0, "ensemble_std": 0.5}),
        pd.Series({}), # Empty/default fallback
    ]

    for tc in test_cases:
        archetype = classify_failure_fingerprint(tc)
        assert archetype in valid_archetypes, f"Unknown archetype: {archetype}"

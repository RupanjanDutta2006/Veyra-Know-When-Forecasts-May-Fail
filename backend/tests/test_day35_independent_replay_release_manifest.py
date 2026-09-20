"""Authoritative Day 35 Test Matrix: Independent Replay + Release Manifest (Gate C5).

Validates:
1. Release manifest schema, checksums, policy versions, and tamper detection.
2. Independent replay harness reproducibility across all 10 golden matrix scenarios.
3. Contract integrity for model hashes, 50 features, IsotonicRegression calibrator, 25 certified stations.
4. Non-circular Git provenance validation.
5. Live provider smoke status handling.
"""
import copy
import json
from pathlib import Path
import tempfile
import pytest

from backend.app.core.golden_replay_matrix import GOLDEN_REPLAY_MATRIX, GoldenReplayScenario
from backend.app.core.live_smoke import LiveProviderStatus, perform_live_provider_smoke_check
from backend.app.core.release_manifest import (
    EXPECTED_CALIBRATOR_SHA256,
    EXPECTED_FEATURE_COUNT,
    EXPECTED_MODEL_SHA256,
    load_release_manifest,
    validate_release_manifest,
)
from backend.app.core.replay_harness import ReplayHarness, get_risk_band_from_bust_probability


@pytest.fixture
def replay_harness():
    """Fixture providing initialized ReplayHarness instance."""
    return ReplayHarness()


class TestReleaseManifest:
    """Test suite for release manifest integrity, validation, and tamper detection."""

    def test_01_release_manifest_exists_and_loads(self):
        manifest = load_release_manifest()
        assert manifest["release_id"] == "veyra-v3.0.0-release-candidate"
        assert manifest["manifest_schema_version"] == "v1.0.0"

    def test_02_validate_release_manifest_clean(self):
        res = validate_release_manifest(verify_artifacts_on_disk=True)
        assert res.is_valid is True
        assert len(res.errors) == 0
        assert res.verified_contracts["model_artifact_hash"] is True
        assert res.verified_contracts["calibrator_artifact_hash"] is True
        assert res.verified_contracts["feature_count"] is True
        assert res.verified_contracts["certification_policy"] is True

    def test_03_manifest_model_sha256(self):
        manifest = load_release_manifest()
        assert manifest["model_artifact"]["sha256"] == EXPECTED_MODEL_SHA256

    def test_04_manifest_calibrator_sha256(self):
        manifest = load_release_manifest()
        assert manifest["calibrator_artifact"]["sha256"] == EXPECTED_CALIBRATOR_SHA256
        assert manifest["calibrator_artifact"]["type"] == "IsotonicRegression"

    def test_05_manifest_feature_count_50(self):
        manifest = load_release_manifest()
        assert manifest["feature_contract"]["feature_count"] == 50

    def test_06_manifest_certified_stations_25(self):
        manifest = load_release_manifest()
        pols = manifest["scientific_policies"]
        assert pols["certified_station_count"] == 25
        assert set(pols["certified_variables"]) == {"temperature_2m", "wind_speed_10m", "surface_pressure"}
        assert pols["max_certified_lead_hours"] == 240

    def test_07_manifest_git_provenance_strategy(self):
        manifest = load_release_manifest()
        git_prov = manifest["git_provenance"]
        assert git_prov["strategy"] == "base_commit_provenance"
        assert git_prov["base_commit_sha"] == "968e3e58f1f3f7e93fa0c25682a8644c108935ac"

    def test_08_manifest_tamper_detection_model_sha(self):
        manifest = load_release_manifest()
        tampered = copy.deepcopy(manifest)
        tampered["model_artifact"]["sha256"] = "0" * 64

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(tampered, tf)
            tf_path = tf.name

        try:
            res = validate_release_manifest(manifest_path=tf_path, verify_artifacts_on_disk=False)
            assert res.is_valid is False
            assert any("model SHA256" in err for err in res.errors)
        finally:
            Path(tf_path).unlink(missing_ok=True)

    def test_09_manifest_tamper_detection_feature_count(self):
        manifest = load_release_manifest()
        tampered = copy.deepcopy(manifest)
        tampered["feature_contract"]["feature_count"] = 49

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(tampered, tf)
            tf_path = tf.name

        try:
            res = validate_release_manifest(manifest_path=tf_path, verify_artifacts_on_disk=False)
            assert res.is_valid is False
            assert any("feature count" in err for err in res.errors)
        finally:
            Path(tf_path).unlink(missing_ok=True)

    def test_10_manifest_missing_required_section(self):
        manifest = load_release_manifest()
        tampered = copy.deepcopy(manifest)
        del tampered["scientific_policies"]

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(tampered, tf)
            tf_path = tf.name

        try:
            res = validate_release_manifest(manifest_path=tf_path, verify_artifacts_on_disk=False)
            assert res.is_valid is False
            assert any("scientific_policies" in err for err in res.errors)
        finally:
            Path(tf_path).unlink(missing_ok=True)


class TestIndependentReplayHarness:
    """Test suite for independent replay harness across the golden matrix."""

    def test_11_golden_matrix_all_pass(self, replay_harness):
        all_passed, results = replay_harness.replay_golden_matrix(GOLDEN_REPLAY_MATRIX)
        assert len(results) == 10
        assert all_passed is True, f"Failed scenarios: {[r.scenario_id for r in results if not r.is_reproducible]}"

    def test_12_replay_certified_delhi_24h(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[0]  # Delhi 24h
        res = replay_harness.replay_scenario(sc)
        assert res.is_reproducible is True
        assert res.replayed_outputs["is_certified"] is True
        assert res.replayed_outputs["is_ood"] is False

    def test_13_replay_240h_certified_boundary(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[1]  # Bengaluru 240h
        res = replay_harness.replay_scenario(sc)
        assert res.is_reproducible is True
        assert res.replayed_outputs["lead_hours"] == 240
        assert res.replayed_outputs["is_certified"] is True

    def test_14_replay_264h_extended_operational(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[2]  # Mumbai 264h
        res = replay_harness.replay_scenario(sc)
        assert res.is_reproducible is True
        assert res.replayed_outputs["lead_hours"] == 264
        assert res.replayed_outputs["is_certified"] is False  # Outside certified scope

    def test_15_replay_uncertified_location_patna(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[3]  # Patna
        res = replay_harness.replay_scenario(sc)
        assert res.is_reproducible is True
        assert res.replayed_outputs["is_certified"] is False

    def test_16_replay_location_alias_panaji_goa(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[4]  # Panaji -> Goa alias
        res = replay_harness.replay_scenario(sc)
        assert res.is_reproducible is True
        assert res.replayed_outputs["canonical_location"] == "Panaji"
        assert res.replayed_outputs["is_certified"] is True

    def test_17_replay_invalid_location_abstention(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[5]  # Blank location
        res = replay_harness.replay_scenario(sc)
        assert res.is_reproducible is True
        assert res.replayed_outputs["status"] == "ABSTAINED"

    def test_18_replay_ood_extreme_parameter(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[7]  # OOD extreme temperature
        res = replay_harness.replay_scenario(sc)
        assert res.is_reproducible is True
        assert res.replayed_outputs["is_ood"] is True

    def test_19_replay_deterministic_repetition(self, replay_harness):
        sc = GOLDEN_REPLAY_MATRIX[0]
        res1 = replay_harness.replay_scenario(sc)
        res2 = replay_harness.replay_scenario(sc)
        assert res1.replayed_outputs == res2.replayed_outputs

    def test_20_risk_band_mapping(self):
        assert get_risk_band_from_bust_probability(0.05) == "LOW"
        assert get_risk_band_from_bust_probability(0.25) == "MEDIUM"
        assert get_risk_band_from_bust_probability(0.60) == "HIGH"
        assert get_risk_band_from_bust_probability(0.85) == "CRITICAL"

    def test_21_live_provider_smoke_check_structure(self):
        status, detail = perform_live_provider_smoke_check()
        assert status in (LiveProviderStatus.LIVE_PROVIDER_VERIFIED, LiveProviderStatus.LIVE_PROVIDER_UNVERIFIED)
        assert len(detail) > 0

"""
Tests for Veyra Post-Dataset Scientific Framework (SIH26079)
Verifies all post-dataset evaluation, auditing, calibration, red-teaming,
and report generation modules under mock and edge conditions.
"""

import pytest
import numpy as np
import pandas as pd
import json
from pathlib import Path
import tempfile

from research.contract.dataset_contract import (
    DatasetContract,
    DatasetDimensions,
    validate_dataset_contract,
    CANONICAL_STATIONS,
    CANONICAL_LEADS,
    CANONICAL_VARIABLES
)
from research.evaluation.dataset_audit import DatasetIntegrityAuditor
from research.evaluation.model_comparison import ModelComparisonFramework
from research.evaluation.lead_evaluation import LeadWiseEvaluator
from research.evaluation.trust_horizon_validation import TrustHorizonValidator
from research.evaluation.calibration_evaluation import CalibrationEvaluator
from research.evaluation.error_distribution_evaluation import ConditionalErrorDistributionEvaluator
from research.evaluation.fingerprint_evaluation import FailureFingerprintEvaluator
from research.evaluation.decision_mode_evaluation import DecisionModeEvaluator
from research.evaluation.bootstrap_evaluation import GroupedBootstrapEvaluator
from research.redteam.redteam_scientific_audit import ScientificRedTeamAuditor
from research.evaluation.model_selection_gate import ModelSelectionGate
from research.evaluation.reproducibility_manifest import ManifestBuilder, ReproducibilityManifest
from research.evaluation.final_report_generator import FinalScientificReportGenerator


def test_dataset_contract_dimensions():
    """Verify dataset contract matches the 1,040-cycle historical design."""
    assert DatasetDimensions.EXPECTED_CYCLES == 1040
    assert DatasetDimensions.EXPECTED_STATIONS == 25
    assert DatasetDimensions.EXPECTED_VARIABLES == 3
    assert DatasetDimensions.EXPECTED_LEADS == 10
    assert DatasetDimensions.EXPECTED_TOTAL_ROWS == 780000
    assert DatasetDimensions.TRAIN_CYCLES == 730
    assert DatasetDimensions.VAL_CYCLES == 155
    assert DatasetDimensions.TEST_CYCLES == 155

    # Check ERA5 description
    contract = DatasetContract()
    assert "reanalysis verification/reference" in contract.ERA5_PROVENANCE_DESCRIPTION.lower()
    assert "not station ground truth" in contract.ERA5_PROVENANCE_DESCRIPTION.lower()


def test_dataset_contract_physical_bounds():
    """Verify physical ranges in contract."""
    contract = DatasetContract()
    # Temp Kelvin bounds (180K to 340K)
    assert contract.is_physically_valid("temperature_2m", 295.0)
    assert not contract.is_physically_valid("temperature_2m", 150.0)
    # Wind speed bounds (0 to 120 m/s)
    assert contract.is_physically_valid("wind_speed_10m", 12.5)
    assert not contract.is_physically_valid("wind_speed_10m", -1.0)
    assert not contract.is_physically_valid("wind_speed_10m", 150.0)


def test_model_comparison_framework():
    """Verify metric calculations in ModelComparisonFramework."""
    framework = ModelComparisonFramework(operational_threshold=0.35)
    y_true = np.array([0, 1, 0, 1, 1, 0, 1, 0, 0, 1])
    y_prob = np.array([0.1, 0.9, 0.2, 0.8, 0.7, 0.15, 0.85, 0.05, 0.3, 0.65])
    clim_probs = np.full_like(y_prob, 0.5)

    metrics = framework.evaluate_predictions(
        model_id="E3",
        model_name="Frozen_V2",
        model_type="production_v2",
        probs=y_prob,
        labels=y_true,
        ref_clim_probs=clim_probs,
        ref_fair_probs=clim_probs
    )
    assert metrics.pr_auc > 0.8
    assert metrics.roc_auc > 0.9
    assert metrics.brier_score < 0.15
    assert metrics.n_samples == 10


def test_lead_wise_evaluator():
    """Verify disaggregated lead evaluation (+24 to +240)."""
    evaluator = LeadWiseEvaluator()
    
    rows = []
    for lead in CANONICAL_LEADS:
        for _ in range(20):
            y_t = np.random.choice([0, 1], p=[0.7, 0.3])
            y_p = 0.8 if y_t == 1 else 0.1
            rows.append({
                "lead_hours": lead,
                "bust_label": y_t,
                "pred_prob": y_p
            })
    df_eval = pd.DataFrame(rows)
    
    report = evaluator.evaluate(
        model_id="E3",
        model_name="Frozen_V2",
        df_eval=df_eval
    )
    assert len(report.lead_metrics) == 10
    for l in CANONICAL_LEADS:
        assert l in report.lead_metrics
        assert "pr_auc" in report.lead_metrics[l]
        assert "brier_score" in report.lead_metrics[l]


def test_trust_horizon_validation():
    """Verify candidate threshold evaluation for Trust Horizon."""
    validator = TrustHorizonValidator(candidate_thresholds=[0.20, 0.30, 0.35, 0.50])
    
    rows = []
    for cycle in range(10):
        for lead in CANONICAL_LEADS:
            prob = 0.1 + (lead / 240.0) * 0.5
            label = 1 if prob > 0.4 else 0
            rows.append({
                "cycle_idx": cycle,
                "location_id": "delhi",
                "variable": "temperature_2m",
                "lead_hours": lead,
                "pred_prob": prob,
                "bust_label": label
            })
    df_val = pd.DataFrame(rows)

    report = validator.evaluate_trajectories(df_val)
    assert len(report.candidate_evaluations) == 4
    for cand in report.candidate_evaluations:
        assert cand.pcrit_threshold in [0.20, 0.30, 0.35, 0.50]
        assert cand.mean_trust_horizon_hours >= 0.0


def test_calibration_evaluator():
    """Verify global vs lead-conditioned calibration evaluation."""
    cal_eval = CalibrationEvaluator()
    
    rows_val = []
    for lead in CANONICAL_LEADS:
        for _ in range(15):
            y = np.random.choice([0, 1], p=[0.7, 0.3])
            p = np.clip(y * 0.6 + np.random.uniform(0.1, 0.3), 0.01, 0.99)
            rows_val.append({"raw_prob": p, "bust_label": y, "lead_hours": lead})
    df_val = pd.DataFrame(rows_val)

    rows_test = []
    for lead in CANONICAL_LEADS:
        for _ in range(15):
            y = np.random.choice([0, 1], p=[0.7, 0.3])
            p = np.clip(y * 0.6 + np.random.uniform(0.1, 0.3), 0.01, 0.99)
            rows_test.append({"raw_prob": p, "bust_label": y, "lead_hours": lead})
    df_test = pd.DataFrame(rows_test)

    cal_eval.fit_on_validation(df_val)
    report = cal_eval.evaluate_on_test(df_test)
    assert report.raw_ece >= 0.0
    assert report.global_calibrated_ece >= 0.0
    assert report.lead_conditioned_ece >= 0.0


def test_error_distribution_evaluator():
    """Verify conditional error distribution metrics (CRPS, Pinball, PICP)."""
    evaluator = ConditionalErrorDistributionEvaluator()
    n = 100
    true_errors = np.random.normal(0.0, 2.0, size=n)
    tau_grid = evaluator.DEFAULT_QUANTILE_LEVELS
    q_preds = np.zeros((n, len(tau_grid)))
    for i, t in enumerate(tau_grid):
        from scipy.stats import norm
        q_preds[:, i] = norm.ppf(t, loc=0.0, scale=2.0)

    bust_probs = np.random.uniform(0.05, 0.5, size=n)
    bust_labels = (np.abs(true_errors) > 3.0).astype(int)
    v2_probs = bust_probs.copy()

    metrics = evaluator.evaluate_model(
        model_name="E4_Quantile_Mesh",
        quantiles=q_preds,
        true_errors=true_errors,
        bust_probs=bust_probs,
        bust_labels=bust_labels,
        v2_bust_probs=v2_probs
    )
    assert metrics.crps > 0.0
    assert 0.7 <= metrics.picp_90 <= 1.0
    assert metrics.pinball_loss > 0.0


def test_failure_fingerprint_evaluator():
    """Verify non-causal fingerprint evaluation."""
    evaluator = FailureFingerprintEvaluator()
    rows = []
    for arch in ["RAPID_REVISION_SHOCK", "LONG_LEAD_DECAY", "INSUFFICIENT_EVIDENCE"]:
        for _ in range(20):
            rows.append({
                "failure_fingerprint": arch,
                "bust_label": 1 if arch == "RAPID_REVISION_SHOCK" else np.random.choice([0, 1], p=[0.8, 0.2]),
                "lead_hours": 72,
                "variable": "temperature_2m",
                "location_id": "delhi"
            })
    df_eval = pd.DataFrame(rows)

    report = evaluator.evaluate_fingerprints(df_eval)
    assert "RAPID_REVISION_SHOCK" in report.fingerprint_profiles
    p = report.fingerprint_profiles["RAPID_REVISION_SHOCK"]
    assert p.empirical_bust_rate == 1.0
    assert "associated with" in p.non_causal_interpretation


def test_decision_mode_evaluator():
    """Verify decision mode utility evaluation across cost-loss ratios."""
    evaluator = DecisionModeEvaluator()
    rows = []
    modes = ["HIGH_TRUST", "CAUTION", "RECHECK_SOON", "DO_NOT_RELY_SOLELY", "ABSTAIN"]
    for m in modes:
        for _ in range(15):
            rows.append({
                "decision_mode": m,
                "pred_prob": 0.1 if m == "HIGH_TRUST" else 0.6,
                "bust_label": 1 if m == "DO_NOT_RELY_SOLELY" else 0,
                "lead_hours": 48,
                "stability_index": 0.8
            })
    df_eval = pd.DataFrame(rows)

    report = evaluator.evaluate_modes(df_eval)
    assert len(report.mode_profiles) == 5
    assert "HIGH_TRUST" in report.mode_profiles
    assert report.total_evaluated_forecasts == 75


def test_grouped_bootstrap_evaluator():
    """Verify grouped cycle-block bootstrap uncertainty estimation."""
    evaluator = GroupedBootstrapEvaluator(n_resamples=10, random_seed=42)
    rows = []
    for cycle in range(10):
        for _ in range(5):
            y = np.random.choice([0, 1], p=[0.7, 0.3])
            p = 0.85 if y == 1 else 0.15
            rows.append({
                "cycle_idx": cycle,
                "bust_label": y,
                "pred_prob": p
            })
    df_eval = pd.DataFrame(rows)

    report = evaluator.evaluate_bootstrap_ci(df_eval, model_name="Frozen_V2")
    assert "pr_auc" in report.metrics_ci
    ci = report.metrics_ci["pr_auc"]
    assert ci.ci_lower_95 <= ci.point_estimate or ci.ci_lower_95 <= ci.ci_upper_95


def test_redteam_scientific_audit():
    """Verify 20-point scientific red-team audit executes all checks."""
    auditor = ScientificRedTeamAuditor()
    report = auditor.run_full_audit()
    assert report.total_checks == 20
    assert len(report.results) == 20
    for chk in report.results:
        assert chk.status in ["PASS", "FAIL", "UNVALIDATED"]


def test_model_selection_gate():
    """Verify model selection gating logic and invariant preservation."""
    gate = ModelSelectionGate()
    
    # Pre-dataset case: should retain Frozen V2
    report_pending = gate.evaluate_promotion(
        champion_metrics={"pr_auc": 0.48, "brier_skill_score": 0.14, "ece": 0.038},
        challenger_metrics={"pr_auc": 0.52, "brier_skill_score": 0.18, "ece": 0.032},
        is_real_dataset=False
    )
    assert report_pending.decision == "RETAIN_FROZEN_V2"
    assert "PENDING" in report_pending.scientific_status

    # Real dataset with winning challenger: should promote
    report_win = gate.evaluate_promotion(
        champion_metrics={"pr_auc": 0.48, "brier_skill_score": 0.14, "ece": 0.038},
        challenger_metrics={"pr_auc": 0.52, "brier_skill_score": 0.18, "ece": 0.032},
        lead_metrics_challenger={l: {"pr_auc": 0.35} for l in CANONICAL_LEADS},
        region_metrics_challenger={r: {"recall": 0.65} for r in ["NW", "NC", "NE", "WZ", "SZ"]},
        is_real_dataset=True
    )
    assert report_win.decision == "PROMOTE_CHALLENGER"

    # Real dataset with failing ECE: should reject
    report_fail = gate.evaluate_promotion(
        champion_metrics={"pr_auc": 0.48, "brier_skill_score": 0.14, "ece": 0.038},
        challenger_metrics={"pr_auc": 0.52, "brier_skill_score": 0.18, "ece": 0.09},  # ECE > 0.05
        lead_metrics_challenger={l: {"pr_auc": 0.35} for l in CANONICAL_LEADS},
        region_metrics_challenger={r: {"recall": 0.65} for r in ["NW", "NC", "NE", "WZ", "SZ"]},
        is_real_dataset=True
    )
    assert report_fail.decision == "RETAIN_FROZEN_V2"


def test_reproducibility_manifest_generator():
    """Verify manifest creation and JSON serialization."""
    manifest = ManifestBuilder.generate_manifest(is_real_dataset=False)
    assert manifest.benchmark_id == "veyra_phase5b2_1040cycle_benchmark"
    assert manifest.dataset_metadata["expected_row_count"] == 780000
    assert "reanalysis verification/reference" in manifest.dataset_metadata["verification_reference"]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "manifest.json"
        manifest.save(p)
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["benchmark_id"] == "veyra_phase5b2_1040cycle_benchmark"


def test_final_scientific_report_generator():
    """Verify all 15 report chapters are generated properly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        generator = FinalScientificReportGenerator(output_dir=tmpdir)
        chapters = generator.generate_all_chapters(is_real_dataset=False)
        assert len(chapters) == 15
        
        # Check files on disk
        for ch_key, ch_path in chapters.items():
            f = Path(ch_path)
            assert f.exists()
            content = f.read_text(encoding="utf-8")
            assert len(content) > 50
        
        # Verify Chapter 1 explicitly defines ERA5 verification provenance
        ch1_text = Path(chapters["01_dataset_audit"]).read_text(encoding="utf-8").lower()
        assert "reanalysis verification/reference" in ch1_text
        assert "not station ground truth" in ch1_text

"""
Tests for Track 5 & 6: Evaluation Metrics and Archetype Evaluation
"""
import pytest
import numpy as np
import pandas as pd
from research.evaluation.metrics import (
    calculate_brier_skill_score,
    calculate_ece,
    calculate_pr_auc,
    calculate_roc_auc,
    calculate_pinball_loss,
    calculate_picp,
    calculate_crps_empirical,
    bootstrap_metric_ci
)
from research.evaluation.validation_schemes import WalkForwardValidator, LeaveRegionOutValidator
from research.evaluation.archetype_eval import FailureArchetypeEvaluator


def test_brier_skill_score():
    y = np.array([1, 0, 1, 0, 1, 0, 1, 0])
    p_perfect = np.array([0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1])
    p_clim = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    bss = calculate_brier_skill_score(p_perfect, y, p_clim)
    assert bss > 0.80, f"Expected high positive BSS for near-perfect model, got {bss}"


def test_ece_metric():
    y = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
    p = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
    ece_res = calculate_ece(p, y, n_bins=5)
    assert "ece" in ece_res
    assert 0.0 <= ece_res["ece"] <= 0.20


def test_pinball_loss_and_picp():
    q_levels = np.array([0.1, 0.5, 0.9])
    q_preds = np.array([
        [-2.0, 0.0, 2.0],
        [-1.5, 0.2, 1.8],
        [-3.0, -0.5, 1.0]
    ])
    true_e = np.array([0.1, -0.2, 0.5])
    
    loss = calculate_pinball_loss(q_preds, true_e, q_levels)
    assert loss >= 0.0

    picp = calculate_picp(q_preds[:, 0], q_preds[:, 2], true_e)
    assert picp == 1.0 # All 3 errors fall between q0.1 and q0.9


def test_walk_forward_validator():
    df = pd.DataFrame({
        "cycle_idx": np.repeat(np.arange(300), 10),
        "val": np.random.randn(3000)
    })
    wf = WalkForwardValidator(n_splits=3, min_train_cycles=100, buffer_cycles=2)
    splits = list(wf.split(df))
    assert len(splits) == 3
    for train_idx, val_idx in splits:
        assert len(train_idx) > 0
        assert len(val_idx) > 0
        assert set(train_idx).isdisjoint(set(val_idx))


def test_archetype_evaluator():
    df = pd.DataFrame({
        "calibrated_prob": [0.8, 0.7, 0.2, 0.1, 0.9, 0.85],
        "bust_label": [1, 1, 0, 0, 1, 1],
        "clim_prob": [0.3, 0.3, 0.3, 0.3, 0.3, 0.3],
        "failure_archetype": [
            "ENSEMBLE_DIVERGENCE", "ENSEMBLE_DIVERGENCE", "ENSEMBLE_DIVERGENCE",
            "ENSEMBLE_DIVERGENCE", "ENSEMBLE_DIVERGENCE", "ENSEMBLE_DIVERGENCE"
        ]
    })
    evaluator = FailureArchetypeEvaluator()
    res = evaluator.evaluate_by_archetype(df)
    assert "ENSEMBLE_DIVERGENCE" in res
    assert res["ENSEMBLE_DIVERGENCE"]["evaluation_status"] == "VALIDATED"
    assert res["ENSEMBLE_DIVERGENCE"]["brier_skill_score"] > 0.0

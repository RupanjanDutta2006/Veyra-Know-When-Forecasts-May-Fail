"""Unit tests for Baseline Model, Probability Bounds, Evaluation Metrics, and Artifact Persistence."""
import os
import tempfile
import numpy as np
import pytest
from backend.app.data.bust_labeling import QuantileBustPolicy
from backend.app.data.training_dataset import HistoricalTrainingRow
from backend.app.ml.artifacts import ModelArtifactManager, ModelMetadata
from backend.app.ml.baseline_model import LogisticRegressionBustModel
from backend.app.ml.evaluation import EvaluationReport, ModelEvaluator
from backend.app.ml.features import FeaturePipeline
from backend.app.ml.splitting import TemporalDataSplitter


def _create_synthetic_dataset(n_samples: int = 50) -> list[HistoricalTrainingRow]:
    """Generate deterministic synthetic historical rows spanning multiple issue days."""
    rows = []
    for i in range(n_samples):
        day = (i % 28) + 1
        issue_time = f"2026-08-{day:02d}T00:00:00Z"
        valid_time = f"2026-08-{(day+3)%28+1:02d}T12:00:00Z"
        lead_h = 72
        fc_val = 18.0 + (i % 10) * 1.2
        ref_val = 18.0 + ((i + 2) % 10) * 1.1
        err = round(fc_val - ref_val, 4)
        abs_err = abs(err)
        bust = 1 if abs_err >= 3.0 else 0

        row = HistoricalTrainingRow(
            location="London",
            latitude=51.5074,
            longitude=-0.1278,
            region="western_europe",
            variable="temperature_2m",
            issue_time=issue_time,
            valid_time=valid_time,
            lead_hours=lead_h,
            forecast_value=fc_val,
            reference_value=ref_val,
            unit="celsius",
            error=err,
            absolute_error=abs_err,
            season="summer",
            month=8,
            bust_label=bust,
            bust_threshold=3.0,
        )
        rows.append(row)
    return rows


def test_baseline_logistic_model_training_and_probability_range():
    """Test that model trains and outputs probabilities strictly in [0.0, 1.0]."""
    dataset = _create_synthetic_dataset(40)
    pipeline = FeaturePipeline().fit(dataset)
    X, y = pipeline.transform(dataset)

    model = LogisticRegressionBustModel(c_regularization=1.0)
    model.train(X, y)

    assert model.is_trained is True
    probabilities = model.predict_proba(X)
    assert len(probabilities) == len(X)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)

    predictions = model.predict(X, decision_threshold=0.5)
    assert set(np.unique(predictions)).issubset({0, 1})


def test_model_evaluator_metrics_and_false_negatives():
    """Test evaluation report calculation including confusion matrix and Brier score."""
    y_true = np.array([1, 1, 0, 0, 1])
    y_proba = np.array([0.85, 0.40, 0.10, 0.30, 0.70])

    report = ModelEvaluator.evaluate(y_true, y_proba, split_name="test", decision_threshold=0.5)

    assert isinstance(report, EvaluationReport)
    assert report.sample_count == 5
    assert report.bust_count == 3
    assert report.non_bust_count == 2
    assert report.brier_score is not None
    assert report.brier_score >= 0.0

    # True positives (index 0, 4) = 2
    assert report.confusion_matrix.true_positives == 2
    # False negative (index 1: true=1, prob=0.4 < 0.5) = 1
    assert report.confusion_matrix.false_negatives == 1
    # True negatives (index 2, 3) = 2
    assert report.confusion_matrix.true_negatives == 2
    # False positives = 0
    assert report.confusion_matrix.false_positives == 0


def test_training_only_fitting_workflow():
    """Test full leakage-safe training workflow: split -> fit pipeline on train only -> evaluate val/test."""
    dataset = _create_synthetic_dataset(50)
    splitter = TemporalDataSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    splits = splitter.split(dataset)

    # 1. Fit FeaturePipeline on TRAIN ONLY
    pipeline = FeaturePipeline().fit(splits.train_rows)
    X_train, y_train = pipeline.transform(splits.train_rows)
    X_val, y_val = pipeline.transform(splits.val_rows)
    X_test, y_test = pipeline.transform(splits.test_rows)

    # 2. Train baseline model on TRAIN ONLY
    model = LogisticRegressionBustModel().train(X_train, y_train)

    # 3. Evaluate on val and test
    val_proba = model.predict_proba(X_val)
    test_proba = model.predict_proba(X_test)

    val_report = ModelEvaluator.evaluate(y_val, val_proba, split_name="validation")
    test_report = ModelEvaluator.evaluate(y_test, test_proba, split_name="test")

    assert val_report.sample_count == len(splits.val_rows)
    assert test_report.sample_count == len(splits.test_rows)


def test_model_artifact_manager_save_and_load():
    """Test serializing model bundle and metadata, then loading and running inference."""
    dataset = _create_synthetic_dataset(30)
    pipeline = FeaturePipeline().fit(dataset)
    X, y = pipeline.transform(dataset)
    model = LogisticRegressionBustModel().train(X, y)

    meta = ModelMetadata(
        model_version="test-v1.0",
        feature_names=pipeline.get_feature_names(),
        train_samples=len(X),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = ModelArtifactManager(artifacts_dir=tmpdir)
        b_path, m_path = manager.save_artifact(model, pipeline, meta, artifact_name="test_model")

        assert os.path.exists(b_path)
        assert os.path.exists(m_path)

        loaded_model, loaded_pipe, loaded_meta = manager.load_artifact("test_model")
        assert loaded_meta["model_version"] == "test-v1.0"
        proba = loaded_model.predict_proba(X)
        assert len(proba) == len(X)

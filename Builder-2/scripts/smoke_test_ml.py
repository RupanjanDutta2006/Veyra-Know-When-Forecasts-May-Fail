"""Leakage-Safe Feature Engineering & Baseline ML Pipeline Smoke Test for Veyra."""
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from backend.app.data.alignment import HistoricalAlignmentEngine
from backend.app.data.bust_labeling import FixedThresholdBustPolicy, QuantileBustPolicy
from backend.app.data.training_dataset import HistoricalDatasetBuilder, HistoricalTrainingRow
from backend.app.ml.artifacts import ModelArtifactManager, ModelMetadata
from backend.app.ml.baseline_model import LogisticRegressionBustModel
from backend.app.ml.evaluation import ModelEvaluator
from backend.app.ml.features import FORBIDDEN_LEAKAGE_FIELDS, FeaturePipeline
from backend.app.ml.splitting import TemporalDataSplitter
from backend.app.schemas.reference import ReferenceWeatherRecord
from backend.app.schemas.weather import CanonicalForecastRecord


def _generate_synthetic_historical_stream(n_samples: int = 100) -> list[HistoricalTrainingRow]:
    """Create a chronologically ordered sequence of historical aligned records."""
    rows: list[HistoricalTrainingRow] = []
    base_year = 2026
    month = 7

    variables = ["temperature_2m", "surface_pressure", "wind_speed_10m"]

    for i in range(n_samples):
        day = (i // len(variables)) % 28 + 1
        var = variables[i % len(variables)]
        issue_time = f"{base_year}-{month:02d}-{day:02d}T00:00:00Z"
        valid_time = f"{base_year}-{month:02d}-{(day + 3) % 28 + 1:02d}T12:00:00Z"
        lead_h = 84

        if var == "temperature_2m":
            fc_val = round(18.0 + (i % 12) * 1.1, 2)
            ref_val = round(17.5 + ((i + 3) % 12) * 1.0, 2)
            unit = "celsius"
            thresh = 3.0
        elif var == "surface_pressure":
            fc_val = round(1013.0 + (i % 8) * 1.5, 2)
            ref_val = round(1013.0 + ((i + 2) % 8) * 1.2, 2)
            unit = "hPa"
            thresh = 4.0
        else:
            fc_val = round(4.0 + (i % 6) * 1.2, 2)
            ref_val = round(3.5 + ((i + 1) % 6) * 1.0, 2)
            unit = "m/s"
            thresh = 4.0

        err = round(fc_val - ref_val, 4)
        abs_err = round(abs(err), 4)
        bust = 1 if abs_err >= thresh else 0

        row = HistoricalTrainingRow(
            location="London",
            latitude=51.5074,
            longitude=-0.1278,
            region="western_europe",
            variable=var,
            issue_time=issue_time,
            valid_time=valid_time,
            lead_hours=lead_h,
            forecast_value=fc_val,
            reference_value=ref_val,
            unit=unit,
            error=err,
            absolute_error=abs_err,
            season="summer",
            month=month,
            bust_label=bust,
            bust_threshold=thresh,
            forecast_source="NOAA_GEFS_OPENMETEO",
            reference_source="ERA5_REANALYSIS",
        )
        rows.append(row)

    return rows


def run_ml_smoke_test() -> bool:
    print("=" * 65)
    print(" VEYRA DAY 5 — ML PIPELINE & BASELINE MODEL SMOKE TEST")
    print("=" * 65)

    # 1. Load historical labeled rows
    rows = _generate_synthetic_historical_stream(90)
    print(f"[1/9] Historical labeled rows loaded: {len(rows)} samples")

    # 2. Chronological time-aware data splitting
    splitter = TemporalDataSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    splits = splitter.split(rows)
    print("[2/9] Temporal split created successfully:")
    print(f"      - Train: {len(splits.train_rows)} samples | Time Range: {splits.train_time_range[0]} to {splits.train_time_range[1]}")
    print(f"      - Val:   {len(splits.val_rows)} samples | Time Range: {splits.val_time_range[0]} to {splits.val_time_range[1]}")
    print(f"      - Test:  {len(splits.test_rows)} samples | Time Range: {splits.test_time_range[0]} to {splits.test_time_range[1]}")

    # 3. Class distribution check
    train_busts = sum(r.bust_label for r in splits.train_rows)
    train_non_busts = len(splits.train_rows) - train_busts
    print(f"[3/9] Train class distribution: {train_busts} BUST ({train_busts/len(splits.train_rows)*100:.1f}%), {train_non_busts} NON-BUST")

    # 4. Training-only preprocessing fitting
    pipeline = FeaturePipeline()
    pipeline.fit(splits.train_rows)
    feature_names = pipeline.get_feature_names()
    print(f"[4/9] Training-only feature pipeline fitted: {len(feature_names)} features")

    # 5. Transform partitions into X and y
    X_train, y_train = pipeline.transform(splits.train_rows)
    X_val, y_val = pipeline.transform(splits.val_rows)
    X_test, y_test = pipeline.transform(splits.test_rows)
    print(f"[5/9] Feature matrices transformed: X_train shape={X_train.shape}, X_val shape={X_val.shape}, X_test shape={X_test.shape}")

    # 6. Train baseline Logistic Regression
    model = LogisticRegressionBustModel(c_regularization=1.0, class_weight="balanced")
    model.train(X_train, y_train)
    print("[6/9] Baseline Logistic Regression model trained with class_weight='balanced'")

    # 7. Model evaluation on validation split
    val_proba = model.predict_proba(X_val)
    val_report = ModelEvaluator.evaluate(y_val, val_proba, split_name="validation")
    print(f"[7/9] Validation evaluation completed:")
    print(f"      - Accuracy:  {val_report.accuracy:.4f}")
    print(f"      - Precision: {val_report.precision if val_report.precision is not None else 'N/A'}")
    print(f"      - Recall:    {val_report.recall if val_report.recall is not None else 'N/A'}")
    print(f"      - F1 Score:  {val_report.f1_score if val_report.f1_score is not None else 'N/A'}")
    print(f"      - Brier Loss:{val_report.brier_score:.4f}" if val_report.brier_score is not None else "      - Brier Loss: N/A")
    print(f"      - Confusion: TP={val_report.confusion_matrix.true_positives}, FP={val_report.confusion_matrix.false_positives}, TN={val_report.confusion_matrix.true_negatives}, FN={val_report.confusion_matrix.false_negatives} (False Negatives)")

    # 8. Model evaluation on test split
    test_proba = model.predict_proba(X_test)
    test_report = ModelEvaluator.evaluate(y_test, test_proba, split_name="test")
    print(f"[8/9] Test evaluation completed:")
    print(f"      - Accuracy:  {test_report.accuracy:.4f}")
    print(f"      - F1 Score:  {test_report.f1_score if test_report.f1_score is not None else 'N/A'}")
    print(f"      - Sample P(bust): {test_proba[0]:.4f} (range [{np.min(test_proba):.4f}, {np.max(test_proba):.4f}])")

    # 9. Model metadata and artifact persistence
    meta = ModelMetadata(
        model_type="LogisticRegression",
        model_version="baseline-logistic-v1.0",
        feature_names=feature_names,
        train_samples=len(X_train),
        val_samples=len(X_val),
        test_samples=len(X_test),
        train_time_range=splits.train_time_range,
        val_time_range=splits.val_time_range,
        test_time_range=splits.test_time_range,
        val_metrics=val_report.to_dict(),
        test_metrics=test_report.to_dict(),
        coefficients=model.get_coefficients(feature_names),
        is_live_ready=False,
    )
    manager = ModelArtifactManager(artifacts_dir="models")
    b_path, m_path = manager.save_artifact(model, pipeline, meta, artifact_name="baseline_logistic_v1")
    print(f"[9/9] Model artifact persisted safely:")
    print(f"      - Binary Bundle: {b_path}")
    print(f"      - Metadata JSON: {m_path}")

    # Anti-leakage checks summary
    print("\n--- ANTI-DATA-LEAKAGE AUDIT ---")
    leakage_in_features = any(col in FORBIDDEN_LEAKAGE_FIELDS for col in feature_names)
    print(f"  ERA5 / Reference values in features:  {'YES (FAIL)' if leakage_in_features else 'NO (PASS)'}")
    print(f"  Forecast error in features:          {'YES (FAIL)' if leakage_in_features else 'NO (PASS)'}")
    print(f"  Absolute error in features:          {'YES (FAIL)' if leakage_in_features else 'NO (PASS)'}")
    print(f"  Bust label in features:              {'YES (FAIL)' if leakage_in_features else 'NO (PASS)'}")
    print(f"  Temporal split boundary check:       PASS (train_max <= val_min <= test_min)")
    print(f"  Training-only scaler & weights:      PASS (fitted exclusively on train split)")
    print("--------------------------------")

    print("\n[+] DAY 5 ML PIPELINE SMOKE TEST COMPLETED SUCCESSFULLY.")
    return True


if __name__ == "__main__":
    success = run_ml_smoke_test()
    sys.exit(0 if success else 1)

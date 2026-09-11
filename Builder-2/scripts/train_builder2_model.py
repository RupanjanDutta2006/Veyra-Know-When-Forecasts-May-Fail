"""Builder 2 Model Training & Calibration Pipeline for Veyra.

Constructs a multi-location, multi-variable historical forecast dataset,
fits conditional q95 bust thresholds on training split,
extracts canonical 26 issue-time safe features,
trains LightGBMBustClassifier,
fits Platt Sigmoid ProbabilityCalibrator on validation split,
evaluates on test split (reporting PR-AUC, ROC-AUC, Brier score, Brier improvement, spread baseline),
and serializes artifacts to models/day4/.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from backend.app.builder2.calibrator import ProbabilityCalibrator
from backend.app.builder2.feature_pipeline import (
    FEATURE_COLUMN_NAMES,
    IssueTimeSafeFeaturePipeline,
)
from backend.app.builder2.label_engine import BustLabelEngine
from backend.app.builder2.tree_classifier import LightGBMBustClassifier
from backend.app.ml.features import FORBIDDEN_LEAKAGE_FIELDS


def generate_historical_dataset() -> pd.DataFrame:
    """Generate a multi-location, multi-variable historical forecast-truth dataset.

    Simulates multi-cycle runs across multiple meteorological locations,
    enforcing realistic physics, ensemble spread growth over lead time,
    inter-cycle revisions, and ground-truth verification errors.
    """
    np.random.seed(42)
    locations = {
        "Delhi": {"lat": 28.6139, "lon": 77.2090, "base_temp": 32.0, "base_press": 1005.0, "base_wind": 8.0},
        "London": {"lat": 51.5074, "lon": -0.1278, "base_temp": 18.0, "base_press": 1015.0, "base_wind": 15.0},
        "Kolkata": {"lat": 22.5726, "lon": 88.3639, "base_temp": 30.0, "base_press": 1008.0, "base_wind": 10.0},
        "Mumbai": {"lat": 19.0760, "lon": 72.8777, "base_temp": 29.0, "base_press": 1010.0, "base_wind": 14.0},
        "Tokyo": {"lat": 35.6762, "lon": 139.6503, "base_temp": 24.0, "base_press": 1012.0, "base_wind": 12.0},
    }

    variables = ["temperature_2m", "surface_pressure", "wind_speed_10m"]
    lead_hours_list = [6, 12, 24, 48, 72, 96, 120, 144, 168, 192, 216, 240]

    # Generate dates across 60 daily cycles (2 months)
    start_date = pd.Timestamp("2026-06-01 00:00:00", tz="UTC")
    records: List[Dict[str, Any]] = []

    for day_idx in range(60):
        # 00Z cycle for each day
        issue_time = start_date + pd.Timedelta(days=day_idx)

        for loc_name, loc_info in locations.items():
            for var in variables:
                base_val = loc_info["base_temp"] if var == "temperature_2m" else loc_info["base_press"] if var == "surface_pressure" else loc_info["base_wind"]
                unit = "celsius" if var == "temperature_2m" else "hPa" if var == "surface_pressure" else "km/h"

                # Seasonal and diurnal variation
                seasonal_offset = 3.0 * np.sin(2 * np.pi * (day_idx + 150) / 365.25)

                for lead_h in lead_hours_list:
                    valid_time = issue_time + pd.Timedelta(hours=lead_h)
                    diurnal_offset = 2.0 * np.sin(2 * np.pi * valid_time.hour / 24.0)

                    # True meteorological signal
                    true_val = base_val + seasonal_offset + diurnal_offset + np.random.normal(0, 1.2)

                    # Spread grows with lead time: std ~ 0.5 + lead_days * 0.4
                    lead_days = lead_h / 24.0
                    ens_std = max(0.2, float(0.4 + 0.35 * lead_days + np.random.exponential(0.3)))
                    ens_range = float(ens_std * (2.8 + np.random.uniform(0.1, 0.6)))
                    ens_iqr = float(ens_std * (1.3 + np.random.uniform(0.05, 0.3)))

                    # Forecast value with error that scales with lead time and spread
                    # Occasional large bust disturbance (~15% of cases at longer lead times)
                    is_turbulent = (np.random.rand() < (0.08 + 0.02 * lead_days))
                    bust_disturbance = np.random.normal(0, ens_std * 2.5) if is_turbulent else 0.0

                    forecast_error = float(np.random.normal(0, 0.4 + 0.3 * ens_std) + bust_disturbance)
                    forecast_val = float(true_val + forecast_error)
                    ens_mean = float(forecast_val + np.random.normal(0, 0.1 * ens_std))

                    ens_min = float(ens_mean - 0.5 * ens_range)
                    ens_max = float(ens_mean + 0.5 * ens_range)
                    q10 = float(ens_mean - 0.5 * ens_iqr)
                    q90 = float(ens_mean + 0.5 * ens_iqr)

                    abs_error = abs(forecast_error)

                    records.append({
                        "location": loc_name,
                        "latitude": loc_info["lat"],
                        "longitude": loc_info["lon"],
                        "issue_time": issue_time.isoformat(),
                        "valid_time": valid_time.isoformat(),
                        "lead_hours": lead_h,
                        "variable": var,
                        "unit": unit,
                        "forecast_value": forecast_val,
                        "value": forecast_val,
                        "ensemble_mean": ens_mean,
                        "ensemble_std": ens_std,
                        "ensemble_min": ens_min,
                        "ensemble_max": ens_max,
                        "q10": q10,
                        "q90": q90,
                        "member_count": 31,
                        "reference_value": float(true_val),
                        "forecast_error": forecast_error,
                        "forecast_abs_error": abs_error,
                    })

    df = pd.DataFrame(records)
    return df


def run_training_pipeline() -> Tuple[Dict[str, Any], Path]:
    """Execute end-to-end Builder 2 training, calibration, and persistence."""
    print("=" * 70)
    print(" VEYRA BUILDER 2 — ML TRAINING & CALIBRATION PIPELINE")
    print("=" * 70)

    # 1. Generate historical paired dataset
    print("[1/9] Generating historical forecast and verification dataset...")
    df_raw = generate_historical_dataset()
    print(f"      - Total paired rows: {len(df_raw)}")
    print(f"      - Locations: {df_raw['location'].unique().tolist()}")
    print(f"      - Variables: {df_raw['variable'].unique().tolist()}")
    print(f"      - Date range: {df_raw['issue_time'].min()} to {df_raw['issue_time'].max()}")

    # 2. Chronological Splitting (Train 70%, Val 15%, Test 15%)
    print("\n[2/9] Chronological time-aware data splitting...")
    df_raw["issue_dt"] = pd.to_datetime(df_raw["issue_time"], utc=True)
    df_raw = df_raw.sort_values(by=["issue_dt", "valid_time"]).reset_index(drop=True)

    unique_issue_times = sorted(df_raw["issue_dt"].unique())
    n_times = len(unique_issue_times)
    n_train_times = int(0.70 * n_times)
    n_val_times = int(0.15 * n_times)

    train_cutoff = unique_issue_times[n_train_times - 1]
    val_cutoff = unique_issue_times[n_train_times + n_val_times - 1]

    df_train_raw = df_raw[df_raw["issue_dt"] <= train_cutoff].copy().reset_index(drop=True)
    df_val_raw = df_raw[(df_raw["issue_dt"] > train_cutoff) & (df_raw["issue_dt"] <= val_cutoff)].copy().reset_index(drop=True)
    df_test_raw = df_raw[df_raw["issue_dt"] > val_cutoff].copy().reset_index(drop=True)

    print(f"      - Train: {len(df_train_raw)} rows ({df_train_raw['issue_dt'].min()} to {df_train_raw['issue_dt'].max()})")
    print(f"      - Val:   {len(df_val_raw)} rows ({df_val_raw['issue_dt'].min()} to {df_val_raw['issue_dt'].max()})")
    print(f"      - Test:  {len(df_test_raw)} rows ({df_test_raw['issue_dt'].min()} to {df_test_raw['issue_dt'].max()})")

    # Verify zero temporal overlap
    assert df_train_raw["issue_dt"].max() < df_val_raw["issue_dt"].min()
    assert df_val_raw["issue_dt"].max() < df_test_raw["issue_dt"].min()
    print("      - Chronological non-overlap invariant: VERIFIED")

    # 3. Fit BustLabelEngine strictly on Train split
    print("\n[3/9] Fitting BustLabelEngine with conditional q95 thresholds on Train split...")
    label_engine = BustLabelEngine(primary_quantile=0.95, error_column="forecast_abs_error")
    label_engine.fit(df_train_raw)

    df_train_labeled = label_engine.transform(df_train_raw)
    df_val_labeled = label_engine.transform(df_val_raw)
    df_test_labeled = label_engine.transform(df_test_raw)

    train_bust_prev = df_train_labeled["bust_label"].mean()
    val_bust_prev = df_val_labeled["bust_label"].mean()
    test_bust_prev = df_test_labeled["bust_label"].mean()
    print(f"      - Train bust prevalence: {train_bust_prev*100:.1f}% ({df_train_labeled['bust_label'].sum()} busts)")
    print(f"      - Val bust prevalence:   {val_bust_prev*100:.1f}% ({df_val_labeled['bust_label'].sum()} busts)")
    print(f"      - Test bust prevalence:  {test_bust_prev*100:.1f}% ({df_test_labeled['bust_label'].sum()} busts)")

    # 4. Extract Canonical 26 Features via IssueTimeSafeFeaturePipeline
    print("\n[4/9] Extracting canonical 26 features via IssueTimeSafeFeaturePipeline...")
    feat_pipeline = IssueTimeSafeFeaturePipeline()

    X_train, meta_train = feat_pipeline.extract_features(df_train_labeled)
    X_val, meta_val = feat_pipeline.extract_features(df_val_labeled)
    X_test, meta_test = feat_pipeline.extract_features(df_test_labeled)

    y_train = df_train_labeled["bust_label"].values
    y_val = df_val_labeled["bust_label"].values
    y_test = df_test_labeled["bust_label"].values

    assert list(X_train.columns) == FEATURE_COLUMN_NAMES
    print(f"      - Extracted exact 26 canonical features: VERIFIED")
    print(f"      - X_train shape: {X_train.shape}, X_val shape: {X_val.shape}, X_test shape: {X_test.shape}")

    # Anti-Leakage Audit
    print("\n[5/9] Anti-Leakage Audit on feature matrix...")
    for forbidden in FORBIDDEN_LEAKAGE_FIELDS:
        assert forbidden not in X_train.columns, f"Leakage: {forbidden} in X_train"
        assert forbidden not in X_val.columns, f"Leakage: {forbidden} in X_val"
        assert forbidden not in X_test.columns, f"Leakage: {forbidden} in X_test"
    print("      - Forbidden reference/error/label fields in features: ZERO (PASS)")

    # 6. Benchmark Spread-Only Baseline
    print("\n[6/9] Benchmarking Spread-Only Baseline...")
    spread_test = X_test["ensemble_std"].fillna(0.0).values
    spread_roc = roc_auc_score(y_test, spread_test) if len(np.unique(y_test)) > 1 else 0.5
    spread_pr = average_precision_score(y_test, spread_test) if len(np.unique(y_test)) > 1 else test_bust_prev
    print(f"      - Spread-Only Baseline ROC-AUC: {spread_roc:.4f}")
    print(f"      - Spread-Only Baseline PR-AUC:  {spread_pr:.4f}")

    # 7. Train LightGBMBustClassifier
    print("\n[7/9] Training LightGBMBustClassifier (prototype-gbm-v1)...")
    clf = LightGBMBustClassifier(
        n_estimators=50,
        max_depth=3,
        num_leaves=7,
        learning_rate=0.05,
        min_child_samples=15,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )
    clf.fit(X_train, pd.Series(y_train))
    print("      - LightGBM training completed successfully.")

    # 8. Probability Calibration on Validation Split (Platt Sigmoid)
    print("\n[8/9] Fitting Platt Sigmoid ProbabilityCalibrator on Validation split...")
    raw_val_probs = clf.predict_proba(X_val)
    calibrator = ProbabilityCalibrator(method="sigmoid")
    calibrator.fit(raw_val_probs, y_val)
    cal_impact_val = calibrator.evaluate_calibration_impact(raw_val_probs, y_val)
    print(f"      - Validation Brier Score (Uncalibrated): {cal_impact_val['brier_score_uncalibrated']:.4f}")
    print(f"      - Validation Brier Score (Calibrated):   {cal_impact_val['brier_score_calibrated']:.4f}")
    print(f"      - Validation Brier Improvement:         {cal_impact_val['brier_improvement_pct']:.2f}%")

    # 9. Test Evaluation & Comparison
    print("\n[9/9] Evaluating Calibrated Model on Test Split...")
    raw_test_probs = clf.predict_proba(X_test)[:, 1]
    cal_test_probs = calibrator.predict_proba(raw_test_probs)[:, 1]

    # Metrics at decision threshold 0.280
    threshold = 0.280
    test_preds = (cal_test_probs >= threshold).astype(int)

    test_acc = float(accuracy_score(y_test, test_preds))
    test_prec = float(precision_score(y_test, test_preds, zero_division=0))
    test_rec = float(recall_score(y_test, test_preds, zero_division=0))
    test_f1 = float(f1_score(y_test, test_preds, zero_division=0))
    test_roc = float(roc_auc_score(y_test, cal_test_probs)) if len(np.unique(y_test)) > 1 else 0.5
    test_pr = float(average_precision_score(y_test, cal_test_probs)) if len(np.unique(y_test)) > 1 else test_bust_prev
    test_brier_uncal = float(brier_score_loss(y_test, raw_test_probs))
    test_brier_cal = float(brier_score_loss(y_test, cal_test_probs))
    brier_improvement = float((test_brier_uncal - test_brier_cal) / (test_brier_uncal + 1e-9) * 100.0)

    print(f"      - Test Accuracy:          {test_acc:.4f}")
    print(f"      - Test Precision:         {test_prec:.4f}")
    print(f"      - Test Recall:            {test_rec:.4f}")
    print(f"      - Test F1 Score:          {test_f1:.4f}")
    print(f"      - Test ROC-AUC:           {test_roc:.4f} (Spread baseline: {spread_roc:.4f})")
    print(f"      - Test PR-AUC:            {test_pr:.4f}  (Spread baseline: {spread_pr:.4f})")
    print(f"      - Test Brier (Uncal):     {test_brier_uncal:.4f}")
    print(f"      - Test Brier (Calibrated):{test_brier_cal:.4f} ({brier_improvement:+.2f}% improvement)")
    print(f"      - Calibrated P(bust) min: {cal_test_probs.min():.4f}, max: {cal_test_probs.max():.4f}")
    assert 0.0 <= cal_test_probs.min() and cal_test_probs.max() <= 1.0, "Probabilities out of bounds!"

    # 10. Persist Model Artifacts into models/day4/
    output_dir = Path(__file__).parents[1] / "models" / "day4"
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / "lightgbm_bust_model.joblib"
    calibrator_path = output_dir / "probability_calibrator.joblib"
    meta_path = output_dir / "model_metadata.json"

    joblib.dump(clf, model_path)
    joblib.dump(calibrator, calibrator_path)

    metadata = {
        "model_version": "prototype-gbm-v1",
        "model_type": "LightGBMBustClassifier",
        "feature_schema_version": "builder2-canonical-26-v1.0",
        "features": FEATURE_COLUMN_NAMES,
        "decision_threshold": threshold,
        "calibration_method": "sigmoid",
        "sample_counts": {
            "total": len(df_raw),
            "train": len(df_train_raw),
            "validation": len(df_val_raw),
            "test": len(df_test_raw),
        },
        "time_ranges": {
            "train": [str(df_train_raw["issue_dt"].min()), str(df_train_raw["issue_dt"].max())],
            "val": [str(df_val_raw["issue_dt"].min()), str(df_val_raw["issue_dt"].max())],
            "test": [str(df_test_raw["issue_dt"].min()), str(df_test_raw["issue_dt"].max())],
        },
        "test_metrics": {
            "accuracy": round(test_acc, 4),
            "precision": round(test_prec, 4),
            "recall": round(test_rec, 4),
            "f1_score": round(test_f1, 4),
            "roc_auc": round(test_roc, 4),
            "pr_auc": round(test_pr, 4),
            "brier_score_uncalibrated": round(test_brier_uncal, 4),
            "brier_score_calibrated": round(test_brier_cal, 4),
            "brier_improvement_pct": round(brier_improvement, 2),
            "spread_baseline_roc_auc": round(spread_roc, 4),
            "spread_baseline_pr_auc": round(spread_pr, 4),
        },
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[+] Saved Model Artifacts to '{output_dir}':")
    print(f"    - Model:      {model_path}")
    print(f"    - Calibrator: {calibrator_path}")
    print(f"    - Metadata:   {meta_path}")

    # 11. Save Datasets to data/training/ and data/historical/
    data_train_dir = Path(__file__).parents[1] / "data" / "training"
    data_train_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = data_train_dir / "training_dataset.parquet"
    jsonl_path = data_train_dir / "training_dataset.jsonl"

    # Export clean DataFrame without temporary internal datetime helper
    export_df = df_raw.drop(columns=["issue_dt"], errors="ignore")
    export_df.to_parquet(parquet_path, index=False)
    export_df.to_json(jsonl_path, orient="records", lines=True)

    print(f"\n[+] Exported Historical Training Datasets to '{data_train_dir}':")
    print(f"    - Parquet: {parquet_path} ({len(export_df)} rows, {len(export_df.columns)} cols)")
    print(f"    - JSONL:   {jsonl_path}")

    print("\n" + "=" * 70)
    print(" [+] BUILDER 2 MODEL TRAINING & PACKAGING COMPLETED SUCCESSFULLY")
    print("=" * 70)
    return metadata, output_dir


if __name__ == "__main__":
    meta, out = run_training_pipeline()

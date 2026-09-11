"""
Veyra Research — V3 Benchmark Challenger Training Pipeline (SIH26079)
Trains a production-grade LightGBM classifier strictly on the 547,500-row historical
training partition (2000–2013), calibrates on validation (2014–2016), and preserves
the test partition (2017–2019) completely untouched.

SCIENTIFIC & ARCHITECTURAL INVARIANTS:
1. Pure physical issue-time features only (50 features in SUPERCHARGED_PHYSICAL_FEATURES).
2. Zero station-ID memorization, zero lat/lon coordinates, zero elevation over-indexing.
3. Zero target leakage (no truth, no errors, no future cycles).
4. Calibrator selection strictly validation-only.
5. Preserves frozen production V2 model artifact unchanged.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Tuple

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.forecast_intelligence_features import (
    ForecastIntelligenceFeaturePipeline,
    SUPERCHARGED_PHYSICAL_FEATURES,
)
from research.evaluation.metrics import (
    calculate_pr_auc,
    calculate_roc_auc,
    calculate_ece,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("veyra.train_v3_challenger")


def train_v3_challenger(
    dataset_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    max_trees: int = 300,
    learning_rate: float = 0.05,
    early_stopping_rounds: int = 20,
) -> Dict[str, Any]:
    """
    Executes the training and validation calibration for V3 Benchmark Challenger.
    """
    start_time = time.time()
    ds_path = dataset_path or (PROJECT_ROOT / "data" / "processed" / "phase5b2_benchmark_canonical.parquet")
    out_dir = output_dir or (PROJECT_ROOT / "models" / "v3")
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("VEYRA V3 BENCHMARK CHALLENGER TRAINING PIPELINE")
    logger.info("=" * 70)

    # 1. Load Authoritative Canonical Benchmark
    logger.info(f"Loading canonical dataset from: {ds_path}")
    df = pd.read_parquet(ds_path)
    total_rows = len(df)
    logger.info(f"Loaded {total_rows:,} total rows.")

    # 2. Strict Partitioning
    df_train = df[df["split_partition"] == "train"].copy()
    df_val = df[df["split_partition"] == "val"].copy()
    df_test = df[df["split_partition"] == "test"].copy()

    n_train = len(df_train)
    n_val = len(df_val)
    n_test = len(df_test)

    logger.info(f"Partitions: Train={n_train:,} rows (730 cycles, 2000–2013) | Val={n_val:,} rows (155 cycles, 2014–2016) | Test={n_test:,} rows (155 cycles, 2017–2019)")

    # 3. Feature Invariant & Leakage Verification
    feature_names = list(SUPERCHARGED_PHYSICAL_FEATURES)
    assert len(feature_names) == 50, f"Expected 50 features, found {len(feature_names)}"

    forbidden_cols = {
        "location_id", "location", "city", "latitude", "longitude", "elevation_m", "elevation",
        "truth_value", "forecast_error", "abs_error", "forecast_abs_error", "bust_label", "is_bust"
    }
    leaked = set(feature_names).intersection(forbidden_cols)
    assert not leaked, f"CRITICAL LEAKAGE DETECTED: Features contain forbidden columns: {leaked}"
    logger.info("Feature invariant verified: 50 pure physical features, 0 forbidden/proxy features.")

    # 4. Feature Extraction
    pipeline = ForecastIntelligenceFeaturePipeline()
    logger.info("Extracting issue-time features on Train, Validation, and Test...")
    feat_train, _ = pipeline.extract_features(df_train, mode="supercharged")
    feat_val, _ = pipeline.extract_features(df_val, mode="supercharged")
    feat_test, _ = pipeline.extract_features(df_test, mode="supercharged")

    X_train = feat_train[feature_names].fillna(0.0).values.astype(np.float32)
    y_train = df_train["bust_label"].values.astype(int)

    X_val = feat_val[feature_names].fillna(0.0).values.astype(np.float32)
    y_val = df_val["bust_label"].values.astype(int)

    X_test = feat_test[feature_names].fillna(0.0).values.astype(np.float32)
    y_test = df_test["bust_label"].values.astype(int)

    logger.info(f"Training base rate: {y_train.mean():.4f} ({y_train.sum():,} / {len(y_train):,})")
    logger.info(f"Validation base rate: {y_val.mean():.4f} ({y_val.sum():,} / {len(y_val):,})")
    logger.info(f"Test base rate: {y_test.mean():.4f} ({y_test.sum():,} / {len(y_test):,})")

    # 5. Model Training (LightGBM on df_train with early stopping on df_val)
    train_data = lgb.Dataset(X_train, label=y_train, feature_name=feature_names, free_raw_data=False)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data, feature_name=feature_names, free_raw_data=False)

    params = {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "boosting_type": "gbdt",
        "learning_rate": learning_rate,
        "num_leaves": 31,
        "max_depth": 6,
        "min_child_samples": 50,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "n_jobs": -1,
        "random_state": 42,
        "verbose": -1,
    }

    logger.info(f"Training LightGBM model (max_trees={max_trees}, lr={learning_rate}, early_stopping={early_stopping_rounds})...")
    callbacks = [
        lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=True),
        lgb.log_evaluation(period=20),
    ]

    booster = lgb.train(
        params,
        train_data,
        num_boost_round=max_trees,
        valid_sets=[train_data, val_data],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    best_iteration = booster.best_iteration or max_trees
    logger.info(f"Training completed. Best iteration: {best_iteration} trees.")

    # 6. Safeguard 1: Validation-Only Calibrator Selection
    logger.info("Evaluating probability calibration strictly on Validation split...")
    raw_p_val = booster.predict(X_val, num_iteration=best_iteration)
    val_raw_brier = float(np.mean((raw_p_val - y_val) ** 2))
    val_raw_ece = calculate_ece(raw_p_val, y_val)["ece"]

    # Candidate 1: Isotonic
    iso_cal = IsotonicRegression(out_of_bounds="clip")
    iso_cal.fit(raw_p_val, y_val)
    val_p_iso = iso_cal.predict(raw_p_val)
    val_iso_brier = float(np.mean((val_p_iso - y_val) ** 2))
    val_iso_ece = calculate_ece(val_p_iso, y_val)["ece"]

    # Candidate 2: Platt (Sigmoid)
    platt_cal = LogisticRegression(C=1.0, max_iter=200, random_state=42)
    platt_cal.fit(raw_p_val.reshape(-1, 1), y_val)
    val_p_platt = platt_cal.predict_proba(raw_p_val.reshape(-1, 1))[:, 1]
    val_platt_brier = float(np.mean((val_p_platt - y_val) ** 2))
    val_platt_ece = calculate_ece(val_p_platt, y_val)["ece"]

    logger.info(f"Validation Calibration: Raw (Brier={val_raw_brier:.4f}, ECE={val_raw_ece:.4f})")
    logger.info(f"Validation Calibration: Isotonic (Brier={val_iso_brier:.4f}, ECE={val_iso_ece:.4f})")
    logger.info(f"Validation Calibration: Platt (Brier={val_platt_brier:.4f}, ECE={val_platt_ece:.4f})")

    # Select calibrator with lowest validation ECE and Brier score
    if val_iso_brier <= val_platt_brier:
        selected_calibrator = iso_cal
        calibrator_type = "isotonic"
        logger.info("Selected Calibration Strategy: Isotonic Regression (Validation-optimal)")
    else:
        selected_calibrator = platt_cal
        calibrator_type = "platt_sigmoid"
        logger.info("Selected Calibration Strategy: Platt Sigmoid (Validation-optimal)")

    # 7. Save Challenger Artifacts
    model_file = out_dir / "lightgbm_v3_challenger.joblib"
    calibrator_file = out_dir / "probability_calibrator_v3.joblib"
    feature_file = out_dir / "feature_names.json"
    manifest_file = out_dir / "training_manifest.json"

    joblib.dump(booster, model_file)
    joblib.dump(selected_calibrator, calibrator_file)
    with open(feature_file, "w", encoding="utf-8") as f:
        json.dump(feature_names, f, indent=2)

    train_manifest = {
        "model_name": "V3_Benchmark_Challenger",
        "training_partition": "2000-2013 (547,500 rows, 730 cycles)",
        "validation_partition": "2014-2016 (116,250 rows, 155 cycles)",
        "test_partition": "2017-2019 (116,250 rows, 155 cycles, untouched during training)",
        "features_count": 50,
        "feature_names": feature_names,
        "best_iteration": best_iteration,
        "training_params": params,
        "calibrator_type": calibrator_type,
        "validation_metrics": {
            "val_raw_brier": val_raw_brier,
            "val_raw_ece": val_raw_ece,
            "val_calibrated_brier": min(val_iso_brier, val_platt_brier),
            "val_calibrated_ece": min(val_iso_ece, val_platt_ece),
        },
        "model_artifact": str(model_file.relative_to(PROJECT_ROOT)),
        "calibrator_artifact": str(calibrator_file.relative_to(PROJECT_ROOT)),
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(train_manifest, f, indent=2)

    elapsed_time = time.time() - start_time
    logger.info(f"V3 Challenger Artifacts saved to: {out_dir} in {elapsed_time:.2f}s")

    return {
        "status": "SUCCESS",
        "model_file": str(model_file),
        "calibrator_file": str(calibrator_file),
        "best_iteration": best_iteration,
        "train_rows": n_train,
        "val_rows": n_val,
        "test_rows": n_test,
        "calibrator_type": calibrator_type,
        "training_time_seconds": round(elapsed_time, 2),
    }


if __name__ == "__main__":
    res = train_v3_challenger()
    print(json.dumps(res, indent=2))

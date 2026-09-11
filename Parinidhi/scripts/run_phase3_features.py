"""
Bust Labels, Features, and Leakage Audit Pipeline Runner.

Executes end-to-end:
1. Load Paired Historical Dataset (Day 2 output)
2. Fit BustLabelEngine on Training Period (Conditional q95 Error Threshold)
3. Generate Bust Labels (0/1) and Sensitivity Labels (q90, q95, q97.5, q99)
4. Extract Issue-Time-Safe Feature Matrix X
5. Execute Automated Data Leakage Audit
6. Persist training_dataset.parquet and Export configs/feature_schema.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from labels.label_engine import BustLabelEngine
from features.feature_pipeline import IssueTimeSafeFeaturePipeline, FEATURE_COLUMN_NAMES
from features.leakage_audit import LeakageAuditor, DataLeakageError


def run_phase3_pipeline(
    input_file: str = "data/historical/delhi/paired_historical_delhi_20260825T221956Z.parquet",
    output_dir: str = "data/features",
    thresholds_file: str = "configs/bust_thresholds.json",
) -> int:
    print("=" * 80)
    print(" FORECAST-BUST SENTINEL — PHASE 3: BUST LABELS, FEATURES & LEAKAGE AUDIT")
    print("=" * 80)
    print(f"Input Dataset    : {input_file}")
    print(f"Output Directory : {output_dir}")
    print("-" * 80)

    # 1. Load Historical Paired Dataset
    print("\n[STEP 1/5] LOADING HISTORICAL DATASET...")
    input_path = Path(input_file)
    if not input_path.exists():
        # Fallback to search any paired historical parquet
        matches = sorted(list(Path("data/historical").glob("**/*.parquet")))
        if not matches:
            print(f"[ERROR] No historical paired dataset found at {input_path} or in data/historical/", file=sys.stderr)
            return 1
        input_path = matches[-1]
        print(f"  [NOTE] Using latest available historical dataset: {input_path}")

    df_hist = pd.read_parquet(input_path)
    print(f"  [OK] Loaded {len(df_hist)} paired historical records.")
    print(f"  [OK] Variables: {list(df_hist['variable'].unique())}")
    print(f"  [OK] Date span: {df_hist['valid_time'].min()} to {df_hist['valid_time'].max()}")

    # 2. Fit BustLabelEngine on Training Data (Conditional q95 Error Threshold)
    print("\n[STEP 2/5] FITTING BUST LABEL ENGINE (TRAINING-PERIOD CONDITIONAL Q95)...")
    label_engine = BustLabelEngine(
        primary_quantile=0.95,
        sensitivity_quantiles=[0.90, 0.95, 0.975, 0.99],
    )
    
    # Chronological training split (e.g. first 80% for training threshold fitting)
    df_sorted = df_hist.sort_values(by=["valid_time"]).reset_index(drop=True)
    n_train = max(int(len(df_sorted) * 0.8), 20)
    df_train_split = df_sorted.iloc[:n_train]

    label_engine.fit(df_train_split)
    df_labeled = label_engine.transform(df_sorted)

    # Save frozen thresholds for offline inference and evaluation
    label_engine.save_thresholds(thresholds_file)
    print(f"  [OK] Bust thresholds fitted on {n_train} training records.")
    print(f"  [OK] Thresholds saved to {thresholds_file}")
    print("  [OK] Sample Fitted Variable Thresholds (q95):")
    for var, q_dict in label_engine.thresholds_.get("variable_thresholds", {}).items():
        print(f"      - {var.ljust(22)}: q95 = {q_dict.get('q_950', 'N/A'):.3f}")

    bust_count = df_labeled["bust_label"].sum()
    bust_pct = (bust_count / len(df_labeled)) * 100.0
    print(f"  [OK] Generated binary bust labels: {bust_count}/{len(df_labeled)} positive busts ({bust_pct:.2f}%)")

    # 3. Extract Issue-Time-Safe Features
    print("\n[STEP 3/5] EXTRACTING ISSUE-TIME-SAFE FEATURES...")
    pipeline = IssueTimeSafeFeaturePipeline()
    X, metadata = pipeline.extract_features(df_labeled)
    print(f"  [OK] Extracted {len(X.columns)} features across {len(X)} records.")

    # 4. Automated Data Leakage Audit
    print("\n[STEP 4/5] RUNNING AUTOMATED DATA LEAKAGE AUDIT...")
    auditor = LeakageAuditor()
    try:
        audit_report = auditor.audit_feature_matrix(
            features_df=X,
            metadata_df=metadata,
            target_series=df_labeled["bust_label"],
        )
        print("  [OK] LEAKAGE AUDIT PASSED:")
        for check in audit_report["leakage_checks_performed"]:
            print(f"      - [PASS] {check}")
    except DataLeakageError as e:
        print(f"[ERROR] LEAKAGE AUDIT FAILED: {e}", file=sys.stderr)
        return 1

    # 5. Assemble and Persist Unified Training Dataset
    print("\n[STEP 5/5] ASSEMBLING & PERSISTING TRAINING DATASET...")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Source ensemble distribution audit columns to preserve for reproducibility and downstream re-extraction
    source_audit_cols = [
        "ensemble_min",
        "ensemble_max",
        "q10",
        "q90",
    ]
    avail_audit = [c for c in source_audit_cols if c in df_labeled.columns]

    # Combine metadata, source audit columns, derived feature matrix X, and target labels without duplicate columns
    target_cols = [
        "bust_label",
        "bust_threshold",
        "is_ambiguous_zone",
        "bust_label_q9",
        "bust_label_q95",
        "bust_label_q975",
        "bust_label_q99",
        "forecast_abs_error",
        "forecast_error",
        "truth_value",
    ]
    avail_targets = [c for c in target_cols if c in df_labeled.columns]
    unique_meta_cols = [c for c in metadata.columns if c not in X.columns]

    final_df = pd.concat([metadata[unique_meta_cols], df_labeled[avail_audit], X, df_labeled[avail_targets]], axis=1)

    parquet_out = out_dir / "training_dataset.parquet"
    csv_out = out_dir / "training_dataset.csv"
    final_df.to_parquet(parquet_out, index=False)
    final_df.to_csv(csv_out, index=False)

    print(f"  [OK] Training dataset parquet : {parquet_out} ({parquet_out.stat().st_size / 1024.0:.2f} KB)")
    print(f"  [OK] Training dataset CSV     : {csv_out} ({csv_out.stat().st_size / 1024.0:.2f} KB)")

    # Print Final Feature List
    print("\n" + "=" * 80)
    print(f" FINAL MODEL FEATURE LIST ({len(FEATURE_COLUMN_NAMES)} FEATURES)")
    print("=" * 80)
    for i, col in enumerate(FEATURE_COLUMN_NAMES, 1):
        print(f"  {i:2d}. {col.ljust(30)} (Type: {str(X[col].dtype):<10})")

    print("\n" + "=" * 80)
    print(" PHASE 3 BUST LABELS, FEATURES & LEAKAGE AUDIT COMPLETED SUCCESSFULLY")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Forecast-Bust Sentinel Phase 3 Feature Pipeline")
    parser.add_argument("--input-file", default="data/historical/delhi/paired_historical_delhi_20260825T221956Z.parquet")
    parser.add_argument("--output-dir", default="data/features")
    parser.add_argument("--thresholds-file", default="configs/bust_thresholds.json")
    args = parser.parse_args()

    sys.exit(run_phase3_pipeline(
        input_file=args.input_file,
        output_dir=args.output_dir,
        thresholds_file=args.thresholds_file,
    ))

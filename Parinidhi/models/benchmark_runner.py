"""
Veyra Controlled Model Benchmark & Feature Ablation Suite.

Conducts rigorous scientific model comparisons (Logistic Regression vs HistGradientBoosting vs Calibrated LightGBM)
and controlled feature family ablation experiments on strict chronological train/validation/test partitions.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
import lightgbm as lgb

from features.forecast_intelligence_features import (
    CANONICAL_26_FEATURES,
    EXTENDED_INTELLIGENCE_FEATURES,
    ForecastIntelligenceFeaturePipeline,
    HistoricalSkillMatrix,
    TrainingOODScorer,
)
from labels.label_engine import BustLabelEngine
from models.calibrator import ProbabilityCalibrator
from models.data_splitter import ChronologicalDataSplitter, SplitData
from models.evaluator import ModelEvaluator
from models.verification_engine import ScientificVerificationEngine


# Feature group definitions for ablation study
ABLATION_FEATURE_GROUPS = {
    "1_BASELINE_CANONICAL_26": CANONICAL_26_FEATURES,
    "2_BASELINE_PLUS_ENSEMBLE_GEOM": [
        "ensemble_mean", "ensemble_median", "ensemble_std", "ensemble_min", "ensemble_max",
        "ensemble_range", "ensemble_p10", "ensemble_p25", "ensemble_p75", "ensemble_p90",
        "ensemble_iqr", "ensemble_skew_proxy", "ensemble_cv", "member_count", "has_full_ensemble",
        "forecast_value", "forecast_delta_6h", "forecast_delta_24h", "lead_hours", "lead_days",
        "valid_hour", "valid_month", "valid_dayofweek", "sin_hour", "cos_hour", "sin_month",
        "cos_month", "is_weekend", "latitude", "longitude"
    ],
    "3_BASELINE_PLUS_REVISION_STABILITY": CANONICAL_26_FEATURES + [
        "forecast_revision_mag_6h", "forecast_revision_mag_24h", "revision_accel_6h", "stability_index"
    ],
    "4_BASELINE_PLUS_SPREAD_SKILL": CANONICAL_26_FEATURES + [
        "hist_expected_error", "spread_skill_ratio", "overconfidence_signal"
    ],
    "5_ALL_INTEGRATED_FEATURES": EXTENDED_INTELLIGENCE_FEATURES,
}


class ModelBenchmarkRunner:
    """
    Executes controlled model benchmarking and feature ablation experiments.
    """

    def __init__(self, random_state: int = 42):
        self.random_state = random_state

    def run_model_benchmark(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        features: Optional[List[str]] = None,
        operational_threshold: float = 0.28,
    ) -> Dict[str, Any]:
        """
        Benchmark multiple model families on identical train/val/test splits.
        """
        cols = features or list(X_train.columns)
        X_tr = X_train[cols].fillna(0.0).values
        X_v = X_val[cols].fillna(0.0).values
        X_te = X_test[cols].fillna(0.0).values

        y_tr = y_train.values.astype(int)
        y_v = y_val.values.astype(int)
        y_te = y_test.values.astype(int)

        results = {}

        # 1. Baseline Logistic Regression
        lr = LogisticRegression(max_iter=1000, random_state=self.random_state)
        lr.fit(X_tr, y_tr)
        p_te_lr = lr.predict_proba(X_te)[:, 1]
        results["LogisticRegression"] = ScientificVerificationEngine.verify_classifier(
            y_te, p_te_lr, threshold=operational_threshold
        )
        results["LogisticRegression"]["brier_score"] = round(float(np.mean((y_te - p_te_lr) ** 2)), 4)

        # 2. HistGradientBoostingClassifier
        hgb = HistGradientBoostingClassifier(max_iter=100, random_state=self.random_state)
        hgb.fit(X_tr, y_tr)
        p_te_hgb = hgb.predict_proba(X_te)[:, 1]
        results["HistGradientBoosting"] = ScientificVerificationEngine.verify_classifier(
            y_te, p_te_hgb, threshold=operational_threshold
        )
        results["HistGradientBoosting"]["brier_score"] = round(float(np.mean((y_te - p_te_hgb) ** 2)), 4)

        # 3. LightGBM (Raw Uncalibrated)
        lgb_model = lgb.LGBMClassifier(
            n_estimators=100,
            learning_rate=0.05,
            num_leaves=31,
            random_state=self.random_state,
            verbose=-1,
        )
        lgb_model.fit(X_tr, y_tr)
        p_v_lgb = lgb_model.predict_proba(X_v)[:, 1]
        p_te_lgb = lgb_model.predict_proba(X_te)[:, 1]

        results["LightGBM_Raw"] = ScientificVerificationEngine.verify_classifier(
            y_te, p_te_lgb, threshold=operational_threshold
        )
        results["LightGBM_Raw"]["brier_score"] = round(float(np.mean((y_te - p_te_lgb) ** 2)), 4)

        # 4. Calibrated LightGBM (Platt Scaling fit on Validation split)
        calibrator = ProbabilityCalibrator(method="sigmoid")
        calibrator.fit(p_v_lgb, y_v)
        p_te_cal = calibrator.predict_proba(p_te_lgb)[:, 1]

        results["LightGBM_Calibrated"] = ScientificVerificationEngine.verify_classifier(
            y_te, p_te_cal, threshold=operational_threshold
        )
        results["LightGBM_Calibrated"]["brier_score"] = round(float(np.mean((y_te - p_te_cal) ** 2)), 4)
        results["LightGBM_Calibrated"]["ece"] = round(
            float(ScientificVerificationEngine.verify_probabilistic(y_te, p_te_cal)["expected_calibration_error"]), 4
        )

        return results

    def run_ablation_study(
        self,
        df_train_raw: pd.DataFrame,
        df_val_raw: pd.DataFrame,
        df_test_raw: pd.DataFrame,
        operational_threshold: float = 0.28,
    ) -> Dict[str, Any]:
        """
        Run feature family ablation study across all 5 configurations.
        """
        # 1. Fit historical skill matrix and OOD scorer STRICTLY on training split
        skill_matrix = HistoricalSkillMatrix().fit(df_train_raw)
        
        # Fit label engine on training split
        label_engine = BustLabelEngine().fit(df_train_raw)
        df_tr_lbl = label_engine.transform(df_train_raw)
        df_v_lbl = label_engine.transform(df_val_raw)
        df_te_lbl = label_engine.transform(df_test_raw)

        # Extract all extended features
        pipeline_tr = ForecastIntelligenceFeaturePipeline(skill_matrix=skill_matrix)
        X_tr_all, _ = pipeline_tr.extract_features(df_tr_lbl)

        ood_scorer = TrainingOODScorer().fit(X_tr_all)
        pipeline = ForecastIntelligenceFeaturePipeline(skill_matrix=skill_matrix, ood_scorer=ood_scorer)

        X_tr_all, _ = pipeline.extract_features(df_tr_lbl)
        X_v_all, _ = pipeline.extract_features(df_v_lbl)
        X_te_all, _ = pipeline.extract_features(df_te_lbl)

        y_tr = df_tr_lbl["bust_label"].astype(int)
        y_v = df_v_lbl["bust_label"].astype(int)
        y_te = df_te_lbl["bust_label"].astype(int)

        ablation_results = {}

        for exp_name, feat_list in ABLATION_FEATURE_GROUPS.items():
            valid_feats = [f for f in feat_list if f in X_tr_all.columns]
            X_tr_sub = X_tr_all[valid_feats].fillna(0.0).values
            X_v_sub = X_v_all[valid_feats].fillna(0.0).values
            X_te_sub = X_te_all[valid_feats].fillna(0.0).values

            model = lgb.LGBMClassifier(
                n_estimators=100,
                learning_rate=0.05,
                num_leaves=31,
                random_state=self.random_state,
                verbose=-1,
            )
            model.fit(X_tr_sub, y_tr.values)
            p_v = model.predict_proba(X_v_sub)[:, 1]
            p_te = model.predict_proba(X_te_sub)[:, 1]

            # Fit calibrator on validation split
            cal = ProbabilityCalibrator(method="sigmoid").fit(p_v, y_v.values)
            p_te_cal = cal.predict_proba(p_te)[:, 1]

            metrics = ScientificVerificationEngine.verify_classifier(y_te.values, p_te_cal, threshold=operational_threshold)
            prob_metrics = ScientificVerificationEngine.verify_probabilistic(y_te.values, p_te_cal)

            ablation_results[exp_name] = {
                "feature_count": len(valid_feats),
                "roc_auc": metrics["roc_auc"],
                "pr_auc": metrics["pr_auc"],
                "brier_score": prob_metrics["brier_score"],
                "ece": prob_metrics["expected_calibration_error"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1_score": metrics["f1_score"],
            }

        return ablation_results

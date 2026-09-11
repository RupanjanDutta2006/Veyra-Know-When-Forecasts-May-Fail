"""
Veyra Forecast Intelligence Feature Engine.

Comprehensive issue-time safe feature extraction, ensemble geometry, inter-cycle revision dynamics,
trajectory stability indexing, historical conditional skill matrices, spread-skill overconfidence detection,
and training-only OOD scoring.

SCIENTIFIC LEAKAGE & REPRODUCIBILITY INVARIANTS:
1. All features are computable strictly at forecast issue_time T.
2. Information available at T includes only current and preceding NWP cycles (<= T) and station spatial metadata.
3. Verification reference (ERA5 / observations) at T + lead is NEVER accessed during feature extraction.
4. Historical skill matrices and OOD parameters are fitted STRICTLY on historical training partitions.
5. Missing previous cycles strictly yield NaN for revisions (never imputed with 0.0).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


# -------------------------------------------------------------------------
# Feature Registry & Metadata Definitions
# -------------------------------------------------------------------------
FEATURE_CATALOG: Dict[str, Dict[str, Any]] = {
    # 1. Ensemble Geometry & Moments
    "ensemble_mean": {
        "family": "ensemble_geometry",
        "description": "Ensemble arithmetic mean across available members",
        "formula": "mean(x_m)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_median": {
        "family": "ensemble_geometry",
        "description": "Ensemble median (P50) across available members",
        "formula": "median(x_m)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_std": {
        "family": "ensemble_geometry",
        "description": "Ensemble standard deviation across available members",
        "formula": "sqrt(sum((x_m - mean)^2) / (M - 1))",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_min": {
        "family": "ensemble_geometry",
        "description": "Minimum value across ensemble members",
        "formula": "min(x_m)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_max": {
        "family": "ensemble_geometry",
        "description": "Maximum value across ensemble members",
        "formula": "max(x_m)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_range": {
        "family": "ensemble_geometry",
        "description": "Ensemble full range (max - min)",
        "formula": "max(x_m) - min(x_m)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_p10": {
        "family": "ensemble_geometry",
        "description": "Ensemble 10th percentile",
        "formula": "quantile(x_m, 0.10)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_p25": {
        "family": "ensemble_geometry",
        "description": "Ensemble 25th percentile (Q1)",
        "formula": "quantile(x_m, 0.25)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_p75": {
        "family": "ensemble_geometry",
        "description": "Ensemble 75th percentile (Q3)",
        "formula": "quantile(x_m, 0.75)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_p90": {
        "family": "ensemble_geometry",
        "description": "Ensemble 90th percentile",
        "formula": "quantile(x_m, 0.90)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_iqr": {
        "family": "ensemble_geometry",
        "description": "Ensemble interquartile range (P75 - P25 or P90 - P10)",
        "formula": "P90 - P10",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_skew_proxy": {
        "family": "ensemble_geometry",
        "description": "Ensemble distribution skewness proxy",
        "formula": "(mean - midpoint) / (std + eps)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_cv": {
        "family": "ensemble_geometry",
        "description": "Coefficient of variation of ensemble",
        "formula": "std / (|mean| + eps)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_spread_to_iqr_ratio": {
        "family": "ensemble_geometry",
        "description": "Ratio of ensemble standard deviation to IQR",
        "formula": "std / (iqr + eps)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "member_count": {
        "family": "ensemble_geometry",
        "description": "Actual count of successfully decoded ensemble members",
        "formula": "count(members)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "has_full_ensemble": {
        "family": "ensemble_geometry",
        "description": "Flag indicating if all expected members for the product are present",
        "formula": "1 if member_count == expected_count else 0",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },

    # 2. Control Forecast & Forecast Values
    "forecast_value": {
        "family": "forecast_core",
        "description": "Deterministic control member forecast value (c00)",
        "formula": "x_c00",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },

    # 3. Inter-Cycle Forecast Revision & Stability
    "forecast_delta_6h": {
        "family": "revision_dynamics",
        "description": "Signed forecast change for identical valid_time from T-6h cycle",
        "formula": "x(T, V) - x(T-6h, V)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "forecast_delta_24h": {
        "family": "revision_dynamics",
        "description": "Signed forecast change for identical valid_time from T-24h cycle",
        "formula": "x(T, V) - x(T-24h, V)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "forecast_revision_mag_6h": {
        "family": "revision_dynamics",
        "description": "Magnitude of 6h forecast revision",
        "formula": "|x(T, V) - x(T-6h, V)|",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "forecast_revision_mag_24h": {
        "family": "revision_dynamics",
        "description": "Magnitude of 24h forecast revision",
        "formula": "|x(T, V) - x(T-24h, V)|",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_spread_delta_6h": {
        "family": "revision_dynamics",
        "description": "Spread change for identical valid_time from T-6h cycle",
        "formula": "std(T, V) - std(T-6h, V)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "ensemble_spread_delta_24h": {
        "family": "revision_dynamics",
        "description": "Spread change for identical valid_time from T-24h cycle",
        "formula": "std(T, V) - std(T-24h, V)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "revision_accel_6h": {
        "family": "revision_dynamics",
        "description": "Second-order revision acceleration across T, T-6h, T-12h",
        "formula": "(x(T, V) - 2*x(T-6h, V) + x(T-12h, V)) / 6",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "stability_index": {
        "family": "forecast_stability",
        "description": "0-100 bounded trajectory stability index (100=stable, 0=erratic flip-flop)",
        "formula": "100 * exp(-(|delta_rev| + 0.5*|accel|) / (std + eps))",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },

    # 4. Spread-Skill Discrepancy & Overconfidence Signal
    "hist_expected_error": {
        "family": "historical_skill",
        "description": "Historical conditional MAE for this location, variable, and lead bin",
        "formula": "TrainingConditionalMAE(loc, var, lead_bin)",
        "leakage_safe": True,
        "earliest_info": "issue_time (training-fitted)",
    },
    "spread_skill_ratio": {
        "family": "spread_skill",
        "description": "Ratio of ensemble spread to historical conditional expected error",
        "formula": "ensemble_std / (hist_expected_error + eps)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "overconfidence_signal": {
        "family": "spread_skill",
        "description": "Overconfidence signal indicating low spread in historically high-error regime",
        "formula": "max(0, (hist_expected_error - ensemble_std) / (hist_expected_error + eps))",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },

    # 5. Horizon & Astronomical / Cyclical Features
    "lead_hours": {
        "family": "horizon_temporal",
        "description": "Forecast lead time in hours (valid_time - issue_time)",
        "formula": "int((valid_time - issue_time).total_seconds() / 3600)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "lead_days": {
        "family": "horizon_temporal",
        "description": "Forecast lead time in days",
        "formula": "lead_hours / 24.0",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "lead_decay_factor": {
        "family": "horizon_temporal",
        "description": "Empirical reliability decay factor scaling linearly with horizon",
        "formula": "1.0 - min(1.0, lead_hours / 240.0)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "valid_hour": {
        "family": "horizon_temporal",
        "description": "UTC hour of validity",
        "formula": "valid_time.dt.hour",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "valid_month": {
        "family": "horizon_temporal",
        "description": "UTC month of validity",
        "formula": "valid_time.dt.month",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "valid_dayofweek": {
        "family": "horizon_temporal",
        "description": "Day of week (0=Mon, 6=Sun)",
        "formula": "valid_time.dt.dayofweek",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "sin_hour": {
        "family": "horizon_temporal",
        "description": "Diurnal cycle sine harmonic",
        "formula": "sin(2 * pi * valid_hour / 24)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "cos_hour": {
        "family": "horizon_temporal",
        "description": "Diurnal cycle cosine harmonic",
        "formula": "cos(2 * pi * valid_hour / 24)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "sin_month": {
        "family": "horizon_temporal",
        "description": "Annual seasonal cycle sine harmonic",
        "formula": "sin(2 * pi * valid_month / 12)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "cos_month": {
        "family": "horizon_temporal",
        "description": "Annual seasonal cycle cosine harmonic",
        "formula": "cos(2 * pi * valid_month / 12)",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "is_weekend": {
        "family": "horizon_temporal",
        "description": "Binary weekend flag",
        "formula": "1 if valid_dayofweek in (5, 6) else 0",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },

    # 6. Spatial Coordinates & Climate Metadata
    "latitude": {
        "family": "spatial_climate",
        "description": "Station latitude in degrees",
        "formula": "requested_latitude",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },
    "longitude": {
        "family": "spatial_climate",
        "description": "Station longitude in degrees",
        "formula": "requested_longitude",
        "leakage_safe": True,
        "earliest_info": "issue_time",
    },

    # 7. Training OOD / Novelty
    "ood_score": {
        "family": "ood_novelty",
        "description": "Mahalanobis distance to training feature distribution",
        "formula": "sqrt((x - mu)^T Sigma^-1 (x - mu))",
        "leakage_safe": True,
        "earliest_info": "issue_time (training-fitted)",
    },
}

CANONICAL_26_FEATURES = [
    "ensemble_std",
    "ensemble_range",
    "ensemble_iqr",
    "ensemble_skew_proxy",
    "ensemble_cv",
    "ensemble_spread_to_iqr_ratio",
    "member_count",
    "has_full_ensemble",
    "forecast_value",
    "ensemble_mean",
    "ensemble_spread_delta_6h",
    "ensemble_spread_delta_24h",
    "forecast_delta_6h",
    "forecast_delta_24h",
    "lead_hours",
    "lead_days",
    "valid_hour",
    "valid_month",
    "valid_dayofweek",
    "sin_hour",
    "cos_hour",
    "sin_month",
    "cos_month",
    "is_weekend",
    "latitude",
    "longitude",
]

EXTENDED_INTELLIGENCE_FEATURES = [
    # Ensemble Geometry
    "ensemble_mean",
    "ensemble_median",
    "ensemble_std",
    "ensemble_min",
    "ensemble_max",
    "ensemble_range",
    "ensemble_p10",
    "ensemble_p25",
    "ensemble_p75",
    "ensemble_p90",
    "ensemble_iqr",
    "ensemble_skew_proxy",
    "ensemble_cv",
    "ensemble_spread_to_iqr_ratio",
    "member_count",
    "has_full_ensemble",
    # Core & Revision
    "forecast_value",
    "forecast_delta_6h",
    "forecast_delta_24h",
    "forecast_revision_mag_6h",
    "forecast_revision_mag_24h",
    "ensemble_spread_delta_6h",
    "ensemble_spread_delta_24h",
    "revision_accel_6h",
    "stability_index",
    # Historical Skill & Overconfidence
    "hist_expected_error",
    "spread_skill_ratio",
    "overconfidence_signal",
    # Horizon & Temporal
    "lead_hours",
    "lead_days",
    "lead_decay_factor",
    "valid_hour",
    "valid_month",
    "valid_dayofweek",
    "sin_hour",
    "cos_hour",
    "sin_month",
    "cos_month",
    "is_weekend",
    # Spatial & OOD
    "latitude",
    "longitude",
    "ood_score",
]

SUPERCHARGED_PHYSICAL_FEATURES = [
    # 1. Ensemble Geometry & Higher-Order Moments
    "ensemble_mean",
    "ensemble_median",
    "ensemble_std",
    "ensemble_min",
    "ensemble_max",
    "ensemble_range",
    "ensemble_p10",
    "ensemble_p25",
    "ensemble_p75",
    "ensemble_p90",
    "ensemble_iqr",
    "ensemble_skew_proxy",
    "ensemble_kurtosis_proxy",
    "ensemble_cv",
    "ensemble_spread_to_iqr_ratio",
    "quantile_spacing_ratio",
    "tail_asymmetry",
    "robust_mad",
    "member_count",
    "has_full_ensemble",
    # 2. Forecast Core & Revisions
    "forecast_value",
    "forecast_delta_6h",
    "forecast_delta_24h",
    "forecast_revision_mag_6h",
    "forecast_revision_mag_24h",
    "ensemble_spread_delta_6h",
    "ensemble_spread_delta_24h",
    "revision_accel_6h",
    "stability_index",
    # 3. Structural Overconfidence & Regime Dynamics (Issue-Time Safe)
    "structural_overconfidence_risk",
    "rapid_change_proxy",
    "diurnal_phase_alignment",
    # 4. Lead Horizon & Physical Interactions
    "lead_hours",
    "lead_days",
    "lead_decay_factor",
    "spread_x_lead",
    "cv_x_lead",
    "revision_x_spread",
    # 5. Temporal Harmonics
    "valid_hour",
    "valid_month",
    "valid_dayofweek",
    "sin_hour",
    "cos_hour",
    "sin_month",
    "cos_month",
    "is_weekend",
    # 6. Physical Variable Indicators
    "is_surface_pressure",
    "is_temperature_2m",
    "is_wind_speed_10m",
    # 7. Issue-time OOD Score
    "ood_score",
]


def classify_failure_fingerprint(row: pd.Series) -> str:
    """
    Mathematically classifies a forecast into one of 6 mutually exclusive failure archetypes
    using strictly issue-time physical observables.
    """
    rev_mag = float(row.get("forecast_revision_mag_6h", 0.0) or 0.0)
    std = float(row.get("ensemble_std", 1.0) or 1.0)
    lead = float(row.get("lead_hours", 0) or 0)
    stab = float(row.get("stability_index", 100.0) or 100.0)
    cos_h = float(row.get("cos_hour", 0.0) or 0.0)
    cv = float(row.get("ensemble_cv", 0.0) or 0.0)
    is_wind = float(row.get("is_wind_speed_10m", 0.0) or 0.0)
    p90 = float(row.get("ensemble_p90", 0.0) or 0.0)
    overconf = float(row.get("structural_overconfidence_risk", 0.0) or 0.0)

    if rev_mag > 1.8 * std and stab < 50.0:
        return "RAPID_REVISION_SHOCK"
    elif lead >= 48 and std > 1.5:
        return "LONG_LEAD_DECAY"
    elif cos_h > 0.3 and cv > 0.12:
        return "DIURNAL_CONVECTIVE_MISMATCH"
    elif is_wind == 1.0 and p90 > 14.0:
        return "WIND_GRADIENT_SHEAR"
    elif overconf > 25.0:
        return "TIGHT_CLUSTER_BREAKDOWN"
    else:
        return "STABLE_SYNOPTIC_CONSENSUS"


# -------------------------------------------------------------------------
# Historical Conditional Skill Matrix (Fitted on Training Set Only)
# -------------------------------------------------------------------------
class HistoricalSkillMatrix:
    """
    Computes and stores historical forecast error benchmarks strictly from historical training data.
    Provides hierarchical conditional error lookups:
    (location, variable, lead_bin) -> (location, variable) -> (variable, lead_bin) -> global.
    """

    def __init__(self, min_stratum_samples: int = 8, error_col: str = "forecast_abs_error"):
        self.min_stratum_samples = min_stratum_samples
        self.error_col = error_col
        self.is_fitted_ = False
        self.stats_: Dict[str, Any] = {}

    def fit(self, df_train: pd.DataFrame) -> "HistoricalSkillMatrix":
        if df_train.empty:
            raise ValueError("Cannot fit HistoricalSkillMatrix on empty training dataframe.")

        df = df_train.copy()
        if self.error_col not in df.columns:
            # Fallback if abs error column missing
            if "forecast_value" in df.columns and "truth_value" in df.columns:
                df[self.error_col] = (df["forecast_value"] - df["truth_value"]).abs()
            elif "value" in df.columns and "truth_value" in df.columns:
                df[self.error_col] = (df["value"] - df["truth_value"]).abs()
            else:
                # Default baseline variance proxy
                df[self.error_col] = df.get("ensemble_std", pd.Series(1.0, index=df.index))

        if "lead_bin" not in df.columns:
            bins = [-1, 24, 72, 144, 240, 9999]
            labels = ["day1", "day2_3", "day4_6", "day7_10", "day10_plus"]
            df["lead_bin"] = pd.cut(df["lead_hours"].astype(int), bins=bins, labels=labels).astype(str)

        # 1. Global stats
        global_mae = float(df[self.error_col].mean())
        global_std = float(df[self.error_col].std())

        # 2. Variable stats
        var_stats = {}
        for var, g in df.groupby("variable"):
            var_stats[str(var)] = {
                "mae": float(g[self.error_col].mean()),
                "rmse": float(np.sqrt(np.mean(g[self.error_col] ** 2))),
                "count": int(len(g)),
            }

        # 3. Location x Variable stats
        loc_var_stats = {}
        for (loc, var), g in df.groupby(["location", "variable"]):
            if len(g) >= self.min_stratum_samples:
                loc_var_stats[f"{loc}__{var}"] = {
                    "mae": float(g[self.error_col].mean()),
                    "rmse": float(np.sqrt(np.mean(g[self.error_col] ** 2))),
                    "count": int(len(g)),
                }

        # 4. Stratified: Location x Variable x LeadBin
        stratified_stats = {}
        for (loc, var, lbin), g in df.groupby(["location", "variable", "lead_bin"]):
            if len(g) >= self.min_stratum_samples:
                stratified_stats[f"{loc}__{var}__{lbin}"] = {
                    "mae": float(g[self.error_col].mean()),
                    "rmse": float(np.sqrt(np.mean(g[self.error_col] ** 2))),
                    "count": int(len(g)),
                }

        # 5. Variable x LeadBin
        var_lead_stats = {}
        for (var, lbin), g in df.groupby(["variable", "lead_bin"]):
            if len(g) >= self.min_stratum_samples:
                var_lead_stats[f"{var}__{lbin}"] = {
                    "mae": float(g[self.error_col].mean()),
                    "rmse": float(np.sqrt(np.mean(g[self.error_col] ** 2))),
                    "count": int(len(g)),
                }

        self.stats_ = {
            "global_mae": global_mae,
            "global_std": global_std,
            "variable_stats": var_stats,
            "location_variable_stats": loc_var_stats,
            "variable_lead_stats": var_lead_stats,
            "stratified_stats": stratified_stats,
            "training_samples": len(df),
        }
        self.is_fitted_ = True
        return self

    def get_expected_error(self, location: str, variable: str, lead_hours: int) -> float:
        """Lookup conditional expected error with hierarchical fallback."""
        if not self.is_fitted_:
            return 1.0

        bins = [-1, 24, 72, 144, 240, 9999]
        labels = ["day1", "day2_3", "day4_6", "day7_10", "day10_plus"]
        lbin = "day1"
        for i in range(len(bins) - 1):
            if bins[i] < lead_hours <= bins[i + 1]:
                lbin = labels[i]
                break

        # Level 1: Stratified (loc, var, lbin)
        k1 = f"{location}__{variable}__{lbin}"
        if k1 in self.stats_["stratified_stats"]:
            return self.stats_["stratified_stats"][k1]["mae"]

        # Level 2: Location x Variable
        k2 = f"{location}__{variable}"
        if k2 in self.stats_["location_variable_stats"]:
            return self.stats_["location_variable_stats"][k2]["mae"]

        # Level 3: Variable x Lead
        k3 = f"{variable}__{lbin}"
        if k3 in self.stats_["variable_lead_stats"]:
            return self.stats_["variable_lead_stats"][k3]["mae"]

        # Level 4: Variable
        if variable in self.stats_["variable_stats"]:
            return self.stats_["variable_stats"][variable]["mae"]

        # Level 5: Global
        return self.stats_["global_mae"]

    def to_dict(self) -> Dict[str, Any]:
        return self.stats_

    def from_dict(self, d: Dict[str, Any]) -> "HistoricalSkillMatrix":
        self.stats_ = d
        self.is_fitted_ = True
        return self


# -------------------------------------------------------------------------
# Training OOD / Novelty Scorer (Fitted on Training Set Only)
# -------------------------------------------------------------------------
class TrainingOODScorer:
    """
    Computes Mahalanobis novelty distance strictly against the training feature distribution.
    Features are robustly standardized using training means and variances.
    """

    def __init__(self, eps: float = 1e-4):
        self.eps = eps
        self.is_fitted_ = False
        self.mean_: np.ndarray = np.array([])
        self.std_: np.ndarray = np.array([])
        self.feature_cols_: List[str] = []

    def fit(self, X_train: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> "TrainingOODScorer":
        if X_train.empty:
            raise ValueError("Cannot fit OOD scorer on empty training set.")

        cols = feature_cols or [c for c in X_train.columns if np.issubdtype(X_train[c].dtype, np.number)]
        self.feature_cols_ = cols

        sub_X = X_train[cols].copy().fillna(0.0)
        self.mean_ = sub_X.mean(axis=0).values.astype(float)
        self.std_ = sub_X.std(axis=0).values.astype(float)
        self.std_[self.std_ < self.eps] = 1.0

        self.is_fitted_ = True
        return self

    def compute_ood_score(self, X: pd.DataFrame) -> pd.Series:
        """Compute normalized Mahalanobis distance proxy for each sample."""
        if not self.is_fitted_:
            return pd.Series(0.0, index=X.index)

        cols = [c for c in self.feature_cols_ if c != "ood_score" and c in X.columns]
        if not cols:
            return pd.Series(0.0, index=X.index)

        sub_X = X[cols].copy().fillna(0.0).values.astype(float)
        mean_sub = self.mean_[[i for i, c in enumerate(self.feature_cols_) if c in cols]]
        std_sub = self.std_[[i for i, c in enumerate(self.feature_cols_) if c in cols]]

        z = (sub_X - mean_sub) / std_sub
        # Euclidean norm of z-score vector normalized by sqrt(n_features)
        dist = np.sqrt(np.mean(z ** 2, axis=1))
        # Scaled to approximately [0, 100] percentile novelty proxy
        score = np.clip(dist * 20.0, 0.0, 100.0)
        return pd.Series(score, index=X.index, name="ood_score").round(3)


# -------------------------------------------------------------------------
# Comprehensive Forecast Intelligence Feature Pipeline
# -------------------------------------------------------------------------
class ForecastIntelligenceFeaturePipeline:
    """
    Unified, issue-time safe feature extraction engine for Forecast Bust Sentinel.
    Computes ensemble geometry, revision dynamics, stability indices, spread-skill ratios,
    and training-calibrated OOD novelty scores.
    """

    def __init__(
        self,
        skill_matrix: Optional[HistoricalSkillMatrix] = None,
        ood_scorer: Optional[TrainingOODScorer] = None,
        eps: float = 1e-6,
    ):
        self.skill_matrix = skill_matrix
        self.ood_scorer = ood_scorer
        self.eps = eps

    def extract_features(
        self,
        df_forecast: pd.DataFrame,
        mode: str = "extended",
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract extended intelligence features and metadata from forecast dataframe.

        Args:
            df_forecast: Standardized forecast DataFrame.

        Returns:
            Tuple of (features_df, metadata_df).
        """
        if df_forecast.empty:
            raise ValueError("Input DataFrame is empty.")

        df = df_forecast.copy()

        # Normalize column names
        if "location" not in df.columns:
            df["location"] = df["location_id"] if "location_id" in df.columns else "delhi"
        if "location_id" not in df.columns:
            df["location_id"] = df["location"]
        if "variable" not in df.columns:
            df["variable"] = "temperature_2m"
        if "issue_time_utc" in df.columns and "issue_time" not in df.columns:
            df["issue_time"] = df["issue_time_utc"]
        if "valid_time_utc" in df.columns and "valid_time" not in df.columns:
            df["valid_time"] = df["valid_time_utc"]
        if "issue_time" not in df.columns:
            df["issue_time"] = datetime.now(timezone.utc).isoformat()
        if "valid_time" not in df.columns:
            if "lead_hours" in df.columns:
                issue_dt = pd.to_datetime(df["issue_time"], utc=True)
                lead_deltas = pd.to_timedelta(pd.to_numeric(df["lead_hours"], errors="coerce").fillna(24), unit="h")
                df["valid_time"] = issue_dt + lead_deltas
            else:
                df["valid_time"] = pd.to_datetime(df["issue_time"], utc=True) + pd.Timedelta(hours=24)
        if "lead_hours" not in df.columns:
            deltas = (pd.to_datetime(df["valid_time"], utc=True) - pd.to_datetime(df["issue_time"], utc=True)).dt.total_seconds() / 3600.0
            df["lead_hours"] = deltas.round().fillna(24).astype(int)
        else:
            df["lead_hours"] = pd.to_numeric(df["lead_hours"], errors="coerce").fillna(24).astype(int)
        if "forecast_value" not in df.columns:
            if "value" in df.columns:
                df["forecast_value"] = df["value"]
            elif "ensemble_mean" in df.columns:
                df["forecast_value"] = df["ensemble_mean"]
            else:
                df["forecast_value"] = 0.0
        if "value" not in df.columns:
            df["value"] = df["forecast_value"]

        # Ensure datetime types
        df["valid_time"] = pd.to_datetime(df["valid_time"], utc=True)
        df["issue_time"] = pd.to_datetime(df["issue_time"], utc=True)

        # Track original row ordering to guarantee 1:1 output alignment
        df["_orig_idx"] = np.arange(len(df))

        # Sort chronologically by location, variable, issue_time, valid_time
        sort_keys = ["location", "variable", "issue_time", "valid_time"]
        avail_sort = [k for k in sort_keys if k in df.columns]
        df = df.sort_values(by=avail_sort).reset_index(drop=True)

        # ---------------------------------------------------------
        # 1. Ensemble Geometry & Dispersion Moments
        # ---------------------------------------------------------
        fc_val = pd.to_numeric(df["forecast_value"], errors="coerce").fillna(300.0).astype(float)
        ens_mean = pd.to_numeric(df["ensemble_mean"], errors="coerce").fillna(fc_val).astype(float) if "ensemble_mean" in df.columns else fc_val
        ens_std = pd.to_numeric(df["ensemble_std"], errors="coerce").fillna(0.0).astype(float) if "ensemble_std" in df.columns else pd.Series(0.0, index=df.index)
        ens_min = pd.to_numeric(df["ensemble_min"], errors="coerce").fillna(ens_mean).astype(float) if "ensemble_min" in df.columns else ens_mean
        ens_max = pd.to_numeric(df["ensemble_max"], errors="coerce").fillna(ens_mean).astype(float) if "ensemble_max" in df.columns else ens_mean
        p10 = pd.to_numeric(df["q10"], errors="coerce").fillna(ens_min).astype(float) if "q10" in df.columns else ens_min
        p90 = pd.to_numeric(df["q90"], errors="coerce").fillna(ens_max).astype(float) if "q90" in df.columns else ens_max
        p25 = pd.to_numeric(df["p25"], errors="coerce").fillna(0.75 * ens_mean + 0.25 * ens_min).astype(float) if "p25" in df.columns else (0.75 * ens_mean + 0.25 * ens_min)
        p75 = pd.to_numeric(df["p75"], errors="coerce").fillna(0.75 * ens_mean + 0.25 * ens_max).astype(float) if "p75" in df.columns else (0.75 * ens_mean + 0.25 * ens_max)
        median = pd.to_numeric(df["median"], errors="coerce").fillna(ens_mean).astype(float) if "median" in df.columns else ens_mean

        df["ensemble_mean"] = ens_mean
        df["ensemble_median"] = median
        df["ensemble_std"] = ens_std
        df["ensemble_min"] = ens_min
        df["ensemble_max"] = ens_max
        df["ensemble_range"] = (ens_max - ens_min).clip(lower=0.0)
        df["ensemble_p10"] = p10
        df["ensemble_p25"] = p25
        df["ensemble_p75"] = p75
        df["ensemble_p90"] = p90
        df["ensemble_iqr"] = (p90 - p10).clip(lower=0.0)

        # Ensemble skewness proxy: (mean - midpoint) / (std + eps)
        midpoint = 0.5 * (ens_max + ens_min)
        df["ensemble_skew_proxy"] = (ens_mean - midpoint) / (ens_std + self.eps)

        # Coefficient of variation: std / (|mean| + eps)
        df["ensemble_cv"] = ens_std / (ens_mean.abs() + self.eps)
        df["ensemble_spread_to_iqr_ratio"] = ens_std / (df["ensemble_iqr"] + self.eps)

        # Member counts
        if "member_count" in df.columns:
            df["member_count"] = df["member_count"].fillna(5).astype(int)
        else:
            df["member_count"] = 5

        expected_count = df.get("expected_member_count", pd.Series(df["member_count"], index=df.index)).fillna(df["member_count"])
        df["has_full_ensemble"] = (df["member_count"] >= expected_count).astype(int)

        # ---------------------------------------------------------
        # 2. Inter-Cycle Forecast & Spread Revisions (Strict Valid-Time Matching)
        # ---------------------------------------------------------
        lookup_cols = ["location", "variable", "valid_time", "issue_time", "forecast_value", "ensemble_std"]
        lookup_cols = [c for c in lookup_cols if c in df.columns]
        lookup = df[lookup_cols].drop_duplicates().copy()

        # Lookup T-6h cycle
        df["_prior_issue_6h"] = df["issue_time"] - pd.Timedelta(hours=6)
        m6 = pd.merge(
            df,
            lookup.rename(columns={
                "forecast_value": "fc_prev_6h",
                "ensemble_std": "std_prev_6h",
                "issue_time": "issue_prev_6h",
            }),
            left_on=["location", "variable", "valid_time", "_prior_issue_6h"],
            right_on=["location", "variable", "valid_time", "issue_prev_6h"],
            how="left",
        )

        # Lookup T-12h cycle (for 2nd-order acceleration)
        df["_prior_issue_12h"] = df["issue_time"] - pd.Timedelta(hours=12)
        m12 = pd.merge(
            df,
            lookup.rename(columns={
                "forecast_value": "fc_prev_12h",
                "ensemble_std": "std_prev_12h",
                "issue_time": "issue_prev_12h",
            }),
            left_on=["location", "variable", "valid_time", "_prior_issue_12h"],
            right_on=["location", "variable", "valid_time", "issue_prev_12h"],
            how="left",
        )

        # Lookup T-24h cycle
        df["_prior_issue_24h"] = df["issue_time"] - pd.Timedelta(hours=24)
        m24 = pd.merge(
            df,
            lookup.rename(columns={
                "forecast_value": "fc_prev_24h",
                "ensemble_std": "std_prev_24h",
                "issue_time": "issue_prev_24h",
            }),
            left_on=["location", "variable", "valid_time", "_prior_issue_24h"],
            right_on=["location", "variable", "valid_time", "issue_prev_24h"],
            how="left",
        )

        # Revisions: current forecast minus prior cycle forecast for SAME valid_time
        df["forecast_delta_6h"] = m6["forecast_value"] - m6["fc_prev_6h"]
        df["forecast_delta_24h"] = m24["forecast_value"] - m24["fc_prev_24h"]
        df["forecast_revision_mag_6h"] = df["forecast_delta_6h"].abs()
        df["forecast_revision_mag_24h"] = df["forecast_delta_24h"].abs()

        df["ensemble_spread_delta_6h"] = m6["ensemble_std"] - m6["std_prev_6h"]
        df["ensemble_spread_delta_24h"] = m24["ensemble_std"] - m24["std_prev_24h"]

        # 2nd-order revision acceleration: (X(T, V) - 2*X(T-6h, V) + X(T-12h, V)) / 6
        df["revision_accel_6h"] = (df["forecast_value"] - 2.0 * m6["fc_prev_6h"] + m12["fc_prev_12h"]) / 6.0

        # Clean up temporary lookup columns
        df.drop(columns=["_prior_issue_6h", "_prior_issue_12h", "_prior_issue_24h"], inplace=True, errors="ignore")

        # ---------------------------------------------------------
        # 3. Forecast Stability Index (Bounded 0 to 100)
        # ---------------------------------------------------------
        # Formula: 100 * exp(-(|delta_rev_24h| + 0.5*|accel_6h|) / (std + eps))
        rev_norm = df["forecast_revision_mag_24h"].fillna(df["forecast_revision_mag_6h"]).fillna(0.0)
        accel_norm = df["revision_accel_6h"].abs().fillna(0.0)
        disp_denom = df["ensemble_std"] + self.eps
        # Exponential decay: when revision is small relative to spread, stability -> 100
        instability_ratio = pd.to_numeric((rev_norm + 0.5 * accel_norm) / disp_denom, errors="coerce").fillna(0.0).values.astype(float)
        df["stability_index"] = (100.0 * np.exp(-np.clip(instability_ratio, 0.0, 20.0))).round(2)

        # ---------------------------------------------------------
        # 4. Historical Conditional Skill & Spread-Skill Overconfidence
        # ---------------------------------------------------------
        if self.skill_matrix is not None and self.skill_matrix.is_fitted_:
            hist_exp_err = []
            for _, r in df.iterrows():
                loc = str(r.get("location", "default"))
                var = str(r.get("variable", "temperature_2m"))
                lead = int(r.get("lead_hours", 24))
                hist_exp_err.append(self.skill_matrix.get_expected_error(loc, var, lead))
            df["hist_expected_error"] = np.array(hist_exp_err, dtype=float)
        else:
            # Baseline proxy: typical physical scale if skill matrix not yet attached
            var_scales = {"temperature_2m": 2.5, "surface_pressure": 15.0, "wind_speed_10m": 3.0}
            df["hist_expected_error"] = df["variable"].map(var_scales).fillna(2.0).astype(float)

        # Spread to skill ratio
        df["spread_skill_ratio"] = (df["ensemble_std"] / (df["hist_expected_error"] + self.eps)).round(4)

        # Overconfidence signal: high when spread is small relative to historical error
        # Normalized in [0, 1]: 1.0 when spread is 0 in high-error regime
        df["overconfidence_signal"] = np.maximum(
            0.0,
            (df["hist_expected_error"] - df["ensemble_std"]) / (df["hist_expected_error"] + self.eps)
        ).round(4)

        # ---------------------------------------------------------
        # 5. Horizon & Astronomical / Cyclical Features
        # ---------------------------------------------------------
        df["lead_hours"] = df["lead_hours"].astype(int)
        df["lead_days"] = (df["lead_hours"] / 24.0).round(3)
        df["lead_decay_factor"] = np.maximum(0.0, 1.0 - (df["lead_hours"] / 240.0)).round(4)

        valid_hour = df["valid_time"].dt.hour
        valid_month = df["valid_time"].dt.month
        valid_dow = df["valid_time"].dt.dayofweek

        df["valid_hour"] = valid_hour
        df["valid_month"] = valid_month
        df["valid_dayofweek"] = valid_dow
        df["is_weekend"] = valid_dow.isin([5, 6]).astype(int)

        # Cyclical harmonics
        df["sin_hour"] = np.sin(2 * np.pi * valid_hour / 24.0).round(5)
        df["cos_hour"] = np.cos(2 * np.pi * valid_hour / 24.0).round(5)
        df["sin_month"] = np.sin(2 * np.pi * valid_month / 12.0).round(5)
        df["cos_month"] = np.cos(2 * np.pi * valid_month / 12.0).round(5)

        # ---------------------------------------------------------
        # 6. Higher-Order Geometry & Distribution Shape
        # ---------------------------------------------------------
        df["ensemble_kurtosis_proxy"] = ((df["ensemble_range"] / (df["ensemble_iqr"] + self.eps)) - 2.5).clip(-10.0, 10.0).round(4)
        df["quantile_spacing_ratio"] = ((df["ensemble_p90"] - df["ensemble_median"]) / (df["ensemble_median"] - df["ensemble_p10"] + self.eps)).clip(0.01, 100.0).round(4)
        df["tail_asymmetry"] = ((df["ensemble_p90"] - df["ensemble_median"]).abs() / (df["ensemble_range"] + self.eps)).clip(0.0, 1.0).round(4)
        df["robust_mad"] = (0.6745 * df["ensemble_iqr"]).round(4)

        # ---------------------------------------------------------
        # 7. Issue-Time Safe Structural Overconfidence & Interactions
        # ---------------------------------------------------------
        rev_24 = df["forecast_revision_mag_24h"].fillna(df["forecast_revision_mag_6h"]).fillna(0.0)
        df["structural_overconfidence_risk"] = (rev_24 * np.sqrt(df["lead_hours"] + 1.0) / (df["ensemble_std"] + 0.1)).clip(0.0, 100.0).round(3)
        df["rapid_change_proxy"] = (df["forecast_revision_mag_6h"].fillna(0.0) / (df["lead_hours"] + 6.0)).round(4)
        df["diurnal_phase_alignment"] = np.cos(2.0 * np.pi * (valid_hour - 14.0) / 24.0).round(4)
        df["spread_x_lead"] = (df["ensemble_std"] * np.log1p(df["lead_hours"].clip(lower=0))).round(4)
        df["cv_x_lead"] = (df["ensemble_cv"] * (df["lead_hours"] / 24.0)).round(4)
        df["revision_x_spread"] = (df["forecast_revision_mag_6h"].fillna(0.0) * df["ensemble_std"]).round(4)

        # Physical variable indicators
        df["is_surface_pressure"] = (df["variable"] == "surface_pressure").astype(float)
        df["is_temperature_2m"] = (df["variable"] == "temperature_2m").astype(float)
        df["is_wind_speed_10m"] = (df["variable"] == "wind_speed_10m").astype(float)

        # ---------------------------------------------------------
        # 8. Spatial Coordinates (for legacy pipelines)
        # ---------------------------------------------------------
        df["latitude"] = df["latitude"].astype(float) if "latitude" in df.columns else 0.0
        df["longitude"] = df["longitude"].astype(float) if "longitude" in df.columns else 0.0

        # ---------------------------------------------------------
        # 9. Training OOD / Novelty Scoring
        # ---------------------------------------------------------
        if "ood_score" in df.columns and not df["ood_score"].isna().all():
            df["ood_score"] = df["ood_score"].fillna(0.0).astype(float)
        elif self.ood_scorer is not None and self.ood_scorer.is_fitted_:
            df["ood_score"] = self.ood_scorer.compute_ood_score(df)
        else:
            # Physical domain sanity heuristic fallback if statistical scorer not fitted
            ood_scores = []
            for _, r in df.iterrows():
                val_raw = r.get("forecast_value")
                val = float(val_raw) if val_raw is not None and not pd.isna(val_raw) else 300.0
                var = str(r.get("variable", "temperature_2m"))
                unit_str = str(r.get("unit", "")).lower()
                score = 0.0
                if var == "temperature_2m":
                    val_k = val + 273.15 if (unit_str in ("c", "celsius") or val < 100.0) else val
                    if val_k > 350.0 or val_k < 200.0:  # Physically extreme / impossible (>77C or <-73C)
                        score = min(100.0, max(45.0, abs(val_k - 300.0) / 10.0 * 20.0))
                elif var == "wind_speed_10m":
                    if val > 60.0 or val < 0.0:
                        score = min(100.0, max(45.0, abs(val - 10.0) / 5.0 * 20.0))
                elif var == "surface_pressure":
                    val_pa = val * 100.0 if (unit_str in ("hpa", "mb", "mbar") or val < 2000.0) else val
                    if val_pa > 110000.0 or val_pa < 50000.0:
                        score = min(100.0, max(45.0, abs(val_pa - 101325.0) / 5000.0 * 20.0))
                ood_scores.append(score)
            df["ood_score"] = pd.Series(ood_scores, index=df.index, dtype=float)

        # Restore exact original input row ordering
        df = df.sort_values(by="_orig_idx").reset_index(drop=True)
        df.drop(columns=["_orig_idx"], inplace=True, errors="ignore")

        # Build feature DataFrame and metadata DataFrame based on requested mode
        if mode == "supercharged":
            feat_list = SUPERCHARGED_PHYSICAL_FEATURES
        elif mode == "canonical":
            feat_list = CANONICAL_26_FEATURES
        else:
            feat_list = EXTENDED_INTELLIGENCE_FEATURES

        X = df[feat_list].copy()
        X = X.replace([np.inf, -np.inf], np.nan)

        meta_cols = ["location", "variable", "issue_time", "valid_time", "lead_hours", "city", "season"]
        meta_cols_present = [c for c in meta_cols if c in df.columns]
        metadata = df[meta_cols_present].copy()

        return X, metadata

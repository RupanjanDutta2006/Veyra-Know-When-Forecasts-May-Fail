"""
Bust Label Engine.

Computes robust forecast bust labels from historical paired forecast-truth datasets.
A forecast bust is defined when the forecast absolute error |forecast_value - truth_value|
exceeds a conditional high-quantile error threshold (default: q95).

Scientific Leakage Invariant:
Thresholds must be fitted strictly on historical training data.
Evaluation and test sets must apply the frozen training-period thresholds without re-fitting.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


DEFAULT_QUANTILES = [0.90, 0.95, 0.975, 0.99]
DEFAULT_PRIMARY_QUANTILE = 0.95
MIN_SAMPLES_FOR_STRATIFICATION = 10


def assign_lead_bin(lead_hours: Union[int, pd.Series]) -> Union[str, pd.Series]:
    """Categorize continuous lead hours into medium-range operational lead bins."""
    bins = [-1, 24, 72, 144, 240, 9999]
    labels = ["day1", "day2_3", "day4_6", "day7_10", "day10_plus"]
    if isinstance(lead_hours, (pd.Series, np.ndarray)):
        return pd.cut(lead_hours, bins=bins, labels=labels).astype(str)
    for i in range(len(bins) - 1):
        if bins[i] < lead_hours <= bins[i + 1]:
            return labels[i]
    return "day10_plus"


class BustLabelEngine:
    """
    Fits and applies conditional quantile error thresholds to generate binary bust labels.
    """

    def __init__(
        self,
        primary_quantile: float = DEFAULT_PRIMARY_QUANTILE,
        sensitivity_quantiles: Optional[List[float]] = None,
        min_samples_per_stratum: int = MIN_SAMPLES_FOR_STRATIFICATION,
        error_column: str = "forecast_abs_error",
    ):
        self.primary_quantile = primary_quantile
        self.sensitivity_quantiles = sensitivity_quantiles or DEFAULT_QUANTILES
        self.min_samples_per_stratum = min_samples_per_stratum
        self.error_column = error_column
        self.thresholds_: Dict[str, Any] = {}
        self.is_fitted_ = False

    def fit(self, df_train: pd.DataFrame) -> "BustLabelEngine":
        """
        Fit conditional error thresholds strictly on the training partition.

        Args:
            df_train: Paired historical DataFrame containing error_column and grouping metadata.

        Returns:
            self (fitted engine).
        """
        if df_train.empty:
            raise ValueError("Cannot fit BustLabelEngine on an empty DataFrame.")
        if self.error_column not in df_train.columns:
            raise ValueError(f"Required error column '{self.error_column}' not found in training DataFrame.")

        df = df_train.copy()
        if "lead_bin" not in df.columns and "lead_hours" in df.columns:
            df["lead_bin"] = assign_lead_bin(df["lead_hours"])

        # Compute quantiles across full sensitivity set + primary
        all_quantiles = sorted(list(set(self.sensitivity_quantiles + [self.primary_quantile])))

        fitted_dict: Dict[str, Any] = {
            "meta": {
                "training_sample_count": len(df),
                "primary_quantile": self.primary_quantile,
                "sensitivity_quantiles": self.sensitivity_quantiles,
                "error_column": self.error_column,
            },
            "global_thresholds": {f"q_{int(q*1000)}": float(df[self.error_column].quantile(q)) for q in all_quantiles},
            "variable_thresholds": {},
            "stratified_thresholds": {},  # Key: f"{location}__{variable}__{lead_bin}"
        }

        # 1. Fit per-variable thresholds
        for var, group in df.groupby("variable"):
            if len(group) >= self.min_samples_per_stratum:
                fitted_dict["variable_thresholds"][var] = {
                    f"q_{int(q*1000)}": float(group[self.error_column].quantile(q)) for q in all_quantiles
                }

        # 2. Fit stratified (location + variable + lead_bin) thresholds where sample size supports it
        grouping_cols = ["location", "variable", "lead_bin"]
        available_cols = [c for c in grouping_cols if c in df.columns]

        if len(available_cols) == 3:
            for (loc, var, lbin), group in df.groupby(available_cols):
                if len(group) >= self.min_samples_per_stratum:
                    stratum_key = f"{loc}__{var}__{lbin}"
                    fitted_dict["stratified_thresholds"][stratum_key] = {
                        "count": len(group),
                        **{f"q_{int(q*1000)}": float(group[self.error_column].quantile(q)) for q in all_quantiles}
                    }

        self.thresholds_ = fitted_dict
        self.is_fitted_ = True
        return self

    def _get_threshold_for_row(self, row: pd.Series, quantile: float) -> float:
        """Lookup the appropriate conditional threshold using fallback hierarchy."""
        q_key = f"q_{int(quantile*1000)}"
        loc = row.get("location")
        var = row.get("variable")
        lbin = row.get("lead_bin") or assign_lead_bin(row.get("lead_hours", 0))

        # Level 1: Stratified (location + variable + lead_bin)
        stratum_key = f"{loc}__{var}__{lbin}"
        if stratum_key in self.thresholds_.get("stratified_thresholds", {}):
            return self.thresholds_["stratified_thresholds"][stratum_key][q_key]

        # Level 2: Variable-level threshold
        if var in self.thresholds_.get("variable_thresholds", {}):
            return self.thresholds_["variable_thresholds"][var][q_key]

        # Level 3: Global threshold fallback
        return self.thresholds_["global_thresholds"][q_key]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply fitted thresholds to compute bust_label (0/1), threshold_applied, and sensitivity labels.

        Args:
            df: Historical paired DataFrame.

        Returns:
            DataFrame with added bust labeling columns.
        """
        if not self.is_fitted_:
            raise RuntimeError("BustLabelEngine must be fitted on training data before transform().")

        df_out = df.copy()
        if "lead_bin" not in df_out.columns and "lead_hours" in df_out.columns:
            df_out["lead_bin"] = assign_lead_bin(df_out["lead_hours"])

        # 1. Primary bust threshold and binary label (q95)
        applied_thresholds = df_out.apply(lambda r: self._get_threshold_for_row(r, self.primary_quantile), axis=1)
        df_out["bust_threshold"] = applied_thresholds
        df_out["bust_label"] = (df_out[self.error_column] >= applied_thresholds).astype(int)

        # 2. Ambiguity / Gray-band: between q90 and q95
        q90_thresholds = df_out.apply(lambda r: self._get_threshold_for_row(r, 0.90), axis=1)
        df_out["is_ambiguous_zone"] = (df_out[self.error_column] >= q90_thresholds) & (df_out[self.error_column] < applied_thresholds)

        # 3. Sensitivity labels across all requested quantiles
        for q in self.sensitivity_quantiles:
            q_thresh = df_out.apply(lambda r: self._get_threshold_for_row(r, q), axis=1)
            q_col_suffix = str(int(q * 1000)).rstrip("0")
            df_out[f"bust_label_q{q_col_suffix}"] = (df_out[self.error_column] >= q_thresh).astype(int)

        return df_out

    def fit_transform(self, df_train: pd.DataFrame) -> pd.DataFrame:
        """Fit on training data and return labeled DataFrame."""
        return self.fit(df_train).transform(df_train)

    def save_thresholds(self, path: Union[str, Path]) -> None:
        """Persist fitted thresholds to a JSON file."""
        if not self.is_fitted_:
            raise RuntimeError("Engine has not been fitted.")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.thresholds_, f, indent=2)

    def load_thresholds(self, path: Union[str, Path]) -> "BustLabelEngine":
        """Load frozen thresholds from a JSON file."""
        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            self.thresholds_ = json.load(f)
        self.primary_quantile = self.thresholds_["meta"]["primary_quantile"]
        self.sensitivity_quantiles = self.thresholds_["meta"]["sensitivity_quantiles"]
        self.error_column = self.thresholds_["meta"]["error_column"]
        self.is_fitted_ = True
        return self

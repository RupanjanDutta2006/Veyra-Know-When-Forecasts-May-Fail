"""
Veyra Research — Calibration Comparison Framework
Empirically benchmarks Global Calibration vs Lead-Conditioned Calibration.

SCIENTIFIC PRINCIPLES:
- Calibration models must be fitted strictly on the held-out validation partition.
- Test partition remains untouched until evaluation.
- Lead-conditioned calibration is NOT assumed to be superior; it must be empirically justified via Brier Score and ECE reductions.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from research.contract.dataset_contract import CANONICAL_LEADS
from research.evaluation.metrics import (
    calculate_brier_skill_score,
    calculate_ece,
    calculate_pr_auc,
)


@dataclass
class CalibrationComparisonReport:
    """Standardized report comparing uncalibrated, global, and lead-conditioned calibrators."""
    raw_brier_score: float
    raw_ece: float
    global_calibrated_brier_score: float
    global_calibrated_ece: float
    lead_conditioned_brier_score: float
    lead_conditioned_ece: float
    brier_improvement_lead_conditioned_vs_global: float
    ece_improvement_lead_conditioned_vs_global: float
    lead_wise_ece_comparison: Dict[int, Dict[str, float]]
    recommended_calibration_strategy: str
    validation_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CalibrationEvaluator:
    """
    Fits and compares global vs lead-stratified calibrators.
    """

    def __init__(self, method: str = "isotonic", target_leads: Optional[List[int]] = None):
        self.method = method
        self.target_leads = target_leads or CANONICAL_LEADS
        self.global_calibrator = None
        self.lead_calibrators: Dict[int, Any] = {}
        self.is_fitted_ = False

    def fit_on_validation(
        self,
        df_val: pd.DataFrame,
        raw_prob_col: str = "raw_prob",
        label_col: str = "bust_label",
        lead_col: str = "lead_hours",
    ) -> "CalibrationEvaluator":
        """
        Fit global and lead-conditioned calibrators strictly on validation partition.
        """
        if df_val.empty:
            raise ValueError("Cannot fit calibrators on empty validation partition.")

        val_clean = df_val.dropna(subset=[raw_prob_col, label_col])
        p_val = val_clean[raw_prob_col].values.astype(float)
        y_val = val_clean[label_col].values.astype(int)

        # 1. Global Calibrator
        if self.method == "isotonic":
            self.global_calibrator = IsotonicRegression(out_of_bounds="clip")
            self.global_calibrator.fit(p_val, y_val)
        else:
            self.global_calibrator = LogisticRegression()
            self.global_calibrator.fit(p_val.reshape(-1, 1), y_val)

        # 2. Lead-Conditioned Calibrators
        self.lead_calibrators = {}
        for lead in self.target_leads:
            sub = val_clean[val_clean[lead_col] == lead]
            if len(sub) >= 20 and len(np.unique(sub[label_col])) > 1:
                p_lead = sub[raw_prob_col].values.astype(float)
                y_lead = sub[label_col].values.astype(int)
                if self.method == "isotonic":
                    cal = IsotonicRegression(out_of_bounds="clip")
                    cal.fit(p_lead, y_lead)
                else:
                    cal = LogisticRegression()
                    cal.fit(p_lead.reshape(-1, 1), y_lead)
                self.lead_calibrators[lead] = cal
            else:
                # Fallback to global calibrator if insufficient stratum samples
                self.lead_calibrators[lead] = self.global_calibrator

        self.is_fitted_ = True
        return self

    def evaluate_on_test(
        self,
        df_test: pd.DataFrame,
        raw_prob_col: str = "raw_prob",
        label_col: str = "bust_label",
        lead_col: str = "lead_hours",
    ) -> CalibrationComparisonReport:
        """
        Evaluates uncalibrated, global calibrated, and lead-conditioned predictions on held-out test data.
        """
        if not self.is_fitted_:
            raise RuntimeError("Calibrator must be fitted on validation partition before evaluating on test.")

        test_clean = df_test.dropna(subset=[raw_prob_col, label_col]).copy()
        p_raw = test_clean[raw_prob_col].values.astype(float)
        y_test = test_clean[label_col].values.astype(int)
        leads = test_clean[lead_col].values.astype(int)

        # Apply Global Calibrator
        if self.method == "isotonic":
            p_global = self.global_calibrator.predict(p_raw)
        else:
            p_global = self.global_calibrator.predict_proba(p_raw.reshape(-1, 1))[:, 1]
        p_global = np.clip(p_global, 0.0, 1.0)

        # Apply Lead-Conditioned Calibrators
        p_lead_cond = np.zeros_like(p_raw)
        for lead in np.unique(leads):
            mask = (leads == lead)
            cal = self.lead_calibrators.get(int(lead), self.global_calibrator)
            if self.method == "isotonic":
                p_lead_cond[mask] = cal.predict(p_raw[mask])
            else:
                p_lead_cond[mask] = cal.predict_proba(p_raw[mask].reshape(-1, 1))[:, 1]
        p_lead_cond = np.clip(p_lead_cond, 0.0, 1.0)

        # Compute Metrics
        bs_raw = float(np.mean((p_raw - y_test) ** 2))
        ece_raw = calculate_ece(p_raw, y_test)["ece"]

        bs_global = float(np.mean((p_global - y_test) ** 2))
        ece_global = calculate_ece(p_global, y_test)["ece"]

        bs_lead = float(np.mean((p_lead_cond - y_test) ** 2))
        ece_lead = calculate_ece(p_lead_cond, y_test)["ece"]

        # Lead-wise comparisons
        lead_ece_comp: Dict[int, Dict[str, float]] = {}
        for lead in self.target_leads:
            mask = (leads == lead)
            if np.sum(mask) >= 5:
                lead_ece_comp[int(lead)] = {
                    "ece_raw": round(calculate_ece(p_raw[mask], y_test[mask])["ece"], 4),
                    "ece_global": round(calculate_ece(p_global[mask], y_test[mask])["ece"], 4),
                    "ece_lead_conditioned": round(calculate_ece(p_lead_cond[mask], y_test[mask])["ece"], 4),
                }

        # Recommendation logic based on test performance
        if ece_lead < ece_global and bs_lead <= bs_global:
            rec = "LEAD_CONDITIONED_CALIBRATION"
        else:
            rec = "GLOBAL_CALIBRATION"

        return CalibrationComparisonReport(
            raw_brier_score=round(bs_raw, 4),
            raw_ece=round(ece_raw, 4),
            global_calibrated_brier_score=round(bs_global, 4),
            global_calibrated_ece=round(ece_global, 4),
            lead_conditioned_brier_score=round(bs_lead, 4),
            lead_conditioned_ece=round(ece_lead, 4),
            brier_improvement_lead_conditioned_vs_global=round(bs_global - bs_lead, 4),
            ece_improvement_lead_conditioned_vs_global=round(ece_global - ece_lead, 4),
            lead_wise_ece_comparison=lead_ece_comp,
            recommended_calibration_strategy=rec,
            validation_status="EMPIRICALLY_VALIDATED_ON_TEST",
        )

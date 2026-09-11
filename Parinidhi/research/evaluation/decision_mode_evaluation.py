"""
Veyra Research — Decision Mode Utility Evaluation
Evaluates the operational effectiveness and decision utility of the 5 product decision modes:
HIGH_TRUST, CAUTION, RECHECK_SOON, DO_NOT_RELY_SOLELY, ABSTAIN.

SCIENTIFIC PRINCIPLE:
Separates ML Model Probability (unbiased statistical estimation) from
Product Decision Policy (loss-asymmetric operational heuristic).
Quantifies whether dispatching under HIGH_TRUST and hedging under DO_NOT_RELY_SOLELY
generates positive net utility under cost-loss asymmetric scenarios.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd


@dataclass
class DecisionModePerformance:
    """Operational performance profile for a specific decision mode."""
    mode: str
    sample_count: int
    frequency_pct: float
    mean_predicted_prob: float
    observed_bust_rate: float
    safe_execution_rate: float            # Fraction of non-bust forecasts (1 - bust_rate)
    mean_lead_hours: float
    mean_stability_index: float
    operational_loss_cost_ratio: float   # Ratio of bust cost incurred vs baseline
    alignment_status: str                # 'CONCORDANT' | 'OVER_CONSERVATIVE' | 'UNDER_CONSERVATIVE'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionUtilityReport:
    """Evaluates decision modes under parameterized asymmetric cost-loss matrices."""
    total_evaluated_forecasts: int
    mode_profiles: Dict[str, DecisionModePerformance]
    cost_loss_c_over_l: float            # C/L ratio (e.g., 0.10)
    policy_expected_loss: float
    climatology_expected_loss: float
    value_of_decision_policy_score: float # Relative economic value: (Loss_clim - Loss_policy) / (Loss_clim - Loss_perfect)
    scientific_disclaimer: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DecisionModeEvaluator:
    """
    Evaluates empirical safety and cost-loss utility of product decision modes.
    """

    MODES = ["HIGH_TRUST", "CAUTION", "RECHECK_SOON", "DO_NOT_RELY_SOLELY", "ABSTAIN"]

    def __init__(self, cost_of_protection: float = 1.0, loss_of_unprotected_bust: float = 10.0):
        self.cost_of_protection = cost_of_protection
        self.loss_of_unprotected_bust = loss_of_unprotected_bust
        self.c_over_l = cost_of_protection / loss_of_unprotected_bust

    def evaluate_modes(
        self,
        df_eval: pd.DataFrame,
        mode_col: str = "decision_mode",
        prob_col: str = "pred_prob",
        label_col: str = "bust_label",
        lead_col: str = "lead_hours",
        stab_col: str = "stability_index",
    ) -> DecisionUtilityReport:
        """
        Calculates empirical safety and economic value across decision modes.
        """
        if df_eval.empty or mode_col not in df_eval.columns or label_col not in df_eval.columns:
            return DecisionUtilityReport(
                total_evaluated_forecasts=0,
                mode_profiles={},
                cost_loss_c_over_l=self.c_over_l,
                policy_expected_loss=0.0,
                climatology_expected_loss=0.0,
                value_of_decision_policy_score=0.0,
                scientific_disclaimer="UNVALIDATED: No decision mode data available.",
            )

        df = df_eval.copy()
        total_n = len(df)
        base_rate = float(df[label_col].mean())

        profiles: Dict[str, DecisionModePerformance] = {}
        total_policy_loss = 0.0

        for m in self.MODES:
            sub = df[df[mode_col] == m]
            n_m = len(sub)
            if n_m == 0:
                profiles[m] = DecisionModePerformance(
                    mode=m,
                    sample_count=0,
                    frequency_pct=0.0,
                    mean_predicted_prob=0.0,
                    observed_bust_rate=0.0,
                    safe_execution_rate=1.0,
                    mean_lead_hours=0.0,
                    mean_stability_index=100.0,
                    operational_loss_cost_ratio=0.0,
                    alignment_status="NO_DATA",
                )
                continue

            freq = round(n_m / total_n * 100.0, 2)
            mean_p = float(sub[prob_col].mean()) if prob_col in sub.columns else 0.0
            bust_r = float(sub[label_col].mean())
            safe_r = round(1.0 - bust_r, 4)
            mean_l = float(sub[lead_col].mean()) if lead_col in sub.columns else 24.0
            mean_s = float(sub[stab_col].mean()) if stab_col in sub.columns else 100.0

            # Alignment checks
            if m == "HIGH_TRUST":
                alignment = "CONCORDANT" if bust_r < 0.10 else "UNDER_CONSERVATIVE"
                # In HIGH_TRUST, operator dispatches without protection: incurs loss if bust occurs
                losses = sub[label_col].sum() * self.loss_of_unprotected_bust
            elif m in ("DO_NOT_RELY_SOLELY", "ABSTAIN"):
                alignment = "CONCORDANT" if bust_r >= 0.20 else "OVER_CONSERVATIVE"
                # In DO_NOT_RELY_SOLELY / ABSTAIN, operator protects/buffers: incurs protection cost
                losses = n_m * self.cost_of_protection
            else:
                alignment = "CONCORDANT"
                # In CAUTION / RECHECK_SOON, partial hedging: 0.5 * C + 0.5 * L * y
                losses = n_m * (0.5 * self.cost_of_protection) + sub[label_col].sum() * (0.5 * self.loss_of_unprotected_bust)

            total_policy_loss += losses

            profiles[m] = DecisionModePerformance(
                mode=m,
                sample_count=n_m,
                frequency_pct=freq,
                mean_predicted_prob=round(mean_p, 4),
                observed_bust_rate=round(bust_r, 4),
                safe_execution_rate=safe_r,
                mean_lead_hours=round(mean_l, 1),
                mean_stability_index=round(mean_s, 1),
                operational_loss_cost_ratio=round(losses / max(1.0, n_m * self.cost_of_protection), 3),
                alignment_status=alignment,
            )

        # Baseline Climatology loss: protect always if base_rate > C/L, else protect never
        if base_rate > self.c_over_l:
            clim_loss = total_n * self.cost_of_protection
        else:
            clim_loss = total_n * base_rate * self.loss_of_unprotected_bust

        # Perfect information loss: only protect when y=1
        perfect_loss = total_n * base_rate * self.cost_of_protection

        # Relative Economic Value: V = (L_clim - L_policy) / (L_clim - L_perfect)
        denom = (clim_loss - perfect_loss) if (clim_loss - perfect_loss) > 0 else 1.0
        rel_value = float(np.clip((clim_loss - total_policy_loss) / denom, -1.0, 1.0))

        return DecisionUtilityReport(
            total_evaluated_forecasts=total_n,
            mode_profiles=profiles,
            cost_loss_c_over_l=round(self.c_over_l, 4),
            policy_expected_loss=round(total_policy_loss / total_n, 4),
            climatology_expected_loss=round(clim_loss / total_n, 4),
            value_of_decision_policy_score=round(rel_value, 4),
            scientific_disclaimer=(
                "Decision modes are operational policy heuristics separating raw probabilities from action thresholds. "
                "Economic value scores are evaluated under stylized 10:1 loss-cost assumptions."
            ),
        )

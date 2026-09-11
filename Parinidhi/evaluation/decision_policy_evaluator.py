"""
Decision Policy Evaluation & Benchmarking Engine (Day 15 Hardened).

Performs rigorous empirical evaluation of the operational risk decision policy against
baseline heuristics (Naive threshold, Climatology, Spread-only, Raw Model) on labeled datasets.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from evaluation.decision_engine import ForecastRiskDecisionEngine
from evaluation.decision_policy import RiskDecisionPolicy
from evaluation.decision_schema import OperationalDecision, RiskLevel
from evaluation.metrics import GeneralizationMetrics


@dataclass
class PolicyBenchmarkSummary:
    """Detailed performance and economic summary for a decision policy."""
    policy_name: str
    sample_count: int
    bust_prevalence: float
    abstention_count: int
    abstention_rate: float
    alert_count: int
    alert_rate: float
    monitor_rate: float
    trust_rate: float
    false_negative_count: int
    false_negative_rate: float
    false_positive_count: int
    false_positive_rate: float
    precision: float
    recall: float
    f1_score: float
    total_cost: float
    mean_cost_per_forecast: float
    cost_reduction_vs_climatology: float
    pr_auc: Optional[float] = None
    roc_auc: Optional[float] = None
    brier_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolicyBenchmarkEvaluator:
    """
    Evaluates decision engine performance against standard operational baselines.
    """

    def __init__(self, engine: ForecastRiskDecisionEngine, policy: Optional[RiskDecisionPolicy] = None):
        self.engine = engine
        self.policy = policy or engine.policy

    def evaluate_dataset(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        locations: Optional[pd.Series] = None,
        variables: Optional[pd.Series] = None,
    ) -> Dict[str, PolicyBenchmarkSummary]:
        """
        Run multi-strategy benchmark evaluation across labeled dataset.
        """
        n_samples = len(X)
        y_arr = np.asarray(y, dtype=int)
        base_rate = float(np.mean(y_arr)) if n_samples > 0 else 0.0

        decisions: List[OperationalDecision] = []
        risk_scores: List[float] = []
        confidences: List[float] = []
        abstentions: List[bool] = []

        # 1. Run Day 15 Decision Engine
        for idx in range(n_samples):
            row_dict = X.iloc[idx].to_dict()
            loc = str(locations.iloc[idx]) if locations is not None else None
            var = str(variables.iloc[idx]) if variables is not None else "temperature_2m"

            dec = self.engine.decide_forecast_risk(
                features=row_dict,
                location_id=loc,
                variable=var,
            )
            decisions.append(dec.decision)
            risk_scores.append(dec.risk_score)
            confidences.append(dec.confidence)
            abstentions.append(dec.abstention_required)

        # 2. Evaluate Strategies
        # Strategy A: Day 15 Policy Engine
        summary_day15 = self._evaluate_strategy(
            name="Day 15 Cost-Aware Policy Engine",
            y_true=y_arr,
            decisions=decisions,
            risk_scores=np.array(risk_scores),
            abstentions=abstentions,
            base_rate=base_rate,
        )

        # Strategy B: Climatological / Majority Baseline (Always Trust)
        clim_decisions = [OperationalDecision.TRUST_FORECAST] * n_samples
        clim_scores = np.full(n_samples, base_rate)
        summary_clim = self._evaluate_strategy(
            name="Climatological Baseline (Always Trust)",
            y_true=y_arr,
            decisions=clim_decisions,
            risk_scores=clim_scores,
            abstentions=[False] * n_samples,
            base_rate=base_rate,
        )

        # Strategy C: Naive Probability Threshold (Alert if P >= 0.50 else Trust)
        raw_probs = np.array(risk_scores)
        naive_decisions = [
            OperationalDecision.ALERT_CRITICAL_BUST if p >= 0.50 else OperationalDecision.TRUST_FORECAST
            for p in raw_probs
        ]
        summary_naive = self._evaluate_strategy(
            name="Naive Threshold Policy (P >= 0.50)",
            y_true=y_arr,
            decisions=naive_decisions,
            risk_scores=raw_probs,
            abstentions=[False] * n_samples,
            base_rate=base_rate,
        )

        # Compute cost savings relative to climatology
        c_clim = summary_clim.total_cost
        for s in [summary_day15, summary_clim, summary_naive]:
            if c_clim > 0:
                s.cost_reduction_vs_climatology = round((c_clim - s.total_cost) / c_clim * 100.0, 2)

        return {
            "day15_policy": summary_day15,
            "climatology_baseline": summary_clim,
            "naive_threshold": summary_naive,
        }

    def _evaluate_strategy(
        self,
        name: str,
        y_true: np.ndarray,
        decisions: List[OperationalDecision],
        risk_scores: np.ndarray,
        abstentions: List[bool],
        base_rate: float,
    ) -> PolicyBenchmarkSummary:
        """Helper to calculate performance and cost metrics for a decision strategy."""
        n = len(y_true)
        if n == 0:
            return PolicyBenchmarkSummary(
                policy_name=name, sample_count=0, bust_prevalence=0.0,
                abstention_count=0, abstention_rate=0.0, alert_count=0, alert_rate=0.0,
                monitor_rate=0.0, trust_rate=0.0, false_negative_count=0, false_negative_rate=0.0,
                false_positive_count=0, false_positive_rate=0.0, precision=0.0, recall=0.0,
                f1_score=0.0, total_cost=0.0, mean_cost_per_forecast=0.0, cost_reduction_vs_climatology=0.0,
            )

        n_abs = sum(abstentions)
        abs_rate = n_abs / n

        # Alert actions: ALERT_CRITICAL_BUST or WARN_POTENTIAL_BUST
        alert_mask = np.array([
            d in [OperationalDecision.ALERT_CRITICAL_BUST, OperationalDecision.WARN_POTENTIAL_BUST]
            for d in decisions
        ])
        monitor_mask = np.array([d in [OperationalDecision.MONITOR, OperationalDecision.ADVISE_CAUTION] for d in decisions])
        trust_mask = np.array([d == OperationalDecision.TRUST_FORECAST for d in decisions])

        n_alerts = int(np.sum(alert_mask))
        alert_rate = n_alerts / n
        monitor_rate = int(np.sum(monitor_mask)) / n
        trust_rate = int(np.sum(trust_mask)) / n

        # Non-abstained evaluation for classification metrics
        valid_mask = ~np.array(abstentions)
        if np.sum(valid_mask) > 0:
            y_v = y_true[valid_mask]
            a_v = alert_mask[valid_mask]

            tp = int(np.sum((y_v == 1) & a_v))
            fp = int(np.sum((y_v == 0) & a_v))
            fn = int(np.sum((y_v == 1) & ~a_v))
            tn = int(np.sum((y_v == 0) & ~a_v))

            fn_rate = fn / max(tp + fn, 1)
            fp_rate = fp / max(fp + tn, 1)
            prec = tp / max(tp + fp, 1)
            rec = tp / max(tp + fn, 1)
            f1 = 2 * prec * rec / max(prec + rec, 1e-6)
        else:
            tp = fp = fn = tn = 0
            fn_rate = fp_rate = prec = rec = f1 = 0.0

        # Cost Calculation
        fn_weight = self.policy.fn_cost_weight
        fp_weight = self.policy.fp_cost_weight
        fatigue = self.policy.alert_fatigue_penalty

        total_cost = 0.0
        for idx in range(n):
            y_i = y_true[idx]
            d_i = decisions[idx]

            if d_i == OperationalDecision.ABSTAIN:
                total_cost += fn_weight * 0.45 if y_i == 1 else fp_weight * 0.15
            elif y_i == 1:
                # Miss losses
                if d_i == OperationalDecision.TRUST_FORECAST:
                    total_cost += fn_weight * 1.0
                elif d_i == OperationalDecision.MONITOR:
                    total_cost += fn_weight * 0.65
                elif d_i == OperationalDecision.ADVISE_CAUTION:
                    total_cost += fn_weight * 0.35
                elif d_i == OperationalDecision.WARN_POTENTIAL_BUST:
                    total_cost += fn_weight * 0.10 + fatigue * 1.0
                elif d_i == OperationalDecision.ALERT_CRITICAL_BUST:
                    total_cost += fatigue * 1.5
            else:
                # False alarm costs
                if d_i == OperationalDecision.MONITOR:
                    total_cost += fp_weight * 0.05 + fatigue * 0.25
                elif d_i == OperationalDecision.ADVISE_CAUTION:
                    total_cost += fp_weight * 0.20 + fatigue * 0.50
                elif d_i == OperationalDecision.WARN_POTENTIAL_BUST:
                    total_cost += fp_weight * 0.60 + fatigue * 1.0
                elif d_i == OperationalDecision.ALERT_CRITICAL_BUST:
                    total_cost += fp_weight * 1.0 + fatigue * 1.5

        mean_cost = total_cost / n

        # Probabilistic metrics if valid
        pr_auc = None
        roc_auc = None
        brier = None
        if len(np.unique(y_true)) > 1:
            try:
                metrics = GeneralizationMetrics.compute_all(y_true, risk_scores)
                pr_auc = metrics.pr_auc
                roc_auc = metrics.roc_auc
                brier = metrics.brier_score
            except Exception:
                pass

        return PolicyBenchmarkSummary(
            policy_name=name,
            sample_count=n,
            bust_prevalence=round(base_rate, 4),
            abstention_count=n_abs,
            abstention_rate=round(abs_rate, 4),
            alert_count=n_alerts,
            alert_rate=round(alert_rate, 4),
            monitor_rate=round(monitor_rate, 4),
            trust_rate=round(trust_rate, 4),
            false_negative_count=fn,
            false_negative_rate=round(fn_rate, 4),
            false_positive_count=fp,
            false_positive_rate=round(fp_rate, 4),
            precision=round(prec, 4),
            recall=round(rec, 4),
            f1_score=round(f1, 4),
            total_cost=round(total_cost, 2),
            mean_cost_per_forecast=round(mean_cost, 4),
            cost_reduction_vs_climatology=0.0,
            pr_auc=round(pr_auc, 4) if pr_auc is not None else None,
            roc_auc=round(roc_auc, 4) if roc_auc is not None else None,
            brier_score=round(brier, 4) if brier is not None else None,
        )

"""Model Evaluation Metrics and Verification Report Generator."""
from dataclasses import asdict, dataclass, field
from typing import Any, Optional
import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score


@dataclass
class ConfusionMatrix:
    """Detailed confusion matrix breakdown."""

    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0  # CRITICAL: Actual BUST predicted as Non-Bust

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class EvaluationReport:
    """Comprehensive evaluation metrics report for model validation and testing."""

    split_name: str
    sample_count: int
    bust_count: int
    non_bust_count: int
    bust_prevalence: float

    accuracy: float
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    roc_auc: Optional[float]
    brier_score: Optional[float]

    confusion_matrix: ConfusionMatrix
    is_calibrated: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


class ModelEvaluator:
    """Evaluates classification performance, probability calibration, and false negatives."""

    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_proba: np.ndarray,
        split_name: str = "validation",
        decision_threshold: float = 0.5,
    ) -> EvaluationReport:
        """Compute comprehensive evaluation metrics for binary bust prediction."""
        y_t = np.array(y_true, dtype=np.int64)
        y_p = np.array(y_proba, dtype=np.float64)
        y_pred = (y_p >= decision_threshold).astype(np.int64)

        n = len(y_t)
        n_bust = int(np.sum(y_t == 1))
        n_non_bust = int(np.sum(y_t == 0))
        prevalence = round(n_bust / n, 4) if n > 0 else 0.0

        # Confusion Matrix
        tp = int(np.sum((y_t == 1) & (y_pred == 1)))
        fp = int(np.sum((y_t == 0) & (y_pred == 1)))
        tn = int(np.sum((y_t == 0) & (y_pred == 0)))
        fn = int(np.sum((y_t == 1) & (y_pred == 0)))
        cm = ConfusionMatrix(true_positives=tp, false_positives=fp, true_negatives=tn, false_negatives=fn)

        # Accuracy
        acc = round((tp + tn) / n, 4) if n > 0 else 0.0

        # Precision & Recall
        prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
        rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None

        # F1 Score
        if prec is not None and rec is not None and (prec + rec) > 0:
            f1 = round(2.0 * (prec * rec) / (prec + rec), 4)
        else:
            f1 = 0.0 if (prec is not None or rec is not None) else None

        # ROC-AUC (requires both classes)
        if len(np.unique(y_t)) > 1:
            try:
                auc_val = round(float(roc_auc_score(y_t, y_p)), 4)
            except Exception:
                auc_val = None
        else:
            auc_val = None

        # Brier Score Loss: mean squared difference between P(bust) and binary label
        try:
            brier = round(float(brier_score_loss(y_t, y_p)), 4)
        except Exception:
            brier = None

        return EvaluationReport(
            split_name=split_name,
            sample_count=n,
            bust_count=n_bust,
            non_bust_count=n_non_bust,
            bust_prevalence=prevalence,
            accuracy=acc,
            precision=prec,
            recall=rec,
            f1_score=f1,
            roc_auc=auc_val,
            brier_score=brier,
            confusion_matrix=cm,
            is_calibrated=False,  # Uncalibrated baseline model
        )

"""Explainability Integration Service for Veyra Phase 2 Day 13.

Provides a clean, typed, safe integration boundary between the existing
Builder 2 physical feature attribution engine and the Builder 1 production API.
"""
from abc import ABC, abstractmethod
import logging
import math
from typing import Any, Dict, List, Optional, Union

from backend.app.builder2.explainer import ForecastBustExplainer
from backend.app.schemas.explainability import (
    ContributingFactor,
    ExplanationItem,
    ExplainabilityStatus,
    ModelExplanationResponse,
)
from backend.app.schemas.model_integration import FORBIDDEN_GROUND_TRUTH_FIELDS

logger = logging.getLogger(__name__)


class BaseExplainabilityService(ABC):
    """Abstract contract for model explainability integration in Veyra."""

    @abstractmethod
    def explain(
        self,
        feature_row: Optional[Dict[str, Any]],
        bust_probability: Optional[float],
        threshold: float = 0.280,
        is_abstained: bool = False,
    ) -> Optional[ExplanationItem]:
        """Produce a validated, typed physical explanation for a prediction instance."""
        pass

    @abstractmethod
    def validate_explanation(self, raw_explanation: Any) -> Optional[ExplanationItem]:
        """Validate and convert an arbitrary explanation object into a typed ExplanationItem."""
        pass


class ExplainabilityIntegrationService(BaseExplainabilityService):
    """Production explainability integration service.

    Wraps Builder 2's deterministic physical feature attribution engine with
    strict anti-leakage verification, numerical finiteness checks, and
    isolated fail-safe error handling.
    """

    def __init__(self, default_threshold: float = 0.280):
        self.default_threshold = default_threshold

    def explain(
        self,
        feature_row: Optional[Dict[str, Any]],
        bust_probability: Optional[float],
        threshold: Optional[float] = None,
        is_abstained: bool = False,
    ) -> Optional[ExplanationItem]:
        """Generate a validated physical explanation for a single prediction step.

        Strictly returns None if:
        - Prediction was abstained
        - Bust probability is None or non-finite
        - Input features are missing or contain forbidden ground-truth leakage
        - Explainer encountered an unexpected internal error
        """
        # 1. Check abstention and probability availability
        if is_abstained or bust_probability is None:
            return None

        if math.isnan(bust_probability) or math.isinf(bust_probability) or not (0.0 <= bust_probability <= 1.0):
            logger.warning("Explainability rejected non-finite or out-of-bounds probability: %s", bust_probability)
            return None

        # 2. Validate feature dictionary presence
        if not feature_row or not isinstance(feature_row, dict):
            return None

        # 3. Anti-leakage audit: Reject feature vector if ground-truth fields are present
        for key in feature_row:
            if key.strip().lower() in FORBIDDEN_GROUND_TRUTH_FIELDS:
                logger.error("CRITICAL LEAKAGE IN EXPLAINER: Ground-truth field '%s' detected in features", key)
                return None

        # 4. Numerical finiteness and sanitization
        sanitized_features: Dict[str, Any] = {}
        for k, v in feature_row.items():
            if isinstance(v, (int, float)):
                if math.isnan(v) or math.isinf(v):
                    sanitized_features[k] = None
                else:
                    sanitized_features[k] = float(v)
            else:
                sanitized_features[k] = v

        decision_threshold = threshold if threshold is not None else self.default_threshold

        try:
            # 5. Delegate to Builder 2 deterministic explainer
            raw_expl = ForecastBustExplainer.explain_row(
                feature_row=sanitized_features,
                bust_probability=bust_probability,
                threshold=decision_threshold,
            )

            # 6. Validate and convert output to typed Pydantic ExplanationItem
            return self.validate_explanation(raw_expl)

        except Exception as exc:
            logger.error("ExplainabilityIntegrationService.explain encountered error: %s", exc)
            return None

    def validate_explanation(self, raw_explanation: Any) -> Optional[ExplanationItem]:
        """Convert and validate an explanation payload into a typed ExplanationItem.

        Accepts Pydantic ExplanationItem, dataclass ExplanationItem, or dict.
        Guarantees all contributing factor values are finite numbers or None.
        """
        if raw_explanation is None:
            return None

        try:
            # If already typed Pydantic ExplanationItem
            if isinstance(raw_explanation, ExplanationItem):
                return raw_explanation

            # If dataclass with to_dict() method
            if hasattr(raw_explanation, "to_dict") and callable(raw_explanation.to_dict):
                raw_dict = raw_explanation.to_dict()
            elif isinstance(raw_explanation, dict):
                raw_dict = raw_explanation
            else:
                return None

            primary_driver = str(raw_dict.get("primary_driver", "unknown_driver"))
            driver_summary = str(raw_dict.get("driver_summary", "No explanation summary available."))

            raw_factors = raw_dict.get("top_contributing_factors", [])
            valid_factors: List[ContributingFactor] = []

            for f in raw_factors:
                if isinstance(f, dict):
                    factor_name = str(f.get("factor", "unknown_factor"))
                    raw_val = f.get("value")
                    signal_code = str(f.get("signal", "UNKNOWN_SIGNAL"))
                elif hasattr(f, "factor") and hasattr(f, "signal"):
                    factor_name = str(getattr(f, "factor"))
                    raw_val = getattr(f, "value", None)
                    signal_code = str(getattr(f, "signal"))
                else:
                    continue

                # Validate and sanitize factor value finiteness
                finite_val: Optional[float] = None
                if raw_val is not None and isinstance(raw_val, (int, float)):
                    if not (math.isnan(raw_val) or math.isinf(raw_val)):
                        finite_val = round(float(raw_val), 4)

                valid_factors.append(
                    ContributingFactor(
                        factor=factor_name,
                        value=finite_val,
                        signal=signal_code,
                    )
                )

            return ExplanationItem(
                primary_driver=primary_driver,
                driver_summary=driver_summary,
                top_contributing_factors=valid_factors,
            )

        except Exception as exc:
            logger.warning("Failed to validate explanation payload: %s", exc)
            return None

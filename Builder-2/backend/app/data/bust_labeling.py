"""Bust Labeling Policy Engine for Medium-Range Weather Forecasts.

Provides statistical and configurable policies for defining and assigning
bust labels (|forecast_error| >= threshold) conditional on variable, lead time, and season.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import numpy as np


@dataclass
class BustLabelResult:
    """Standardized output from bust labeling policy evaluation."""

    is_bust: int  # 1 for bust, 0 for no-bust
    threshold: float
    policy_name: str
    absolute_error: float
    details: dict[str, Any] = field(default_factory=dict)


class BaseBustPolicy(ABC):
    """Abstract base class for bust label threshold policies."""

    @abstractmethod
    def evaluate(
        self,
        variable: str,
        absolute_error: float,
        lead_hours: int = 0,
        season: Optional[str] = None,
    ) -> BustLabelResult:
        """Evaluate whether a given absolute error constitutes a forecast bust."""
        pass


class FixedThresholdBustPolicy(BaseBustPolicy):
    """Bust policy using meteorologically grounded fixed error thresholds per variable."""

    DEFAULT_THRESHOLDS: dict[str, float] = {
        "temperature_2m": 3.0,  # 3.0 °C error threshold
        "surface_pressure": 4.0,  # 4.0 hPa error threshold
        "wind_speed_10m": 4.0,  # 4.0 m/s error threshold
        "relative_humidity_2m": 20.0,  # 20% error threshold
        "precipitation": 10.0,  # 10 mm error threshold
        "geopotential_height_500hPa": 60.0,  # 60 gpm error threshold
    }

    def __init__(self, thresholds: Optional[dict[str, float]] = None, default_fallback: float = 5.0):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
        self.default_fallback = default_fallback

    def evaluate(
        self,
        variable: str,
        absolute_error: float,
        lead_hours: int = 0,
        season: Optional[str] = None,
    ) -> BustLabelResult:
        var_clean = variable.lower()
        threshold = self.thresholds.get(var_clean, self.default_fallback)
        is_bust = 1 if absolute_error >= threshold else 0

        return BustLabelResult(
            is_bust=is_bust,
            threshold=threshold,
            policy_name="FixedThresholdPolicy",
            absolute_error=absolute_error,
            details={"variable": var_clean, "lead_hours": lead_hours, "season": season},
        )


class QuantileBustPolicy(BaseBustPolicy):
    """Statistical bust policy setting thresholds at conditional extreme quantiles (e.g. q95, q90).

    Strict Anti-Leakage Requirement:
    Quantiles must be fitted exclusively on the historical training set error distribution.
    """

    def __init__(
        self,
        quantile: float = 0.95,
        min_samples: int = 10,
        fallback_policy: Optional[BaseBustPolicy] = None,
    ):
        if not (0.5 < quantile < 1.0):
            raise ValueError(f"Quantile must be in (0.5, 1.0), got {quantile}")
        self.quantile = quantile
        self.min_samples = min_samples
        self.fallback_policy = fallback_policy or FixedThresholdBustPolicy()
        # Fitted thresholds indexed by (variable, lead_bin)
        self.fitted_thresholds: dict[tuple[str, str], float] = {}

    @staticmethod
    def get_lead_bin(lead_hours: int) -> str:
        """Partition lead time into operational forecasting bins."""
        if lead_hours <= 24:
            return "day1"
        elif lead_hours <= 72:
            return "day2-3"
        elif lead_hours <= 168:
            return "day4-7"
        else:
            return "day8+"

    def fit_from_errors(self, error_records: list[dict[str, Any]]) -> None:
        """Fit empirical extreme quantile thresholds from training error records.

        Each record must contain 'variable', 'lead_hours', and 'absolute_error'.
        """
        # Group absolute errors by (variable, lead_bin)
        grouped_errors: dict[tuple[str, str], list[float]] = {}
        for rec in error_records:
            var = rec["variable"].lower()
            lead_bin = self.get_lead_bin(rec.get("lead_hours", 0))
            key = (var, lead_bin)
            grouped_errors.setdefault(key, []).append(rec["absolute_error"])

        for key, errors in grouped_errors.items():
            if len(errors) >= self.min_samples:
                threshold = float(np.percentile(errors, self.quantile * 100))
                self.fitted_thresholds[key] = round(threshold, 4)

    def evaluate(
        self,
        variable: str,
        absolute_error: float,
        lead_hours: int = 0,
        season: Optional[str] = None,
    ) -> BustLabelResult:
        var_clean = variable.lower()
        lead_bin = self.get_lead_bin(lead_hours)
        key = (var_clean, lead_bin)

        if key in self.fitted_thresholds:
            threshold = self.fitted_thresholds[key]
            is_bust = 1 if absolute_error >= threshold else 0
            policy_name = f"QuantileBustPolicy_q{int(self.quantile * 100)}"
            return BustLabelResult(
                is_bust=is_bust,
                threshold=threshold,
                policy_name=policy_name,
                absolute_error=absolute_error,
                details={"variable": var_clean, "lead_bin": lead_bin, "sample_fit": True},
            )

        # Fallback if specific bin has not been fitted or sample count insufficient
        fallback_res = self.fallback_policy.evaluate(variable, absolute_error, lead_hours, season)
        return BustLabelResult(
            is_bust=fallback_res.is_bust,
            threshold=fallback_res.threshold,
            policy_name=f"QuantileBustPolicy_Fallback({fallback_res.policy_name})",
            absolute_error=absolute_error,
            details={"variable": var_clean, "lead_bin": lead_bin, "sample_fit": False},
        )

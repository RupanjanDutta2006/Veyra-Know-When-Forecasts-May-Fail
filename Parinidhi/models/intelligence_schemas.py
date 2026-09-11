"""
Veyra Forecast Intelligence Response Schemas.

Exposes production contracts for forecast failure risk estimation, reliability index,
overconfidence detection, trajectory stability, and defensible risk driver attribution.
Uses standard Python dataclasses for lightweight, pure-Python zero-dependency runtime portability.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class RiskDriver:
    """Structured risk driver contributing to elevated forecast bust probability."""
    signal_name: str
    signal_value: float
    risk_direction: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForecastReliabilityResult:
    """Primary forecast failure intelligence and reliability response."""
    # Identification
    location: str
    variable: str
    issue_time: str
    valid_time: str
    lead_hours: int

    # Forecast & Ensemble Distribution
    forecast_value: float
    ensemble_mean: float
    ensemble_std: float
    ensemble_range: float
    ensemble_iqr: float
    member_count: int
    unit: str

    # Failure Risk & Reliability
    bust_probability: float
    risk_level: str
    confidence_index: float
    overconfidence_signal: float
    stability_index: float
    ood_score: float

    # Interpretability & Drivers
    dominant_risk_drivers: List[RiskDriver] = field(default_factory=list)

    # Provenance
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dominant_risk_drivers"] = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.dominant_risk_drivers]
        return d

    def dict(self) -> Dict[str, Any]:
        return self.to_dict()

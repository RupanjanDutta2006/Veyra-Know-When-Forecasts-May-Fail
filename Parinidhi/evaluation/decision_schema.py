"""
Forecast Risk Decision Schema & Enums (Day 15).

Defines the formal machine-readable schema, enums, and data containers for
operational forecast-bust risk decisions, warnings, and abstentions.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional
import numpy as np


class RiskLevel(str, Enum):
    """Operational severity of forecast failure risk."""
    LOW = "LOW"
    WATCH = "WATCH"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OperationalDecision(str, Enum):
    """Actionable operational recommendation."""
    TRUST_FORECAST = "TRUST_FORECAST"
    MONITOR = "MONITOR"
    ADVISE_CAUTION = "ADVISE_CAUTION"
    WARN_POTENTIAL_BUST = "WARN_POTENTIAL_BUST"
    ALERT_CRITICAL_BUST = "ALERT_CRITICAL_BUST"
    ABSTAIN = "ABSTAIN"


class WarningPriority(str, Enum):
    """Notification urgency priority."""
    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LOW = "P3_LOW"
    P4_INFORMATIONAL = "P4_INFORMATIONAL"


class DataQualityState(str, Enum):
    """Input data completeness and physical sanity."""
    CLEAN = "CLEAN"
    DEGRADED = "DEGRADED"
    CORRUPTED = "CORRUPTED"
    INSUFFICIENT = "INSUFFICIENT"


def _json_fallback(obj: Any) -> Any:
    """Helper to convert NumPy / custom types to standard Python primitives."""
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [_json_fallback(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_fallback(v) for k, v in obj.items()}
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)


@dataclass
class EvidenceItem:
    """Single item of supporting or contradicting evidence."""
    source: str
    direction: str  # INCREASES_RISK, DECREASES_RISK, NEUTRAL
    strength: float  # [0.0, 1.0]
    confidence: float  # [0.0, 1.0]
    summary: str
    metric_value: Optional[float] = None


@dataclass
class ForecastRiskDecision:
    """
    Formal, machine-readable operational forecast-bust risk decision payload.
    """
    decision_id: str
    decision: OperationalDecision
    risk_level: RiskLevel
    risk_score: float
    raw_bust_probability: float
    calibrated_bust_probability: float
    confidence: float
    confidence_level: str
    uncertainty_level: str
    novelty_level: str
    data_quality_level: DataQualityState
    lead_time_level: str
    warning_priority: WarningPriority
    recommended_action: str
    abstention_required: bool
    abstention_reason: Optional[str] = None
    dominant_risk_drivers: List[Dict[str, Any]] = field(default_factory=list)
    supporting_evidence: List[Dict[str, Any]] = field(default_factory=list)
    contradicting_evidence: List[Dict[str, Any]] = field(default_factory=list)
    evidence_conflict_score: float = 0.0
    historical_analogue_support: Dict[str, Any] = field(default_factory=dict)
    location_reliability: Dict[str, Any] = field(default_factory=dict)
    sensitivity_analysis: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to fully JSON-serializable dictionary."""
        d = asdict(self)
        return _json_fallback(d)

    def to_json(self, indent: int = 2) -> str:
        """Convert to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForecastRiskDecision":
        """Reconstruct decision object from dictionary."""
        return cls(
            decision_id=str(data.get("decision_id", "")),
            decision=OperationalDecision(data.get("decision", OperationalDecision.MONITOR.value)),
            risk_level=RiskLevel(data.get("risk_level", RiskLevel.LOW.value)),
            risk_score=float(data.get("risk_score", 0.0)),
            raw_bust_probability=float(data.get("raw_bust_probability", 0.0)),
            calibrated_bust_probability=float(data.get("calibrated_bust_probability", 0.0)),
            confidence=float(data.get("confidence", 0.5)),
            confidence_level=str(data.get("confidence_level", "MODERATE")),
            uncertainty_level=str(data.get("uncertainty_level", "MODERATE")),
            novelty_level=str(data.get("novelty_level", "NORMAL")),
            data_quality_level=DataQualityState(data.get("data_quality_level", DataQualityState.CLEAN.value)),
            lead_time_level=str(data.get("lead_time_level", "SHORT")),
            warning_priority=WarningPriority(data.get("warning_priority", WarningPriority.P4_INFORMATIONAL.value)),
            recommended_action=str(data.get("recommended_action", "")),
            abstention_required=bool(data.get("abstention_required", False)),
            abstention_reason=data.get("abstention_reason"),
            dominant_risk_drivers=list(data.get("dominant_risk_drivers", [])),
            supporting_evidence=list(data.get("supporting_evidence", [])),
            contradicting_evidence=list(data.get("contradicting_evidence", [])),
            evidence_conflict_score=float(data.get("evidence_conflict_score", 0.0)),
            historical_analogue_support=dict(data.get("historical_analogue_support", {})),
            location_reliability=dict(data.get("location_reliability", {})),
            sensitivity_analysis=dict(data.get("sensitivity_analysis", {})),
            provenance=dict(data.get("provenance", {})),
        )

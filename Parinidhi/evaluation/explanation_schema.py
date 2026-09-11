"""
Composite Failure Explanation Schema & Serializer (Day 14).

Defines the formal, machine-readable composite explanation object representing
the complete failure attribution, uncertainty decomposition, and risk confidence profile.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import numpy as np


def _json_serialize_fallback(obj: Any) -> Any:
    """Helper to convert NumPy / custom types to standard Python primitives."""
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (np.ndarray, list, tuple)):
        return [_json_serialize_fallback(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_serialize_fallback(v) for k, v in obj.items()}
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return str(obj)


@dataclass
class CompositeFailureExplanation:
    """
    Structured, fully serializable forecast failure explanation.
    """
    risk_probability: float
    risk_level: str
    risk_confidence: float
    confidence_level: str
    primary_drivers: List[Dict[str, Any]] = field(default_factory=list)
    uncertainty_components: Dict[str, Any] = field(default_factory=dict)
    novelty: Dict[str, Any] = field(default_factory=dict)
    historical_analogues: Dict[str, Any] = field(default_factory=dict)
    lead_time_context: Dict[str, Any] = field(default_factory=dict)
    location_profile: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        return _json_serialize_fallback(d)

    def to_json(self, indent: int = 2) -> str:
        """Convert to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompositeFailureExplanation":
        """Reconstruct explanation from dictionary."""
        return cls(
            risk_probability=float(data.get("risk_probability", 0.0)),
            risk_level=str(data.get("risk_level", "LOW")),
            risk_confidence=float(data.get("risk_confidence", 0.5)),
            confidence_level=str(data.get("confidence_level", "MODERATE")),
            primary_drivers=list(data.get("primary_drivers", [])),
            uncertainty_components=dict(data.get("uncertainty_components", {})),
            novelty=dict(data.get("novelty", {})),
            historical_analogues=dict(data.get("historical_analogues", {})),
            lead_time_context=dict(data.get("lead_time_context", {})),
            location_profile=dict(data.get("location_profile", {})),
            warnings=list(data.get("warnings", [])),
            provenance=dict(data.get("provenance", {})),
        )

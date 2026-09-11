"""
Temporal Forecast Trajectory & Early-Warning Schema (Day 16).

Defines typed dataclasses and enums for trajectory states, warning horizons,
temporal observation points, and composite trajectory assessments.
Includes strict trajectory integrity auditing.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional


class TrajectoryState(str, Enum):
    """Deterministic classification of forecast failure risk trajectory."""
    STABLE_LOW = "STABLE_LOW"
    RISING_RISK = "RISING_RISK"
    ACCELERATING_RISK = "ACCELERATING_RISK"
    PERSISTENT_HIGH_RISK = "PERSISTENT_HIGH_RISK"
    REVERSING_RISK = "REVERSING_RISK"
    UNSTABLE_SIGNAL = "UNSTABLE_SIGNAL"
    NOVEL_UNTRUSTED = "NOVEL_UNTRUSTED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class WarningHorizon(str, Enum):
    """Operational lead-time urgency horizon."""
    WATCH = "WATCH"                  # > 48h lead or low rising slope
    EARLY_WARNING = "EARLY_WARNING"  # 24-48h lead with accelerating trajectory
    IMMINENT = "IMMINENT"            # 6-24h lead with high persistent risk
    CRITICAL = "CRITICAL"            # 0-6h lead with severe failure probability


@dataclass
class ForecastTrajectoryPoint:
    """A single issue-time observation point within an event trajectory."""
    issue_time_utc: str
    valid_time_utc: str
    lead_hours: float
    forecast_value: float
    ensemble_mean: float
    ensemble_std: float
    calibrated_risk: float
    raw_risk: float
    novelty_score: float = 1.0
    missing_fraction: float = 0.0
    features: Dict[str, float] = field(default_factory=dict)
    location_id: Optional[str] = None
    variable: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForecastTrajectory:
    """
    Ordered sequence of forecast issue states for a SINGLE atmospheric target event.
    Enforces strict invariant: identical (location_id, variable, valid_time_utc).
    """
    location_id: str
    variable: str
    valid_time_utc: str
    points: List[ForecastTrajectoryPoint] = field(default_factory=list)

    @property
    def sequence_length(self) -> int:
        return len(self.points)

    def validate_integrity(self, strict_monotonic_leads: bool = True) -> bool:
        """
        Audit trajectory consistency. Rejects malformed, mixed, or duplicate sequences.
        """
        if not self.points:
            return True

        seen_issues = set()
        prev_issue = None
        prev_lead = None

        for idx, pt in enumerate(self.points):
            # Check target identity alignment
            if pt.location_id and pt.location_id != self.location_id:
                raise ValueError(
                    f"Trajectory location mismatch at index {idx}: point has '{pt.location_id}', "
                    f"trajectory expects '{self.location_id}'."
                )
            if pt.variable and pt.variable != self.variable:
                raise ValueError(
                    f"Trajectory variable mismatch at index {idx}: point has '{pt.variable}', "
                    f"trajectory expects '{self.variable}'."
                )
            if pt.valid_time_utc != self.valid_time_utc:
                raise ValueError(
                    f"Trajectory valid_time mismatch at index {idx}: point has '{pt.valid_time_utc}', "
                    f"trajectory expects '{self.valid_time_utc}'."
                )

            # Check lead time sanity
            if pt.lead_hours < 0.0:
                raise ValueError(f"Negative lead_hours ({pt.lead_hours}) at index {idx}.")

            # Check duplicate issue times
            if pt.issue_time_utc in seen_issues:
                raise ValueError(f"Duplicate issue_time_utc '{pt.issue_time_utc}' detected in trajectory.")
            seen_issues.add(pt.issue_time_utc)

            # Check chronological ordering if previous point exists
            if prev_issue is not None:
                if pt.issue_time_utc < prev_issue:
                    raise ValueError(
                        f"Non-chronological issue_time at index {idx}: '{pt.issue_time_utc}' < previous '{prev_issue}'."
                    )
                if strict_monotonic_leads and prev_lead is not None and pt.lead_hours >= prev_lead:
                    raise ValueError(
                        f"Non-decreasing lead_hours at index {idx}: current {pt.lead_hours} >= previous {prev_lead} "
                        f"for same valid_time target."
                    )

            prev_issue = pt.issue_time_utc
            prev_lead = pt.lead_hours

        return True

    def is_chronologically_sorted(self) -> bool:
        if len(self.points) <= 1:
            return True
        for i in range(1, len(self.points)):
            if self.points[i].issue_time_utc <= self.points[i-1].issue_time_utc:
                return False
        return True

    def sort_chronologically(self) -> "ForecastTrajectory":
        self.points.sort(key=lambda p: p.issue_time_utc)
        return self


@dataclass
class TrajectoryAssessment:
    """Comprehensive early-warning and failure-trajectory assessment."""
    trajectory_id: str
    location_id: str
    variable: str
    valid_time_utc: str
    latest_issue_time_utc: str
    sequence_length: int
    current_risk: float
    risk_slope: float
    risk_acceleration: float
    risk_persistence: float
    spread_slope: float
    revision_velocity: float
    instability_detected: bool
    state: TrajectoryState
    early_warning_score: float
    warning_horizon: WarningHorizon
    trajectory_confidence: float
    instability_reason: Optional[str] = None
    estimated_cycles_to_critical: Optional[float] = None
    estimated_hours_to_critical: Optional[float] = None
    explanation_factors: List[str] = field(default_factory=list)
    historical_analogue_support: Dict[str, Any] = field(default_factory=dict)
    is_safe_for_decision: bool = True
    abstention_triggered: bool = False
    abstention_reason: Optional[str] = None
    provenance_hash: str = ""

    def __post_init__(self):
        if not self.provenance_hash:
            payload = f"{self.trajectory_id}:{self.latest_issue_time_utc}:{self.current_risk:.4f}:{self.state.value}"
            self.provenance_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["warning_horizon"] = self.warning_horizon.value
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

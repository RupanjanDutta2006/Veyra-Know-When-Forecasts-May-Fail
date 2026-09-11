"""
Day 6 Schemas and Data Contracts for Forecast-Bust Sentinel.

Defines typed request, response, status, and provenance data models
for the operational forecast-risk API and service layer.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class DataStatus(str, Enum):
    """Operational data availability status."""
    MODEL_PREDICTION = "MODEL_PREDICTION"
    INSUFFICIENT_FEATURES = "INSUFFICIENT_FEATURES"
    STALE_FORECAST = "STALE_FORECAST"
    SERVICE_ERROR = "SERVICE_ERROR"
    ABSTAINED = "ABSTAINED"


class DecisionMode(str, Enum):
    """Actionable decision support modes for forecast consumers."""
    HIGH_TRUST = "HIGH_TRUST"
    CAUTION = "CAUTION"
    RECHECK_SOON = "RECHECK_SOON"
    DO_NOT_RELY_SOLELY = "DO_NOT_RELY_SOLELY"
    ABSTAIN = "ABSTAIN"



class VerificationStatus(str, Enum):
    """Scientific ground-truth verification status."""
    HISTORICALLY_VERIFIED = "HISTORICALLY_VERIFIED"
    UNVERIFIED_HORIZON_NO_TRUTH = "UNVERIFIED_HORIZON_NO_TRUTH"
    NO_TRUTH_AVAILABLE = "NO_TRUTH_AVAILABLE"


@dataclass
class LocationCoordinates:
    """Geographic coordinate representation."""
    latitude: float
    longitude: float

    def to_dict(self) -> Dict[str, float]:
        return {"latitude": round(self.latitude, 4), "longitude": round(self.longitude, 4)}


@dataclass
class LocationInfo:
    """Location metadata with explicit spatial offset to forecast grid point and climate regime."""
    location_id: str
    country: str
    state_region: str
    city: str
    requested_coordinates: LocationCoordinates
    actual_grid_coordinates: Optional[LocationCoordinates] = None
    spatial_distance_km: Optional[float] = None
    climate_zone: Optional[str] = None
    meteorological_regime: Optional[str] = None
    elevation_m: Optional[float] = None
    is_benchmark: bool = False
    rationale: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "location_id": self.location_id,
            "country": self.country,
            "state_region": self.state_region,
            "city": self.city,
            "requested_coordinates": self.requested_coordinates.to_dict(),
            "actual_grid_coordinates": self.actual_grid_coordinates.to_dict() if self.actual_grid_coordinates else None,
            "spatial_distance_km": round(self.spatial_distance_km, 2) if self.spatial_distance_km is not None else None,
        }
        if self.climate_zone is not None:
            data["climate_zone"] = self.climate_zone
        if self.meteorological_regime is not None:
            data["meteorological_regime"] = self.meteorological_regime
        if self.elevation_m is not None:
            data["elevation_m"] = self.elevation_m
        data["is_benchmark"] = self.is_benchmark
        if self.rationale is not None:
            data["rationale"] = self.rationale
        return data


@dataclass
class ProvenanceInfo:
    """Comprehensive provenance and audit metadata."""
    forecast_source: str
    grid_resolution: str
    model_version: str
    feature_schema_version: str
    prediction_timestamp_utc: str
    truth_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_source": self.forecast_source,
            "grid_resolution": self.grid_resolution,
            "model_version": self.model_version,
            "feature_schema_version": self.feature_schema_version,
            "prediction_timestamp_utc": self.prediction_timestamp_utc,
            "truth_source": self.truth_source,
        }


@dataclass
class ContributingFactor:
    """Individual physical feature contribution."""
    factor: str
    value: Optional[float]
    signal: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor": self.factor,
            "value": round(self.value, 4) if self.value is not None else None,
            "signal": self.signal,
        }


@dataclass
class FailureFingerprintDetail:
    """Rich structured diagnostic for atmospheric forecast failure modes."""
    fingerprint_id: str
    name: str
    description: str
    supporting_signals: List[str] = field(default_factory=list)
    evidence_state: str = "SUPPORTED_BY_SIGNALS"
    interpretation: str = ""
    limitations: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint_id": self.fingerprint_id,
            "name": self.name,
            "description": self.description,
            "supporting_signals": self.supporting_signals,
            "evidence_state": self.evidence_state,
            "interpretation": self.interpretation,
            "limitations": self.limitations,
        }


@dataclass
class TrustTimelineItem:
    """Per-lead-time forecast reliability and trust state."""
    lead_hours: int
    lead_days: float
    bust_probability: Optional[float] = None
    risk_level: Optional[str] = None
    decision_mode: Optional[str] = None
    within_trust_horizon: bool = True
    stability_index: Optional[float] = None
    failure_fingerprint: Optional[str] = None
    is_available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lead_hours": self.lead_hours,
            "lead_days": round(self.lead_days, 2),
            "bust_probability": round(self.bust_probability, 4) if self.bust_probability is not None else None,
            "risk_level": self.risk_level,
            "decision_mode": self.decision_mode,
            "within_trust_horizon": self.within_trust_horizon,
            "stability_index": round(self.stability_index, 1) if self.stability_index is not None else None,
            "failure_fingerprint": self.failure_fingerprint,
            "is_available": self.is_available,
        }


@dataclass
class OperationalTrustHorizonInfo:
    """Operational trust horizon summary across forecast leads."""
    operational_trust_horizon_hours: Optional[int]
    threshold_used: float = 0.35
    threshold_type: str = "product_design_threshold"
    status: str = "WITHIN_HORIZON"
    scientific_note: str = (
        "Pcrit is a configurable research/product design threshold, not a universal scientific constant. "
        "Subject to future empirical validation on the 1,040-cycle dataset."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operational_trust_horizon_hours": self.operational_trust_horizon_hours,
            "threshold_used": self.threshold_used,
            "threshold_type": self.threshold_type,
            "status": self.status,
            "scientific_note": self.scientific_note,
        }


@dataclass
class DecisionGuidance:
    """High-level actionable decision guidance for end users."""
    decision_mode: str
    headline: str
    actionable_recommendation: str
    primary_reason: str
    confidence_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_mode": self.decision_mode,
            "headline": self.headline,
            "actionable_recommendation": self.actionable_recommendation,
            "primary_reason": self.primary_reason,
            "confidence_summary": self.confidence_summary,
        }


@dataclass
class DemoScenarioInfo:
    """Deterministic demonstration fixture descriptor."""
    scenario_id: str
    title: str
    location_id: str
    city: str
    variable: str
    lead_hours: int
    intended_decision_mode: str
    description: str
    disclaimer: str = (
        "Deterministic demonstration fixture clearly labeled as a demo/simulation scenario. "
        "NOT a scientific validation case and must NOT be presented as measured real-world performance evidence."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "location_id": self.location_id,
            "city": self.city,
            "variable": self.variable,
            "lead_hours": self.lead_hours,
            "intended_decision_mode": self.intended_decision_mode,
            "description": self.description,
            "disclaimer": self.disclaimer,
        }


@dataclass
class ExplanationItem:
    """Physical explanation of forecast bust risk."""
    primary_driver: str
    driver_summary: str
    top_contributing_factors: List[ContributingFactor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_driver": self.primary_driver,
            "driver_summary": self.driver_summary,
            "top_contributing_factors": [f.to_dict() for f in self.top_contributing_factors],
        }


@dataclass
class ForecastRiskItem:
    """Single lead-time forecast risk evaluation with V2 intelligence."""
    valid_time: str
    lead_hours: int
    lead_days: float
    variable: str
    forecast_value: float
    ensemble_mean: float
    ensemble_std: float
    unit: str
    bust_probability: float
    bust_alert: bool
    data_status: str
    verification_status: str
    explanation: ExplanationItem
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    confidence_index: Optional[float] = None
    structural_overconfidence: Optional[float] = None
    stability_index: Optional[float] = None
    ood_score: Optional[float] = None
    failure_fingerprint: Optional[str] = None
    uncertainty_pct: Optional[float] = None
    dominant_risk_drivers: List[Dict[str, Any]] = field(default_factory=list)
    decision_mode: Optional[str] = None
    recommended_action: Optional[str] = None
    within_trust_horizon: Optional[bool] = None
    failure_fingerprint_detail: Optional[FailureFingerprintDetail] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "valid_time": self.valid_time,
            "lead_hours": self.lead_hours,
            "lead_days": round(self.lead_days, 2),
            "variable": self.variable,
            "forecast_value": round(self.forecast_value, 4),
            "ensemble_mean": round(self.ensemble_mean, 4),
            "ensemble_std": round(self.ensemble_std, 4),
            "unit": self.unit,
            "bust_probability": round(self.bust_probability, 4),
            "bust_alert": self.bust_alert,
            "data_status": self.data_status,
            "verification_status": self.verification_status,
            "confidence": self.confidence,
            "explanation": self.explanation.to_dict() if hasattr(self.explanation, "to_dict") else self.explanation,
        }
        if self.risk_level is not None:
            d["risk_level"] = self.risk_level
        if self.confidence_index is not None:
            d["confidence_index"] = round(self.confidence_index, 1)
        if self.structural_overconfidence is not None:
            d["structural_overconfidence"] = round(self.structural_overconfidence, 4)
        if self.stability_index is not None:
            d["stability_index"] = round(self.stability_index, 1)
        if self.ood_score is not None:
            d["ood_score"] = round(self.ood_score, 2)
        if self.failure_fingerprint is not None:
            d["failure_fingerprint"] = self.failure_fingerprint
        if self.uncertainty_pct is not None:
            d["uncertainty_pct"] = round(self.uncertainty_pct, 2)
        if self.dominant_risk_drivers:
            d["dominant_risk_drivers"] = self.dominant_risk_drivers
        if self.decision_mode is not None:
            d["decision_mode"] = self.decision_mode
        if self.recommended_action is not None:
            d["recommended_action"] = self.recommended_action
        if self.within_trust_horizon is not None:
            d["within_trust_horizon"] = self.within_trust_horizon
        if self.failure_fingerprint_detail is not None:
            d["failure_fingerprint_detail"] = self.failure_fingerprint_detail.to_dict()
        return d


@dataclass
class ForecastRiskResponse:
    """Complete operational response for single location forecast risk."""
    request_id: str
    location: LocationInfo
    issue_time: str
    model_version: str
    decision_threshold: float
    provenance: ProvenanceInfo
    forecasts: List[ForecastRiskItem]
    operational_trust_horizon: Optional[OperationalTrustHorizonInfo] = None
    decision_guidance: Optional[DecisionGuidance] = None
    trust_timeline: List[TrustTimelineItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "request_id": self.request_id,
            "location": self.location.to_dict(),
            "issue_time": self.issue_time,
            "model_version": self.model_version,
            "decision_threshold": self.decision_threshold,
            "provenance": self.provenance.to_dict(),
            "forecasts": [f.to_dict() for f in self.forecasts],
        }
        if self.operational_trust_horizon is not None:
            res["operational_trust_horizon"] = self.operational_trust_horizon.to_dict()
        if self.decision_guidance is not None:
            res["decision_guidance"] = self.decision_guidance.to_dict()
        if self.trust_timeline:
            res["trust_timeline"] = [t.to_dict() for t in self.trust_timeline]
        return res


@dataclass
class RegionalLocationSummary:
    """Per-location summary within a regional aggregation."""
    location_id: str
    city: str
    peak_bust_probability: float
    has_active_alert: bool
    worst_lead_hours: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            "city": self.city,
            "peak_bust_probability": round(self.peak_bust_probability, 4),
            "has_active_alert": self.has_active_alert,
            "worst_lead_hours": self.worst_lead_hours,
        }


@dataclass
class RegionalRiskSummaryResponse:
    """
    State/Region aggregation summary.
    
    CRITICAL: Output fields are spatial summaries across monitored locations,
    NOT calibrated state-level probabilities.
    """
    region_name: str
    location_count: int
    regional_peak_bust_probability: float
    regional_alert_fraction: float
    worst_risk_lead_hours: int
    dominant_risk_variable: str
    locations_summary: List[RegionalLocationSummary]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_name": self.region_name,
            "location_count": self.location_count,
            "regional_peak_bust_probability": round(self.regional_peak_bust_probability, 4),
            "regional_alert_fraction": round(self.regional_alert_fraction, 4),
            "worst_risk_lead_hours": self.worst_risk_lead_hours,
            "dominant_risk_variable": self.dominant_risk_variable,
            "locations_summary": [loc.to_dict() for loc in self.locations_summary],
        }

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
    """Location metadata with explicit spatial offset to forecast grid point."""
    location_id: str
    country: str
    state_region: str
    city: str
    requested_coordinates: LocationCoordinates
    actual_grid_coordinates: Optional[LocationCoordinates] = None
    spatial_distance_km: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            "country": self.country,
            "state_region": self.state_region,
            "city": self.city,
            "requested_coordinates": self.requested_coordinates.to_dict(),
            "actual_grid_coordinates": self.actual_grid_coordinates.to_dict() if self.actual_grid_coordinates else None,
            "spatial_distance_km": round(self.spatial_distance_km, 2) if self.spatial_distance_km is not None else None,
        }


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
    """Single lead-time forecast risk evaluation."""
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
    confidence: Optional[float] = None  # None until real OOD/calibration confidence layer is implemented

    def to_dict(self) -> Dict[str, Any]:
        return {
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
            "explanation": self.explanation.to_dict(),
        }


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "location": self.location.to_dict(),
            "issue_time": self.issue_time,
            "model_version": self.model_version,
            "decision_threshold": self.decision_threshold,
            "provenance": self.provenance.to_dict(),
            "forecasts": [f.to_dict() for f in self.forecasts],
        }


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

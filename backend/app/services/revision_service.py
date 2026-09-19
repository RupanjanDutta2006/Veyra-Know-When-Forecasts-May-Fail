"""Forecast Revision and Trajectory Intelligence for Veyra Phase 3 Day 30.

The repository currently has no durable, provider-verified archive containing
multiple forecast issue cycles for the same target. Production responses must
therefore preserve revision fields as unavailable instead of manufacturing
history from repeated requests or caller-provided timestamps.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Optional
import uuid

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    TrustState,
)
from backend.app.schemas.revision import (
    EnsembleRevisionDiagnostics,
    ForecastRevisionRequest,
    ForecastRevisionResponse,
    RevisionDirection,
    RevisionStatus,
    RevisionUnits,
    TrajectoryDiagnostics,
)
from backend.app.services.location_service import BaseLocationService, DynamicLocationService

logger = logging.getLogger(__name__)

REVISION_HISTORY_UNAVAILABLE = "REVISION_HISTORY_UNAVAILABLE"

VARIABLE_UNIT_MAP = {
    "temperature_2m": "°C",
    "wind_speed_10m": "m/s",
    "surface_pressure": "hPa",
}


def calculate_trajectory_diagnostics(
    current_value: float,
    previous_value: float,
) -> TrajectoryDiagnostics:
    """Apply the frozen revision definition: CURRENT minus PREVIOUS."""
    delta = round(current_value - previous_value, 3)
    if delta > 0:
        direction = RevisionDirection.INCREASED
    elif delta < 0:
        direction = RevisionDirection.DECREASED
    else:
        direction = RevisionDirection.UNCHANGED
    return TrajectoryDiagnostics(
        current_value=round(current_value, 2),
        previous_value=round(previous_value, 2),
        revision_delta=delta,
        absolute_revision=round(abs(delta), 3),
        direction=direction,
    )


def calculate_ensemble_revision(
    current_mean: Optional[float],
    previous_mean: Optional[float],
    current_spread: Optional[float],
    previous_spread: Optional[float],
) -> EnsembleRevisionDiagnostics:
    """Calculate ensemble deltas only when both comparable values exist."""
    mean_delta = (
        round(current_mean - previous_mean, 3)
        if current_mean is not None and previous_mean is not None
        else None
    )
    spread_delta = (
        round(current_spread - previous_spread, 3)
        if current_spread is not None and previous_spread is not None
        else None
    )
    return EnsembleRevisionDiagnostics(
        current_mean=round(current_mean, 2) if current_mean is not None else None,
        previous_mean=round(previous_mean, 2) if previous_mean is not None else None,
        mean_delta=mean_delta,
        current_spread=round(current_spread, 3) if current_spread is not None else None,
        previous_spread=round(previous_spread, 3) if previous_spread is not None else None,
        spread_delta=spread_delta,
    )


class RevisionService:
    """Evaluate current V3 risk while honestly withholding unsupported history."""

    def __init__(
        self,
        location_service: Optional[BaseLocationService] = None,
        agent: Optional[ForecastBustAgent] = None,
    ):
        self.location_service = location_service or DynamicLocationService()
        self._agent = agent

    def _get_agent(self) -> Any:
        if self._agent is None:
            from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent

            self._agent = get_forecast_bust_agent()
        return self._agent

    @staticmethod
    def _reason_values(reason_codes: list[Any]) -> list[str]:
        return [getattr(code, "value", str(code)) for code in reason_codes]

    @staticmethod
    def _scope(lead_hours: int) -> tuple[bool, str]:
        within_benchmark = lead_hours <= 240
        return (
            within_benchmark,
            "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE"
            if within_benchmark
            else "EXTENDED_OPERATIONAL_HORIZON",
        )

    def evaluate_revision(self, request: ForecastRevisionRequest) -> ForecastRevisionResponse:
        request_id = f"rev_{uuid.uuid4().hex[:12]}"
        resolved = self.location_service.resolve(request.location)
        lead_hours = request.lead_hours

        if request.issue_time and request.valid_time:
            issue_dt = datetime.fromisoformat(request.issue_time.replace("Z", "+00:00"))
            valid_dt = datetime.fromisoformat(request.valid_time.replace("Z", "+00:00"))
            lead_hours = int((valid_dt - issue_dt).total_seconds() // 3600)
        else:
            # This is an evaluation anchor, not a claimed provider issue cycle.
            issue_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            valid_dt = issue_dt + timedelta(hours=lead_hours)

        issue_iso = issue_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        valid_iso = valid_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lead_days = round(lead_hours / 24.0, 4)
        within_benchmark, scientific_scope = self._scope(lead_hours)

        if resolved is None or resolved.latitude is None or resolved.longitude is None:
            from backend.app.core.metrics import default_metrics

            default_metrics.record_abstention(ReasonCode.INVALID_LOCATION.value)
            return ForecastRevisionResponse(
                status=RevisionStatus.ABSTAINED,
                location=request.location,
                resolved_name=None,
                latitude=None,
                longitude=None,
                variable=request.variable,
                lead_hours=lead_hours,
                lead_days=lead_days,
                current_issue_time=None,
                previous_issue_time=None,
                valid_time=None,
                trajectory=None,
                ensemble_revision=None,
                trajectory_points=[],
                current_value=None,
                previous_value=None,
                revision_delta=None,
                units=None,
                bust_probability=None,
                previous_bust_probability=None,
                bust_probability_delta=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                calibration_status=CalibrationStatus.UNAVAILABLE.value,
                scientific_scope=scientific_scope,
                is_certified_horizon=within_benchmark,
                history_is_durable=False,
                history_source=None,
                abstain=True,
                reason_codes=[ReasonCode.INVALID_LOCATION.value],
                request_id=request_id,
            )

        prediction_request = PredictionRequest(
            location=request.location,
            variable=request.variable,
            issue_time=issue_iso,
            valid_time=valid_iso,
        )
        prediction: PredictionResponse = self._get_agent().analyze(prediction_request)
        reasons = self._reason_values(prediction.reason_codes or [])

        if prediction.abstain:
            status = RevisionStatus.ABSTAINED
        else:
            status = RevisionStatus.INSUFFICIENT_HISTORY
            if REVISION_HISTORY_UNAVAILABLE not in reasons:
                reasons.append(REVISION_HISTORY_UNAVAILABLE)

        unit_label = VARIABLE_UNIT_MAP[request.variable]
        units = None
        if not prediction.abstain:
            units = RevisionUnits(
                value=unit_label,
                revision_delta=unit_label,
                absolute_revision=unit_label,
                ensemble_mean=unit_label,
                ensemble_spread=unit_label,
            )

        logger.info(
            "event=revision_history_unavailable location=%s variable=%s valid_time=%s",
            resolved.name,
            request.variable,
            valid_iso,
        )
        return ForecastRevisionResponse(
            status=status,
            location=request.location,
            resolved_name=resolved.name,
            latitude=resolved.latitude,
            longitude=resolved.longitude,
            variable=request.variable,
            lead_hours=lead_hours,
            lead_days=lead_days,
            current_issue_time=None,
            previous_issue_time=None,
            valid_time=valid_iso,
            trajectory=None,
            ensemble_revision=None,
            trajectory_points=[],
            current_value=None,
            previous_value=None,
            revision_delta=None,
            units=units,
            bust_probability=prediction.bust_probability,
            previous_bust_probability=None,
            bust_probability_delta=None,
            risk_level=prediction.risk_level,
            trust_state=prediction.trust_state,
            calibration_status=prediction.calibration_status,
            scientific_scope=scientific_scope,
            is_certified_horizon=within_benchmark,
            history_is_durable=False,
            history_source=None,
            abstain=prediction.abstain,
            reason_codes=reasons,
            request_id=request_id,
        )


_default_revision_service = RevisionService()


def get_revision_service() -> RevisionService:
    """Dependency provider for the stateless revision service."""
    return _default_revision_service

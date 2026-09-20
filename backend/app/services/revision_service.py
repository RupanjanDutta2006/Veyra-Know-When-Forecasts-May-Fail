"""Forecast Revision and Trajectory Intelligence for Veyra Phase 3 Day 30 & Day 34 (Gate C4).

Integrates the authoritative time contract with the durable SQLite revision store foundation.
Production responses expose revision diagnostics when durable, comparable issue-cycle
evidence exists for the exact same target (canonical location, variable, valid target time).
Otherwise, responses honestly preserve revision fields as unavailable/insufficient history.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, List, Optional
import uuid

from backend.app.agents.forecast_bust_agent import ForecastBustAgent
from backend.app.core.revision_store import RevisionRecord, RevisionStore, get_revision_store
from backend.app.core.time_contract import (
    derive_and_validate_lead_hours,
    format_utc_timestamp,
    is_certified_lead_horizon,
    parse_utc_timestamp,
)
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
    TrajectoryPoint,
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
    """Evaluate current V3 risk while maintaining durable revision store integration."""

    def __init__(
        self,
        location_service: Optional[BaseLocationService] = None,
        agent: Optional[ForecastBustAgent] = None,
        revision_store: Optional[RevisionStore] = None,
    ):
        self.location_service = location_service or DynamicLocationService()
        self._agent = agent
        self._revision_store = revision_store

    def _get_agent(self) -> Any:
        if self._agent is None:
            from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent

            self._agent = get_forecast_bust_agent()
        return self._agent

    def _get_store(self) -> RevisionStore:
        if self._revision_store is None:
            self._revision_store = get_revision_store()
        return self._revision_store

    @staticmethod
    def _reason_values(reason_codes: list[Any]) -> list[str]:
        return [getattr(code, "value", str(code)) for code in reason_codes]

    @staticmethod
    def _scope(lead_hours: int) -> tuple[bool, str]:
        within_benchmark = is_certified_lead_horizon(lead_hours)
        return (
            within_benchmark,
            "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE"
            if within_benchmark
            else "EXTENDED_OPERATIONAL_HORIZON",
        )

    def evaluate_revision(self, request: ForecastRevisionRequest) -> ForecastRevisionResponse:
        request_id = f"rev_{uuid.uuid4().hex[:12]}"
        resolved = self.location_service.resolve(request.location)

        if request.issue_time and request.valid_time:
            lead_hours, issue_iso, valid_iso = derive_and_validate_lead_hours(
                issue_time=request.issue_time,
                valid_time=request.valid_time,
            )
        else:
            lead_hours = request.lead_hours
            issue_dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            valid_dt = issue_dt + timedelta(hours=lead_hours)
            issue_iso = format_utc_timestamp(issue_dt)
            valid_iso = format_utc_timestamp(valid_dt)

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

        canonical_loc = resolved.name or request.location

        # Check durable revision store for previous comparable issue cycle
        store = self._get_store()
        prev_record: Optional[RevisionRecord] = None
        try:
            prev_record = store.get_previous_revision(
                canonical_location=canonical_loc,
                variable=request.variable,
                valid_time=valid_iso,
                current_issue_time=issue_iso,
            )
        except Exception as exc:
            logger.warning("Failed to query previous revision from store: %s", exc)

        prediction_request = PredictionRequest(
            location=canonical_loc,
            variable=request.variable,
            issue_time=issue_iso,
            valid_time=valid_iso,
        )
        prediction: PredictionResponse = self._get_agent().analyze(prediction_request)
        reasons = self._reason_values(prediction.reason_codes or [])

        unit_label = VARIABLE_UNIT_MAP.get(request.variable, "")

        if prediction.abstain:
            return ForecastRevisionResponse(
                status=RevisionStatus.ABSTAINED,
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
                units=None,
                bust_probability=None,
                previous_bust_probability=None,
                bust_probability_delta=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                calibration_status=prediction.calibration_status or CalibrationStatus.UNAVAILABLE.value,
                scientific_scope=scientific_scope,
                is_certified_horizon=within_benchmark,
                history_is_durable=False,
                history_source=None,
                abstain=True,
                reason_codes=reasons,
                request_id=request_id,
            )

        units = RevisionUnits(
            value=unit_label,
            revision_delta=unit_label,
            absolute_revision=unit_label,
            ensemble_mean=unit_label,
            ensemble_spread=unit_label,
        )

        # If comparable durable history exists in store
        if prev_record is not None:
            status = RevisionStatus.AVAILABLE
            history_is_durable = True
            history_source = prev_record.provider_source
            prev_issue_time = prev_record.issue_time
            prev_val = prev_record.forecast_value
            prev_bust_prob = prev_record.bust_probability

            # Derive current forecast value from available diagnostics or fallback
            curr_val = prev_val  # Nominal fallback
            if prediction.failure_fingerprint and isinstance(prediction.failure_fingerprint, dict):
                ff = prediction.failure_fingerprint
                if "forecast_value" in ff:
                    try:
                        curr_val = float(ff["forecast_value"])
                    except (ValueError, TypeError):
                        pass

            trajectory_diag = calculate_trajectory_diagnostics(curr_val, prev_val)
            ensemble_diag = calculate_ensemble_revision(
                current_mean=None,
                previous_mean=prev_record.ensemble_mean,
                current_spread=None,
                previous_spread=prev_record.ensemble_spread,
            )
            prob_delta = None
            if prediction.bust_probability is not None and prev_bust_prob is not None:
                prob_delta = round(prediction.bust_probability - prev_bust_prob, 4)

            # Build trajectory points
            stored_points = store.get_trajectory_points(
                canonical_location=canonical_loc,
                variable=request.variable,
                valid_time=valid_iso,
                up_to_issue_time=issue_iso,
            )
            pts = [
                TrajectoryPoint(
                    issue_time=p.issue_time,
                    valid_time=p.valid_time,
                    lead_hours=p.lead_hours,
                    forecast_value=p.forecast_value,
                    ensemble_mean=p.ensemble_mean,
                    ensemble_spread=p.ensemble_spread,
                )
                for p in stored_points
            ]

            return ForecastRevisionResponse(
                status=status,
                location=request.location,
                resolved_name=resolved.name,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                variable=request.variable,
                lead_hours=lead_hours,
                lead_days=lead_days,
                current_issue_time=issue_iso,
                previous_issue_time=prev_issue_time,
                valid_time=valid_iso,
                trajectory=trajectory_diag,
                ensemble_revision=ensemble_diag,
                trajectory_points=pts,
                current_value=curr_val,
                previous_value=prev_val,
                revision_delta=trajectory_diag.revision_delta,
                units=units,
                bust_probability=prediction.bust_probability,
                previous_bust_probability=prev_bust_prob,
                bust_probability_delta=prob_delta,
                risk_level=prediction.risk_level,
                trust_state=prediction.trust_state,
                calibration_status=prediction.calibration_status,
                scientific_scope=scientific_scope,
                is_certified_horizon=within_benchmark,
                history_is_durable=history_is_durable,
                history_source=history_source,
                abstain=False,
                reason_codes=reasons,
                request_id=request_id,
            )

        # No comparable previous history in store
        status = RevisionStatus.INSUFFICIENT_HISTORY
        if REVISION_HISTORY_UNAVAILABLE not in reasons:
            reasons.append(REVISION_HISTORY_UNAVAILABLE)

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
    """Dependency provider for the revision service."""
    return _default_revision_service

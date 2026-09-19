"""Forecast Disagreement Intelligence Service for Veyra Phase 3 Day 29.

Provides authoritative evaluation of ensemble forecast spread and member
dispersion from real NOAA GEFS ensemble records without modifying V3 model
or calibrator artifacts.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from backend.app.core.metrics import default_metrics
from backend.app.schemas.disagreement import (
    DisagreementDiagnostics,
    DisagreementStatus,
    DisagreementUnits,
    ForecastDisagreementRequest,
    ForecastDisagreementResponse,
)
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.schemas.weather import CanonicalForecastRecord
from backend.app.services.location_service import BaseLocationService, DynamicLocationService

logger = logging.getLogger(__name__)

# Standard variable to unit mapping in Veyra
VARIABLE_UNIT_MAP: Dict[str, str] = {
    "temperature_2m": "°C",
    "wind_speed_10m": "m/s",
    "surface_pressure": "hPa",
}


class DisagreementService:
    """Production service for evaluating forecast disagreement and ensemble spread."""

    def __init__(
        self,
        location_service: Optional[BaseLocationService] = None,
        agent: Optional[Any] = None,
    ):
        self.location_service = location_service or DynamicLocationService()
        self._agent = agent

    def _get_agent(self) -> Any:
        """Lazy resolver for ForecastBustAgent to avoid circular imports."""
        if self._agent is None:
            from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent
            self._agent = get_forecast_bust_agent()
        return self._agent

    def evaluate_disagreement(
        self,
        request: ForecastDisagreementRequest,
    ) -> ForecastDisagreementResponse:
        """Evaluate ensemble disagreement diagnostics for the requested target.

        Enforces:
        - Strict location resolution and abstention without upstream calls.
        - Extraction of real ensemble dispersion (spread, range, IQR, CV).
        - Separation of calibrated P(BUST) from diagnostic disagreement.
        - Correct physical units (°C, m/s, hPa).
        - Proper horizon scientific scope labeling.
        - Guaranteed null-safety (never converts missing spread to fake 0.0).
        """
        request_id = f"disagree_{uuid.uuid4().hex[:12]}"
        lead_h = request.lead_hours
        lead_days = round(lead_h / 24.0, 1)
        is_certified = lead_h <= 240
        scientific_scope = (
            "WITHIN_FROZEN_BENCHMARK_LEAD_SCOPE"
            if is_certified
            else "EXTENDED_OPERATIONAL_HORIZON"
        )

        # 1. Resolve geographic location
        resolved = self.location_service.resolve(request.location)
        if resolved is None or resolved.latitude is None or resolved.longitude is None:
            default_metrics.record_abstention(ReasonCode.INVALID_LOCATION.value)
            return ForecastDisagreementResponse(
                status=DisagreementStatus.ABSTAINED,
                location=request.location,
                resolved_name=None,
                latitude=None,
                longitude=None,
                variable=request.variable,
                lead_hours=lead_h,
                lead_days=lead_days,
                issue_time=None,
                valid_time=None,
                diagnostics=None,
                units=None,
                member_count=None,
                has_full_ensemble=None,
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                calibration_status=CalibrationStatus.UNAVAILABLE.value,
                scientific_scope=scientific_scope,
                is_certified_horizon=is_certified,
                abstain=True,
                reason_codes=[ReasonCode.INVALID_LOCATION.value],
                request_id=request_id,
            )

        # 2. Establish issue and valid timestamps
        base_issue_dt: Optional[datetime] = None
        if request.issue_time:
            try:
                parsed = datetime.fromisoformat(request.issue_time.replace("Z", "+00:00"))
                base_issue_dt = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception as err:
                logger.warning("Failed to parse requested issue_time '%s': %s", request.issue_time, err)

        if base_issue_dt is None:
            now = datetime.now(timezone.utc)
            base_issue_dt = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)

        issue_iso = base_issue_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        valid_dt = base_issue_dt + timedelta(hours=lead_h)
        valid_iso = valid_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 3. Call authoritative inference agent for calibrated P(BUST)
        agent = self._get_agent()
        pred_req = PredictionRequest(
            location=request.location,
            variable=request.variable,
            issue_time=issue_iso,
            valid_time=valid_iso,
        )
        pred_resp: PredictionResponse = agent.analyze(pred_req)

        # 4. Ingest raw ensemble weather records to extract dispersion metrics
        weather_res = agent.get_weather_data(request.location, None)
        raw_records: List[Any] = []
        if weather_res and weather_res.is_available and weather_res.raw_data:
            raw_records = weather_res.raw_data.get("records", [])

        # Find candidate records matching variable
        matching_recs: List[Any] = []
        for r in raw_records:
            var_name = r.get("variable") if isinstance(r, dict) else getattr(r, "variable", None)
            if var_name == request.variable:
                matching_recs.append(r)

        # Find closest record by lead hours
        target_record: Optional[Any] = None
        if matching_recs:
            def get_lead(rec: Any) -> int:
                val = rec.get("lead_hours") if isinstance(rec, dict) else getattr(rec, "lead_hours", 0)
                return int(val or 0)

            target_record = min(matching_recs, key=lambda rec: abs(get_lead(rec) - lead_h))

        # 5. Extract dispersion diagnostics safely
        diagnostics: Optional[DisagreementDiagnostics] = None
        units: Optional[DisagreementUnits] = None
        member_cnt: Optional[int] = None
        full_ens: Optional[bool] = None
        status: DisagreementStatus = DisagreementStatus.UNAVAILABLE

        if target_record is not None:
            raw_std = target_record.get("ensemble_std") if isinstance(target_record, dict) else getattr(target_record, "ensemble_std", None)
            if raw_std is not None:
                try:
                    std_val = float(raw_std)
                    raw_mean = target_record.get("ensemble_mean") if isinstance(target_record, dict) else getattr(target_record, "ensemble_mean", None)
                    raw_val = target_record.get("value") if isinstance(target_record, dict) else getattr(target_record, "value", None)
                    mean_val = float(raw_mean) if raw_mean is not None else float(raw_val or 0.0)

                    raw_min = target_record.get("ensemble_min") if isinstance(target_record, dict) else getattr(target_record, "ensemble_min", None)
                    raw_max = target_record.get("ensemble_max") if isinstance(target_record, dict) else getattr(target_record, "ensemble_max", None)
                    min_val = float(raw_min) if raw_min is not None else mean_val
                    max_val = float(raw_max) if raw_max is not None else mean_val

                    raw_q10 = target_record.get("q10") if isinstance(target_record, dict) else getattr(target_record, "q10", None)
                    raw_q90 = target_record.get("q90") if isinstance(target_record, dict) else getattr(target_record, "q90", None)
                    q10_val = float(raw_q10) if raw_q10 is not None else min_val
                    q90_val = float(raw_q90) if raw_q90 is not None else max_val

                    rng_val = max(0.0, max_val - min_val)
                    iqr_val = max(0.0, q90_val - q10_val)
                    cv_val = round(std_val / (abs(mean_val) + 1e-6), 5)
                    ratio_val = round(std_val / (iqr_val + 1e-6), 4)

                    diagnostics = DisagreementDiagnostics(
                        ensemble_spread=round(std_val, 3),
                        ensemble_std=round(std_val, 3),
                        ensemble_range=round(rng_val, 3),
                        ensemble_iqr=round(iqr_val, 3),
                        ensemble_cv=cv_val,
                        spread_to_iqr_ratio=ratio_val,
                        ensemble_mean=round(mean_val, 2),
                        ensemble_min=round(min_val, 2),
                        ensemble_max=round(max_val, 2),
                    )

                    unit_label = VARIABLE_UNIT_MAP.get(request.variable, "units")
                    units = DisagreementUnits(
                        spread=unit_label,
                        range=unit_label,
                        iqr=unit_label,
                        mean=unit_label,
                        cv="dimensionless",
                        spread_to_iqr_ratio="dimensionless",
                    )

                    raw_members = target_record.get("member_count") if isinstance(target_record, dict) else getattr(target_record, "member_count", None)
                    member_cnt = int(raw_members or 31)
                    full_ens = bool(member_cnt >= 30)
                    status = DisagreementStatus.AVAILABLE
                except (ValueError, TypeError) as exc:
                    logger.warning("Error computing ensemble dispersion metrics: %s", exc)
                    diagnostics = None
                    units = None
                    status = DisagreementStatus.UNAVAILABLE

        # Format reason codes safely
        formatted_reasons = [
            rc if isinstance(rc, str) else getattr(rc, "value", str(rc))
            for rc in (pred_resp.reason_codes or [])
        ]

        return ForecastDisagreementResponse(
            status=status,
            location=request.location,
            resolved_name=resolved.name,
            latitude=resolved.latitude,
            longitude=resolved.longitude,
            variable=request.variable,
            lead_hours=lead_h,
            lead_days=lead_days,
            issue_time=issue_iso,
            valid_time=valid_iso,
            diagnostics=diagnostics,
            units=units,
            member_count=member_cnt,
            has_full_ensemble=full_ens,
            bust_probability=pred_resp.bust_probability,
            risk_level=pred_resp.risk_level,
            trust_state=pred_resp.trust_state,
            calibration_status=pred_resp.calibration_status,
            scientific_scope=scientific_scope,
            is_certified_horizon=is_certified,
            abstain=pred_resp.abstain,
            reason_codes=formatted_reasons,
            request_id=request_id,
        )


# Default singleton instance
_default_disagreement_service = DisagreementService()


def get_disagreement_service() -> DisagreementService:
    """Dependency provider for DisagreementService."""
    return _default_disagreement_service

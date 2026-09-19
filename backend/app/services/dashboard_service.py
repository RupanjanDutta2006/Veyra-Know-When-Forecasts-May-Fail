"""Dashboard Intelligence Service for Veyra Phase 3 Day 25.

Orchestrates unified, multi-horizon forecast bust intelligence for dashboard consumption.
Reuses existing ForecastBustAgent, DynamicLocationService, and caching pipelines
without modifying frozen model weights or duplicating prediction logic.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Callable, List, Optional

from backend.app.core.metrics import default_metrics
from backend.app.schemas.dashboard import (
    DashboardIntelligenceResponse,
    DashboardLocationContext,
    DashboardMode,
    DashboardRequest,
    DashboardScientificContext,
    DashboardStatus,
    DashboardSummary,
    DashboardTimelinePoint,
    DecisionMode,
)
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    PredictionResponse,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.services.location_service import BaseLocationService, DynamicLocationService

logger = logging.getLogger(__name__)


def normalize_dashboard_decision_mode(
    raw_mode: Optional[str], risk_level: Optional[RiskLevel]
) -> DecisionMode:
    """Translate legacy agent modes without overstating their risk severity."""
    normalized = (raw_mode or "").upper().strip()
    if normalized in [mode.value for mode in DecisionMode]:
        return DecisionMode(normalized)
    if normalized not in {"ELEVATED_RISK", "ACTIVE_ALERT"}:
        return DecisionMode.ABSTAINED
    if risk_level == RiskLevel.CRITICAL:
        return DecisionMode.CRITICAL_INTERVENTION
    if risk_level == RiskLevel.HIGH:
        return DecisionMode.HIGH_UNCERTAINTY
    if risk_level == RiskLevel.MEDIUM:
        return DecisionMode.ELEVATED_AWARENESS
    if risk_level == RiskLevel.LOW:
        return DecisionMode.STANDARD_MONITORING
    return DecisionMode.ABSTAINED


class DashboardIntelligenceService:
    """Production service orchestrating dashboard-ready probabilistic intelligence."""

    def __init__(
        self,
        location_service: Optional[BaseLocationService] = None,
        agent_factory: Optional[Callable[[], Any]] = None,
    ):
        self.location_service = location_service or DynamicLocationService()
        self.agent_factory = agent_factory

    @staticmethod
    def get_horizons_for_mode(mode: DashboardMode) -> List[int]:
        """Return canonical ordered lead hour list for requested evaluation mode."""
        if mode == DashboardMode.SINGLE:
            return [24]
        if mode == DashboardMode.STANDARD_7D:
            return [24, 48, 72, 96, 120, 144, 168]
        if mode == DashboardMode.FULL_16D:
            return [24 * i for i in range(1, 17)]  # 24 through 384 every 24h
        return [24, 48, 72, 96, 120, 144, 168]

    def _get_agent(self) -> Any:
        """Retrieve or construct the ForecastBustAgent."""
        if self.agent_factory:
            return self.agent_factory()
        from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent

        return get_forecast_bust_agent()

    def orchestrate(
        self, request: DashboardRequest, request_id: Optional[str] = None
    ) -> DashboardIntelligenceResponse:
        """Synthesize unified multi-horizon intelligence for a single dashboard request."""
        horizons = self.get_horizons_for_mode(request.mode)
        total_points = len(horizons)

        # 1. Parse base issue timestamp if explicitly requested
        base_issue_dt: Optional[datetime] = None
        if request.issue_time:
            try:
                raw = request.issue_time.strip().replace("Z", "+00:00")
                parsed = datetime.fromisoformat(raw)
                base_issue_dt = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception as err:
                logger.warning("Failed to parse requested issue_time '%s': %s", request.issue_time, err)

        # 2. Resolve geographic location
        resolved = self.location_service.resolve(request.location)
        if resolved is None or resolved.latitude is None or resolved.longitude is None:
            # Short-circuit on invalid location without triggering upstream weather requests
            default_metrics.record_abstention(ReasonCode.INVALID_LOCATION.value)
            default_metrics.record_dashboard_request("ABSTAINED", total_points, 0, total_points)

            if base_issue_dt is None:
                # Truncate current UTC time to 6-hour numerical cycle
                now = datetime.now(timezone.utc)
                base_issue_dt = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)

            issue_iso = base_issue_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            location_ctx = DashboardLocationContext(
                query=request.location,
                resolved_name=None,
                latitude=None,
                longitude=None,
                region_id=None,
            )
            abstained_pred = PredictionResponse(
                location=request.location,
                bust_probability=None,
                risk_level=None,
                trust_state=TrustState.UNAVAILABLE,
                abstain=True,
                reason_codes=[ReasonCode.INVALID_LOCATION],
                calibration_status=CalibrationStatus.UNAVAILABLE,
                decision_mode=DecisionMode.ABSTAINED,
            )
            timeline_points = [
                DashboardTimelinePoint(
                    lead_hours=h,
                    lead_days=round(h / 24.0, 1),
                    valid_time=(base_issue_dt + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    bust_probability=None,
                    risk_level=None,
                    trust_state=TrustState.UNAVAILABLE,
                    abstain=True,
                    reason_codes=[ReasonCode.INVALID_LOCATION],
                    calibration_status=CalibrationStatus.UNAVAILABLE,
                    decision_mode=DecisionMode.ABSTAINED,
                    within_trust_horizon=h <= 168,
                    operational_trust_horizon_hours=168,
                    is_certified_horizon=h <= 240,
                )
                for h in horizons
            ]
            summary = DashboardSummary(
                available_points=0,
                abstained_points=total_points,
                total_points=total_points,
                max_bust_probability=None,
                max_risk_level=None,
                max_risk_lead_hours=None,
                mean_bust_probability=None,
                elevated_risk_points=0,
                first_elevated_risk_lead_hours=None,
                overall_decision_mode=DecisionMode.ABSTAINED,
            )
            return DashboardIntelligenceResponse(
                status=DashboardStatus.ABSTAINED,
                location=location_ctx,
                variable=request.variable or "temperature_2m",
                issue_time=issue_iso,
                mode=request.mode,
                selected_prediction=abstained_pred,
                timeline=timeline_points,
                summary=summary,
                scientific_context=DashboardScientificContext(),
                request_id=request_id,
            )

        region_id_val = getattr(resolved, "region_id", None)
        if not region_id_val and resolved.country == "India":
            region_id_val = f"IN_{resolved.name.upper().replace(' ', '_')}"

        location_ctx = DashboardLocationContext(
            query=request.location,
            resolved_name=resolved.name,
            latitude=resolved.latitude,
            longitude=resolved.longitude,
            region_id=region_id_val,
        )

        agent = self._get_agent()

        # 3. Determine base issue timestamp for valid location if not explicitly provided
        if base_issue_dt is None and hasattr(agent, "get_weather_data"):
            # Query weather service once to establish canonical cycle and prime cache
            try:
                weather_res = agent.get_weather_data(request.location, None)
                if weather_res and weather_res.is_available and weather_res.raw_data:
                    raw_records = weather_res.raw_data.get("records", [])
                    if raw_records:
                        first_issue = raw_records[0].get("issue_time")
                        if first_issue:
                            try:
                                parsed_first = datetime.fromisoformat(first_issue.replace("Z", "+00:00"))
                                base_issue_dt = parsed_first.astimezone(timezone.utc) if parsed_first.tzinfo else parsed_first.replace(tzinfo=timezone.utc)
                            except Exception:
                                pass
            except Exception as exc:
                logger.debug("Could not pre-fetch weather for issue time: %s", exc)


        if base_issue_dt is None:
            # Truncate current UTC time to 6-hour numerical cycle
            now = datetime.now(timezone.utc)
            base_issue_dt = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)

        issue_iso = base_issue_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 3. Evaluate each requested horizon
        timeline_points: List[DashboardTimelinePoint] = []
        selected_pred: Optional[PredictionResponse] = None

        for h in horizons:
            lead_days = round(h / 24.0, 1)
            valid_dt = base_issue_dt + timedelta(hours=h)
            valid_iso = valid_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            pred_req = PredictionRequest(
                location=request.location,
                variable=request.variable or "temperature_2m",
                issue_time=issue_iso,
                valid_time=valid_iso,
            )
            pred_resp = agent.analyze(pred_req)

            is_certified = h <= 240
            within_h = pred_resp.within_trust_horizon if pred_resp.within_trust_horizon is not None else (h <= 168)
            op_trust_h = pred_resp.operational_trust_horizon_hours if pred_resp.operational_trust_horizon_hours is not None else 168
            dec_mode = normalize_dashboard_decision_mode(
                pred_resp.decision_mode, pred_resp.risk_level
            )

            point = DashboardTimelinePoint(
                lead_hours=h,
                lead_days=lead_days,
                valid_time=valid_iso,
                bust_probability=pred_resp.bust_probability,
                risk_level=pred_resp.risk_level,
                trust_state=pred_resp.trust_state,
                abstain=pred_resp.abstain,
                reason_codes=pred_resp.reason_codes,
                calibration_status=pred_resp.calibration_status,
                decision_mode=dec_mode,
                within_trust_horizon=within_h,
                operational_trust_horizon_hours=op_trust_h,
                is_certified_horizon=is_certified,
            )
            timeline_points.append(point)

            if h == 24:
                selected_pred = pred_resp

        if selected_pred is None:
            selected_pred = agent.analyze(
                PredictionRequest(
                    location=request.location,
                    variable=request.variable or "temperature_2m",
                )
            )

        # 4. Compute deterministic summary intelligence
        valid_points = [p for p in timeline_points if p.bust_probability is not None]
        available_cnt = len(valid_points)
        abstained_cnt = total_points - available_cnt

        if available_cnt == 0:
            summary = DashboardSummary(
                available_points=0,
                abstained_points=total_points,
                total_points=total_points,
                max_bust_probability=None,
                max_risk_level=None,
                max_risk_lead_hours=None,
                mean_bust_probability=None,
                elevated_risk_points=0,
                first_elevated_risk_lead_hours=None,
                overall_decision_mode=DecisionMode.ABSTAINED,
            )
            status = DashboardStatus.ABSTAINED
        else:
            valid_probs = [p.bust_probability for p in valid_points if p.bust_probability is not None]
            max_pt = max(valid_points, key=lambda p: (p.bust_probability if p.bust_probability is not None else -1.0))
            max_prob = max_pt.bust_probability
            max_risk = max_pt.risk_level
            max_lead = max_pt.lead_hours
            mean_prob = round(sum(valid_probs) / len(valid_probs), 4)

            elevated = [
                p for p in valid_points
                if p.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
            ]
            elevated_cnt = len(elevated)
            first_elevated_lead = elevated[0].lead_hours if elevated else None

            # Peak operational decision mode across valid points
            modes = {p.decision_mode for p in valid_points}
            if DecisionMode.CRITICAL_INTERVENTION in modes:
                overall_mode = DecisionMode.CRITICAL_INTERVENTION
            elif DecisionMode.HIGH_UNCERTAINTY in modes:
                overall_mode = DecisionMode.HIGH_UNCERTAINTY
            elif DecisionMode.ELEVATED_AWARENESS in modes:
                overall_mode = DecisionMode.ELEVATED_AWARENESS
            elif DecisionMode.STANDARD_MONITORING in modes:
                overall_mode = DecisionMode.STANDARD_MONITORING
            else:
                overall_mode = DecisionMode.ABSTAINED

            summary = DashboardSummary(
                available_points=available_cnt,
                abstained_points=abstained_cnt,
                total_points=total_points,
                max_bust_probability=max_prob,
                max_risk_level=max_risk,
                max_risk_lead_hours=max_lead,
                mean_bust_probability=mean_prob,
                elevated_risk_points=elevated_cnt,
                first_elevated_risk_lead_hours=first_elevated_lead,
                overall_decision_mode=overall_mode,
            )

            status = DashboardStatus.SUCCESS if abstained_cnt == 0 else DashboardStatus.PARTIAL

        # 5. Record telemetry
        default_metrics.record_dashboard_request(
            outcome=status.value,
            total_points=total_points,
            valid_points=available_cnt,
            abstained_points=abstained_cnt,
        )

        return DashboardIntelligenceResponse(
            status=status,
            location=location_ctx,
            variable=request.variable or "temperature_2m",
            issue_time=issue_iso,
            mode=request.mode,
            selected_prediction=selected_pred,
            timeline=timeline_points,
            summary=summary,
            scientific_context=DashboardScientificContext(),
            request_id=request_id,
        )

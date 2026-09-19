"""Spatial Forecast Reliability Service for Veyra Phase 3 Day 27.

Orchestrates spatial forecast reliability intelligence across discrete geographic locations.
Reuses authoritative ForecastBustAgent, DynamicLocationService, and caching pipelines
without modifying frozen model weights or duplicating prediction logic.
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.app.core.metrics import default_metrics
from backend.app.schemas.dashboard import DashboardStatus
from backend.app.schemas.prediction import (
    CalibrationStatus,
    PredictionRequest,
    ReasonCode,
    RiskLevel,
    TrustState,
)
from backend.app.schemas.spatial import (
    SpatialReliabilityPoint,
    SpatialReliabilityRequest,
    SpatialReliabilityResponse,
    SpatialReliabilitySummary,
)
from backend.app.services.location_service import BaseLocationService, DynamicLocationService

logger = logging.getLogger(__name__)


class SpatialReliabilityService:
    """Production service orchestrating discrete spatial forecast reliability intelligence."""

    def __init__(
        self,
        location_service: Optional[BaseLocationService] = None,
        agent_factory: Optional[Callable[[], Any]] = None,
    ):
        self.location_service = location_service or DynamicLocationService()
        self.agent_factory = agent_factory

    def _get_agent(self) -> Any:
        """Retrieve or construct the ForecastBustAgent."""
        if self.agent_factory:
            return self.agent_factory()
        from backend.app.api.v1.endpoints.predict import get_forecast_bust_agent

        return get_forecast_bust_agent()

    def evaluate_spatial(
        self, request: SpatialReliabilityRequest, request_id: Optional[str] = None
    ) -> SpatialReliabilityResponse:
        """Evaluate forecast bust reliability across multiple discrete locations."""
        total_locations = len(request.locations)
        lead_h = request.lead_hours
        lead_days = round(lead_h / 24.0, 1)
        is_certified = lead_h <= 240
        scientific_scope = (
            "FROZEN_BENCHMARK_LEAD_SCOPE" if is_certified else "EXTENDED_OPERATIONAL_HORIZON"
        )

        # 1. Parse or determine base issue timestamp
        base_issue_dt: Optional[datetime] = None
        if request.issue_time:
            try:
                raw = request.issue_time.strip().replace("Z", "+00:00")
                parsed = datetime.fromisoformat(raw)
                base_issue_dt = (
                    parsed.astimezone(timezone.utc)
                    if parsed.tzinfo
                    else parsed.replace(tzinfo=timezone.utc)
                )
            except Exception as err:
                logger.warning("Failed to parse requested issue_time '%s': %s", request.issue_time, err)

        agent = self._get_agent()

        # Prime issue time from first valid location if not explicitly provided
        if base_issue_dt is None and hasattr(agent, "get_weather_data"):
            for loc_candidate in request.locations:
                resolved_probe = self.location_service.resolve(loc_candidate)
                if resolved_probe and resolved_probe.latitude is not None:
                    try:
                        weather_res = agent.get_weather_data(loc_candidate, None)
                        if weather_res and weather_res.is_available and weather_res.raw_data:
                            raw_records = weather_res.raw_data.get("records", [])
                            if raw_records:
                                first_issue = raw_records[0].get("issue_time")
                                if first_issue:
                                    parsed_first = datetime.fromisoformat(first_issue.replace("Z", "+00:00"))
                                    base_issue_dt = (
                                        parsed_first.astimezone(timezone.utc)
                                        if parsed_first.tzinfo
                                        else parsed_first.replace(tzinfo=timezone.utc)
                                    )
                                    break
                    except Exception as probe_err:
                        logger.debug("Could not establish issue cycle from probe '%s': %s", loc_candidate, probe_err)

        if base_issue_dt is None:
            now = datetime.now(timezone.utc)
            base_issue_dt = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)

        issue_iso = base_issue_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        valid_dt = base_issue_dt + timedelta(hours=lead_h)
        valid_iso = valid_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 2. Deduplicate identical queries to avoid redundant upstream weather and inference calls
        # Map: normalized_key -> (raw_location_str, [indices])
        unique_queries: Dict[str, Tuple[str, List[int]]] = {}
        for idx, loc in enumerate(request.locations):
            norm_key = loc.strip().lower()
            if norm_key not in unique_queries:
                unique_queries[norm_key] = (loc, [idx])
            else:
                unique_queries[norm_key][1].append(idx)

        # 3. Evaluate each unique location
        computed_points: List[Optional[SpatialReliabilityPoint]] = [None] * total_locations

        for norm_key, (raw_loc, indices) in unique_queries.items():
            resolved = self.location_service.resolve(raw_loc)
            if resolved is None or resolved.latitude is None or resolved.longitude is None:
                default_metrics.record_abstention(ReasonCode.INVALID_LOCATION.value)
                abstained_point = SpatialReliabilityPoint(
                    location=raw_loc,
                    resolved_name=None,
                    latitude=None,
                    longitude=None,
                    region_id=None,
                    variable=request.variable,
                    lead_hours=lead_h,
                    lead_days=lead_days,
                    issue_time=issue_iso,
                    valid_time=valid_iso,
                    bust_probability=None,
                    risk_level=None,
                    trust_state=TrustState.UNAVAILABLE,
                    abstain=True,
                    reason_codes=[ReasonCode.INVALID_LOCATION.value],
                    calibration_status=CalibrationStatus.UNAVAILABLE.value,
                    model_version=None,
                    data_version=None,
                    is_certified_horizon=is_certified,
                    scientific_scope=scientific_scope,
                    decision_mode="ABSTAINED",
                )
                for idx in indices:
                    computed_points[idx] = abstained_point
                continue

            region_id_val = getattr(resolved, "region_id", None)
            if not region_id_val and resolved.country == "India":
                region_id_val = f"IN_{resolved.name.upper().replace(' ', '_')}"

            pred_req = PredictionRequest(
                location=raw_loc,
                variable=request.variable,
                issue_time=issue_iso,
                valid_time=valid_iso,
            )
            pred_resp = agent.analyze(pred_req)

            # Format reason codes safely
            formatted_reasons = [
                rc if isinstance(rc, str) else getattr(rc, "value", str(rc))
                for rc in (pred_resp.reason_codes or [])
            ]

            # Day 29: Extract real ensemble dispersion diagnostics from cached weather data
            ens_spread = None
            ens_range = None
            ens_iqr = None
            ens_cv = None
            spread_u = None
            m_count = None
            if not pred_resp.abstain:
                try:
                    weather_res = agent.get_weather_data(raw_loc, None)
                    if weather_res and weather_res.raw_data:
                        raw_recs = weather_res.raw_data.get("records", [])
                        matching = [
                            r for r in raw_recs
                            if (r.get("variable") if isinstance(r, dict) else getattr(r, "variable", None)) == request.variable
                        ]
                        if matching:
                            def _get_lh(rec: Any) -> int:
                                val = rec.get("lead_hours") if isinstance(rec, dict) else getattr(rec, "lead_hours", 0)
                                return int(val or 0)

                            closest_rec = min(matching, key=lambda r: abs(_get_lh(r) - lead_h))
                            raw_s = closest_rec.get("ensemble_std") if isinstance(closest_rec, dict) else getattr(closest_rec, "ensemble_std", None)
                            if raw_s is not None:
                                std_f = float(raw_s)
                                raw_mean = closest_rec.get("ensemble_mean") if isinstance(closest_rec, dict) else getattr(closest_rec, "ensemble_mean", None)
                                raw_v = closest_rec.get("value") if isinstance(closest_rec, dict) else getattr(closest_rec, "value", None)
                                mean_f = float(raw_mean) if raw_mean is not None else float(raw_v or 0.0)
                                raw_min = closest_rec.get("ensemble_min") if isinstance(closest_rec, dict) else getattr(closest_rec, "ensemble_min", None)
                                raw_max = closest_rec.get("ensemble_max") if isinstance(closest_rec, dict) else getattr(closest_rec, "ensemble_max", None)
                                min_f = float(raw_min) if raw_min is not None else mean_f
                                max_f = float(raw_max) if raw_max is not None else mean_f
                                raw_q10 = closest_rec.get("q10") if isinstance(closest_rec, dict) else getattr(closest_rec, "q10", None)
                                raw_q90 = closest_rec.get("q90") if isinstance(closest_rec, dict) else getattr(closest_rec, "q90", None)
                                q10_f = float(raw_q10) if raw_q10 is not None else min_f
                                q90_f = float(raw_q90) if raw_q90 is not None else max_f

                                ens_spread = round(std_f, 3)
                                ens_range = round(max(0.0, max_f - min_f), 3)
                                ens_iqr = round(max(0.0, q90_f - q10_f), 3)
                                ens_cv = round(std_f / (abs(mean_f) + 1e-6), 5)
                                spread_u = "°C" if request.variable == "temperature_2m" else ("m/s" if request.variable == "wind_speed_10m" else ("hPa" if request.variable == "surface_pressure" else "units"))
                                raw_mc = closest_rec.get("member_count") if isinstance(closest_rec, dict) else getattr(closest_rec, "member_count", None)
                                m_count = int(raw_mc or 31)
                except Exception as exc:
                    logger.debug("Could not extract ensemble spread for spatial point %s: %s", raw_loc, exc)

            point = SpatialReliabilityPoint(
                location=raw_loc,
                resolved_name=resolved.name,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                region_id=region_id_val,
                variable=request.variable,
                lead_hours=lead_h,
                lead_days=lead_days,
                issue_time=issue_iso,
                valid_time=valid_iso,
                bust_probability=pred_resp.bust_probability,
                risk_level=pred_resp.risk_level,
                trust_state=pred_resp.trust_state,
                abstain=pred_resp.abstain,
                reason_codes=formatted_reasons,
                calibration_status=pred_resp.calibration_status,
                model_version=pred_resp.model_version,
                data_version=pred_resp.data_version,
                is_certified_horizon=is_certified,
                scientific_scope=scientific_scope,
                confidence_index=pred_resp.confidence_index,
                uncertainty_pct=pred_resp.uncertainty_pct,
                ood_score=pred_resp.ood_score,
                stability_index=pred_resp.stability_index,
                dominant_risk_drivers=pred_resp.dominant_risk_drivers,
                decision_mode=pred_resp.decision_mode,
                decision_guidance=pred_resp.decision_guidance,
                ensemble_spread=ens_spread,
                ensemble_range=ens_range,
                ensemble_iqr=ens_iqr,
                ensemble_cv=ens_cv,
                spread_unit=spread_u,
                member_count=m_count,
            )

            for idx in indices:
                computed_points[idx] = point

        # Final points list in 1:1 input order
        final_points: List[SpatialReliabilityPoint] = [p for p in computed_points if p is not None]

        # 4. Compute Spatial Summary
        available_pts = [p for p in final_points if not p.abstain and p.bust_probability is not None]
        abstained_count = len(final_points) - len(available_pts)

        if available_pts:
            probs = [p.bust_probability for p in available_pts if p.bust_probability is not None]
            max_prob = max(probs) if probs else None
            max_pt = next((p for p in available_pts if p.bust_probability == max_prob), None)
            max_risk = max_pt.risk_level if max_pt else None
            max_loc = max_pt.location if max_pt else None
            mean_prob = round(sum(probs) / len(probs), 4) if probs else None
            elevated_count = sum(
                1
                for p in available_pts
                if p.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
            )
            low_count = sum(1 for p in available_pts if p.risk_level == RiskLevel.LOW)
            med_count = sum(1 for p in available_pts if p.risk_level == RiskLevel.MEDIUM)
            high_count = sum(1 for p in available_pts if p.risk_level == RiskLevel.HIGH)
            crit_count = sum(1 for p in available_pts if p.risk_level == RiskLevel.CRITICAL)
            status = DashboardStatus.SUCCESS if abstained_count == 0 else DashboardStatus.PARTIAL
        else:
            max_prob = None
            max_risk = None
            max_loc = None
            mean_prob = None
            elevated_count = 0
            low_count = 0
            med_count = 0
            high_count = 0
            crit_count = 0
            status = DashboardStatus.ABSTAINED

        summary = SpatialReliabilitySummary(
            total_locations=total_locations,
            available_locations=len(available_pts),
            abstained_locations=abstained_count,
            max_bust_probability=max_prob,
            max_risk_level=max_risk,
            max_risk_location=max_loc,
            mean_bust_probability=mean_prob,
            elevated_risk_locations=elevated_count,
            low_risk_locations=low_count,
            medium_risk_locations=med_count,
            high_risk_locations=high_count,
            critical_risk_locations=crit_count,
        )

        # 5. Record Process Metrics
        default_metrics.record_spatial_request(
            status.value, total_locations, len(available_pts), abstained_count
        )

        return SpatialReliabilityResponse(
            status=status,
            variable=request.variable,
            lead_hours=lead_h,
            lead_days=lead_days,
            issue_time=issue_iso,
            is_certified_horizon=is_certified,
            scientific_scope=scientific_scope,
            points=final_points,
            summary=summary,
            request_id=request_id,
        )

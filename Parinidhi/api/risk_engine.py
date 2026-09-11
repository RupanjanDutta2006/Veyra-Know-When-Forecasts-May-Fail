"""
Operational Forecast-Risk Engine.

Coordinates location colocation, issue-time feature extraction, calibrated model
inference via ForecastIntelligenceService (V2 Champion), dynamic verification
status derivation, lead-conditioned Operational Trust Horizon, Actionable Decision
Modes, Epistemic Abstention, and rich analytical Failure Fingerprints.

Scientific Constraints:
- Non-Causal Diagnostic Framing: Fingerprints document physical patterns associated with
  error modes without making unverified causal claims.
- Configurable Design Thresholds: Pcrit (0.35) and OOD Severe Threshold (40.0) are designated
  as operational heuristics/product design parameters, not universal scientific constants.
- Single feature pipeline path: uses features/feature_pipeline.py directly.
- Verification status strictly requires an actual verified truth pair to claim HISTORICALLY_VERIFIED.
- Grid resolution provenance is never silently guessed (returns UNKNOWN if resolution is absent).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

import numpy as np
import pandas as pd

from api.explainer import ForecastBustExplainer
from api.location_service import LocationRegistry
from api.schemas import (
    ContributingFactor,
    DataStatus,
    DecisionGuidance,
    DecisionMode,
    ExplanationItem,
    FailureFingerprintDetail,
    ForecastRiskItem,
    ForecastRiskResponse,
    LocationCoordinates,
    LocationInfo,
    OperationalTrustHorizonInfo,
    ProvenanceInfo,
    TrustTimelineItem,
    VerificationStatus,
)
from models.forecast_intelligence_service import ForecastIntelligenceService

# -------------------------------------------------------------------------
# Configurable Operational & Product Design Parameters
# -------------------------------------------------------------------------
# Research/Product design threshold for the trust horizon cutoff.
# NOT a universal scientific constant; subject to future empirical validation on the 1,040-cycle dataset.
TRUST_HORIZON_DEFAULT_THRESHOLD: float = 0.35

# Operational heuristic boundary for severe out-of-distribution detection.
# In V2 TrainingOODScorer (scaled 0-100), D_M >= 40.0 corresponds to a >= 2-sigma multivariate feature anomaly.
OOD_SEVERE_ABSTAIN_THRESHOLD: float = 40.0

# Standard meteorological lead-time grid (hours)
STANDARD_LEAD_HOURS: List[int] = [24, 48, 72, 96, 120, 144, 168, 192, 216, 240]

# -------------------------------------------------------------------------
# Failure Fingerprint Scientific Catalog (Non-Causal Diagnostic Taxonomy)
# -------------------------------------------------------------------------
FINGERPRINT_CATALOG: Dict[str, Dict[str, Any]] = {
    "RAPID_REVISION_SHOCK": {
        "name": "Rapid Revision Shock",
        "description": "Large short-interval forecast shifts relative to ensemble spread indicating numerical solver volatility.",
        "interpretation": "Observed when consecutive forecast cycles swing abruptly, historically associated with convective initialization adjustments or frontal timing uncertainty.",
        "limitations": "Does not prove a bust will occur, but indicates heightened trajectory instability.",
    },
    "LONG_LEAD_DECAY": {
        "name": "Long Lead Decay",
        "description": "Progressive accumulation of chaotic ensemble dispersion at extended horizons (lead >= 48h).",
        "interpretation": "Consistent with natural deterministic predictability loss as error growth saturates across ensemble members.",
        "limitations": "Synoptic blocking regimes may retain skill despite elevated nominal lead times.",
    },
    "DIURNAL_CONVECTIVE_MISMATCH": {
        "name": "Diurnal Convective Mismatch",
        "description": "Sub-grid boundary-layer heating and localized diurnal cycle dispersion discrepancies.",
        "interpretation": "Pattern frequently observed during afternoon peak heating where parameterized convection diverges among ensemble members.",
        "limitations": "Surface topography and local microclimates can modulate diurnal variance beyond grid-scale representation.",
    },
    "WIND_GRADIENT_SHEAR": {
        "name": "Wind Gradient Shear",
        "description": "Tail-risk wind speed amplification exceeding 90th percentile threshold across coastal/shear zones.",
        "interpretation": "Associated with localized baroclinic gradients, squall dynamics, or coastal thermal contrasts.",
        "limitations": "Point measurements may experience sub-grid gustiness not captured by 10-meter mean fields.",
    },
    "TIGHT_CLUSTER_BREAKDOWN": {
        "name": "Tight Cluster Breakdown",
        "description": "Structural overconfidence where ensemble spread is deceptively narrow despite high historical error rates.",
        "interpretation": "Pattern observed when ensemble members cluster tightly around a shared model solution despite elevated historical error rates.",
        "limitations": "Spread-skill relationship varies across synoptic regimes; tight clustering can also reflect high atmospheric predictability.",
    },
    "STABLE_SYNOPTIC_CONSENSUS": {
        "name": "Stable Synoptic Consensus",
        "description": "Coherent multi-agreement under quiescent or well-resolved synoptic flow.",
        "interpretation": "Consistent with high-confidence atmospheric regimes exhibiting low revision drift and normal ensemble spread.",
        "limitations": "Unmodeled sudden events (e.g., unrepresented aerosol radiative forcing) can occasionally bypass synoptic consensus.",
    },
    "INSUFFICIENT_EVIDENCE": {
        "name": "Insufficient Evidence / Anomaly",
        "description": "Input atmospheric features fall outside the known training domain or contain incomplete signal data.",
        "interpretation": "Pattern cannot be reliably classified under known failure archetypes due to high novelty distance or missing observations.",
        "limitations": "Automated ML predictions should be withheld or treated with extreme skepticism.",
    },
}


class OperationalRiskEngine:
    """Operational engine turning weather forecasts into calibrated bust risk products via V2 Champion."""

    def __init__(
        self,
        intelligence_service: Optional[ForecastIntelligenceService] = None,
        location_registry: Optional[LocationRegistry] = None,
        model_service: Optional[Any] = None,
        feature_pipeline: Optional[Any] = None,
        trust_horizon_threshold: float = TRUST_HORIZON_DEFAULT_THRESHOLD,
        ood_severe_threshold: float = OOD_SEVERE_ABSTAIN_THRESHOLD,
    ):
        self.intelligence_service = intelligence_service or ForecastIntelligenceService()
        self.location_registry = location_registry or LocationRegistry()
        self.model_service = self.intelligence_service
        self.trust_horizon_threshold = trust_horizon_threshold
        self.ood_severe_threshold = ood_severe_threshold

    def evaluate_verification_status(
        self,
        valid_time: datetime,
        issue_time: datetime,
        max_truth_time_utc: Optional[datetime] = None,
        has_verified_truth_pair: bool = False,
    ) -> str:
        """Derive ground-truth verification status from actual temporal and truth availability context."""
        if has_verified_truth_pair:
            return VerificationStatus.HISTORICALLY_VERIFIED.value

        if max_truth_time_utc is not None and valid_time > max_truth_time_utc:
            return VerificationStatus.UNVERIFIED_HORIZON_NO_TRUTH.value

        now_utc = datetime.now(timezone.utc)
        if valid_time > now_utc:
            return VerificationStatus.NO_TRUTH_AVAILABLE.value

        return VerificationStatus.NO_TRUTH_AVAILABLE.value

    def resolve_grid_resolution(
        self,
        explicit_res: Optional[str] = None,
        df_forecast: Optional[pd.DataFrame] = None,
        forecast_source: Optional[str] = None,
    ) -> str:
        """Derive grid resolution provenance without silent guesswork."""
        if explicit_res is not None and explicit_res.strip():
            return explicit_res.strip()

        if df_forecast is not None and "grid_resolution" in df_forecast.columns:
            val = str(df_forecast["grid_resolution"].iloc[0]).strip()
            if val and val.lower() != "nan" and val.lower() != "none":
                return val

        if forecast_source is not None:
            src = forecast_source.lower()
            if "0p50" in src or "pgrb2a" in src:
                return "0.50°"
            if "0p25" in src or "gefs025" in src or "openmeteo" in src:
                return "0.25°"

        return "UNKNOWN"

    def infer_failure_fingerprint(
        self,
        raw_fingerprint: str,
        lead_hours: int,
        p_bust: float,
        stability_index: float,
        ood_score: float,
        overconfidence_signal: float = 0.0,
        ensemble_std: float = 0.0,
        variable: str = "temperature_2m",
        has_corrupted_input: bool = False,
    ) -> str:
        """Infer failure fingerprint archetype from physical signals if not explicitly specified."""
        if has_corrupted_input or ood_score >= self.ood_severe_threshold:
            return "INSUFFICIENT_EVIDENCE"

        if raw_fingerprint in FINGERPRINT_CATALOG and raw_fingerprint not in ("NOMINAL", "UNKNOWN", "NONE"):
            return raw_fingerprint

        if stability_index < 50.0:
            return "RAPID_REVISION_SHOCK"

        if overconfidence_signal > 0.40 and ensemble_std < 0.50:
            return "TIGHT_CLUSTER_BREAKDOWN"

        if variable == "wind_speed_10m" and (ensemble_std > 2.5 or p_bust > 0.25):
            return "WIND_GRADIENT_SHEAR"

        if lead_hours >= 120 and (p_bust >= 0.15 or ensemble_std > 1.5):
            return "LONG_LEAD_DECAY"

        if p_bust < 0.20 and stability_index >= 60.0:
            return "STABLE_SYNOPTIC_CONSENSUS"

        if lead_hours >= 72:
            return "LONG_LEAD_DECAY"

        return "STABLE_SYNOPTIC_CONSENSUS"

    def build_fingerprint_detail(
        self,
        raw_fingerprint: str,
        supporting_signals: List[str],
        ood_score: float,
        lead_hours: int = 24,
        p_bust: float = 0.0,
        stability_index: float = 100.0,
        overconfidence_signal: float = 0.0,
        ensemble_std: float = 0.0,
        variable: str = "temperature_2m",
        has_corrupted_input: bool = False,
    ) -> FailureFingerprintDetail:
        """Construct structured non-causal failure fingerprint metadata."""
        fp_key = self.infer_failure_fingerprint(
            raw_fingerprint=raw_fingerprint,
            lead_hours=lead_hours,
            p_bust=p_bust,
            stability_index=stability_index,
            ood_score=ood_score,
            overconfidence_signal=overconfidence_signal,
            ensemble_std=ensemble_std,
            variable=variable,
            has_corrupted_input=has_corrupted_input,
        )

        meta = FINGERPRINT_CATALOG.get(fp_key, FINGERPRINT_CATALOG["INSUFFICIENT_EVIDENCE"])
        evidence_state = "SUPPORTED_BY_SIGNALS" if fp_key != "INSUFFICIENT_EVIDENCE" else "INSUFFICIENT_EVIDENCE"

        return FailureFingerprintDetail(
            fingerprint_id=fp_key,
            name=meta["name"],
            description=meta["description"],
            supporting_signals=supporting_signals,
            evidence_state=evidence_state,
            interpretation=meta["interpretation"],
            limitations=meta["limitations"],
        )

    def determine_decision_mode(
        self,
        p_bust: float,
        ood_score: float,
        stability_index: float,
        fingerprint: str,
        lead_hours: int,
        has_corrupted_input: bool = False,
    ) -> Tuple[DecisionMode, str, str]:
        """
        Derive actionable decision mode, primary rationale, and recommended action.
        
        Returns:
            Tuple of (DecisionMode, primary_reason, recommended_action)
        """
        # 1. Epistemic Abstention Rule (OOD or corrupted/missing data)
        if has_corrupted_input or ood_score >= self.ood_severe_threshold:
            return (
                DecisionMode.ABSTAIN,
                f"Severe atmospheric out-of-distribution anomaly (D_M={ood_score:.1f} >= {self.ood_severe_threshold:.1f}) or invalid input telemetry.",
                "Abstain from automated decision-making. Require manual meteorological consultation.",
            )

        # 2. Critical Bust Risk or Extended Horizon Decay
        if p_bust >= 0.60 or (lead_hours >= 120 and (fingerprint == "LONG_LEAD_DECAY" or p_bust >= self.trust_horizon_threshold or stability_index < 50.0)):
            return (
                DecisionMode.DO_NOT_RELY_SOLELY,
                f"Extended lead-time predictability decay (+{lead_hours}h) or elevated bust probability ({p_bust*100:.1f}%) indicating high risk of forecast deviation.",
                "Do NOT commit irreversible resources solely to this forecast. Secure secondary verification or contingency buffers.",
            )

        # 3. Trajectory Volatility / Revision Shock
        if fingerprint in ("RAPID_REVISION_SHOCK", "DIURNAL_CONVECTIVE_MISMATCH"):
            return (
                DecisionMode.RECHECK_SOON,
                f"Active {fingerprint.replace('_', ' ').title()} detected with inter-cycle revision volatility (stability: {stability_index:.1f}/100).",
                "Recheck forecast on the next model cycle (06Z/12Z/18Z) before finalizing operational plans.",
            )

        # 4. Elevated Risk or Approaching Trust Horizon
        if p_bust >= self.trust_horizon_threshold or p_bust >= 0.10 or stability_index < 75.0:
            return (
                DecisionMode.CAUTION,
                f"Elevated bust risk ({p_bust*100:.1f}%) within operational monitoring boundaries.",
                "Use with standard operational safety margins and monitor subsequent ensemble updates.",
            )

        # 5. Nominal High Trust
        return (
            DecisionMode.HIGH_TRUST,
            f"Nominal forecast stability ({stability_index:.1f}/100) and low bust probability ({p_bust*100:.1f}%).",
            "Proceed with standard operational workflows. Forecast is within reliable trust envelope.",
        )

    def process_forecast_dataframe(
        self,
        df_forecast: pd.DataFrame,
        location_id: str = "delhi",
        forecast_source: str = "NOAA_GEFS",
        grid_resolution: Optional[str] = None,
        max_truth_time_utc: Optional[datetime] = None,
        target_lead_hours: Optional[int] = None,
    ) -> ForecastRiskResponse:
        """
        Execute full operational risk pipeline for a standardized forecast DataFrame using V2 Champion.
        """
        if df_forecast.empty:
            raise ValueError("Input forecast DataFrame is empty.")

        df_forecast = df_forecast.copy()
        if "location_id" not in df_forecast.columns:
            df_forecast["location_id"] = location_id
        if "location" not in df_forecast.columns:
            df_forecast["location"] = location_id
        if "issue_time_utc" in df_forecast.columns and "issue_time" not in df_forecast.columns:
            df_forecast["issue_time"] = df_forecast["issue_time_utc"]
        if "valid_time_utc" in df_forecast.columns and "valid_time" not in df_forecast.columns:
            df_forecast["valid_time"] = df_forecast["valid_time_utc"]
        if "issue_time" not in df_forecast.columns:
            df_forecast["issue_time"] = datetime.now(timezone.utc).isoformat()
        if "valid_time" not in df_forecast.columns:
            if "lead_hours" in df_forecast.columns:
                issue_dt = pd.to_datetime(df_forecast["issue_time"], utc=True)
                lead_deltas = pd.to_timedelta(pd.to_numeric(df_forecast["lead_hours"], errors="coerce").fillna(24), unit="h")
                df_forecast["valid_time"] = (issue_dt + lead_deltas).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                df_forecast["valid_time"] = df_forecast["issue_time"]
        if "forecast_value" not in df_forecast.columns:
            if "value" in df_forecast.columns:
                df_forecast["forecast_value"] = df_forecast["value"]
            elif "ensemble_mean" in df_forecast.columns:
                df_forecast["forecast_value"] = df_forecast["ensemble_mean"]
            else:
                df_forecast["forecast_value"] = 0.0
        if "value" not in df_forecast.columns:
            df_forecast["value"] = df_forecast["forecast_value"]

        # 1. Determine grid coordinates from data if available
        actual_lat = float(df_forecast["latitude"].iloc[0]) if "latitude" in df_forecast.columns else None
        actual_lon = float(df_forecast["longitude"].iloc[0]) if "longitude" in df_forecast.columns else None

        # 2. Derive dynamic grid resolution without silent guessing
        resolved_grid_res = self.resolve_grid_resolution(
            explicit_res=grid_resolution,
            df_forecast=df_forecast,
            forecast_source=forecast_source,
        )

        # 3. Resolve Location Info safely
        try:
            location_info = self.location_registry.get_location(
                location_id=location_id,
                actual_grid_lat=actual_lat,
                actual_grid_lon=actual_lon,
            )
            is_unregistered_location = False
        except (KeyError, ValueError):
            location_info = LocationInfo(
                location_id=str(location_id).lower().strip() or "unregistered",
                country="Out-of-Domain",
                state_region="Out-of-Domain",
                city=str(location_id).title().strip() or "Unknown Location",
                requested_coordinates=LocationCoordinates(
                    latitude=actual_lat if actual_lat is not None else 0.0,
                    longitude=actual_lon if actual_lon is not None else 0.0,
                ),
                actual_grid_coordinates=LocationCoordinates(latitude=actual_lat, longitude=actual_lon) if actual_lat and actual_lon else None,
                is_benchmark=False,
                rationale="Unregistered, novel, or out-of-domain geographical monitoring point.",
            )
            is_unregistered_location = True

        # Check for unresolvable NaN / corrupted inputs or unregistered location
        has_corrupted_input = bool(
            is_unregistered_location
            or (
                df_forecast[["ensemble_mean", "ensemble_std"]].isna().any().any()
                if {"ensemble_mean", "ensemble_std"}.issubset(df_forecast.columns)
                else False
            )
        )

        # 4. Invoke Authoritative V2 Forecast Intelligence Service
        results = self.intelligence_service.evaluate_forecast(df_forecast)

        # 5. Extract metadata & provenance
        model_version = self.intelligence_service.model_version
        decision_threshold = float(self.intelligence_service.operational_threshold)

        issue_time_val = df_forecast["issue_time"].iloc[0] if "issue_time" in df_forecast.columns else datetime.now(timezone.utc)
        issue_time_str = pd.to_datetime(issue_time_val, utc=True).isoformat()

        provenance = ProvenanceInfo(
            forecast_source=forecast_source,
            grid_resolution=resolved_grid_res,
            model_version=model_version,
            feature_schema_version="2.0.0-supercharged-50f",
            prediction_timestamp_utc=datetime.now(timezone.utc).isoformat(),
            truth_source="ECMWF_ERA5_REANALYSIS",
        )

        # 6. Assemble Forecast Risk Items with V2 fields and decision intelligence
        forecast_items: List[ForecastRiskItem] = []
        eval_lead_map: Dict[int, ForecastRiskItem] = {}

        has_multi_issue = bool("issue_time" in df_forecast.columns and df_forecast["issue_time"].nunique() > 1)
        latest_issue_raw = df_forecast["issue_time"].max() if "issue_time" in df_forecast.columns else None
        latest_issue_str = pd.to_datetime(latest_issue_raw, utc=True).isoformat() if latest_issue_raw is not None else None

        for r in results:
            if has_multi_issue and latest_issue_str is not None:
                r_issue_str = pd.to_datetime(r.issue_time, utc=True).isoformat()
                if r_issue_str != latest_issue_str:
                    continue

            prob = float(r.bust_probability)
            alert = bool(prob >= decision_threshold)

            v_time_dt = pd.to_datetime(r.valid_time, utc=True).to_pydatetime()
            i_time_dt = pd.to_datetime(r.issue_time, utc=True).to_pydatetime()

            has_truth = "forecast_abs_error" in df_forecast.columns and not pd.isna(df_forecast["forecast_abs_error"].iloc[0] if len(df_forecast) else None)
            v_status = self.evaluate_verification_status(
                valid_time=v_time_dt,
                issue_time=i_time_dt,
                max_truth_time_utc=max_truth_time_utc,
                has_verified_truth_pair=has_truth,
            )

            primary_drv = r.dominant_risk_drivers[0].signal_name if r.dominant_risk_drivers else "NONE"
            drv_summary = r.dominant_risk_drivers[0].description if r.dominant_risk_drivers else "All feature signals nominal."
            factors = [
                ContributingFactor(
                    factor=d.signal_name,
                    value=float(d.signal_value),
                    signal=d.risk_direction,
                )
                for d in r.dominant_risk_drivers
            ]

            explanation = ExplanationItem(
                primary_driver=primary_drv,
                driver_summary=drv_summary,
                top_contributing_factors=factors,
            )

            raw_fp = str(r.provenance.get("failure_fingerprint", "NOMINAL"))
            ood_score = float(r.ood_score)
            stab_index = float(r.stability_index)
            lead_h = int(r.lead_hours)

            supporting_sigs = [d.signal_name for d in r.dominant_risk_drivers[:3]]
            fp_detail = self.build_fingerprint_detail(
                raw_fingerprint=raw_fp,
                supporting_signals=supporting_sigs,
                ood_score=ood_score,
                lead_hours=lead_h,
                p_bust=prob,
                stability_index=stab_index,
                overconfidence_signal=float(r.overconfidence_signal),
                ensemble_std=float(r.ensemble_std),
                variable=str(r.variable),
                has_corrupted_input=has_corrupted_input,
            )

            # Evaluate decision mode & action
            dec_mode, prim_reason, rec_action = self.determine_decision_mode(
                p_bust=prob,
                ood_score=ood_score,
                stability_index=stab_index,
                fingerprint=fp_detail.fingerprint_id,
                lead_hours=lead_h,
                has_corrupted_input=has_corrupted_input,
            )

            data_status_val = (
                DataStatus.ABSTAINED.value
                if dec_mode == DecisionMode.ABSTAIN
                else DataStatus.MODEL_PREDICTION.value
            )

            # Within trust horizon if below threshold and stability healthy
            within_horizon = bool(
                prob < self.trust_horizon_threshold
                and stab_index >= 50.0
                and dec_mode != DecisionMode.ABSTAIN
            )

            item = ForecastRiskItem(
                valid_time=v_time_dt.isoformat(),
                lead_hours=lead_h,
                lead_days=round(float(lead_h / 24.0), 2),
                variable=str(r.variable),
                forecast_value=float(r.forecast_value),
                ensemble_mean=float(r.ensemble_mean),
                ensemble_std=float(r.ensemble_std),
                unit=str(r.unit),
                bust_probability=prob,
                bust_alert=alert,
                data_status=data_status_val,
                verification_status=v_status,
                explanation=explanation,
                confidence=None,
                risk_level=str(r.risk_level),
                confidence_index=float(r.confidence_index),
                structural_overconfidence=float(r.overconfidence_signal),
                stability_index=stab_index,
                ood_score=ood_score,
                failure_fingerprint=fp_detail.fingerprint_id,
                uncertainty_pct=float(r.provenance.get("prediction_uncertainty_pct", 3.37)),
                dominant_risk_drivers=[d.to_dict() for d in r.dominant_risk_drivers],
                decision_mode=dec_mode.value,
                recommended_action=rec_action,
                within_trust_horizon=within_horizon,
                failure_fingerprint_detail=fp_detail,
            )
            forecast_items.append(item)
            eval_lead_map[lead_h] = item

        # 7. Construct Lead-Time Trust Timeline across standard leads
        trust_timeline: List[TrustTimelineItem] = []
        for lead in STANDARD_LEAD_HOURS:
            if lead in eval_lead_map:
                it = eval_lead_map[lead]
                trust_timeline.append(
                    TrustTimelineItem(
                        lead_hours=lead,
                        lead_days=round(lead / 24.0, 2),
                        bust_probability=it.bust_probability,
                        risk_level=it.risk_level,
                        decision_mode=it.decision_mode,
                        within_trust_horizon=bool(it.within_trust_horizon),
                        stability_index=it.stability_index,
                        failure_fingerprint=it.failure_fingerprint,
                        is_available=True,
                    )
                )
            else:
                trust_timeline.append(
                    TrustTimelineItem(
                        lead_hours=lead,
                        lead_days=round(lead / 24.0, 2),
                        bust_probability=None,
                        risk_level=None,
                        decision_mode=None,
                        within_trust_horizon=False,
                        stability_index=None,
                        failure_fingerprint=None,
                        is_available=False,
                    )
                )

        # 8. Compute Operational Trust Horizon across evaluated items
        operational_horizon_hours: Optional[int] = None
        horizon_status = "WITHIN_HORIZON"

        sorted_items = sorted(forecast_items, key=lambda x: x.lead_hours)
        for it in sorted_items:
            if (
                it.bust_probability >= self.trust_horizon_threshold
                or (it.stability_index is not None and it.stability_index < 50.0)
                or it.decision_mode == DecisionMode.ABSTAIN.value
            ):
                operational_horizon_hours = it.lead_hours
                horizon_status = "DECAYS_AT_LEAD"
                break

        if operational_horizon_hours is None and sorted_items:
            operational_horizon_hours = sorted_items[-1].lead_hours
            horizon_status = "FULL_HORIZON_RELIABLE"

        op_trust_horizon = OperationalTrustHorizonInfo(
            operational_trust_horizon_hours=operational_horizon_hours,
            threshold_used=self.trust_horizon_threshold,
            threshold_type="product_design_threshold",
            status=horizon_status,
            scientific_note=(
                f"Pcrit ({self.trust_horizon_threshold:.2f}) is a configurable research/product design threshold, "
                "not a universal scientific constant. Subject to future empirical validation on the 1,040-cycle dataset."
            ),
        )

        # 9. Top-Level Decision Guidance
        if target_lead_hours is not None and target_lead_hours in eval_lead_map:
            active_item = eval_lead_map[target_lead_hours]
        else:
            abstain_items = [it for it in sorted_items if it.decision_mode == DecisionMode.ABSTAIN.value]
            critical_items = [it for it in sorted_items if it.decision_mode in (DecisionMode.DO_NOT_RELY_SOLELY.value, DecisionMode.RECHECK_SOON.value)]
            if abstain_items:
                active_item = abstain_items[0]
            elif critical_items:
                active_item = max(critical_items, key=lambda x: x.bust_probability)
            elif sorted_items:
                active_item = sorted_items[0]
            else:
                active_item = None

        if active_item:
            guidance = DecisionGuidance(
                decision_mode=active_item.decision_mode or DecisionMode.HIGH_TRUST.value,
                headline=f"{active_item.decision_mode}: {active_item.recommended_action}",
                actionable_recommendation=active_item.recommended_action or "Proceed with standard operations.",
                primary_reason=active_item.explanation.driver_summary if active_item.explanation else "Nominal",
                confidence_summary=f"Confidence Index: {active_item.confidence_index:.1f}/100 | Bust Risk: {active_item.bust_probability*100:.1f}%",
            )
        else:
            guidance = None

        return ForecastRiskResponse(
            request_id=f"req-{uuid.uuid4().hex[:12]}",
            location=location_info,
            issue_time=issue_time_str,
            model_version=model_version,
            decision_threshold=decision_threshold,
            provenance=provenance,
            forecasts=forecast_items,
            operational_trust_horizon=op_trust_horizon,
            decision_guidance=guidance,
            trust_timeline=trust_timeline,
        )

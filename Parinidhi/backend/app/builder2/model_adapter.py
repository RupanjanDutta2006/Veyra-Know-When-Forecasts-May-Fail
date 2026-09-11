"""Builder 2 HTTP & Local Model Inference Adapter for Veyra.

Communicates with Builder 2 authoritative ForecastIntelligenceService
over HTTP/REST (default: http://localhost:8001/api/forecast-risk) or via
in-process service when api_url is empty.

Receives calibrated bust probabilities, operational risk tiers, reliability indices,
structural overconfidence, OOD scores, trajectory stability, analytical failure fingerprints,
and physical risk drivers from the V3 Benchmark Challenger (or V2 Champion via rollback).
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import urllib.request
import urllib.error
import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.schemas.prediction import ReasonCode
from backend.app.services.base import BaseModelService, FeatureResult, ModelResult

logger = logging.getLogger(__name__)


class Builder2ModelAdapter(BaseModelService):
    """Production model adapter wrapping Veyra ForecastIntelligenceService.

    Uses the verified V3 Benchmark Challenger (or V2 Champion via rollback) with
    calibrated probability estimation at the decision threshold of 0.060.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        model_dir: Optional[Union[str, Path]] = None,
        aggregation_method: str = "max",
        timeout_seconds: float = 30.0,
        model_version: Optional[str] = None,
    ):
        if api_url is None:
            self.api_url = (os.getenv("BUILDER2_API_URL") or getattr(settings, "BUILDER2_API_URL", None) or os.getenv("BUILDER2_URL", "http://localhost:8001")).rstrip("/")
        else:
            self.api_url = api_url.rstrip("/") if api_url else ""
            
        self.use_http = bool(self.api_url)
        self.timeout_seconds = timeout_seconds
        self.aggregation_method = aggregation_method
        
        env_version = os.getenv("VEYRA_MODEL_VERSION", "v3").strip().lower()
        self.requested_version = (model_version or env_version).strip().lower()
        
        if self.requested_version == "v2":
            self.model_version: str = "veyra-v2-champion-lightgbm"
            self.decision_threshold: float = 0.060
        else:
            self.model_version: str = "veyra-v3-benchmark-lightgbm"
            self.decision_threshold: float = 0.060
            
        self.threshold: float = self.decision_threshold
        self.is_ready: bool = True
        
        if not self.use_http:
            try:
                from models.forecast_intelligence_service import ForecastIntelligenceService
                self.service = ForecastIntelligenceService(model_dir=model_dir, version=self.requested_version)
                self.is_ready = True
            except Exception as exc:
                logger.warning(f"Could not initialize local ForecastIntelligenceService: {exc}")
                self.service = None
                self.is_ready = False

    def predict(self, feature_result: FeatureResult) -> ModelResult:
        """Compute calibrated forecast-bust probability via Builder 2 HTTP or Local Service."""
        if not feature_result.is_ready or feature_result.error:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error=feature_result.error or "Features not ready for model inference",
            )

        matrix_rows = (
            feature_result.metadata.get("forecast_dataframe_rows")
            or feature_result.metadata.get("feature_matrix_rows")
        )
        if matrix_rows and isinstance(matrix_rows, list):
            forecast_data = matrix_rows
        elif feature_result.features:
            forecast_data = [feature_result.features]
        else:
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.FEATURES_NOT_READY.value},
                error="FeatureResult contains no feature data",
            )

        if not self.use_http:
            if not self.is_ready or self.service is None:
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.MODEL_UNAVAILABLE.value},
                    error="Local ForecastIntelligenceService unavailable or uninitialized",
                )
            df_features = pd.DataFrame(forecast_data)
            return self._predict_local(df_features)

        try:
            from backend.app.services.location_service import get_location_registry
            location_id = get_location_registry().resolve_canonical_id(feature_result.location) or feature_result.location or "delhi"
        except Exception:
            location_id = str(feature_result.location or "delhi").strip().lower()

        payload = {
            "forecast_data": forecast_data,
            "location_id": location_id,
            "forecast_source": "NOAA_GEFS",
        }

        endpoint_url = f"{self.api_url}/api/forecast-risk"
        req_data = json.dumps(payload).encode("utf-8")
        http_req = urllib.request.Request(
            endpoint_url,
            data=req_data,
            headers={"Content-Type": "application/json", "User-Agent": "VeyraBuilder1/3.0"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_req, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    return ModelResult(
                        probability=None,
                        model_version=self.model_version,
                        is_ready=False,
                        metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                        error=f"Builder 2 HTTP service returned status {response.status}",
                    )
                resp_bytes = response.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))

            forecasts = resp_json.get("forecasts", [])
            if not forecasts:
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                    error="Builder 2 returned zero forecast risk predictions",
                )

            probabilities = [f.get("bust_probability", 0.0) for f in forecasts]
            top_f = forecasts[0]

            if self.aggregation_method == "max":
                agg_prob = float(np.max(probabilities))
            else:
                agg_prob = float(np.mean(probabilities))

            if not (0.0 <= agg_prob <= 1.0) or np.isnan(agg_prob) or np.isinf(agg_prob):
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.QC_FAILED.value},
                    error=f"Model computed invalid probability: {agg_prob}",
                )

            model_ver = resp_json.get("model_version", self.model_version)
            thresh = float(resp_json.get("decision_threshold", self.threshold))

            trust_horizon_obj = resp_json.get("operational_trust_horizon") or {}
            op_trust_hours = trust_horizon_obj.get("operational_trust_horizon_hours")
            guidance_obj = resp_json.get("decision_guidance") or {}
            decision_mode_val = guidance_obj.get("decision_mode") or top_f.get("decision_mode")
            within_trust_val = top_f.get("within_trust_horizon")
            service_tag = "Builder2_HTTP_V2" if "v2" in model_ver.lower() else "Builder2_HTTP_V3"

            metadata: Dict[str, Any] = {
                "status": ReasonCode.SUCCESS.value,
                "model_version": model_ver,
                "decision_threshold": thresh,
                "risk_level": top_f.get("risk_level", "LOW"),
                "confidence_index": top_f.get("confidence_index", 100.0),
                "structural_overconfidence": top_f.get("structural_overconfidence", 0.0),
                "ood_score": top_f.get("ood_score", 0.0),
                "stability_index": top_f.get("stability_index", 100.0),
                "failure_fingerprint": top_f.get("failure_fingerprint", "NOMINAL"),
                "uncertainty_pct": top_f.get("uncertainty_pct", 3.37),
                "revision": top_f.get("revision"),
                "dominant_risk_drivers": top_f.get("dominant_risk_drivers") or [],
                "decision_mode": decision_mode_val,
                "within_trust_horizon": within_trust_val,
                "operational_trust_horizon_hours": op_trust_hours,
                "backend_service": service_tag,
            }

            return ModelResult(
                probability=round(agg_prob, 4),
                model_version=model_ver,
                is_ready=True,
                metadata=metadata,
            )

        except urllib.error.URLError as url_err:
            logger.error("Builder 2 HTTP connection error to %s: %s", endpoint_url, url_err)
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.MODEL_UNAVAILABLE.value},
                error=f"Builder 2 HTTP service unavailable at {self.api_url}: {url_err}",
            )
        except Exception as exc:
            logger.error("Builder 2 inference failed: %s", exc)
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                error=f"Builder 2 inference failed: {exc}",
            )

    def _predict_local(self, df_features: pd.DataFrame) -> ModelResult:
        try:
            results = self.service.evaluate_forecast(df_features)
            if not results:
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                    error="ForecastIntelligenceService returned zero results",
                )

            probabilities = [r.bust_probability for r in results]
            r_top = results[0]

            if self.aggregation_method == "max":
                agg_prob = float(np.max(probabilities))
            else:
                agg_prob = float(np.mean(probabilities))

            if not (0.0 <= agg_prob <= 1.0) or np.isnan(agg_prob) or np.isinf(agg_prob):
                return ModelResult(
                    probability=None,
                    model_version=self.model_version,
                    is_ready=False,
                    metadata={"status": ReasonCode.QC_FAILED.value},
                    error=f"Model computed invalid probability: {agg_prob}",
                )

            service_tag = "Builder2_Local_V2" if "v2" in self.model_version.lower() else "Builder2_Local_V3"

            metadata: Dict[str, Any] = {
                "status": ReasonCode.SUCCESS.value,
                "model_version": self.model_version,
                "decision_threshold": self.threshold,
                "risk_level": r_top.risk_level,
                "confidence_index": r_top.confidence_index,
                "structural_overconfidence": r_top.overconfidence_signal,
                "ood_score": r_top.ood_score,
                "stability_index": r_top.stability_index,
                "failure_fingerprint": r_top.provenance.get("failure_fingerprint", "NOMINAL"),
                "uncertainty_pct": r_top.provenance.get("prediction_uncertainty_pct", 3.37),
                "dominant_risk_drivers": [d.to_dict() if hasattr(d, "to_dict") else d for d in r_top.dominant_risk_drivers],
                "decision_mode": getattr(r_top, "decision_mode", None) or r_top.provenance.get("decision_mode"),
                "within_trust_horizon": getattr(r_top, "within_trust_horizon", None) or r_top.provenance.get("within_trust_horizon"),
                "operational_trust_horizon_hours": r_top.provenance.get("operational_trust_horizon_hours", 0),
                "backend_service": service_tag,
            }

            return ModelResult(
                probability=round(agg_prob, 4),
                model_version=self.model_version,
                is_ready=True,
                metadata=metadata,
            )
        except Exception as exc:
            logger.error("Local model inference failed: %s", exc)
            return ModelResult(
                probability=None,
                model_version=self.model_version,
                is_ready=False,
                metadata={"status": ReasonCode.INTERNAL_ERROR.value},
                error=f"Model inference failed: {exc}",
            )

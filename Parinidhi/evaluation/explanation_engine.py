"""
Failure Explanation and Risk Attribution Master Engine (Day 14).

Orchestrates the unified failure attribution, uncertainty decomposition,
OOD novelty analysis, historical analogue retrieval, and risk confidence pipeline.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from evaluation.attribution import ForecastRiskAttributionEngine
from evaluation.explanation_schema import CompositeFailureExplanation
from evaluation.failure_patterns import HistoricalFailureRetriever
from evaluation.novelty import FeatureNoveltyDetector
from evaluation.profiles import LocationRegimeProfiler
from evaluation.risk_confidence import RiskConfidenceEngine
from evaluation.uncertainty import UncertaintyDecomposer
from features.contract import validate_feature_contract


class ForecastFailureExplainer:
    """
    Unified engine for generating interpretable, structured forecast failure explanations.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        feature_names: Optional[List[str]] = None,
    ):
        self.model = model
        self.feature_names = feature_names or []
        self.novelty_detector = FeatureNoveltyDetector()
        self.uncertainty_decomposer = UncertaintyDecomposer(novelty_detector=self.novelty_detector)
        self.failure_retriever = HistoricalFailureRetriever()
        self.attribution_engine = ForecastRiskAttributionEngine(model=model, feature_names=feature_names)
        self.profiler = LocationRegimeProfiler()
        self.confidence_engine = RiskConfidenceEngine()
        self.is_fitted_ = False

    def fit_reference_context(
        self,
        df_train: pd.DataFrame,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model: Any,
        lolo_results: Optional[Dict[str, Any]] = None,
    ) -> "ForecastFailureExplainer":
        """
        Fit all reference modules strictly on training split data.
        """
        self.model = model
        self.feature_names = list(X_train.columns)

        # 1. Fit Novelty Detector
        self.novelty_detector.fit(X_train)
        self.uncertainty_decomposer.novelty_detector = self.novelty_detector

        # 2. Fit Failure Retriever
        loc_col = "location_id" if "location_id" in df_train.columns else ("location" if "location" in df_train.columns else None)
        err_col = "forecast_abs_error" if "forecast_abs_error" in df_train.columns else None

        locs = df_train[loc_col] if loc_col else None
        errs = df_train[err_col] if err_col else None

        self.failure_retriever.fit(
            X_train=X_train,
            y_train=y_train,
            errors_train=errs,
            locations_train=locs,
        )

        # 3. Fit Attribution Engine
        self.attribution_engine.fit_model_context(model=model, feature_names=self.feature_names)

        # 4. Fit Location / Regime Profiler
        self.profiler.fit_from_historical_data(df_train, lolo_results=lolo_results)

        self.is_fitted_ = True
        return self

    def explain_forecast(
        self,
        features: Union[pd.Series, pd.DataFrame, Dict[str, Any]],
        risk_probability: float,
        location_id: Optional[str] = None,
        variable: str = "temperature_2m",
    ) -> CompositeFailureExplanation:
        """
        Generate complete composite failure explanation for a forecast issue instance.
        """
        if isinstance(features, pd.DataFrame):
            row_dict = features.iloc[0].to_dict()
        elif isinstance(features, pd.Series):
            row_dict = features.to_dict()
        else:
            row_dict = dict(features)

        # 1. Determine Risk Level
        if risk_probability >= 0.70:
            risk_level = "CRITICAL"
        elif risk_probability >= 0.40:
            risk_level = "HIGH"
        elif risk_probability >= 0.20:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        # 2. Uncertainty Decomposition
        uncertainty_res = self.uncertainty_decomposer.decompose(row_dict, variable=variable)

        # 3. Novelty / OOD Diagnostics
        if self.novelty_detector.is_fitted_:
            novelty_res = self.novelty_detector.evaluate_sample(row_dict)
        else:
            novelty_res = {"novelty_score": 1.0, "novelty_state": "UNAUDITED", "outlier_features_count": 0}

        # 4. Historical Analogue Retrieval
        loc_str = str(location_id or row_dict.get("location_id", row_dict.get("location", ""))).lower()
        if self.failure_retriever.is_fitted_:
            retrieval_res = self.failure_retriever.retrieve(row_dict, filter_location=loc_str if loc_str else None)
        else:
            retrieval_res = {"support_status": "UNAUDITED", "analogue_count": 0}

        # 5. Feature Attribution
        drivers = self.attribution_engine.attribute(row_dict, top_k=5)

        # 6. Location / Regime Profile
        loc_prof = self.profiler.get_location_profile(loc_str) if loc_str else {}

        # 7. Missing feature check
        missing_count = sum(1 for f in self.feature_names if pd.isna(row_dict.get(f, np.nan)))
        missing_fraction = missing_count / max(len(self.feature_names), 1)

        # 8. Self-Confidence Assessment
        confidence_res = self.confidence_engine.evaluate_confidence(
            risk_probability=risk_probability,
            novelty_eval=novelty_res,
            retrieval_eval=retrieval_res,
            location_profile=loc_prof,
            missing_feature_fraction=missing_fraction,
        )

        # 9. Lead-time context
        lead_h = int(row_dict.get("lead_hours", 24))
        lead_context = {
            "lead_hours": lead_h,
            "horizon_window": "SHORT (0-24h)" if lead_h <= 24 else ("MEDIUM (25-48h)" if lead_h <= 48 else "EXTENDED (49-72h)"),
            "lead_risk_factor": round(float(lead_h / 72.0), 2),
        }

        # 10. Operational Warnings
        warnings = []
        if novelty_res.get("novelty_state") in ["HIGH", "EXTREME"]:
            warnings.append("High meteorological novelty: Forecast features lie outside standard training distribution.")
        if confidence_res.get("confidence_level") in ["LOW", "VERY_LOW"]:
            warnings.append("Low estimate confidence: Risk score reflects elevated uncertainty in model extrapolation.")
        if lead_h >= 48:
            warnings.append("Extended forecast horizon: Vulnerable to synoptic timing errors.")
        if uncertainty_res.get("dominant_uncertainty_driver") == "ENSEMBLE_DISPERSION":
            warnings.append("High ensemble dispersion: NWP initializations diverge significantly.")

        provenance = {
            "engine_version": "14.0.0",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_type": type(self.model).__name__ if self.model else "Heuristic",
            "feature_count": len(self.feature_names) or len(row_dict),
        }

        return CompositeFailureExplanation(
            risk_probability=round(float(risk_probability), 4),
            risk_level=risk_level,
            risk_confidence=confidence_res["risk_confidence"],
            confidence_level=confidence_res["confidence_level"],
            primary_drivers=drivers,
            uncertainty_components=uncertainty_res,
            novelty=novelty_res,
            historical_analogues=retrieval_res,
            lead_time_context=lead_context,
            location_profile=loc_prof,
            warnings=warnings,
            provenance=provenance,
        )

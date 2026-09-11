"""
API Router and Service Handlers.

Provides typed dispatching functions for health checks, location listings,
forecast risk inference, regional risk aggregations, and deterministic demonstration scenarios.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Union
import pandas as pd

from api.demo_scenarios import DEMO_SCENARIOS_METADATA, generate_scenario_dataframe
from api.location_service import LocationRegistry
from api.regional_aggregator import RegionalRiskAggregator
from api.risk_engine import OperationalRiskEngine
from api.schemas import (
    ForecastRiskResponse,
    RegionalRiskSummaryResponse,
)


class ForecastBustAPI:
    """REST API service controller for Forecast-Bust Sentinel."""

    def __init__(
        self,
        risk_engine: Optional[OperationalRiskEngine] = None,
        location_registry: Optional[LocationRegistry] = None,
    ):
        self.risk_engine = risk_engine or OperationalRiskEngine()
        self.location_registry = location_registry or LocationRegistry()

    def get_health(self) -> Dict[str, Any]:
        """Return system health, loaded model version, and runtime status."""
        svc = self.risk_engine.intelligence_service
        return {
            "status": "healthy",
            "service": "Forecast-Bust Sentinel Operational API",
            "model_version": svc.model_version,
            "decision_threshold": float(svc.operational_threshold),
            "trust_horizon_threshold": float(self.risk_engine.trust_horizon_threshold),
            "ood_severe_threshold": float(self.risk_engine.ood_severe_threshold),
            "feature_count": len(svc.feature_names),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def list_locations(self) -> Dict[str, Any]:
        """Return all registered meteorological monitoring locations."""
        locations = self.location_registry.list_locations()
        return {
            "count": len(locations),
            "locations": locations,
        }

    def list_scenarios(self) -> Dict[str, Any]:
        """Return metadata for all 4 deterministic demonstration fixtures."""
        return {
            "count": len(DEMO_SCENARIOS_METADATA),
            "disclaimer": (
                "Deterministic demonstration fixtures clearly labeled as demo/simulation scenarios. "
                "NOT scientific validation cases and must NOT be presented as measured real-world performance evidence."
            ),
            "scenarios": DEMO_SCENARIOS_METADATA,
        }

    def run_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """Run a deterministic demonstration fixture through the authoritative operational risk pipeline."""
        df_scenario, meta = generate_scenario_dataframe(scenario_id)
        res = self.risk_engine.process_forecast_dataframe(
            df_forecast=df_scenario,
            location_id=meta["location_id"],
            forecast_source="NOAA_GEFS_SIMULATION_FIXTURE",
            grid_resolution="0.25°",
            target_lead_hours=meta.get("lead_hours"),
        )
        data = res.to_dict()
        data["scenario_meta"] = meta
        return data

    def get_forecast_risk(
        self,
        forecast_input: Union[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]],
        location_id: str = "delhi",
        forecast_source: str = "NOAA_GEFS",
        grid_resolution: Optional[str] = None,
        max_truth_time_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Compute operational forecast bust probabilities and explanations.

        Args:
            forecast_input: DataFrame or records of standardized forecast steps.
            location_id: Target location ID.
            forecast_source: NWP forecast source name.
            grid_resolution: Optional grid resolution string.
            max_truth_time_utc: Optional ground-truth cutoff timestamp for verification status.

        Returns:
            Dict representing ForecastRiskResponse.
        """
        if isinstance(forecast_input, pd.DataFrame):
            df = forecast_input
        elif isinstance(forecast_input, list):
            df = pd.DataFrame(forecast_input)
        elif isinstance(forecast_input, dict):
            df = pd.DataFrame([forecast_input])
        else:
            raise TypeError(f"Unsupported forecast_input type: {type(forecast_input).__name__}")

        response: ForecastRiskResponse = self.risk_engine.process_forecast_dataframe(
            df_forecast=df,
            location_id=location_id,
            forecast_source=forecast_source,
            grid_resolution=grid_resolution,
            max_truth_time_utc=max_truth_time_utc,
        )

        return response.to_dict()

    def get_regional_summary(
        self,
        region_name: str,
        location_forecast_inputs: Dict[str, Union[pd.DataFrame, List[Dict[str, Any]]]],
        forecast_source: str = "NOAA_GEFS",
        grid_resolution: Optional[str] = None,
        max_truth_time_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Compute transparent spatial summary across multiple locations in a region.

        Args:
            region_name: Descriptive region name.
            location_forecast_inputs: Dict mapping location_id -> forecast data.
            forecast_source: NWP forecast source name.
            grid_resolution: Optional grid resolution string.
            max_truth_time_utc: Optional ground-truth cutoff timestamp.

        Returns:
            Dict representing RegionalRiskSummaryResponse.
        """
        responses: List[ForecastRiskResponse] = []

        for loc_id, f_data in location_forecast_inputs.items():
            if isinstance(f_data, pd.DataFrame):
                df = f_data
            else:
                df = pd.DataFrame(f_data)

            resp = self.risk_engine.process_forecast_dataframe(
                df_forecast=df,
                location_id=loc_id,
                forecast_source=forecast_source,
                grid_resolution=grid_resolution,
                max_truth_time_utc=max_truth_time_utc,
            )
            responses.append(resp)

        summary: RegionalRiskSummaryResponse = RegionalRiskAggregator.aggregate_region(
            region_name=region_name,
            location_responses=responses,
        )

        return summary.to_dict()

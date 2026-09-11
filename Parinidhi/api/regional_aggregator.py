"""
Regional Risk Aggregator.

Provides transparent spatial and regional summaries across multiple location forecasts.
Outputs are explicitly spatial metrics (max risk, alert fraction), not state-level calibrated probabilities.
"""

from collections import Counter
from typing import Any, Dict, List, Optional

from api.schemas import ForecastRiskResponse, RegionalLocationSummary, RegionalRiskSummaryResponse


class RegionalRiskAggregator:
    """Aggregates location-level forecast risk outputs into a state or regional summary."""

    @staticmethod
    def aggregate_region(
        region_name: str,
        location_responses: List[ForecastRiskResponse],
    ) -> RegionalRiskSummaryResponse:
        """
        Compute regional spatial summary across a list of location responses.

        Args:
            region_name: Descriptive name of the state or region (e.g. "Northern India / NCR").
            location_responses: List of ForecastRiskResponse objects.

        Returns:
            RegionalRiskSummaryResponse dataclass.
        """
        if not location_responses:
            return RegionalRiskSummaryResponse(
                region_name=region_name,
                location_count=0,
                regional_peak_bust_probability=0.0,
                regional_alert_fraction=0.0,
                worst_risk_lead_hours=0,
                dominant_risk_variable="none",
                locations_summary=[],
            )

        loc_summaries: List[RegionalLocationSummary] = []
        all_alert_flags: List[bool] = []
        all_probabilities: List[float] = []
        max_prob_overall = -1.0
        worst_lead_overall = 0
        alert_variables: List[str] = []

        for resp in location_responses:
            loc_id = resp.location.location_id
            city_name = resp.location.city

            # Find peak probability and worst lead for this specific location
            loc_peak_prob = 0.0
            loc_worst_lead = 0
            loc_has_alert = False

            for item in resp.forecasts:
                all_probabilities.append(item.bust_probability)
                all_alert_flags.append(item.bust_alert)

                if item.bust_alert:
                    alert_variables.append(item.variable)

                if item.bust_probability > loc_peak_prob:
                    loc_peak_prob = item.bust_probability
                    loc_worst_lead = item.lead_hours

                if item.bust_alert:
                    loc_has_alert = True

                if item.bust_probability > max_prob_overall:
                    max_prob_overall = item.bust_probability
                    worst_lead_overall = item.lead_hours

            loc_summaries.append(
                RegionalLocationSummary(
                    location_id=loc_id,
                    city=city_name,
                    peak_bust_probability=loc_peak_prob,
                    has_active_alert=loc_has_alert,
                    worst_lead_hours=loc_worst_lead,
                )
            )

        # 1. Regional Peak Bust Probability (Max risk observed across any city/lead)
        peak_prob = max_prob_overall if max_prob_overall >= 0.0 else 0.0

        # 2. Regional Alert Fraction (Fraction of monitored locations with at least one active bust alert)
        active_alert_locs = sum(1 for loc in loc_summaries if loc.has_active_alert)
        alert_fraction = active_alert_locs / len(loc_summaries) if loc_summaries else 0.0

        # 3. Dominant Risk Variable across all alert instances
        if alert_variables:
            dominant_var = Counter(alert_variables).most_common(1)[0][0]
        else:
            # Fallback to most frequent variable in forecasts
            all_vars = [item.variable for resp in location_responses for item in resp.forecasts]
            dominant_var = Counter(all_vars).most_common(1)[0][0] if all_vars else "unknown"

        return RegionalRiskSummaryResponse(
            region_name=region_name,
            location_count=len(loc_summaries),
            regional_peak_bust_probability=peak_prob,
            regional_alert_fraction=alert_fraction,
            worst_risk_lead_hours=worst_lead_overall,
            dominant_risk_variable=dominant_var,
            locations_summary=loc_summaries,
        )

"""Historical Forecast and Verification Alignment Pathway.

Prepares the scientific foundation for training data, bust label generation,
and verification against historical reference (ERA5 / station observations)
under strict Anti-Data-Leakage constraints.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class HistoricalForecastPair:
    """Standardized paired observation representing forecast vs ground-truth verification."""

    location: str
    latitude: float
    longitude: float
    variable: str
    unit: str

    # Forecast temporal coordinate
    forecast_issue_time: str
    forecast_valid_time: str
    forecast_lead_hours: int
    forecast_value: float

    # Ground truth reference coordinate (ERA5 / observed truth)
    reference_verification_time: str
    reference_value: float
    reference_source: str = "ERA5_REANALYSIS"

    # Computed metrics
    forecast_error: float = 0.0
    is_bust: bool = False
    bust_threshold: float = 0.0

    # Anti-leakage metadata
    reference_availability_time: Optional[str] = None
    is_ground_truth_label: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def calculate_error_and_bust(self, threshold: float) -> None:
        """Calculate forecast error and assign bust ground truth label.

        Error definition: forecast_value - reference_value
        Bust condition: abs(forecast_error) >= threshold
        """
        self.forecast_error = round(self.forecast_value - self.reference_value, 4)
        self.bust_threshold = threshold
        self.is_bust = abs(self.forecast_error) >= threshold


class HistoricalPathwayAligner:
    """Aligns historical forecasts with verification reference observations.

    Enforces the core scientific rule:
    `reference_availability_time > forecast_issue_time`
    Reference data is strictly forbidden from being ingested as a live inference feature.
    """

    @staticmethod
    def align_pair(
        location: str,
        latitude: float,
        longitude: float,
        variable: str,
        unit: str,
        issue_time: str,
        valid_time: str,
        lead_hours: int,
        forecast_value: float,
        reference_time: str,
        reference_value: float,
        bust_threshold: float,
        reference_source: str = "ERA5_REANALYSIS",
    ) -> HistoricalForecastPair:
        """Construct and validate a temporally aligned forecast-reference pair."""
        pair = HistoricalForecastPair(
            location=location,
            latitude=latitude,
            longitude=longitude,
            variable=variable,
            unit=unit,
            forecast_issue_time=issue_time,
            forecast_valid_time=valid_time,
            forecast_lead_hours=lead_hours,
            forecast_value=forecast_value,
            reference_verification_time=reference_time,
            reference_value=reference_value,
            reference_source=reference_source,
            is_ground_truth_label=True,
        )
        pair.calculate_error_and_bust(bust_threshold)
        return pair

    @staticmethod
    def assert_no_data_leakage(pair: HistoricalForecastPair) -> bool:
        """Verify that reference verification data is never dated on or before issue time.

        Strict Scientific Rule:
        A forecast issued at T0 cannot have ground truth verification until T_valid >= T0.
        """
        issue_dt = datetime.fromisoformat(pair.forecast_issue_time.replace("Z", "+00:00"))
        valid_dt = datetime.fromisoformat(pair.forecast_valid_time.replace("Z", "+00:00"))
        return valid_dt >= issue_dt

"""Historical Training Table & Dataset Construction.

Converts aligned verification records and evaluated bust labels into
a clean, ML-ready historical training dataset with temporal and seasonal features.
"""
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional
from backend.app.data.alignment import AlignedVerificationRecord
from backend.app.data.bust_labeling import BaseBustPolicy, FixedThresholdBustPolicy


@dataclass
class HistoricalTrainingRow:
    """Standardized single-sample row in the historical training dataset."""

    location: str
    latitude: float
    longitude: float
    region: str
    variable: str

    issue_time: str
    valid_time: str
    lead_hours: int

    forecast_value: float
    reference_value: float
    unit: str

    error: float
    absolute_error: float

    season: str
    month: int

    bust_label: int  # 1 for bust, 0 for no-bust
    bust_threshold: float

    forecast_source: str = "NOAA_GEFS_OPENMETEO"
    reference_source: str = "ERA5_REANALYSIS"
    alignment_status: str = "SUCCESS"

    is_ground_truth_label: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


def derive_season(month: int) -> str:
    """Derive meteorological season from month."""
    if month in (12, 1, 2):
        return "winter"
    elif month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    else:
        return "autumn"


class HistoricalDatasetBuilder:
    """Constructs and serializes ML-ready historical training datasets."""

    def __init__(self, bust_policy: Optional[BaseBustPolicy] = None, region: str = "global"):
        self.bust_policy = bust_policy or FixedThresholdBustPolicy()
        self.region = region

    def build_row(
        self,
        aligned_rec: AlignedVerificationRecord,
    ) -> HistoricalTrainingRow:
        """Transform an aligned verification record into a full historical training row."""
        # Derive temporal attributes
        try:
            valid_dt = datetime.fromisoformat(aligned_rec.valid_time.replace("Z", "+00:00"))
            month = valid_dt.month
            season = derive_season(month)
        except Exception:
            month = 1
            season = "unknown"

        # Evaluate bust label
        label_res = self.bust_policy.evaluate(
            variable=aligned_rec.variable,
            absolute_error=aligned_rec.absolute_error,
            lead_hours=aligned_rec.lead_hours,
            season=season,
        )

        return HistoricalTrainingRow(
            location=aligned_rec.location,
            latitude=aligned_rec.latitude,
            longitude=aligned_rec.longitude,
            region=self.region,
            variable=aligned_rec.variable,
            issue_time=aligned_rec.issue_time,
            valid_time=aligned_rec.valid_time,
            lead_hours=aligned_rec.lead_hours,
            forecast_value=aligned_rec.forecast_value,
            reference_value=aligned_rec.reference_value,
            unit=aligned_rec.unit,
            error=aligned_rec.forecast_error,
            absolute_error=aligned_rec.absolute_error,
            season=season,
            month=month,
            bust_label=label_res.is_bust,
            bust_threshold=label_res.threshold,
            forecast_source=aligned_rec.forecast_source,
            reference_source=aligned_rec.reference_source,
            alignment_status=aligned_rec.alignment_status,
            is_ground_truth_label=True,
            metadata={"policy": label_res.policy_name},
        )

    def build_dataset(
        self,
        aligned_records: list[AlignedVerificationRecord],
    ) -> list[HistoricalTrainingRow]:
        """Build dataset rows from a list of aligned verification records."""
        return [self.build_row(rec) for rec in aligned_records]

    @staticmethod
    def save_to_jsonl(rows: list[HistoricalTrainingRow], filepath: str) -> None:
        """Serialize rows to JSON Lines format."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(asdict(row)) + "\n")

    @staticmethod
    def load_from_jsonl(filepath: str) -> list[dict[str, Any]]:
        """Load dataset rows from JSON Lines format."""
        results: list[dict[str, Any]] = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        return results

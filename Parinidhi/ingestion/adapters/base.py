"""Base interfaces and contracts for historical and operational forecast data source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import pandas as pd


class BaseForecastSourceAdapter(ABC):
    """Abstract Base Class for Forecast Data Source Adapters.

    Adapters isolate the downstream Builder 2 pipeline (QC, alignment, feature engineering,
    labeling, model training, risk evaluation) from underlying storage formats (direct NOAA S3
    byte slices, Zarr stores, GRIB2 archives, cloud object stores, etc.).
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Canonical identifier of the data source provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model version identifier (e.g., GEFSv12-reforecast)."""
        pass

    @abstractmethod
    def discover_members(self, issue_time: Union[str, datetime, pd.Timestamp]) -> List[int]:
        """Discover actual available ensemble members for a given model run."""
        pass

    @abstractmethod
    def fetch_run(
        self,
        issue_time: Union[str, datetime, pd.Timestamp],
        locations: Sequence[Dict[str, Any]],
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
        horizon_hours: int = 72,
        step_hours: int = 3,
        members: Optional[Sequence[int]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Fetch real forecast data for one model run initialization across multiple locations.

        Args:
            issue_time: Model run initialization time (UTC).
            locations: List of location dicts, each with at least 'location_id' (or 'location'),
                       'latitude', and 'longitude'.
            variables: Variables to retrieve.
            horizon_hours: Maximum forecast lead in hours.
            step_hours: Lead step increment in hours.
            members: Optional subset of member IDs (0 for c00, 1..N for p01..pN).

        Returns:
            Tuple of (standardized_dataframe, manifest_dict).
        """
        pass

    @abstractmethod
    def fetch_range(
        self,
        start_date: Union[str, datetime, pd.Timestamp],
        end_date: Union[str, datetime, pd.Timestamp],
        locations: Sequence[Dict[str, Any]],
        cycle: str = "00",
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
        horizon_hours: int = 72,
        step_hours: int = 3,
        use_cache: bool = True,
    ) -> Tuple[pd.DataFrame, Dict[str, Any], Any, Any]:
        """Fetch real forecast data over a date range across multiple locations.

        Returns:
            Tuple of (combined_df, range_manifest, raw_summary_path, manifest_path).
        """
        pass

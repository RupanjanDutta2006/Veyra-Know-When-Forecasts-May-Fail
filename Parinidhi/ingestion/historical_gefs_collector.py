"""NOAA GEFSv12 reforecast collector.

This collector uses direct NOAA AWS S3 index and HTTP range requests via the
NOAAS3ReforecastAdapter. Every record keeps the exact initialization time, member,
source URL, model version, and actual NWP grid point. No issue time is inferred
from the first valid time.

The public Phase-2 reforecast archive is 00Z once per day, with c00+p01..p04 on
normal days and c00+p01..p10 on the extended weekly runs.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from ingestion.adapters.noaa_s3 import (
    NOAAS3ReforecastAdapter,
    MODEL_VERSION,
    SOURCE_NAME as SOURCE,
    NOAA_REFORECAST_S3_ROOT as NOAA_ROOT,
    _member_code,
    _utc_date,
    _haversine_km,
)

VARIABLES = {
    "temperature_2m": {"file": "tmp_2m", "search": ":TMP:2 m above ground:", "unit": "degC"},
    "surface_pressure": {"file": "pres_msl", "search": ":PRES:mean sea level:", "unit": "hPa"},
    "u_wind_10m": {"file": "ugrd_hgt", "search": ":UGRD:10 m above ground:", "unit": "m/s"},
    "v_wind_10m": {"file": "vgrd_hgt", "search": ":VGRD:10 m above ground:", "unit": "m/s"},
}


def _url(issue: pd.Timestamp, member: int, prefix: str) -> str:
    code = _member_code(member)
    stamp = issue.strftime("%Y%m%d%H")
    year = issue.strftime("%Y")
    return f"{NOAA_ROOT}/{year}/{stamp}/{code}/Days:1-10/{prefix}_{stamp}_{code}.grib2"


def _exists(url: str) -> bool:
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "forecast-bust-sentinel/2.0"})
        with urlopen(req, timeout=15) as response:
            return 200 <= response.status < 400
    except (HTTPError, URLError, TimeoutError, Exception):
        return False


def discover_members(issue_time: Union[str, datetime, pd.Timestamp], max_member: int = 10) -> List[int]:
    """Discover the actual member directories present for a run.

    We probe the c00 temperature file and p01..p10 temperature files. This avoids
    hard-coding the weekly 11-member schedule and makes member_count auditable.
    """
    adapter = NOAAS3ReforecastAdapter()
    return adapter.discover_members(issue_time, max_member=max_member)


class HistoricalGEFSCollector:
    """Fetch real GEFSv12 reforecast values at requested point locations."""

    def __init__(self, raw_dir: str = "data/raw/gefs_reforecast"):
        self.raw_dir = Path(raw_dir)
        self.adapter = NOAAS3ReforecastAdapter(raw_dir=raw_dir)

    def collect_run(
        self,
        issue_time: Union[str, datetime, pd.Timestamp],
        latitude: float,
        longitude: float,
        location_name: str,
        horizon_hours: int = 72,
        step_hours: int = 3,
        members: Optional[Sequence[int]] = None,
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Collect one exact 00Z run and return ensemble-summary rows.

        The underlying member-level values are preserved in a sidecar JSON manifest
        keyed by variable/valid_time/member. The returned table remains compatible
        with the existing Builder-2 pipeline.
        """
        locations = [{"location": location_name, "latitude": latitude, "longitude": longitude}]
        df, manifest = self.adapter.fetch_run(
            issue_time=issue_time,
            locations=locations,
            variables=variables,
            horizon_hours=horizon_hours,
            step_hours=step_hours,
            members=members,
        )
        return df, manifest

    def collect_multi_location_run(
        self,
        issue_time: Union[str, datetime, pd.Timestamp],
        locations: Sequence[Dict[str, Any]],
        horizon_hours: int = 72,
        step_hours: int = 3,
        members: Optional[Sequence[int]] = None,
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Collect one exact 00Z run across multiple locations in a single vectorized pass."""
        return self.adapter.fetch_run(
            issue_time=issue_time,
            locations=locations,
            variables=variables,
            horizon_hours=horizon_hours,
            step_hours=step_hours,
            members=members,
        )

    def collect_range(
        self,
        start_date: Union[str, datetime, pd.Timestamp],
        end_date: Union[str, datetime, pd.Timestamp],
        cycle: str,
        horizon_hours: int,
        step_hours: int,
        latitude: float,
        longitude: float,
        location_name: str,
        use_cache: bool = True,
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
    ) -> Tuple[pd.DataFrame, Dict[str, Any], Path, Path]:
        """Collect historical forecast data over a date range for a single location."""
        locations = [{"location": location_name, "latitude": latitude, "longitude": longitude}]
        return self.adapter.fetch_range(
            start_date=start_date,
            end_date=end_date,
            locations=locations,
            cycle=cycle,
            variables=variables,
            horizon_hours=horizon_hours,
            step_hours=step_hours,
            use_cache=use_cache,
        )

    def collect_multi_location_range(
        self,
        start_date: Union[str, datetime, pd.Timestamp],
        end_date: Union[str, datetime, pd.Timestamp],
        locations: Sequence[Dict[str, Any]],
        cycle: str = "00",
        horizon_hours: int = 72,
        step_hours: int = 3,
        use_cache: bool = True,
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
    ) -> Tuple[pd.DataFrame, Dict[str, Any], Path, Path]:
        """Collect historical forecast data over a date range for multiple locations simultaneously."""
        return self.adapter.fetch_range(
            start_date=start_date,
            end_date=end_date,
            locations=locations,
            cycle=cycle,
            variables=variables,
            horizon_hours=horizon_hours,
            step_hours=step_hours,
            use_cache=use_cache,
        )

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        return _haversine_km(lat1, lon1, lat2, lon2)

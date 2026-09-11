"""Unit and integration tests for the NOAA S3 historical forecast adapter."""

import math
import numpy as np
import pandas as pd
import pytest

from ingestion.adapters.base import BaseForecastSourceAdapter
from ingestion.adapters.noaa_s3 import (
    NOAAS3ReforecastAdapter,
    MODEL_VERSION,
    SOURCE_NAME,
    VARIABLE_SPECS,
    _member_code,
    _haversine_km,
    _utc_date,
)
from backend.app.builder2.location_service import LocationRegistry, haversine_distance_km


def test_member_code_formatting():
    assert _member_code(0) == "c00"
    assert _member_code(1) == "p01"
    assert _member_code(4) == "p04"
    assert _member_code(10) == "p10"


def test_authoritative_s3_url_formatting():
    adapter = NOAAS3ReforecastAdapter()
    issue = pd.Timestamp("2017-03-14T00:00:00Z")
    url_grib = adapter._build_url(issue, 0, "tmp_2m", is_idx=False)
    url_idx = adapter._build_url(issue, 0, "tmp_2m", is_idx=True)

    assert url_grib == "https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast/2017/2017031400/c00/Days:1-10/tmp_2m_2017031400_c00.grib2"
    assert url_idx == "https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast/2017/2017031400/c00/Days:1-10/tmp_2m_2017031400_c00.grib2.idx"


def test_variable_specs_and_transforms():
    assert "temperature_2m" in VARIABLE_SPECS
    assert "surface_pressure" in VARIABLE_SPECS
    assert "u_wind_10m" in VARIABLE_SPECS
    assert "v_wind_10m" in VARIABLE_SPECS

    # Temperature K to °C
    t_c = VARIABLE_SPECS["temperature_2m"]["transform"](300.15)
    assert pytest.approx(t_c, 0.01) == 27.00

    # Pressure Pa to hPa
    p_hpa = VARIABLE_SPECS["surface_pressure"]["transform"](101325.0)
    assert pytest.approx(p_hpa, 0.01) == 1013.25


def test_idx_byte_range_parser():
    adapter = NOAAS3ReforecastAdapter()
    sample_idx = """1:0:d=2017031400:TMP:2 m above ground:3 hour fcst:ENS=low-res ctl
2:722128:d=2017031400:TMP:2 m above ground:6 hour fcst:ENS=low-res ctl
3:1460327:d=2017031400:TMP:2 m above ground:9 hour fcst:ENS=low-res ctl
4:2206145:d=2017031400:TMP:2 m above ground:12 hour fcst:ENS=low-res ctl"""

    ranges = adapter._parse_idx_byte_ranges(sample_idx, "TMP", "2 m above ground")
    assert 3 in ranges
    assert 6 in ranges
    assert 9 in ranges
    assert 12 in ranges

    assert ranges[3] == (0, 722127)
    assert ranges[6] == (722128, 1460326)
    assert ranges[9] == (1460327, 2206144)
    assert ranges[12] == (2206145, None)


def test_haversine_distance_calculations():
    # Delhi to Kolkata (~1300 km)
    dist = _haversine_km(28.6139, 77.2090, 22.5726, 88.3639)
    assert 1250 < dist < 1350

    # Same coordinate distance should be zero
    assert _haversine_km(28.6139, 77.2090, 28.6139, 77.2090) == pytest.approx(0.0, abs=0.01)


def test_reforecast_rejects_non_00z_cycle():
    adapter = NOAAS3ReforecastAdapter()
    with pytest.raises(ValueError, match="00Z only"):
        adapter.fetch_run(
            issue_time="2017-03-14T06:00:00Z",
            locations=[{"location": "delhi", "latitude": 28.61, "longitude": 77.20}],
        )


def test_reforecast_rejects_invalid_horizon_and_step():
    adapter = NOAAS3ReforecastAdapter()
    # Invalid horizon < 3
    with pytest.raises(ValueError, match="between 3 and 237"):
        adapter.fetch_run(
            issue_time="2017-03-14T00:00:00Z",
            locations=[{"location": "delhi", "latitude": 28.61, "longitude": 77.20}],
            horizon_hours=0,
        )

    # Invalid step (not multiple of 3)
    with pytest.raises(ValueError, match="multiple of 3"):
        adapter.fetch_run(
            issue_time="2017-03-14T00:00:00Z",
            locations=[{"location": "delhi", "latitude": 28.61, "longitude": 77.20}],
            horizon_hours=12,
            step_hours=5,
        )


def test_adapter_interface_hierarchy():
    adapter = NOAAS3ReforecastAdapter()
    assert isinstance(adapter, BaseForecastSourceAdapter)
    assert adapter.source_name == SOURCE_NAME
    assert adapter.model_name == MODEL_VERSION


def test_location_registry_25_locations_resolved():
    registry = LocationRegistry()
    location_ids = registry.get_all_location_ids()
    assert len(location_ids) == 25

    for loc_id in location_ids:
        info = registry.get_location(loc_id)
        assert info.location_id == loc_id
        assert -90 <= info.requested_coordinates.latitude <= 90
        assert -180 <= info.requested_coordinates.longitude <= 180

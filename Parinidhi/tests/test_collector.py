"""
Unit tests for GEFS Ingestion Collector & Authoritative Model Status Verification.

Tests:
1. Normal case: Authoritative status query retrieves valid cycle time.
2. Failure case: Unreachable status registry raises RuntimeError (strictly NO silent 00z fallback).
3. Manifest integrity: Provenance manifest records authoritative status response and explicit issue time.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from ingestion.collector import GEFSCollector


def test_authoritative_status_retrieval_success():
    """Test that query_model_status successfully parses NOAA S3 cycle registry."""
    collector = GEFSCollector()
    mock_s3_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult>
        <Prefix>gefs.20260825/</Prefix>
        <CommonPrefixes><Prefix>gefs.20260825/00/</Prefix></CommonPrefixes>
        <CommonPrefixes><Prefix>gefs.20260825/06/</Prefix></CommonPrefixes>
        <CommonPrefixes><Prefix>gefs.20260825/12/</Prefix></CommonPrefixes>
        <CommonPrefixes><Prefix>gefs.20260825/18/</Prefix></CommonPrefixes>
    </ListBucketResult>
    """
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = mock_s3_xml.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        cycle_dt, status_info = collector.query_model_status(datetime(2026, 8, 25, tzinfo=timezone.utc))

        assert cycle_dt == datetime(2026, 8, 25, 18, 0, 0, tzinfo=timezone.utc)
        assert status_info["selected_cycle"] == "18z"
        assert status_info["available_cycles"] == ["00", "06", "12", "18"]
        assert status_info["verified_initialization_time_utc"] == "2026-08-25T18:00:00+00:00"


def test_authoritative_status_failure_raises_loudly():
    """
    Test that failure to reach Open-Meteo and NOAA registry raises a loud RuntimeError.
    Strictly verifies that NO silent 00z fallback is performed.
    """
    collector = GEFSCollector()

    # Simulate network failure / unreachable registry
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")):
        with pytest.raises(RuntimeError, match="Failed to obtain authoritative GEFS model-run status"):
            collector.query_model_status(datetime(2026, 8, 25, tzinfo=timezone.utc))


def test_query_range_cycles_historical():
    """Test querying and verifying cycles for a historical date range."""
    collector = GEFSCollector()
    mock_s3_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <ListBucketResult>
        <Prefix>gefs.20260820/</Prefix>
        <CommonPrefixes><Prefix>gefs.20260820/00/</Prefix></CommonPrefixes>
        <CommonPrefixes><Prefix>gefs.20260820/06/</Prefix></CommonPrefixes>
        <CommonPrefixes><Prefix>gefs.20260820/12/</Prefix></CommonPrefixes>
        <CommonPrefixes><Prefix>gefs.20260820/18/</Prefix></CommonPrefixes>
    </ListBucketResult>
    """
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = mock_s3_xml.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        range_results = collector.query_range_cycles("2026-08-20", "2026-08-20")
        assert "20260820" in range_results
        assert range_results["20260820"]["status"] == "VERIFIED"
        assert range_results["20260820"]["latest_cycle"] == "18z"
        assert range_results["20260820"]["available_cycles"] == ["00", "06", "12", "18"]


def test_fetch_forecast_saves_status_json(tmp_path):
    """Test that fetch_forecast records raw status json alongside raw data and manifest."""
    collector = GEFSCollector(raw_dir=str(tmp_path))

    mock_raw_payload = {
        "latitude": 28.5,
        "longitude": 77.25,
        "elevation": 214.0,
        "generationtime_ms": 1.0,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": ["2026-08-25T18:00", "2026-08-25T19:00"],
            "temperature_2m": [28.0, 27.5],
            "surface_pressure": [980.0, 981.0],
            "wind_speed_10m": [10.0, 9.0],
        },
    }

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = bytes(str(mock_raw_payload).replace("'", '"'), "utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(collector, "query_model_status") as mock_status:
        mock_status.return_value = (
            datetime(2026, 8, 25, 18, 0, 0, tzinfo=timezone.utc),
            {
                "authoritative_source": "NOAA NCEP GEFS AWS S3 Open Data Registry",
                "selected_cycle": "18z",
                "verified_initialization_time_utc": "2026-08-25T18:00:00+00:00",
            },
        )
        with patch("urllib.request.urlopen", return_value=mock_resp):
            raw_data, raw_path, manifest_path, manifest = collector.fetch_forecast(
                location_name="delhi",
                forecast_days=1,
            )

            assert raw_path.exists()
            assert manifest_path.exists()
            status_path = Path(manifest["status_file_path"])
            assert status_path.exists()
            assert manifest["explicit_issue_time_utc"] == "2026-08-25T18:00:00+00:00"
            assert manifest["issue_time_source"] == "NOAA NCEP GEFS AWS S3 Open Data Registry"

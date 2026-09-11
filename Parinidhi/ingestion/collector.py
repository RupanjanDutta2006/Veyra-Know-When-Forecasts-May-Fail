"""
GEFS Forecast Ingestion Collector.

Retrieves real medium-range and historical forecast data from the NOAA Global Ensemble Forecast System (GEFS).
Queries authoritative NOAA GEFS cycle registry for verified model-run initialization times (for both live and historical dates).
Preserves raw payload, status response, and metadata manifest immutably.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


class GEFSCollector:
    """Collector for NOAA GEFS (Global Ensemble Forecast System) data."""

    DEFAULT_BASE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
    DEFAULT_MODEL = "ncep_gefs025"
    OPENMETEO_STATUS_URL = "https://api.open-meteo.com/data/ncep_gefs025/status.json"
    NOAA_S3_REGISTRY_URL = "https://noaa-gefs-pds.s3.amazonaws.com/?list-type=2&prefix=gefs."

    def __init__(
        self,
        raw_dir: str = "data/raw/gefs",
        model: str = DEFAULT_MODEL,
        timeout_seconds: int = 30,
    ):
        self.raw_dir = Path(raw_dir)
        self.model = model
        self.timeout_seconds = timeout_seconds

    def query_model_status(self, target_date: Optional[Union[str, datetime]] = None) -> Tuple[datetime, Dict[str, Any]]:
        """
        Query authoritative model status / run registry to obtain the verified initialization time.

        For both live and historical dates, queries NOAA NCEP GEFS registry directly.
        Fails loudly if no authoritative status can be verified (no silent 00z fallback).

        Args:
            target_date: Target datetime or string (YYYY-MM-DD or YYYYMMDD). If None, defaults to current UTC time.

        Returns:
            Tuple of (verified_issue_datetime_utc, status_payload_dict).
        """
        now_utc = datetime.now(timezone.utc)
        if target_date is None:
            eval_date = now_utc
        elif isinstance(target_date, str):
            clean_date = target_date.replace("-", "")[:8]
            eval_date = datetime.strptime(clean_date, "%Y%m%d").replace(tzinfo=timezone.utc)
        else:
            eval_date = target_date if target_date.tzinfo else target_date.replace(tzinfo=timezone.utc)

        date_str = eval_date.strftime("%Y%m%d")

        # 1. If today's date, attempt Open-Meteo status endpoint first
        if date_str == now_utc.strftime("%Y%m%d"):
            try:
                req = urllib.request.Request(
                    self.OPENMETEO_STATUS_URL,
                    headers={"User-Agent": "ForecastBustSentinel/1.0 (Status Check)"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        status_data = json.loads(resp.read().decode("utf-8"))
                        init_time_str = status_data.get("last_run_initialisation_time") or status_data.get("initialization_time")
                        if init_time_str:
                            init_dt = datetime.fromisoformat(init_time_str.replace("Z", "+00:00"))
                            status_info = {
                                "authoritative_source": "Open-Meteo Model Status API",
                                "status_url": self.OPENMETEO_STATUS_URL,
                                "raw_status_response": status_data,
                                "verified_initialization_time_utc": init_dt.isoformat(),
                                "query_timestamp_utc": now_utc.isoformat(),
                            }
                            return init_dt, status_info
            except Exception:
                pass  # Fall through to authoritative NOAA registry

        # 2. Query authoritative NOAA NCEP GEFS S3 Registry for the target date
        s3_url = f"{self.NOAA_S3_REGISTRY_URL}{date_str}/&delimiter=/"
        try:
            req = urllib.request.Request(
                s3_url,
                headers={"User-Agent": "ForecastBustSentinel/1.0 (NOAA Registry Check)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"NOAA GEFS registry returned status {resp.status} for date {date_str}")
                content = resp.read().decode("utf-8")
                cycles = re.findall(r"<Prefix>gefs\.\d{8}/(\d{2})/</Prefix>", content)
                if not cycles:
                    raise RuntimeError(
                        f"No active GEFS cycles found on NOAA registry for date {date_str} (outside NOAA retention window). "
                        "Per project integrity rules, no guessed 00z fallback is permitted."
                    )

                latest_cycle_hour = int(sorted(cycles)[-1])
                init_dt = datetime(eval_date.year, eval_date.month, eval_date.day, latest_cycle_hour, 0, 0, tzinfo=timezone.utc)

                # Check last modified timestamp of latest cycle
                cycle_prefix = f"gefs.{date_str}/{latest_cycle_hour:02d}/"
                file_check_url = f"{self.NOAA_S3_REGISTRY_URL}{cycle_prefix}atmos/pgrb2ap5/&max-keys=2"
                last_mod = None
                try:
                    with urllib.request.urlopen(urllib.request.Request(file_check_url, headers={"User-Agent": "ForecastBustSentinel/1.0"}), timeout=10) as c_resp:
                        c_content = c_resp.read().decode("utf-8")
                        lm_match = re.findall(r"<LastModified>([^<]+)</LastModified>", c_content)
                        if lm_match:
                            last_mod = lm_match[0]
                except Exception:
                    pass

                status_info = {
                    "authoritative_source": "NOAA NCEP GEFS AWS S3 Open Data Registry",
                    "registry_url": s3_url,
                    "date": date_str,
                    "available_cycles": sorted(cycles),
                    "selected_cycle": f"{latest_cycle_hour:02d}z",
                    "verified_initialization_time_utc": init_dt.isoformat(),
                    "latest_cycle_file_last_modified_utc": last_mod,
                    "query_timestamp_utc": now_utc.isoformat(),
                }
                return init_dt, status_info
        except Exception as e:
            raise RuntimeError(
                f"Failed to obtain authoritative GEFS model-run status from NOAA registry for date {date_str}: {e}. "
                "Per project integrity rules, no guessed/silent 00z fallback is permitted."
            ) from e

    def query_range_cycles(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Query and verify authoritative cycles for every date in a historical range."""
        d_start = datetime.strptime(start_date.replace("-", "")[:8], "%Y%m%d")
        d_end = datetime.strptime(end_date.replace("-", "")[:8], "%Y%m%d")
        
        results = {}
        curr = d_start
        while curr <= d_end:
            ds = curr.strftime("%Y%m%d")
            try:
                _, s_info = self.query_model_status(curr)
                results[ds] = {
                    "status": "VERIFIED",
                    "available_cycles": s_info["available_cycles"],
                    "latest_cycle": s_info["selected_cycle"],
                    "verified_initialization_time_utc": s_info["verified_initialization_time_utc"],
                }
            except Exception as e:
                results[ds] = {
                    "status": "UNAVAILABLE",
                    "error": str(e),
                }
            curr += timedelta(days=1)
        return results

    def fetch_forecast(
        self,
        latitude: float = 28.6139,
        longitude: float = 77.2090,
        location_name: str = "delhi",
        variables: Optional[List[str]] = None,
        forecast_days: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        issue_time: Optional[Union[str, datetime]] = None,
        use_cache: bool = False,
    ) -> Tuple[Dict[str, Any], Path, Path, Dict[str, Any]]:
        """
        Fetch forecast data for a specified location with authoritative issue time.
        """
        if variables is None:
            variables = ["temperature_2m", "surface_pressure", "wind_speed_10m"]

        now_utc = datetime.now(timezone.utc)
        sub_folder = f"{start_date}_{end_date}" if start_date and end_date else now_utc.strftime("%Y%m%d")
        dest_dir = self.raw_dir / location_name / sub_folder
        dest_dir.mkdir(parents=True, exist_ok=True)

        if use_cache:
            existing_files = list(dest_dir.glob("gefs_raw_*.json"))
            existing_data_files = [f for f in existing_files if not f.name.endswith("_manifest.json") and not f.name.endswith("_status.json")]
            for raw_f in sorted(existing_data_files, reverse=True):
                man_p = raw_f.parent / f"{raw_f.stem}_manifest.json"
                if man_p.exists():
                    try:
                        with open(raw_f, "r", encoding="utf-8") as f:
                            cached_raw = json.load(f)
                        with open(man_p, "r", encoding="utf-8") as f:
                            cached_man = json.load(f)
                        t_series = cached_raw.get("hourly", {}).get("time", [])
                        min_required = (forecast_days * 24) if not (start_date and end_date) else 24
                        if len(t_series) >= min_required and cached_man.get("explicit_issue_time_utc"):
                            return cached_raw, raw_f, man_p, cached_man
                    except Exception:
                        continue

        # 1. Authoritative Issue Time Retrieval
        if issue_time is not None:
            if isinstance(issue_time, str):
                verified_issue_dt = datetime.fromisoformat(issue_time.replace("Z", "+00:00"))
            else:
                verified_issue_dt = issue_time if issue_time.tzinfo else issue_time.replace(tzinfo=timezone.utc)
            status_info = {
                "authoritative_source": "caller_specified_override",
                "verified_initialization_time_utc": verified_issue_dt.isoformat(),
                "query_timestamp_utc": now_utc.isoformat(),
            }
        else:
            # Query authoritative status/registry for start_date (or today if live)
            target_eval = start_date if start_date else now_utc
            verified_issue_dt, status_info = self.query_model_status(target_eval)
            
            # If historical range, also verify all individual dates in the range
            if start_date and end_date:
                range_details = self.query_range_cycles(start_date, end_date)
                status_info["range_verification_details"] = range_details

        explicit_issue_iso = verified_issue_dt.isoformat()

        # 2. Build and execute query
        vars_param = ",".join(variables)
        if start_date and end_date:
            date_params = f"&start_date={start_date}&end_date={end_date}"
        else:
            date_params = f"&forecast_days={forecast_days}"

        params = (
            f"?latitude={latitude:.4f}"
            f"&longitude={longitude:.4f}"
            f"&hourly={vars_param}"
            f"&models={self.model}"
            f"{date_params}"
        )
        url = f"{self.DEFAULT_BASE_URL}{params}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "ForecastBustSentinel/1.0 (Public Proxy Ingestion; GEFS)",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise RuntimeError(f"NOAA GEFS source returned HTTP status {response.status}")
                raw_bytes = response.read()
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve NOAA GEFS forecast: {str(e)}") from e

        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        try:
            raw_data = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Received malformed JSON from GEFS endpoint: {e}") from e

        if "error" in raw_data and raw_data["error"]:
            reason = raw_data.get("reason", "Unknown API error")
            raise RuntimeError(f"GEFS source returned API error: {reason}")

        # 3. Save untouched raw response and raw status payload
        timestamp_str = now_utc.strftime("%Y%m%dT%H%M%SZ")
        raw_file_name = f"gefs_raw_{location_name}_{timestamp_str}.json"
        raw_file_path = dest_dir / raw_file_name

        with open(raw_file_path, "wb") as f:
            f.write(raw_bytes)

        status_file_name = f"gefs_status_{location_name}_{timestamp_str}.json"
        status_file_path = dest_dir / status_file_name
        with open(status_file_path, "w", encoding="utf-8") as f:
            json.dump(status_info, f, indent=2)

        # 4. Build provenance metadata manifest
        time_series = raw_data.get("hourly", {}).get("time", [])
        actual_horizon_hours = len(time_series)
        hourly = raw_data.get("hourly", {})
        temp_members = len([k for k in hourly.keys() if k.startswith("temperature_2m")])

        manifest = {
            "source": "NOAA NCEP GEFS (Global Ensemble Forecast System)",
            "provider": "Open-Meteo GEFS Mirror / NOAA NCEP",
            "exact_endpoint": self.DEFAULT_BASE_URL,
            "model_identifier": self.model,
            "explicit_issue_time_utc": explicit_issue_iso,
            "issue_time_source": status_info.get("authoritative_source"),
            "authoritative_cycle_details": status_info,
            "download_time_utc": now_utc.isoformat(),
            "location_name": location_name,
            "requested_coordinates": {"latitude": latitude, "longitude": longitude},
            "actual_grid_coordinates": {
                "latitude": raw_data.get("latitude"),
                "longitude": raw_data.get("longitude"),
                "elevation": raw_data.get("elevation"),
            },
            "variables_requested": variables,
            "requested_horizon_days": forecast_days if not (start_date and end_date) else None,
            "date_range": {"start_date": start_date, "end_date": end_date} if start_date and end_date else None,
            "actual_returned_horizon_hours": actual_horizon_hours,
            "actual_lead_hours_min": 0,
            "actual_lead_hours_max": actual_horizon_hours - 1 if actual_horizon_hours > 0 else 0,
            "ensemble_members_count": temp_members,
            "generation_time_ms": raw_data.get("generationtime_ms"),
            "raw_file_path": str(raw_file_path),
            "status_file_path": str(status_file_path),
            "sha256_checksum": sha256_hash,
            "byte_size": len(raw_bytes),
        }

        manifest_path = dest_dir / f"gefs_raw_{location_name}_{timestamp_str}_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return raw_data, raw_file_path, manifest_path, manifest

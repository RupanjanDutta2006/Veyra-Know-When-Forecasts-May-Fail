"""Direct NOAA AWS S3 Reforecast Data Source Adapter.

Retrieves real GEFSv12 reforecast fields via direct S3 index parsing and concurrent HTTP byte-range slicing.
Decodes raw GRIB2 messages in-memory via ecCodes without relying on fragile third-party wrappers,
local disk-cache hacks, or synthetic/interpolated fallbacks.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union
import numpy as np
import pandas as pd
import requests

# Ensure ecCodes C-library DLL is resolvable on Windows environments
_ENV_DIR = Path(__file__).resolve().parent.parent.parent / "scratch" / "env_eccodes"
_BIN_DIR = _ENV_DIR / "Library" / "bin"
if _BIN_DIR.exists():
    try:
        os.add_dll_directory(str(_BIN_DIR))
    except Exception:
        pass
    if str(_BIN_DIR) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

try:
    import eccodes
    _ECCODES_AVAILABLE = True
except Exception:
    _ECCODES_AVAILABLE = False

from ingestion.adapters.base import BaseForecastSourceAdapter

NOAA_REFORECAST_S3_ROOT = "https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast"
MODEL_VERSION = "GEFSv12-reforecast"
SOURCE_NAME = "NOAA_GEFSV12_REFORECAST_AWS"

# Mutex lock for thread-safe ecCodes C-library bindings
_DECODE_LOCK = threading.Lock()

# Thread-local storage for HTTP connection pooling
_THREAD_LOCAL = threading.local()


def _get_session() -> requests.Session:
    if not hasattr(_THREAD_LOCAL, "session"):
        s = requests.Session()
        from urllib3.util import Retry
        retry = Retry(
            total=4,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = requests.adapters.HTTPAdapter(pool_connections=30, pool_maxsize=30, max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({"User-Agent": "ForecastBustSentinel/2.0 (NOAA-S3-Direct)"})
        _THREAD_LOCAL.session = s
    return _THREAD_LOCAL.session


def _utc_date(value: Union[str, datetime, pd.Timestamp]) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _member_code(member: int) -> str:
    return "c00" if member == 0 else f"p{member:02d}"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if lat2 is None or lon2 is None:
        return 0.0
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dlon_deg = abs(lon2 - lon1)
    if dlon_deg > 180.0:
        dlon_deg = 360.0 - dlon_deg
    dl = math.radians(dlon_deg)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


VARIABLE_SPECS: Dict[str, Dict[str, Any]] = {
    "temperature_2m": {
        "file_prefix": "tmp_2m",
        "var_key": "TMP",
        "level_key": "2 m above ground",
        "unit": "degC",
        "transform": lambda k: float(k - 273.15),
    },
    "surface_pressure": {
        "file_prefix": "pres_msl",
        "var_key": "PRES",
        "level_key": "mean sea level",
        "unit": "hPa",
        "transform": lambda pa: float(pa / 100.0),
    },
    "u_wind_10m": {
        "file_prefix": "ugrd_hgt",
        "var_key": "UGRD",
        "level_key": "10 m above ground",
        "unit": "m/s",
        "transform": lambda v: float(v),
    },
    "v_wind_10m": {
        "file_prefix": "vgrd_hgt",
        "var_key": "VGRD",
        "level_key": "10 m above ground",
        "unit": "m/s",
        "transform": lambda v: float(v),
    },
    "cape_surface": {
        "file_prefix": "cape_sfc",
        "var_key": "CAPE",
        "level_key": "surface",
        "unit": "J/kg",
        "transform": lambda v: float(v),
    },
}


class NOAAS3ReforecastAdapter(BaseForecastSourceAdapter):
    """Direct NOAA S3 Range-Slicing Adapter for GEFSv12 Reforecasts."""

    def __init__(
        self,
        raw_dir: str = "data/raw/gefs_reforecast",
        timeout_seconds: int = 30,
        s3_root: str = NOAA_REFORECAST_S3_ROOT,
        max_workers: int = 12,
        use_cache: bool = True,
    ):
        self.raw_dir = Path(raw_dir)
        self.timeout_seconds = timeout_seconds
        self.s3_root = s3_root.rstrip("/")
        self.max_workers = max_workers
        self.use_cache = use_cache
        self.idx_cache_dir = self.raw_dir / "idx"
        self.slice_cache_dir = self.raw_dir / "slices"
        if not _ECCODES_AVAILABLE:
            raise RuntimeError(
                "ecCodes library is required for NOAA S3 decoding. Ensure python-eccodes is installed."
            )

    @property
    def source_name(self) -> str:
        return SOURCE_NAME

    @property
    def model_name(self) -> str:
        return MODEL_VERSION

    def _build_url(self, issue: pd.Timestamp, member: int, prefix: str, is_idx: bool = False) -> str:
        code = _member_code(member)
        stamp = issue.strftime("%Y%m%d%H")
        year = issue.strftime("%Y")
        ext = ".grib2.idx" if is_idx else ".grib2"
        return f"{self.s3_root}/{year}/{stamp}/{code}/Days:1-10/{prefix}_{stamp}_{code}{ext}"

    def _check_member_exists(self, issue: pd.Timestamp, member: int) -> Optional[int]:
        code = _member_code(member)
        stamp = issue.strftime("%Y%m%d%H")
        if self.use_cache:
            cache_file = self.idx_cache_dir / f"tmp_2m_{stamp}_{code}.idx"
            if cache_file.exists() and cache_file.stat().st_size > 0:
                return member

        idx_url = self._build_url(issue, member, "tmp_2m", is_idx=True)
        session = _get_session()
        try:
            resp = session.head(idx_url, timeout=10)
            return member if resp.status_code == 200 else None
        except Exception:
            return None

    def discover_members(self, issue_time: Union[str, datetime, pd.Timestamp], max_member: int = 10) -> List[int]:
        """Probe the actual member index files present on S3 for this run."""
        issue = _utc_date(issue_time)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_member + 1) as pool:
            futures = [pool.submit(self._check_member_exists, issue, m) for m in range(max_member + 1)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        members = sorted([m for m in results if m is not None])
        if not members:
            raise FileNotFoundError(f"No NOAA GEFSv12 reforecast members found on S3 for run {issue.isoformat()}")
        return members

    def _fetch_idx(self, issue: pd.Timestamp, member: int, prefix: str) -> Tuple[int, str, str]:
        code = _member_code(member)
        stamp = issue.strftime("%Y%m%d%H")
        cache_file = self.idx_cache_dir / f"{prefix}_{stamp}_{code}.idx"

        if self.use_cache and cache_file.exists() and cache_file.stat().st_size > 0:
            idx_text = cache_file.read_text(encoding="utf-8")
            return member, prefix, idx_text

        idx_url = self._build_url(issue, member, prefix, is_idx=True)
        session = _get_session()
        resp = session.get(idx_url, timeout=self.timeout_seconds)
        if resp.status_code != 200:
            raise FileNotFoundError(f"Failed to fetch NOAA S3 index from {idx_url} (HTTP {resp.status_code})")
        idx_text = resp.text

        if self.use_cache:
            self.idx_cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(idx_text, encoding="utf-8")

        return member, prefix, idx_text

    def _parse_idx_byte_ranges(self, idx_text: str, var_key: str, level_key: str) -> Dict[int, Tuple[int, Optional[int]]]:
        lines = idx_text.splitlines()
        lead_ranges: Dict[int, Tuple[int, Optional[int]]] = {}
        for i, line in enumerate(lines):
            parts = line.split(":")
            if len(parts) >= 6:
                v = parts[3]
                lvl = parts[4]
                fcst = parts[5]
                if v == var_key and level_key in lvl:
                    fcst_tokens = fcst.strip().split()
                    if fcst_tokens and fcst_tokens[0].isdigit():
                        lead_h = int(fcst_tokens[0])
                        start_b = int(parts[1])
                        end_b = int(lines[i + 1].split(":")[1]) - 1 if i + 1 < len(lines) else None
                        lead_ranges[lead_h] = (start_b, end_b)
        return lead_ranges

    def _fetch_grib_task(
        self, issue: pd.Timestamp, member: int, prefix: str, lead: int, byte_start: int, byte_end: Optional[int]
    ) -> Tuple[int, str, int, bytes, str]:
        code = _member_code(member)
        stamp = issue.strftime("%Y%m%d%H")
        end_tag = str(byte_end) if byte_end is not None else "end"
        slice_filename = f"{prefix}_{stamp}_{code}_f{lead:03d}_{byte_start}_{end_tag}.grib2"
        slice_cache_file = self.slice_cache_dir / slice_filename
        grib_url = self._build_url(issue, member, prefix, is_idx=False)

        if self.use_cache and slice_cache_file.exists() and slice_cache_file.stat().st_size > 0:
            content = slice_cache_file.read_bytes()
            return member, prefix, lead, content, grib_url

        range_header = f"bytes={byte_start}-{byte_end}" if byte_end is not None else f"bytes={byte_start}-"
        session = _get_session()
        resp = session.get(grib_url, headers={"Range": range_header}, timeout=self.timeout_seconds)
        if resp.status_code not in (200, 206):
            raise RuntimeError(
                f"Failed to fetch S3 GRIB range {range_header} from {grib_url} (HTTP {resp.status_code})"
            )
        content = resp.content

        if self.use_cache:
            self.slice_cache_dir.mkdir(parents=True, exist_ok=True)
            slice_cache_file.write_bytes(content)

        return member, prefix, lead, content, grib_url

    def _decode_global_field(self, grib_bytes: bytes) -> Tuple[np.ndarray, Dict[str, Any]]:
        with _DECODE_LOCK:
            gid = eccodes.codes_new_from_message(grib_bytes)
            try:
                ni = int(eccodes.codes_get(gid, "Ni"))
                nj = int(eccodes.codes_get(gid, "Nj"))
                lat_first = float(eccodes.codes_get(gid, "latitudeOfFirstGridPointInDegrees"))
                lon_first = float(eccodes.codes_get(gid, "longitudeOfFirstGridPointInDegrees"))
                dlat = float(eccodes.codes_get(gid, "jDirectionIncrementInDegrees"))
                dlon = float(eccodes.codes_get(gid, "iDirectionIncrementInDegrees"))
                values = eccodes.codes_get_values(gid)
                grid_meta = {
                    "Ni": ni,
                    "Nj": nj,
                    "lat_first": lat_first,
                    "lon_first": lon_first,
                    "dlat": dlat,
                    "dlon": dlon,
                }
                return np.asarray(values, dtype=float), grid_meta
            finally:
                eccodes.codes_release(gid)

    def fetch_run(
        self,
        issue_time: Union[str, datetime, pd.Timestamp],
        locations: Sequence[Dict[str, Any]],
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
        horizon_hours: int = 72,
        step_hours: int = 3,
        members: Optional[Sequence[int]] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Fetch one model run initialization across multiple locations simultaneously."""
        issue = _utc_date(issue_time)
        if issue.hour != 0:
            raise ValueError("NOAA GEFSv12 reforecast public runs are 00Z only; issue_time must be 00Z.")
        if horizon_hours < 3 or horizon_hours > 237:
            raise ValueError("horizon_hours must be between 3 and 237 hours for GEFSv12 reforecast fields.")
        if step_hours <= 0 or step_hours % 3 != 0:
            raise ValueError("step_hours must be a positive multiple of 3 hours.")

        actual_members = list(members) if members is not None else self.discover_members(issue)
        wanted_leads = [int(h) for h in np.arange(3, horizon_hours + 0.1, step_hours)]

        norm_locs = []
        for loc in locations:
            loc_id = loc.get("location_id") or loc.get("location") or loc.get("name") or "unnamed"
            req_c = loc.get("requested_coordinates", {})
            lat_val = loc.get("latitude") if loc.get("latitude") is not None else (req_c.get("latitude") if isinstance(req_c, dict) else getattr(req_c, "latitude", None))
            lon_val = loc.get("longitude") if loc.get("longitude") is not None else (req_c.get("longitude") if isinstance(req_c, dict) else getattr(req_c, "longitude", None))
            if lat_val is None or lon_val is None:
                raise ValueError(f"Could not resolve latitude/longitude for location entry: {loc}")
            norm_locs.append({"location": str(loc_id), "latitude": float(lat_val), "longitude": float(lon_val)})

        needed_prefixes = set()
        for var in variables:
            if var == "wind_speed_10m":
                needed_prefixes.add("u_wind_10m")
                needed_prefixes.add("v_wind_10m")
            elif var in VARIABLE_SPECS:
                needed_prefixes.add(var)
            else:
                raise ValueError(f"Unsupported variable: '{var}'. Supported: {list(VARIABLE_SPECS.keys()) + ['wind_speed_10m']}")

        # Step 1: Concurrently fetch indices for all (member, prefix) combinations
        indices: Dict[int, Dict[str, Dict[int, Tuple[int, Optional[int]]]]] = {m: {} for m in actual_members}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            idx_futures = [
                pool.submit(self._fetch_idx, issue, m, VARIABLE_SPECS[p]["file_prefix"])
                for m in actual_members
                for p in needed_prefixes
            ]
            for f in concurrent.futures.as_completed(idx_futures):
                m, file_pfx, idx_txt = f.result()
                for p in needed_prefixes:
                    spec = VARIABLE_SPECS[p]
                    if spec["file_prefix"] == file_pfx:
                        ranges = self._parse_idx_byte_ranges(idx_txt, spec["var_key"], spec["level_key"])
                        indices[m][p] = ranges

        # Step 2: Concurrently fetch all required GRIB2 message byte slices
        grib_tasks = []
        for m in actual_members:
            for p in needed_prefixes:
                spec = VARIABLE_SPECS[p]
                for lead in wanted_leads:
                    if lead not in indices[m][p]:
                        raise ValueError(f"Lead hour {lead}h not found in S3 index for {p} (member {_member_code(m)})")
                    s_b, e_b = indices[m][p][lead]
                    grib_tasks.append((issue, m, spec["file_prefix"], p, lead, s_b, e_b))

        raw_fields: Dict[int, Dict[str, Dict[int, np.ndarray]]] = {
            m: {p: {} for p in needed_prefixes} for m in actual_members
        }
        source_urls_seen = set()
        grid_meta = None

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [
                pool.submit(self._fetch_grib_task, iss, mem, pfx, ld, sb, eb)
                for (iss, mem, pfx, _, ld, sb, eb) in grib_tasks
            ]
            fut_to_key = {
                futures[i]: grib_tasks[i][3] for i in range(len(futures))
            }
            for fut in concurrent.futures.as_completed(futures):
                mem, _, ld, grib_bytes, grib_url = fut.result()
                p_key = fut_to_key[fut]
                source_urls_seen.add(grib_url)
                vals_arr, g_meta = self._decode_global_field(grib_bytes)
                raw_fields[mem][p_key][ld] = vals_arr
                if grid_meta is None:
                    grid_meta = g_meta

        # Step 3: Spatial grid alignment and point extraction
        ni = grid_meta["Ni"]
        lat_first = grid_meta["lat_first"]
        lon_first = grid_meta["lon_first"]
        dlat = grid_meta["dlat"]
        dlon = grid_meta["dlon"]

        loc_grid_coords: Dict[str, Tuple[float, float, float, int]] = {}
        for loc in norm_locs:
            loc_id = loc["location"]
            req_lat = loc["latitude"]
            req_lon = loc["longitude"]

            j = round((lat_first - req_lat) / dlat)
            lon_360 = req_lon % 360.0
            i_idx = round((lon_360 - lon_first) / dlon) % ni
            flat_idx = j * ni + i_idx

            grid_lat = round(lat_first - j * dlat, 4)
            grid_lon = round((lon_first + i_idx * dlon) % 360.0, 4)
            dist_km = round(_haversine_km(req_lat, req_lon, grid_lat, grid_lon), 2)
            loc_grid_coords[loc_id] = (grid_lat, grid_lon, dist_km, flat_idx)

        # Structure: point_data[location][variable][lead_hours][member_code] = val
        point_data: Dict[str, Dict[str, Dict[int, Dict[str, float]]]] = {
            loc["location"]: {v: {lead: {} for lead in wanted_leads} for v in variables}
            for loc in norm_locs
        }

        for loc in norm_locs:
            loc_id = loc["location"]
            _, _, _, flat_idx = loc_grid_coords[loc_id]

            for lead in wanted_leads:
                for m in actual_members:
                    m_code = _member_code(m)
                    for var in variables:
                        if var == "wind_speed_10m":
                            u_val = float(raw_fields[m]["u_wind_10m"][lead][flat_idx])
                            v_val = float(raw_fields[m]["v_wind_10m"][lead][flat_idx])
                            w_spd_kmh = math.sqrt(u_val * u_val + v_val * v_val) * 3.6
                            point_data[loc_id][var][lead][m_code] = round(w_spd_kmh, 4)
                        else:
                            spec = VARIABLE_SPECS[var]
                            raw_v = float(raw_fields[m][var][lead][flat_idx])
                            trans_v = spec["transform"](raw_v)
                            point_data[loc_id][var][lead][m_code] = round(trans_v, 4)

        # Step 4: Build standard DataFrame
        rows: List[Dict[str, Any]] = []
        for loc in norm_locs:
            loc_id = loc["location"]
            req_lat = loc["latitude"]
            req_lon = loc["longitude"]
            grid_lat, grid_lon, dist_km, _ = loc_grid_coords[loc_id]

            for var in variables:
                unit = "km/h" if var == "wind_speed_10m" else VARIABLE_SPECS[var]["unit"]
                for lead in wanted_leads:
                    valid_time = issue + pd.Timedelta(hours=lead)
                    m_map = point_data[loc_id][var][lead]
                    vals = np.array(list(m_map.values()), dtype=float)
                    primary_val = float(m_map[_member_code(actual_members[0])])

                    rows.append({
                        "location": loc_id,
                        "latitude": float(req_lat),
                        "longitude": float(req_lon),
                        "grid_latitude": float(grid_lat),
                        "grid_longitude": float(grid_lon),
                        "issue_time": issue,
                        "valid_time": valid_time,
                        "lead_hours": int(lead),
                        "variable": var,
                        "value": round(primary_val, 4),
                        "unit": unit,
                        "source": SOURCE_NAME,
                        "model": MODEL_VERSION,
                        "model_run": issue.isoformat(),
                        "member_id": "ensemble_summary",
                        "ensemble_mean": round(float(vals.mean()), 4),
                        "ensemble_std": round(float(vals.std(ddof=1)) if len(vals) > 1 else 0.0, 4),
                        "ensemble_min": round(float(vals.min()), 4),
                        "ensemble_max": round(float(vals.max()), 4),
                        "q10": round(float(np.percentile(vals, 10)), 4),
                        "q90": round(float(np.percentile(vals, 90)), 4),
                        "member_count": int(len(vals)),
                        "expected_member_count": int(len(actual_members)),
                        "member_ids": ",".join(_member_code(m) for m in actual_members),
                        "member_values_json": json.dumps(m_map, sort_keys=True),
                        "spatial_distance_km": dist_km,
                    })

        df = pd.DataFrame(rows)
        manifest = {
            "source": SOURCE_NAME,
            "model": MODEL_VERSION,
            "issue_time_utc": issue.isoformat(),
            "location_count": len(norm_locs),
            "locations": [loc["location"] for loc in norm_locs],
            "member_codes": [_member_code(m) for m in actual_members],
            "member_count": len(actual_members),
            "horizon_hours": horizon_hours,
            "step_hours": step_hours,
            "variables": list(variables),
            "archive_url_root": self.s3_root,
            "source_urls": sorted(source_urls_seen),
            "total_records": len(df),
            "member_values_sha256": hashlib.sha256(json.dumps(point_data, sort_keys=True).encode()).hexdigest(),
        }
        return df, manifest

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
    ) -> Tuple[pd.DataFrame, Dict[str, Any], Path, Path]:
        """Fetch real forecast data over a historical date range across multiple locations."""
        if str(cycle).zfill(2) != "00":
            raise ValueError("NOAA GEFSv12 reforecast public archive is 00Z once daily; cycle must be 00.")
        start = _utc_date(start_date).normalize()
        end = _utc_date(end_date).normalize()

        slices: List[pd.DataFrame] = []
        manifests: List[Dict[str, Any]] = []

        for day in pd.date_range(start, end, freq="D", tz="UTC"):
            df_day, man_day = self.fetch_run(
                issue_time=day,
                locations=locations,
                variables=variables,
                horizon_hours=horizon_hours,
                step_hours=step_hours,
            )
            slices.append(df_day)
            manifests.append(man_day)

        out_df = pd.concat(slices, ignore_index=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        loc_tag = f"{len(locations)}_locations" if len(locations) > 1 else str(locations[0].get("location_id") or locations[0].get("location"))
        stamp = f"{start:%Y%m%d}_{end:%Y%m%d}_{loc_tag}"
        raw_path = self.raw_dir / f"{stamp}_member_summary.json"
        manifest_path = self.raw_dir / f"{stamp}_manifest.json"

        raw_path.write_text(json.dumps(manifests, indent=2, default=str), encoding="utf-8")
        range_manifest = {
            "source": SOURCE_NAME,
            "model": MODEL_VERSION,
            "start_date": str(start.date()),
            "end_date": str(end.date()),
            "total_distinct_cycles": len(manifests),
            "location_count": len(locations),
            "member_counts": [m["member_count"] for m in manifests],
            "runs": manifests,
        }
        manifest_path.write_text(json.dumps(range_manifest, indent=2, default=str), encoding="utf-8")
        return out_df, range_manifest, raw_path, manifest_path

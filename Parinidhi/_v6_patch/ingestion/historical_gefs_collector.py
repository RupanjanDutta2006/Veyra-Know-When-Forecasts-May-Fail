"""NOAA GEFSv12 reforecast collector.

This collector intentionally uses the NOAA GEFSv12 reforecast archive rather than
an operational API.  Every record keeps the exact initialization time, member,
source URL, model version, and actual NWP grid point.  No issue time is inferred
from the first valid time.

The public Phase-2 reforecast archive is 00Z once per day, with c00+p01..p04 on
normal days and c00+p01..p10 on the extended weekly runs.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

NOAA_ROOT = "https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast"
MODEL_VERSION = "GEFSv12-reforecast"
SOURCE = "NOAA_GEFSV12_REFORECAST_AWS"
VARIABLES = {
    "temperature_2m": {"file": "tmp_2m", "search": ":TMP:2 m above ground:", "unit": "degC"},
    "surface_pressure": {"file": "pres_msl", "search": ":PRMSL:mean sea level:", "unit": "hPa"},
    "u_wind_10m": {"file": "ugrd_10m", "search": ":UGRD:10 m above ground:", "unit": "m/s"},
    "v_wind_10m": {"file": "vgrd_10m", "search": ":VGRD:10 m above ground:", "unit": "m/s"},
}


def _utc_date(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _member_code(member: int) -> str:
    return "c00" if member == 0 else f"p{member:02d}"


def _url(issue: pd.Timestamp, member: int, prefix: str) -> str:
    code = _member_code(member)
    stamp = issue.strftime("%Y%m%d%H")
    year = issue.strftime("%Y")
    return f"{NOAA_ROOT}/{year}/{stamp}/{code}/Days:1-10/{prefix}_{stamp}_{code}.grib2"


def _exists(url: str) -> bool:
    try:
        req = Request(url, method="HEAD")
        with urlopen(req, timeout=30) as response:
            return 200 <= response.status < 400
    except (HTTPError, URLError, TimeoutError):
        return False


def discover_members(issue_time: pd.Timestamp, max_member: int = 10) -> List[int]:
    """Discover the actual member directories present for a run.

    We probe the c00 temperature file and p01..p10 temperature files.  This avoids
    hard-coding the weekly 11-member schedule and makes member_count auditable.
    """
    members = []
    for member in range(max_member + 1):
        if _exists(_url(issue_time, member, "tmp_2m")):
            members.append(member)
    if not members:
        raise FileNotFoundError(f"No NOAA GEFSv12 reforecast members found for {issue_time.isoformat()}")
    return members


def _point(ds, latitude: float, longitude: float):
    lon = longitude % 360.0
    return ds.sel(latitude=latitude, longitude=lon, method="nearest")


def _open_grib_point(path: str, search: str, latitude: float, longitude: float):
    """Open a locally cached GRIB2 file with cfgrib and select the nearest grid point."""
    import xarray as xr
    ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    return _point(ds, latitude, longitude)


def _download(url: str, destination: Path) -> Path:
    """Download an exact NOAA GRIB2 object once and cache it byte-for-byte."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    tmp = destination.with_suffix(destination.suffix + ".part")
    req = Request(url, headers={"User-Agent": "forecast-bust-sentinel/1.0"})
    with urlopen(req, timeout=120) as response, tmp.open("wb") as fh:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(destination)
    return destination


def _open_member_field(issue: pd.Timestamp, member: int, cfg: Dict, raw_dir: Path,
                       latitude: float, longitude: float, fxx: int):
    """Use Herbie for supported normal members; fall back to exact NOAA URL for extended members."""
    if member <= 4:
        from herbie import Herbie
        H = Herbie(issue.tz_localize(None).to_pydatetime(), model="gefs_reforecast", fxx=max(1, int(fxx)),
                   member=member, variable_level=cfg["file"], priority=["aws"], verbose=False)
        return _point(H.xarray(cfg["search"], backend_kwargs={"indexpath": ""}), latitude, longitude), H.grib
    url = _url(issue, member, cfg["file"])
    local = raw_dir / "grib" / issue.strftime("%Y%m%d%H") / _member_code(member) / f"{cfg['file']}_{issue:%Y%m%d%H}_{_member_code(member)}.grib2"
    path = _download(url, local)
    return _open_grib_point(str(path), cfg["search"], latitude, longitude), url


def _lead_hours(values: Iterable) -> np.ndarray:
    vals = pd.to_timedelta(values).total_seconds() / 3600.0
    return np.asarray(vals, dtype=float)


class HistoricalGEFSCollector:
    """Fetch real GEFSv12 reforecast values at requested point locations."""

    def __init__(self, raw_dir: str = "data/raw/gefs_reforecast"):
        self.raw_dir = Path(raw_dir)

    def collect_run(
        self,
        issue_time: str | datetime,
        latitude: float,
        longitude: float,
        location_name: str,
        horizon_hours: int = 72,
        step_hours: int = 3,
        members: Optional[Sequence[int]] = None,
        variables: Sequence[str] = ("temperature_2m", "surface_pressure", "wind_speed_10m"),
    ) -> Tuple[pd.DataFrame, Dict]:
        """Collect one exact 00Z run and return ensemble-summary rows.

        The underlying member-level values are preserved in a sidecar JSON manifest
        keyed by variable/valid_time/member.  The returned table remains compatible
        with the existing Builder-2 pipeline.
        """
        issue = _utc_date(issue_time)
        if issue.hour != 0:
            raise ValueError("GEFSv12 reforecast public Phase-2 runs are 00Z only; issue_time must be 00Z.")
        try:
            from herbie import Herbie
        except Exception as exc:
            raise RuntimeError("Herbie/ecCodes is required. Use the project's scratch/env_eccodes environment.") from exc
        if horizon_hours < 3 or horizon_hours > 237:
            raise ValueError("horizon_hours must be between 3 and 237 hours; the public reforecast GRIB contains 3-hour forecast leads through +237h (no +0h forecast field).")
        if step_hours <= 0:
            raise ValueError("step_hours must be positive.")

        unknown_vars = [v for v in variables if v not in VARIABLES and v != "wind_speed_10m"]
        if unknown_vars:
            raise ValueError(f"Unsupported historical GEFS variables: {unknown_vars}")

        actual_members = list(members) if members is not None else discover_members(issue)
        unknown = [m for m in actual_members if m not in range(11)]
        if unknown:
            raise ValueError(f"Unsupported GEFSv12 reforecast member IDs: {unknown}")

        if step_hours % 3 != 0:
            raise ValueError("step_hours must be a multiple of 3 hours for the GEFSv12 reforecast fields.")
        wanted_leads = np.arange(3, horizon_hours + 0.1, step_hours, dtype=float)
        member_values: Dict[str, Dict[str, Dict[str, float]]] = {}
        rows: List[Dict] = []
        grid_lat = grid_lon = None
        source_urls_seen = set()

        # Load each member's field once per variable; Herbie uses the remote IDX to
        # retrieve the GRIB message instead of requiring a full global file download.
        per_member: Dict[int, Dict[str, pd.DataFrame]] = {}
        for member in actual_members:
            per_member[member] = {}
            for var in variables:
                if var == "wind_speed_10m":
                    prefixes = ("u_wind_10m", "v_wind_10m")
                else:
                    prefixes = (var,)
                datasets = {}
                for prefix in prefixes:
                    cfg = VARIABLES[prefix]
                    ds, source_url = _open_member_field(
                        issue, member, cfg, self.raw_dir, latitude, longitude, horizon_hours
                    )
                    datasets[prefix] = ds
                    source_urls_seen.add(source_url)
                    if grid_lat is None:
                        grid_lat = float(datasets[prefix].latitude.values)
                        grid_lon = float(datasets[prefix].longitude.values)
                per_member[member][var] = datasets

        for var in variables:
            for lead in wanted_leads:
                valid = issue + pd.Timedelta(hours=float(lead))
                member_map: Dict[str, float] = {}
                for member in actual_members:
                    dsmap = per_member[member][var]
                    if var == "wind_speed_10m":
                        u = dsmap["u_wind_10m"]
                        v = dsmap["v_wind_10m"]
                        valid_times = pd.to_datetime(u.valid_time.values, utc=True)
                        idx = int(np.argmin(np.abs((valid_times - valid).total_seconds())))
                        uval = float(np.asarray(u["u10"].values).reshape(-1)[idx])
                        vval = float(np.asarray(v["v10"].values).reshape(-1)[idx])
                        value = math.sqrt(uval * uval + vval * vval) * 3.6
                    else:
                        ds = dsmap[var]
                        valid_times = pd.to_datetime(ds.valid_time.values, utc=True)
                        idx = int(np.argmin(np.abs((valid_times - valid).total_seconds())))
                        data_var = list(ds.data_vars)[0]
                        value = float(np.asarray(ds[data_var].values).reshape(-1)[idx])
                        if var == "temperature_2m":
                            value -= 273.15
                        elif var == "surface_pressure":
                            value /= 100.0
                    if abs((valid_times[idx] - valid).total_seconds()) > 60:
                        raise ValueError(f"No exact 3-hour GEFS lead for {valid}; nearest is {valid_times[idx]}")
                    member_map[_member_code(member)] = value

                vals = np.asarray(list(member_map.values()), dtype=float)
                member_values.setdefault(var, {})[valid.isoformat()] = member_map
                rows.append({
                    "location": location_name,
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "grid_latitude": grid_lat,
                    "grid_longitude": grid_lon,
                    "issue_time": issue,
                    "valid_time": valid,
                    "lead_hours": int(lead),
                    "variable": var,
                    "value": float(member_map[_member_code(actual_members[0])]),
                    "unit": "km/h" if var == "wind_speed_10m" else VARIABLES[var]["unit"],
                    "source": SOURCE,
                    "model": MODEL_VERSION,
                    "model_run": issue.isoformat(),
                    "member_id": "ensemble_summary",
                    "ensemble_mean": float(vals.mean()),
                    "ensemble_std": float(vals.std(ddof=1)) if len(vals) > 1 else 0.0,
                    "ensemble_min": float(vals.min()),
                    "ensemble_max": float(vals.max()),
                    "q10": float(np.percentile(vals, 10)),
                    "q90": float(np.percentile(vals, 90)),
                    "member_count": int(len(vals)),
                    "expected_member_count": int(len(actual_members)),
                    "member_ids": ",".join(_member_code(m) for m in actual_members),
                    "member_values_json": json.dumps(member_map, sort_keys=True),
                    "spatial_distance_km": self._haversine(latitude, longitude, grid_lat, grid_lon),
                })

        df = pd.DataFrame(rows)
        manifest = {
            "source": SOURCE,
            "model": MODEL_VERSION,
            "issue_time_utc": issue.isoformat(),
            "location": location_name,
            "requested_latitude": latitude,
            "requested_longitude": longitude,
            "grid_latitude": grid_lat,
            "grid_longitude": grid_lon,
            "spatial_distance_km": self._haversine(latitude, longitude, grid_lat, grid_lon),
            "member_codes": [_member_code(m) for m in actual_members],
            "member_count": len(actual_members),
            "horizon_hours": horizon_hours,
            "step_hours": step_hours,
            "variables": list(variables),
            "archive_url_pattern": NOAA_ROOT,
            "source_urls": sorted(source_urls_seen),
            "member_values_sha256": hashlib.sha256(json.dumps(member_values, sort_keys=True).encode()).hexdigest(),
            "member_values": member_values,
        }
        return df, manifest

    def collect_range(self, start_date: str, end_date: str, cycle: str, horizon_hours: int,
                      step_hours: int, latitude: float, longitude: float, location_name: str,
                      use_cache: bool = True):
        if str(cycle).zfill(2) != "00":
            raise ValueError("GEFSv12 reforecast Phase-2 public archive is 00Z once daily; use --cycle 00.")
        start = _utc_date(start_date).normalize()
        end = _utc_date(end_date).normalize()
        slices = []
        manifests = []
        for day in pd.date_range(start, end, freq="D", tz="UTC"):
            df, manifest = self.collect_run(day, latitude, longitude, location_name, horizon_hours, step_hours)
            slices.append(df)
            manifests.append(manifest)
        out = pd.concat(slices, ignore_index=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        stamp = f"{start:%Y%m%d}_{end:%Y%m%d}_{location_name}"
        raw_path = self.raw_dir / f"{stamp}_member_summary.json"
        manifest_path = self.raw_dir / f"{stamp}_manifest.json"
        raw_path.write_text(json.dumps(manifests, indent=2, default=str), encoding="utf-8")
        manifest = {
            "source": SOURCE, "model": MODEL_VERSION, "start_date": str(start.date()), "end_date": str(end.date()),
            "total_distinct_cycles": len(manifests), "member_counts": [m["member_count"] for m in manifests],
            "spatial_distance_km": manifests[0]["spatial_distance_km"] if manifests else None,
            "runs": manifests,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        return out, manifest, raw_path, manifest_path

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        if lat2 is None or lon2 is None:
            return None
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

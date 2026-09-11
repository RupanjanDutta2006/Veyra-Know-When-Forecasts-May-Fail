"""ERA5 reanalysis reference collector via Open-Meteo's historical archive."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import pandas as pd

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
SOURCE = "ERA5_REANALYSIS_OPEN_METEO_ARCHIVE"

class ERA5ReferenceCollector:
    def __init__(self, raw_dir: str = "data/raw/era5"):
        self.raw_dir = Path(raw_dir)

    def fetch_historical_reference(self, start_date: str, end_date: str, latitude: float,
                                   longitude: float, location_name: str, use_cache: bool = True):
        params = {
            "latitude": latitude, "longitude": longitude,
            "start_date": start_date, "end_date": end_date,
            "hourly": "temperature_2m,surface_pressure,wind_speed_10m",
            "timezone": "UTC", "temperature_unit": "celsius", "wind_speed_unit": "kmh",
        }
        url = f"{ARCHIVE_URL}?{urlencode(params)}"
        cache_dir = self.raw_dir / location_name
        cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = f"{start_date}_{end_date}"
        raw_path = cache_dir / f"era5_{stamp}.json"
        if use_cache and raw_path.exists():
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            with urlopen(url, timeout=60) as response:
                raw = json.loads(response.read().decode("utf-8"))
            raw_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        manifest = {
            "source": SOURCE, "requested_latitude": latitude, "requested_longitude": longitude,
            "provider_grid_latitude": raw.get("latitude"), "provider_grid_longitude": raw.get("longitude"),
            "start_date": start_date, "end_date": end_date, "request_sha256": hashlib.sha256(url.encode()).hexdigest(),
            "url": url,
        }
        manifest_path = cache_dir / f"era5_{stamp}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return raw, raw_path, manifest_path, manifest

"""Canonical Location Registry Service for Builder 1.

Loads authoritative canonical locations and aliases directly from
configs/canonical_locations.json with zero duplicated hardcoded dicts.
"""

import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def normalize_alias(name: str) -> str:
    """Normalize location string by trimming, lowercasing, and collapsing whitespace."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


def find_canonical_registry_path() -> Path:
    """Find authoritative configs/canonical_locations.json."""
    env_path = os.environ.get("VEYRA_LOCATION_REGISTRY_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    here = Path(__file__).resolve().parent
    candidates = [
        here.parents[2] / "configs" / "canonical_locations.json",
        here.parents[2] / "data" / "canonical_locations.json",
        Path.cwd() / "configs" / "canonical_locations.json",
        Path.cwd().parent / "forecast-bust-sentinel" / "configs" / "canonical_locations.json",
        Path.cwd().parent / "veyra" / "configs" / "canonical_locations.json",
    ]
    for c in candidates:
        if c.is_file():
            return c

    return here.parents[2] / "configs" / "canonical_locations.json"


class CanonicalLocationRegistry:
    """Authoritative location registry loaded from JSON with alias resolution and collision detection."""

    def __init__(self, registry_path: Optional[Union[str, Path]] = None):
        self._path = Path(registry_path) if registry_path else find_canonical_registry_path()
        self._locations: Dict[str, Dict[str, Any]] = {}
        self._alias_map: Dict[str, str] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(f"Canonical location registry not found at '{self._path}'")

        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data.get("locations", []):
            loc_id = normalize_alias(item.get("location_id", ""))
            if not loc_id:
                continue

            canonical_name = item.get("canonical_name", loc_id.capitalize())
            norm_name = normalize_alias(canonical_name)

            entry = {
                "location_id": loc_id,
                "canonical_name": canonical_name,
                "city": item.get("city", canonical_name),
                "country": item.get("country", "India"),
                "state_region": item.get("state_region", ""),
                "requested_latitude": float(item.get("requested_latitude", item.get("latitude", 0.0))),
                "requested_longitude": float(item.get("requested_longitude", item.get("longitude", 0.0))),
                "verified_grid_latitude": item.get("verified_grid_latitude"),
                "verified_grid_longitude": item.get("verified_grid_longitude"),
                "is_benchmark": bool(item.get("is_benchmark", False)),
                "is_extended": bool(item.get("is_extended", False)),
                "is_international": bool(item.get("is_international", False) or item.get("country", "") != "India"),
                "enabled": bool(item.get("enabled", True)),
                "elevation_m": item.get("elevation_m"),
                "climate_zone": item.get("climate_zone"),
                "meteorological_regime": item.get("meteorological_regime"),
                "rationale": item.get("rationale"),
                "aliases": item.get("aliases", []),
            }

            self._locations[loc_id] = entry

            all_aliases = [loc_id, norm_name] + [normalize_alias(a) for a in entry["aliases"]]
            for alias in all_aliases:
                if not alias:
                    continue
                if alias in self._alias_map and self._alias_map[alias] != loc_id:
                    raise ValueError(
                        f"Alias collision detected: '{alias}' is mapped to '{self._alias_map[alias]}' and cannot also map to '{loc_id}'."
                    )
                self._alias_map[alias] = loc_id

    def resolve_location(self, name_or_coords: str) -> Optional[Dict[str, Any]]:
        """Resolve input string to location dictionary."""
        if not isinstance(name_or_coords, str):
            return None

        clean = normalize_alias(name_or_coords)
        if not clean:
            return None

        if clean in self._alias_map:
            loc_id = self._alias_map[clean]
            return self._locations.get(loc_id)

        if "," in name_or_coords:
            parts = name_or_coords.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return {
                            "location_id": f"{lat:.4f},{lon:.4f}",
                            "canonical_name": f"{lat:.4f},{lon:.4f}",
                            "city": f"{lat:.4f},{lon:.4f}",
                            "country": "Custom",
                            "state_region": "Custom",
                            "requested_latitude": lat,
                            "requested_longitude": lon,
                            "is_benchmark": False,
                            "is_extended": False,
                            "is_international": False,
                            "enabled": True,
                        }
                except ValueError:
                    pass

        return None

    def resolve_coordinates(self, location: str) -> Optional[Tuple[float, float]]:
        res = self.resolve_location(location)
        if res:
            return (res["requested_latitude"], res["requested_longitude"])
        return None

    def resolve_canonical_id(self, location: str) -> Optional[str]:
        res = self.resolve_location(location)
        if res:
            return res.get("location_id")
        return None

    def is_enabled_for_prediction(self, location: str) -> bool:
        """Verify location is an enabled in-domain location (not international / unsupported)."""
        res = self.resolve_location(location)
        if not res:
            return False
        # International locations are unsupported for Indian ML model predictions
        if res.get("is_international", False) or not res.get("enabled", True):
            return False
        return True

    def get_all_locations(self) -> List[Dict[str, Any]]:
        return [self._locations[k] for k in sorted(self._locations.keys())]

    def get_benchmark_locations(self) -> List[Dict[str, Any]]:
        return [
            self._locations[k] for k in sorted(self._locations.keys())
            if self._locations[k].get("is_benchmark", False)
        ]


_default_registry = CanonicalLocationRegistry()


def get_location_registry() -> CanonicalLocationRegistry:
    return _default_registry


KNOWN_LOCATIONS: Dict[str, Tuple[float, float]] = {
    alias: (
        _default_registry._locations[loc_id]["requested_latitude"],
        _default_registry._locations[loc_id]["requested_longitude"],
    )
    for alias, loc_id in _default_registry._alias_map.items()
    if loc_id in _default_registry._locations
}

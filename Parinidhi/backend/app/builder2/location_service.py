"""
Location Registry and Spatial Colocation Service.

Resolves requested geographic coordinates to actual NWP forecast grid points,
computes explicit spatial mismatch distance (km), and manages regional groupings.

Zero hardcoded duplicate dictionaries — data-driven from configs/canonical_locations.json.
"""

import json
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.app.builder2.schemas import LocationCoordinates, LocationInfo


def normalize_alias(name: str) -> str:
    """Normalize location string by trimming, lowercasing, and collapsing whitespace."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth in kilometers.
    """
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def find_canonical_registry_path() -> Path:
    """Find the path to configs/canonical_locations.json."""
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


class LocationRegistry:
    """Registry of known monitoring points and spatial metadata."""

    def __init__(
        self,
        registry_path: Optional[Union[str, Path]] = None,
        custom_locations: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self._path = Path(registry_path) if registry_path else find_canonical_registry_path()
        self._locations: Dict[str, Dict[str, Any]] = {}
        self._alias_map: Dict[str, str] = {}

        self._load_registry()

        if custom_locations:
            for loc_id, cfg in custom_locations.items():
                self._register_internal(loc_id, cfg)

    def _load_registry(self) -> None:
        """Load and validate the authoritative JSON registry asset."""
        if not self._path.exists():
            raise FileNotFoundError(f"Authoritative canonical location registry not found at '{self._path}'")

        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_locs = data.get("locations", [])
        for item in raw_locs:
            loc_id = normalize_alias(item.get("location_id", ""))
            if not loc_id:
                continue
            self._register_internal(loc_id, item)

    def _register_internal(self, loc_id: str, cfg: Dict[str, Any]) -> None:
        norm_id = normalize_alias(loc_id)
        norm_name = normalize_alias(cfg.get("canonical_name", cfg.get("city", loc_id)))

        entry = {
            "location_id": norm_id,
            "canonical_name": cfg.get("canonical_name", cfg.get("city", loc_id.capitalize())),
            "city": cfg.get("city", cfg.get("canonical_name", loc_id.capitalize())),
            "country": cfg.get("country", "India"),
            "state_region": cfg.get("state_region", ""),
            "requested_latitude": float(cfg.get("requested_latitude", cfg.get("latitude", 0.0))),
            "requested_longitude": float(cfg.get("requested_longitude", cfg.get("longitude", 0.0))),
            "verified_grid_latitude": cfg.get("verified_grid_latitude"),
            "verified_grid_longitude": cfg.get("verified_grid_longitude"),
            "is_benchmark": bool(cfg.get("is_benchmark", False)),
            "is_extended": bool(cfg.get("is_extended", False)),
            "enabled": bool(cfg.get("enabled", True)),
            "elevation_m": cfg.get("elevation_m"),
            "climate_zone": cfg.get("climate_zone"),
            "meteorological_regime": cfg.get("meteorological_regime"),
            "rationale": cfg.get("rationale"),
            "aliases": cfg.get("aliases", []),
        }

        self._locations[norm_id] = entry

        all_aliases = [norm_id, norm_name] + [normalize_alias(a) for a in entry["aliases"]]
        for alias in all_aliases:
            if not alias:
                continue
            if alias in self._alias_map and self._alias_map[alias] != norm_id:
                raise ValueError(
                    f"Alias collision detected: '{alias}' is mapped to '{self._alias_map[alias]}' "
                    f"and cannot also map to '{norm_id}'."
                )
            self._alias_map[alias] = norm_id

    def resolve_location_id(self, location_name_or_alias: str) -> Optional[str]:
        if not isinstance(location_name_or_alias, str):
            return None
        norm = normalize_alias(location_name_or_alias)
        return self._alias_map.get(norm)

    def has_location(self, location_id_or_alias: str) -> bool:
        return self.resolve_location_id(location_id_or_alias) is not None

    def get_location(
        self,
        location_id: str,
        actual_grid_lat: Optional[float] = None,
        actual_grid_lon: Optional[float] = None,
    ) -> LocationInfo:
        resolved_id = self.resolve_location_id(location_id)
        if not resolved_id or resolved_id not in self._locations:
            raise KeyError(
                f"Unknown location_id '{location_id}'. Registered locations: {sorted(list(self._locations.keys()))}"
            )

        cfg = self._locations[resolved_id]
        req_lat = cfg["requested_latitude"]
        req_lon = cfg["requested_longitude"]

        grid_lat = actual_grid_lat if actual_grid_lat is not None else cfg.get("verified_grid_latitude")
        grid_lon = actual_grid_lon if actual_grid_lon is not None else cfg.get("verified_grid_longitude")

        if grid_lat is not None and grid_lon is not None:
            actual_coords = LocationCoordinates(latitude=grid_lat, longitude=grid_lon)
            dist_km = haversine_distance_km(req_lat, req_lon, grid_lat, grid_lon)
        else:
            actual_coords = None
            dist_km = None

        return LocationInfo(
            location_id=cfg["location_id"],
            country=cfg["country"],
            state_region=cfg["state_region"],
            city=cfg["city"],
            requested_coordinates=LocationCoordinates(latitude=req_lat, longitude=req_lon),
            actual_grid_coordinates=actual_coords,
            spatial_distance_km=dist_km,
        )

    def get_all_location_ids(self) -> List[str]:
        return sorted(self._locations.keys())

    def list_locations(self) -> List[Dict[str, Any]]:
        results = []
        for loc_id in sorted(self._locations.keys()):
            info = self.get_location(loc_id)
            results.append(info.to_dict())
        return results

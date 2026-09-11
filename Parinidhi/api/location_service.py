"""
Location Registry and Spatial Colocation Service.

Resolves requested geographic coordinates and location names/aliases
from the authoritative canonical location registry asset.
Computes explicit spatial mismatch distance (km) and manages regional groupings.

Zero hardcoded duplicate dictionaries — data-driven from configs/canonical_locations.json.
"""

import json
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from api.schemas import LocationCoordinates, LocationInfo


def normalize_alias(name: str) -> str:
    """Normalize location string by trimming, lowercasing, and collapsing whitespace."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
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
        here.parent / "configs" / "canonical_locations.json",
        here.parent / "data" / "canonical_locations.json",
        Path.cwd() / "configs" / "canonical_locations.json",
        Path.cwd().parent / "forecast-bust-sentinel" / "configs" / "canonical_locations.json",
        Path.cwd().parent / "veyra" / "configs" / "canonical_locations.json",
    ]
    for c in candidates:
        if c.is_file():
            return c

    return here.parent / "configs" / "canonical_locations.json"


class LocationRegistry:
    """
    Authoritative Registry of known meteorological monitoring points,
    loaded directly from declarative canonical registry asset.
    """

    def __init__(
        self,
        registry_path: Optional[Union[str, Path]] = None,
        custom_locations: Optional[Dict[str, Dict[str, Any]]] = None,
        include_extended: bool = False,
        include_international: bool = False,
        enabled_only: bool = False,
    ):
        self._path = Path(registry_path) if registry_path else find_canonical_registry_path()
        self._locations: Dict[str, Dict[str, Any]] = {}
        self._alias_map: Dict[str, str] = {}
        self._include_extended = include_extended
        self._include_international = include_international
        self._enabled_only = enabled_only

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

            is_intl = item.get("is_international", False) or item.get("country", "") != "India"

            # Filter international unless explicitly requested
            if is_intl and not self._include_international:
                continue

            if self._enabled_only and not item.get("enabled", True):
                continue

            # If extended stations are not requested, filter out is_extended stations
            if not self._include_extended and item.get("is_extended", False):
                continue

            self._register_internal(loc_id, item)

    def _register_internal(self, loc_id: str, cfg: Dict[str, Any]) -> None:
        """Internal helper to index location and validate alias uniqueness."""
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
            "is_international": bool(cfg.get("is_international", False)),
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
        """Resolve a name, alias, or ID string into canonical location_id, or None if unknown."""
        if not isinstance(location_name_or_alias, str):
            return None
        norm = normalize_alias(location_name_or_alias)
        return self._alias_map.get(norm)

    def has_location(self, location_id_or_alias: str) -> bool:
        """Check if a location_id or alias is registered."""
        return self.resolve_location_id(location_id_or_alias) is not None

    def get(self, location_id_or_alias: str) -> Optional[LocationInfo]:
        """Safely get location info by ID or alias, or return None if not found."""
        try:
            return self.get_location(location_id_or_alias)
        except (KeyError, ValueError):
            return None

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
            climate_zone=cfg.get("climate_zone"),
            meteorological_regime=cfg.get("meteorological_regime"),
            elevation_m=cfg.get("elevation_m"),
            is_benchmark=cfg.get("is_benchmark", False),
            rationale=cfg.get("rationale"),
        )

    def resolve_location(
        self,
        location_id_or_name: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        **kwargs: Any,
    ) -> LocationInfo:
        if not isinstance(location_id_or_name, str) or not location_id_or_name.strip():
            raise ValueError(f"Invalid location_id_or_name '{location_id_or_name}'. Must be a non-empty string.")

        resolved_id = self.resolve_location_id(location_id_or_name)
        if resolved_id:
            actual_grid_lat = kwargs.get("actual_grid_lat")
            actual_grid_lon = kwargs.get("actual_grid_lon")
            return self.get_location(resolved_id, actual_grid_lat=actual_grid_lat, actual_grid_lon=actual_grid_lon)

        if latitude is not None and longitude is not None:
            return self.register_location(
                location_id=location_id_or_name,
                requested_latitude=latitude,
                requested_longitude=longitude,
                **kwargs,
            )

        raise KeyError(
            f"Location '{location_id_or_name}' is not registered and no coordinates were supplied to register it on-the-fly."
        )

    def register_location(
        self,
        location_id: str,
        requested_latitude: float,
        requested_longitude: float,
        country: str = "India",
        state_region: str = "Custom Region",
        city: Optional[str] = None,
        verified_grid_latitude: Optional[float] = None,
        verified_grid_longitude: Optional[float] = None,
        climate_zone: Optional[str] = None,
        meteorological_regime: Optional[str] = None,
        elevation_m: Optional[float] = None,
        is_benchmark: bool = False,
        rationale: Optional[str] = None,
    ) -> LocationInfo:
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError(f"Invalid location_id '{location_id}'. Must be a non-empty string.")

        loc_key = normalize_alias(location_id)

        try:
            req_lat_f = float(requested_latitude)
            req_lon_f = float(requested_longitude)
        except (TypeError, ValueError) as err:
            raise ValueError(f"Requested coordinates must be valid numbers: {err}") from err

        if math.isnan(req_lat_f) or math.isinf(req_lat_f) or req_lat_f < -90.0 or req_lat_f > 90.0:
            raise ValueError(f"Invalid requested_latitude: {requested_latitude}. Must be finite and in [-90.0, 90.0].")
        if math.isnan(req_lon_f) or math.isinf(req_lon_f) or req_lon_f < -180.0 or req_lon_f > 180.0:
            raise ValueError(f"Invalid requested_longitude: {requested_longitude}. Must be finite and in [-180.0, 180.0].")

        if self.is_benchmark_location(loc_key):
            existing_cfg = self._locations[loc_key]
            existing_lat = existing_cfg["requested_latitude"]
            existing_lon = existing_cfg["requested_longitude"]
            if not (math.isclose(existing_lat, req_lat_f, abs_tol=1e-4) and math.isclose(existing_lon, req_lon_f, abs_tol=1e-4)):
                raise ValueError(
                    f"Cannot overwrite protected benchmark location '{loc_key}' with differing coordinates "
                    f"(existing: {existing_lat}, {existing_lon}; requested: {req_lat_f}, {req_lon_f})."
                )
            return self.get_location(loc_key)

        city_name = city or loc_key.capitalize()

        entry = {
            "location_id": loc_key,
            "country": country,
            "state_region": state_region,
            "city": city_name,
            "canonical_name": city_name,
            "requested_latitude": req_lat_f,
            "requested_longitude": req_lon_f,
            "verified_grid_latitude": float(verified_grid_latitude) if verified_grid_latitude is not None else None,
            "verified_grid_longitude": float(verified_grid_longitude) if verified_grid_longitude is not None else None,
            "climate_zone": climate_zone,
            "meteorological_regime": meteorological_regime,
            "elevation_m": float(elevation_m) if elevation_m is not None else None,
            "is_benchmark": bool(is_benchmark),
            "is_extended": False,
            "is_international": False,
            "enabled": True,
            "rationale": rationale,
            "aliases": [loc_key, normalize_alias(city_name)],
        }

        self._register_internal(loc_key, entry)
        return self.get_location(loc_key)

    def is_benchmark_location(self, location_id: str) -> bool:
        resolved_id = self.resolve_location_id(location_id)
        if not resolved_id or resolved_id not in self._locations:
            return False
        return bool(self._locations[resolved_id].get("is_benchmark", False))

    def list_locations(self) -> List[Dict[str, Any]]:
        results = []
        for loc_id in sorted(self._locations.keys()):
            info = self.get_location(loc_id)
            results.append(info.to_dict())
        return results

    def list_benchmark_locations(self) -> List[Dict[str, Any]]:
        results = []
        for loc_id in sorted(self._locations.keys()):
            if self._locations[loc_id].get("is_benchmark", False):
                info = self.get_location(loc_id)
                results.append(info.to_dict())
        return results

    def get_all_location_ids(self) -> List[str]:
        return sorted(list(self._locations.keys()))

    def get_benchmark_location_ids(self) -> List[str]:
        return sorted([
            loc_id for loc_id, cfg in self._locations.items()
            if cfg.get("is_benchmark", False)
        ])

    def get_climate_zone(self, location_id: str) -> Optional[str]:
        resolved_id = self.resolve_location_id(location_id)
        if not resolved_id or resolved_id not in self._locations:
            raise KeyError(f"Unknown location_id '{location_id}'")
        return self._locations[resolved_id].get("climate_zone")

    def get_meteorological_regime(self, location_id: str) -> Optional[str]:
        resolved_id = self.resolve_location_id(location_id)
        if not resolved_id or resolved_id not in self._locations:
            raise KeyError(f"Unknown location_id '{location_id}'")
        return self._locations[resolved_id].get("meteorological_regime")

    def get_locations_by_region(self, region: str) -> List[Dict[str, Any]]:
        region_clean = normalize_alias(region)
        results = []
        for loc_id, cfg in self._locations.items():
            if region_clean in normalize_alias(cfg.get("state_region", "")):
                results.append(self.get_location(loc_id).to_dict())
        return results

    def get_locations_by_climate(self, climate_zone: str) -> List[Dict[str, Any]]:
        cz_clean = normalize_alias(climate_zone).upper()
        results = []
        for loc_id, cfg in self._locations.items():
            cz = (cfg.get("climate_zone") or "").upper()
            if cz_clean in cz:
                results.append(self.get_location(loc_id).to_dict())
        return results

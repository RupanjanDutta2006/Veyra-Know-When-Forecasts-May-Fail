"""
Location Registry and Spatial Colocation Service.

Resolves requested geographic coordinates to actual NWP forecast grid points,
computes explicit spatial mismatch distance (km), and manages regional groupings.

If actual forecast grid coordinates are not supplied by the source dataset,
actual_grid_coordinates and spatial_distance_km remain unresolved (None).
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from backend.app.builder2.schemas import LocationCoordinates, LocationInfo


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth in kilometers.

    Args:
        lat1, lon1: Latitude and longitude of point 1 in degrees.
        lat2, lon2: Latitude and longitude of point 2 in degrees.

    Returns:
        Distance in kilometers.
    """
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class LocationRegistry:
    """Registry of known monitoring points and spatial metadata."""

    # Default registered locations (Delhi retains verified pilot grid point; others require source-resolution)
    DEFAULT_LOCATIONS: Dict[str, Dict[str, Any]] = {
        # North
        "delhi": {
            "location_id": "delhi",
            "country": "India",
            "state_region": "National Capital Region",
            "city": "Delhi",
            "requested_latitude": 28.6139,
            "requested_longitude": 77.2090,
            "verified_grid_latitude": 28.50,
            "verified_grid_longitude": 77.25,
        },
        "srinagar": {
            "location_id": "srinagar",
            "country": "India",
            "state_region": "Jammu and Kashmir",
            "city": "Srinagar",
            "requested_latitude": 34.0837,
            "requested_longitude": 74.7973,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "chandigarh": {
            "location_id": "chandigarh",
            "country": "India",
            "state_region": "Chandigarh",
            "city": "Chandigarh",
            "requested_latitude": 30.7333,
            "requested_longitude": 76.7794,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "jaipur": {
            "location_id": "jaipur",
            "country": "India",
            "state_region": "Rajasthan",
            "city": "Jaipur",
            "requested_latitude": 26.9124,
            "requested_longitude": 75.7873,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "lucknow": {
            "location_id": "lucknow",
            "country": "India",
            "state_region": "Uttar Pradesh",
            "city": "Lucknow",
            "requested_latitude": 26.8467,
            "requested_longitude": 80.9462,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        # West
        "mumbai": {
            "location_id": "mumbai",
            "country": "India",
            "state_region": "Maharashtra",
            "city": "Mumbai",
            "requested_latitude": 19.0760,
            "requested_longitude": 72.8777,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "pune": {
            "location_id": "pune",
            "country": "India",
            "state_region": "Maharashtra",
            "city": "Pune",
            "requested_latitude": 18.5204,
            "requested_longitude": 73.8567,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "ahmedabad": {
            "location_id": "ahmedabad",
            "country": "India",
            "state_region": "Gujarat",
            "city": "Ahmedabad",
            "requested_latitude": 23.0225,
            "requested_longitude": 72.5714,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "goa": {
            "location_id": "goa",
            "country": "India",
            "state_region": "Goa",
            "city": "Panaji",
            "requested_latitude": 15.2993,
            "requested_longitude": 73.8278,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        # Central
        "bhopal": {
            "location_id": "bhopal",
            "country": "India",
            "state_region": "Madhya Pradesh",
            "city": "Bhopal",
            "requested_latitude": 23.2599,
            "requested_longitude": 77.4126,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "nagpur": {
            "location_id": "nagpur",
            "country": "India",
            "state_region": "Maharashtra",
            "city": "Nagpur",
            "requested_latitude": 21.1458,
            "requested_longitude": 79.0882,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "raipur": {
            "location_id": "raipur",
            "country": "India",
            "state_region": "Chhattisgarh",
            "city": "Raipur",
            "requested_latitude": 21.2514,
            "requested_longitude": 81.6296,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        # East & North-East
        "kolkata": {
            "location_id": "kolkata",
            "country": "India",
            "state_region": "West Bengal",
            "city": "Kolkata",
            "requested_latitude": 22.5726,
            "requested_longitude": 88.3639,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "bhubaneswar": {
            "location_id": "bhubaneswar",
            "country": "India",
            "state_region": "Odisha",
            "city": "Bhubaneswar",
            "requested_latitude": 20.2961,
            "requested_longitude": 85.8245,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "ranchi": {
            "location_id": "ranchi",
            "country": "India",
            "state_region": "Jharkhand",
            "city": "Ranchi",
            "requested_latitude": 23.3441,
            "requested_longitude": 85.3096,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "guwahati": {
            "location_id": "guwahati",
            "country": "India",
            "state_region": "Assam",
            "city": "Guwahati",
            "requested_latitude": 26.1445,
            "requested_longitude": 91.7362,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        # South
        "bengaluru": {
            "location_id": "bengaluru",
            "country": "India",
            "state_region": "Karnataka",
            "city": "Bengaluru",
            "requested_latitude": 12.9716,
            "requested_longitude": 77.5946,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "chennai": {
            "location_id": "chennai",
            "country": "India",
            "state_region": "Tamil Nadu",
            "city": "Chennai",
            "requested_latitude": 13.0827,
            "requested_longitude": 80.2707,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "hyderabad": {
            "location_id": "hyderabad",
            "country": "India",
            "state_region": "Telangana",
            "city": "Hyderabad",
            "requested_latitude": 17.3850,
            "requested_longitude": 78.4867,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
        "kochi": {
            "location_id": "kochi",
            "country": "India",
            "state_region": "Kerala",
            "city": "Kochi",
            "requested_latitude": 9.9312,
            "requested_longitude": 76.2673,
            "verified_grid_latitude": None,
            "verified_grid_longitude": None,
        },
    }

    def __init__(self, custom_locations: Optional[Dict[str, Dict[str, Any]]] = None):
        self._locations = dict(self.DEFAULT_LOCATIONS)
        if custom_locations:
            self._locations.update(custom_locations)

    def get_location(
        self,
        location_id: str,
        actual_grid_lat: Optional[float] = None,
        actual_grid_lon: Optional[float] = None,
    ) -> LocationInfo:
        """
        Retrieve location info, resolving the spatial offset if actual grid coordinates exist.

        Args:
            location_id: Identifier of the location (case-insensitive).
            actual_grid_lat: Actual grid latitude from forecast source metadata.
            actual_grid_lon: Actual grid longitude from forecast source metadata.

        Returns:
            LocationInfo dataclass.
        """
        loc_key = location_id.strip().lower()
        if loc_key not in self._locations:
            raise KeyError(f"Unknown location_id '{location_id}'. Registered locations: {list(self._locations.keys())}")

        cfg = self._locations[loc_key]
        req_lat = cfg["requested_latitude"]
        req_lon = cfg["requested_longitude"]

        # Resolve actual grid coordinate: caller override > verified pilot grid coordinate > None
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

    def list_locations(self) -> List[Dict[str, Any]]:
        """Return list of all registered locations."""
        results = []
        for loc_id in sorted(self._locations.keys()):
            info = self.get_location(loc_id)
            results.append(info.to_dict())
        return results

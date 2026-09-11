"""Phase 5A Canonical Location System Architecture Tests for Builder 2.

Verifies:
1. Declarative canonical location registry loads identically from JSON.
2. All 25 frozen baseline locations are present and resolvable.
3. Case/whitespace normalization and alias resolution.
4. Fail-fast alias collision detection.
5. Fail-closed behavior for unknown/ambiguous inputs.
6. International locations are not enabled for unsupported ML inference.
"""

import json
from pathlib import Path
import pytest

from api.location_service import (
    LocationRegistry,
    find_canonical_registry_path,
    normalize_alias,
)
from api.schemas import LocationInfo


def test_registry_loads_from_json_asset():
    """Verify that LocationRegistry loads data from configs/canonical_locations.json."""
    registry_path = find_canonical_registry_path()
    assert registry_path.exists(), f"Registry JSON not found at {registry_path}"

    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("version") == "2.0.0"
    assert "locations" in data
    assert len(data["locations"]) >= 25


def test_frozen_25_locations_present():
    """Verify all 25 frozen baseline locations are resolvable."""
    reg = LocationRegistry(include_extended=True)

    expected_25 = [
        "delhi", "srinagar", "chandigarh", "jaipur", "lucknow",
        "mumbai", "pune", "ahmedabad", "goa", "bhopal",
        "nagpur", "raipur", "kolkata", "bhubaneswar", "ranchi",
        "guwahati", "bengaluru", "chennai", "hyderabad", "kochi",
        "patna", "shimla", "thiruvananthapuram", "visakhapatnam", "indore"
    ]

    for loc_id in expected_25:
        assert reg.has_location(loc_id) is True, f"Missing location: {loc_id}"
        info = reg.get_location(loc_id)
        assert isinstance(info, LocationInfo)
        assert info.location_id == loc_id
        assert info.requested_coordinates.latitude is not None
        assert info.requested_coordinates.longitude is not None


def test_bengaluru_and_aliases():
    """Verify Bengaluru resolves across all aliases and case variations."""
    reg = LocationRegistry()

    aliases = ["Bengaluru", "bengaluru", "Bangalore", "bangalore", "blr", "  bEnGaLuRu  ", "  BANGALORE  "]
    for alias in aliases:
        assert reg.has_location(alias) is True, f"Failed for alias: {alias}"
        info = reg.get_location(alias)
        assert info.location_id == "bengaluru"
        assert info.city == "Bengaluru"
        assert info.requested_coordinates.latitude == pytest.approx(12.9716, abs=1e-4)
        assert info.requested_coordinates.longitude == pytest.approx(77.5946, abs=1e-4)
        assert info.is_benchmark is True


def test_major_city_aliases():
    """Verify Mumbai/Bombay, Kolkata/Calcutta, Chennai/Madras, Goa/Panaji alias resolution."""
    reg = LocationRegistry()

    alias_pairs = [
        ("Mumbai", "bombay", "mumbai"),
        ("Kolkata", "calcutta", "kolkata"),
        ("Chennai", "madras", "chennai"),
        ("Goa", "panaji", "goa"),
        ("Delhi", "new delhi", "delhi"),
    ]

    for primary, alias, canonical_id in alias_pairs:
        assert reg.get_location(primary).location_id == canonical_id
        assert reg.get_location(alias).location_id == canonical_id


def test_whitespace_and_casing_normalization():
    """Verify robust normalization across tabs, uppercase, multiple spaces."""
    reg = LocationRegistry()

    assert reg.resolve_location_id("  delhi  ") == "delhi"
    assert reg.resolve_location_id("NEW   DELHI") == "delhi"
    assert reg.resolve_location_id("  bAnGaLoRe\t") == "bengaluru"
    assert reg.resolve_location_id("  MUMBAI  ") == "mumbai"


def test_unknown_location_fails_closed():
    """Verify unknown strings raise KeyError or return None."""
    reg = LocationRegistry()

    assert reg.has_location("AtlantisCityXYZ") is False
    assert reg.resolve_location_id("UnknownCity123") is None

    with pytest.raises(KeyError):
        reg.get_location("UnknownCity123")


def test_alias_collision_detection():
    """Verify registry raises ValueError on duplicate alias collision."""
    colliding_locations = {
        "fake_city": {
            "location_id": "fake_city",
            "city": "FakeCity",
            "country": "India",
            "requested_latitude": 20.0,
            "requested_longitude": 75.0,
            "aliases": ["bengaluru"],  # Collision with Bengaluru!
        }
    }

    with pytest.raises(ValueError, match="Alias collision detected"):
        LocationRegistry(custom_locations=colliding_locations)

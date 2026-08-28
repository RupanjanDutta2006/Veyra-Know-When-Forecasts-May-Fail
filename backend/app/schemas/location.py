"""Location and Spatial Resolution Schemas for Veyra."""
from dataclasses import dataclass
from typing import Any, Optional
from pydantic import BaseModel, Field


class ResolvedLocation(BaseModel):
    """Standardized representation of a resolved geographic location."""

    original_input: str = Field(
        ...,
        description="Original place name or coordinate string requested by the caller",
    )
    name: str = Field(
        ...,
        description="Standardized, canonical place or city name",
    )
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Resolved latitude in decimal degrees (-90.0 to 90.0)",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Resolved longitude in decimal degrees (-180.0 to 180.0)",
    )
    country: Optional[str] = Field(
        default=None,
        description="Country name if available",
    )
    state_region: Optional[str] = Field(
        default=None,
        description="State, province, or administrative region name",
    )
    timezone: Optional[str] = Field(
        default=None,
        description="Local timezone identifier (e.g., 'Asia/Kolkata', 'Europe/London')",
    )
    source: str = Field(
        default="dynamic_geocoding",
        description="Resolution mechanism ('direct_coordinates', 'geocoding_api', 'registry', 'cache')",
    )

    def to_coordinates(self) -> tuple[float, float]:
        """Return (latitude, longitude) coordinate tuple."""
        return (self.latitude, self.longitude)

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard dictionary format."""
        return {
            "original_input": self.original_input,
            "name": self.name,
            "latitude": round(self.latitude, 4),
            "longitude": round(self.longitude, 4),
            "country": self.country,
            "state_region": self.state_region,
            "timezone": self.timezone,
            "source": self.source,
        }

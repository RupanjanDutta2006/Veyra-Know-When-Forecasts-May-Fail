"""Unit Conversion Policy and Utilities for Meteorological Verification.

Provides explicit, documented conversions for temperature, pressure, wind speed,
and precipitation, rejecting any incompatible or unsupported unit pairs.
"""
from typing import Optional


class UnitMismatchError(ValueError):
    """Raised when two units belong to incompatible physical dimensions."""


class UnitConverter:
    """Rigorous physical unit converter for forecast and reference alignment."""

    # Standard canonical units for Veyra
    CANONICAL_UNITS: dict[str, str] = {
        "temperature_2m": "celsius",
        "surface_pressure": "hPa",
        "wind_speed_10m": "m/s",
        "relative_humidity_2m": "%",
        "precipitation": "mm",
        "geopotential_height_500hPa": "m",
    }

    @staticmethod
    def normalize_unit_string(unit: str) -> str:
        """Normalize unit string representations."""
        u = unit.strip().lower()
        mapping = {
            "°c": "celsius",
            "degc": "celsius",
            "c": "celsius",
            "k": "kelvin",
            "degk": "kelvin",
            "f": "fahrenheit",
            "degf": "fahrenheit",
            "pa": "pa",
            "hpa": "hpa",
            "mb": "hpa",
            "mbar": "hpa",
            "bar": "bar",
            "atm": "atm",
            "m/s": "m/s",
            "ms-1": "m/s",
            "mps": "m/s",
            "km/h": "km/h",
            "kmh": "km/h",
            "knot": "knots",
            "knots": "knots",
            "kt": "knots",
            "mph": "mph",
            "mm": "mm",
            "inch": "inches",
            "inches": "inches",
            "in": "inches",
            "%": "%",
            "percent": "%",
            "m": "m",
            "meter": "m",
            "meters": "m",
        }
        return mapping.get(u, u)

    @classmethod
    def convert(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert a numerical meteorological value between compatible units.

        Raises UnitMismatchError if units are incompatible or unknown.
        """
        u_from = cls.normalize_unit_string(from_unit)
        u_to = cls.normalize_unit_string(to_unit)

        if u_from == u_to:
            return value

        # Temperature conversions
        temp_units = {"celsius", "kelvin", "fahrenheit"}
        if u_from in temp_units and u_to in temp_units:
            # Convert from source to Celsius first
            if u_from == "kelvin":
                celsius = value - 273.15
            elif u_from == "fahrenheit":
                celsius = (value - 32.0) * 5.0 / 9.0
            else:
                celsius = value

            # Convert from Celsius to target
            if u_to == "kelvin":
                return round(celsius + 273.15, 4)
            elif u_to == "fahrenheit":
                return round((celsius * 9.0 / 5.0) + 32.0, 4)
            return round(celsius, 4)

        # Pressure conversions
        pressure_units = {"pa", "hpa", "bar", "atm"}
        if u_from in pressure_units and u_to in pressure_units:
            # Convert to hPa first
            if u_from == "pa":
                hpa = value / 100.0
            elif u_from == "bar":
                hpa = value * 1000.0
            elif u_from == "atm":
                hpa = value * 1013.25
            else:
                hpa = value

            # Convert from hPa to target
            if u_to == "pa":
                return round(hpa * 100.0, 4)
            elif u_to == "bar":
                return round(hpa / 1000.0, 6)
            elif u_to == "atm":
                return round(hpa / 1013.25, 6)
            return round(hpa, 4)

        # Wind Speed conversions
        speed_units = {"m/s", "km/h", "knots", "mph"}
        if u_from in speed_units and u_to in speed_units:
            # Convert to m/s first
            if u_from == "km/h":
                ms = value / 3.6
            elif u_from == "knots":
                ms = value * 0.514444
            elif u_from == "mph":
                ms = value * 0.44704
            else:
                ms = value

            # Convert from m/s to target
            if u_to == "km/h":
                return round(ms * 3.6, 4)
            elif u_to == "knots":
                return round(ms / 0.514444, 4)
            elif u_to == "mph":
                return round(ms / 0.44704, 4)
            return round(ms, 4)

        # Precipitation conversions
        precip_units = {"mm", "inches"}
        if u_from in precip_units and u_to in precip_units:
            if u_from == "inches" and u_to == "mm":
                return round(value * 25.4, 4)
            elif u_from == "mm" and u_to == "inches":
                return round(value / 25.4, 4)

        # Length / Geopotential conversions
        length_units = {"m"}
        if u_from in length_units and u_to in length_units:
            return value

        raise UnitMismatchError(
            f"Cannot convert between incompatible units: '{from_unit}' ({u_from}) and '{to_unit}' ({u_to})"
        )

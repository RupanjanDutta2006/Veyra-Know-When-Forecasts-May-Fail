"""Unit tests for Meteorological Unit Conversion Policy."""
import pytest
from backend.app.data.unit_conversion import UnitConverter, UnitMismatchError


def test_temperature_conversions():
    """Test standard temperature conversions."""
    # Kelvin to Celsius: 293.15 K == 20.0 °C
    assert UnitConverter.convert(293.15, "kelvin", "celsius") == 20.0
    # Celsius to Kelvin: 0.0 °C == 273.15 K
    assert UnitConverter.convert(0.0, "celsius", "kelvin") == 273.15
    # Fahrenheit to Celsius: 68.0 °F == 20.0 °C
    assert UnitConverter.convert(68.0, "fahrenheit", "celsius") == 20.0
    # Celsius to Fahrenheit: 20.0 °C == 68.0 °F
    assert UnitConverter.convert(20.0, "celsius", "fahrenheit") == 68.0
    # Same unit
    assert UnitConverter.convert(15.5, "celsius", "celsius") == 15.5


def test_pressure_conversions():
    """Test standard atmospheric pressure conversions."""
    # Pa to hPa: 101325 Pa == 1013.25 hPa
    assert UnitConverter.convert(101325.0, "pa", "hpa") == 1013.25
    # hPa to Pa: 1000.0 hPa == 100000.0 Pa
    assert UnitConverter.convert(1000.0, "hpa", "pa") == 100000.0
    # atm to hPa: 1.0 atm == 1013.25 hPa
    assert UnitConverter.convert(1.0, "atm", "hpa") == 1013.25


def test_wind_speed_conversions():
    """Test wind speed conversions."""
    # km/h to m/s: 36.0 km/h == 10.0 m/s
    assert UnitConverter.convert(36.0, "km/h", "m/s") == 10.0
    # knots to m/s: 10.0 knots == 5.1444 m/s
    assert UnitConverter.convert(10.0, "knots", "m/s") == 5.1444
    # mph to m/s: 10.0 mph == 4.4704 m/s
    assert UnitConverter.convert(10.0, "mph", "m/s") == 4.4704


def test_precipitation_conversions():
    """Test precipitation accumulation conversions."""
    # inches to mm: 1.0 inch == 25.4 mm
    assert UnitConverter.convert(1.0, "inches", "mm") == 25.4
    # mm to inches: 25.4 mm == 1.0 inch
    assert UnitConverter.convert(25.4, "mm", "inches") == 1.0


def test_incompatible_unit_rejection():
    """Test that attempting to convert across incompatible physical dimensions raises UnitMismatchError."""
    with pytest.raises(UnitMismatchError):
        UnitConverter.convert(20.0, "celsius", "m/s")

    with pytest.raises(UnitMismatchError):
        UnitConverter.convert(1013.25, "hpa", "kelvin")

    with pytest.raises(UnitMismatchError):
        UnitConverter.convert(10.0, "unknown_unit", "celsius")

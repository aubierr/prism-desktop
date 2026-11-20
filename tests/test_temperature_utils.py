import pytest

from core.temperature_utils import (
    convert_temperature,
    convert_temperature_delta,
    format_temperature,
    is_temperature_entity,
    normalize_temperature_unit,
    preference_to_unit,
    unit_suffix,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("°C", "C"),
        ("c", "C"),
        (" Celsius ", "C"),
        ("°F", "F"),
        ("fahrenheit", "F"),
        ("K", None),
        ("", None),
        (None, None),
        ("%", None),
    ],
)
def test_normalize_temperature_unit(raw, expected):
    assert normalize_temperature_unit(raw) == expected


def test_preference_falls_back_to_source_unit():
    assert preference_to_unit("fahrenheit") == "F"
    assert preference_to_unit("auto", fallback="°C") == "C"
    assert preference_to_unit(None, fallback=None) is None


def test_unit_suffix():
    assert unit_suffix("celsius") == "°C"
    assert unit_suffix("lux") == "°"


@pytest.mark.parametrize(
    "value, src, dst, expected",
    [
        (0, "°C", "°F", 32.0),
        (100, "C", "F", 212.0),
        (212, "F", "C", 100.0),
        ("21.5", "C", "C", 21.5),
        (20, "C", None, 20.0),  # unknown target: value unchanged
    ],
)
def test_convert_temperature(value, src, dst, expected):
    assert convert_temperature(value, src, dst) == pytest.approx(expected)


@pytest.mark.parametrize("value", [None, "", "--", "unavailable"])
def test_convert_temperature_rejects_non_numbers(value):
    assert convert_temperature(value, "C", "F") is None


def test_convert_delta_has_no_offset():
    # A 10 °C step is an 18 °F step, not 50.
    assert convert_temperature_delta(10, "C", "F") == pytest.approx(18.0)
    assert convert_temperature_delta(18, "F", "C") == pytest.approx(10.0)


@pytest.mark.parametrize(
    "value, src, pref, expected",
    [
        (20.0, "°C", None, "20°C"),
        (20.05, "°C", None, "20.1°C"),
        ("20.05", "°C", None, "20.1°C"),
        (0, "°C", "fahrenheit", "32°F"),
        (-0.01, "°C", None, "0°C"),  # no "-0"
        (None, "°C", None, "--°C"),
        ("unknown", None, None, "--"),
    ],
)
def test_format_temperature(value, src, pref, expected):
    assert format_temperature(value, src, pref) == expected


def test_format_temperature_keeps_inner_zeros():
    # Regression: a blanket replace(".0", "") used to turn 20.05 into "205".
    assert format_temperature(20.05, "C", precision=2) == "20.05°C"


def test_is_temperature_entity():
    assert is_temperature_entity({"device_class": "Temperature"})
    assert is_temperature_entity({"unit_of_measurement": "°F"})
    assert is_temperature_entity({"temperature_unit": "°C"})
    assert not is_temperature_entity({"unit_of_measurement": "%"})
    assert not is_temperature_entity(None)

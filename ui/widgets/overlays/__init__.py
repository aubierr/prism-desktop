"""Overlays that morph out of a dashboard tile into detailed controls.

One module per overlay; everything is re-exported here so callers keep
importing from ``ui.widgets.overlays``.
"""

from ui.widgets.overlays.base import (
    BORDER_SPIN_DURATION,
    BORDER_SPIN_EASING,
    CLOSE_FADE_EXPONENT,
    CLOSE_FADE_START,
    CONTENT_FADE_DURATION,
    CONTENT_FADE_EASING,
    MORPH_CLOSE_DURATION,
    MORPH_CLOSE_EASING,
    MORPH_OPEN_DURATION,
    MORPH_OPEN_EASING,
    OVERLAY_CORNER_RADIUS,
    BaseOverlay,
)
from ui.widgets.overlays.dimmer import DimmerOverlay
from ui.widgets.overlays.climate import ClimateOverlay
from ui.widgets.overlays.printer import PrinterOverlay
from ui.widgets.overlays.weather import WeatherOverlay
from ui.widgets.overlays.camera import CameraOverlay
from ui.widgets.overlays.robot import RobotOverlay, MowerOverlay, VacuumOverlay
from ui.widgets.overlays.alarm import AlarmOverlay

__all__ = [
    "BORDER_SPIN_DURATION", "BORDER_SPIN_EASING", "CLOSE_FADE_EXPONENT",
    "CLOSE_FADE_START", "CONTENT_FADE_DURATION", "CONTENT_FADE_EASING",
    "MORPH_CLOSE_DURATION", "MORPH_CLOSE_EASING", "MORPH_OPEN_DURATION",
    "MORPH_OPEN_EASING", "OVERLAY_CORNER_RADIUS",
    "BaseOverlay", "DimmerOverlay", "ClimateOverlay", "PrinterOverlay",
    "WeatherOverlay", "CameraOverlay", "RobotOverlay", "MowerOverlay",
    "VacuumOverlay", "AlarmOverlay",
]

"""
Free window placement for the dashboard (fork feature).

By default the dashboard is pinned next to the system tray. Once the user drags
it somewhere else, its position is stored in config['appearance']['window_position']
and reused on every show and on the next start, on whichever screen it was left.

The stored anchor is the window's TOP-RIGHT corner, because the dashboard grows
leftward when columns are added and downward when rows are added: keeping the
top-right fixed means a resize never makes the window jump.

Everything here is pure geometry (QRect/QPoint only, no QApplication needed) so
it can be unit tested.
"""

from typing import Iterable, Optional

from PyQt6.QtCore import QPoint, QRect

CONFIG_KEY = "window_position"


def saved_anchor(config: dict) -> Optional[QPoint]:
    """Return the saved top-right corner, or None when the window is tray-anchored."""
    pos = config.get("appearance", {}).get(CONFIG_KEY)
    if not isinstance(pos, dict):
        return None
    right, top = pos.get("right"), pos.get("top")
    if not isinstance(right, int) or not isinstance(top, int) \
            or isinstance(right, bool) or isinstance(top, bool):
        return None
    return QPoint(right, top)


def save_anchor(config: dict, geometry: QRect) -> None:
    """Store the window's top-right corner from its current geometry."""
    config.setdefault("appearance", {})[CONFIG_KEY] = {
        # QRect.right() is x + width - 1; store the exclusive edge instead.
        "right": geometry.x() + geometry.width(),
        "top": geometry.y(),
    }


def clear_anchor(config: dict) -> bool:
    """Forget the saved position. Returns True if there was one."""
    return config.get("appearance", {}).pop(CONFIG_KEY, None) is not None


def place(anchor: QPoint, width: int, height: int,
          screens: Iterable[QRect]) -> Optional[QPoint]:
    """Top-left position for a window of the given size at the saved anchor.

    The window is kept fully inside the available area of the screen it
    overlaps most (it may have been saved on a monitor that is now smaller, or
    resized since). Returns None when it no longer touches any screen, e.g. the
    monitor it was on has been unplugged; the caller then falls back to the tray.
    """
    rect = QRect(anchor.x() - width, anchor.y(), width, height)

    best, best_area = None, 0
    for screen in screens:
        inter = rect.intersected(screen)
        area = inter.width() * inter.height() if not inter.isEmpty() else 0
        if area > best_area:
            best, best_area = screen, area
    if best is None:
        return None

    x = min(max(rect.x(), best.x()), best.x() + best.width() - width)
    y = min(max(rect.y(), best.y()), best.y() + best.height() - height)
    # Window larger than the screen: pin to its top-left rather than going negative.
    x = max(x, best.x())
    y = max(y, best.y())
    return QPoint(x, y)

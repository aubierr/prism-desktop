"""
Drag-to-move for the frameless dashboard (fork feature).

Two ways to grab the window:
  * the edges the user can't resize from: the right edge, and the top or
    bottom edge opposite the resize one;
  * Alt + drag anywhere on the window, even over tiles.

The move itself is handed to the OS (QWindow.startSystemMove) so it follows
the cursor across monitors with different scaling. When it ends, the window's
top-right corner is saved and reused on every show and on the next start.
Tray menu → "Reset window position" goes back to the tray-anchored behaviour.

Lives in its own mixin so ui/dashboard.py only needs a few hooks and keeps
merging cleanly with the upstream project.
"""

import logging

from PyQt6.QtCore import QEvent, QPoint, QTimer, Qt
from PyQt6.QtWidgets import QApplication

from ui import window_placement
from ui.constants import RESIZE_MARGIN

logger = logging.getLogger(__name__)

# The OS move loop doesn't always hand the mouse release back to Qt, so the
# end of a move is detected as "no movement for this long and button up".
MOVE_SETTLE_MS = 350


class WindowMoveMixin:
    """Mixed into Dashboard. Expects self.config, self.save_config_requested,
    self._glass_ui / self._glass_refresh_timer and the resize state fields."""

    def _init_window_move(self):
        self._user_moving = False
        self._manual_move_offset: QPoint | None = None
        self._move_settle_timer = QTimer(self)
        self._move_settle_timer.setSingleShot(True)
        self._move_settle_timer.setInterval(MOVE_SETTLE_MS)
        self._move_settle_timer.timeout.connect(self._on_move_settled)

    # ── State ────────────────────────────────────────────────────────────

    def _is_free_positioned(self) -> bool:
        """True once the user has dragged the window away from the tray."""
        return window_placement.saved_anchor(self.config) is not None

    def _free_target_pos(self) -> QPoint | None:
        """Where the window belongs in free mode, clamped to a connected screen.
        None if not in free mode or the saved screen is gone (tray fallback)."""
        anchor = window_placement.saved_anchor(self.config)
        if anchor is None:
            return None
        screens = [s.availableGeometry() for s in QApplication.screens()]
        return window_placement.place(anchor, self.width(), self.height(), screens)

    def _clamp_free_position(self):
        """Keep a free-positioned window on screen after it changed size."""
        if self._user_moving or not self.isVisible():
            return
        pos = self._free_target_pos()
        if pos is not None and pos != self.pos():
            self._target_pos = pos
            self.move(pos)

    def reset_window_position(self):
        """Forget the dragged position and snap back next to the tray."""
        if window_placement.clear_anchor(self.config):
            logger.info("Window position reset to the tray")
            self.save_config_requested.emit()
        self.refresh_tray_anchor(move_now=True)

    # ── Grabbing ─────────────────────────────────────────────────────────

    def _in_move_zone(self, x: float, y: float) -> bool:
        """Edges that don't resize: right, plus top or bottom (whichever the
        resize handle isn't on)."""
        if x > self.width() - RESIZE_MARGIN:
            return True
        if self._is_top_anchored():
            return y < RESIZE_MARGIN
        return y > self.height() - RESIZE_MARGIN

    def _start_window_move(self, global_pos: QPoint):
        self._dismiss_banner_immediate()
        if getattr(self, 'overlay_manager', None):
            self.overlay_manager.close_all_overlays()
        self._ignore_focus_loss = True
        self._user_moving = True
        self._glass_refresh_timer.stop()

        handle = self.windowHandle()
        if handle is not None and handle.startSystemMove():
            # In case the user clicks without moving at all.
            self._move_settle_timer.start()
            return
        # Platform without system move support: drag it ourselves.
        self._manual_move_offset = global_pos - self.pos()
        self.grabMouse()

    def _manual_move_to(self, global_pos: QPoint):
        if self._manual_move_offset is not None:
            self.move(global_pos - self._manual_move_offset)

    def _end_manual_move(self):
        if self._manual_move_offset is None:
            return False
        self._manual_move_offset = None
        self.releaseMouse()
        self._on_move_settled()
        return True

    def _handle_alt_drag(self, obj, event) -> bool:
        """Called from the app-level event filter. Returns True if consumed."""
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.AltModifier
                and not self._user_moving
                and not self._is_resizing_window
                and not self._assist_active
                and (obj is self or self.isAncestorOf(obj))):
            self._start_window_move(event.globalPosition().toPoint())
            return True
        return False

    # ── End of a move ────────────────────────────────────────────────────

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._user_moving and self._manual_move_offset is None:
            self._move_settle_timer.start()

    def _on_move_settled(self):
        if self._manual_move_offset is not None:
            return
        if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            # Still holding the window, just not moving it right now.
            self._move_settle_timer.start()
            return
        if not self._user_moving:
            return
        self._user_moving = False

        window_placement.save_anchor(self.config, self.geometry())
        self._target_pos = self.pos()
        # Slightly off-screen drops get pulled back in, then saved where they land.
        self._clamp_free_position()
        window_placement.save_anchor(self.config, self.geometry())
        logger.info(f"Window moved; saved position {self.config['appearance'][window_placement.CONFIG_KEY]}")
        self.save_config_requested.emit()

        if self._glass_ui and self.isVisible():
            self._refresh_glass_background()
            self._glass_refresh_timer.start()

        self.raise_()
        self.activateWindow()
        QTimer.singleShot(300, lambda: setattr(self, '_ignore_focus_loss', False))

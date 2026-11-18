"""Dimmer overlay: brightness/volume slider that morphs out of a tile."""

from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient, QPainterPath
from core.utils import SYSTEM_FONT
from ui.widgets.dashboard_button_painter import DashboardButtonPainter
from ui.widgets.overlays.base import BaseOverlay, OVERLAY_CORNER_RADIUS


# ─────────────────────────────────────────────────────────────────────────────


class DimmerOverlay(BaseOverlay):
    """Overlay slider that morphs from a button."""
    value_changed = pyqtSignal(int)   # 0-100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value      = 0
        self._text       = "Dimmer"
        self._color      = QColor("#FFD700")
        self._base_color = QColor("#2d2d2d")

    def start_morph(self, start_geo: QRect, target_geo: QRect, initial_value: int, text: str,
                    color: QColor = None, base_color: QColor = None):
        self._value      = initial_value
        self._text       = text
        self._color      = color      or QColor("#FFD700")
        self._base_color = base_color or QColor("#2d2d2d")
        self._start_morph_animations(start_geo, target_geo)
        self.grabMouse()

    def close_morph(self):
        self.releaseMouse()
        super().close_morph()

    def mousePressEvent(self, event):
        event.accept()
        self.grabMouse()
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        rect = self.rect()
        if rect.width() == 0:
            return
        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
        pct = max(0.0, min(1.0, local_pos.x() / rect.width()))
        new_val = int(pct * 100)
        if new_val != self._value:
            self._value = new_val
            self.update()
            self.value_changed.emit(self._value)

    def mouseReleaseEvent(self, event):
        self.close_morph()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_close_fade(painter)

        rect = self.rect()
        self._draw_background(painter, rect)

        fill_width = int(rect.width() * (self._value / 100.0))
        if fill_width > 0:
            grad = QLinearGradient(0, 0, rect.width(), 0)
            grad.setColorAt(0, self._color.darker(120))
            grad.setColorAt(1, self._color)
            painter.setBrush(grad)
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), OVERLAY_CORNER_RADIUS, OVERLAY_CORNER_RADIUS)
            painter.setClipPath(path)
            painter.drawRect(QRect(0, 0, fill_width, rect.height()))

        painter.setClipping(False)
        DashboardButtonPainter.draw_image_edge_effects(painter, QRectF(rect), is_top_clamped=False, is_light=self._is_light_bg())
        self._draw_border_animation(painter, rect)

        painter.setClipping(False)
        alpha = max(0, int(255 * self._morph_progress))

        font_label = QFont(SYSTEM_FONT, 11, QFont.Weight.DemiBold)
        font_label.setCapitalization(QFont.Capitalization.AllUppercase)
        painter.setFont(font_label)
        text_rect = rect.adjusted(16, 0, -16, 0)
        painter.setPen(self._fg_color(int(alpha * 0.7)))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)

        painter.setFont(QFont(SYSTEM_FONT, 20, QFont.Weight.Light))
        painter.setPen(self._fg_color(alpha))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{self._value}%")

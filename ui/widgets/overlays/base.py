"""Shared animation constants and BaseOverlay, the parent of every overlay."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QRect,
    QPointF,
    QRectF,
)
from PyQt6.QtGui import QColor, QBrush, QPen, QConicalGradient


# ── Shared Overlay Animation Constants ──────────────────────────────
MORPH_OPEN_DURATION   = 400                          # ms – expand from button


MORPH_OPEN_EASING     = QEasingCurve.Type.OutCubic


MORPH_CLOSE_DURATION  = 400                          # ms – shrink back to button


MORPH_CLOSE_EASING    = QEasingCurve.Type.InOutCubic


CLOSE_FADE_EXPONENT   = 0.5                          # painter opacity = progress ** this


CLOSE_FADE_START      = 0.35                          # start fading when progress drops below this


BORDER_SPIN_DURATION  = 1300                         # ms – rainbow/aurora border animation


BORDER_SPIN_EASING    = QEasingCurve.Type.InOutQuad


CONTENT_FADE_DURATION = 300                          # ms – content fade-in after open


CONTENT_FADE_EASING   = QEasingCurve.Type.OutQuad


OVERLAY_CORNER_RADIUS = 12                           # px – rounded rect radius


# ────────────────────────────────────────────────────────────────────


class BaseOverlay(QWidget):
    """
    Shared animation, border drawing, and color logic for all overlays.

    Provides: morph animation, border spin animation, content fade animation,
    luminance-based text color, and common paint helpers.
    Subclasses implement start_morph() and paintEvent().
    """
    finished      = pyqtSignal()
    morph_changed = pyqtSignal(float)   # 0.0 – 1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.raise_()
        self.hide()

        self._text       = ""
        self._color      = QColor("#FFD700")
        self._base_color = QColor("#2d2d2d")

        # ── Morph animation ──
        self._morph_progress = 0.0
        self.anim = QPropertyAnimation(self, b"morph_progress")
        self.anim.setDuration(MORPH_OPEN_DURATION)
        self.anim.setEasingCurve(MORPH_OPEN_EASING)
        self.anim.finished.connect(self.on_anim_finished)

        # ── Border spin animation ──
        self._border_progress = 0.0
        self.anim_border = QPropertyAnimation(self, b"border_progress")
        self.anim_border.setDuration(BORDER_SPIN_DURATION)
        self.anim_border.setEasingCurve(BORDER_SPIN_EASING)

        # ── Content fade animation ──
        self._content_opacity = 0.0
        self.content_anim = QPropertyAnimation(self, b"content_opacity")
        self.content_anim.setDuration(CONTENT_FADE_DURATION)
        self.content_anim.setEasingCurve(CONTENT_FADE_EASING)
        self.content_anim.setStartValue(0.0)
        self.content_anim.setEndValue(1.0)

        self._border_effect = 'Rainbow'
        self._is_closing    = False
        self._start_geom    = QRect()
        self._target_geom   = QRect()

    # ── Color helpers ──

    def _is_light_bg(self):
        c = self._base_color
        lum = 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()
        return lum > 140

    def _fg_color(self, alpha=255):
        if self._is_light_bg():
            return QColor(0, 0, 0, alpha)
        return QColor(255, 255, 255, alpha)

    # ── Qt properties ──

    def get_morph_progress(self):
        return self._morph_progress

    def set_morph_progress(self, val):
        self._morph_progress = val
        self.morph_changed.emit(val)
        current_rect = QRect(
            int(self._start_geom.x() + (self._target_geom.x() - self._start_geom.x()) * val),
            int(self._start_geom.y() + (self._target_geom.y() - self._start_geom.y()) * val),
            int(self._start_geom.width()  + (self._target_geom.width()  - self._start_geom.width())  * val),
            int(self._start_geom.height() + (self._target_geom.height() - self._start_geom.height()) * val),
        )
        self.setGeometry(current_rect)
        self.update()

    morph_progress = pyqtProperty(float, get_morph_progress, set_morph_progress)

    def get_border_progress(self):
        return self._border_progress

    def set_border_progress(self, val):
        self._border_progress = val
        self.update()

    border_progress = pyqtProperty(float, get_border_progress, set_border_progress)

    def get_content_opacity(self):
        return self._content_opacity

    def set_content_opacity(self, val):
        self._content_opacity = val
        self.update()

    content_opacity = pyqtProperty(float, get_content_opacity, set_content_opacity)

    # ── Lifecycle ──

    def _start_morph_animations(self, start_geo: QRect, target_geo: QRect):
        """Start morph + border animations. Call from subclass start_morph()."""
        self._start_geom      = start_geo
        self._target_geom     = target_geo
        self._is_closing      = False
        self._content_opacity = 0.0

        self.content_anim.stop()

        self.setGeometry(start_geo)
        self.show()
        self.raise_()
        self.activateWindow()

        self.anim.stop()
        self.anim.setDuration(MORPH_OPEN_DURATION)
        self.anim.setEasingCurve(MORPH_OPEN_EASING)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

        self.anim_border.stop()
        self.anim_border.setStartValue(0.0)
        self.anim_border.setEndValue(1.0)
        self.anim_border.start()

    def close_morph(self):
        self._is_closing      = True
        self._content_opacity = 0.0
        self.update()

        self.anim.stop()
        self.anim.setDuration(MORPH_CLOSE_DURATION)
        self.anim.setEasingCurve(MORPH_CLOSE_EASING)
        self.anim.setStartValue(self._morph_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def on_anim_finished(self):
        if self._is_closing:
            self.hide()
            self.finished.emit()
        else:
            self.content_anim.start()

    def set_border_effect(self, effect: str):
        self._border_effect = effect
        self.update()

    # ── Paint helpers ──

    def _draw_close_fade(self, painter):
        """Apply closing fade opacity. Call at the top of paintEvent."""
        if self._is_closing and self._morph_progress < CLOSE_FADE_START:
            t = self._morph_progress / CLOSE_FADE_START
            painter.setOpacity(t ** CLOSE_FADE_EXPONENT)

    def _draw_background(self, painter, rect):
        painter.setBrush(self._base_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, OVERLAY_CORNER_RADIUS, OVERLAY_CORNER_RADIUS)

    def _draw_border_animation(self, painter, rect):
        if self.anim_border.state() != QPropertyAnimation.State.Running:
            return
        if self._border_effect == 'Rainbow':
            self._draw_rainbow_border(painter, rect)
        elif self._border_effect == 'Aurora Borealis':
            self._draw_aurora_border(painter, rect)
        elif self._border_effect == 'Prism Shard':
            self._draw_prism_shard_border(painter, rect)
        elif self._border_effect == 'Liquid Mercury':
            self._draw_liquid_mercury_border(painter, rect)
        painter.setOpacity(1.0)

    # ── Border drawing ──

    def _draw_rainbow_border(self, painter, rect):
        self._draw_gradient_border(painter, rect, ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#4285F4"])

    def _draw_aurora_border(self, painter, rect):
        self._draw_gradient_border(painter, rect, ["#00C896", "#0078FF", "#8C00FF", "#0078FF", "#00C896"])

    def _draw_prism_shard_border(self, painter, rect):
        self._draw_gradient_border(painter, rect, ["#26C6DA", "#EC407A", "#FFCA28", "#CFD8DC", "#26C6DA"])

    def _draw_liquid_mercury_border(self, painter, rect):
        self._draw_gradient_border(painter, rect, ["#37474F", "#78909C", "#CFD8DC", "#ECEFF1", "#CFD8DC", "#78909C", "#37474F"])

    def _draw_gradient_border(self, painter, rect, colors):
        speed = 0.9 if self._border_effect == 'Prism Shard' else 1.5
        if self._border_effect == 'Liquid Mercury':
            speed = 1.2
        angle = self._border_progress * 360.0 * speed

        opacity = 1.0
        if self._border_progress > 0.8:
            opacity = (1.0 - self._border_progress) / 0.2
        painter.setOpacity(opacity)

        gradient = QConicalGradient(QPointF(rect.center()), angle)
        for i, color in enumerate(colors):
            gradient.setColorAt(i / (len(colors) - 1), QColor(color))

        pen = QPen(QBrush(gradient), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), OVERLAY_CORNER_RADIUS, OVERLAY_CORNER_RADIUS)

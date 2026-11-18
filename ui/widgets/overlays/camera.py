"""Camera overlay: enlarged camera image."""

from PyQt6.QtCore import Qt, QRect, QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from ui.icons import get_icon, get_mdi_font
from ui.widgets.dashboard_button_painter import DashboardButtonPainter
from ui.widgets.overlays.base import BaseOverlay, OVERLAY_CORNER_RADIUS


# ─────────────────────────────────────────────────────────────────────────────


class CameraOverlay(BaseOverlay):
    """Dynamic overlay for full camera view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._camera_pixmap = None
        self._text          = "Camera"
        self._base_color    = QColor("#2d2d2d")
        self._btn_close     = QRect()

    def on_anim_finished(self):
        if self._is_closing:
            self._camera_pixmap = None
        super().on_anim_finished()

    def set_camera_pixmap(self, pixmap):
        self._camera_pixmap = pixmap
        if self.isVisible():
            self.update()

    def start_morph(self, start_geo: QRect, target_geo: QRect, text: str, base_color: QColor = None):
        self._text       = text
        self._base_color = base_color or QColor("#2d2d2d")
        self._start_morph_animations(start_geo, target_geo)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_close_fade(painter)

        rect = self.rect()
        self._draw_background(painter, rect)

        bg_pix = None
        x_bg   = 0
        y_bg   = 0

        if self._camera_pixmap and not self._camera_pixmap.isNull():
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), OVERLAY_CORNER_RADIUS, OVERLAY_CORNER_RADIUS)
            painter.setClipPath(path)

            w = rect.width()
            h = rect.height()
            scaled_cam = self._camera_pixmap.scaled(
                int(w), int(h),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x_off = (scaled_cam.width()  - w) / 2
            y_off = (scaled_cam.height() - h) / 2

            painter.drawPixmap(0, 0, scaled_cam, int(x_off), int(y_off), int(w), int(h))

            bg_pix = scaled_cam
            x_bg   = int(x_off)
            y_bg   = int(y_off)

        DashboardButtonPainter.draw_image_edge_effects(painter, QRectF(rect), is_top_clamped=False, is_light=self._is_light_bg())
        self._draw_border_animation(painter, rect)

        rect_int = rect.toRect() if isinstance(rect, QRectF) else rect
        alpha    = int(255 * self._morph_progress)
        if alpha < 10:
            return

        painter.setOpacity(alpha / 255.0)

        is_light = self._is_light_bg()
        pill_bg  = QColor(255, 255, 255) if is_light else QColor(30, 30, 30)
        pill_fg  = QColor(30, 30, 30)   if is_light else QColor(255, 255, 255)

        DashboardButtonPainter._draw_pill_label(
            painter, rect_int, self._text,
            background_pixmap=bg_pix, x_off=x_bg, y_off=y_bg,
            position='top-left', forced_bg_color=pill_bg, forced_text_color=pill_fg
        )

        close_size      = 28
        close_x         = rect_int.width() - close_size - 12
        close_y         = 12
        self._btn_close = QRect(close_x, close_y, close_size, close_size)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(pill_bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(self._btn_close), 14, 14)
        painter.restore()

        painter.setFont(get_mdi_font(18))
        painter.setPen(pill_fg)
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

    def mousePressEvent(self, event):
        if self._btn_close.contains(event.pos()):
            self.close_morph()

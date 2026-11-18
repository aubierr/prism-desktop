"""3D printer overlay: camera, temperatures, progress and controls."""

from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPainterPath
from ui.icons import get_icon, get_mdi_font
from core.utils import SYSTEM_FONT
from core.temperature_utils import format_temperature
from core.localization_manager import t
from ui.widgets.dashboard_button_painter import DashboardButtonPainter
from ui.widgets.overlays.base import BaseOverlay


# ─────────────────────────────────────────────────────────────────────────────


class PrinterOverlay(BaseOverlay):
    """Overlay for 3D Printer telemetry and controls."""
    action_requested = pyqtSignal(str)   # 'pause', 'stop'

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text       = "3D Printer"
        self._color      = QColor("#FF6D00")
        self._base_color = QColor("#2d2d2d")

        self._state                       = "unknown"
        self._hotend_actual               = 0.0
        self._hotend_target               = 0.0
        self._bed_actual                  = 0.0
        self._bed_target                  = 0.0
        self._progress                    = 0.0
        self._time_remaining              = ""
        self._camera_pixmap               = None
        self._temperature_unit_preference = "celsius"
        self._printer_source_unit         = None

        self._btn_close = QRect()
        self._btn_pause = QRect()
        self._btn_stop  = QRect()

        self._confirm_stop_mode = False
        self._confirm_timer     = QTimer(self)
        self._confirm_timer.setSingleShot(True)
        self._confirm_timer.setInterval(3000)
        self._confirm_timer.timeout.connect(self._reset_confirm_mode)

        self.setMouseTracking(True)
        self._hover_pause = False
        self._hover_stop  = False

    def _state_color(self) -> QColor:
        s = self._state.lower()
        if s in ('printing', 'heating'):
            return QColor("#4CAF50")
        elif s == 'paused':
            return QColor("#FF9800")
        elif s in ('error', 'offline', 'unknown'):
            return QColor("#F44336")
        else:
            return QColor("#2196F3")

    def _is_active_state(self) -> bool:
        return self._state.lower() in ('printing', 'heating', 'paused')

    def _reset_confirm_mode(self):
        self._confirm_stop_mode = False
        self.update()

    def update_state(self, current_state: dict):
        self._state = current_state.get('state', 'unknown')
        attrs = current_state.get('attributes', {})

        def safe_float(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        self._hotend_actual           = safe_float(attrs.get('hotend_actual', 0.0))
        self._hotend_target           = safe_float(attrs.get('hotend_target', 0.0))
        self._bed_actual              = safe_float(attrs.get('bed_actual', 0.0))
        self._bed_target              = safe_float(attrs.get('bed_target', 0.0))
        self._printer_source_unit     = attrs.get('temperature_unit')
        self._progress                = safe_float(attrs.get('progress', 0.0))
        self._time_remaining          = attrs.get('time_remaining', '')
        self.update()

    def set_camera_pixmap(self, pixmap):
        self._camera_pixmap = pixmap
        self.update()

    def set_temperature_unit_preference(self, preference: str):
        self._temperature_unit_preference = preference
        self.update()

    def start_morph(self, start_geo: QRect, target_geo: QRect, label: str,
                    color: QColor = None, base_color: QColor = None, current_state: dict = None):
        if current_state:
            self.update_state(current_state)
        self._text              = label
        self._color             = color      or QColor("#FF6D00")
        self._base_color        = base_color or QColor("#2d2d2d")
        self._confirm_stop_mode = False
        self._start_morph_animations(start_geo, target_geo)

    def mousePressEvent(self, event):
        pos = event.pos()
        if self._btn_close.contains(pos):
            self.close_morph()
        elif self._btn_pause.contains(pos):
            action = 'resume' if self._state.lower() == 'paused' else 'pause'
            self.action_requested.emit(action)
        elif self._btn_stop.contains(pos):
            if not self._confirm_stop_mode:
                self._confirm_stop_mode = True
                self._confirm_timer.start()
                self.update()
            else:
                self._confirm_stop_mode = False
                self._confirm_timer.stop()
                self.action_requested.emit('stop')
                self.close_morph()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        new_hover_pause = self._btn_pause.contains(pos) if hasattr(self, '_btn_pause') else False
        new_hover_stop  = self._btn_stop.contains(pos)  if hasattr(self, '_btn_stop')  else False
        if new_hover_pause != self._hover_pause or new_hover_stop != self._hover_stop:
            self._hover_pause = new_hover_pause
            self._hover_stop  = new_hover_stop
            self.update()

    def leaveEvent(self, event):
        self._hover_pause = False
        self._hover_stop  = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_close_fade(painter)

        rect = self.rect()
        self._draw_background(painter, rect)
        DashboardButtonPainter.draw_image_edge_effects(painter, QRectF(rect), is_top_clamped=False, is_light=self._is_light_bg())
        self._draw_border_animation(painter, rect)

        base_alpha = int(255 * self._morph_progress)
        alpha = int(base_alpha * self._content_opacity)
        if alpha < 10:
            return

        is_wide = rect.width() > rect.height() * 1.2
        if is_wide:
            self._draw_split_layout(painter, rect, alpha)
        else:
            self._draw_stacked_layout(painter, rect, alpha)

    def _draw_split_layout(self, painter, rect, alpha):
        pad   = 14
        mid_x = int(rect.width() * 0.6)

        # Camera (left 60%)
        cam_rect = QRect(pad, pad, mid_x - pad * 2, rect.height() - pad * 2)
        self._draw_camera(painter, cam_rect, alpha)

        # Close button anchored top-right of whole overlay
        close_size      = 20
        self._btn_close = QRect(rect.width() - close_size - pad, pad, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(self._fg_color(int(alpha * 0.5)))
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

        # Right panel
        rx = mid_x
        rw = rect.width() - mid_x - pad
        ry = pad

        # Header: title left, compact state badge right (before close)
        _badge_pad  = 12
        badge_label = self._state.upper()
        fm_badge    = QFontMetrics(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        badge_w     = fm_badge.horizontalAdvance(badge_label) + _badge_pad
        badge_x     = max(rx + 4, rect.width() - close_size - pad - 4 - badge_w)
        self._draw_state_badge(painter, badge_x, ry + 1, alpha, pill_pad=_badge_pad)

        title_w = badge_x - rx - 4
        if title_w > 20:
            title_font = QFont(SYSTEM_FONT, 10, QFont.Weight.Bold)
            fm_title   = QFontMetrics(title_font)
            painter.setFont(title_font)
            painter.setPen(self._fg_color(alpha))
            elided = fm_title.elidedText(self._text, Qt.TextElideMode.ElideRight, title_w)
            painter.drawText(QRect(rx, ry, title_w, 22),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)
        ry += 26   # header (22px) + gap (4px)

        # Progress bar — always visible; green when printing, yellow otherwise
        _active   = self._is_active_state()
        bar_color = QColor("#4CAF50") if self._state.lower() in ('printing', 'heating') else QColor("#FF9800")
        track_col = QColor(bar_color); track_col.setAlpha(45)
        fill_col  = QColor(bar_color); fill_col.setAlpha(220)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_col)
        painter.drawRoundedRect(QRect(rx, ry, rw, 6), 3, 3)
        fill_w = int(rw * (self._progress / 100.0))
        if fill_w > 0:
            painter.setBrush(fill_col)
            painter.drawRoundedRect(QRect(rx, ry, fill_w, 6), 3, 3)
        ry += 10   # bar + gap

        if _active:
            # Time remaining + percentage
            painter.setFont(QFont(SYSTEM_FONT, 8))
            painter.setPen(self._fg_color(int(alpha * 0.6)))
            painter.drawText(QRect(rx, ry, rw, 16), Qt.AlignmentFlag.AlignLeft,  self._time_remaining)
            painter.drawText(QRect(rx, ry, rw, 16), Qt.AlignmentFlag.AlignRight, f"{self._progress:.0f}%")

        # Decide whether to use side-by-side cards or inline temps
        use_cards = (rw - 8) // 2 >= 52
        card_h    = 40 if use_cards else 28

        if _active:
            # Anchored to bottom when active
            btn_y  = rect.height() - pad - 36
            card_y = btn_y - 8 - card_h
        else:
            # Center cards+buttons in remaining space below the bar
            content_h = card_h + 8 + 36
            avail     = rect.height() - ry - pad
            start_y   = ry + max(4, (avail - content_h) // 2)
            card_y    = start_y
            btn_y     = start_y + card_h + 8

        if use_cards:
            self._draw_temp_cards(painter, rx, card_y, rw, card_h, alpha)
        else:
            self._draw_inline_temps(painter, rx, card_y, rw, card_h, alpha)
        self._draw_action_buttons(painter, rx, btn_y, rw, 36, alpha)

    def _draw_stacked_layout(self, painter, rect, alpha):
        if rect.height() < 210:
            self._draw_compact_stacked(painter, rect, alpha)
        else:
            self._draw_full_stacked(painter, rect, alpha)

    def _draw_full_stacked(self, painter, rect, alpha):
        pad = 12
        sw  = rect.width() - pad * 2

        # Close button
        close_size      = 20
        self._btn_close = QRect(rect.width() - close_size - pad, pad, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(self._fg_color(int(alpha * 0.5)))
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

        # State badge right of title in the same header row
        badge_label = self._state.upper()
        fm_badge    = QFontMetrics(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        badge_w     = fm_badge.horizontalAdvance(badge_label) + 18
        badge_x     = rect.width() - close_size - pad - 6 - badge_w
        self._draw_state_badge(painter, badge_x, pad + 1, alpha)

        painter.setFont(QFont(SYSTEM_FONT, 11, QFont.Weight.Bold))
        painter.setPen(self._fg_color(alpha))
        painter.drawText(QRect(pad, pad, badge_x - pad - 4, 22),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)

        # Bottom section (anchored from bottom upward)
        _active   = self._is_active_state()
        btn_y     = rect.height() - pad - 36
        card_y    = btn_y - 8 - 44
        cam_top   = pad + 22 + 8
        bar_color = QColor("#4CAF50") if self._state.lower() in ('printing', 'heating') else QColor("#FF9800")

        # Bar and optional time row sit between camera and temp cards
        if _active:
            time_y = card_y - 4 - 16
            bar_y  = time_y - 4 - 6
        else:
            bar_y  = card_y - 10  # bar flush above cards

        # Camera fills space between header and bar
        cam_h = bar_y - 8 - cam_top
        if cam_h > 24:
            self._draw_camera(painter, QRect(pad, cam_top, sw, cam_h), alpha)

        # Progress bar — always visible
        track_col = QColor(bar_color); track_col.setAlpha(45)
        fill_col  = QColor(bar_color); fill_col.setAlpha(220)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_col)
        painter.drawRoundedRect(QRect(pad, bar_y, sw, 6), 3, 3)
        fill_w = int(sw * (self._progress / 100.0))
        if fill_w > 0:
            painter.setBrush(fill_col)
            painter.drawRoundedRect(QRect(pad, bar_y, fill_w, 6), 3, 3)

        if _active:
            # Time remaining + percentage
            painter.setFont(QFont(SYSTEM_FONT, 8))
            painter.setPen(self._fg_color(int(alpha * 0.6)))
            painter.drawText(QRect(pad, time_y, sw, 16), Qt.AlignmentFlag.AlignLeft,  self._time_remaining)
            painter.drawText(QRect(pad, time_y, sw, 16), Qt.AlignmentFlag.AlignRight, f"{self._progress:.0f}%")

        self._draw_temp_cards(painter, pad, card_y, sw, 44, alpha)
        self._draw_action_buttons(painter, pad, btn_y, sw, 36, alpha)

    def _draw_compact_stacked(self, painter, rect, alpha):
        pad = 12
        sw  = rect.width() - pad * 2
        y   = 10

        # Title + close button
        close_size      = 20
        self._btn_close = QRect(rect.width() - close_size - pad, y, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(self._fg_color(int(alpha * 0.5)))
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

        painter.setFont(QFont(SYSTEM_FONT, 11, QFont.Weight.Bold))
        painter.setPen(self._fg_color(alpha))
        painter.drawText(QRect(pad, y, sw - close_size - 4, 22),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)
        y += 28

        # State badge
        self._draw_state_badge(painter, pad, y, alpha)
        y += 28   # 16px badge + 12px margin before bar

        # Progress bar — always visible; green when printing, yellow otherwise
        _active   = self._is_active_state()
        bar_color = QColor("#4CAF50") if self._state.lower() in ('printing', 'heating') else QColor("#FF9800")
        track_col = QColor(bar_color); track_col.setAlpha(45)
        fill_col  = QColor(bar_color); fill_col.setAlpha(220)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_col)
        painter.drawRoundedRect(QRect(pad, y, sw, 6), 3, 3)
        fill_w = int(sw * (self._progress / 100.0))
        if fill_w > 0:
            painter.setBrush(fill_col)
            painter.drawRoundedRect(QRect(pad, y, fill_w, 6), 3, 3)
        y += 10   # bar + gap

        if _active:
            # Time remaining + percentage
            painter.setFont(QFont(SYSTEM_FONT, 8))
            painter.setPen(self._fg_color(int(alpha * 0.6)))
            painter.drawText(QRect(pad, y, sw, 16), Qt.AlignmentFlag.AlignLeft,  self._time_remaining)
            painter.drawText(QRect(pad, y, sw, 16), Qt.AlignmentFlag.AlignRight, f"{self._progress:.0f}%")
            y += 20
        else:
            y += 4

        # Inline temp row
        self._draw_inline_temps(painter, pad, y, sw, 28, alpha)
        y += 32

        # Action buttons
        self._draw_action_buttons(painter, pad, y, sw, 36, alpha)

    def _draw_camera(self, painter, rect, alpha):
        painter.setBrush(QColor(0, 0, 0, int(alpha * 0.4)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 8, 8)

        if self._camera_pixmap and not self._camera_pixmap.isNull():
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 8, 8)
            painter.setClipPath(path)

            scale = max(rect.width() / self._camera_pixmap.width(), rect.height() / self._camera_pixmap.height())
            pw = self._camera_pixmap.width()  * scale
            ph = self._camera_pixmap.height() * scale
            px = rect.x() + (rect.width()  - pw) / 2
            py = rect.y() + (rect.height() - ph) / 2

            painter.setOpacity(alpha / 255.0)
            painter.drawPixmap(QRectF(px, py, pw, ph), self._camera_pixmap, QRectF(self._camera_pixmap.rect()))
            painter.setOpacity(1.0)
            painter.setClipping(False)

            scaled_pixmap = self._camera_pixmap.scaled(
                int(pw), int(ph),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x_off = (pw - rect.width())  / 2
            y_off = (ph - rect.height()) / 2

            if self._is_active_state():
                painter.translate(rect.x(), rect.y())
                DashboardButtonPainter._draw_pill_label(
                    painter, QRect(0, 0, rect.width(), rect.height()), f"{self._progress:.0f}%",
                    background_pixmap=scaled_pixmap, x_off=x_off, y_off=y_off, position='top-right'
                )
                painter.translate(-rect.x(), -rect.y())
        else:
            painter.setPen(self._fg_color(int(alpha * 0.3)))
            painter.setFont(get_mdi_font(32))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, get_icon("video-off"))
            painter.setFont(QFont(SYSTEM_FONT, 10))
            painter.drawText(rect.adjusted(0, 40, 0, 0), Qt.AlignmentFlag.AlignCenter, t("overlay.printer.no_feed"))

            if self._is_active_state():
                painter.translate(rect.x(), rect.y())
                DashboardButtonPainter._draw_pill_label(
                    painter, QRect(0, 0, rect.width(), rect.height()), f"{self._progress:.0f}%",
                    background_pixmap=None, x_off=0, y_off=0, position='top-right'
                )
                painter.translate(-rect.x(), -rect.y())

    def _draw_state_badge(self, painter, x, y, alpha, pill_pad: int = 18):
        state_color = self._state_color()
        state_color.setAlpha(min(255, int(alpha * 0.9)))

        label  = self._state.upper()
        fm     = QFontMetrics(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        pill_w = fm.horizontalAdvance(label) + pill_pad

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(state_color)
        painter.drawRoundedRect(QRect(x, y, pill_w, 16), 8, 8)

        painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        painter.setPen(QColor(255, 255, 255, alpha))
        painter.drawText(QRect(x, y, pill_w, 16), Qt.AlignmentFlag.AlignCenter, label)

    def _draw_temp_cards(self, painter, x, y, w, h, alpha):
        _fmt        = lambda v: format_temperature(v, self._printer_source_unit, self._temperature_unit_preference, precision=0, fallback="0")
        gap         = 8
        card_w      = (w - gap) // 2
        icon_colors = [QColor("#FF6D00"), QColor("#42A5F5")]  # orange nozzle, blue bed

        for i, (icon_name, actual, target) in enumerate([
            ('printer-3d-nozzle', self._hotend_actual, self._hotend_target),
            ('square-medium',     self._bed_actual,    self._bed_target),
        ]):
            cx        = x + i * (card_w + gap)
            card_rect = QRect(cx, y, card_w, h)
            ic        = icon_colors[i]

            # Card with colored tint matching its icon
            border_col = QColor(ic); border_col.setAlpha(130)
            bg_col     = QColor(ic); bg_col.setAlpha(35)
            painter.setPen(QPen(border_col, 1.5))
            painter.setBrush(bg_col)
            painter.drawRoundedRect(card_rect, 8, 8)

            ic_pen   = QColor(ic); ic_pen.setAlpha(min(255, int(alpha * 0.95)))
            font_val = QFont(SYSTEM_FONT, 9, QFont.Weight.Bold)
            tx       = cx + 8 + 22
            tw       = card_w - 8 - 22 - 4

            if target > 5:
                half = h // 2
                painter.setFont(get_mdi_font(15))
                painter.setPen(ic_pen)
                painter.drawText(QRect(cx + 8, y, 22, half),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, get_icon(icon_name))
                painter.setFont(font_val)
                painter.setPen(self._fg_color(alpha))
                painter.drawText(QRect(tx, y, tw, half),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, _fmt(actual))
                painter.setFont(QFont(SYSTEM_FONT, 8))
                painter.setPen(self._fg_color(int(alpha * 0.55)))
                painter.drawText(QRect(tx, y + half, tw, half),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"→ {_fmt(target)}")
            else:
                painter.setFont(get_mdi_font(14))
                painter.setPen(ic_pen)
                painter.drawText(QRect(cx + 8, y, 22, h),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, get_icon(icon_name))
                painter.setFont(font_val)
                painter.setPen(self._fg_color(alpha))
                painter.drawText(QRect(tx, y, tw, h),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, _fmt(actual))

    def _draw_inline_temps(self, painter, x, y, w, h, alpha):
        # Strip trailing letter from unit ("205°C" → "205°") to save space in compact layout
        def _fmt_short(v):
            s = format_temperature(v, self._printer_source_unit, self._temperature_unit_preference, precision=0, fallback="0")
            return s[:-1] if s and s[-1].isalpha() else s

        painter.setPen(QPen(self._fg_color(50), 1.5))
        painter.setBrush(self._fg_color(20))
        painter.drawRoundedRect(QRect(x, y, w, h), 8, 8)

        # Vertical divider
        mid_x = x + w // 2
        painter.setPen(QPen(self._fg_color(35), 1))
        painter.drawLine(mid_x, y + 4, mid_x, y + h - 4)

        icon_colors = [QColor("#FF6D00"), QColor("#42A5F5")]  # orange nozzle, blue bed
        half_w      = w // 2
        for i, (icon_name, actual, target) in enumerate([
            ('printer-3d-nozzle', self._hotend_actual, self._hotend_target),
            ('square-medium',     self._bed_actual,    self._bed_target),
        ]):
            hx     = x + i * half_w
            ic_pen = QColor(icon_colors[i]); ic_pen.setAlpha(min(255, int(alpha * 0.95)))

            painter.setFont(get_mdi_font(12))
            painter.setPen(ic_pen)
            painter.drawText(QRect(hx + 4, y, 16, h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, get_icon(icon_name))

            # "205°/210°" or just "205°" when target is off/idle
            if target > 5:
                val_text = f"{_fmt_short(actual)}/{_fmt_short(target)}"
            else:
                val_text = _fmt_short(actual)
            painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
            painter.setPen(self._fg_color(alpha))
            painter.drawText(QRect(hx + 20, y, half_w - 22, h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, val_text)

    def _draw_action_buttons(self, painter, x, y, w, h, alpha):
        btn_w      = (w - 8) // 2
        is_paused  = self._state.lower() == 'paused'
        pause_icon = 'play' if is_paused else 'pause'
        pause_label = t("overlay.printer.resume_btn") if is_paused else t("overlay.printer.pause_btn")
        stop_label  = t("overlay.printer.stop_btn")

        show_text = btn_w >= 80
        font_text = QFont(SYSTEM_FONT, 10, QFont.Weight.Bold)
        icon_w    = 20   # MDI glyph width at 15pt
        icon_gap  = 6
        radius    = 8

        def _draw_btn(btn_rect, icon_name, label, is_stop):
            if is_stop and self._confirm_stop_mode:
                bg  = QColor("#C62828")
                bdr = QColor(255, 110, 110, 220)
            elif is_stop:
                hover = self._hover_stop
                bg  = QColor(200, 60, 60, 70 if hover else 45)
                bdr = QColor(220, 80, 80, 160 if hover else 110)
            else:
                hover = self._hover_pause
                bg  = QColor(60, 110, 200, 70 if hover else 45)
                bdr = QColor(80, 140, 230, 160 if hover else 110)

            painter.setPen(QPen(bdr, 1.5))
            painter.setBrush(bg)
            painter.drawRoundedRect(btn_rect, radius, radius)
            painter.setPen(self._fg_color(alpha))

            if is_stop and self._confirm_stop_mode:
                painter.setFont(font_text)
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, t("overlay.printer.confirm_stop"))
            elif show_text:
                painter.setFont(get_mdi_font(15))
                painter.drawText(QRect(btn_rect.x() + 8, btn_rect.y(), icon_w, btn_rect.height()),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 get_icon(icon_name))
                painter.setFont(font_text)
                painter.drawText(QRect(btn_rect.x() + 8 + icon_w + icon_gap, btn_rect.y(), btn_rect.width() - 8 - icon_w - icon_gap - 4, btn_rect.height()),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            else:
                painter.setFont(get_mdi_font(16))
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, get_icon(icon_name))

        self._btn_pause = QRect(x, y, btn_w, h)
        _draw_btn(self._btn_pause, pause_icon, pause_label, False)

        self._btn_stop = QRect(x + btn_w + 8, y, btn_w, h)
        _draw_btn(self._btn_stop, 'stop', stop_label, True)

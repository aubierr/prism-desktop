"""Robot overlays: shared RobotOverlay and the lawn mower and vacuum variants."""

from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from ui.icons import get_icon, get_mdi_font
from core.utils import SYSTEM_FONT
from core.localization_manager import t
from ui.widgets.dashboard_button_painter import DashboardButtonPainter
from ui.widgets.overlays.base import BaseOverlay, OVERLAY_CORNER_RADIUS


# ─────────────────────────────────────────────────────────────────────────────


class RobotOverlay(BaseOverlay):
    """
    Base class for robot device overlays (lawn mower, vacuum, etc.).

    Subclasses declare domain-specific constants:
        ACTIVE_STATES  – tuple of HA states that trigger "Pause" mode
        START_ACTION   – service action string emitted when starting
        DOCK_ACTION    – service action string emitted for dock button
        DEFAULT_LABEL  – fallback label when none is provided
    """
    ACTIVE_STATES: tuple = ()
    START_ACTION:  str   = ''
    DOCK_ACTION:   str   = ''
    DEFAULT_LABEL: str   = ''

    action_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text       = self.DEFAULT_LABEL
        self._color      = QColor("#4CAF50")
        self._base_color = QColor("#2d2d2d")

        self._state         = "unknown"
        self._battery_level = -1.0

        self._btn_close       = QRect()
        self._btn_start_pause = QRect()
        self._btn_dock        = QRect()

        self.setMouseTracking(True)
        self._hover_start_pause = False
        self._hover_dock        = False

    def update_state(self, state_dict: dict):
        self._state = state_dict.get('state', 'unknown')
        attrs = state_dict.get('attributes', {})
        try:
            self._battery_level = float(attrs.get('battery_level', -1))
        except (ValueError, TypeError):
            self._battery_level = -1.0
        self.update()

    def start_morph(self, start_geo: QRect, target_geo: QRect, label: str,
                    color: QColor = None, base_color: QColor = None, current_state: dict = None):
        if current_state:
            self.update_state(current_state)
        self._text       = label
        self._color      = color      or QColor("#4CAF50")
        self._base_color = base_color or QColor("#2d2d2d")
        self._start_morph_animations(start_geo, target_geo)

    def mousePressEvent(self, event):
        pos = event.pos()
        if self._btn_close.contains(pos):
            self.close_morph()
        elif self._btn_start_pause.contains(pos):
            if self._state in self.ACTIVE_STATES:
                self.action_requested.emit('pause')
            else:
                self.action_requested.emit(self.START_ACTION)
        elif self._btn_dock.contains(pos):
            self.action_requested.emit(self.DOCK_ACTION)

    def mouseMoveEvent(self, event):
        pos    = event.pos()
        new_sp = self._btn_start_pause.contains(pos)
        new_dk = self._btn_dock.contains(pos)
        if new_sp != self._hover_start_pause or new_dk != self._hover_dock:
            self._hover_start_pause = new_sp
            self._hover_dock        = new_dk
            self.update()

    def leaveEvent(self, event):
        self._hover_start_pause = False
        self._hover_dock        = False
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
        alpha      = int(base_alpha * self._content_opacity)
        if alpha < 10:
            return

        padding = 16
        fg      = self._fg_color(alpha)
        dim_fg  = self._fg_color(int(alpha * 0.5))

        close_size      = 20
        self._btn_close = QRect(rect.width() - close_size - padding, padding, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(dim_fg)
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

        state_display = self._state.replace('_', ' ').capitalize()
        painter.setFont(QFont(SYSTEM_FONT, 13, QFont.Weight.Bold))
        painter.setPen(fg)
        state_rect = QRectF(padding, padding, rect.width() - padding * 2 - close_size, 24)
        painter.drawText(state_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, state_display)

        btn_h         = 36
        gap           = 8
        pill_h        = 22
        pill_gap      = 10
        avail_w       = rect.width() - padding * 2
        btn_w         = (avail_w - gap) / 2
        total_group_h = btn_h + pill_gap + pill_h
        btn_y         = padding + 24 + 4 + (rect.height() - padding * 2 - 24 - 4 - total_group_h) / 2
        pill_y        = btn_y + btn_h + pill_gap
        pill_rect     = QRectF(padding, pill_y, avail_w, pill_h)

        is_active = self._state in self.ACTIVE_STATES
        sp_rect   = QRectF(padding, btn_y, btn_w, btn_h)
        self._btn_start_pause = sp_rect.toAlignedRect()

        sp_color = QColor(self._color)
        if self._hover_start_pause:
            sp_color = sp_color.lighter(120)
        sp_color.setAlpha(alpha)

        path_sp = QPainterPath()
        path_sp.addRoundedRect(sp_rect, OVERLAY_CORNER_RADIUS, OVERLAY_CORNER_RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(sp_color)
        painter.drawPath(path_sp)

        sp_icon  = get_icon('pause') if is_active else get_icon('play')
        sp_label = t("overlay.robot.pause_btn") if is_active else t("overlay.robot.start_btn")
        painter.setPen(self._fg_color(alpha))
        icon_x = sp_rect.x() + 12
        painter.setFont(get_mdi_font(16))
        painter.drawText(QRectF(icon_x, sp_rect.y(), 20, btn_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, sp_icon)
        painter.setFont(QFont(SYSTEM_FONT, 11, QFont.Weight.DemiBold))
        painter.drawText(QRectF(icon_x + 22, sp_rect.y(), btn_w - 34, btn_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, sp_label)

        dk_rect  = QRectF(padding + btn_w + gap, btn_y, btn_w, btn_h)
        self._btn_dock = dk_rect.toAlignedRect()

        dk_fill  = self._fg_color(int(alpha * 0.20) if self._hover_dock else int(alpha * 0.12))
        path_dk  = QPainterPath()
        path_dk.addRoundedRect(dk_rect, OVERLAY_CORNER_RADIUS, OVERLAY_CORNER_RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dk_fill)
        painter.drawPath(path_dk)

        painter.setPen(self._fg_color(alpha))
        icon_x2 = dk_rect.x() + 12
        painter.setFont(get_mdi_font(16))
        painter.drawText(QRectF(icon_x2, dk_rect.y(), 20, btn_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, get_icon('home'))
        painter.setFont(QFont(SYSTEM_FONT, 11, QFont.Weight.DemiBold))
        painter.drawText(QRectF(icon_x2 + 22, dk_rect.y(), btn_w - 34, btn_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, t("overlay.robot.dock_btn"))

        if self._battery_level >= 0:
            if self._battery_level > 50:
                bar_color = QColor("#34A853")
            elif self._battery_level > 20:
                bar_color = QColor("#FBBC05")
            else:
                bar_color = QColor("#EA4335")
            bar_color.setAlpha(alpha)

            DashboardButtonPainter.draw_horizontal_bar_pill(
                painter,
                pill_rect,
                fraction=self._battery_level / 100.0,
                fill_color=bar_color,
                track_color=self._fg_color(int(alpha * 0.12)),
                text=f"{int(self._battery_level)}%",
                font=QFont(SYSTEM_FONT, 9, QFont.Weight.Bold),
                text_color=self._fg_color(alpha),
            )

        painter.end()


# ─────────────────────────────────────────────────────────────────────────────


class MowerOverlay(RobotOverlay):
    """Lawn mower control overlay."""
    ACTIVE_STATES = ('mowing', 'returning')
    START_ACTION  = 'start_mowing'
    DOCK_ACTION   = 'dock'
    DEFAULT_LABEL = 'Mower'


class VacuumOverlay(RobotOverlay):
    """Vacuum control overlay."""
    ACTIVE_STATES = ('cleaning', 'returning')
    START_ACTION  = 'start'
    DOCK_ACTION   = 'return_to_base'
    DEFAULT_LABEL = 'Vacuum'

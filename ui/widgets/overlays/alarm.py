"""Alarm panel overlay: arm/disarm actions and keypad."""

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QRect,
    QRectF,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath
from ui.icons import get_icon, get_mdi_font
from core.utils import SYSTEM_FONT
from core.localization_manager import t
from ui.widgets.dashboard_button_painter import DashboardButtonPainter
from ui.widgets.overlays.base import BaseOverlay, OVERLAY_CORNER_RADIUS


# ─────────────────────────────────────────────────────────────────────────────


class AlarmOverlay(BaseOverlay):
    """
    Overlay for alarm_control_panel: arm-mode selection, a Disarm button, and an
    optional numeric keypad when the panel requires a code.

    Emits action_requested(action, code) where action is one of
    'arm_home' / 'arm_away' / 'arm_night' / 'arm_vacation' / 'arm_custom_bypass' / 'disarm'.
    """

    action_requested = pyqtSignal(str, str)
    keypad_toggled   = pyqtSignal(bool)  # True when the keypad needs to be shown/hidden — panel must resize

    # action -> (mdi icon name, translation key)
    MODE_META = {
        'arm_home':          ('home',              'overlay.alarm.mode_home'),
        'arm_away':          ('briefcase-outline',  'overlay.alarm.mode_away'),
        'arm_night':         ('weather-night',      'overlay.alarm.mode_night'),
        'arm_vacation':      ('airplane',           'overlay.alarm.mode_vacation'),
        'arm_custom_bypass': ('shield-half-full',   'overlay.alarm.mode_bypass'),
    }
    ARMED_STATES = (
        'armed_home', 'armed_away', 'armed_night', 'armed_vacation',
        'armed_custom_bypass', 'arming', 'pending', 'disarming', 'triggered',
    )
    STATE_LABEL_KEYS = {
        'disarmed':            'overlay.alarm.state_disarmed',
        'armed_home':          'overlay.alarm.state_armed_home',
        'armed_away':          'overlay.alarm.state_armed_away',
        'armed_night':         'overlay.alarm.state_armed_night',
        'armed_vacation':      'overlay.alarm.state_armed_vacation',
        'armed_custom_bypass': 'overlay.alarm.state_armed_bypass',
        'arming':              'overlay.alarm.state_arming',
        'pending':              'overlay.alarm.state_pending',
        'disarming':           'overlay.alarm.state_disarming',
        'triggered':            'overlay.alarm.state_triggered',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text       = 'Alarm'
        self._color      = QColor("#4285F4")
        self._base_color = QColor("#2d2d2d")

        self._state           = 'unknown'
        self._available_modes = []     # e.g. ['arm_home', 'arm_away']
        self._code_for_arm    = False
        self._code_for_disarm = False

        self._pending_action  = None   # action awaiting code confirmation, or None
        self._entered_code    = ''

        self._btn_close  = QRect()
        self._mode_btns  = []          # [(QRect, action)]
        self._btn_disarm = QRect()
        self._keypad_btns = []         # [(QRect, 'digit'|'back'|'submit', value)]

        self._press_rect  = QRect()
        self._press_scale = 1.0
        self._press_anim  = QPropertyAnimation(self, b"press_scale_prop")
        self._press_anim.finished.connect(self._on_press_anim_finished)

    def get_press_scale(self): return self._press_scale
    def set_press_scale(self, v):
        self._press_scale = v
        self.update()
    press_scale_prop = pyqtProperty(float, get_press_scale, set_press_scale)

    def _on_press_anim_finished(self):
        if self._press_scale < 1.0:
            self._press_anim.setDuration(180)
            self._press_anim.setEasingCurve(QEasingCurve.Type.OutBack)
            self._press_anim.setStartValue(self._press_scale)
            self._press_anim.setEndValue(1.0)
            self._press_anim.start()
        else:
            self._press_rect = QRect()

    def _trigger_press_anim(self, btn_rect: QRect):
        self._press_rect = btn_rect
        self._press_anim.stop()
        self._press_anim.setDuration(80)
        self._press_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._press_anim.setStartValue(1.0)
        self._press_anim.setEndValue(0.85)
        self._press_anim.start()

    # ── Configuration ──

    def configure_modes(self, modes: list):
        self._available_modes = [m for m in modes if m in self.MODE_META]

    def configure_code(self, code_for_arm: bool, code_for_disarm: bool):
        self._code_for_arm    = code_for_arm
        self._code_for_disarm = code_for_disarm

    def update_state(self, state_dict: dict):
        if not state_dict:
            return
        new_state = state_dict.get('state', 'unknown')
        if new_state != self._state:
            # Entity moved on (e.g. armed, or someone else disarmed it) — drop any in-progress entry.
            self._entered_code = ''
            self._set_pending_action(None)
        self._state = new_state
        self.update()

    def start_morph(self, start_geo: QRect, target_geo: QRect, label: str,
                    color: QColor = None, base_color: QColor = None, current_state: dict = None):
        self._pending_action = None
        self._entered_code   = ''
        self._btn_disarm     = QRect()
        self._mode_btns      = []
        self._keypad_btns    = []
        if current_state:
            self.update_state(current_state)
        self._text       = label
        self._color      = color      or QColor("#4285F4")
        self._base_color = base_color or QColor("#2d2d2d")
        self._start_morph_animations(start_geo, target_geo)

    def _requires_code(self, action: str) -> bool:
        return self._code_for_disarm if action == 'disarm' else self._code_for_arm

    def _set_pending_action(self, action):
        """Show/hide the keypad, notifying the manager so the panel can resize to fit it."""
        was_showing = self._pending_action is not None
        self._pending_action = action
        now_showing = self._pending_action is not None
        if now_showing != was_showing:
            self.keypad_toggled.emit(now_showing)
        self.update()

    def resize_to(self, new_target_geo: QRect):
        """Animate a live resize (e.g. growing to fit the keypad) without re-doing the button morph."""
        self._start_morph_animations(self.geometry(), new_target_geo)

    def _request_action(self, action: str):
        if self._requires_code(action):
            self._entered_code = ''
            self._set_pending_action(action)
        else:
            self.action_requested.emit(action, '')

    # ── Interaction ──

    def mousePressEvent(self, event):
        pos = event.pos()
        if self._btn_close.contains(pos):
            self.close_morph()
            return

        if self._pending_action:
            for rect_btn, kind, value in self._keypad_btns:
                if not rect_btn.contains(pos):
                    continue
                self._trigger_press_anim(rect_btn)
                if kind == 'digit':
                    if len(self._entered_code) < 8:
                        self._entered_code += value
                        self.update()
                elif kind == 'back':
                    if self._entered_code:
                        self._entered_code = self._entered_code[:-1]
                        self.update()
                    else:
                        # Nothing to erase — treat as "back" out of the keypad.
                        self._set_pending_action(None)
                elif kind == 'submit':
                    if self._entered_code:
                        self.action_requested.emit(self._pending_action, self._entered_code)
                        self._entered_code = ''
                        self._set_pending_action(None)
                return
            return

        if self._btn_disarm.contains(pos):
            self._trigger_press_anim(self._btn_disarm)
            self._request_action('disarm')
            return

        for rect_btn, action in self._mode_btns:
            if rect_btn.contains(pos):
                self._trigger_press_anim(rect_btn)
                self._request_action(action)
                return

    # ── Painting ──

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

        close_size      = 20
        self._btn_close = QRect(rect.width() - close_size - padding, padding, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(self._fg_color(int(alpha * 0.5)))
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

        is_triggered = self._state == 'triggered'
        header_color = QColor('#EA4335') if is_triggered else fg
        header_color.setAlpha(alpha)
        label_key   = self.STATE_LABEL_KEYS.get(self._state)
        state_label = t(label_key) if label_key else self._state.replace('_', ' ').capitalize()

        painter.setFont(QFont(SYSTEM_FONT, 13, QFont.Weight.Bold))
        painter.setPen(header_color)
        header_rect = QRectF(padding, padding, rect.width() - padding * 2 - close_size, 24)
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, state_label)

        content_top = padding + 24 + 10

        if self._pending_action:
            self._draw_keypad(painter, rect, alpha, content_top)
        elif self._state in self.ARMED_STATES:
            self._draw_disarm_button(painter, rect, alpha, content_top, is_triggered)
        else:
            self._draw_mode_buttons(painter, rect, alpha, content_top)

        painter.end()

    def _draw_disarm_button(self, painter, rect, alpha, top, is_triggered):
        padding  = 16
        btn_h    = 40
        btn_rect = QRect(padding, top, rect.width() - padding * 2, btn_h)
        self._btn_disarm = btn_rect
        self._mode_btns = []  # hit rects are only valid for the view that was just drawn

        scale = self._press_scale if btn_rect == self._press_rect else 1.0
        if scale != 1.0:
            c = btn_rect.center()
            painter.save()
            painter.translate(c.x(), c.y())
            painter.scale(scale, scale)
            painter.translate(-c.x(), -c.y())

        fill = QColor('#EA4335') if is_triggered else QColor(255, 255, 255, int(alpha * 0.14))
        if is_triggered:
            fill.setAlpha(alpha)
        path = QPainterPath()
        path.addRoundedRect(QRectF(btn_rect), OVERLAY_CORNER_RADIUS, OVERLAY_CORNER_RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPath(path)

        text_color = QColor(255, 255, 255, alpha) if is_triggered else self._fg_color(alpha)
        painter.setPen(text_color)
        painter.setFont(get_mdi_font(16))
        icon_x = btn_rect.center().x() - 60
        painter.drawText(QRectF(icon_x, btn_rect.y(), 20, btn_h),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, get_icon('shield-off-outline'))
        painter.setFont(QFont(SYSTEM_FONT, 12, QFont.Weight.DemiBold))
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, t("overlay.alarm.disarm_btn"))

        if scale != 1.0:
            painter.restore()

    def _draw_mode_buttons(self, painter, rect, alpha, top):
        padding = 16
        self._mode_btns = []
        self._btn_disarm = QRect()  # no Disarm button in this view

        modes = self._available_modes or ['arm_home', 'arm_away']
        gap     = 8
        btn_h   = 40
        avail_w = rect.width() - padding * 2
        n       = len(modes)
        btn_w   = (avail_w - (n - 1) * gap) / n if n else avail_w
        show_label = btn_w >= 64

        for i, action in enumerate(modes):
            icon_name, label_key = self.MODE_META[action]
            x = padding + i * (btn_w + gap)
            btn_rect = QRect(int(x), top, int(btn_w), btn_h)
            self._mode_btns.append((btn_rect, action))

            scale = self._press_scale if btn_rect == self._press_rect else 1.0
            if scale != 1.0:
                c = btn_rect.center()
                painter.save()
                painter.translate(c.x(), c.y())
                painter.scale(scale, scale)
                painter.translate(-c.x(), -c.y())

            path = QPainterPath()
            path.addRoundedRect(QRectF(btn_rect), 10, 10)
            painter.fillPath(path, QColor(255, 255, 255, int(alpha * 0.10)))
            painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.14)), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            painter.setPen(self._fg_color(alpha))
            if show_label:
                painter.setFont(get_mdi_font(16))
                icon_x = btn_rect.x() + 10
                painter.drawText(QRectF(icon_x, btn_rect.y(), 20, btn_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, get_icon(icon_name))
                painter.setFont(QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold))
                painter.drawText(QRectF(icon_x + 22, btn_rect.y(), btn_w - 34, btn_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, t(label_key))
            else:
                painter.setFont(get_mdi_font(18))
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, get_icon(icon_name))

            if scale != 1.0:
                painter.restore()

    def _draw_keypad(self, painter, rect, alpha, top):
        padding = 16
        self._mode_btns = []
        self._btn_disarm = QRect()

        action_label_key = 'overlay.alarm.enter_code_disarm' if self._pending_action == 'disarm' else 'overlay.alarm.enter_code_arm'
        painter.setFont(QFont(SYSTEM_FONT, 9, QFont.Weight.DemiBold))
        painter.setPen(self._fg_color(int(alpha * 0.5)))
        subtitle_rect = QRectF(padding, top, rect.width() - padding * 2, 16)
        painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t(action_label_key))

        dots_rect = QRectF(padding, top + 18, rect.width() - padding * 2, 22)
        painter.setFont(QFont(SYSTEM_FONT, 18, QFont.Weight.Bold))
        painter.setPen(self._fg_color(alpha))
        dots = "• " * len(self._entered_code)
        painter.drawText(dots_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, dots.strip())

        keys = [
            ('1', '1'), ('2', '2'), ('3', '3'),
            ('4', '4'), ('5', '5'), ('6', '6'),
            ('7', '7'), ('8', '8'), ('9', '9'),
            ('back', None), ('0', '0'), ('submit', None),
        ]
        cols    = 3
        rows    = 4
        gap     = 6
        grid_top = top + 46
        avail_w = rect.width() - padding * 2
        avail_h = rect.height() - grid_top - padding
        cell_w  = (avail_w - (cols - 1) * gap) / cols
        cell_h  = min((avail_h - (rows - 1) * gap) / rows, 32)

        self._keypad_btns = []
        for i, (key, digit) in enumerate(keys):
            col = i % cols
            row = i // cols
            x = padding + col * (cell_w + gap)
            y = grid_top + row * (cell_h + gap)
            btn_rect = QRect(int(x), int(y), int(cell_w), int(cell_h))

            if key == 'back':
                kind, value = 'back', None
            elif key == 'submit':
                kind, value = 'submit', None
            else:
                kind, value = 'digit', digit
            self._keypad_btns.append((btn_rect, kind, value))

            scale = self._press_scale if btn_rect == self._press_rect else 1.0
            if scale != 1.0:
                c = btn_rect.center()
                painter.save()
                painter.translate(c.x(), c.y())
                painter.scale(scale, scale)
                painter.translate(-c.x(), -c.y())

            path = QPainterPath()
            path.addRoundedRect(QRectF(btn_rect), 8, 8)
            if kind == 'submit':
                fill = QColor(52, 168, 83, int(alpha * 0.85))
            else:
                fill = QColor(255, 255, 255, int(alpha * 0.08))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawPath(path)

            if kind == 'digit':
                painter.setFont(QFont(SYSTEM_FONT, 13, QFont.Weight.Medium))
                painter.setPen(self._fg_color(alpha))
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, digit)
            else:
                painter.setFont(get_mdi_font(16))
                painter.setPen(QColor(255, 255, 255, alpha) if kind == 'submit' else self._fg_color(int(alpha * 0.7)))
                icon = get_icon('check-bold') if kind == 'submit' else get_icon('backspace-outline')
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, icon)

            if scale != 1.0:
                painter.restore()

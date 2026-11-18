"""Climate overlay: thermostat target, modes and fan speed."""

from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    pyqtProperty,
    QRect,
    QPoint,
    QPointF,
    QRectF,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath
from ui.icons import get_icon, get_mdi_font
from core.utils import SYSTEM_FONT
from core.localization_manager import t
from ui.widgets.dashboard_button_painter import DashboardButtonPainter
from ui.widgets.overlays.base import BaseOverlay


# ─────────────────────────────────────────────────────────────────────────────


class ClimateOverlay(BaseOverlay):
    """Overlay for climate control with +/- buttons."""
    value_changed = pyqtSignal(float)   # Temperature value
    mode_changed  = pyqtSignal(str)     # HVAC mode
    fan_changed   = pyqtSignal(str)     # Fan mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value      = 20.0
        self._text       = "Climate"
        self._color      = QColor("#EA4335")
        self._base_color = QColor("#2d2d2d")

        self._min_temp            = 5.0
        self._max_temp            = 35.0
        self._step                = 0.5
        self._display_temp_unit   = 'C'
        self._current_hvac_mode   = 'off'
        self._current_fan_mode    = 'auto'
        self._hvac_modes          = []
        self._fan_modes           = []

        self._btn_minus       = QRect()
        self._btn_plus        = QRect()
        self._btn_close       = QRect()
        self._btn_minus_click = QRect()
        self._btn_plus_click  = QRect()
        self._mode_btns       = []
        self._fan_btns        = []

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

    def configure_temperature_range(self, min_temp: float, max_temp: float, step: float, display_unit: str | None = None):
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._step = step if step and step > 0 else 0.5
        if display_unit:
            self._display_temp_unit = display_unit

    def update_state(self, current_state: dict):
        if not current_state:
            return
        self._current_hvac_mode = current_state.get('state', 'off')
        attrs = current_state.get('attributes', {})
        self._current_fan_mode = attrs.get('fan_mode', 'auto')
        if attrs.get('hvac_modes'):
            self._hvac_modes = attrs.get('hvac_modes')
        if attrs.get('fan_modes'):
            self._fan_modes = attrs.get('fan_modes')
        self.update()

    def start_morph(self, start_geo: QRect, target_geo: QRect, initial_value: float, text: str,
                    color: QColor = None, base_color: QColor = None, current_state: dict = None):
        self._hvac_modes = ['off', 'heat', 'cool', 'auto']
        self._fan_modes  = ['auto', 'low', 'medium', 'high']
        if current_state:
            self.update_state(current_state)
        self._value      = initial_value
        self._text       = text
        self._color      = color      or QColor("#EA4335")
        self._base_color = base_color or QColor("#2d2d2d")
        self._start_morph_animations(start_geo, target_geo)

    def adjust_temp(self, delta: float):
        new_val = max(self._min_temp, min(self._max_temp, self._value + delta))
        if new_val != self._value:
            self._value = new_val
            self.update()
            self.value_changed.emit(self._value)

    def mousePressEvent(self, event):
        pos = event.pos()
        if self._btn_close.contains(pos):
            self.close_morph()
        elif self._btn_minus_click.contains(pos):
            self.adjust_temp(-self._step)
        elif self._btn_plus_click.contains(pos):
            self.adjust_temp(self._step)
        for rect_btn, mode in self._mode_btns:
            if rect_btn.contains(pos):
                self._trigger_press_anim(rect_btn)
                self._current_hvac_mode = mode
                self.mode_changed.emit(mode)
                self.update()
                return
        for rect_btn, mode in self._fan_btns:
            if rect_btn.contains(pos):
                self._trigger_press_anim(rect_btn)
                self._current_fan_mode = mode
                self.fan_changed.emit(mode)
                self.update()
                return

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

        is_wide = rect.width() > 420
        if is_wide:
            self._draw_split_layout(painter, rect, alpha)
        else:
            self._draw_stacked_layout(painter, rect, alpha)

    def _draw_stacked_layout(self, painter, rect, alpha):
        close_size = 20
        self._btn_close = QRect(rect.width() - close_size - 12, 8, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(self._fg_color(int(alpha * 0.5)))
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

        title_rect = QRect(20, 8, rect.width() - 80, 20)
        font_title = QFont(SYSTEM_FONT, 8, QFont.Weight.Bold)
        font_title.setCapitalization(QFont.Capitalization.AllUppercase)
        painter.setFont(font_title)
        painter.setPen(self._fg_color(int(alpha * 0.4)))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)

        self._draw_control_pill(painter, rect.center().x(), 48, alpha, compact=True)

        if self._content_opacity > 0.01:
            self._draw_advanced_controls(painter, rect, int(alpha * self._content_opacity), start_y=78)

    def _draw_split_layout(self, painter, rect, alpha):
        close_size = 20
        self._btn_close = QRect(rect.width() - close_size - 12, 8, close_size, close_size)
        painter.setFont(get_mdi_font(18))
        painter.setPen(self._fg_color(int(alpha * 0.5)))
        painter.drawText(self._btn_close, Qt.AlignmentFlag.AlignCenter, get_icon('close'))

        title_rect = QRect(20, 8, rect.width() - 80, 20)
        font_title = QFont(SYSTEM_FONT, 8, QFont.Weight.Bold)
        font_title.setCapitalization(QFont.Capitalization.AllUppercase)
        painter.setFont(font_title)
        painter.setPen(self._fg_color(int(alpha * 0.4)))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._text)

        mid_x = int(rect.width() * 0.40)
        painter.setPen(QPen(self._fg_color(int(alpha * 0.1)), 1))
        painter.drawLine(mid_x, 20, mid_x, rect.height() - 20)

        self._draw_control_pill(painter, mid_x // 2, rect.height() // 2 + 5, alpha)

        if self._content_opacity > 0.01:
            right_rect = QRect(mid_x, 0, rect.width() - mid_x, rect.height())
            self._draw_advanced_controls_split(painter, right_rect, int(alpha * self._content_opacity))

    def _draw_control_pill(self, painter, cx, cy, alpha, compact=False):
        btn_radius = 10 if compact else 13
        spacing    = 12 if compact else 16

        font_val = QFont(SYSTEM_FONT, 13 if compact else 16, QFont.Weight.Light)
        painter.setFont(font_val)
        fm = painter.fontMetrics()
        val_str = f"{self._value:.1f}".replace('.0', '')
        val_str = f"{val_str}°{self._display_temp_unit}"
        text_w  = fm.horizontalAdvance(val_str)

        inner_w  = btn_radius * 2 + spacing + text_w + 10 + spacing + btn_radius * 2
        pill_h   = 36 if compact else 46
        pill_rect = QRect(0, 0, inner_w + 24, pill_h)
        pill_rect.moveCenter(QPoint(cx, cy))

        pill_path = QPainterPath()
        pill_path.addRoundedRect(QRectF(pill_rect), pill_h // 2, pill_h // 2)
        painter.fillPath(pill_path, QColor(0, 0, 0, int(alpha * 0.18)))
        painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.12)), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(pill_rect), pill_h // 2, pill_h // 2)

        text_left  = cx - text_w // 2
        text_right = cx + text_w // 2

        btn_x_minus = text_left - spacing - btn_radius
        self._btn_minus_click = QRect(btn_x_minus - btn_radius, cy - btn_radius, btn_radius * 2, btn_radius * 2)
        btn_x_plus  = text_right + spacing + btn_radius
        self._btn_plus_click  = QRect(btn_x_plus - btn_radius, cy - btn_radius, btn_radius * 2, btn_radius * 2)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(66, 133, 244, int(alpha * 0.85)))
        painter.drawEllipse(QPoint(btn_x_minus, cy), btn_radius, btn_radius)

        painter.setBrush(QColor(234, 67, 53, int(alpha * 0.85)))
        painter.drawEllipse(QPoint(btn_x_plus, cy), btn_radius, btn_radius)

        painter.setFont(get_mdi_font(16))
        painter.setPen(QColor(255, 255, 255, alpha))
        painter.drawText(self._btn_minus_click, Qt.AlignmentFlag.AlignCenter, get_icon('minus'))
        painter.drawText(self._btn_plus_click,  Qt.AlignmentFlag.AlignCenter, get_icon('plus'))

        # Baseline position so text is visually centered at cy
        baseline_y = cy + (fm.ascent() - fm.descent()) / 2.0
        painter.setFont(font_val)
        painter.setPen(self._fg_color(alpha))
        painter.drawText(QPointF(text_left, baseline_y), val_str)

    def _draw_icon_pill(self, painter, btn_rect, is_active, alpha):
        path = QPainterPath()
        path.addRoundedRect(QRectF(btn_rect), 10, 10)
        if is_active:
            painter.fillPath(path, QColor(255, 255, 255, int(alpha * 0.14)))
            painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.22)), 1))
        else:
            painter.fillPath(path, QColor(255, 255, 255, int(alpha * 0.06)))
            painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.08)), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(btn_rect), 10, 10)

    def _draw_advanced_controls_split(self, painter, rect, alpha):
        self._mode_btns = []
        self._fan_btns  = []

        modes     = self._hvac_modes or ['off', 'heat', 'cool']
        fan_modes = self._fan_modes  or ['auto', 'low', 'high']

        margin_left = 20
        y_mode    = 45
        icon_size = 36
        spacing   = 16
        y_fan     = y_mode + icon_size + 30

        painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        painter.setPen(self._fg_color(int(alpha * 0.4)))
        painter.drawText(QRect(rect.left() + margin_left, y_mode - 25, 60, 20),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t("overlay.climate.mode_label"))

        start_x = rect.left() + margin_left
        mode_icons = {
            'cool': 'snowflake', 'heat': 'fire', 'off': 'power',
            'auto': 'thermostat-auto', 'dry': 'water-percent',
            'fan_only': 'fan', 'heat_cool': 'sun-snowflake-variant'
        }

        painter.setFont(get_mdi_font(22))
        for i, mode in enumerate(modes):
            x = start_x + (i * (icon_size + spacing))
            if x + icon_size > rect.right() - 10:
                break
            btn_rect = QRect(x, y_mode, icon_size, icon_size)
            self._mode_btns.append((btn_rect, mode))
            is_active = (mode == self._current_hvac_mode)
            scale = self._press_scale if btn_rect == self._press_rect else 1.0
            if scale != 1.0:
                c = btn_rect.center()
                painter.save()
                painter.translate(c.x(), c.y())
                painter.scale(scale, scale)
                painter.translate(-c.x(), -c.y())
            self._draw_icon_pill(painter, btn_rect, is_active, alpha)
            painter.setPen(self._fg_color(alpha if is_active else int(alpha * 0.4)))
            painter.setFont(get_mdi_font(22))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, get_icon(mode_icons.get(mode, 'help-circle-outline')))
            if scale != 1.0:
                painter.restore()

        painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        painter.setPen(self._fg_color(int(alpha * 0.4)))
        painter.drawText(QRect(rect.left() + margin_left, y_fan - 25, 60, 20),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t("overlay.climate.fan_label"))

        fan_map = {'low': '1', 'medium': '2', 'high': '3', 'mid': '2', 'min': '1', 'max': 'Max'}

        for i, mode in enumerate(fan_modes):
            x = start_x + (i * (icon_size + spacing))
            if x + icon_size > rect.right() - 10:
                break
            btn_rect = QRect(x, y_fan, icon_size, icon_size)
            self._fan_btns.append((btn_rect, mode))
            is_active = (mode == self._current_fan_mode)
            scale = self._press_scale if btn_rect == self._press_rect else 1.0
            if scale != 1.0:
                c = btn_rect.center()
                painter.save()
                painter.translate(c.x(), c.y())
                painter.scale(scale, scale)
                painter.translate(-c.x(), -c.y())
            self._draw_icon_pill(painter, btn_rect, is_active, alpha)
            painter.setPen(self._fg_color(alpha if is_active else int(alpha * 0.4)))
            mode_lower = mode.lower()
            if mode_lower == 'auto':
                painter.setFont(get_mdi_font(22))
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, get_icon('fan-auto'))
            else:
                painter.setFont(QFont(SYSTEM_FONT, 11, QFont.Weight.Bold))
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter,
                                 fan_map.get(mode_lower, mode_lower.capitalize()[:1]))
            if scale != 1.0:
                painter.restore()

    def _draw_advanced_controls(self, painter, rect, alpha, start_y=78):
        self._mode_btns = []
        self._fan_btns  = []

        modes     = self._hvac_modes or ['off', 'heat', 'cool']
        fan_modes = self._fan_modes  or ['auto', 'low', 'high']

        mode_icons = {
            'cool': 'snowflake', 'heat': 'fire', 'off': 'power',
            'auto': 'thermostat-auto', 'dry': 'water-percent',
            'fan_only': 'fan', 'heat_cool': 'sun-snowflake-variant'
        }

        icon_size   = 32
        spacing     = 12
        y_pos_1     = start_y
        label_width = 80
        avail_width = rect.width() - label_width - 20

        painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        painter.setPen(self._fg_color(int(alpha * 0.4)))
        painter.drawText(QRect(20, y_pos_1, 60, icon_size),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t("overlay.climate.mode_label"))

        total_items     = len(modes)
        total_icon_width = (total_items * icon_size) + ((total_items - 1) * spacing)

        if total_icon_width > avail_width:
            spacing = (avail_width - (total_items * icon_size)) / (total_items - 1) if total_items > 1 else 0
            start_x = label_width
        else:
            start_x = label_width + (avail_width - total_icon_width) / 2

        painter.setFont(get_mdi_font(20))
        for i, mode in enumerate(modes):
            x = int(start_x + (i * (icon_size + spacing)))
            btn_rect = QRect(x, y_pos_1, icon_size, icon_size)
            self._mode_btns.append((btn_rect, mode))
            is_active = (mode == self._current_hvac_mode)
            scale = self._press_scale if btn_rect == self._press_rect else 1.0
            if scale != 1.0:
                c = btn_rect.center()
                painter.save()
                painter.translate(c.x(), c.y())
                painter.scale(scale, scale)
                painter.translate(-c.x(), -c.y())
            self._draw_icon_pill(painter, btn_rect, is_active, alpha)
            painter.setPen(self._fg_color(alpha if is_active else int(alpha * 0.5)))
            painter.setFont(get_mdi_font(20))
            painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter,
                             get_icon(mode_icons.get(mode, 'help-circle-outline')))
            if scale != 1.0:
                painter.restore()

        y_pos_2 = y_pos_1 + icon_size + 12
        fan_map = {'low': '1', 'medium': '2', 'high': '3', 'mid': '2', 'middle': '2', 'min': '1', 'max': 'Max'}

        painter.setFont(QFont(SYSTEM_FONT, 8, QFont.Weight.Bold))
        painter.setPen(self._fg_color(int(alpha * 0.4)))
        painter.drawText(QRect(20, y_pos_2, 60, icon_size),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, t("overlay.climate.fan_label"))

        total_items      = len(fan_modes)
        total_icon_width = (total_items * icon_size) + ((total_items - 1) * spacing)

        if total_icon_width > avail_width:
            spacing_fan = (avail_width - (total_items * icon_size)) / (total_items - 1) if total_items > 1 else 0
            start_x = label_width
        else:
            spacing_fan = spacing
            start_x = label_width + (avail_width - total_icon_width) / 2

        for i, mode in enumerate(fan_modes):
            x = int(start_x + (i * (icon_size + spacing_fan)))
            btn_rect = QRect(x, y_pos_2, icon_size, icon_size)
            self._fan_btns.append((btn_rect, mode))
            is_active = (mode == self._current_fan_mode)
            scale = self._press_scale if btn_rect == self._press_rect else 1.0
            if scale != 1.0:
                c = btn_rect.center()
                painter.save()
                painter.translate(c.x(), c.y())
                painter.scale(scale, scale)
                painter.translate(-c.x(), -c.y())
            self._draw_icon_pill(painter, btn_rect, is_active, alpha)
            painter.setPen(self._fg_color(alpha if is_active else int(alpha * 0.5)))
            mode_lower = mode.lower()
            if mode_lower == 'auto':
                painter.setFont(get_mdi_font(20))
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, get_icon('fan-auto'))
            else:
                text = fan_map.get(mode_lower)
                if not text:
                    text = mode_lower.capitalize() if len(mode) > 3 else mode.upper()
                painter.setFont(QFont(SYSTEM_FONT, 12, QFont.Weight.DemiBold))
                painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, text)
            if scale != 1.0:
                painter.restore()

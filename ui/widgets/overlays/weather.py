"""Weather overlay: daily forecast."""

from PyQt6.QtCore import Qt, QRect, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from ui.icons import get_icon, get_mdi_font, Icons
from core.utils import SYSTEM_FONT
from core.temperature_utils import format_temperature
from ui.widgets.dashboard_button_painter import DashboardButtonPainter
from ui.widgets.overlays.base import BaseOverlay


# ─────────────────────────────────────────────────────────────────────────────


class WeatherOverlay(BaseOverlay):
    """Overlay for weather forecasts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text       = "Weather"
        self._color      = QColor("#4285F4")
        self._base_color = QColor("#2d2d2d")

        self._current_state               = {}
        self._forecasts                   = []
        self._temperature_unit_preference = "celsius"
        self._btn_close                   = QRect()

    def update_state(self, current_state: dict):
        if not current_state:
            return
        self._current_state = current_state
        self.update()

    def set_temperature_unit_preference(self, preference: str):
        self._temperature_unit_preference = preference
        self.update()

    def start_morph(self, start_geo: QRect, target_geo: QRect, current_state: dict, forecasts: list,
                    text: str, color: QColor = None, base_color: QColor = None):
        self.update_state(current_state)
        self._forecasts  = forecasts or []
        self._text       = text
        self._color      = color      or QColor("#4285F4")
        self._base_color = base_color or QColor("#2d2d2d")
        self._start_morph_animations(start_geo, target_geo)

    def mousePressEvent(self, event):
        if self._btn_close.contains(event.pos()):
            self.close_morph()

    def _get_weather_emoji(self, state: str) -> str:
        import sys
        if sys.platform.startswith('linux'):
            mapping = {
                'clear-night': Icons.WEATHER_NIGHT, 'cloudy': Icons.WEATHER_CLOUDY,
                'fog': Icons.WEATHER_FOG, 'hail': Icons.WEATHER_HAIL,
                'lightning': Icons.WEATHER_LIGHTNING, 'lightning-rainy': Icons.WEATHER_LIGHTNING_RAINY,
                'partlycloudy': Icons.WEATHER_PARTLY_CLOUDY, 'pouring': Icons.WEATHER_POURING,
                'rainy': Icons.WEATHER_RAINY, 'snowy': Icons.WEATHER_SNOWY,
                'snowy-rainy': Icons.WEATHER_SNOWY_RAINY, 'sunny': Icons.WEATHER_SUNNY,
                'windy': Icons.WEATHER_WINDY, 'windy-variant': Icons.WEATHER_WINDY_VARIANT,
                'exceptional': Icons.ALERT_CIRCLE
            }
            return mapping.get(state, Icons.WEATHER_CLOUDY)
        else:
            mapping = {
                'clear-night': '🌙', 'cloudy': '☁️', 'fog': '🌫️',
                'hail': '🌨️', 'lightning': '🌩️', 'lightning-rainy': '⛈️',
                'partlycloudy': '⛅', 'pouring': '🌧️', 'rainy': '🌧️',
                'snowy': '❄️', 'snowy-rainy': '🌨️', 'sunny': '☀️',
                'windy': '💨', 'windy-variant': '🌬️', 'exceptional': '⚠️'
            }
            return mapping.get(state, 'Unknown')

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

        import sys
        is_linux = sys.platform.startswith('linux')

        close_size      = 20
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

        mid_x = int(rect.width() * 0.3)
        painter.setPen(QPen(self._fg_color(int(alpha * 0.1)), 1))
        painter.drawLine(mid_x, 20, mid_x, rect.height() - 20)

        current_st  = self._current_state.get('state', 'unknown')
        attrs       = self._current_state.get('attributes', {})
        temp        = attrs.get('temperature', '--')
        emoji       = self._get_weather_emoji(current_st)
        source_unit = attrs.get('temperature_unit')
        temp_str    = format_temperature(temp, source_unit, self._temperature_unit_preference, precision=1)

        if is_linux:
            painter.setFont(get_mdi_font(36))
        else:
            painter.setFont(QFont(SYSTEM_FONT, 32))
        painter.setPen(self._fg_color(alpha))

        fm     = painter.fontMetrics()
        icon_h = fm.height()
        painter.drawText(QRect(0, rect.height() // 2 - icon_h // 2 - 12, mid_x, icon_h), Qt.AlignmentFlag.AlignCenter, emoji)

        painter.setFont(QFont(SYSTEM_FONT, 14, QFont.Weight.DemiBold))
        painter.drawText(QRect(0, rect.height() // 2 + 18, mid_x, 30), Qt.AlignmentFlag.AlignCenter, temp_str)

        right_rect     = QRect(mid_x, 0, rect.width() - mid_x, rect.height())
        forecast_count = len(self._forecasts)

        if forecast_count > 0:
            item_w        = 65
            avail_w       = right_rect.width() - 20
            max_items     = avail_w // item_w
            display_count = min(forecast_count, max_items)
            start_x       = right_rect.left() + (avail_w - (display_count * item_w)) // 2 + 10

            for i in range(display_count):
                f   = self._forecasts[i]
                fx  = start_x + (i * item_w)
                fy  = rect.height() // 2 - 35
                dt_str = f.get('datetime', '')
                try:
                    from datetime import datetime
                    day_str = datetime.fromisoformat(dt_str).strftime("%a")
                except (TypeError, ValueError):
                    day_str = "-"

                f_emoji = self._get_weather_emoji(f.get('condition', 'unknown'))
                high    = format_temperature(f.get('temperature', '--'), source_unit, self._temperature_unit_preference, precision=1)
                low     = format_temperature(f.get('templow', '--'),     source_unit, self._temperature_unit_preference, precision=1, fallback='--')

                painter.setFont(QFont(SYSTEM_FONT, 9, QFont.Weight.DemiBold))
                painter.setPen(self._fg_color(int(alpha * 0.6)))
                painter.drawText(QRect(fx, fy, item_w, 15), Qt.AlignmentFlag.AlignCenter, day_str.upper())

                if is_linux:
                    painter.setFont(get_mdi_font(20))
                else:
                    painter.setFont(QFont(SYSTEM_FONT, 16))
                painter.setPen(self._fg_color(alpha))
                painter.drawText(QRect(fx, fy + 18, item_w, 30), Qt.AlignmentFlag.AlignCenter, f_emoji)

                painter.setFont(QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold))
                painter.setPen(self._fg_color(int(alpha * 0.95)))
                painter.drawText(QRect(fx, fy + 50, item_w, 16), Qt.AlignmentFlag.AlignCenter, high)

                if not str(low).startswith('--'):
                    painter.setFont(QFont(SYSTEM_FONT, 9, QFont.Weight.Medium))
                    painter.setPen(self._fg_color(int(alpha * 0.4)))
                    painter.drawText(QRect(fx, fy + 68, item_w, 16), Qt.AlignmentFlag.AlignCenter, low)

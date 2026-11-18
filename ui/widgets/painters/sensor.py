"""Painting for sensor widget tiles (value, gauge, bar and ring styles)."""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath
from core.utils import SYSTEM_FONT
from ui.widgets.painters.shapes import ShapePainter

_DEFAULT_SENSOR_COLOR = '#3c3c3c'


class SensorPainter:
    """Painting for sensor widget tiles (value, gauge, bar and ring styles)."""

    @staticmethod
    def _paint_widget_sensor(button):
        style = button.config.get('display_style')
        if style not in ('gauge', 'bar', 'perimeter'):
            return

        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = button.rect()

        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), 12, 12)
        painter.setClipPath(clip_path)

        # Resolve colors
        accent_hex = '#4285F4'
        text_hex = '#ffffff'
        if button.theme_manager:
            colors = button.theme_manager.get_colors()
            accent_hex = colors.get('accent', accent_hex)
            text_hex = colors.get('text', text_hex)

        # User-picked color (from edit menu) drives the gauge/bar fill; fall back to theme accent.
        custom_color = button.config.get('color')
        # "#3c3c3c" is the sentinel for "default sensor color" — treat as unset.
        if custom_color and custom_color.lower() != _DEFAULT_SENSOR_COLOR:
            fill_color = QColor(custom_color)
        else:
            fill_color = QColor(accent_hex)
        text_color = QColor(text_hex)
        track_color = QColor(text_hex)
        track_color.setAlpha(40)

        fraction = getattr(button, '_sensor_fraction', None)
        gauge_fraction = getattr(button, '_gauge_fraction', fraction)
        text = getattr(button, '_sensor_text', '') or ''

        has_label = bool(button.config.get('label'))
        label_reserve = 24 if has_label else 0

        if style == 'bar':
            # Upper area holds the pill; lower area (if label exists) is left for the QLabel.
            top_pad = 8
            available_h = rect.height() - label_reserve - top_pad
            pill_h = int(max(12, min(available_h * 0.60, 24)))
            margin_x = 18
            pill_y = rect.y() + top_pad + (available_h - pill_h) / 2
            pill_rect = QRectF(
                rect.x() + margin_x,
                pill_y,
                rect.width() - 2 * margin_x,
                pill_h,
            )
            is_1x1 = button.span_x == 1 and button.span_y == 1
            font_size = max(6, min(9, int(pill_h * 0.4))) if is_1x1 else max(7, min(12, int(pill_h * 0.5)))
            ShapePainter.draw_horizontal_bar_pill(
                painter,
                pill_rect,
                fraction=fraction,
                fill_color=fill_color,
                track_color=track_color,
                text=text,
                font=QFont(SYSTEM_FONT, font_size, QFont.Weight.Bold if is_1x1 else QFont.Weight.Normal),
                text_color=text_color,
            )
        elif style == 'gauge':
            is_1x1 = button.span_x == 1 and button.span_y == 1
            is_tall_1col = button.span_x == 1 and button.span_y >= 2
            if is_tall_1col:
                # Tall single-column: arc centered in upper half, value + label below.
                label_text = button.config.get('label', '')
                top_pad = 16
                arc_size = int(min(rect.width() - 16, (rect.height() * 0.55)))
                arc_x = rect.x() + (rect.width() - arc_size) / 2
                arc_y = rect.y() + top_pad
                arc_rect = QRectF(arc_x, arc_y, arc_size, arc_size)
                ShapePainter.draw_gauge_arc(
                    painter, arc_rect, fraction=gauge_fraction,
                    fill_color=fill_color, track_color=track_color,
                )
                baseline_y = arc_y + arc_size / 2
                remaining_h = rect.y() + rect.height() - baseline_y
                value_h = remaining_h * 0.5 if label_text else remaining_h
                value_rect = QRectF(rect.x(), baseline_y, rect.width(), value_h)
                painter.setPen(text_color)
                painter.setFont(QFont(SYSTEM_FONT, 13, QFont.Weight.Bold))
                painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, text)
                if label_text:
                    label_rect = QRectF(rect.x(), baseline_y + value_h, rect.width(), remaining_h * 0.5)
                    label_color = QColor(text_color)
                    label_color.setAlpha(160)
                    painter.setPen(label_color)
                    painter.setFont(QFont(SYSTEM_FONT, 9, QFont.Weight.DemiBold))
                    painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label_text.upper())
            elif is_1x1:
                # 1x1 gauge: arc fills upper portion; value text drawn below the arc.
                value_strip_h = 20
                max_arc_w = int((rect.width() - 8) * 0.72)
                arc_size = max(min(max_arc_w, int((rect.width() - 8) * 0.72)), 24)
                # Center the arc+text block vertically with the arc sitting just above mid
                content_h = arc_size // 2 + value_strip_h + 4
                top_pad = max(6, (rect.height() - content_h) // 2)
                arc_x = rect.x() + (rect.width() - arc_size) / 2
                arc_y = rect.y() + top_pad
                arc_rect = QRectF(arc_x, arc_y, arc_size, arc_size)
                ShapePainter.draw_gauge_arc(
                    painter,
                    arc_rect,
                    fraction=gauge_fraction,
                    fill_color=fill_color,
                    track_color=track_color,
                )
                # Value text right under the arc's flat baseline (= vertical center of arc_rect).
                baseline_y = arc_y + arc_size / 2
                text_rect = QRectF(
                    rect.x(),
                    baseline_y,
                    rect.width(),
                    rect.y() + rect.height() - baseline_y,
                )
                painter.setPen(text_color)
                painter.setFont(QFont(SYSTEM_FONT, 11))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)
            else:
                # 2x1+: arc on the left, QLabels on the right. Position arc_rect so that
                # the VISIBLE arc (top half of arc_rect) is vertically centered in the button.
                arc_size = min(rect.height() - 12, rect.width() // 2 - 10)
                arc_size = max(arc_size, 32)
                arc_x = rect.x() + 13
                # Visible arc spans [arc_y, arc_y + arc_size/2]; center its midpoint on rect center.
                arc_y = rect.y() + rect.height() / 2 - arc_size / 4
                arc_rect = QRectF(arc_x, arc_y, arc_size, arc_size)
                ShapePainter.draw_gauge_arc(
                    painter,
                    arc_rect,
                    fraction=gauge_fraction,
                    fill_color=fill_color,
                    track_color=track_color,
                )

        if style == 'perimeter':
            ShapePainter.draw_perimeter_progress(
                painter,
                QRectF(rect),
                fraction=getattr(button, '_perimeter_fraction', fraction),
                fill_color=fill_color,
                track_color=track_color,
            )

        painter.end()

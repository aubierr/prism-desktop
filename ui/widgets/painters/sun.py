"""Painting for sun tiles (sun and moon arc, time to next sunrise or sunset)."""

import math
from datetime import datetime, timezone, timedelta
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QBrush
from core.utils import SYSTEM_FONT
from core.localization_manager import t


class SunPainter:
    """Painting for sun tiles (sun and moon arc, time to next sunrise or sunset)."""

    @staticmethod
    def _draw_sun_button(button):
        """Draw the sun entity as a gauge arc (sensor-style) with the sun/moon travelling along it."""

        def parse_iso(s):
            return datetime.fromisoformat(s.replace('Z', '+00:00'))

        def format_remaining(total_secs):
            days  = total_secs // 86400
            hours = (total_secs % 86400) // 3600
            mins  = (total_secs % 3600) // 60
            if days >= 1:
                return f"{int(days)}d"
            if hours >= 1:
                return f"{int(hours)}h"
            return f"{int(mins)}m"

        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(button.rect())
        w = rect.width()
        h = rect.height()

        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)
        painter.setClipPath(clip_path)

        # Colors
        is_light = (getattr(button, 'theme_manager', None) and
                    button.theme_manager.get_effective_theme() == 'light')
        track_color = QColor(0, 0, 0, 80)  if is_light else QColor(255, 255, 255, 65)
        text_hex = '#1e1e1e' if is_light else '#ffffff'
        if getattr(button, 'theme_manager', None):
            colors = button.theme_manager.get_colors()
            text_hex = colors.get('text', text_hex)
        text_color = QColor(text_hex)

        # State
        above            = (getattr(button, 'sun_state', 'unknown') == 'above_horizon')
        next_rising_str  = getattr(button, 'sun_next_rising', None)
        next_setting_str = getattr(button, 'sun_next_setting', None)

        # Sun ratio: 0 = sunrise, 1 = sunset
        ratio = None
        if above and next_rising_str and next_setting_str:
            try:
                now          = datetime.now(timezone.utc)
                next_rising  = parse_iso(next_rising_str)
                next_setting = parse_iso(next_setting_str)
                sunrise      = next_rising - timedelta(days=1)
                total_secs   = (next_setting - sunrise).total_seconds()
                elapsed      = (now - sunrise).total_seconds()
                ratio = max(0.0, min(1.0, elapsed / total_secs)) if total_secs > 0 else 0.5
            except (AttributeError, TypeError, ValueError):  # missing or malformed timestamps
                ratio = 0.5

        # Moon ratio: 0 = prev sunset, 1 = next sunrise
        moon_ratio = None
        if not above and next_rising_str and next_setting_str:
            try:
                now          = datetime.now(timezone.utc)
                next_rising  = parse_iso(next_rising_str)
                next_setting = parse_iso(next_setting_str)
                prev_sunset  = next_setting - timedelta(days=1)
                night_dur    = (next_rising - prev_sunset).total_seconds()
                elapsed      = (now - prev_sunset).total_seconds()
                moon_ratio = max(0.0, min(1.0, elapsed / night_dur)) if night_dur > 0 else 0.5
            except (AttributeError, TypeError, ValueError):  # missing or malformed timestamps
                moon_ratio = 0.5

        # Layout — mirrors sensor gauge positioning
        is_wide = button.span_x >= 2
        is_1x1  = button.span_x == 1 and button.span_y == 1

        if is_wide:
            arc_size = int(min(h - 12, w // 2 - 10))
            arc_size = max(arc_size, 32)
            arc_x    = rect.x() + 13
            arc_y    = rect.y() + h / 2 - arc_size / 4
        elif is_1x1:
            arc_size = int((w - 8) * 0.72)
            arc_size = max(arc_size, 24)
            content_h = arc_size // 2 + 24
            top_pad  = max(6, int((h - content_h) // 2))
            arc_x    = rect.x() + (w - arc_size) / 2
            arc_y    = rect.y() + top_pad
        else:
            # tall single column
            arc_size = int(min(w - 16, h * 0.45))
            arc_size = max(arc_size, 32)
            arc_x    = rect.x() + (w - arc_size) / 2
            arc_y    = rect.y() + 12

        # Draw track arc (top semicircle, unfilled — sun/moon travel along it)
        thickness = max(6.0, arc_size / 10.0)
        inset     = thickness / 2.0
        draw_rect = QRectF(arc_x, arc_y, arc_size, arc_size).adjusted(inset, inset, -inset, -inset)

        pen_track = QPen(track_color, thickness)
        pen_track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_track)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(draw_rect, 0, 180 * 16)

        # Point on the arc: r=0 → left/sunrise, r=0.5 → top/noon, r=1 → right/sunset
        def arc_point(r):
            cx = draw_rect.center().x()
            cy = draw_rect.center().y()
            rx = draw_rect.width() / 2
            ry = draw_rect.height() / 2
            theta = math.radians(180.0 - r * 180.0)
            return cx + rx * math.cos(theta), cy - ry * math.sin(theta)

        phase = getattr(button, 'sun_pulse_phase', 0.0)
        pulse = (1.0 + math.sin(phase * 2.0 * math.pi)) / 2.0
        entry = getattr(button, '_sun_entry_fraction', 1.0)

        # Sun dot travelling along the arc
        if above and ratio is not None:
            animated_ratio = ratio * entry
            dot_x, dot_y = arc_point(animated_ratio)
            sin_t     = math.sin(animated_ratio * math.pi)
            dot_color = QColor(255, int(100 + 115 * sin_t), int(20 * (1.0 - sin_t)))
            base_r    = 5.0 + 2.0 * sin_t
            glow_c    = QColor(dot_color)
            glow_c.setAlpha(int(22 + 14 * pulse))
            painter.setBrush(QBrush(glow_c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(dot_x, dot_y), base_r + 2.5 + 1.0 * pulse, base_r + 2.5 + 1.0 * pulse)
            painter.setBrush(QBrush(dot_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(dot_x, dot_y), base_r, base_r)

        # Moon sphere travelling along the arc
        if not above and moon_ratio is not None:
            animated_moon = moon_ratio * entry
            moon_x, moon_y = arc_point(animated_moon)
            moon_r = 5.0
            glow_c = QColor(200, 210, 230, int(15 + 15 * pulse))
            painter.setBrush(QBrush(glow_c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(moon_x, moon_y), moon_r + 2.5, moon_r + 2.5)
            sphere_path = QPainterPath()
            sphere_path.addEllipse(QPointF(moon_x, moon_y), moon_r, moon_r)
            painter.setBrush(QBrush(QColor(215, 215, 220)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(sphere_path)

        # Time remaining text
        try:
            now = datetime.now(timezone.utc)
            if above and next_setting_str:
                secs = int((parse_iso(next_setting_str) - now).total_seconds())
                time_str = format_remaining(secs) if secs > 0 else None
            elif not above and next_rising_str:
                secs = int((parse_iso(next_rising_str) - now).total_seconds())
                time_str = format_remaining(secs) if secs > 0 else None
            else:
                time_str = None
        except (AttributeError, TypeError, ValueError):  # missing or malformed timestamps
            time_str = None

        if time_str:
            if is_wide:
                context_str = t("sun.until_sunset") if above else t("sun.until_sunrise")
                ctx_color = QColor(text_color)
                ctx_color.setAlphaF(text_color.alphaF() * 0.55)

                text_x  = arc_x + arc_size + 4
                right_w = w - (text_x - rect.x())

                time_font = QFont(SYSTEM_FONT, 15, QFont.Weight.Medium)
                ctx_font  = QFont(SYSTEM_FONT, 8)
                time_h = QFontMetrics(time_font).height()
                ctx_h  = QFontMetrics(ctx_font).height()
                gap    = 3
                block_y = rect.y() + (h - time_h - gap - ctx_h) / 2

                painter.setFont(time_font)
                painter.setPen(text_color)
                painter.drawText(QRectF(text_x, block_y, right_w, time_h),
                                 Qt.AlignmentFlag.AlignCenter, time_str)

                painter.setFont(ctx_font)
                painter.setPen(ctx_color)
                painter.drawText(QRectF(text_x, block_y + time_h + gap, right_w, ctx_h),
                                 Qt.AlignmentFlag.AlignCenter, context_str)
            else:
                # Below the arc (1x1 only — no context label, space is too tight)
                baseline_y = arc_y + arc_size / 2
                bottom_rect = QRectF(rect.x(), baseline_y + 2, w, rect.y() + h - baseline_y - 2)
                painter.setFont(QFont(SYSTEM_FONT, 11))
                painter.setPen(text_color)
                painter.drawText(bottom_rect, Qt.AlignmentFlag.AlignCenter, time_str)

        painter.end()

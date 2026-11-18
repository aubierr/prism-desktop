"""Reusable shapes for tiles: bars, gauges, perimeter progress and pill labels."""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush, QLinearGradient
from core.utils import SYSTEM_FONT


class ShapePainter:
    """Reusable shapes for tiles: bars, gauges, perimeter progress and pill labels."""

    @staticmethod
    def draw_bottom_bar(painter, rect, value, max_value, color, bar_height=4):
        """Draw a horizontal fill bar at the bottom of a rect.

        Reusable across entity types (3D printer progress, mower battery, etc.).

        Args:
            painter: Active QPainter instance.
            rect: QRectF or QRect bounding the area.
            value: Current fill value (e.g. progress or battery level).
            max_value: Value that represents 100 % fill.
            color: QColor for the filled portion.
            bar_height: Pixel height of the bar (default 4).
        """
        if value <= 0 or max_value <= 0:
            return
        fraction = min(float(value) / float(max_value), 1.0)
        bar_y = rect.y() + rect.height() - bar_height
        fill_w = rect.width() * fraction
        painter.fillRect(QRectF(rect.x(), bar_y, fill_w, bar_height), color)

    @staticmethod
    def draw_horizontal_bar_pill(painter, rect, fraction, fill_color, track_color,
                                 text=None, font=None, text_color=None):
        pill_rect = QRectF(rect)
        radius = pill_rect.height() / 2.0

        pill_path = QPainterPath()
        pill_path.addRoundedRect(pill_rect, radius, radius)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawPath(pill_path)

        if fraction is not None:
            frac = max(0.0, min(1.0, float(fraction)))
            if frac > 0:
                fill_w = pill_rect.width() * frac
                fill_rect = QRectF(pill_rect.x(), pill_rect.y(), fill_w, pill_rect.height())
                grad = QLinearGradient(0, fill_rect.bottom(), 0, fill_rect.top())
                grad.setColorAt(0.0, fill_color)
                lighter = QColor(fill_color)
                lighter.setHsvF(lighter.hsvHueF(), max(0.0, lighter.hsvSaturationF() - 0.05), min(1.0, lighter.valueF() + 0.12))
                grad.setColorAt(1.0, lighter)
                painter.setClipPath(pill_path)
                painter.setBrush(QBrush(grad))
                painter.drawRect(fill_rect)
                painter.setClipping(False)

        if text:
            painter.setPen(text_color)
            painter.setFont(font)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, text)

    @staticmethod
    def _perimeter_path(rect, corner_r):
        """Clockwise rounded-rect path starting at top-center (12 o'clock)."""
        l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
        cx = (l + r) / 2.0
        cr = corner_r
        path = QPainterPath()
        path.moveTo(cx, t)
        path.lineTo(r - cr, t)
        path.arcTo(r - 2*cr, t, 2*cr, 2*cr, 90, -90)
        path.lineTo(r, b - cr)
        path.arcTo(r - 2*cr, b - 2*cr, 2*cr, 2*cr, 0, -90)
        path.lineTo(l + cr, b)
        path.arcTo(l, b - 2*cr, 2*cr, 2*cr, 270, -90)
        path.lineTo(l, t + cr)
        path.arcTo(l, t, 2*cr, 2*cr, 180, -90)
        path.lineTo(cx, t)
        return path

    @staticmethod
    def draw_perimeter_progress(painter, rect, fraction, fill_color, track_color, thickness=3, offset=8):
        """Draw a progress bar running around the button perimeter, inset by `offset` pixels."""
        inset_rect = QRectF(rect).adjusted(offset, offset, -offset, -offset)
        corner_r = max(8.0, 12.0 - offset)

        path = ShapePainter._perimeter_path(inset_rect, corner_r)
        total_len = path.length()
        if total_len <= 0:
            return

        track_pen = QPen(track_color, thickness)
        track_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        if fraction is None:
            return
        frac = max(0.0, min(1.0, float(fraction)))
        if frac <= 0:
            return

        filled_len = frac * total_len
        gap_len = max(0.001, total_len - filled_len)

        grad = QLinearGradient(inset_rect.topLeft(), inset_rect.bottomLeft())
        grad.setColorAt(0.0, fill_color)
        lighter = QColor(fill_color)
        lighter.setHsvF(
            lighter.hsvHueF(),
            max(0.0, lighter.hsvSaturationF() - 0.05),
            min(1.0, lighter.valueF() + 0.12),
        )
        grad.setColorAt(1.0, lighter)

        fill_pen = QPen(QBrush(grad), thickness)
        fill_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        # setDashPattern values are in pen-width units, so divide by thickness
        fill_pen.setDashPattern([filled_len / thickness, gap_len / thickness])
        painter.setPen(fill_pen)
        painter.drawPath(path)

    @staticmethod
    def draw_gauge_arc(painter, rect, fraction, fill_color, track_color, thickness=None):
        arc_rect = QRectF(rect)
        if thickness is None:
            thickness = max(6.0, min(arc_rect.width(), arc_rect.height()) / 10.0)

        inset = thickness / 2.0
        arc_rect.adjust(inset, inset, -inset, -inset)

        pen_track = QPen(track_color, thickness)
        pen_track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_track)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(arc_rect, 0, 180 * 16)

        if fraction is not None:
            frac = max(0.0, min(1.0, float(fraction)))
            if frac > 0:
                grad = QLinearGradient(0, arc_rect.bottom(), 0, arc_rect.top())
                grad.setColorAt(0.0, fill_color)
                lighter = QColor(fill_color)
                lighter.setHsvF(lighter.hsvHueF(), max(0.0, lighter.hsvSaturationF() - 0.05), min(1.0, lighter.valueF() + 0.12))
                grad.setColorAt(1.0, lighter)
                pen_fill = QPen(QBrush(grad), thickness)
                pen_fill.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen_fill)
                painter.drawArc(arc_rect, 180 * 16, -int(180 * 16 * frac))

    @staticmethod
    def _draw_pill_label(painter, rect, label, background_pixmap=None, x_off=0, y_off=0, position='top-center', forced_bg_color=None, forced_text_color=None, force_dark=False):
        """Draws a pill label (frosted glass by default, or solid if colors provided)."""
        if not label:
            return

        # Calculate Pill Geometry
        if position == 'top-right':
            font = QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold)
            old_font = painter.font()
            painter.setFont(font)
            fm = painter.fontMetrics()
            
            text_w = fm.horizontalAdvance(label.upper())
            painter.setFont(old_font) # restore
            
            pill_w = max(48, text_w + 24)
            pill_h = 28
            pill_x = rect.width() - pill_w - 12
            pill_y = 12
        elif position == 'top-left':
            font = QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold)
            old_font = painter.font()
            painter.setFont(font)
            fm = painter.fontMetrics()
            
            text_w = fm.horizontalAdvance(label.upper())
            painter.setFont(old_font) # restore
            
            pill_w = max(48, text_w + 24)
            pill_h = 28
            pill_x = 12
            pill_y = 12
        else: # top-center (Upper Third)
            font = QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold)
            old_font = painter.font()
            painter.setFont(font)
            fm = painter.fontMetrics()
            
            text_w = fm.horizontalAdvance(label.upper())
            painter.setFont(old_font) # restore
            
            pill_w = min(rect.width() * 0.9, max(48, text_w + 24)) # Max width constraint
            pill_h = 28
            pill_x = (rect.width() - pill_w) / 2
            pill_y = rect.height() * 0.15 # 15% from top
            
        pill_rect = QRectF(pill_x, pill_y, pill_w, pill_h)
        
        if forced_bg_color:
            # Draw solid pill
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(forced_bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(pill_rect, 14, 14)
            painter.restore()
            text_color = forced_text_color or QColor("white")
        else:
            # Draw the frosted background and auto-magically get the correct text color contrast
            from ui.utils.glass_effect import draw_frosted_pill
            
            text_color = draw_frosted_pill(
                painter,
                pill_rect,
                background_pixmap=background_pixmap,
                bg_x_offset=x_off,
                bg_y_offset=y_off,
                force_dark=force_dark
            )

        font = QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, label.upper())

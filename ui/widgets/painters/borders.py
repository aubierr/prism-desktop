"""Tile borders and edges: animated effect borders, image edge shading and bevels."""

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QLinearGradient, QConicalGradient, QRadialGradient


class BorderPainter:
    """Tile borders and edges: animated effect borders, image edge shading and bevels."""

    @staticmethod
    def draw_rainbow_border(painter, rect, angle):
        colors = ["#4285F4", "#EA4335", "#FBBC05", "#34A853", "#4285F4"]
        BorderPainter.draw_gradient_border(painter, rect, angle, colors)

    @staticmethod
    def draw_aurora_border(painter, rect, angle):
        colors = ["#00C896", "#0078FF", "#8C00FF", "#0078FF", "#00C896"]
        BorderPainter.draw_gradient_border(painter, rect, angle, colors)

    @staticmethod
    def draw_prism_shard_border(painter, rect, angle):
        # Muted jewel tones for a less "neon" look
        colors = ["#26C6DA", "#EC407A", "#FFCA28", "#CFD8DC", "#26C6DA"]
        BorderPainter.draw_gradient_border(painter, rect, angle, colors)

    @staticmethod
    def draw_liquid_mercury_border(painter, rect, angle):
        # Gunmetal Chrome: Darker, more sophisticated palette
        colors = ["#37474F", "#78909C", "#CFD8DC", "#ECEFF1", "#CFD8DC", "#78909C", "#37474F"]
        BorderPainter.draw_gradient_border(painter, rect, angle, colors)

    @staticmethod
    def draw_gradient_border(painter, rect, angle, colors):
        """Draw a conical gradient border."""
        gradient = QConicalGradient(QPointF(rect.center()), angle)

        for i, color in enumerate(colors):
            gradient.setColorAt(i / (len(colors) - 1), QColor(color))
        
        pen = QPen()
        pen.setWidth(2)
        pen.setBrush(QBrush(gradient))
        
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 9, 9)

    @staticmethod
    def draw_image_edge_effects(painter, rect, is_top_clamped=False, is_light=False, corner_radius=12):
        """Draws a soft inner vignette shadow and a bright top-left specular highlight to make camera feeds look like physical glass rather than hard stickers."""
        painter.save()

        # 1. Inner Vignette — clipped to rounded rect so Multiply mode doesn't
        #    bleed into transparent widget corners and create a visible dark box
        clip = QPainterPath()
        clip.addRoundedRect(rect, corner_radius, corner_radius)
        painter.setClipPath(clip)

        center = rect.center()
        radius = max(rect.width(), rect.height()) / 1.5

        grad = QRadialGradient(center, radius)
        grad.setColorAt(0.7, QColor(0, 0, 0, 0))    # Transparent core
        grad.setColorAt(1.0, QColor(0, 0, 0, 100))  # Darkened exterior edges

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.fillRect(rect, grad)

        # Restore for the highlight pass
        painter.setClipping(False)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # 2. Specular Glass Highlight & Perimeter
        BorderPainter.draw_button_bevel_edge(painter, rect, intensity_modifier=1.3, is_top_clamped=is_top_clamped, is_light=is_light, corner_radius=corner_radius)

        painter.restore()

    @staticmethod
    def draw_button_bevel_edge(painter, rect, intensity_modifier=1.0, is_top_clamped=False, corner_radius=11, is_light=False):
        """Draws a top-left specular highlight and perimeter outline to give buttons physical depth."""
        painter.save()

        line_rect = QRectF(rect)

        def make_path(adj_rect, r):
            p = QPainterPath()
            if is_top_clamped:
                p.moveTo(adj_rect.bottomLeft())
                p.lineTo(adj_rect.left(), adj_rect.top() + r)
                p.arcTo(adj_rect.left(), adj_rect.top(), r*2, r*2, 180, -90)
                p.lineTo(adj_rect.right() - r, adj_rect.top())
                p.arcTo(adj_rect.right() - r*2, adj_rect.top(), r*2, r*2, 90, -90)
                p.lineTo(adj_rect.bottomRight())
                p.closeSubpath()
            else:
                p.addRoundedRect(adj_rect, r, r)
            return p

        if is_light:
            # Light mode: skip white highlight (invisible), just draw a visible dark perimeter
            perimeter_pen = QPen(QColor(0, 0, 0, 28))
            perimeter_pen.setWidthF(1.0)
            painter.setPen(perimeter_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(make_path(line_rect.adjusted(0.5, 0.5, -0.5, -0.5), corner_radius + 0.5))
        else:
            # Dark mode: white top-left highlight gradient + subtle white perimeter
            highlight_grad = QLinearGradient(line_rect.topLeft(), line_rect.topRight())
            alpha_start = min(255, int(45 * intensity_modifier))
            alpha_mid = min(255, int(15 * intensity_modifier))
            highlight_grad.setColorAt(0.0, QColor(255, 255, 255, alpha_start))
            highlight_grad.setColorAt(0.4, QColor(255, 255, 255, alpha_mid))
            highlight_grad.setColorAt(1.0, QColor(255, 255, 255, 0))

            pen = QPen(QBrush(highlight_grad), 2.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(make_path(line_rect.adjusted(1, 1, -1, -1), corner_radius))

            perimeter_alpha = min(255, int(15 * intensity_modifier))
            perimeter_pen = QPen(QColor(255, 255, 255, perimeter_alpha))
            perimeter_pen.setWidthF(1.0)
            painter.setPen(perimeter_pen)
            painter.drawPath(make_path(line_rect.adjusted(0.5, 0.5, -0.5, -0.5), corner_radius + 0.5))

        painter.restore()

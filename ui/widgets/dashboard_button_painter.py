from PyQt6.QtCore import Qt, QRectF, QPointF, QPropertyAnimation
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush, QLinearGradient,
)
from ui.icons import get_mdi_font, Icons
from ui.widgets.painters.shapes import ShapePainter
from ui.widgets.painters.borders import BorderPainter
from ui.widgets.painters.media_player import MediaPlayerPainter
from ui.widgets.painters.sensor import SensorPainter
from ui.widgets.painters.printer import PrinterPainter
from ui.widgets.painters.sun import SunPainter


class DashboardButtonPainter(
    ShapePainter, BorderPainter, MediaPlayerPainter, SensorPainter, PrinterPainter, SunPainter,
):
    """Handles custom painting for DashboardButton.

    paint() and the small state indicators live here; shapes, borders and the
    larger tile types live in ui/widgets/painters/ and are inherited, so every
    DashboardButtonPainter.<name> call keeps working.
    """

    @staticmethod
    def _paint_lock_hold_ring(button):
        """Amber ring traced around the border while a lock's unlock-hold is in progress."""
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        DashboardButtonPainter.draw_perimeter_progress(
            painter,
            QRectF(button.rect()),
            fraction=button._lock_hold_progress,
            fill_color=QColor('#F2A600'),
            track_color=QColor(255, 255, 255, 30),
            thickness=3,
            offset=6,
        )
        painter.end()

    @staticmethod
    def paint(button, event):
        """Main paint method."""
        # Media Player (Apple-like)
        if button.config.get('type') == 'media_player':
            DashboardButtonPainter._paint_media_player(button)
            
        # 3D Printer
        if button.config.get('type') == '3d_printer':
            DashboardButtonPainter._paint_3d_printer(button)

        # Sun
        if button.config.get('type') == 'sun':
            DashboardButtonPainter._draw_sun_button(button)

        # Sensor widget with gauge/bar/perimeter display style
        if (button.config.get('type') == 'widget'
                and button.config.get('display_style') in ('gauge', 'bar', 'perimeter')):
            DashboardButtonPainter._paint_widget_sensor(button)

        # Lock hold-to-unlock progress ring
        if button.config.get('type') == 'lock' and getattr(button, '_lock_hold_progress', 0.0) > 0.0:
            DashboardButtonPainter._paint_lock_hold_ring(button)

        # Draw Camera Image (if applicable)
        if button.config and button.config.get('type') == 'camera':
             # Use cached rounded pixmap if available (Performance + Style)
             if hasattr(button, '_cached_display_pixmap') and button._cached_display_pixmap and not button._cached_display_pixmap.isNull():
                 painter = QPainter(button)
                 painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                 
                 # Ensure clipping even when using cached pixmap (for the edge effects)
                 path = QPainterPath()
                 path.addRoundedRect(QRectF(button.rect()), 12, 12)
                 painter.setClipPath(path)
                 
                 painter.drawPixmap(0, 0, button._cached_display_pixmap)
                 DashboardButtonPainter.draw_image_edge_effects(painter, QRectF(button.rect()), is_top_clamped=False)
                 painter.end()
             
             # Fallback to direct scaling if cache missing (e.g. first frame or resize race condition)
             elif hasattr(button, '_last_camera_pixmap') and button._last_camera_pixmap:
                 painter = QPainter(button)
                 painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                 
                 # Clip to rounded rect
                 path = QPainterPath()
                 path.addRoundedRect(QRectF(button.rect()), 12, 12)
                 painter.setClipPath(path)
                 
                 # Scale to fill button while maintaining aspect ratio (crop if needed)
                 scaled = button._last_camera_pixmap.scaled(
                     button.width(), button.height(),
                     Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation
                 )
                 
                 # Center crop
                 x = (scaled.width() - button.width()) // 2
                 y = (scaled.height() - button.height()) // 2
                 
                 # Draw cropped
                 painter.drawPixmap(0, 0, scaled, x, y, button.width(), button.height())
                 DashboardButtonPainter.draw_image_edge_effects(painter, QRectF(button.rect()), is_top_clamped=False)
                 painter.end()
                 
        # === Camera Pill Label ===
        if button.config and button.config.get('type') == 'camera':
             label = button.config.get('label')
             if label:
                 # Re-open painter for overlay
                 painter = QPainter(button)
                 painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                 
                 # Prepare background for blur
                 bg_pix = None
                 x_off = 0
                 y_off = 0
                 
                 if hasattr(button, '_cached_display_pixmap') and button._cached_display_pixmap and not button._cached_display_pixmap.isNull():
                     bg_pix = button._cached_display_pixmap
                 elif hasattr(button, '_last_camera_pixmap') and button._last_camera_pixmap:
                     # For fallback, we need to replicate the scale/crop to get correct blur source
                     # This is expensive but fallback is rare
                     scaled = button._last_camera_pixmap.scaled(
                         button.width(), button.height(),
                         Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                         Qt.TransformationMode.SmoothTransformation
                     )
                     bg_pix = scaled
                     x_off = (scaled.width() - button.width()) // 2
                     y_off = (scaled.height() - button.height()) // 2
                 
                 DashboardButtonPainter._draw_pill_label(painter, button.rect(), label, bg_pix, x_off, y_off)
                 painter.end()
        
        # Pulse Animation (Script)
        if button._pulse_opacity > 0.01:
            DashboardButtonPainter._paint_pulse(button)

        # Only draw special border if animating or if progress > 0
        if button.anim.state() == QPropertyAnimation.State.Running or button._anim_progress > 0.0:
            DashboardButtonPainter._paint_border_animation(button)

        # Draw input_number blink feedback
        if getattr(button, '_input_blink_opacity', 0.0) > 0.01 and button.config.get('type') == 'input_number':
            DashboardButtonPainter._paint_input_blink(button)

        # Draw input_number hover arrows
        if getattr(button, '_arrow_opacity', 0.0) > 0.01 and button.config.get('type') == 'input_number':
            DashboardButtonPainter._paint_input_arrows(button)

        # Per-tile refresh indicator (opt-in, Settings > Appearance > Options):
        # painted last among these overlays so a simultaneous full-tile flash
        # (script pulse, input_number blink) never hides the corner dot.
        if getattr(button, '_refresh_flash_opacity', 0.0) > 0.01:
            DashboardButtonPainter._paint_refresh_indicator(button)

        if not button.config:
            DashboardButtonPainter._paint_empty_slot(button)

        # Draw Resize Handle (Glass-like)
        if button._resize_handle_opacity > 0.01:
            DashboardButtonPainter._paint_resize_handle(button)

        # UNIVERSAL EDGE BEVEL HIGHLIGHT
        # Gives ALL configured buttons a subtle physical lip, making them feel like 3D glass/plastic tiles
        button_style = getattr(button, 'button_style', 'Gradient')
        if button.config and button.config.get('type') != 'forbidden' and button_style == 'Gradient':
            is_light = (button.theme_manager and button.theme_manager.get_effective_theme() == 'light')
            painter = QPainter(button)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            DashboardButtonPainter.draw_button_bevel_edge(painter, QRectF(button.rect()), intensity_modifier=0.25, is_light=is_light)
            painter.end()


    @staticmethod
    def _paint_pulse(button):
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Use custom color or accent
        c = QColor("#0078d4")
        if button.theme_manager:
            colors = button.theme_manager.get_colors()
            c = QColor(colors.get('accent', '#0078d4'))
        
        # Allow custom color override
        if button.config and 'color' in button.config:
            c = QColor(button.config['color'])
            
        c.setAlphaF(button._pulse_opacity)
        
        # Draw rounded rect overlay
        painter.setBrush(QBrush(c))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(button.rect()), 12, 12)
        painter.end()

    @staticmethod
    def _paint_refresh_indicator(button):
        """Small corner dot marking a live push from Home Assistant (opt-in).

        Deliberately ignores the tile's accent/custom color: unlike the
        script pulse (a full-tile wash, where matching the tile's color
        looks intentional), this dot has to stand out *against* the tile —
        including tiles whose custom color equals the theme accent, where a
        same-colored dot would be invisible. A white fill with a dark
        outline reads on light and dark tiles alike.
        """
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        opacity = button._refresh_flash_opacity
        radius = 3.5
        margin = 8.0
        cx = button.rect().width() - margin - radius
        cy = margin + radius
        center = QPointF(cx, cy)

        outline = QColor(0, 0, 0)
        outline.setAlphaF(0.35 * opacity)
        pen = QPen(outline)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius + 0.6, radius + 0.6)

        fill = QColor(255, 255, 255)
        fill.setAlphaF(opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(center, radius, radius)

        painter.end()

    @staticmethod
    def _paint_input_blink(button):
        """Draw a quick white flash over the button when value changes."""
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        c = QColor(255, 255, 255)
        c.setAlphaF(button._input_blink_opacity)
        
        painter.setBrush(QBrush(c))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(button.rect()), 12, 12)
        painter.end()
        
    @staticmethod
    def _paint_input_arrows(button):
        """Draw minimalist up/down arrows on hover."""
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Determine color based on theme
        if button.theme_manager:
            colors = button.theme_manager.get_colors()
            base_text = colors.get('text', '#ffffff')
            is_light = base_text == '#1e1e1e'
            c = QColor(0, 0, 0) if is_light else QColor(255, 255, 255)
        else:
            c = QColor(255, 255, 255)
            
        c.setAlphaF(getattr(button, '_arrow_opacity', 0.0) * 0.6)
        painter.setPen(c)
        rect = button.rect()
        w, h = rect.width(), rect.height()
        
        if button.span_y == 1:
            if button.span_x == 1:
                # No arrows for 1x1 layout - relies purely on drag
                pass
            else:
                # Left and right vertical centers
                font_size = 20 if button.span_x == 1 else 24
                painter.setFont(get_mdi_font(font_size))
                
                padding = 12
                left_rect = QRectF(padding, 0, w * 0.25, h)
                painter.drawText(left_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, Icons.CHEVRON_LEFT)
                
                right_rect = QRectF(w * 0.75 - padding, 0, w * 0.25, h)
                painter.drawText(right_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, Icons.CHEVRON_RIGHT)
        else:
            painter.setFont(get_mdi_font(24))
            
            # Top quarter for Up Arrow
            up_rect = QRectF(0, 8, w, h * 0.25)
            painter.drawText(up_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop, Icons.CHEVRON_UP)
            
            # Bottom quarter for Down Arrow
            down_rect = QRectF(0, h * 0.75 - 8, w, h * 0.25)
            painter.drawText(down_rect, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom, Icons.CHEVRON_DOWN)
        
        painter.end()

    @staticmethod
    def _paint_border_animation(button):
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Interactive 'Press' feedback
        speed = 0.9 if button._border_effect == 'Prism Shard' else 1.5
        if button._border_effect == 'Liquid Mercury': speed = 1.2
        angle = button._anim_progress * 360.0 * speed
        
        opacity = 1.0
        if button._anim_progress > 0.8:
            opacity = (1.0 - button._anim_progress) / 0.2

        opacity = max(0.0, opacity)
        
        painter.setOpacity(opacity)
        rect = button.rect().adjusted(1, 1, -1, -1)
        
        if button._border_effect == 'Rainbow':
            DashboardButtonPainter.draw_rainbow_border(painter, rect, angle)
        elif button._border_effect == 'Aurora Borealis':
            DashboardButtonPainter.draw_aurora_border(painter, rect, angle)
        elif button._border_effect == 'Prism Shard':
            DashboardButtonPainter.draw_prism_shard_border(painter, rect, angle)
        elif button._border_effect == 'Liquid Mercury':
            DashboardButtonPainter.draw_liquid_mercury_border(painter, rect, angle)
        painter.end()

    @staticmethod
    def _paint_empty_slot(button):
        # Dashed border for empty slots (drawn over stylesheet bg)
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = button.rect().adjusted(1, 1, -1, -1)
        
        # Theme-aware border color
        is_light = (button.theme_manager and button.theme_manager.get_effective_theme() == 'light')
        border_color = QColor("#c0c0c0") if is_light else QColor("#555555")
        
        if not hasattr(button, '_dashed_pen') or getattr(button, '_dashed_pen_light', None) != is_light:
            button._dashed_pen = QPen(border_color)
            button._dashed_pen.setStyle(Qt.PenStyle.DashLine)
            button._dashed_pen.setWidth(2)
            button._dashed_pen_light = is_light
            
        painter.setPen(button._dashed_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)
            
        painter.end()

    @staticmethod
    def _paint_resize_handle(button):
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setOpacity(button._resize_handle_opacity)
        
        # Bottom-right corner
        r = button.rect()
        radius = 12 # Match button border radius
        handle_size = 28 # Bigger handle
        
        path = QPainterPath()
        
        # 1. Start on bottom edge, left of corner
        path.moveTo(r.right() - handle_size, r.bottom())
        
        # 2. Outer Edge: Follow the button's rounded corner exactly
        corner_rect = QRectF(r.right() - 2*radius, r.bottom() - 2*radius, 2*radius, 2*radius)
        
        path.lineTo(r.right() - radius, r.bottom()) # Line to start of arc
        path.arcTo(corner_rect, 270, 90) # The corner itself
        path.lineTo(r.right(), r.bottom() - handle_size) # Line to handle top
        
        # 3. Inner Edge: Curve inward back to start
        path.quadTo(r.right() - 4, r.bottom() - 4, r.right() - handle_size, r.bottom())
        
        path.closeSubpath()
        
        # Glass Style
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Gradient for glass/shiny look
        grad = QLinearGradient(QPointF(r.right() - handle_size, r.bottom() - handle_size), QPointF(r.bottomRight()))
        grad.setColorAt(0.0, QColor(255, 255, 255, 120)) # Start brighter 
        grad.setColorAt(1.0, QColor(255, 255, 255, 10))  # Fade out
        
        painter.setBrush(QBrush(grad))
        painter.drawPath(path)
        
        # Accent line (Inner Edge only) for sharpness
        pen = QPen(QColor(255, 255, 255, 70))
        pen.setWidthF(2.0)
        painter.strokePath(path, pen)
        painter.end()



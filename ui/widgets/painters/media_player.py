"""Painting for media player tiles."""

from PyQt6.QtCore import Qt, QRect, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QLinearGradient
from ui.icons import get_mdi_font, Icons
from core.utils import SYSTEM_FONT
from ui.visuals.background_generator import BackgroundGenerator
from ui.widgets.painters.shapes import ShapePainter


class MediaPlayerPainter:
    """Painting for media player tiles."""

    @staticmethod
    def _paint_media_player(button):
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = button.rect()
        is_playing = button._state == "playing"
        is_huge = button.span_x >= 2 and button.span_y >= 2  # 2x2+
        is_wide = button.span_x >= 2
        is_tall = button.span_y >= 2 and button.span_x < 2  # 1x2
        
        # Resolve accent color
        btn_color = button.config.get('color')
        if not btn_color and button.theme_manager:
            colors = button.theme_manager.get_colors()
            btn_color = colors.get('accent', '#4285F4')
        elif not btn_color:
            btn_color = "#4285F4"
        
        # --- Background ---
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), 12, 12)
        painter.setClipPath(clip_path)
        
        # Album art background (any size except 1x1, if enabled)
        has_art = button._album_art and not button._album_art.isNull()
        show_art = button.config.get('show_album_art', True)
        if (is_huge or is_tall or is_wide) and has_art and show_art:
            # Draw blurred/dimmed album art
            scaled = button._album_art.scaled(
                rect.width(), rect.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            # Center crop
            x_off = (scaled.width() - rect.width()) // 2
            y_off = (scaled.height() - rect.height()) // 2
            painter.drawPixmap(0, 0, scaled, x_off, y_off, rect.width(), rect.height())
            
            # Gradient overlay: user color at bottom -> transparent at top
            # FIX: Use explicit TopLeft/BottomLeft for full coverage
            grad = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomLeft()))
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))           # Top: transparent
            overlay_color = QColor(btn_color)
            overlay_color.setAlpha(255)
            grad.setColorAt(1.0, overlay_color)                  # Bottom: user color
            painter.fillRect(rect, grad)
        else:
             # No Art -> Procedural Background

             # Generate deterministic seed based on media info or button slot
             media_state = button._media_state or {}
             attrs = media_state.get('attributes', {})

             title = attrs.get('media_title', '')
             artist = attrs.get('media_artist', '')

             if title or artist:
                 seed = hash(f"{title}{artist}")
             else:
                 seed = button.slot

             animated = button.config.get('animated_bg', True)
             w, h = rect.width(), rect.height()

             if animated:
                 # --- Animated prismatic light field ---
                 button._ensure_anim_bg_layers(seed)
                 bg = BackgroundGenerator.render_frame(
                     w, h,
                     button._anim_bg_layers,
                     button._anim_bg_frame,
                     tiny_pixmap=button._anim_bg_tiny,
                 )
                 painter.drawPixmap(0, 0, bg)
             else:
                 # --- Static background (original behaviour) ---
                 light_mode = bool(
                     button.theme_manager
                     and button.theme_manager.get_effective_theme() == 'light'
                 )
                 bg_pixmap = BackgroundGenerator.generate(w, h, seed=seed, light_mode=light_mode)
                 painter.drawPixmap(0, 0, bg_pixmap)

             # Gradient overlay (for text readability)
             grad = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomLeft()))
             grad.setColorAt(0.0, QColor(0, 0, 0, 0))
             overlay_color = QColor(btn_color)
             overlay_color.setAlpha(200 if is_playing else 120)
             grad.setColorAt(1.0, overlay_color)
             painter.fillRect(rect, grad)
            
        # === PILL LABEL (Apple-like) ===
        # Always show Pill if Huge 2x2+
        label = button.config.get('label')
        if is_huge and label:
            bg_pix = None
            x_off = 0
            y_off = 0
            if has_art and show_art:
                 bg_pix = scaled
                 # x_off and y_off are already calculated above
            
            ShapePainter._draw_pill_label(painter, rect, label, bg_pix, x_off, y_off)

        
        # --- Icons ---
        is_playing = button._state == 'playing'
        is_paused = button._state == 'paused'
        
        play_icon = Icons.PLAY_PAUSE
        if is_playing:
            play_icon = Icons.PAUSE
        elif is_paused:
            play_icon = Icons.PLAY
            
        painter.setPen(QColor("white"))
        
        # Get media info
        attrs = button._media_state.get('attributes', {})
        title = attrs.get('media_title', '')
        artist = attrs.get('media_artist', '')
        
        if is_huge:
            # === 2x2: Now Playing Layout ===
            # Layout: album art top | transport controls middle | text bottom
            w = rect.width()
            h = rect.height()
            
            # Transport controls (center area)
            ctrl_h = 40
            ctrl_y = h // 2 - ctrl_h // 2
            painter.setFont(get_mdi_font(30))
            
            r_prev = QRect(0, ctrl_y, w // 3, ctrl_h)
            painter.drawText(r_prev, Qt.AlignmentFlag.AlignCenter, Icons.PREVIOUS)
            
            r_play = QRect(w // 3, ctrl_y, w // 3, ctrl_h)
            painter.drawText(r_play, Qt.AlignmentFlag.AlignCenter, play_icon)
            
            r_next = QRect((w // 3) * 2, ctrl_y, w // 3, ctrl_h)
            painter.drawText(r_next, Qt.AlignmentFlag.AlignCenter, Icons.NEXT)
            
            # === SONG INFO PILL (bottom area) ===
            if title or artist:
                # Build single-line display string: "Artist - Title"
                if artist and title:
                    info_text = f"{artist}  \u2013  {title}"
                else:
                    info_text = title or artist
                
                # Measure text to determine pill size
                info_font = QFont(SYSTEM_FONT, 8, QFont.Weight.DemiBold)
                info_fm = QFontMetrics(info_font)
                
                text_w = info_fm.horizontalAdvance(info_text)
                padding_h = 20  # Horizontal padding
                info_pill_w = min(text_w + padding_h * 2, w * 0.9)
                info_pill_h = 28  # Single line pill
                
                info_pill_x = (w - info_pill_w) / 2
                info_pill_y = h - info_pill_h - 8  # 8px from bottom
                info_pill_rect = QRectF(info_pill_x, info_pill_y, info_pill_w, info_pill_h)
                
                # --- Pill Background ---
                info_pill_path = QPainterPath()
                info_pill_path.addRoundedRect(info_pill_rect, 14, 14)
                
                if has_art and show_art:
                    # Blurred art background
                    from ui.utils.glass_effect import draw_frosted_pill
                    info_text_color = draw_frosted_pill(
                        painter, 
                        info_pill_rect, 
                        background_pixmap=scaled, 
                        bg_x_offset=x_off, 
                        bg_y_offset=y_off
                    )
                else:
                    # No art fallback
                    info_text_color = QColor(255, 255, 255, 220)
                    painter.save()
                    painter.fillPath(info_pill_path, QColor(0, 0, 0, 60))
                    pen = QPen(QColor(255, 255, 255, 30))
                    pen.setWidth(1)
                    painter.setPen(pen)
                    painter.drawRoundedRect(info_pill_rect, 14, 14)
                    painter.restore()
                
                # --- Draw Text ---
                painter.setFont(info_font)
                painter.setPen(info_text_color)
                max_text_area = info_pill_w - padding_h * 2
                fm = painter.fontMetrics()
                elided = fm.elidedText(info_text, Qt.TextElideMode.ElideRight, int(max_text_area))
                painter.drawText(info_pill_rect, Qt.AlignmentFlag.AlignCenter, elided)
            
        elif is_tall:
            # === 1x2: Tall Layout ===
            w = rect.width()
            h = rect.height()
            
            # Play/pause (upper area)
            painter.setFont(get_mdi_font(30))
            play_rect = QRect(0, 0, w, h // 2)
            painter.drawText(play_rect, Qt.AlignmentFlag.AlignCenter, play_icon)
            
            # Prev / Next (bottom area)
            ctrl_y = h // 2 + 8
            ctrl_h = h // 2 - 8
            painter.setFont(get_mdi_font(24))
            
            r_prev = QRect(0, ctrl_y, w // 2, ctrl_h)
            painter.drawText(r_prev, Qt.AlignmentFlag.AlignCenter, Icons.PREVIOUS)
            
            r_next = QRect(w // 2, ctrl_y, w // 2, ctrl_h)
            painter.drawText(r_next, Qt.AlignmentFlag.AlignCenter, Icons.NEXT)
            
        elif is_wide:
            # === 2x1: Wide Transport ===
            w = rect.width()
            h = rect.height()
            painter.setFont(get_mdi_font(28))
            
            r_prev = QRect(0, 0, w // 3, h)
            painter.drawText(r_prev, Qt.AlignmentFlag.AlignCenter, Icons.PREVIOUS)
            
            r_play = QRect(w // 3, 0, w // 3, h)
            painter.drawText(r_play, Qt.AlignmentFlag.AlignCenter, play_icon)
            
            r_next = QRect((w // 3) * 2, 0, w // 3, h)
            painter.drawText(r_next, Qt.AlignmentFlag.AlignCenter, Icons.NEXT)
            
        else:
            # === 1x1: Compact Play/Pause ===
            painter.setFont(get_mdi_font(28))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, play_icon)

        painter.end()

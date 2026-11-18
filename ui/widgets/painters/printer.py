"""Painting for 3D printer tiles."""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from ui.icons import get_icon, get_mdi_font, Icons
from core.utils import SYSTEM_FONT
from core.temperature_utils import format_temperature
from ui.widgets.painters.borders import BorderPainter
from ui.widgets.painters.shapes import ShapePainter


class PrinterPainter:
    """Painting for 3D printer tiles."""

    @staticmethod
    def _paint_3d_printer(button):
        painter = QPainter(button)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = button.rect()
        is_huge = button.span_x >= 2 and button.span_y >= 2  # 2x2+
        is_wide = button.span_x >= 2

        # State Data
        state = button._state.lower()  # printing, paused, operational, etc.
        printer_state = state.capitalize()
        
        # Theme / Colors
        if button.theme_manager:
            colors = button.theme_manager.get_colors()
            text_color = QColor(colors.get('text', '#e0e0e0'))
            dim_text_color = text_color.darker(150)
        else:
            text_color = QColor('#e0e0e0')
            dim_text_color = QColor('#aaaaaa')
            
        # Accent color based on state
        if state in ['printing', 'heating']:
            accent_color = QColor('#34A853') # Green
        elif state == 'paused':
            accent_color = QColor('#FBBC05') # Yellow
        elif 'error' in state or state == 'offline':
            accent_color = QColor('#EA4335') # Red
        else:
            accent_color = QColor('#4285F4') # Blue (Idle/Operational)
            
        # Fetch entities manually since standard button abstraction binds to 1 entity
        dashboard = button.window()  # Walk up to dashboard
        camera_pixmap = None
        nozzle_str = "--"
        bed_str = "--"
        progress = 0
        
        cfg = button.config
        
        if hasattr(dashboard, '_entity_states'):
            # Camera image is handled by the standard `_last_camera_pixmap` on button if configured via `set_camera_image`
            if hasattr(button, '_cached_display_pixmap') and button._cached_display_pixmap and not button._cached_display_pixmap.isNull():
                 camera_pixmap = button._cached_display_pixmap
            elif hasattr(button, '_last_camera_pixmap') and button._last_camera_pixmap:
                 camera_pixmap = button._last_camera_pixmap
            
            # Prefer dedicated progress entity if configured
            state_data = dashboard._entity_states.get(cfg.get('printer_state_entity'), {})
            attrs = state_data.get('attributes', {})
            prog_entity = cfg.get('printer_progress_entity')
            if prog_entity:
                prog_data = dashboard._entity_states.get(prog_entity, {})
                progress = prog_data.get('state', 0)
            else:
                # Fall back to common progress attributes on state entity
                progress = attrs.get('progress', attrs.get('job_percentage', 0))
            
            try:
                progress = float(progress)
            except (ValueError, TypeError):
                progress = 0.0
            
            # Nozzle
            nozzle_data = dashboard._entity_states.get(cfg.get('printer_nozzle_entity'), {})
            nozzle_val = nozzle_data.get('state', '--')
            nozzle_target_data = dashboard._entity_states.get(cfg.get('printer_nozzle_target_entity'), {})
            nozzle_target_val = nozzle_target_data.get('state', None)
            nozzle_attrs = nozzle_data.get('attributes', {})
            src_unit = nozzle_attrs.get('unit_of_measurement')
            pref = getattr(button, 'temperature_unit_preference', None)
            _fmt = lambda v: format_temperature(v, src_unit, pref, precision=0, fallback="--")

            if nozzle_val != '--':
                try:
                    n_act = float(nozzle_val)
                    if button.span_x > 3 and nozzle_target_val and nozzle_target_val != 'unknown':
                        n_tgt = float(nozzle_target_val)
                        nozzle_str = f"{_fmt(n_act)}/{_fmt(n_tgt)}"
                    else:
                        nozzle_str = _fmt(n_act)
                except (TypeError, ValueError): nozzle_str = _fmt(nozzle_val)

            # Bed
            bed_data = dashboard._entity_states.get(cfg.get('printer_bed_entity'), {})
            bed_val = bed_data.get('state', '--')
            bed_target_data = dashboard._entity_states.get(cfg.get('printer_bed_target_entity'), {})
            bed_target_val = bed_target_data.get('state', None)
            bed_attrs = bed_data.get('attributes', {})
            bed_src_unit = bed_attrs.get('unit_of_measurement') or src_unit
            _fmt_bed = lambda v: format_temperature(v, bed_src_unit, pref, precision=0, fallback="--")

            if bed_val != '--':
                try:
                    b_act = float(bed_val)
                    if button.span_x > 3 and bed_target_val and bed_target_val != 'unknown':
                        b_tgt = float(bed_target_val)
                        bed_str = f"{_fmt_bed(b_act)}/{_fmt_bed(b_tgt)}"
                    else:
                        bed_str = _fmt_bed(b_act)
                except (TypeError, ValueError): bed_str = _fmt_bed(bed_val)
            
        icon = Icons.PRINTER_3D # standard mdi-printer-3d
        
        # DRAW LOGIC
        if is_huge:
            # === 2x2+: Camera Top, Stats Strip Bottom ===
            w = rect.width()
            h = rect.height()
            
            # 1. Camera Feed (fills entire card; footer pills float over it)
            cam_h = h
            cam_rect = QRectF(0, 0, w, cam_h)
            
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 12, 12)
            painter.setClipPath(path)
            
            if camera_pixmap and not camera_pixmap.isNull():
                 # Fast direct draw if using cached rounded pixmap
                 if camera_pixmap == getattr(button, '_cached_display_pixmap', None):
                      painter.drawPixmap(0, 0, camera_pixmap)
                      bg_pix = camera_pixmap
                      x_bg = 0
                      y_bg = 0
                 else:
                      # Aspect fill the top section
                      scaled = camera_pixmap.scaled(
                          int(w), int(cam_h),
                          Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                          Qt.TransformationMode.SmoothTransformation
                      )
                      x_off = (scaled.width() - w) / 2
                      y_off = (scaled.height() - cam_h) / 2
                      painter.drawPixmap(0, 0, scaled, int(x_off), int(y_off), int(w), int(cam_h))
                      bg_pix = scaled
                      x_bg = int(x_off)
                      y_bg = int(y_off)
                      
                 # Add glass edge effects (shadow + highlight) to the camera feed
                 BorderPainter.draw_image_edge_effects(painter, cam_rect, is_top_clamped=False)
                 
            else:
                 bg_pix = None
                 x_bg = 0
                 y_bg = 0
                 # Fallback empty camera zone
                 painter.fillRect(cam_rect.toRect(), QColor(0, 0, 0, 100))
                 painter.setFont(get_mdi_font(40))
                 painter.setPen(QColor(255, 255, 255, 100))
                 painter.drawText(cam_rect, Qt.AlignmentFlag.AlignCenter, Icons.VIDEO_OFF)
            
            # Draw Pill Overlay for Progress %
            try:
                prog_val = float(progress)
            except (ValueError, TypeError):
                prog_val = 0.0
                
            if printer_state.lower() not in ["off", "unavailable"]:
                prog_str = f"{prog_val:.0f}%"
                ShapePainter._draw_pill_label(
                    painter, cam_rect, prog_str, bg_pix, x_bg, y_bg, position='top-right', force_dark=True
                )

            if button.span_x > 2 or button.span_y > 2:
                btn_name = button.config.get("label", button.config.get("name", "3D Printer"))
                ShapePainter._draw_pill_label(
                    painter, cam_rect, btn_name, bg_pix, x_bg, y_bg, position='top-left', force_dark=True
                )
            
            # 2. Floating frosted pills at the bottom (state left, temps right)
            from ui.utils.glass_effect import draw_frosted_pill

            pill_h     = 28
            pill_y     = h - pill_h - 12
            pad_x      = 12
            inter_pill = 8

            is_offline = printer_state.lower() in ("off", "unavailable")

            # --- Right pill: nozzle + bed (icons + values) — sized first; takes priority ---
            icon_font = get_mdi_font(13)
            val_font  = QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold)
            fm_icon   = QFontMetrics(icon_font)
            fm_val    = QFontMetrics(val_font)

            noz_icon = get_icon('printer-3d-nozzle')
            bed_icon = get_icon('square-medium')

            gap = 6
            sep = 12
            temps_content_w = (
                fm_icon.horizontalAdvance(noz_icon) + gap + fm_val.horizontalAdvance(nozzle_str)
                + sep
                + fm_icon.horizontalAdvance(bed_icon) + gap + fm_val.horizontalAdvance(bed_str)
            )
            temps_pill_w = 0 if is_offline else min(temps_content_w + 24, w - pad_x * 2)

            # --- Left pill: state — only if there's room left after temps ---
            state_label  = printer_state.capitalize() if printer_state else ""
            state_font   = QFont(SYSTEM_FONT, 10, QFont.Weight.DemiBold)
            fm_state     = QFontMetrics(state_font)
            state_text_w = fm_state.horizontalAdvance(state_label.upper()) if state_label else 0
            ideal_state_w = max(56, state_text_w + 24) if state_label else 0

            remaining_w  = w - pad_x * 2 - (temps_pill_w + inter_pill if temps_pill_w else 0)
            state_pill_w = min(ideal_state_w, remaining_w) if remaining_w >= 56 else 0

            # Draw state pill
            if state_pill_w:
                state_rect = QRectF(pad_x, pill_y, state_pill_w, pill_h)
                state_text_color = draw_frosted_pill(painter, state_rect, bg_pix, x_bg, y_bg, force_dark=True)
                elided = fm_state.elidedText(state_label.upper(), Qt.TextElideMode.ElideRight, int(state_pill_w - 16))
                painter.setFont(state_font)
                painter.setPen(state_text_color)
                painter.drawText(state_rect, Qt.AlignmentFlag.AlignCenter, elided)

            # Draw temps pill
            if temps_pill_w > 0:
                temps_rect = QRectF(w - temps_pill_w - pad_x, pill_y, temps_pill_w, pill_h)
                temps_text_color = draw_frosted_pill(painter, temps_rect, bg_pix, x_bg, y_bg, force_dark=True)

                cx = temps_rect.x() + (temps_rect.width() - temps_content_w) / 2
                painter.setPen(temps_text_color)

                painter.setFont(icon_font)
                nw = fm_icon.horizontalAdvance(noz_icon)
                painter.drawText(QRectF(cx, pill_y, nw, pill_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, noz_icon)
                cx += nw + gap

                painter.setFont(val_font)
                nvw = fm_val.horizontalAdvance(nozzle_str)
                painter.drawText(QRectF(cx, pill_y, nvw, pill_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, nozzle_str)
                cx += nvw + sep

                painter.setFont(icon_font)
                bw = fm_icon.horizontalAdvance(bed_icon)
                painter.drawText(QRectF(cx, pill_y, bw, pill_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, bed_icon)
                cx += bw + gap

                painter.setFont(val_font)
                bvw = fm_val.horizontalAdvance(bed_str)
                painter.drawText(QRectF(cx, pill_y, bvw, pill_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, bed_str)
            
        elif is_wide:
            # === 2x1: Wide layout ===
            # Icon/Ring Left, Stats Right
            w = rect.width()
            h = rect.height()
            
            # Left Icon (with circular progress if printing)
            icon_size = 40
            icon_x = 24
            icon_y = (h - icon_size) // 2
            
            painter.setFont(get_mdi_font(28))
            painter.setPen(accent_color)
            painter.drawText(QRectF(icon_x, icon_y, icon_size, icon_size), Qt.AlignmentFlag.AlignCenter, icon)
            
            # Text area on the right
            text_x = icon_x + icon_size + 16
            
            # State Title
            state_font = QFont(SYSTEM_FONT, 12, QFont.Weight.Bold)
            painter.setFont(state_font)
            painter.setPen(text_color)
            
            avail_width = w - text_x - 16
            fm = QFontMetrics(state_font)
            elided_state = fm.elidedText(printer_state, Qt.TextElideMode.ElideRight, int(avail_width))
            
            painter.drawText(QRectF(text_x, 16, avail_width, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, elided_state)
            
            # Sub stats
            painter.setFont(QFont(SYSTEM_FONT, 10, QFont.Weight.Medium))
            painter.setPen(dim_text_color)
            stats_str = f"N: {nozzle_str}  B: {bed_str}"
            painter.drawText(QRectF(text_x, 44, w - text_x - 16, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, stats_str)
            
            # Progress Bar Bottom
            ShapePainter.draw_bottom_bar(painter, QRectF(0, 0, w, h), float(progress), 100.0, accent_color)

        elif button.span_y >= 2 and button.span_x == 1:
            # === 1x2: Tall layout ===
            w = rect.width()
            h = rect.height()
            
            # Icon in the identical spot as a 1x1 (top half)
            top_half = QRectF(0, 0, w, 80)
            painter.setFont(get_mdi_font(40))
            painter.setPen(accent_color)
            painter.drawText(top_half, Qt.AlignmentFlag.AlignCenter, icon)
            
            # State Title
            state_font = QFont(SYSTEM_FONT, 12, QFont.Weight.Bold)
            painter.setFont(state_font)
            painter.setPen(text_color)
            
            fm = QFontMetrics(state_font)
            elided_state = fm.elidedText(printer_state.capitalize(), Qt.TextElideMode.ElideRight, int(w - 16))
            
            painter.drawText(QRectF(0, 90, w, 24), Qt.AlignmentFlag.AlignCenter, elided_state)
            
            # Progress %
            try: prog_val = float(progress)
            except (TypeError, ValueError): prog_val = 0.0
                
            if printer_state.lower() not in ["off", "unavailable"]:
                 painter.setFont(QFont(SYSTEM_FONT, 11, QFont.Weight.Medium))
                 painter.setPen(dim_text_color)
                 painter.drawText(QRectF(0, 116, w, 20), Qt.AlignmentFlag.AlignCenter, f"{prog_val:.0f}%")
                 
            # Progress Bar Bottom
            ShapePainter.draw_bottom_bar(painter, QRectF(0, 0, w, h), prog_val, 100.0, accent_color)
            
        else:
            # === 1x1: Compact ===
            w = rect.width()
            h = rect.height()
            # Just the icon centered, color coded
            painter.setFont(get_mdi_font(40))
            painter.setPen(accent_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, icon)
            
            try: prog_val = float(progress)
            except (TypeError, ValueError): prog_val = 0.0
            
            if prog_val > 0 and prog_val < 100 and printer_state.lower() not in ["off", "unavailable"]:
                 # Small progress indicator text below icon
                 painter.setFont(QFont(SYSTEM_FONT, 10, QFont.Weight.Bold))
                 painter.setPen(text_color)
                 painter.drawText(QRectF(0, h/2 + 20, w, 20), Qt.AlignmentFlag.AlignCenter, f"{prog_val:.0f}%")

        painter.end()

"""OverlayManager part for the 3D printer overlay."""

from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QColor
from ui.constants import TWO_ROW_MIN_HEIGHT


class PrinterOverlayMixin:
    """OverlayManager part for the 3D printer overlay."""

    def _push_printer_state(self):
        """Consolidate entities into a virtual state for the printer overlay."""
        if not self._active_printer_config: return None
        
        cfg = self._active_printer_config
        
        state_data = self._entity_states.get(cfg.get('printer_state_entity'), {})
        primary_state = state_data.get('state', 'unknown')
        attrs = dict(state_data.get('attributes', {}))
        
        # Mix in Nozzle
        noz_data = self._entity_states.get(cfg.get('printer_nozzle_entity'), {})
        attrs['hotend_actual'] = noz_data.get('attributes', {}).get('actual_temperature', noz_data.get('state', 0.0))
        noz_unit = noz_data.get('attributes', {}).get('unit_of_measurement')
        if noz_unit:
            attrs['temperature_unit'] = noz_unit
        
        noz_target_ent = cfg.get('printer_nozzle_target_entity')
        if noz_target_ent:
            noz_tgt_data = self._entity_states.get(noz_target_ent, {})
            try:
                attrs['hotend_target'] = float(noz_tgt_data.get('state', 0.0))
            except (ValueError, TypeError):
                attrs['hotend_target'] = 0.0
        else:
            attrs['hotend_target'] = noz_data.get('attributes', {}).get('target_temperature', noz_data.get('attributes', {}).get('temperature', 0.0))
        
        # Mix in Bed
        bed_data = self._entity_states.get(cfg.get('printer_bed_entity'), {})
        attrs['bed_actual'] = bed_data.get('attributes', {}).get('actual_temperature', bed_data.get('state', 0.0))
        
        bed_target_ent = cfg.get('printer_bed_target_entity')
        if bed_target_ent:
            bed_tgt_data = self._entity_states.get(bed_target_ent, {})
            try:
                attrs['bed_target'] = float(bed_tgt_data.get('state', 0.0))
            except (ValueError, TypeError):
                attrs['bed_target'] = 0.0
        else:
            attrs['bed_target'] = bed_data.get('attributes', {}).get('target_temperature', bed_data.get('attributes', {}).get('temperature', 0.0))
        
        # Ensure progress is there
        prog_ent = cfg.get('printer_progress_entity')
        if prog_ent:
            prog_val = self._entity_states.get(prog_ent, {}).get('state', 0.0)
            try:
                attrs['progress'] = float(prog_val)
            except (ValueError, TypeError):
                attrs['progress'] = 0.0
        elif 'progress' not in attrs:
            attrs['progress'] = attrs.get('job_percentage', 0.0)
            
        virtual_state = {
            'state': primary_state,
            'attributes': attrs
        }
        self.printer_overlay.update_state(virtual_state)
        return virtual_state

    # ==========================
    # 3D Printer Logic
    # ==========================

    def start_printer(self, slot: int, global_rect: QRect, config: dict):
        if self._queue_or_start_overlay(self.start_printer, slot, global_rect, config):
            return

        if not config: return
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        self._active_printer_entity = entity_id
        self._active_printer_config = config
        
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        self._overlay_state[self.printer_overlay]['source'] = source_btn

        # Push initial camera if available on button
        if source_btn and hasattr(source_btn, '_last_camera_pixmap') and source_btn._last_camera_pixmap:
            self.printer_overlay.set_camera_pixmap(source_btn._last_camera_pixmap)
        
        # Colors
        if self.theme_manager:
            base_color = QColor(self.theme_manager.get_colors().get('base', '#2d2d2d'))
        else:
            base_color = QColor("#2d2d2d")
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#FF6D00")
        
        if self.theme_manager and not button_color:
            cols = self.theme_manager.get_colors()
            accent_color = QColor(cols.get('accent', '#FF6D00'))
            
        start_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())
        
        # Use existing shared logic but with 'printer' overlay_type
        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='printer')
        
        # We want the printer overlay to be as big as possible (at least 2x4 usually)
        min_height = TWO_ROW_MIN_HEIGHT
        if target_rect.height() < min_height:
            target_rect.setHeight(min_height)
            
            safe_bottom = self.parent_widget.height() - 40 
            if target_rect.bottom() > safe_bottom:
                 if source_btn:
                     src_pos = source_btn.mapTo(self.parent_widget, QPoint(0, 0))
                     src_bottom = src_pos.y() + source_btn.height()
                     target_rect.moveBottom(src_bottom)
                 else:
                     diff = target_rect.bottom() - safe_bottom
                     target_rect.moveTop(target_rect.top() - diff)

            self._add_covered_siblings(self.printer_overlay, source_btn, target_rect)

        # Consolidate entities into a virtual state for the printer overlay
        virtual_state = self._push_printer_state()
        
        self.printer_overlay.set_border_effect(self._border_effect)
        self.printer_overlay.start_morph(
            start_rect, target_rect, config.get('label', '3D Printer'),
            color=accent_color, base_color=base_color,
            current_state=virtual_state
        )

    def on_printer_action(self, action: str):
        if not self._active_printer_config: return
        
        if action in ('pause', 'resume'):
            entity = self._active_printer_config.get('printer_pause_entity')
            if entity:
                self._emit_service({
                    "service": "button.press",
                    "entity_id": entity
                })
        elif action == 'stop':
            entity = self._active_printer_config.get('printer_stop_entity')
            if entity:
                self._emit_service({
                    "service": "button.press",
                    "entity_id": entity
                })

    def on_printer_finished(self):
        self._active_printer_entity = None
        self._active_printer_config = None
        self._restore_overlay_state(self.printer_overlay)
        self.parent_widget.activateWindow()
        self._check_pending_actions()

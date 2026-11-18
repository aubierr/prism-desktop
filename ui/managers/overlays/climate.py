"""OverlayManager part for the climate (thermostat) overlay."""

from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QColor
from ui.constants import TWO_ROW_MIN_HEIGHT
from core.temperature_utils import convert_temperature, convert_temperature_delta, normalize_temperature_unit, preference_to_unit


class ClimateOverlayMixin:
    """OverlayManager part for the climate (thermostat) overlay."""

    # ==========================
    # Climate Logic
    # ==========================
    
    def start_climate(self, slot: int, global_rect: QRect, config: dict):
        if self._queue_or_start_overlay(self.start_climate, slot, global_rect, config):
            return

        if not config: return
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        self._active_climate_entity = entity_id
        
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        curr_temp = 20.0
        if source_btn and hasattr(source_btn, '_value'):
             try:
                 temp_str = str(source_btn._value).replace('°', '').strip()
                 curr_temp = float(temp_str)
             except ValueError: pass
             
        # Colors
        if self.theme_manager:
            base_color = QColor(self.theme_manager.get_colors().get('base', '#2d2d2d'))
        else:
            base_color = QColor("#2d2d2d")
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#EA4335")
        
        if self.theme_manager and not button_color:
            cols = self.theme_manager.get_colors()
            accent_color = QColor(cols.get('accent', '#EA4335'))
            
        start_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())
        
        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='climate')
        
        # Enforce Minimum Height (2 Rows) for Climate Overlay
        min_height = TWO_ROW_MIN_HEIGHT
        if target_rect.height() < min_height:
            target_rect.setHeight(min_height)
            
            # Check if it goes off-screen (bottom)
            # Use parent widget height minus footer area (approx 40px) as safe zone
            safe_bottom = self.parent_widget.height() - 40 
            
            if target_rect.bottom() > safe_bottom:
                 # Shift up so the BOTTOM of the overlay aligns with the BOTTOM of the source button
                 # This makes it expand UPWARDS from the button
                 if source_btn:
                     src_pos = source_btn.mapTo(self.parent_widget, QPoint(0, 0))
                     src_bottom = src_pos.y() + source_btn.height()
                     target_rect.moveBottom(src_bottom)
                 else:
                     # Fallback: Just shift it on screen
                     diff = target_rect.bottom() - safe_bottom
                     target_rect.moveTop(target_rect.top() - diff)

            self._add_covered_siblings(self.climate_overlay, source_btn, target_rect)

        
        current_state = self._entity_states.get(entity_id, {})
        attrs = current_state.get('attributes', {})
        source_unit = attrs.get('temperature_unit')
        display_unit = preference_to_unit(self._temperature_unit_preference, fallback=source_unit)
        current_temp = attrs.get('temperature', curr_temp)
        converted_temp = convert_temperature(current_temp, source_unit, display_unit)
        if converted_temp is not None:
            curr_temp = converted_temp

        min_temp = attrs.get('min_temp', 5.0)
        max_temp = attrs.get('max_temp', 35.0)
        temp_step = attrs.get('target_temp_step', 0.5)
        converted_min = convert_temperature(min_temp, source_unit, display_unit)
        converted_max = convert_temperature(max_temp, source_unit, display_unit)
        converted_step = convert_temperature_delta(temp_step, source_unit, display_unit)
        self.climate_overlay.configure_temperature_range(
            converted_min if converted_min is not None else 5.0,
            converted_max if converted_max is not None else 35.0,
            converted_step if converted_step is not None else 0.5,
            normalize_temperature_unit(display_unit),
        )
        
        self.climate_overlay.set_border_effect(self._border_effect)
        self.climate_overlay.start_morph(
            start_rect, target_rect, curr_temp, config.get('label', 'Climate'),
            color=accent_color, base_color=base_color,
            current_state=current_state
        )
        self.climate_timer.start()

    def on_climate_value_changed(self, value):
        self._pending_climate_val = value

    def process_pending_climate(self):
        if self._pending_climate_val is None or not self._active_climate_entity:
            return
        
        val = self._pending_climate_val
        self._pending_climate_val = None

        attrs = self._entity_states.get(self._active_climate_entity, {}).get('attributes', {})
        source_unit = attrs.get('temperature_unit')
        display_unit = preference_to_unit(self._temperature_unit_preference, fallback=source_unit)
        service_temp = convert_temperature(val, display_unit, source_unit)
        if service_temp is None:
            service_temp = val
        
        self._emit_service({
            "service": "climate.set_temperature",
            "entity_id": self._active_climate_entity,
            "service_data": {"temperature": service_temp}
        })

    def on_climate_mode_changed(self, mode):
        if self._active_climate_entity:
            self._emit_service({
                "service": "climate.set_hvac_mode",
                "entity_id": self._active_climate_entity,
                "service_data": {"hvac_mode": mode}
            })

    def on_climate_fan_changed(self, mode):
        if self._active_climate_entity:
             self._emit_service({
                "service": "climate.set_fan_mode",
                "entity_id": self._active_climate_entity,
                "service_data": {"fan_mode": mode}
            })

    def on_climate_finished(self):
        self.climate_timer.stop()
        self._pending_climate_val = None
        self._active_climate_entity = None
        
        self._restore_overlay_state(self.climate_overlay)
            
        self.parent_widget.activateWindow()
        self._check_pending_actions()

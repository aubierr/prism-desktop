"""OverlayManager part for the weather forecast overlay."""

from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QColor
from ui.constants import TWO_ROW_MIN_HEIGHT


class WeatherOverlayMixin:
    """OverlayManager part for the weather forecast overlay."""

    # ==========================
    # Weather Logic
    # ==========================

    def start_weather(self, slot: int, global_rect: QRect, config: dict, forecasts: list):
        if self._queue_or_start_overlay(self.start_weather, slot, global_rect, config, forecasts):
            return

        if not config: return
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        self._active_weather_entity = entity_id
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        
        if self.theme_manager:
            base_color = QColor(self.theme_manager.get_colors().get('base', '#2d2d2d'))
        else:
            base_color = QColor("#2d2d2d")
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#4285F4")
        
        if self.theme_manager and not button_color:
            cols = self.theme_manager.get_colors()
            accent_color = QColor(cols.get('accent', '#4285F4'))
            
        start_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())
        
        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='weather')
        
        # Enforce Minimum Height (2 Rows) for Weather Overlay
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

            self._add_covered_siblings(self.weather_overlay, source_btn, target_rect)

        current_state = self._entity_states.get(entity_id, {})
        
        self.weather_overlay.set_border_effect(self._border_effect)
        self.weather_overlay.start_morph(
            start_rect, target_rect, current_state, forecasts, config.get('label', 'Weather'),
            color=accent_color, base_color=base_color
        )

    def on_weather_finished(self):
        self._active_weather_entity = None
        self._restore_overlay_state(self.weather_overlay)
        self.parent_widget.activateWindow()
        self._check_pending_actions()

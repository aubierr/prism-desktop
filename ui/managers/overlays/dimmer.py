"""OverlayManager part for the dimmer and volume overlay."""

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor


class DimmerOverlayMixin:
    """OverlayManager part for the dimmer and volume overlay."""

    # ==========================
    # Dimmer / Volume Logic
    # ==========================

    def start_dimmer(self, slot: int, global_rect: QRect, config: dict):
        """Start the dimmer morph sequence."""
        if self._queue_or_start_overlay(self.start_dimmer, slot, global_rect, config):
            return

        if not config: return
        
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        self._active_dimmer_entity = entity_id
        self._active_dimmer_type = config.get('type', 'switch')
        
        # Calculate Start Value
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        current_val = 0
        
        state_obj = self._entity_states.get(entity_id, {})
        attrs = state_obj.get('attributes', {})
        
        if self._active_dimmer_type == 'curtain':
            pos = attrs.get('current_position')
            if pos is not None:
                current_val = int(pos)
            elif source_btn:
                current_val = 100 if source_btn._state == "open" else 0
        else:
            bri = attrs.get('brightness')
            if bri is not None:
                current_val = int((bri / 255.0) * 100)
            elif source_btn and hasattr(source_btn, '_state'):
                current_val = 100 if source_btn._state == "on" else 0
        
        # Colors
        if self.theme_manager:
            base_color = QColor(self.theme_manager.get_colors().get('base', '#2d2d2d'))
        else:
            base_color = QColor("#2d2d2d")
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#FFD700")
        
        if self.theme_manager and not button_color:
            cols = self.theme_manager.get_colors()
            accent_color = QColor(cols.get('accent', '#FFD700'))
            
        # Geometries
        start_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())
        
        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='dimmer')
        
        # Start
        self.dimmer_overlay.set_border_effect(self._border_effect)
        
        label = config.get('label', 'Dimmer')

        self.dimmer_overlay.start_morph(
            start_rect, target_rect, current_val, label,
            color=accent_color, base_color=base_color
        )
        self.dimmer_timer.start()

    def start_volume(self, slot: int, global_rect: QRect, config: dict):
        """Start volume slider using dimmer overlay."""
        if self._queue_or_start_overlay(self.start_volume, slot, global_rect, config):
            return

        if not config: return
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        if not source_btn: return

        current_vol = source_btn._media_state.get('attributes', {}).get('volume_level', 0.5)
        start_pct = int(current_vol * 100)
        
        self._active_dimmer_entity = entity_id
        self._active_dimmer_type = 'media_player'
        self._pending_dimmer_val = None
        self._final_dimmer_val = None
        
        # Geometries
        local_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(local_rect, global_rect.size())
        
        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='dimmer')
        
        # Color
        accent = config.get('color')
        color = QColor(accent) if accent else QColor("#4285F4")
        
        self.dimmer_overlay.set_border_effect(self._border_effect)
        self.dimmer_overlay.start_morph(
            start_rect, target_rect, start_pct, "Volume",
            color=color, base_color=QColor(self.theme_manager.get_colors().get('base', '#2d2d2d')) if self.theme_manager else QColor("#2d2d2d")
        )
        if not self.dimmer_timer.isActive():
            self.dimmer_timer.start()

    def on_dimmer_value_changed(self, value):
        self._pending_dimmer_val = value

    def process_pending_dimmer(self):
        if self._pending_dimmer_val is None or not self._active_dimmer_entity:
            return
            
        val = self._pending_dimmer_val
        self._pending_dimmer_val = None
        self._final_dimmer_val = val
        
        dimmer_type = getattr(self, '_active_dimmer_type', 'switch')
        
        if dimmer_type in ['curtain', 'media_player']:
            # Send only on release
            return
            
        if not self._live_dimming:
            return
            
        # Live update for lights
        self._emit_service({
            "service": "light.turn_on",
            "entity_id": self._active_dimmer_entity,
            "service_data": {"brightness_pct": val},
            "skip_debounce": True
        })

    def on_dimmer_finished(self):
        self.dimmer_timer.stop()
        
        final_val = getattr(self, '_final_dimmer_val', None)
        dimmer_type = getattr(self, '_active_dimmer_type', 'switch')
        entity_id = self._active_dimmer_entity
        
        if final_val is not None and entity_id:
            if dimmer_type == 'curtain':
                self._emit_service({
                    "service": "cover.set_cover_position",
                    "entity_id": entity_id,
                    "service_data": {"position": final_val}
                })
            elif dimmer_type == 'media_player':
                self._emit_service({
                    "service": "media_player.volume_set",
                    "entity_id": entity_id,
                    "service_data": {"volume_level": final_val / 100.0},
                    "skip_debounce": True
                })
            # Lights are usually handled by live update, but send one final to be sure? 
            # Or if live dimming was off.
            elif dimmer_type != 'curtain' and (not self._live_dimming or final_val is not None):
                 self._emit_service({
                    "service": "light.turn_on",
                    "entity_id": entity_id,
                    "service_data": {"brightness_pct": final_val},
                    "skip_debounce": True
                })
        
        self._reset_dimmer_state()
        self.parent_widget.activateWindow()

    def _reset_dimmer_state(self):
        self._active_dimmer_entity = None
        self._active_dimmer_type = None
        self._pending_dimmer_val = None
        self._final_dimmer_val = None
        
        self._restore_overlay_state(self.dimmer_overlay)
            
        self._check_pending_actions()

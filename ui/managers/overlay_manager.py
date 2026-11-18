from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRect, QPoint, QEvent
from PyQt6.QtWidgets import QWidget

from ui.widgets.overlays import DimmerOverlay, ClimateOverlay, PrinterOverlay, WeatherOverlay, CameraOverlay, MowerOverlay, VacuumOverlay, AlarmOverlay
from ui.constants import BUTTON_HEIGHT, BUTTON_SPACING, BUTTON_WIDTH
from ui.managers.overlays.dimmer import DimmerOverlayMixin
from ui.managers.overlays.climate import ClimateOverlayMixin
from ui.managers.overlays.printer import PrinterOverlayMixin
from ui.managers.overlays.robot import RobotOverlayMixin
from ui.managers.overlays.alarm import AlarmOverlayMixin
from ui.managers.overlays.weather import WeatherOverlayMixin
from ui.managers.overlays.camera import CameraOverlayMixin


class OverlayManager(
    DimmerOverlayMixin, ClimateOverlayMixin, PrinterOverlayMixin, RobotOverlayMixin,
    AlarmOverlayMixin, WeatherOverlayMixin, CameraOverlayMixin, QObject,
):
    """
    Manages overlay widgets (Dimmer, Climate) and their interactions.
    Decouples logic from Dashboard.

    Shared plumbing lives here; each overlay type's start/finish handlers
    live in a mixin under ui/managers/overlays/.
    """
    
    # Signals
    service_request = pyqtSignal(dict)  # Emit service calls (to be connected to HAClient or Dashboard)
    morph_changed = pyqtSignal(float) # Optional: if dashboard needs to know global animation progress
    
    def __init__(self, parent: QWidget, theme_manager=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.theme_manager = theme_manager
        
        self.buttons = [] # Reference to dashboard buttons
        self._entity_states = {} # Reference or copy of states
        
        # Overlays
        self.dimmer_overlay = DimmerOverlay(parent)
        self.dimmer_overlay.value_changed.connect(self.on_dimmer_value_changed)
        self.dimmer_overlay.finished.connect(self.on_dimmer_finished)
        self.dimmer_overlay.morph_changed.connect(self.on_morph_changed)
        
        self.climate_overlay = ClimateOverlay(parent)
        self.climate_overlay.value_changed.connect(self.on_climate_value_changed)
        self.climate_overlay.mode_changed.connect(self.on_climate_mode_changed)
        self.climate_overlay.fan_changed.connect(self.on_climate_fan_changed)
        self.climate_overlay.finished.connect(self.on_climate_finished)
        self.climate_overlay.morph_changed.connect(self.on_morph_changed)
        
        self.printer_overlay = PrinterOverlay(parent)
        self.printer_overlay.action_requested.connect(self.on_printer_action)
        self.printer_overlay.finished.connect(self.on_printer_finished)
        self.printer_overlay.morph_changed.connect(self.on_morph_changed)
        
        self.weather_overlay = WeatherOverlay(parent)
        self.weather_overlay.finished.connect(self.on_weather_finished)
        self.weather_overlay.morph_changed.connect(self.on_morph_changed)
        
        self.camera_overlay = CameraOverlay(parent)
        self.camera_overlay.finished.connect(self.on_camera_finished)
        self.camera_overlay.morph_changed.connect(self.on_morph_changed)

        self.mower_overlay = MowerOverlay(parent)
        self.mower_overlay.action_requested.connect(self.on_mower_action)
        self.mower_overlay.finished.connect(self.on_mower_finished)
        self.mower_overlay.morph_changed.connect(self.on_morph_changed)

        self.vacuum_overlay = VacuumOverlay(parent)
        self.vacuum_overlay.action_requested.connect(self.on_vacuum_action)
        self.vacuum_overlay.finished.connect(self.on_vacuum_finished)
        self.vacuum_overlay.morph_changed.connect(self.on_morph_changed)

        self.alarm_overlay = AlarmOverlay(parent)
        self.alarm_overlay.action_requested.connect(self.on_alarm_action)
        self.alarm_overlay.finished.connect(self.on_alarm_finished)
        self.alarm_overlay.morph_changed.connect(self.on_morph_changed)
        self.alarm_overlay.keypad_toggled.connect(self.on_alarm_keypad_toggled)

        # Per-overlay state: siblings faded by the overlay, and the source button it morphed from
        self._overlay_state = {
            overlay: {'siblings': [], 'source': None}
            for overlay in (
                self.dimmer_overlay, self.climate_overlay, self.printer_overlay,
                self.weather_overlay, self.camera_overlay, self.mower_overlay, self.vacuum_overlay,
                self.alarm_overlay,
            )
        }

        # State Tracking
        self._active_dimmer_entity = None
        self._active_dimmer_type = None
        self._pending_dimmer_val = None
        self._final_dimmer_val = None

        self._active_climate_entity = None
        self._pending_climate_val = None

        self._active_printer_entity = None
        self._active_printer_config = None

        self._active_weather_entity = None
        self._active_camera_entity = None
        self._active_mower_entity = None
        self._active_vacuum_entity = None
        self._active_alarm_entity = None

        # Throttling Timers
        self.dimmer_timer = QTimer(self)
        self.dimmer_timer.setInterval(100)
        self.dimmer_timer.timeout.connect(self.process_pending_dimmer)
        
        self.climate_timer = QTimer(self)
        self.climate_timer.setInterval(500)
        self.climate_timer.timeout.connect(self.process_pending_climate)
        
        self._border_effect = 'Rainbow'
        self._live_dimming = True
        self._pending_open_action = None
        self._temperature_unit_preference = "celsius"

        parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.parent_widget and event.type() == QEvent.Type.Resize:
            self.close_all_overlays()
        return False

    def _emit_service(self, request: dict):
        """Forward an overlay's service call to the app.

        These are deliberate, distinct actions (a temperature step, then a mode,
        then a fan speed...), not accidental double-clicks, so they bypass the
        per-entity click debounce that would otherwise swallow the later ones.
        """
        request.setdefault("skip_debounce", True)
        self.service_request.emit(request)

    def any_overlay_open(self) -> bool:
        """Return True if any overlay is currently visible."""
        return (self.dimmer_overlay.isVisible() or
                self.climate_overlay.isVisible() or
                self.printer_overlay.isVisible() or
                self.weather_overlay.isVisible() or
                self.camera_overlay.isVisible() or
                self.mower_overlay.isVisible() or
                self.vacuum_overlay.isVisible() or
                self.alarm_overlay.isVisible())

    def close_all_overlays_animated(self):
        """Trigger close_morph on all visible overlays instead of instant hide."""
        if self.dimmer_overlay.isVisible() and not getattr(self.dimmer_overlay, '_is_closing', False):
            self.dimmer_overlay.close_morph()
        if self.climate_overlay.isVisible() and not getattr(self.climate_overlay, '_is_closing', False):
            self.climate_overlay.close_morph()
        if self.printer_overlay.isVisible() and not getattr(self.printer_overlay, '_is_closing', False):
            self.printer_overlay.close_morph()
        if self.weather_overlay.isVisible() and not getattr(self.weather_overlay, '_is_closing', False):
            self.weather_overlay.close_morph()
        if self.camera_overlay.isVisible() and not getattr(self.camera_overlay, '_is_closing', False):
            self.camera_overlay.close_morph()
        if self.mower_overlay.isVisible() and not getattr(self.mower_overlay, '_is_closing', False):
            self.mower_overlay.close_morph()
        if self.vacuum_overlay.isVisible() and not getattr(self.vacuum_overlay, '_is_closing', False):
            self.vacuum_overlay.close_morph()
        if self.alarm_overlay.isVisible() and not getattr(self.alarm_overlay, '_is_closing', False):
            self.alarm_overlay.close_morph()

    def _queue_or_start_overlay(self, method, slot, *args):
        """
        Check if any overlay is open. If so, animate them closed and queue this method.
        Returns True if the method was queued or discarded (caller should return), False if safe to run now.
        """
        if self.any_overlay_open():
            active_btn = None
            for overlay, state in self._overlay_state.items():
                if overlay.isVisible() and not getattr(overlay, '_is_closing', False):
                    active_btn = state['source']
                    break

            if active_btn and active_btn.slot == slot:
                # Toggle off the current overlay, don't reopen
                self.close_all_overlays_animated()
                return True
                
            self._pending_open_action = lambda: method(slot, *args)
            self.close_all_overlays_animated()
            return True
            
        return False

    def _check_pending_actions(self):
        """Run pending open action after overlays finish closing."""
        if self._pending_open_action and not self.any_overlay_open():
            action = self._pending_open_action
            self._pending_open_action = None
            action()

    def close_all_overlays(self):
        """Instantly hide any active overlay. Called before navigating away from grid."""
        if self.dimmer_overlay.isVisible():
            self.dimmer_overlay.hide()
            self.on_dimmer_finished()
        if self.climate_overlay.isVisible():
            self.climate_overlay.hide()
            self.on_climate_finished()
        if self.printer_overlay.isVisible():
            self.printer_overlay.hide()
            self.on_printer_finished()
        if self.weather_overlay.isVisible():
            self.weather_overlay.hide()
            self.on_weather_finished()
        if self.camera_overlay.isVisible():
            self.camera_overlay.hide()
            self.on_camera_finished()
        if self.mower_overlay.isVisible():
            self.mower_overlay.hide()
            self.on_mower_finished()
        if self.vacuum_overlay.isVisible():
            self.vacuum_overlay.hide()
            self.on_vacuum_finished()
        if self.alarm_overlay.isVisible():
            self.alarm_overlay.hide()
            self.on_alarm_finished()

    def update_buttons(self, buttons: list):
        """Update reference to buttons."""
        self.buttons = buttons

    def update_states(self, states: dict):
        """Update reference to entity states."""
        self._entity_states = states
        
    def update_entity_state(self, entity_id: str, state: dict):
        """Update a single entity's state and notify active overlays."""
        self._entity_states[entity_id] = state
        
        # Notify active printer overlay if any of its entities changed
        if self.printer_overlay.isVisible() and self._active_printer_config:
            cfg = self._active_printer_config
            relevant_entities = [
                cfg.get('printer_state_entity'),
                cfg.get('printer_nozzle_entity'),
                cfg.get('printer_nozzle_target_entity'),
                cfg.get('printer_bed_entity'),
                cfg.get('printer_bed_target_entity'),
                cfg.get('printer_progress_entity')
            ]
            if entity_id in relevant_entities:
                self._push_printer_state()
                
        if self.climate_overlay.isVisible() and self._active_climate_entity == entity_id:
            self.climate_overlay.update_state(state)

        if self.weather_overlay.isVisible() and self._active_weather_entity == entity_id:
            self.weather_overlay.update_state(state)

        if self.mower_overlay.isVisible() and self._active_mower_entity == entity_id:
            self.mower_overlay.update_state(state)

        if self.vacuum_overlay.isVisible() and self._active_vacuum_entity == entity_id:
            self.vacuum_overlay.update_state(state)

        if self.alarm_overlay.isVisible() and self._active_alarm_entity == entity_id:
            self.alarm_overlay.update_state(state)

    def update_camera_image(self, entity_id: str, pixmap):
        """Update active overlays with new camera image."""
        if self.printer_overlay.isVisible() and self._active_printer_config:
            if self._active_printer_config.get('printer_camera_entity') == entity_id:
                self.printer_overlay.set_camera_pixmap(pixmap)
        if self.camera_overlay.isVisible() and self._active_camera_entity == entity_id:
            self.camera_overlay.set_camera_pixmap(pixmap)

        
    def set_border_effect(self, effect: str):
        self._border_effect = effect
        self.dimmer_overlay.set_border_effect(effect)
        self.climate_overlay.set_border_effect(effect)
        self.printer_overlay.set_border_effect(effect)
        self.weather_overlay.set_border_effect(effect)
        self.mower_overlay.set_border_effect(effect)
        self.vacuum_overlay.set_border_effect(effect)
        self.alarm_overlay.set_border_effect(effect)

    def set_temperature_unit_preference(self, preference: str):
        self._temperature_unit_preference = preference
        self.weather_overlay.set_temperature_unit_preference(preference)
        self.printer_overlay.set_temperature_unit_preference(preference)


    def _add_covered_siblings(self, overlay, source_btn, target_rect):
        """Append any buttons covered by target_rect to the overlay's sibling list and fade them.

        Coverage is decided purely by actual rect intersection (_fade_opacity_for_coverage),
        so this catches buttons in *any* direction — the overlay's target_rect can be shifted
        up or left to fit the grid, covering buttons above/beside the source button's row.
        """
        state = self._overlay_state[overlay]
        for btn in self.buttons:
            if not btn.isVisible() or btn == source_btn: continue
            if btn in state['siblings']: continue
            btn_pos = btn.mapTo(self.parent_widget, QPoint(0, 0))
            btn_rect = QRect(btn_pos, btn.size())
            opacity = self._fade_opacity_for_coverage(target_rect, btn_rect)
            if opacity < 1.0:
                state['siblings'].append(btn)
                btn.set_opacity(opacity)

    def _restore_overlay_state(self, overlay):
        """Restore opacity for all buttons faded by an overlay, then clear its state."""
        state = self._overlay_state[overlay]
        for btn in state['siblings']:
            btn.set_opacity(1.0)
        if state['source']:
            state['source'].set_opacity(1.0)
        state['siblings'] = []
        state['source'] = None

    @staticmethod
    def _fade_opacity_for_coverage(overlay_rect: QRect, btn_rect: QRect) -> float:
        """Graded opacity: 0.0 if >=50% covered, 0.4 if >=15%, 1.0 otherwise."""
        inter = overlay_rect.intersected(btn_rect)
        if inter.isEmpty():
            return 1.0
        btn_area = btn_rect.width() * btn_rect.height()
        if btn_area == 0:
            return 1.0
        coverage = (inter.width() * inter.height()) / btn_area
        if coverage >= 0.5:
            return 0.0
        if coverage >= 0.15:
            return 0.4
        return 1.0

    def _calculate_target_rect_and_siblings(self, source_btn, slot, overlay_type='dimmer'):
        if not source_btn: return QRect()

        src_pos = source_btn.mapTo(self.parent_widget, QPoint(0, 0))

        # Slot-based row detection — avoids pixel-overlap false positives for span_y>1 buttons
        cols = getattr(self.parent_widget, '_cols', 4)
        src_row = source_btn.slot // cols

        row_buttons = []
        for btn in self.buttons:
            if not btn.isVisible(): continue
            btn_row = btn.slot // cols
            btn_row_end = btn_row + getattr(btn, 'span_y', 1)
            if btn_row < src_row + 1 and btn_row_end > src_row:
                btn_pos = btn.mapTo(self.parent_widget, QPoint(0, 0))
                row_buttons.append((btn, btn_pos))

        _overlay_map = {
            'dimmer': self.dimmer_overlay, 'climate': self.climate_overlay,
            'printer': self.printer_overlay, 'weather': self.weather_overlay,
            'camera': self.camera_overlay, 'mower': self.mower_overlay,
            'vacuum': self.vacuum_overlay, 'alarm': self.alarm_overlay,
        }
        _overlay = _overlay_map.get(overlay_type, self.dimmer_overlay)
        _state = self._overlay_state[_overlay]
        _state['source'] = source_btn
        _state['siblings'] = []
        source_btn.set_opacity(0.0)
            
        # Calculate Rect
        if row_buttons:
            row_buttons.sort(key=lambda x: x[1].x())
            first_btn, first_pos = row_buttons[0]
            last_btn, last_pos = row_buttons[-1]
            
            target_x = first_pos.x()
            target_width = (last_pos.x() + last_btn.width()) - first_pos.x()
            
            from ui.constants import BUTTON_WIDTH, BUTTON_SPACING
            max_6_col_width = (6 * BUTTON_WIDTH) + (5 * BUTTON_SPACING)

            if target_width > max_6_col_width:
                row_width = (last_pos.x() + last_btn.width()) - first_pos.x()
                src_center = src_pos.x() + (source_btn.width() / 2)
                row_center = first_pos.x() + (row_width / 2)
                if src_center > row_center:
                    right_edge = target_x + target_width
                    target_width = max_6_col_width
                    target_x = right_edge - target_width
                else:
                    target_width = max_6_col_width

            max_w = self.parent_widget.width()
            if target_x + target_width > max_w:
                target_width = max_w - target_x
            if target_x < 0:
                target_x = 0

            # Single-row height — overlays that need more vertical space expand via their own loops
            final_rect = QRect(int(target_x), src_pos.y(), int(target_width), BUTTON_HEIGHT)

            filtered_siblings = []
            for btn, btn_pos in row_buttons:
                if btn == source_btn: continue
                btn_rect = QRect(btn_pos, btn.size())
                opacity = self._fade_opacity_for_coverage(final_rect, btn_rect)
                if opacity < 1.0:
                    filtered_siblings.append(btn)
                    btn.set_opacity(opacity)
                else:
                    btn.set_opacity(1.0)
            
            _state['siblings'] = filtered_siblings
                
            return final_rect
        else:
            return QRect(src_pos, source_btn.size())


    # ==========================
    # Shared
    # ==========================
    
    def on_morph_changed(self, progress: float):
        """Update sibling opacity for the overlay that fired this signal."""
        overlay = self.sender()
        state = self._overlay_state.get(overlay)
        if state is None:
            self.morph_changed.emit(progress)
            return

        opacity = 1.0 - (progress * 0.8)
        for btn in state['siblings']:
            btn.set_opacity(opacity)

        if state['source'] and overlay._is_closing:
            state['source'].set_opacity(1.0 - progress)

        self.morph_changed.emit(progress)


    # ==========================
    # Alarm Control Panel Logic
    # ==========================

    # alarm_control_panel supported_features bit -> arm action
    ALARM_FEATURE_BITS = {
        1:  'arm_home',
        2:  'arm_away',
        4:  'arm_night',
        16: 'arm_custom_bypass',
        32: 'arm_vacation',
    }


    # Alarm never needs a full grid-row width — a handful of pill buttons or a 3-column
    # keypad both fit comfortably in 3 columns, so cap it instead of stretching edge to edge.
    ALARM_MAX_WIDTH = (3 * BUTTON_WIDTH) + (2 * BUTTON_SPACING)



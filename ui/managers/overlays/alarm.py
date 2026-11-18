"""OverlayManager part for the alarm panel overlay."""

from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QColor
from ui.constants import BUTTON_HEIGHT, BUTTON_SPACING


class AlarmOverlayMixin:
    """OverlayManager part for the alarm panel overlay."""

    def start_alarm(self, slot: int, global_rect: QRect, config: dict):
        if self._queue_or_start_overlay(self.start_alarm, slot, global_rect, config):
            return

        if not config: return
        entity_id = config.get('entity_id')
        if not entity_id: return

        self._active_alarm_entity = entity_id
        source_btn = next((b for b in self.buttons if b.slot == slot), None)

        # Colors
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

        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='alarm')

        current_state = self._entity_states.get(entity_id, {})
        attrs = current_state.get('attributes', {})

        supported = int(attrs.get('supported_features', 0) or 0)
        modes = [action for bit, action in self.ALARM_FEATURE_BITS.items() if supported & bit]
        self.alarm_overlay.configure_modes(modes)

        code_required = attrs.get('code_format') is not None
        code_arm_required = attrs.get('code_arm_required', True)
        self.alarm_overlay.configure_code(
            code_for_arm=code_required and code_arm_required,
            code_for_disarm=code_required,
        )

        # Open compact like every other overlay — grows on demand if a keypad is needed
        # (see on_alarm_keypad_toggled), so the common "just tap Home/Away" case stays small.
        target_rect = self._size_alarm_rect(source_btn, target_rect, rows=2)

        self.alarm_overlay.set_border_effect(self._border_effect)
        self.alarm_overlay.start_morph(
            start_rect, target_rect, config.get('label', 'Alarm'),
            color=accent_color, base_color=base_color, current_state=current_state
        )

    def _size_alarm_rect(self, source_btn, target_rect: QRect, rows: int) -> QRect:
        """Cap target_rect to a sane width and grow it to fit `rows` of button height,
        shifting on-screen and (re)computing sibling fade against the final rect."""
        state = self._overlay_state[self.alarm_overlay]
        for btn in state['siblings']:
            btn.set_opacity(1.0)
        state['siblings'] = []
        if source_btn:
            source_btn.set_opacity(0.0)

        if target_rect.width() > self.ALARM_MAX_WIDTH:
            row_center = target_rect.x() + target_rect.width() / 2
            if source_btn:
                src_pos = source_btn.mapTo(self.parent_widget, QPoint(0, 0))
                src_center = src_pos.x() + source_btn.width() / 2
            else:
                src_center = row_center
            new_x = target_rect.right() - self.ALARM_MAX_WIDTH + 1 if src_center > row_center else target_rect.x()
            target_rect = QRect(int(new_x), target_rect.y(), int(self.ALARM_MAX_WIDTH), target_rect.height())

        min_height = (BUTTON_HEIGHT * rows) + (BUTTON_SPACING * (rows - 1))
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

        self._add_covered_siblings(self.alarm_overlay, source_btn, target_rect)
        return target_rect

    def on_alarm_keypad_toggled(self, show_keypad: bool):
        """Alarm panel needs to grow (keypad appearing) or shrink back (keypad dismissed)."""
        if not self.alarm_overlay.isVisible():
            return
        state = self._overlay_state[self.alarm_overlay]
        source_btn = state['source']
        slot = source_btn.slot if source_btn else None

        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='alarm')
        target_rect = self._size_alarm_rect(source_btn, target_rect, rows=3 if show_keypad else 2)

        self.alarm_overlay.resize_to(target_rect)

    def on_alarm_action(self, action: str, code: str):
        if not self._active_alarm_entity:
            return
        service_data = {'code': code} if code else {}
        self._emit_service({
            "service": f"alarm_control_panel.alarm_{action}",
            "entity_id": self._active_alarm_entity,
            "service_data": service_data,
        })

    def on_alarm_finished(self):
        self._active_alarm_entity = None
        self._restore_overlay_state(self.alarm_overlay)
        self.parent_widget.activateWindow()
        self._check_pending_actions()

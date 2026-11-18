"""OverlayManager part for the lawn mower and vacuum overlays."""

from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QColor
from ui.constants import TWO_ROW_MIN_HEIGHT


class RobotOverlayMixin:
    """OverlayManager part for the lawn mower and vacuum overlays."""

    # ==========================
    # Lawn Mower Logic
    # ==========================

    def start_mower(self, slot: int, global_rect: QRect):
        if self._queue_or_start_overlay(self.start_mower, slot, global_rect):
            return

        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        if not source_btn or not source_btn.config:
            return
        config = source_btn.config
        entity_id = config.get('entity_id')
        if not entity_id:
            return

        self._active_mower_entity = entity_id

        # Colors
        if self.theme_manager:
            base_color = QColor(self.theme_manager.get_colors().get('base', '#2d2d2d'))
        else:
            base_color = QColor("#2d2d2d")
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#4CAF50")
        if self.theme_manager and not button_color:
            accent_color = QColor(self.theme_manager.get_colors().get('accent', '#4CAF50'))

        start_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())

        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='mower')

        # Enforce 2-row minimum height
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

            self._add_covered_siblings(self.mower_overlay, source_btn, target_rect)

        current_state = self._entity_states.get(entity_id, {})

        self.mower_overlay.set_border_effect(self._border_effect)
        self.mower_overlay.start_morph(
            start_rect, target_rect, config.get('label', 'Mower'),
            color=accent_color, base_color=base_color,
            current_state=current_state
        )

    def on_mower_action(self, action: str):
        if not self._active_mower_entity:
            return
        self._emit_service({
            "service": f"lawn_mower.{action}",
            "entity_id": self._active_mower_entity
        })

    def on_mower_finished(self):
        self._active_mower_entity = None
        self._restore_overlay_state(self.mower_overlay)
        self.parent_widget.activateWindow()
        self._check_pending_actions()

    # ==========================
    # Vacuum Logic
    # ==========================

    def start_vacuum(self, slot: int, global_rect: QRect):
        if self._queue_or_start_overlay(self.start_vacuum, slot, global_rect):
            return

        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        if not source_btn or not source_btn.config:
            return
        config = source_btn.config
        entity_id = config.get('entity_id')
        if not entity_id:
            return

        self._active_vacuum_entity = entity_id

        # Colors
        if self.theme_manager:
            base_color = QColor(self.theme_manager.get_colors().get('base', '#2d2d2d'))
        else:
            base_color = QColor("#2d2d2d")
        button_color = config.get('color')
        accent_color = QColor(button_color) if button_color else QColor("#4CAF50")
        if self.theme_manager and not button_color:
            accent_color = QColor(self.theme_manager.get_colors().get('accent', '#4CAF50'))

        start_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())

        target_rect = self._calculate_target_rect_and_siblings(source_btn, slot, overlay_type='vacuum')

        # Enforce 2-row minimum height
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

            self._add_covered_siblings(self.vacuum_overlay, source_btn, target_rect)

        current_state = self._entity_states.get(entity_id, {})

        self.vacuum_overlay.set_border_effect(self._border_effect)
        self.vacuum_overlay.start_morph(
            start_rect, target_rect, config.get('label', 'Vacuum'),
            color=accent_color, base_color=base_color,
            current_state=current_state
        )

    def on_vacuum_action(self, action: str):
        if not self._active_vacuum_entity:
            return
        self._emit_service({
            "service": f"vacuum.{action}",
            "entity_id": self._active_vacuum_entity
        })

    def on_vacuum_finished(self):
        self._active_vacuum_entity = None
        self._restore_overlay_state(self.vacuum_overlay)
        self.parent_widget.activateWindow()
        self._check_pending_actions()

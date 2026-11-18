"""OverlayManager part for the camera overlay."""

from PyQt6.QtCore import QRect, QPoint
from PyQt6.QtGui import QColor


class CameraOverlayMixin:
    """OverlayManager part for the camera overlay."""

    # ==========================
    # Camera Logic
    # ==========================
    
    def start_camera(self, slot: int, global_rect: QRect, config: dict):
        if self._queue_or_start_overlay(self.start_camera, slot, global_rect, config):
            return

        if not config: return
        entity_id = config.get('entity_id')
        if not entity_id: return
        
        self._active_camera_entity = entity_id
        
        source_btn = next((b for b in self.buttons if b.slot == slot), None)
        self._overlay_state[self.camera_overlay]['source'] = source_btn

        if source_btn and hasattr(source_btn, '_last_camera_pixmap') and source_btn._last_camera_pixmap:
            self.camera_overlay.set_camera_pixmap(source_btn._last_camera_pixmap)
            
        if self.theme_manager:
            base_color = QColor(self.theme_manager.get_colors().get('base', '#2d2d2d'))
        else:
            base_color = QColor("#2d2d2d")
            
        start_rect = self.parent_widget.mapFromGlobal(global_rect.topLeft())
        start_rect = QRect(start_rect, global_rect.size())
        
        from ui.constants import BUTTON_HEIGHT, BUTTON_SPACING, BUTTON_WIDTH
        
        # Calculate max boundaries of the actual grid layout
        visible_rects = []
        for btn in self.buttons:
            if btn.isVisible():
                pos = btn.mapTo(self.parent_widget, QPoint(0, 0))
                visible_rects.append(QRect(pos, btn.size()))
                
        if visible_rects:
            grid_min_x = min(r.left() for r in visible_rects)
            grid_max_x = max(r.right() for r in visible_rects)
            grid_min_y = min(r.top() for r in visible_rects)
            grid_max_y = max(r.bottom() for r in visible_rects)
        else:
            # Fallback if no layout calculated
            grid_min_x = start_rect.left()
            grid_max_x = start_rect.right()
            grid_min_y = start_rect.top()
            grid_max_y = start_rect.bottom()
            
        avail_w = grid_max_x - grid_min_x + 1
        avail_h = grid_max_y - grid_min_y + 1
        
        max_cols = 4
        max_rows = 4
        
        ideal_w = (BUTTON_WIDTH * max_cols) + (BUTTON_SPACING * (max_cols - 1))
        ideal_h = (BUTTON_HEIGHT * max_rows) + (BUTTON_SPACING * (max_rows - 1))
        
        target_w = min(ideal_w, avail_w)
        target_h = min(ideal_h, avail_h)
        
        # Start at top-left of source button
        target_x = start_rect.left()
        target_y = start_rect.top()
        
        # Shift left if hanging over the right edge
        if target_x + target_w > grid_max_x + 1:
            target_x = grid_max_x - target_w + 1
            if target_x < grid_min_x:
                target_x = grid_min_x
                
        # Shift up if hanging over the bottom edge
        if target_y + target_h > grid_max_y + 1:
            target_y = grid_max_y - target_h + 1
            if target_y < grid_min_y:
                target_y = grid_min_y

        target_rect = QRect(target_x, target_y, target_w, target_h)
        
        self._add_covered_siblings(self.camera_overlay, source_btn, target_rect)
                
        self.camera_overlay.set_border_effect(self._border_effect)
        label = config.get('label', 'Camera')
        self.camera_overlay.start_morph(
            start_rect, target_rect, label, base_color=base_color
        )

    def on_camera_finished(self):
        self._active_camera_entity = None
        self._restore_overlay_state(self.camera_overlay)
        self.parent_widget.activateWindow()
        self._check_pending_actions()

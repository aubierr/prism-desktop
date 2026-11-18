from ui.grid_layout_engine import GridLayoutEngine, plan_move


class FakeButton:
    """Stands in for DashboardButton: only what the engine reads."""

    def __init__(self, row=None, col=None, span_x=1, span_y=1, entity="light.x",
                 visible=True, btn_type=None):
        if row is None:
            self.config = {}
        else:
            self.config = {"row": row, "col": col, "span_x": span_x, "span_y": span_y}
            if entity:
                self.config["entity_id"] = entity
            if btn_type:
                self.config["type"] = btn_type
        self.span_x = span_x
        self.span_y = span_y
        self._visible = visible

    def isVisible(self):
        return self._visible


def empties(n):
    return [FakeButton() for _ in range(n)]


def cells(placements):
    return {(r, c) for _, r, c, sy, sx in placements for r in range(r, r + sy) for c in range(c, c + sx)}


# --- calculate_layout -------------------------------------------------------

def test_layout_places_buttons_and_fills_the_rest():
    a, b = FakeButton(0, 0), FakeButton(1, 2, span_x=2)
    engine = GridLayoutEngine(cols=4)
    placements = engine.calculate_layout([a, b] + empties(8), rows=2)

    by_btn = {id(p[0]): p[1:] for p in placements}
    assert by_btn[id(a)] == (0, 0, 1, 1)
    assert by_btn[id(b)] == (1, 2, 1, 2)
    # Every one of the 8 cells is used exactly once.
    assert cells(placements) == {(r, c) for r in range(2) for c in range(4)}
    assert len(placements) == 2 + 5
    assert engine.get_forbidden_cells() == set()


def test_pin_window_counts_as_a_real_button():
    pin = FakeButton(0, 3, entity=None, btn_type="pin_window")
    placements = GridLayoutEngine(cols=4).calculate_layout([pin] + empties(3), rows=1)
    assert (pin, 0, 3, 1, 1) in placements


def test_button_partly_outside_the_grid_is_hidden_and_blocks_its_cells():
    wide = FakeButton(0, 3, span_x=2)  # needs cols 3-4, grid has 0-3
    engine = GridLayoutEngine(cols=4)
    placements = engine.calculate_layout([wide] + empties(4), rows=1)

    assert wide not in [p[0] for p in placements]
    assert engine.get_forbidden_cells() == {(0, 3)}
    # The blocked cell still gets a placeholder so the dashboard can mark it.
    assert (0, 3) in cells(placements)


def test_colliding_button_loses_and_marks_free_cells_forbidden():
    first = FakeButton(0, 0, span_x=2)
    second = FakeButton(0, 1, span_x=2)  # overlaps (0, 1), sorts after first
    engine = GridLayoutEngine(cols=4)
    placements = engine.calculate_layout([second, first] + empties(4), rows=1)

    placed = [p[0] for p in placements]
    assert first in placed and second not in placed
    assert engine.get_forbidden_cells() == {(0, 2)}


# --- find_first_empty_slot ----------------------------------------------------

def test_first_empty_slot_respects_span():
    buttons = [FakeButton(0, 0), FakeButton(0, 2)]
    engine = GridLayoutEngine(cols=4)
    assert engine.find_first_empty_slot(buttons, rows=2) == (0, 1)
    assert engine.find_first_empty_slot(buttons, rows=2, span_x=2) == (1, 0)


def test_first_empty_slot_ignores_hidden_buttons():
    buttons = [FakeButton(0, 0, visible=False)]
    assert GridLayoutEngine(cols=4).find_first_empty_slot(buttons, rows=1) == (0, 0)


def test_first_empty_slot_when_full():
    buttons = [FakeButton(0, c) for c in range(4)]
    assert GridLayoutEngine(cols=4).find_first_empty_slot(buttons, rows=1) == (-1, -1)


# --- find_relocations ---------------------------------------------------------

def test_relocations_empty_when_nothing_overlaps():
    a, b = FakeButton(0, 0), FakeButton(1, 3)
    assert GridLayoutEngine(cols=4).find_relocations(a, 2, 1, [a, b], rows=2) == []


def test_relocations_move_displaced_button_to_first_free_cell():
    a, b = FakeButton(0, 0), FakeButton(0, 1)
    result = GridLayoutEngine(cols=4).find_relocations(a, 2, 1, [a, b], rows=2)
    assert result == [(b, 0, 2)]


def test_relocations_block_resize_when_no_room():
    a, b = FakeButton(0, 0), FakeButton(0, 1)
    others = [FakeButton(0, 2), FakeButton(0, 3)]
    assert GridLayoutEngine(cols=4).find_relocations(a, 2, 1, [a, b] + others, rows=1) is None


# --- plan_move ----------------------------------------------------------------

def cfg(row, col, span_x=1, span_y=1):
    return {"entity_id": "light.x", "row": row, "col": col, "span_x": span_x, "span_y": span_y}


def test_move_to_empty_cell():
    src = cfg(0, 0)
    assert plan_move([src], src, None, 1, 3, cols=4, rows=2) == {id(src): (1, 3)}


def test_move_onto_a_button_swaps_them():
    src, dst = cfg(0, 0), cfg(1, 2)
    moves = plan_move([src, dst], src, dst, 1, 2, cols=4, rows=2)
    assert moves == {id(src): (1, 2), id(dst): (0, 0)}


def test_move_outside_grid_is_refused():
    src = cfg(0, 0, span_x=2)
    assert plan_move([src], src, None, 0, 3, cols=4, rows=1) is None


def test_wide_tile_cannot_land_on_its_neighbour():
    src, other = cfg(1, 0, span_x=2), cfg(0, 1)
    assert plan_move([src, other], src, None, 0, 0, cols=4, rows=2) is None


def test_swap_refused_when_target_does_not_fit_at_source():
    small, wide = cfg(0, 3), cfg(1, 0, span_x=2)
    # wide would go to (0, 3) and stick out of a 4-column grid.
    assert plan_move([small, wide], small, wide, 1, 0, cols=4, rows=2) is None


def test_placeholders_do_not_block_moves():
    src, placeholder = cfg(0, 0), {"row": 0, "col": 1}
    assert plan_move([src, placeholder], src, None, 0, 1, cols=4, rows=1) == {id(src): (0, 1)}

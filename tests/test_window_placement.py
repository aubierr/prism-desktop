from PyQt6.QtCore import QPoint, QRect

from ui import window_placement as wp

LEFT = QRect(0, 0, 1920, 1040)  # primary, taskbar at the bottom
RIGHT = QRect(1920, -200, 2560, 1400)  # second monitor, taller and offset up


def test_no_saved_position_means_tray_anchored():
    assert wp.saved_anchor({}) is None
    assert wp.saved_anchor({"appearance": {}}) is None
    assert wp.saved_anchor({"appearance": {"window_position": "junk"}}) is None
    assert wp.saved_anchor({"appearance": {"window_position": {"right": "1", "top": 2}}}) is None
    assert wp.saved_anchor({"appearance": {"window_position": {"right": True, "top": 2}}}) is None


def test_save_and_read_back_top_right_corner():
    config = {}
    wp.save_anchor(config, QRect(100, 200, 500, 300))
    assert config["appearance"]["window_position"] == {"right": 600, "top": 200}
    assert wp.saved_anchor(config) == QPoint(600, 200)


def test_clear_anchor():
    config = {"appearance": {"window_position": {"right": 1, "top": 1}, "rows": 2}}
    assert wp.clear_anchor(config) is True
    assert config == {"appearance": {"rows": 2}}
    assert wp.clear_anchor(config) is False


def test_place_inside_a_screen_keeps_position():
    assert wp.place(QPoint(800, 100), 500, 300, [LEFT, RIGHT]) == QPoint(300, 100)


def test_place_on_second_monitor_with_negative_y():
    assert wp.place(QPoint(3000, -150), 500, 300, [LEFT, RIGHT]) == QPoint(2500, -150)


def test_wider_window_grows_left_from_the_saved_corner():
    # Same anchor, more columns: right edge stays put.
    assert wp.place(QPoint(1500, 100), 700, 300, [LEFT]) == QPoint(800, 100)


def test_place_pulls_partially_offscreen_window_back_in():
    # Taller window near the bottom of the screen gets pushed up.
    assert wp.place(QPoint(1900, 900), 500, 300, [LEFT]) == QPoint(1400, 740)
    # Dropped half past the left edge.
    assert wp.place(QPoint(200, 10), 500, 300, [LEFT]) == QPoint(0, 10)


def test_straddling_two_monitors_goes_to_the_one_with_most_of_it():
    # 400 px on the right monitor, 100 px on the left one.
    assert wp.place(QPoint(2320, 100), 500, 300, [LEFT, RIGHT]) == QPoint(1920, 100)


def test_unplugged_monitor_falls_back_to_tray():
    assert wp.place(QPoint(3000, 100), 500, 300, [LEFT]) is None
    assert wp.place(QPoint(800, 100), 500, 300, []) is None


def test_window_bigger_than_screen_pins_top_left():
    small = QRect(0, 0, 400, 200)
    assert wp.place(QPoint(450, 0), 500, 300, [small]) == QPoint(0, 0)

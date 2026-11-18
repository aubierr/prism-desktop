import socket
import threading
from collections import namedtuple

import psutil
import pytest

from services import power_control as pc

Addr = namedtuple("Addr", "family address netmask broadcast ptp")


@pytest.mark.parametrize("message, expected", [
    ("command_shutdown", ("shutdown", 0)),
    ("  Command_Restart ", ("restart", 0)),
    ("command_sleep", ("sleep", 0)),
    ("command_hibernate", ("hibernate", 0)),
    ("command_lock", ("lock", 0)),
    ("command_cancel", ("cancel", 0)),
    ("command_selfdestruct", None),
    ("shutdown", None),
    ("", None),
    (None, None),
])
def test_parse_command(message, expected):
    assert pc.parse_command({"message": message}) == expected


def test_unknown_commands_are_still_commands_so_they_are_not_shown():
    assert pc.is_command("command_selfdestruct")
    assert not pc.is_command("Door opened")
    assert not pc.is_command(None)


@pytest.mark.parametrize("raw, expected", [
    (30, 30), ("45", 45), (12.9, 12), (-5, 0), (10_000, pc.MAX_DELAY_S),
    ("soon", 0), (None, 0), (True, 0),
])
def test_delay(raw, expected):
    assert pc.parse_command({"message": "command_shutdown", "delay": raw}) == ("shutdown", expected)


def test_windows_commands():
    assert pc.os_command("shutdown", 30, "win32") == ["shutdown", "/s", "/t", "30"]
    assert pc.os_command("restart", 0, "win32") == ["shutdown", "/r", "/t", "0"]
    assert pc.os_command("cancel", 0, "win32") == ["shutdown", "/a"]
    # Sleep and lock go through the Win32 API, not a command.
    assert pc.os_command("sleep", 0, "win32") is None
    assert pc.is_supported("sleep", "win32") and pc.is_supported("lock", "win32")
    assert pc.native_delay("shutdown", "win32") and not pc.native_delay("lock", "win32")


def test_linux_and_mac_commands():
    assert pc.os_command("shutdown", 0, "linux") == ["systemctl", "poweroff"]
    assert pc.os_command("lock", 0, "linux") == ["loginctl", "lock-session"]
    assert pc.os_command("sleep", 0, "darwin") == ["pmset", "sleepnow"]
    assert not pc.is_supported("hibernate", "darwin")
    assert not pc.native_delay("shutdown", "linux")


def test_execute_runs_immediately():
    calls = []
    pc.execute("restart", 0, runner=lambda a, d: calls.append((a, d)))
    assert calls == [("restart", 0)]


def test_execute_never_raises():
    def boom(action, delay):
        raise OSError("nope")
    pc.execute("shutdown", 0, runner=boom)


def test_delayed_action_can_be_cancelled(monkeypatch):
    monkeypatch.setattr(pc.sys, "platform", "linux")
    calls = []
    pc.execute("lock", 60, runner=lambda a, d: calls.append(a))
    assert pc._pending_timer is not None
    pc.execute("cancel", 0, runner=lambda a, d: calls.append(a))
    assert pc._pending_timer is None
    assert calls == []


def test_delayed_action_fires(monkeypatch):
    monkeypatch.setattr(pc.sys, "platform", "linux")
    done = threading.Event()
    pc.execute("lock", 0.05, runner=lambda a, d: done.set())
    # parse_delay gives ints, but execute itself just waits the given time.
    assert done.wait(2)


@pytest.mark.parametrize("raw, expected", [
    ("aa-bb-cc-dd-ee-ff", "AA:BB:CC:DD:EE:FF"),
    ("AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF"),
    ("aabb.ccdd.eeff", "AA:BB:CC:DD:EE:FF"),
    ("00-00-00-00-00-00", None),
    ("not a mac", None),
    ("", None),
    (None, None),
])
def test_normalize_mac(raw, expected):
    assert pc.normalize_mac(raw) == expected


def test_find_mac_for_ip_picks_the_interface_holding_that_ip():
    addrs = {
        "Wi-Fi": [Addr(psutil.AF_LINK, "11-22-33-44-55-66", None, None, None),
                  Addr(socket.AF_INET, "10.0.0.5", "255.255.255.0", None, None)],
        "Ethernet": [Addr(psutil.AF_LINK, "aa-bb-cc-dd-ee-ff", None, None, None),
                     Addr(socket.AF_INET, "192.168.1.42", "255.255.255.0", None, None)],
    }
    assert pc.find_mac_for_ip(addrs, "192.168.1.42") == "AA:BB:CC:DD:EE:FF"
    assert pc.find_mac_for_ip(addrs, "172.16.0.1") is None
    assert pc.find_netmask_for_ip(addrs, "10.0.0.5") == "255.255.255.0"


def test_local_ip_towards_bad_urls():
    assert pc.local_ip_towards("") is None
    assert pc.local_ip_towards("not a url") is None


def test_notify_service_name_matches_home_assistant_slug():
    assert pc.notify_service_name("DESKTOP-ABC123") == "notify.mobile_app_desktop_abc123"
    assert pc.notify_service_name("PC de Kévin") == "notify.mobile_app_pc_de_kevin"


def test_broadcast_only_for_private_networks():
    assert pc.broadcast_for("192.168.1.42") == "192.168.1.255"
    assert pc.broadcast_for("10.1.2.3", "255.255.0.0") == "10.1.255.255"
    assert pc.broadcast_for("192.168.1.42", "garbage") is None
    assert pc.broadcast_for("8.8.8.8") is None
    assert pc.broadcast_for(None) is None

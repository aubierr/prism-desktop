"""
Remote power control from Home Assistant (fork feature).

Turning the PC OFF: Home Assistant calls the notify service Prism registered
(notify.mobile_app_<pc_name>) with a command as the message, same convention
as the official companion apps:

    action: notify.mobile_app_my_pc
    data:
      message: command_shutdown
      data:
        delay: 30          # optional, seconds (0-600)

Commands: command_shutdown, command_restart, command_sleep, command_hibernate,
command_lock, command_cancel (aborts a delayed shutdown/restart).

Only messages delivered on the mobile_app push channel are treated as commands;
persistent notifications never are. Nothing runs unless the user enabled
"remote power control" in the settings (off by default).

Turning the PC ON can't be done by Prism (it isn't running then): Home
Assistant sends a Wake-on-LAN magic packet. services/power_switch.py creates
the Home Assistant switch that does both.
"""

import ipaddress
import logging
import re
import socket
import subprocess
import sys
import threading
import unicodedata
from typing import Callable, Optional
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

COMMAND_PREFIX = "command_"
ACTIONS = ("shutdown", "restart", "sleep", "hibernate", "lock", "cancel")
# Actions after which the PC is off (as far as the HA switch is concerned).
POWER_OFF_ACTIONS = ("shutdown", "sleep", "hibernate")
MAX_DELAY_S = 600

# Delayed sleep/hibernate/lock (and every delayed action off Windows) wait here
# so command_cancel can stop them.
_pending_timer: Optional[threading.Timer] = None
_pending_lock = threading.Lock()


# ── Parsing ──────────────────────────────────────────────────────────────────

def is_command(message) -> bool:
    """True for any 'command_*' message, known or not, so unknown commands are
    swallowed instead of being shown as a notification."""
    return isinstance(message, str) and message.strip().lower().startswith(COMMAND_PREFIX)


def parse_command(payload: dict) -> Optional[tuple[str, int]]:
    """(action, delay_seconds) for a known command, else None."""
    if not isinstance(payload, dict):
        return None
    message = payload.get("message")
    if not is_command(message):
        return None
    action = message.strip().lower()[len(COMMAND_PREFIX):]
    if action not in ACTIONS:
        return None
    return action, parse_delay(payload.get("delay"))


def parse_delay(raw) -> int:
    """Seconds, clamped to 0..MAX_DELAY_S. Anything unreadable means 0."""
    if isinstance(raw, bool):
        return 0
    try:
        delay = int(float(raw))
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_DELAY_S, delay))


# ── Platform commands ────────────────────────────────────────────────────────

def os_command(action: str, delay: int, platform: str = sys.platform) -> Optional[list]:
    """Shell command for an action, or None when it is done another way
    (Win32 API call) or isn't supported on this OS.

    Only Windows shutdown/restart take a native delay (and show Windows' own
    countdown, cancellable with `shutdown /a`); other delays are handled by
    a timer in execute().
    """
    if platform == "win32":
        return {
            "shutdown": ["shutdown", "/s", "/t", str(delay)],
            "restart": ["shutdown", "/r", "/t", str(delay)],
            "hibernate": ["shutdown", "/h"],
            "cancel": ["shutdown", "/a"],
        }.get(action)
    if platform == "darwin":
        return {
            "shutdown": ["osascript", "-e", 'tell application "System Events" to shut down'],
            "restart": ["osascript", "-e", 'tell application "System Events" to restart'],
            "sleep": ["pmset", "sleepnow"],
            "lock": ["pmset", "displaysleepnow"],
        }.get(action)
    return {
        "shutdown": ["systemctl", "poweroff"],
        "restart": ["systemctl", "reboot"],
        "sleep": ["systemctl", "suspend"],
        "hibernate": ["systemctl", "hibernate"],
        "lock": ["loginctl", "lock-session"],
    }.get(action)


def native_delay(action: str, platform: str = sys.platform) -> bool:
    return platform == "win32" and action in ("shutdown", "restart")


def is_supported(action: str, platform: str = sys.platform) -> bool:
    if action == "cancel":
        return True
    if platform == "win32" and action in ("sleep", "lock"):
        return True
    return os_command(action, 0, platform) is not None


def _win_sleep():
    import ctypes
    # SetSuspendState(hibernate=False, force=False, disableWakeEvent=False).
    # Note: Windows hibernates instead when hibernation is enabled.
    ctypes.windll.powrprof.SetSuspendState(False, False, False)


def _win_lock():
    import ctypes
    ctypes.windll.user32.LockWorkStation()


def _run_now(action: str, delay: int = 0):
    if sys.platform == "win32" and action == "sleep":
        _win_sleep()
        return
    if sys.platform == "win32" and action == "lock":
        _win_lock()
        return
    cmd = os_command(action, delay)
    if cmd is None:
        logger.warning(f"[Power] '{action}' is not supported on this system")
        return
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False, **kwargs)
    if res.returncode != 0:
        logger.warning(f"[Power] {' '.join(cmd)} exited with {res.returncode}: {res.stderr.strip()}")


def _cancel_pending() -> bool:
    global _pending_timer
    with _pending_lock:
        timer, _pending_timer = _pending_timer, None
    if timer:
        timer.cancel()
        return True
    return False


def _run_logged(runner, action: str):
    try:
        runner(action, 0)
    except Exception as e:
        logger.error(f"[Power] Delayed '{action}' failed: {e}")


def execute(action: str, delay: int = 0,
            runner: Callable[[str, int], None] = _run_now) -> None:
    """Carry out an action. Never raises (logs instead)."""
    global _pending_timer
    try:
        if action == "cancel":
            _cancel_pending()
            if sys.platform == "win32":
                runner("cancel", 0)  # aborts Windows' own shutdown countdown
            logger.info("[Power] Pending power action cancelled")
            return

        _cancel_pending()
        if delay and not native_delay(action):
            timer = threading.Timer(delay, _run_logged, args=(runner, action))
            timer.daemon = True
            with _pending_lock:
                _pending_timer = timer
            timer.start()
            logger.info(f"[Power] '{action}' scheduled in {delay}s")
            return

        logger.info(f"[Power] Running '{action}' (delay {delay}s)")
        runner(action, delay)
    except Exception as e:
        logger.error(f"[Power] '{action}' failed: {e}")


# ── Wake-on-LAN helper ───────────────────────────────────────────────────────

def local_ip_towards(ha_url: str) -> Optional[str]:
    """IP address of the network interface this PC uses to reach Home Assistant.
    A UDP connect sends no packet; it only picks the route."""
    try:
        parts = urlsplit(ha_url)
        host = parts.hostname
        port = parts.port or (443 if parts.scheme == "https" else 8123)
    except ValueError:
        return None
    if not host:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((host, port))
            ip = s.getsockname()[0]
    except OSError:
        return None
    return None if ip.startswith("0.") else ip


def normalize_mac(raw) -> Optional[str]:
    """'aa-bb-cc-dd-ee-ff' / 'aabb.ccdd.eeff' → 'AA:BB:CC:DD:EE:FF'."""
    if not isinstance(raw, str):
        return None
    hexdigits = re.sub(r"[-:.]", "", raw.strip()).upper()
    if not re.fullmatch(r"[0-9A-F]{12}", hexdigits) or hexdigits == "0" * 12:
        return None
    return ":".join(hexdigits[i:i + 2] for i in range(0, 12, 2))


def find_mac_for_ip(if_addrs: dict, ip: str) -> Optional[str]:
    """MAC of the interface holding `ip`, from psutil.net_if_addrs()-shaped data."""
    import psutil
    for addrs in if_addrs.values():
        if not any(getattr(a, "address", None) == ip for a in addrs):
            continue
        for a in addrs:
            if a.family == psutil.AF_LINK:
                mac = normalize_mac(a.address)
                if mac:
                    return mac
    return None


def find_netmask_for_ip(if_addrs: dict, ip: str) -> Optional[str]:
    for addrs in if_addrs.values():
        for a in addrs:
            if getattr(a, "address", None) == ip and getattr(a, "netmask", None):
                return a.netmask
    return None


def network_identity(ha_url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(ip, mac, netmask) of the interface used to reach Home Assistant."""
    import psutil
    ip = local_ip_towards(ha_url)
    if not ip:
        return None, None, None
    try:
        if_addrs = psutil.net_if_addrs()
    except Exception:
        return ip, None, None
    return ip, find_mac_for_ip(if_addrs, ip), find_netmask_for_ip(if_addrs, ip)


def ha_slugify(text: str) -> str:
    """Close enough to homeassistant.util.slugify for device names."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return text or "unknown"


def notify_service_name(device_name: str) -> str:
    return f"notify.mobile_app_{ha_slugify(device_name)}"


def broadcast_for(ip: Optional[str], netmask: Optional[str] = None) -> Optional[str]:
    """Directed broadcast of the PC's local network (/24 if the mask is unknown),
    or None for a non-private address."""
    try:
        addr = ipaddress.IPv4Address(ip)
        net = ipaddress.IPv4Network(f"{addr}/{netmask or 24}", strict=False)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, TypeError, ValueError):
        return None
    if not addr.is_private or net.prefixlen >= 31:
        return None
    return str(net.broadcast_address)

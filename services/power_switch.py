"""
On/off switch for this PC on its Home Assistant device page (fork feature).

The mobile_app integration only lets an app create sensors, so Prism instead
creates a Template switch helper through Home Assistant's config-flow API and
links it to the Prism device. It then shows under "Controls" on the device page.

  * state:    the Prism "Power" binary sensor is on AND was reported recently
              (Prism pushes it every 30 s and sends "off" when it quits)
  * turn on:  wake_on_lan.send_magic_packet to this PC's MAC address
  * turn off: notify.mobile_app_<pc> with message command_shutdown

Needs an administrator token (config flows are admin-only). Running it again
updates the existing switch instead of creating a second one.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

POWER_SENSOR_UID = "power_state"
# Heartbeat is 30 s; allow a few missed pushes before showing the PC as off.
STALE_AFTER_S = 150


class PowerSwitchError(Exception):
    """Carries a translation key for the settings panel."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(detail or key)
        self.key = key
        self.detail = detail


@dataclass
class PowerSwitchResult:
    entry_id: str
    created: bool  # False when an existing switch was updated
    wol_added: bool  # True when the Wake-on-LAN integration had to be set up


# ── Pure helpers (unit tested) ───────────────────────────────────────────────


def find_ha_device_id(devices: list, mobile_device_id: str) -> Optional[str]:
    """Device registry id of the Prism device (identifier ["mobile_app", <id>])."""
    for dev in devices or []:
        for ident in dev.get("identifiers") or []:
            if len(ident) == 2 and ident[0] == "mobile_app" and ident[1] == mobile_device_id:
                return dev.get("id")
    return None


def find_entity_id(entities: list, unique_id: str) -> Optional[str]:
    for ent in entities or []:
        if ent.get("platform") == "mobile_app" and ent.get("unique_id") == unique_id:
            return ent.get("entity_id")
    return None


def find_notify_service(services: list, device_slug: str) -> Optional[str]:
    """notify.mobile_app_<slug> if Home Assistant has it (it may carry a _2 suffix)."""
    notify = next((d.get("services", {}) for d in services or [] if d.get("domain") == "notify"), {})
    wanted = f"mobile_app_{device_slug}"
    if wanted in notify:
        return f"notify.{wanted}"
    candidates = sorted(n for n in notify if n.startswith(wanted + "_"))
    return f"notify.{candidates[0]}" if candidates else None


def has_service(services: list, domain: str, service: str) -> bool:
    return any(d.get("domain") == domain and service in (d.get("services") or {}) for d in services or [])


def state_template(sensor_entity_id: str) -> str:
    return (
        f"{{% set s = states['{sensor_entity_id}'] %}}"
        "{{ s is not none and s.state == 'on' and "
        f"(now() - (s.last_reported or s.last_updated)).total_seconds() < {STALE_AFTER_S} }}}}"
    )


def switch_options(
    sensor_entity_id: str, notify_service: str, mac: str, broadcast: Optional[str], ha_device_id: str
) -> dict:
    """Fields of the template switch form (minus the name)."""
    wol_data = {"mac": mac}
    if broadcast:
        wol_data["broadcast_address"] = broadcast
    return {
        "value_template": state_template(sensor_entity_id),
        "turn_on": [{"action": "wake_on_lan.send_magic_packet", "data": wol_data}],
        "turn_off": [{"action": notify_service, "data": {"message": "command_shutdown"}}],
        "device_id": ha_device_id,
    }


# ── Home Assistant API ───────────────────────────────────────────────────────


class _HA:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str):
        self.s = session
        self.url = url.rstrip("/")
        self.token = token

    async def rest(self, method: str, path: str, json=None):
        async with self.s.request(
            method,
            self.url + path,
            json=json,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            if r.status in (401, 403):
                # Home Assistant answers 401 both for a bad token and for a
                # non-admin user on the config API.
                raise PowerSwitchError("settings.ha.power_switch_err_admin")
            if r.status >= 400:
                raise PowerSwitchError(
                    "settings.ha.power_switch_err_http", f"{method} {path}: HTTP {r.status} {await r.text()}"
                )
            return await r.json(content_type=None)

    async def ws_commands(self, *commands: dict) -> list:
        """Run a few WebSocket commands on a short-lived connection."""
        ws_url = self.url.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/api/websocket"
        async with self.s.ws_connect(ws_url, timeout=15) as ws:
            await ws.receive_json(timeout=15)  # auth_required
            await ws.send_json({"type": "auth", "access_token": self.token})
            auth = await ws.receive_json(timeout=15)
            if auth.get("type") != "auth_ok":
                raise PowerSwitchError("settings.ha.power_switch_err_auth")
            results = []
            for i, cmd in enumerate(commands, start=1):
                await ws.send_json({"id": i, **cmd})
                while True:
                    msg = await ws.receive_json(timeout=15)
                    if msg.get("id") == i and msg.get("type") == "result":
                        break
                if not msg.get("success"):
                    err = msg.get("error") or {}
                    if err.get("code") == "unauthorized":
                        raise PowerSwitchError("settings.ha.power_switch_err_admin")
                    raise PowerSwitchError("settings.ha.power_switch_err_http", f"{cmd['type']}: {err}")
                results.append(msg.get("result"))
            return results

    async def submit_flow(self, kind: str, flow_id: str, data: dict) -> dict:
        return await self.rest("POST", f"/api/config/{kind}/flow/{flow_id}", data)


async def _entry_exists(ha: _HA, entry_id: str) -> bool:
    if not entry_id:
        return False
    entries = await ha.rest("GET", "/api/config/config_entries/entry?domain=template")
    return any(e.get("entry_id") == entry_id for e in entries or [])


async def _ensure_wake_on_lan(ha: _HA, services: list, mac: str, broadcast: Optional[str]) -> bool:
    """Load the Wake-on-LAN integration if its action isn't available. Returns True if added."""
    if has_service(services, "wake_on_lan", "send_magic_packet"):
        return False
    flow = await ha.rest("POST", "/api/config/config_entries/flow", {"handler": "wake_on_lan"})
    data = {"mac": mac}
    if broadcast:
        data["broadcast_address"] = broadcast
    res = await ha.submit_flow("config_entries", flow["flow_id"], data)
    # "already_configured" means it is there already (another entry for this MAC).
    if res.get("type") not in ("create_entry", "abort"):
        raise PowerSwitchError("settings.ha.power_switch_err_http", f"wake_on_lan flow: {res}")
    return res.get("type") == "create_entry"


async def create_or_update(
    ha_url: str,
    token: str,
    *,
    mobile_device_id: str,
    webhook_id: str,
    device_slug: str,
    mac: str,
    broadcast: Optional[str],
    name: str,
    existing_entry_id: str = "",
) -> PowerSwitchResult:
    if not (ha_url and token and webhook_id and mobile_device_id):
        raise PowerSwitchError("settings.ha.power_switch_err_not_registered")
    if not mac:
        raise PowerSwitchError("settings.ha.wol_no_mac")

    async with aiohttp.ClientSession() as session:
        ha = _HA(session, ha_url, token)

        devices, entities = await ha.ws_commands(
            {"type": "config/device_registry/list"},
            {"type": "config/entity_registry/list"},
        )
        ha_device_id = find_ha_device_id(devices, mobile_device_id)
        sensor_id = find_entity_id(entities, f"{webhook_id}_{POWER_SENSOR_UID}")
        if not ha_device_id or not sensor_id:
            raise PowerSwitchError("settings.ha.power_switch_err_not_registered")

        services = await ha.rest("GET", "/api/services")
        notify = find_notify_service(services, device_slug)
        if not notify:
            raise PowerSwitchError("settings.ha.power_switch_err_not_registered")
        wol_added = await _ensure_wake_on_lan(ha, services, mac, broadcast)

        options = switch_options(sensor_id, notify, mac, broadcast, ha_device_id)

        if await _entry_exists(ha, existing_entry_id):
            flow = await ha.rest("POST", "/api/config/config_entries/options/flow", {"handler": existing_entry_id})
            if flow.get("type") == "form" and flow.get("step_id") != "switch":
                flow = await ha.submit_flow("config_entries/options", flow["flow_id"], {})
            res = await ha.submit_flow("config_entries/options", flow["flow_id"], options)
            if res.get("type") != "create_entry":
                raise PowerSwitchError("settings.ha.power_switch_err_http", f"options flow: {res}")
            logger.info(f"[PowerSwitch] Updated template switch {existing_entry_id}")
            return PowerSwitchResult(existing_entry_id, created=False, wol_added=wol_added)

        flow = await ha.rest("POST", "/api/config/config_entries/flow", {"handler": "template"})
        if flow.get("type") == "menu":
            flow = await ha.submit_flow("config_entries", flow["flow_id"], {"next_step_id": "switch"})
        res = await ha.submit_flow("config_entries", flow["flow_id"], {"name": name, **options})
        if res.get("type") != "create_entry":
            raise PowerSwitchError("settings.ha.power_switch_err_http", f"template flow: {res}")
        entry_id = (res.get("result") or {}).get("entry_id", "")
        logger.info(f"[PowerSwitch] Created template switch {entry_id} on device {ha_device_id}")
        return PowerSwitchResult(entry_id, created=True, wol_added=wol_added)

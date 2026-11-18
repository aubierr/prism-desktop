from services import power_switch as ps

DEVICES = [
    {"id": "other", "identifiers": [["hue", "x"]]},
    {"id": "dev123", "identifiers": [["mobile_app", "abc"]]},
]
ENTITIES = [
    {"platform": "mobile_app", "unique_id": "hook_cpu_usage", "entity_id": "sensor.pc_cpu_usage"},
    {"platform": "mobile_app", "unique_id": "hook_power_state", "entity_id": "binary_sensor.pc_power"},
    {"platform": "template", "unique_id": "hook_power_state", "entity_id": "switch.decoy"},
]
SERVICES = [
    {"domain": "notify", "services": {"notify": {}, "mobile_app_pc_de_kevin_2": {}, "mobile_app_phone": {}}},
    {"domain": "wake_on_lan", "services": {"send_magic_packet": {}}},
]


def test_find_device_and_power_sensor():
    assert ps.find_ha_device_id(DEVICES, "abc") == "dev123"
    assert ps.find_ha_device_id(DEVICES, "zzz") is None
    assert ps.find_entity_id(ENTITIES, "hook_power_state") == "binary_sensor.pc_power"
    assert ps.find_entity_id(ENTITIES, "hook_missing") is None


def test_notify_service_lookup_accepts_suffix():
    assert ps.find_notify_service(SERVICES, "pc_de_kevin") == "notify.mobile_app_pc_de_kevin_2"
    exact = [{"domain": "notify", "services": {"mobile_app_pc": {}, "mobile_app_pc_2": {}}}]
    assert ps.find_notify_service(exact, "pc") == "notify.mobile_app_pc"
    assert ps.find_notify_service(SERVICES, "laptop") is None


def test_has_service():
    assert ps.has_service(SERVICES, "wake_on_lan", "send_magic_packet")
    assert not ps.has_service(SERVICES[:1], "wake_on_lan", "send_magic_packet")


def test_switch_options():
    opts = ps.switch_options("binary_sensor.pc_power", "notify.mobile_app_pc",
                             "AA:BB:CC:DD:EE:FF", "192.168.1.255", "dev123")
    assert opts["device_id"] == "dev123"
    assert opts["turn_on"] == [{"action": "wake_on_lan.send_magic_packet",
                                "data": {"mac": "AA:BB:CC:DD:EE:FF", "broadcast_address": "192.168.1.255"}}]
    assert opts["turn_off"] == [{"action": "notify.mobile_app_pc", "data": {"message": "command_shutdown"}}]
    tpl = opts["value_template"]
    assert "states['binary_sensor.pc_power']" in tpl
    assert f"< {ps.STALE_AFTER_S}" in tpl
    assert tpl.count("{{") == tpl.count("}}") == 1 and tpl.count("{%") == tpl.count("%}") == 1


def test_state_template_renders_with_jinja():
    jinja2 = __import__("pytest").importorskip("jinja2")
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 11, 18, 22, 0, tzinfo=timezone.utc)

    class S:
        def __init__(self, state, age):
            self.state, self.last_reported, self.last_updated = state, now - timedelta(seconds=age), now

    def render(state):
        tpl = jinja2.Environment().from_string(ps.state_template("binary_sensor.pc_power"))
        return tpl.render(states={"binary_sensor.pc_power": state}, now=lambda: now).strip()

    assert render(S("on", 20)) == "True"
    assert render(S("on", 600)) == "False"   # Prism stopped reporting: PC off or crashed
    assert render(S("off", 5)) == "False"
    assert render(None) == "False"

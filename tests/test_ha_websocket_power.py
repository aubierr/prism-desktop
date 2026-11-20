"""Power commands must only come from the mobile_app push channel
(notify.mobile_app_<pc>), never from a persistent notification."""

import asyncio

import pytest
from PyQt6.QtCore import QCoreApplication

from core.ha_websocket import HAWebSocket

PUSH_ID = 7


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def ws(qapp):
    client = HAWebSocket("http://ha.local:8123", "token")
    client._push_channel_id = PUSH_ID
    got = {"notification": [], "power": []}
    client.notification_received.connect(got["notification"].append)
    client.power_command_received.connect(got["power"].append)
    return client, got


def push(message, **data):
    return {"type": "event", "id": PUSH_ID, "event": {"message": message, "title": "HA", "data": data}}


def test_push_command_goes_to_power_signal(ws):
    client, got = ws
    asyncio.run(client._handle_message(push("command_shutdown", delay=30)))
    assert got["notification"] == []
    assert got["power"][0]["message"] == "command_shutdown"
    assert got["power"][0]["delay"] == 30


def test_normal_push_message_is_still_a_notification(ws):
    client, got = ws
    asyncio.run(client._handle_message(push("Door opened")))
    assert got["power"] == []
    assert got["notification"][0]["message"] == "Door opened"


def test_persistent_notification_never_triggers_power(ws):
    client, got = ws
    asyncio.run(
        client._handle_message(
            {
                "type": "event",
                "id": 99,
                "event": {
                    "event_type": "state_changed",
                    "data": {
                        "entity_id": "persistent_notification.x",
                        "new_state": {"state": "notifying", "attributes": {"message": "command_shutdown"}},
                    },
                },
            }
        )
    )
    assert got["power"] == []

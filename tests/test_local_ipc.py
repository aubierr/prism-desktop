import threading

import pytest
from PyQt6.QtCore import QCoreApplication, QTimer

from services import local_ipc


@pytest.fixture(autouse=True)
def private_server_name(tmp_path, monkeypatch):
    """Use a name tied to the temp dir so a running Prism is never contacted."""
    monkeypatch.setattr(local_ipc, "get_config_path", lambda: tmp_path / "config.json")


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


def test_server_name_is_stable_and_per_config(tmp_path, monkeypatch):
    first = local_ipc.prism_ipc_server_name()
    assert first == local_ipc.prism_ipc_server_name()
    assert first.startswith("prism-desktop-")

    monkeypatch.setattr(local_ipc, "get_config_path", lambda: tmp_path / "other" / "config.json")
    assert local_ipc.prism_ipc_server_name() != first


def test_send_without_running_instance_returns_false():
    assert local_ipc.send_local_command("toggle") is False


@pytest.mark.parametrize("command", ["toggle", "assist"])
def test_command_reaches_running_instance(qapp, command):
    server = local_ipc.LocalCommandServer()
    assert server.start()
    received, sent = [], []
    server.command_received.connect(lambda c: (received.append(c), qapp.quit()))

    # The client blocks, so send from a thread while the Qt loop serves it.
    sender = threading.Thread(target=lambda: sent.append(local_ipc.send_local_command(f" {command}\n")))
    QTimer.singleShot(0, sender.start)
    QTimer.singleShot(5000, qapp.quit)  # safety net
    qapp.exec()
    sender.join(5)
    server.close()

    assert sent == [True]
    assert received == [command]

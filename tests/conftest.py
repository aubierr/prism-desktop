"""Shared fixtures.

Every test runs with the config directory redirected to a temp folder and the
OS keyring switched off, so nothing ever reads or writes the real config.json,
the real encrypted token file or the user's keyring.
"""

import os

import pytest

# Qt widgets need a display; tests never show one.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    from core import config_manager, token_storage

    def fake_config_path(filename: str = "config.json"):
        return tmp_path / filename

    monkeypatch.setattr(config_manager, "get_config_path", fake_config_path)
    monkeypatch.setattr(token_storage, "get_config_path", fake_config_path)
    monkeypatch.setattr(token_storage, "_keyring_probed", True)
    monkeypatch.setattr(token_storage, "_keyring_available", False)
    return tmp_path

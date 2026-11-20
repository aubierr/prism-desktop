import json

from core.config_manager import ConfigManager
from core.token_storage import load_token, store_token


def write_config(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def read_config(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_file_gives_defaults_and_creates_it(isolated_config):
    cm = ConfigManager()
    assert cm.config["home_assistant"] == {"url": "", "token": ""}
    assert cm.config["assist"]["enabled"] is False
    assert cm.config["buttons"] == []
    assert (isolated_config / "config.json").exists()


def test_plaintext_token_is_migrated_and_scrubbed(isolated_config):
    path = isolated_config / "config.json"
    write_config(path, {"home_assistant": {"url": "http://ha:8123", "token": "secret"}})

    cm = ConfigManager()

    assert cm.config["home_assistant"]["token"] == "secret"  # usable in memory
    assert read_config(path)["home_assistant"]["token"] == ""  # gone from disk
    assert "secret" not in path.read_text(encoding="utf-8")
    assert load_token() == "secret"


def test_stored_token_wins_over_file(isolated_config):
    store_token("from-storage")
    write_config(isolated_config / "config.json", {"home_assistant": {"url": "u", "token": "stale"}})
    assert ConfigManager().config["home_assistant"]["token"] == "from-storage"


def test_legacy_slots_become_row_col_and_get_page_zero(isolated_config):
    write_config(
        isolated_config / "config.json",
        {
            "appearance": {"cols": 3},
            "buttons": [{"slot": 4, "entity_id": "light.a"}, {"row": 1, "col": 1, "page": 2, "entity_id": "light.b"}],
        },
    )
    buttons = ConfigManager().config["buttons"]
    assert buttons[0] == {"slot": 4, "entity_id": "light.a", "row": 1, "col": 1, "page": 0}
    assert buttons[1]["page"] == 2  # existing page untouched


def test_corrupt_file_is_backed_up_not_lost(isolated_config):
    path = isolated_config / "config.json"
    path.write_text("{not json", encoding="utf-8")

    cm = ConfigManager()

    assert cm.config["buttons"] == []
    assert (isolated_config / "config.json.bak").read_text(encoding="utf-8") == "{not json"


def test_save_never_writes_token_and_leaves_no_temp_file(isolated_config):
    cm = ConfigManager()
    cm.config["home_assistant"]["token"] = "new-token"
    cm.save_config()

    assert read_config(isolated_config / "config.json")["home_assistant"]["token"] == ""
    assert load_token() == "new-token"
    assert not list(isolated_config.glob(".config_*.tmp"))

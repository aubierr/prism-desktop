import os
import stat

import pytest

from core import token_storage as ts


def test_round_trip_through_encrypted_file(isolated_config):
    ts.store_token("abc123")
    enc = isolated_config / ".ha_token.enc"
    assert enc.exists()
    assert b"abc123" not in enc.read_bytes()
    assert ts.load_token() == "abc123"


def test_load_without_stored_token_is_empty():
    assert ts.load_token() == ""


def test_empty_token_is_not_stored(isolated_config):
    ts.store_token("")
    assert not (isolated_config / ".ha_token.enc").exists()


def test_clear_removes_files(isolated_config):
    ts.store_token("abc123")
    ts.clear_token()
    assert not (isolated_config / ".ha_token.enc").exists()
    assert not (isolated_config / ".ha_token.salt").exists()
    assert ts.load_token() == ""


def test_tampered_file_loads_as_empty(isolated_config):
    ts.store_token("abc123")
    (isolated_config / ".ha_token.enc").write_bytes(b"garbage")
    assert ts.load_token() == ""


def test_store_overwrites_previous_token():
    ts.store_token("old")
    ts.store_token("new")
    assert ts.load_token() == "new"


@pytest.mark.skipif(os.name != "posix", reason="file modes only apply on POSIX")
def test_token_files_are_private(isolated_config):
    ts.store_token("abc123")
    for name in (".ha_token.enc", ".ha_token.salt"):
        mode = stat.S_IMODE((isolated_config / name).stat().st_mode)
        assert mode == 0o600, f"{name} is {oct(mode)}"

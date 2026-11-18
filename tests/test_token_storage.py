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


windows_only = pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")


def store_as_fernet(monkeypatch, token):
    """Write a token the way older versions did on Windows (machine-key Fernet)."""
    with monkeypatch.context() as m:
        m.setattr(ts.sys, "platform", "linux")
        ts.store_token(token)


@windows_only
def test_windows_file_is_sealed_with_dpapi(isolated_config):
    ts.store_token("abc123")
    data = (isolated_config / ".ha_token.enc").read_bytes()
    assert data.startswith(ts._DPAPI_MAGIC)
    assert b"abc123" not in data
    assert not (isolated_config / ".ha_token.salt").exists()
    assert ts.load_token() == "abc123"


@windows_only
def test_old_machine_key_file_is_moved_to_dpapi(isolated_config, monkeypatch):
    store_as_fernet(monkeypatch, "legacy-token")
    enc = isolated_config / ".ha_token.enc"
    assert not enc.read_bytes().startswith(ts._DPAPI_MAGIC)

    assert ts.load_token() == "legacy-token"

    assert enc.read_bytes().startswith(ts._DPAPI_MAGIC)
    assert not (isolated_config / ".ha_token.salt").exists()
    assert ts.load_token() == "legacy-token"


@windows_only
def test_tampered_dpapi_file_loads_as_empty(isolated_config):
    ts.store_token("abc123")
    enc = isolated_config / ".ha_token.enc"
    enc.write_bytes(enc.read_bytes()[:-8] + b"tampered")
    assert ts.load_token() == ""


@windows_only
def test_dpapi_failure_falls_back_to_machine_key(isolated_config, monkeypatch):
    def broken(_data):
        raise OSError("DPAPI unavailable")

    monkeypatch.setattr(ts, "_dpapi_protect", broken)
    ts.store_token("abc123")

    assert not (isolated_config / ".ha_token.enc").read_bytes().startswith(ts._DPAPI_MAGIC)
    assert ts.load_token() == "abc123"  # the failed re-seal does not lose the token


def test_dpapi_is_never_used_off_windows(monkeypatch):
    def forbidden(_data):
        raise AssertionError("DPAPI called off Windows")

    monkeypatch.setattr(ts, "_dpapi_protect", forbidden)
    monkeypatch.setattr(ts, "_dpapi_unprotect", forbidden)
    store_as_fernet(monkeypatch, "abc123")
    with monkeypatch.context() as m:
        m.setattr(ts.sys, "platform", "linux")
        assert ts.load_token() == "abc123"


@pytest.mark.skipif(os.name != "posix", reason="file modes only apply on POSIX")
def test_token_files_are_private(isolated_config):
    ts.store_token("abc123")
    for name in (".ha_token.enc", ".ha_token.salt"):
        mode = stat.S_IMODE((isolated_config / name).stat().st_mode)
        assert mode == 0o600, f"{name} is {oct(mode)}"

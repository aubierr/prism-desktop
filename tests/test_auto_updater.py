import hashlib
from unittest import mock

import pytest

from services import auto_updater as au

ASSET = "PrismDesktopSetup.exe"
SUMS = [{"name": "SHA256SUMS", "browser_download_url": "https://example.invalid/SHA256SUMS"}]
# Format published with 1.7 (sha256sum output for every asset).
REAL_SUMS_1_7 = """\
7f15c1ba5c8ee32d7d193f8143ae07d08d4b4511f0e898803b10da0b8de16935  PrismDesktop-macOS-arm64.dmg
ee99e15d955d374bb054d66016e6a8f92a049febef7a43150076203e6fcd01d4  PrismDesktop-macOS-arm64.zip
3c260a929c7990a6a1738cdc2b1f083c8b1e39a34c4e05e37ac792c9e91e6fee  PrismDesktop-macOS-x86_64.dmg
77df83344ffd32ed85ad7ac1566abb9aa31eb9a262de3d493d7fba876f9e4571  PrismDesktop-macOS-x86_64.zip
f1a5257c55d6fbf16b41ed141bcc95df51943ffc21aa51953bb3c99f9321a772  PrismDesktop-x86_64.AppImage
8a0d2df0aa1ea6d9aad366d39026ea824f6cf3ed4183fef111fdff0aa40773f7  PrismDesktopSetup.exe
"""


@pytest.fixture
def download(tmp_path):
    path = tmp_path / ASSET
    path.write_bytes(b"fake installer")
    return path


def verify(download, assets, sums_text=""):
    response = mock.Mock(text=sums_text)
    thread = au.AutoUpdateThread.__new__(au.AutoUpdateThread)  # skip QThread init
    with mock.patch.object(au.requests, "get", return_value=response) as get:
        result = thread._verify_checksum(download, ASSET, assets)
    return result, get


def good_sum():
    return hashlib.sha256(b"fake installer").hexdigest()


def test_missing_sums_file_is_refused(download):
    result, get = verify(download, [])
    assert result is False
    get.assert_not_called()


def test_sums_file_without_this_asset_is_refused(download):
    assert verify(download, SUMS, "abc  Other.exe\n")[0] is False


def test_matching_sum_passes(download):
    assert verify(download, SUMS, f"{good_sum()}  {ASSET}\n")[0] is True


def test_binary_mode_marker_is_accepted(download):
    assert verify(download, SUMS, f"{good_sum()} *{ASSET}\n")[0] is True


def test_uppercase_sum_is_accepted(download):
    assert verify(download, SUMS, f"{good_sum().upper()}  {ASSET}\n")[0] is True


def test_mismatching_sum_is_refused(download):
    # The real 1.7 sums list this asset, but with the real installer's hash.
    assert verify(download, SUMS, REAL_SUMS_1_7)[0] is False


@pytest.mark.parametrize(
    "platform_name, machine, expected",
    [
        ("win32", "AMD64", "PrismDesktopSetup.exe"),
        ("linux", "x86_64", "PrismDesktop-x86_64.AppImage"),
        ("linux", "aarch64", "PrismDesktop-aarch64.AppImage"),
        ("darwin", "arm64", "PrismDesktop-macOS-arm64.zip"),
        ("darwin", "x86_64", "PrismDesktop-macOS-x86_64.zip"),
        ("freebsd13", "amd64", None),
    ],
)
def test_platform_asset_name(monkeypatch, platform_name, machine, expected):
    monkeypatch.setattr(au.sys, "platform", platform_name)
    monkeypatch.setattr(au.platform, "machine", lambda: machine)
    assert au._platform_asset_name() == expected

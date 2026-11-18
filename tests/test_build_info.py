import re

from core import build_info
from services.update_checker import UpdateCheckerThread


def test_app_version_stays_a_plain_number():
    # Update checks, Home Assistant and the macOS bundle parse APP_VERSION.
    assert re.fullmatch(r"\d+(\.\d+)+", build_info.APP_VERSION)


def test_label_marks_the_fork():
    assert build_info.VERSION_LABEL == f"{build_info.APP_VERSION}-fork"


def test_display_version_uses_label(monkeypatch):
    monkeypatch.setattr(build_info, "BUILD_COMMIT", "")
    monkeypatch.setattr(build_info, "_run_git_command", lambda *a: "")
    assert build_info.get_display_version() == build_info.VERSION_LABEL

    monkeypatch.setattr(build_info, "BUILD_COMMIT", "abc123def456")
    monkeypatch.setattr(build_info, "BUILD_DIRTY", True)
    assert build_info.get_display_version() == f"{build_info.VERSION_LABEL} (abc123def456, dirty)"


def test_label_does_not_change_update_comparison():
    checker = UpdateCheckerThread.__new__(UpdateCheckerThread)
    label = checker._parse_version(checker._extract_version(build_info.VERSION_LABEL))
    plain = checker._parse_version(build_info.APP_VERSION)
    assert label == plain

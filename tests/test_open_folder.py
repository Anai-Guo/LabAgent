"""Tests for open_folder's per-platform explorer dispatch (no real processes spawned)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_harness.orchestrator import folder as folder_mod


@pytest.mark.parametrize(
    "platform, expected_cmd",
    [("win32", "explorer"), ("darwin", "open"), ("linux", "xdg-open")],
)
def test_open_folder_dispatches_on_platform(monkeypatch, tmp_path, platform, expected_cmd):
    calls: list[list[str]] = []
    monkeypatch.setattr(folder_mod.sys, "platform", platform)
    monkeypatch.setattr(folder_mod.subprocess, "Popen", lambda args: calls.append(args))

    assert folder_mod.open_folder(tmp_path) is True
    assert calls == [[expected_cmd, str(Path(tmp_path).resolve())]]


def test_open_folder_accepts_str_and_resolves(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    monkeypatch.setattr(folder_mod.sys, "platform", "linux")
    monkeypatch.setattr(folder_mod.subprocess, "Popen", lambda args: calls.append(args))

    assert folder_mod.open_folder(str(tmp_path)) is True
    assert calls[0][1] == str(tmp_path.resolve())


def test_open_folder_returns_false_and_warns_on_failure(monkeypatch, tmp_path, caplog):
    def boom(args):
        raise OSError("no explorer here")

    monkeypatch.setattr(folder_mod.sys, "platform", "linux")
    monkeypatch.setattr(folder_mod.subprocess, "Popen", boom)

    with caplog.at_level("WARNING", logger="lab_harness.orchestrator.folder"):
        assert folder_mod.open_folder(tmp_path) is False
    assert "Could not open folder" in caplog.text

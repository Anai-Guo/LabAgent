"""CLI integration tests -- argument parsing and command dispatch."""

from __future__ import annotations

import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "lab_harness.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "labharness" in result.stdout.lower() or "lab" in result.stdout.lower()


def test_cli_scan_help():
    result = subprocess.run(
        [sys.executable, "-m", "lab_harness.cli", "scan", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0


def test_cli_propose_help():
    result = subprocess.run(
        [sys.executable, "-m", "lab_harness.cli", "propose", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0


def test_cli_procedures():
    result = subprocess.run(
        [sys.executable, "-m", "lab_harness.cli", "procedures"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "IV_K2400" in result.stdout or "K2400" in result.stdout

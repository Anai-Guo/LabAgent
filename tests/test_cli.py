"""CLI integration tests -- argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest


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


@pytest.fixture
def legacy_locale_paths(monkeypatch):
    """Make Path.read_text/write_text default to cp1252, like a typical Windows lab PC."""
    real_read, real_write = Path.read_text, Path.write_text

    def read_text(self, encoding=None, errors=None):
        return real_read(self, encoding=encoding or "cp1252", errors=errors)

    def write_text(self, data, encoding=None, errors=None, newline=None):
        return real_write(self, data, encoding=encoding or "cp1252", errors=errors, newline=newline)

    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(Path, "write_text", write_text)


def _non_ascii_instrument():
    from lab_harness.models.instrument import InstrumentRecord

    return InstrumentRecord(resource="GPIB0::5::INSTR", vendor="Lab Ωmega", model="µV-2000", serial="№42")


def test_cmd_scan_writes_inventory_as_utf8(tmp_path, monkeypatch, legacy_locale_paths):
    """Inventory JSON (raw non-ASCII from pydantic) must be saved as UTF-8 regardless of locale."""
    from lab_harness import cli
    from lab_harness.discovery import visa_scanner

    monkeypatch.setattr(visa_scanner, "scan_visa_instruments", lambda: [_non_ascii_instrument()])
    out = tmp_path / "inventory.json"

    cli.cmd_scan(argparse.Namespace(output=str(out)), settings=None)

    data = json.loads(out.read_bytes().decode("utf-8"))
    assert data["instruments"][0]["vendor"] == "Lab Ωmega"
    assert data["instruments"][0]["serial"] == "№42"


def test_cmd_classify_reads_inventory_as_utf8(tmp_path, monkeypatch, legacy_locale_paths):
    """A UTF-8 inventory file with non-ASCII fields loads intact under a legacy locale."""
    from lab_harness import cli
    from lab_harness.discovery import classifier
    from lab_harness.models.instrument import LabInventory

    inv_path = tmp_path / "inventory.json"
    inv_path.write_bytes(LabInventory(instruments=[_non_ascii_instrument()]).model_dump_json().encode("utf-8"))
    seen = {}

    def fake_classify(inventory, measurement_type):
        seen["inventory"] = inventory
        return {}

    monkeypatch.setattr(classifier, "classify_instruments", fake_classify)

    cli.cmd_classify(argparse.Namespace(inventory=str(inv_path), measurement_type="IV"), settings=None)

    assert seen["inventory"].instruments[0].model == "µV-2000"

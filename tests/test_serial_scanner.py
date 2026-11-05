"""Tests for the serial port scanner (pyserial replaced by an in-memory fake)."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from lab_harness.discovery.serial_scanner import scan_serial_ports
from lab_harness.models.instrument import InstrumentBus


def _install_fake_pyserial(monkeypatch: pytest.MonkeyPatch, ports: list) -> None:
    """Register fake ``serial`` / ``serial.tools`` / ``serial.tools.list_ports`` modules."""
    list_ports = types.ModuleType("serial.tools.list_ports")
    list_ports.comports = lambda: ports
    tools = types.ModuleType("serial.tools")
    tools.list_ports = list_ports
    serial = types.ModuleType("serial")
    serial.tools = tools
    monkeypatch.setitem(sys.modules, "serial", serial)
    monkeypatch.setitem(sys.modules, "serial.tools", tools)
    monkeypatch.setitem(sys.modules, "serial.tools.list_ports", list_ports)


def _port(device: str, description=None, manufacturer=None, serial_number=None) -> SimpleNamespace:
    return SimpleNamespace(
        device=device,
        description=description,
        manufacturer=manufacturer,
        serial_number=serial_number,
    )


def test_returns_empty_list_when_pyserial_missing(monkeypatch, caplog):
    """A missing pyserial install degrades to an empty result with a warning."""
    monkeypatch.setitem(sys.modules, "serial", None)
    monkeypatch.setitem(sys.modules, "serial.tools", None)
    with caplog.at_level("WARNING", logger="lab_harness.discovery.serial_scanner"):
        assert scan_serial_ports() == []
    assert "pyserial not installed" in caplog.text


def test_no_ports_found(monkeypatch):
    _install_fake_pyserial(monkeypatch, [])
    assert scan_serial_ports() == []


def test_port_metadata_mapped_to_record(monkeypatch):
    """Each COM port becomes a SERIAL InstrumentRecord carrying its USB metadata."""
    _install_fake_pyserial(
        monkeypatch,
        [_port("COM3", description="USB Serial Port", manufacturer="FTDI", serial_number="A1B2C3")],
    )
    records = scan_serial_ports()
    assert len(records) == 1
    rec = records[0]
    assert rec.resource == "COM3"
    assert rec.bus == InstrumentBus.SERIAL
    assert rec.vendor == "FTDI"
    assert rec.model == "USB Serial Port"
    assert rec.serial == "A1B2C3"


def test_missing_metadata_becomes_empty_strings(monkeypatch):
    """Ports without manufacturer/description/serial (e.g. built-in UARTs) still yield records."""
    _install_fake_pyserial(monkeypatch, [_port("/dev/ttyS0")])
    rec = scan_serial_ports()[0]
    assert rec.resource == "/dev/ttyS0"
    assert rec.vendor == ""
    assert rec.model == ""
    assert rec.serial == ""


def test_multiple_ports_preserve_order(monkeypatch):
    _install_fake_pyserial(
        monkeypatch,
        [_port("COM1", description="Communications Port"), _port("COM7", manufacturer="Prolific")],
    )
    records = scan_serial_ports()
    assert [r.resource for r in records] == ["COM1", "COM7"]
    assert all(r.bus == InstrumentBus.SERIAL for r in records)

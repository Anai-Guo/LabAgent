"""Tests for visa_scanner (no PyVISA hardware required)."""

from __future__ import annotations

import sys
import types

import pytest

from lab_harness.discovery.visa_scanner import _detect_bus, _parse_idn, scan_visa_instruments
from lab_harness.models.instrument import InstrumentBus

# ---------------------------------------------------------------------------
# _parse_idn
# ---------------------------------------------------------------------------


def test_parse_idn_standard():
    """Standard IEEE 488.2 *IDN? response with four fields."""
    result = _parse_idn("KEITHLEY INSTRUMENTS INC.,MODEL 2400,1234567,C30")
    assert result["vendor"] == "KEITHLEY INSTRUMENTS INC."
    assert result["model"] == "MODEL 2400"
    assert result["serial"] == "1234567"
    assert result["firmware"] == "C30"


def test_parse_idn_short():
    """IDN with fewer than four fields fills missing ones as empty string."""
    result = _parse_idn("LAKESHORE,MODEL 425")
    assert result["vendor"] == "LAKESHORE"
    assert result["model"] == "MODEL 425"
    assert result["serial"] == ""
    assert result["firmware"] == ""


def test_parse_idn_empty():
    """Empty IDN string returns all empty fields."""
    result = _parse_idn("")
    assert result["vendor"] == ""
    assert result["model"] == ""
    assert result["serial"] == ""
    assert result["firmware"] == ""


def test_parse_idn_whitespace_stripping():
    """Leading/trailing whitespace in fields is stripped."""
    result = _parse_idn("  ACME ,  X100 , SN999 , v1.2 ")
    assert result["vendor"] == "ACME"
    assert result["model"] == "X100"
    assert result["serial"] == "SN999"
    assert result["firmware"] == "v1.2"


# ---------------------------------------------------------------------------
# _detect_bus
# ---------------------------------------------------------------------------


def test_detect_bus_gpib():
    """GPIB resource string detected correctly."""
    assert _detect_bus("GPIB0::5::INSTR") == InstrumentBus.GPIB


def test_detect_bus_usb():
    """USB resource string detected correctly."""
    assert _detect_bus("USB0::0x1234::0x5678::INSTR") == InstrumentBus.USB


def test_detect_bus_serial():
    """ASRL and COM resource strings detected as SERIAL."""
    assert _detect_bus("ASRL3::INSTR") == InstrumentBus.SERIAL
    assert _detect_bus("COM3") == InstrumentBus.SERIAL


def test_detect_bus_ethernet():
    """TCPIP resource string detected as ETHERNET."""
    assert _detect_bus("TCPIP0::192.168.1.100::INSTR") == InstrumentBus.ETHERNET


def test_detect_bus_unknown():
    """Unrecognized resource string returns UNKNOWN."""
    assert _detect_bus("SOMETHING_ELSE::1::INSTR") == InstrumentBus.UNKNOWN


def test_detect_bus_case_insensitive():
    """Detection is case-insensitive."""
    assert _detect_bus("gpib0::5::INSTR") == InstrumentBus.GPIB
    assert _detect_bus("usb0::1::INSTR") == InstrumentBus.USB
    assert _detect_bus("tcpip0::host::INSTR") == InstrumentBus.ETHERNET


# ---------------------------------------------------------------------------
# scan_visa_instruments (fake pyvisa module, no real bus access)
# ---------------------------------------------------------------------------


class _FakeInstrument:
    def __init__(self, idn):
        self._idn = idn
        self.closed = False

    def query(self, cmd):
        assert cmd == "*IDN?"
        if isinstance(self._idn, Exception):
            raise self._idn
        return self._idn

    def close(self):
        self.closed = True


class _FakeResourceManager:
    def __init__(self, replies):
        self.replies = replies
        self.opened = []

    def list_resources(self):
        return tuple(self.replies)

    def open_resource(self, resource, timeout=None):
        inst = _FakeInstrument(self.replies[resource])
        self.opened.append((resource, timeout, inst))
        return inst


@pytest.fixture
def fake_pyvisa(monkeypatch):
    """Install a fake ``pyvisa`` module; returns a setter for the bus replies."""

    def install(replies):
        rm = _FakeResourceManager(replies)
        module = types.ModuleType("pyvisa")
        module.ResourceManager = lambda: rm
        monkeypatch.setitem(sys.modules, "pyvisa", module)
        return rm

    return install


def _recorder():
    events = []

    def emit(name, **kwargs):
        events.append((name, kwargs))

    return events, emit


def test_scan_without_pyvisa_returns_empty_and_completes(monkeypatch):
    """Missing PyVISA yields no instruments but still emits start/complete."""
    monkeypatch.setitem(sys.modules, "pyvisa", None)
    events, emit = _recorder()
    assert scan_visa_instruments(emit=emit) == []
    assert events == [("instruments.scan_start", {}), ("instruments.complete", {"count": 0})]


def test_scan_parses_idn_and_closes_resources(fake_pyvisa):
    """Each resource is opened with the timeout, queried, parsed and closed."""
    rm = fake_pyvisa(
        {
            "GPIB0::24::INSTR": "KEITHLEY INSTRUMENTS INC.,MODEL 2400,1234567,C30\n",
            "TCPIP0::10.0.0.5::INSTR": "LSCI,MODEL336,LSA1234,2.9",
        }
    )
    records = scan_visa_instruments(timeout_ms=500)

    assert [r.resource for r in records] == ["GPIB0::24::INSTR", "TCPIP0::10.0.0.5::INSTR"]
    keithley, lakeshore = records
    assert keithley.bus == InstrumentBus.GPIB
    assert (keithley.vendor, keithley.model) == ("KEITHLEY INSTRUMENTS INC.", "MODEL 2400")
    assert (keithley.serial, keithley.firmware) == ("1234567", "C30")
    assert keithley.raw_idn == "KEITHLEY INSTRUMENTS INC.,MODEL 2400,1234567,C30"
    assert lakeshore.bus == InstrumentBus.ETHERNET
    assert lakeshore.display_name == "LSCI MODEL336"
    assert [(res, timeout) for res, timeout, _ in rm.opened] == [
        ("GPIB0::24::INSTR", 500),
        ("TCPIP0::10.0.0.5::INSTR", 500),
    ]
    assert all(inst.closed for _, _, inst in rm.opened)


def test_scan_query_failure_keeps_bare_record(fake_pyvisa):
    """A resource whose *IDN? query fails is still reported, without identity."""
    fake_pyvisa(
        {
            "ASRL3::INSTR": TimeoutError("VI_ERROR_TMO"),
            "USB0::0x0957::0x0607::MY1::INSTR": "Agilent Technologies,34401A,0,11-5-2",
        }
    )
    serial_rec, usb_rec = scan_visa_instruments()

    assert serial_rec.resource == "ASRL3::INSTR"
    assert serial_rec.bus == InstrumentBus.SERIAL
    assert (serial_rec.vendor, serial_rec.raw_idn) == ("", "")
    assert serial_rec.display_name == "ASRL3::INSTR"
    assert usb_rec.vendor == "Agilent Technologies"
    assert usb_rec.model == "34401A"


def test_scan_without_idn_query_does_not_open(fake_pyvisa):
    """query_idn=False lists resources without opening any of them."""
    rm = fake_pyvisa({"GPIB0::5::INSTR": "SHOULD,NOT,BE,READ"})
    records = scan_visa_instruments(query_idn=False)

    assert rm.opened == []
    assert [(r.bus, r.vendor) for r in records] == [(InstrumentBus.GPIB, "")]


def test_scan_emits_progress_events(fake_pyvisa):
    """emit receives scan_start, one resource_found per instrument, then complete."""
    fake_pyvisa(
        {
            "GPIB0::24::INSTR": "KEITHLEY INSTRUMENTS INC.,MODEL 2400,1234567,C30",
            "ASRL3::INSTR": OSError("port busy"),
        }
    )
    events, emit = _recorder()
    scan_visa_instruments(emit=emit)

    assert events == [
        ("instruments.scan_start", {}),
        (
            "instruments.resource_found",
            {"resource": "GPIB0::24::INSTR", "vendor": "KEITHLEY INSTRUMENTS INC.", "model": "MODEL 2400"},
        ),
        ("instruments.resource_found", {"resource": "ASRL3::INSTR", "vendor": "", "model": ""}),
        ("instruments.complete", {"count": 2}),
    ]

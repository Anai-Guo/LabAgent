"""Tests for pure functions in visa_scanner (no PyVISA hardware required)."""

from __future__ import annotations

from lab_harness.discovery.visa_scanner import _detect_bus, _parse_idn
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

"""Tests for the scan_instruments and classify_instruments harness tools.

The VISA scanner is monkeypatched so the tools run without PyVISA or any
connected instrument; classification uses the real built-in lookup table.
"""

from __future__ import annotations

import json

import lab_harness.discovery.visa_scanner as scanner_module
from lab_harness.harness.tools.base import ToolContext
from lab_harness.harness.tools.classify_tool import ClassifyInput, ClassifyInstrumentsTool
from lab_harness.harness.tools.scan_tool import ScanInput, ScanInstrumentsTool
from lab_harness.models.instrument import InstrumentRecord


def _payload(output: str):
    """Parse the JSON body that follows the tool's one-line summary."""
    return json.loads(output.split("\n", 1)[1])


def _records() -> list[InstrumentRecord]:
    return [
        InstrumentRecord(resource="GPIB0::24::INSTR", vendor="KEITHLEY", model="MODEL 2400"),
        InstrumentRecord(resource="GPIB0::16::INSTR", vendor="KEITHLEY", model="MODEL 2000"),
        InstrumentRecord(resource="GPIB0::12::INSTR", vendor="LSCI", model="MODEL425"),
    ]


async def test_scan_reports_found_instruments(monkeypatch):
    seen: dict = {}

    def fake_scan(timeout_ms=2000, **kwargs):
        seen["timeout_ms"] = timeout_ms
        return _records()[:2]

    monkeypatch.setattr(scanner_module, "scan_visa_instruments", fake_scan)

    result = await ScanInstrumentsTool().execute(ScanInput(timeout_ms=500), ToolContext())

    assert not result.is_error
    assert seen["timeout_ms"] == 500
    assert result.output.startswith("Found 2 instrument(s):")
    assert result.metadata == {"count": 2}
    assert _payload(result.output) == [
        {"resource": "GPIB0::24::INSTR", "vendor": "KEITHLEY", "model": "MODEL 2400"},
        {"resource": "GPIB0::16::INSTR", "vendor": "KEITHLEY", "model": "MODEL 2000"},
    ]


async def test_scan_with_no_instruments(monkeypatch):
    monkeypatch.setattr(scanner_module, "scan_visa_instruments", lambda **kw: [])

    result = await ScanInstrumentsTool().execute(ScanInput(), ToolContext())

    assert not result.is_error
    assert result.output.startswith("Found 0 instrument(s):")
    assert result.metadata == {"count": 0}
    assert _payload(result.output) == []


async def test_scan_failure_is_reported_as_error(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("no VISA backend")

    monkeypatch.setattr(scanner_module, "scan_visa_instruments", boom)

    result = await ScanInstrumentsTool().execute(ScanInput(), ToolContext())

    assert result.is_error
    assert result.output == "Scan failed: no VISA backend"


def test_scan_tool_schema_and_defaults():
    tool = ScanInstrumentsTool()
    schema = tool.to_api_schema()

    assert schema["function"]["name"] == "scan_instruments"
    assert "timeout_ms" in schema["function"]["parameters"]["properties"]
    assert ScanInput().timeout_ms == 2000
    assert tool.is_read_only(ScanInput())


async def test_classify_assigns_roles_from_provided_data(monkeypatch):
    def must_not_scan(**kwargs):
        raise AssertionError("live scan should not run when instrument_data is given")

    monkeypatch.setattr(scanner_module, "scan_visa_instruments", must_not_scan)
    data = [r.model_dump() for r in _records()]

    result = await ClassifyInstrumentsTool().execute(
        ClassifyInput(measurement_type="AHE", instrument_data=data), ToolContext()
    )

    assert not result.is_error
    assert result.output.startswith("Role assignments for AHE:")
    assert result.metadata == {"roles_assigned": 3}
    assert _payload(result.output) == {
        "source_meter": {"resource": "GPIB0::24::INSTR", "vendor": "KEITHLEY", "model": "MODEL 2400"},
        "dmm": {"resource": "GPIB0::16::INSTR", "vendor": "KEITHLEY", "model": "MODEL 2000"},
        "gaussmeter": {"resource": "GPIB0::12::INSTR", "vendor": "LSCI", "model": "MODEL425"},
    }


async def test_classify_falls_back_to_live_scan(monkeypatch):
    calls: list[dict] = []

    def fake_scan(**kwargs):
        calls.append(kwargs)
        return _records()[:1]

    monkeypatch.setattr(scanner_module, "scan_visa_instruments", fake_scan)

    result = await ClassifyInstrumentsTool().execute(ClassifyInput(measurement_type="iv"), ToolContext())

    assert not result.is_error
    assert len(calls) == 1
    assert result.metadata == {"roles_assigned": 1}
    assert _payload(result.output) == {
        "source_meter": {"resource": "GPIB0::24::INSTR", "vendor": "KEITHLEY", "model": "MODEL 2400"},
    }


async def test_classify_unknown_measurement_type_assigns_nothing():
    data = [r.model_dump() for r in _records()]

    result = await ClassifyInstrumentsTool().execute(
        ClassifyInput(measurement_type="NOT_A_TYPE", instrument_data=data), ToolContext()
    )

    assert not result.is_error
    assert result.metadata == {"roles_assigned": 0}
    assert _payload(result.output) == {}


async def test_classify_invalid_instrument_data_is_reported_as_error():
    result = await ClassifyInstrumentsTool().execute(
        ClassifyInput(measurement_type="IV", instrument_data=[{"vendor": "no resource field"}]),
        ToolContext(),
    )

    assert result.is_error
    assert result.output.startswith("Classification failed:")

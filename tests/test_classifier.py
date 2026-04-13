"""Tests for instrument classifier."""

from lab_harness.discovery.classifier import classify_instruments
from lab_harness.models.instrument import InstrumentBus, InstrumentRecord, LabInventory


def _make_instrument(resource: str, vendor: str, model: str) -> InstrumentRecord:
    return InstrumentRecord(
        resource=resource,
        vendor=vendor,
        model=model,
        bus=InstrumentBus.GPIB,
    )


def test_classify_ahe_basic():
    """Test AHE classification with typical instruments."""
    inventory = LabInventory(instruments=[
        _make_instrument("GPIB0::5::INSTR", "KEITHLEY INSTRUMENTS INC.", "MODEL 2400"),
        _make_instrument("GPIB0::2::INSTR", "KEITHLEY INSTRUMENTS INC.", "MODEL 2000"),
        _make_instrument("COM3", "LAKESHORE", "MODEL 425"),
    ])

    assignments = classify_instruments(inventory, "AHE")

    assert "source_meter" in assignments
    assert "dmm" in assignments
    assert "gaussmeter" in assignments
    assert assignments["source_meter"].resource == "GPIB0::5::INSTR"


def test_classify_iv_minimal():
    """IV measurement only needs a source meter."""
    inventory = LabInventory(instruments=[
        _make_instrument("GPIB0::5::INSTR", "KEITHLEY", "2400"),
    ])

    assignments = classify_instruments(inventory, "IV")
    assert "source_meter" in assignments


def test_classify_missing_instrument():
    """Gracefully handle missing instruments."""
    inventory = LabInventory(instruments=[
        _make_instrument("GPIB0::5::INSTR", "KEITHLEY", "2400"),
    ])

    assignments = classify_instruments(inventory, "AHE")
    # Should assign source_meter but miss dmm and gaussmeter
    assert "source_meter" in assignments
    assert "dmm" not in assignments

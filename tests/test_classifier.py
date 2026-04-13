"""Tests for instrument classifier."""

from unittest.mock import MagicMock

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


# ---------------------------------------------------------------------------
# LLM fallback tests
# ---------------------------------------------------------------------------

def _make_mock_router(response_json: str) -> MagicMock:
    """Create a mock LLMRouter whose complete() returns *response_json*."""
    router = MagicMock()
    router.complete.return_value = {
        "choices": [{"message": {"content": response_json}}],
    }
    return router


def test_classify_with_llm_fills_gaps():
    """LLM fallback fills roles that dict lookup could not match."""
    inventory = LabInventory(instruments=[
        # Known: matches source_meter via dict
        _make_instrument("GPIB0::5::INSTR", "KEITHLEY", "MODEL 2400"),
        # Unknown to the dict -- LLM should classify it as gaussmeter
        _make_instrument("USB0::0x1234::INSTR", "ACME", "MagSensor-9000"),
    ])

    llm_response = (
        '{"assignments": {'
        '  "USB0::0x1234::INSTR": {'
        '    "role": "gaussmeter",'
        '    "confidence": 0.85,'
        '    "reasoning": "MagSensor-9000 measures magnetic field"'
        "  }"
        "}}"
    )
    router = _make_mock_router(llm_response)

    assignments = classify_instruments(inventory, "AHE", router=router)

    # Dict should have filled source_meter
    assert assignments["source_meter"].resource == "GPIB0::5::INSTR"
    # LLM should have filled gaussmeter
    assert "gaussmeter" in assignments
    assert assignments["gaussmeter"].resource == "USB0::0x1234::INSTR"
    # LLM was actually invoked
    router.complete.assert_called_once()


def test_classify_with_llm_ignores_filled_roles():
    """LLM cannot override a role already filled by dict lookup."""
    inventory = LabInventory(instruments=[
        _make_instrument("GPIB0::5::INSTR", "KEITHLEY", "MODEL 2400"),
        _make_instrument("USB0::0x5678::INSTR", "ACME", "VoltMaster-X"),
    ])

    # LLM tries to reassign source_meter (already filled) and also dmm
    llm_response = (
        '{"assignments": {'
        '  "USB0::0x5678::INSTR": {'
        '    "role": "source_meter",'
        '    "confidence": 0.9,'
        '    "reasoning": "looks like a source meter"'
        "  }"
        "}}"
    )
    router = _make_mock_router(llm_response)

    assignments = classify_instruments(inventory, "AHE", router=router)

    # Dict match must be preserved
    assert assignments["source_meter"].resource == "GPIB0::5::INSTR"
    # LLM suggestion for source_meter was ignored -- no extra key added
    assert "dmm" not in assignments


def test_classify_without_router_unchanged():
    """Without a router, behaviour is identical to the original dict-only path."""
    inventory = LabInventory(instruments=[
        _make_instrument("GPIB0::5::INSTR", "KEITHLEY", "MODEL 2400"),
        _make_instrument("USB0::0x1234::INSTR", "ACME", "MagSensor-9000"),
    ])

    assignments = classify_instruments(inventory, "AHE", router=None)

    # Only the known instrument gets assigned
    assert "source_meter" in assignments
    assert "gaussmeter" not in assignments
    assert "dmm" not in assignments

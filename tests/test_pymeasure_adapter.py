"""Tests for drivers/pymeasure_adapter.py.

pymeasure is an optional dep. These tests never call .connect() on a real
adapter — they verify the model-mapping logic, the unsupported-model error
path, and the build() factory with mocked imports.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lab_harness.drivers import pymeasure_adapter as pm


def test_known_model_resolves_to_pymeasure_class():
    """The 'K2400' family maps to pymeasure.instruments.keithley.Keithley2400."""
    dotted = pm._resolve_pymeasure_class("MODEL 2400")
    assert dotted == "pymeasure.instruments.keithley.Keithley2400"


def test_longer_key_beats_shorter_substring():
    """'2410' should hit Keithley2400, '2450' should hit Keithley2450 — the
    mapping picks longer keys first so '2450' is not mis-routed to 2400."""
    assert pm._resolve_pymeasure_class("Keithley 2450") == ("pymeasure.instruments.keithley.Keithley2450")
    assert pm._resolve_pymeasure_class("Keithley 2410") == ("pymeasure.instruments.keithley.Keithley2400")


def test_unsupported_model_raises():
    """Unknown model → UnsupportedInstrumentError, not a silent mis-match."""
    with pytest.raises(pm.UnsupportedInstrumentError):
        pm._resolve_pymeasure_class("ObscureVendor X-1000")


def test_is_supported_predicate():
    assert pm.is_supported("Keithley 2400") is True
    assert pm.is_supported("SR830") is True
    assert pm.is_supported("Obscure") is False
    assert pm.is_supported("") is False


def test_role_hint():
    assert pm._role_hint("MODEL 2400") == "source_meter"
    assert pm._role_hint("SR830") == "lockin_amplifier"
    assert pm._role_hint("Unknown") is None


def test_list_supported_models_has_all_keys():
    """Every row in PYMEASURE_MODEL_MAP is exported by list_supported_models."""
    rows = pm.list_supported_models()
    assert len(rows) == len(pm.PYMEASURE_MODEL_MAP)
    for key, dotted, role in rows:
        assert key in pm.PYMEASURE_MODEL_MAP
        assert "pymeasure.instruments" in dotted
        assert role  # non-empty role hint


def test_build_rejects_unsupported_model_before_import():
    """build() should fail fast before importing pymeasure at all."""
    with pytest.raises(pm.UnsupportedInstrumentError):
        pm.build(resource="GPIB0::1::INSTR", model="Obscure", vendor="Vendor", role="source_meter")


def test_build_returns_driver_wrapper_for_known_model():
    """For a known model, build() returns a PyMeasureDriver not yet connected."""
    drv = pm.build(
        resource="GPIB0::5::INSTR",
        model="Keithley 2400",
        vendor="Keithley",
        role="source_meter",
    )
    assert isinstance(drv, pm.PyMeasureDriver)
    assert drv.connected is False
    assert drv.role == "source_meter"


def test_connect_raises_if_pymeasure_missing():
    """If importing pymeasure fails, connect() raises PyMeasureUnavailableError."""
    drv = pm.build(
        resource="GPIB0::5::INSTR",
        model="Keithley 2400",
        vendor="Keithley",
        role="source_meter",
    )
    with patch.object(pm.importlib, "import_module", side_effect=ImportError("no pymeasure")):
        with pytest.raises(pm.PyMeasureUnavailableError):
            drv.connect()


def test_role_enforcement_source_meter_only():
    """read_temperature should refuse on a source_meter-role driver."""
    drv = pm.build(
        resource="GPIB0::5::INSTR",
        model="Keithley 2400",
        vendor="Keithley",
        role="source_meter",
    )
    # Mock past the connect() gate so we can exercise the method dispatch
    drv._connected = True
    drv._pm_instrument = MagicMock(input_A=MagicMock(kelvin=300.0))
    with pytest.raises(NotImplementedError):
        drv.read_temperature()


def test_configure_source_current_uses_pymeasure_properties():
    """configure_source_current sets compliance_voltage on the underlying class."""
    mock_inst = MagicMock()
    mock_inst.apply_current = MagicMock()
    mock_inst.measure_voltage = MagicMock()
    drv = pm.PyMeasureDriver(
        resource="X",
        model="Keithley 2400",
        vendor="Keithley",
        role="source_meter",
        _pm_instrument=mock_inst,
        _connected=True,
    )
    drv.configure_source_current(compliance_v=15.0)
    mock_inst.apply_current.assert_called_once()
    assert mock_inst.compliance_voltage == 15.0
    mock_inst.measure_voltage.assert_called_once()


def test_measure_voltage_prefers_voltage_property():
    mock_inst = MagicMock()
    mock_inst.voltage = 2.5  # pymeasure Keithley2400 exposes this
    drv = pm.PyMeasureDriver(
        resource="X",
        model="Keithley 2400",
        vendor="Keithley",
        role="source_meter",
        _pm_instrument=mock_inst,
        _connected=True,
    )
    assert drv.measure_voltage() == pytest.approx(2.5)


def test_disconnect_idempotent_when_never_connected():
    """disconnect() on a never-connected driver should be a no-op."""
    drv = pm.build(resource="X", model="Keithley 2400", vendor="Keithley", role="source_meter")
    drv.disconnect()  # must not raise
    assert drv.connected is False


def test_context_manager_calls_connect_disconnect():
    """`with drv:` should round-trip connect/disconnect via __enter__/__exit__."""
    drv = pm.build(resource="X", model="Keithley 2400", vendor="Keithley", role="source_meter")
    connect_calls, disconnect_calls = [], []
    drv.connect = lambda: connect_calls.append(1) or setattr(drv, "_connected", True)
    drv.disconnect = lambda: disconnect_calls.append(1) or setattr(drv, "_connected", False)

    with drv:
        assert drv.connected is True
    assert len(connect_calls) == 1
    assert len(disconnect_calls) == 1

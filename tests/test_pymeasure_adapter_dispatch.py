"""Dispatch tests for PyMeasureDriver role methods and lifecycle.

These use plain fake classes (not MagicMock) so that ``hasattr`` checks in the
adapter see exactly the attributes a given fake defines. That lets us exercise
the fallback branches (``read()`` instead of ``voltage``, ``setpoint`` instead
of ``set_temperature_setpoint``, ...) and the "unknown instrument" errors.
pymeasure itself is never imported.
"""

from __future__ import annotations

import logging
import types

import pytest

from lab_harness.drivers import pymeasure_adapter as pm


def _driver(inst, role="source_meter", model="Keithley 2400"):
    return pm.PyMeasureDriver(
        resource="GPIB0::5::INSTR",
        model=model,
        vendor="Vendor",
        role=role,
        _pm_instrument=inst,
        _connected=True,
    )


class _Bare:
    """An instrument that exposes none of the attributes the adapter knows."""


# ── lifecycle ───────────────────────────────────────────────────────────


class _FakeAdapter:
    def __init__(self, fail=False):
        self.closed = 0
        self.fail = fail

    def close(self):
        self.closed += 1
        if self.fail:
            raise OSError("bus error")


class _FakeKeithley:
    def __init__(self, resource):
        self.resource = resource
        self.adapter = _FakeAdapter()


def _fake_import(name):
    if name == "pymeasure":
        return types.ModuleType("pymeasure")
    if name == "pymeasure.instruments.keithley":
        mod = types.ModuleType(name)
        mod.Keithley2400 = _FakeKeithley
        return mod
    raise ImportError(name)


def test_connect_instantiates_mapped_class_with_resource(monkeypatch):
    monkeypatch.setattr(pm.importlib, "import_module", _fake_import)
    drv = pm.build(resource="GPIB0::5::INSTR", model="Keithley 2400", vendor="Keithley", role="source_meter")
    drv.connect()
    assert drv.connected is True
    assert isinstance(drv._pm_instrument, _FakeKeithley)
    assert drv._pm_instrument.resource == "GPIB0::5::INSTR"
    first = drv._pm_instrument
    drv.connect()  # second call is a no-op
    assert drv._pm_instrument is first


def test_disconnect_closes_adapter_and_resets_state():
    inst = _FakeKeithley("X")
    drv = _driver(inst)
    drv.disconnect()
    assert inst.adapter.closed == 1
    assert drv.connected is False
    assert drv._pm_instrument is None


def test_disconnect_logs_and_swallows_close_error(caplog):
    inst = _FakeKeithley("X")
    inst.adapter = _FakeAdapter(fail=True)
    drv = _driver(inst)
    with caplog.at_level(logging.WARNING, logger=pm.logger.name):
        drv.disconnect()
    assert drv.connected is False
    assert "bus error" in caplog.text


def test_import_class_resolves_dotted_path():
    assert pm._import_class("collections.OrderedDict").__name__ == "OrderedDict"


# ── source_meter ────────────────────────────────────────────────────────


def test_set_current_prefers_source_current_then_current():
    a = types.SimpleNamespace(source_current=0.0)
    _driver(a).set_current(1e-3)
    assert a.source_current == 1e-3

    b = types.SimpleNamespace(current=0.0)
    _driver(b).set_current(2e-3)
    assert b.current == 2e-3

    with pytest.raises(NotImplementedError):
        _driver(_Bare()).set_current(1e-3)


def test_enable_and_disable_output_methods():
    calls = []
    inst = types.SimpleNamespace(
        enable_source=lambda: calls.append("on"),
        disable_source=lambda: calls.append("off"),
    )
    drv = _driver(inst)
    drv.enable_output()
    drv.disable_output()
    assert calls == ["on", "off"]


def test_enable_and_disable_output_via_property():
    inst = types.SimpleNamespace(output_enabled=None)
    drv = _driver(inst)
    drv.enable_output()
    assert inst.output_enabled is True
    drv.disable_output()
    assert inst.output_enabled is False


def test_disable_output_is_noop_when_not_connected():
    inst = types.SimpleNamespace(output_enabled=True)
    drv = _driver(inst)
    drv._connected = False
    drv.disable_output()
    assert inst.output_enabled is True


def test_measure_voltage_falls_back_to_read_then_errors():
    assert _driver(types.SimpleNamespace(read=lambda: "1.5")).measure_voltage() == pytest.approx(1.5)
    with pytest.raises(NotImplementedError):
        _driver(_Bare()).measure_voltage()


def test_set_voltage_fallbacks():
    inst = types.SimpleNamespace(voltage=0.0)
    _driver(inst).set_voltage(3.0)
    assert inst.voltage == 3.0

    class ReadOnly:
        @property
        def voltage(self):
            return 0.0

    with pytest.raises(NotImplementedError):
        _driver(ReadOnly()).set_voltage(1.0)
    with pytest.raises(NotImplementedError):
        _driver(_Bare()).set_voltage(1.0)


def test_measure_current_fallbacks_and_role():
    assert _driver(types.SimpleNamespace(read=lambda: 4e-9), role="dmm").measure_current() == pytest.approx(4e-9)
    with pytest.raises(NotImplementedError):
        _driver(_Bare(), role="electrometer").measure_current()
    with pytest.raises(NotImplementedError):
        _driver(types.SimpleNamespace(current=1.0), role="lcr_meter").measure_current()


def test_measure_voltage_nv_reads_voltage_or_read():
    assert _driver(types.SimpleNamespace(voltage=1e-9), role="nanovoltmeter").measure_voltage_nv() == 1e-9
    assert _driver(types.SimpleNamespace(read=lambda: 2e-9), role="dmm").measure_voltage_nv() == 2e-9
    with pytest.raises(NotImplementedError):
        _driver(_Bare(), role="nanovoltmeter").measure_voltage_nv()


# ── temperature controller ──────────────────────────────────────────────


def test_read_temperature_channels_and_fallback():
    inst = types.SimpleNamespace(
        input_A=types.SimpleNamespace(kelvin=4.2),
        input_B=types.SimpleNamespace(kelvin=77.0),
    )
    drv = _driver(inst, role="temperature_controller")
    assert drv.read_temperature("a") == pytest.approx(4.2)
    assert drv.read_temperature("B") == pytest.approx(77.0)

    plain = _driver(types.SimpleNamespace(temperature="295.5"), role="gaussmeter")
    assert plain.read_temperature() == pytest.approx(295.5)

    with pytest.raises(NotImplementedError):
        _driver(_Bare(), role="temperature_controller").read_temperature()


def test_set_temperature_method_and_setpoint_property():
    calls = []
    inst = types.SimpleNamespace(set_temperature_setpoint=lambda loop, k: calls.append((loop, k)))
    _driver(inst, role="temperature_controller").set_temperature(10.0, loop=2)
    assert calls == [(2, 10.0)]

    sp = types.SimpleNamespace(setpoint=0.0)
    _driver(sp, role="temperature_controller").set_temperature(300.0)
    assert sp.setpoint == 300.0

    with pytest.raises(NotImplementedError):
        _driver(sp, role="gaussmeter").set_temperature(1.0)


# ── LCR meter ───────────────────────────────────────────────────────────


def test_configure_lcr_sets_mode_level_and_frequency():
    inst = types.SimpleNamespace(mode=None, ac_voltage=None, frequency=None)
    _driver(inst, role="lcr_meter").configure_lcr(ac_volts=0.1, frequency_hz=1e3)
    assert (inst.mode, inst.ac_voltage, inst.frequency) == ("CPD", 0.1, 1e3)


def test_set_dc_bias_branches():
    a = types.SimpleNamespace(bias_voltage=0.0)
    _driver(a, role="lcr_meter").set_dc_bias(-1.0)
    assert a.bias_voltage == -1.0

    b = types.SimpleNamespace(dc_bias=0.0)
    _driver(b, role="lcr_meter").set_dc_bias(2.0)
    assert b.dc_bias == 2.0

    with pytest.raises(NotImplementedError):
        _driver(_Bare(), role="lcr_meter").set_dc_bias(1.0)


def test_enable_disable_bias():
    inst = types.SimpleNamespace(bias_enabled=False)
    drv = _driver(inst, role="lcr_meter")
    drv.enable_bias()
    assert inst.bias_enabled is True
    drv.disable_bias()
    assert inst.bias_enabled is False

    inst.bias_enabled = True
    drv._connected = False
    drv.disable_bias()
    assert inst.bias_enabled is True


def test_measure_capacitance_impedance_tuple_or_property():
    assert _driver(types.SimpleNamespace(impedance=(1e-12, 0.01)), role="lcr_meter").measure_capacitance() == 1e-12
    assert _driver(types.SimpleNamespace(capacitance="3e-12"), role="lcr_meter").measure_capacitance() == 3e-12
    with pytest.raises(NotImplementedError):
        _driver(_Bare(), role="lcr_meter").measure_capacitance()
    with pytest.raises(NotImplementedError):
        _driver(types.SimpleNamespace(capacitance=1.0), role="dmm").measure_capacitance()

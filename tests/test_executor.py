"""Tests for orchestrator/executor.py.

Executor is the real-instrument measurement layer. These tests mock the
driver registry so nothing actually touches VISA or pymeasure — we only
verify the executor's control flow (role lookup, sweep generation, safety
clamping, cleanup in finally).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lab_harness.drivers.registry import DriverRegistry
from lab_harness.models.measurement import (
    DataChannel,
    MeasurementPlan,
    MeasurementType,
    SweepAxis,
)
from lab_harness.orchestrator import executor

# ─────────────────────── Helpers ────────────────────────


def _iv_plan() -> MeasurementPlan:
    return MeasurementPlan(
        measurement_type=MeasurementType.IV,
        x_axis=SweepAxis(
            label="Current",
            unit="A",
            start=-1e-3,
            stop=1e-3,
            step=5e-4,
            role="source_meter",
        ),
        y_channels=[DataChannel(label="Voltage", unit="V", role="source_meter")],
        max_current_a=1e-3,
        max_voltage_v=20.0,
        settling_time_s=0.0,  # keep tests fast
    )


def _rt_plan() -> MeasurementPlan:
    return MeasurementPlan(
        measurement_type=MeasurementType.RT,
        x_axis=SweepAxis(
            label="Temperature",
            unit="K",
            start=100.0,
            stop=120.0,
            step=10.0,
            role="temperature_controller",
        ),
        y_channels=[DataChannel(label="Resistance", unit="Ohm", role="source_meter")],
        max_current_a=1e-5,
        max_voltage_v=20.0,
        max_temperature_k=300.0,
        settling_time_s=0.0,
    )


class _FakeSourceMeter:
    """Minimal duck-typed source meter: records the sweep and returns fake voltage."""

    def __init__(self):
        self.currents_set: list[float] = []
        self.output_enabled: bool = False
        self.output_disabled: bool = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def configure_source_current(self, compliance_v: float = 20.0):
        self.compliance_v = compliance_v

    def set_current(self, amps: float):
        self.currents_set.append(amps)

    def enable_output(self):
        self.output_enabled = True

    def disable_output(self):
        self.output_disabled = True

    def measure_voltage(self) -> float:
        # Linear IV: V = 100 Ω * I
        return 100.0 * self.currents_set[-1]


class _FakeTempController:
    def __init__(self):
        self.setpoints: list[float] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def set_temperature(self, target_k: float):
        self.setpoints.append(target_k)

    def read_temperature(self):
        return self.setpoints[-1]


# ─────────────────────── Tests ────────────────────────


def test_supported_types_lists_iv_and_rt():
    assert "IV" in executor.supported_types()
    assert "RT" in executor.supported_types()


def test_unsupported_measurement_raises():
    plan = _iv_plan()
    registry = DriverRegistry()
    with pytest.raises(executor.UnsupportedMeasurementError):
        executor.execute(plan, "NONSENSE", registry)


def test_missing_role_raises():
    plan = _iv_plan()
    registry = DriverRegistry()  # empty
    with pytest.raises(executor.MissingRoleError):
        executor.execute(plan, "IV", registry)


def test_iv_sweep_produces_ohmic_line():
    """IV on a 100-Ω fake source meter returns V = 100·I for every point."""
    plan = _iv_plan()
    fake = _FakeSourceMeter()

    registry = DriverRegistry(configs={"source_meter": {"driver": "stub", "resource": "X"}})
    # Bypass registry.get_driver by pre-populating the instance cache.
    registry._instances["source_meter"] = fake

    points = executor.execute(plan, "IV", registry)

    # Sweep = [-1e-3, -5e-4, 0, 5e-4, 1e-3]
    assert len(points) == plan.x_axis.num_points
    x_key = "Current (A)"
    y_key = "Voltage (V)"
    for p in points:
        assert p[y_key] == pytest.approx(100.0 * p[x_key])

    # Cleanup: disable_output always called in finally.
    assert fake.output_enabled and fake.output_disabled


def test_iv_clamps_to_max_current():
    """If the sweep overruns plan.max_current_a, points are clamped."""
    plan = _iv_plan()
    plan.max_current_a = 5e-4  # tighten limit after the sweep was defined
    fake = _FakeSourceMeter()
    registry = DriverRegistry(configs={"source_meter": {"driver": "stub", "resource": "X"}})
    registry._instances["source_meter"] = fake

    executor.execute(plan, "IV", registry)

    # Currents actually set on the source meter must respect the tighter limit
    assert max(fake.currents_set) == pytest.approx(5e-4)
    assert min(fake.currents_set) == pytest.approx(-5e-4)


def test_iv_disables_output_even_when_measurement_raises():
    """A fault mid-sweep must still trip the finally-block cleanup."""
    plan = _iv_plan()
    fake = _FakeSourceMeter()
    fake.measure_voltage = MagicMock(side_effect=RuntimeError("instrument fell off"))
    registry = DriverRegistry(configs={"source_meter": {"driver": "stub", "resource": "X"}})
    registry._instances["source_meter"] = fake

    with pytest.raises(RuntimeError, match="fell off"):
        executor.execute(plan, "IV", registry)

    assert fake.output_disabled is True


def test_iv_progress_callback_fires_for_every_point():
    plan = _iv_plan()
    fake = _FakeSourceMeter()
    registry = DriverRegistry(configs={"source_meter": {"driver": "stub", "resource": "X"}})
    registry._instances["source_meter"] = fake

    calls = []

    def cb(i, n, row):
        calls.append((i, n, row))

    executor.execute(plan, "IV", registry, progress=cb)
    assert len(calls) == plan.x_axis.num_points
    # i should be the loop index, n the total count
    assert calls[0][0] == 0
    assert calls[-1][0] == plan.x_axis.num_points - 1
    assert all(c[1] == plan.x_axis.num_points for c in calls)


def test_rt_sweep_computes_resistance_from_voltage_over_current():
    """RT: V / I_probe = R. Fake returns V = 1 mV, I_probe = 1e-5 A → R = 100 Ω."""
    plan = _rt_plan()
    fake_src = _FakeSourceMeter()
    fake_src.measure_voltage = lambda: 1e-3  # 1 mV
    fake_tc = _FakeTempController()

    registry = DriverRegistry(
        configs={
            "source_meter": {"driver": "stub", "resource": "X1"},
            "temperature_controller": {"driver": "stub", "resource": "X2"},
        }
    )
    registry._instances["source_meter"] = fake_src
    registry._instances["temperature_controller"] = fake_tc

    points = executor.execute(plan, "RT", registry)
    assert len(points) == plan.x_axis.num_points
    for p in points:
        assert p["Resistance (Ohm)"] == pytest.approx(100.0, rel=1e-6)


def test_rt_skips_setpoints_above_max_temperature():
    """RT execution should not request temperatures above plan.max_temperature_k."""
    plan = _rt_plan()
    plan.max_temperature_k = 105.0  # only the first setpoint (100 K) is legal

    fake_src = _FakeSourceMeter()
    fake_src.measure_voltage = lambda: 1e-3
    fake_tc = _FakeTempController()

    registry = DriverRegistry(
        configs={
            "source_meter": {"driver": "stub", "resource": "X1"},
            "temperature_controller": {"driver": "stub", "resource": "X2"},
        }
    )
    registry._instances["source_meter"] = fake_src
    registry._instances["temperature_controller"] = fake_tc

    points = executor.execute(plan, "RT", registry)
    assert all(sp <= 105.0 for sp in fake_tc.setpoints)
    assert len(points) == len(fake_tc.setpoints)


def test_probe_registry_true_when_all_drivers_connect():
    class OkDrv:
        _connected = False

        def connect(self):
            self._connected = True

        def disconnect(self):
            self._connected = False

    registry = DriverRegistry(configs={"source_meter": {"driver": "stub", "resource": "X"}})
    registry._instances["source_meter"] = OkDrv()
    assert executor.probe_registry(registry) is True


def test_probe_registry_false_when_any_driver_raises():
    class BadDrv:
        def connect(self):
            raise RuntimeError("VISA timeout")

        def disconnect(self):
            pass

    registry = DriverRegistry(configs={"source_meter": {"driver": "stub", "resource": "X"}})
    registry._instances["source_meter"] = BadDrv()
    assert executor.probe_registry(registry) is False

"""Tests for the executor types added in P1: DELTA, HIGH_R, BREAKDOWN,
SEEBECK, TUNNELING, PHOTO_IV.

All tests use fake duck-typed drivers — no VISA, no pymeasure. Focus is on
the per-type control flow (correct role lookups, correct readout pattern,
proper safety cleanup).
"""

from __future__ import annotations

import pytest

from lab_harness.drivers.registry import DriverRegistry
from lab_harness.models.measurement import (
    DataChannel,
    MeasurementPlan,
    MeasurementType,
    SweepAxis,
)
from lab_harness.orchestrator import executor

# ──────────────────────────── Fakes ────────────────────────────


class _FakeCurrentSource:
    """K6221-like current source."""

    def __init__(self):
        self.currents_set: list[float] = []
        self.output_enabled = False
        self.output_disabled = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def set_current(self, amps):
        self.currents_set.append(amps)

    def enable_output(self):
        self.output_enabled = True

    def disable_output(self):
        self.output_disabled = True


class _FakeNanoVoltmeter:
    """K2182A-like nanovoltmeter. Returns R = 100 Ω · I based on last current set
    by an external source (to simulate a real DELTA setup)."""

    def __init__(self, source_ref=None, resistance=100.0):
        self._source = source_ref
        self._resistance = resistance

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def measure_voltage_nv(self):
        if self._source is None or not self._source.currents_set:
            return 0.0
        return self._resistance * self._source.currents_set[-1]


class _FakeElectrometer:
    """K6517B-like electrometer: voltage source + picoamp measure."""

    def __init__(self, resistance=1e9):
        self._resistance = resistance
        self.voltage = 0.0
        self.output_enabled = False
        self.output_disabled = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def configure_source_voltage(self, compliance_i=1e-6):
        self.compliance_i = compliance_i

    def set_voltage(self, v):
        self.voltage = v

    def enable_output(self):
        self.output_enabled = True

    def disable_output(self):
        self.output_disabled = True

    def measure_current(self):
        return self.voltage / self._resistance


class _FakeSourceMeterV:
    """Source-meter in voltage-source mode (for BREAKDOWN, TUNNELING, PHOTO_IV).

    ``current_fn`` maps applied voltage to returned current.
    """

    def __init__(self, current_fn):
        self._current_fn = current_fn
        self.voltage = 0.0
        self.output_enabled = False
        self.output_disabled = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def configure_source_voltage(self, compliance_i=1e-6):
        self.compliance_i = compliance_i

    def set_voltage(self, v):
        self.voltage = v

    def enable_output(self):
        self.output_enabled = True

    def disable_output(self):
        self.output_disabled = True

    def measure_current(self):
        return self._current_fn(self.voltage)


class _FakeTempController:
    def __init__(self):
        self.setpoints: list[float] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def set_temperature(self, target_k):
        self.setpoints.append(target_k)

    def read_temperature(self):
        return self.setpoints[-1]


# ──────────────────────────── Helpers ────────────────────────────


def _plan(
    mt: MeasurementType,
    x_start: float,
    x_stop: float,
    x_step: float,
    x_label: str,
    x_unit: str,
    y_label: str,
    y_unit: str,
    **kwargs,
) -> MeasurementPlan:
    return MeasurementPlan(
        measurement_type=mt,
        x_axis=SweepAxis(label=x_label, unit=x_unit, start=x_start, stop=x_stop, step=x_step, role="src"),
        y_channels=[DataChannel(label=y_label, unit=y_unit, role="src")],
        settling_time_s=0.0,
        **kwargs,
    )


def _reg_with(**roles) -> DriverRegistry:
    """Build a registry pre-populated with fake driver instances."""
    configs = {r: {"driver": "stub", "resource": "X"} for r in roles}
    reg = DriverRegistry(configs=configs)
    for role, drv in roles.items():
        reg._instances[role] = drv
    return reg


# ──────────────────────────── DELTA ────────────────────────────


def test_delta_computes_resistance_from_plus_minus_current():
    src = _FakeCurrentSource()
    nv = _FakeNanoVoltmeter(source_ref=src, resistance=100.0)
    plan = _plan(
        MeasurementType.DELTA,
        -1e-3,
        1e-3,
        5e-4,
        "Current",
        "A",
        "Resistance",
        "Ohm",
        max_current_a=1e-3,
    )

    points = executor.execute(plan, "DELTA", _reg_with(ac_current_source=src, nanovoltmeter=nv))

    # 5 sweep points; each should yield R ≈ 100 Ω (but the I=0 point is NaN)
    assert len(points) == 5
    for p in points:
        if p["Current (A)"] != 0.0:
            assert p["Resistance (Ohm)"] == pytest.approx(100.0, rel=1e-3)

    # The delta protocol must have toggled both +I and -I between points.
    assert src.output_enabled and src.output_disabled
    assert any(c > 0 for c in src.currents_set)
    assert any(c < 0 for c in src.currents_set)


# ──────────────────────────── HIGH_R ────────────────────────────


def test_high_r_ohmic_line():
    em = _FakeElectrometer(resistance=1e9)  # 1 GΩ
    plan = _plan(
        MeasurementType.HIGH_R,
        0.0,
        100.0,
        50.0,
        "Voltage",
        "V",
        "Current",
        "A",
        max_voltage_v=100.0,
        max_current_a=1e-6,
    )
    points = executor.execute(plan, "HIGH_R", _reg_with(electrometer=em))
    for p in points:
        if p["Voltage (V)"] == 0.0:
            assert p["Current (A)"] == pytest.approx(0.0)
        else:
            assert p["Current (A)"] == pytest.approx(p["Voltage (V)"] / 1e9, rel=1e-6)
    assert em.output_disabled


# ──────────────────────────── BREAKDOWN ────────────────────────────


def test_breakdown_stops_at_compliance_trip():
    """Breakdown executor must cut the sweep short when current reaches compliance."""
    # Device current: quadratic in V → hits 1 µA at V=10 V
    # compliance 1e-6 → breakdown should trip around there.
    sm = _FakeSourceMeterV(current_fn=lambda v: 1e-8 * (v**2))
    plan = _plan(
        MeasurementType.BREAKDOWN,
        0.0,
        50.0,
        5.0,
        "Voltage",
        "V",
        "Current",
        "A",
        max_voltage_v=50.0,
        max_current_a=1e-6,  # compliance
    )
    points = executor.execute(plan, "BREAKDOWN", _reg_with(source_meter=sm))
    # 1e-8 * V^2 >= 0.95e-6 ⇒ V >= sqrt(95) ≈ 9.75 V
    # sweep steps are 0, 5, 10, 15, ...; the first point at/over 9.75 is V=10.
    assert points[-1]["Voltage (V)"] == pytest.approx(10.0)
    assert len(points) <= 3  # should stop early
    assert sm.output_disabled


def test_breakdown_runs_full_sweep_when_no_trip():
    """If current never hits compliance, we sweep to the end."""
    sm = _FakeSourceMeterV(current_fn=lambda v: 1e-12)  # always tiny
    plan = _plan(
        MeasurementType.BREAKDOWN,
        0.0,
        20.0,
        5.0,
        "Voltage",
        "V",
        "Current",
        "A",
        max_voltage_v=20.0,
        max_current_a=1e-6,
    )
    points = executor.execute(plan, "BREAKDOWN", _reg_with(source_meter=sm))
    assert points[-1]["Voltage (V)"] == pytest.approx(20.0)


# ──────────────────────────── SEEBECK ────────────────────────────


def test_seebeck_records_voltage_vs_temperature():
    tc = _FakeTempController()
    calls = {"n": 0}

    class NV:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def measure_voltage_nv(self):
            calls["n"] += 1
            return 1e-6 * calls["n"]  # 1 µV per step

    plan = _plan(
        MeasurementType.SEEBECK,
        100.0,
        300.0,
        50.0,
        "Temperature",
        "K",
        "V_thermo",
        "V",
        max_temperature_k=310.0,
    )
    points = executor.execute(plan, "SEEBECK", _reg_with(temperature_controller=tc, nanovoltmeter=NV()))
    assert len(points) == 5
    assert points[0]["V_thermo (V)"] == pytest.approx(1e-6)
    assert points[-1]["V_thermo (V)"] == pytest.approx(5e-6)
    # Every setpoint must be within max_temperature_k
    assert all(sp <= 310.0 for sp in tc.setpoints)


# ──────────────────────────── TUNNELING ────────────────────────────


def test_tunneling_voltage_sweep_returns_nonlinear_current():
    """Tunneling is voltage-sweep, current-readout; analysis computes dI/dV."""
    # Sinh-like tunneling response
    import math

    sm = _FakeSourceMeterV(current_fn=lambda v: 1e-9 * math.sinh(v))
    plan = _plan(
        MeasurementType.TUNNELING,
        -0.5,
        0.5,
        0.1,
        "Voltage",
        "V",
        "Current",
        "A",
        max_voltage_v=1.0,
        max_current_a=1e-6,
    )
    points = executor.execute(plan, "TUNNELING", _reg_with(source_meter=sm))
    # Should see symmetric around 0 (sinh is odd)
    vs = [p["Voltage (V)"] for p in points]
    assert min(vs) == pytest.approx(-0.5)
    assert max(vs) == pytest.approx(0.5)
    # I(+v) = -I(-v) for odd sinh
    pos = [p for p in points if p["Voltage (V)"] > 0]
    neg = [p for p in points if p["Voltage (V)"] < 0]
    for p, n in zip(
        sorted(pos, key=lambda x: x["Voltage (V)"]),
        sorted(neg, key=lambda x: -x["Voltage (V)"]),
    ):
        assert p["Current (A)"] == pytest.approx(-n["Current (A)"], rel=1e-6)


# ──────────────────────────── PHOTO_IV ────────────────────────────


def test_photo_iv_sweeps_full_voltage_range():
    """Solar-cell IV: just a voltage sweep, stopping at the endpoints (no early exit)."""
    sm = _FakeSourceMeterV(current_fn=lambda v: -1e-3 + 1e-4 * v)  # diode-ish
    plan = _plan(
        MeasurementType.PHOTO_IV,
        0.0,
        0.7,
        0.1,
        "Voltage",
        "V",
        "Current",
        "A",
        max_voltage_v=1.0,
        max_current_a=1e-2,
    )
    points = executor.execute(plan, "PHOTO_IV", _reg_with(source_meter=sm))
    assert len(points) == plan.x_axis.num_points
    assert points[0]["Voltage (V)"] == pytest.approx(0.0)
    assert points[-1]["Voltage (V)"] == pytest.approx(0.7)


# ──────────────────────────── supported_types ────────────────────────────


def test_supported_types_contains_all_p1_additions():
    expected = {"IV", "RT", "DELTA", "HIGH_R", "BREAKDOWN", "SEEBECK", "TUNNELING", "PHOTO_IV"}
    assert expected.issubset(set(executor.supported_types()))

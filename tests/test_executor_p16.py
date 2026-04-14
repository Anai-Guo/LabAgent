"""Tests for P1.6 executors: EIS, CHRONOAMPEROMETRY, PHOTORESPONSE, POTENTIOMETRY."""

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

# ─────────────── Fake drivers ───────────────


class _FakePotEIS:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def run_eis(
        self,
        e_dc,
        frequency_start,
        frequency_stop,
        amplitude=0.01,
        points_per_decade=10,
    ):
        # 3 points, impedance = R + 1/(jωC) with R=100Ω, C=1µF
        import math

        R, C = 100.0, 1e-6
        freqs = [frequency_start, (frequency_start * frequency_stop) ** 0.5, frequency_stop]
        out = []
        for f in freqs:
            omega = 2 * math.pi * f
            # Z = R + 1/(jωC) = R - j/(ωC)
            z = complex(R, -1 / (omega * C))
            out.append((f, z))
        return out


class _FakePotCA:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def run_ca(self, e_hold, duration_s, sample_interval_s=0.1):
        # Cottrell decay: I(t) = I0 / sqrt(t+tau)
        import math

        n = max(1, int(duration_s / sample_interval_s) + 1)
        out = []
        for k in range(n):
            t = k * sample_interval_s
            current = 1e-6 / math.sqrt(t + 0.1)
            out.append((t, current))
        return out


class _FakePotOCP:
    """Returns a slowly-drifting OCP."""

    def __init__(self):
        self._base = 0.25
        self._call = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read_ocp(self):
        self._call += 1
        return self._base + 1e-3 * self._call


class _FakeSourceMeterV:
    def __init__(self, current_at_bias):
        self._current = current_at_bias
        self.voltage = 0.0
        self.output_enabled = False
        self.output_disabled = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def configure_source_voltage(self, compliance_i=1e-6):
        pass

    def set_voltage(self, v):
        self.voltage = v

    def enable_output(self):
        self.output_enabled = True

    def disable_output(self):
        self.output_disabled = True

    def measure_current(self):
        return self._current


# ─────────────── Helpers ───────────────


def _reg_with(**roles) -> DriverRegistry:
    configs = {r: {"driver": "stub", "resource": "X"} for r in roles}
    reg = DriverRegistry(configs=configs)
    for role, drv in roles.items():
        reg._instances[role] = drv
    return reg


# ─────────────── EIS ───────────────


def test_eis_returns_nyquist_rows():
    pot = _FakePotEIS()
    plan = MeasurementPlan(
        measurement_type=MeasurementType.EIS,
        x_axis=SweepAxis(label="Frequency", unit="Hz", start=1.0, stop=1e5, step=1.0, role="potentiostat"),
        y_channels=[
            DataChannel(label="Re_Z", unit="Ohm", role="potentiostat"),
            DataChannel(label="Im_Z", unit="Ohm", role="potentiostat"),
        ],
        max_voltage_v=1.0,
        max_current_a=1e-3,
        settling_time_s=0.0,
    )
    points = executor.execute(plan, "EIS", _reg_with(potentiostat=pot))
    assert len(points) == 3
    # Each row must have frequency + Re_Z + Im_Z
    for p in points:
        assert "Frequency (Hz)" in p
        assert "Re_Z (Ohm)" in p
        assert "Im_Z (Ohm)" in p
        # R=100 → Re(Z) should be exactly 100 for our fake
        assert p["Re_Z (Ohm)"] == pytest.approx(100.0)
        assert p["Im_Z (Ohm)"] < 0  # capacitive → negative imaginary


# ─────────────── CHRONOAMPEROMETRY ───────────────


def test_chronoamperometry_records_current_decay():
    pot = _FakePotCA()
    plan = MeasurementPlan(
        measurement_type=MeasurementType.CHRONOAMPEROMETRY,
        x_axis=SweepAxis(label="Time", unit="s", start=0.0, stop=1.0, step=0.1, role="potentiostat"),
        y_channels=[DataChannel(label="Current", unit="A", role="potentiostat")],
        max_voltage_v=1.0,
        max_current_a=1e-3,
        settling_time_s=0.0,
    )
    points = executor.execute(plan, "CHRONOAMPEROMETRY", _reg_with(potentiostat=pot))
    assert len(points) > 0
    # Cottrell decay: later times should show smaller current
    assert points[0]["Current (A)"] > points[-1]["Current (A)"]


# ─────────────── PHOTORESPONSE ───────────────


def test_photoresponse_time_sweep_returns_current_readings():
    sm = _FakeSourceMeterV(current_at_bias=1e-7)
    plan = MeasurementPlan(
        measurement_type=MeasurementType.PHOTORESPONSE,
        x_axis=SweepAxis(label="Time", unit="s", start=0.0, stop=0.05, step=0.01, role="source_meter"),
        y_channels=[DataChannel(label="Current", unit="A", role="source_meter")],
        max_voltage_v=5.0,
        max_current_a=1e-4,
        settling_time_s=0.0,
    )
    points = executor.execute(plan, "PHOTORESPONSE", _reg_with(source_meter=sm))
    assert len(points) >= 3
    for p in points:
        assert p["Current (A)"] == pytest.approx(1e-7)
    assert sm.output_disabled is True


# ─────────────── POTENTIOMETRY ───────────────


def test_potentiometry_prefers_potentiostat_over_electrometer():
    pot = _FakePotOCP()
    plan = MeasurementPlan(
        measurement_type=MeasurementType.POTENTIOMETRY,
        x_axis=SweepAxis(label="Time", unit="s", start=0.0, stop=0.03, step=0.01, role="potentiostat"),
        y_channels=[DataChannel(label="E_OCP", unit="V", role="potentiostat")],
        max_voltage_v=5.0,
        max_current_a=1e-6,
        settling_time_s=0.0,
    )
    points = executor.execute(plan, "POTENTIOMETRY", _reg_with(potentiostat=pot))
    assert len(points) >= 3
    # OCP drift: monotonic increase
    ocps = [p["E_OCP (V)"] for p in points]
    assert ocps == sorted(ocps)


def test_potentiometry_falls_back_to_electrometer():
    class _FakeElectro:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def measure_voltage(self):
            return 0.42

    plan = MeasurementPlan(
        measurement_type=MeasurementType.POTENTIOMETRY,
        x_axis=SweepAxis(label="Time", unit="s", start=0.0, stop=0.03, step=0.01, role="electrometer"),
        y_channels=[DataChannel(label="E_OCP", unit="V", role="electrometer")],
        max_voltage_v=5.0,
        max_current_a=1e-6,
        settling_time_s=0.0,
    )
    points = executor.execute(plan, "POTENTIOMETRY", _reg_with(electrometer=_FakeElectro()))
    for p in points:
        assert p["E_OCP (V)"] == pytest.approx(0.42)


def test_supported_types_contains_p16_additions():
    expected = {"EIS", "CHRONOAMPEROMETRY", "PHOTORESPONSE", "POTENTIOMETRY"}
    assert expected.issubset(set(executor.supported_types()))

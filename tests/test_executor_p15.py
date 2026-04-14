"""Tests for executor types added in P1.5: CV, TRANSFER, OUTPUT, CYCLIC_VOLTAMMETRY."""

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


class _FakeLCR:
    def __init__(self, mott_schottky_slope=1e14):
        # C vs V follows a Mott-Schottky-ish 1/C^2 ∝ V for a depletion region
        # Here keep it simple: C(V) = C0 / (1 + V/V0)^(1/2)
        self._C0 = 1e-9  # 1 nF
        self._V0 = 5.0
        self.bias = 0.0
        self.bias_enabled = False
        self.bias_disabled = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def configure_lcr(self, ac_volts=0.05, frequency_hz=1e6):
        self.ac = ac_volts
        self.f = frequency_hz

    def set_dc_bias(self, v):
        self.bias = v

    def enable_bias(self):
        self.bias_enabled = True

    def disable_bias(self):
        self.bias_disabled = True

    def measure_capacitance(self):
        import math

        return self._C0 / math.sqrt(1 + max(0, self.bias) / self._V0)


class _FakeGate:
    """Source-meter in voltage-source mode for the gate."""

    def __init__(self):
        self.voltage = 0.0
        self.output_enabled = False
        self.output_disabled = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def configure_source_voltage(self, compliance_i=1e-9):
        self.comp = compliance_i

    def set_voltage(self, v):
        self.voltage = v

    def enable_output(self):
        self.output_enabled = True

    def disable_output(self):
        self.output_disabled = True


class _FakeDrain:
    """Drain source-meter. Returns an Id depending on Vgs set on a companion gate."""

    def __init__(self, gate_ref=None, v_th=0.5, mu_cox_w_over_l=1e-4):
        self._gate = gate_ref
        self._v_th = v_th
        self._k = mu_cox_w_over_l
        self.voltage = 0.0
        self.output_enabled = False
        self.output_disabled = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def configure_source_voltage(self, compliance_i=1e-3):
        self.comp = compliance_i

    def set_voltage(self, v):
        self.voltage = v

    def enable_output(self):
        self.output_enabled = True

    def disable_output(self):
        self.output_disabled = True

    def measure_current(self):
        """MOSFET saturation / triode: depends on V_gs and V_ds."""
        vgs = self._gate.voltage if self._gate else 0.0
        if vgs <= self._v_th:
            return 0.0
        v_ov = vgs - self._v_th
        vds = self.voltage
        if vds < v_ov:
            # triode
            return self._k * (v_ov * vds - 0.5 * vds * vds)
        # saturation
        return 0.5 * self._k * v_ov * v_ov


class _FakePotentiostat:
    """Returns a synthetic triangular CV with a peak."""

    def __init__(self):
        self.connected_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def connect(self):
        self.connected_calls += 1

    def disconnect(self):
        pass

    def run_cv(
        self,
        e_start,
        e_vertex,
        e_step=0.001,
        scan_rate_mv_per_s=100.0,
        n_cycles=1,
    ):
        # Build a triangular E sweep and a peak-shaped I(E).
        import math

        n = max(2, int(abs(e_vertex - e_start) / e_step) + 1)
        forward = [e_start + i * (e_vertex - e_start) / (n - 1) for i in range(n)]
        backward = list(reversed(forward))
        points = []
        for e in forward + backward:
            # Gaussian-ish peak at E = 0.1 V
            current = 1e-6 * math.exp(-((e - 0.1) ** 2) / 0.01)
            points.append((e, current))
        return points


# ─────────────── Helpers ───────────────


def _reg_with(**roles) -> DriverRegistry:
    configs = {r: {"driver": "stub", "resource": "X"} for r in roles}
    reg = DriverRegistry(configs=configs)
    for role, drv in roles.items():
        reg._instances[role] = drv
    return reg


# ─────────────── CV (C-V) ───────────────


def test_cv_sweep_returns_capacitance_vs_bias():
    lcr = _FakeLCR()
    plan = MeasurementPlan(
        measurement_type=MeasurementType.CV,
        x_axis=SweepAxis(label="Bias", unit="V", start=-2.0, stop=2.0, step=1.0, role="lcr_meter"),
        y_channels=[DataChannel(label="C", unit="F", role="lcr_meter")],
        max_voltage_v=5.0,
        settling_time_s=0.0,
    )
    points = executor.execute(plan, "CV", _reg_with(lcr_meter=lcr))
    assert len(points) == plan.x_axis.num_points
    # Capacitance at V=-2 should be larger than at V=+2 (depletion grows w/ +V).
    # Here our FakeLCR only depletes on positive bias, so equal at V<=0.
    c_at_minus = [p["C (F)"] for p in points if p["Bias (V)"] == -2.0][0]
    c_at_plus = [p["C (F)"] for p in points if p["Bias (V)"] == 2.0][0]
    assert c_at_minus > c_at_plus
    assert lcr.bias_enabled and lcr.bias_disabled


def test_cv_bias_cleanup_on_error():
    """If capacitance read raises, bias must still be disabled in finally."""
    lcr = _FakeLCR()
    lcr.measure_capacitance = lambda: (_ for _ in ()).throw(RuntimeError("probe fell"))
    plan = MeasurementPlan(
        measurement_type=MeasurementType.CV,
        x_axis=SweepAxis(label="Bias", unit="V", start=-1.0, stop=1.0, step=1.0, role="lcr_meter"),
        y_channels=[DataChannel(label="C", unit="F", role="lcr_meter")],
        max_voltage_v=5.0,
        settling_time_s=0.0,
    )
    with pytest.raises(RuntimeError, match="probe fell"):
        executor.execute(plan, "CV", _reg_with(lcr_meter=lcr))
    assert lcr.bias_disabled is True


# ─────────────── FET TRANSFER ───────────────


def test_transfer_produces_monotonic_increase_above_vth():
    gate = _FakeGate()
    drain = _FakeDrain(gate_ref=gate, v_th=0.5, mu_cox_w_over_l=1e-4)
    plan = MeasurementPlan(
        measurement_type=MeasurementType.TRANSFER,
        x_axis=SweepAxis(label="V_gs", unit="V", start=0.0, stop=2.0, step=0.5, role="source_meter_gate"),
        y_channels=[DataChannel(label="I_d", unit="A", role="source_meter_drain")],
        max_voltage_v=2.0,
        max_current_a=1e-3,
        settling_time_s=0.0,
    )
    # Attach the optional v_ds_fixed through object.__setattr__ because the
    # plan is a frozen-ish pydantic model — the executor reads it via
    # getattr() with a default, so arbitrary attrs are fine at runtime.
    object.__setattr__(plan, "v_ds_fixed", 0.1)

    points = executor.execute(plan, "TRANSFER", _reg_with(source_meter_gate=gate, source_meter_drain=drain))
    # Below V_th (0.5 V) Id=0; above it should rise
    id_at_0 = [p["I_d (A)"] for p in points if p["V_gs (V)"] == 0.0][0]
    id_at_2 = [p["I_d (A)"] for p in points if p["V_gs (V)"] == 2.0][0]
    assert id_at_0 == pytest.approx(0.0)
    assert id_at_2 > id_at_0
    assert drain.output_disabled and gate.output_disabled


# ─────────────── FET OUTPUT ───────────────


def test_output_curve_nested_sweep_shape():
    gate = _FakeGate()
    drain = _FakeDrain(gate_ref=gate, v_th=0.5)

    plan = MeasurementPlan(
        measurement_type=MeasurementType.OUTPUT,
        x_axis=SweepAxis(label="V_ds", unit="V", start=0.0, stop=1.0, step=0.5, role="source_meter_drain"),
        outer_sweep=SweepAxis(label="V_gs", unit="V", start=0.5, stop=2.0, step=0.5, role="source_meter_gate"),
        y_channels=[DataChannel(label="I_d", unit="A", role="source_meter_drain")],
        max_voltage_v=3.0,
        max_current_a=1e-3,
        settling_time_s=0.0,
    )
    points = executor.execute(plan, "OUTPUT", _reg_with(source_meter_gate=gate, source_meter_drain=drain))
    # 4 gate values × 3 drain values = 12 points
    assert len(points) == 4 * 3
    # Each row should contain both V_gs and V_ds columns
    for p in points:
        assert "V_gs (V)" in p
        assert "V_ds (V)" in p
        assert "I_d (A)" in p


# ─────────────── CYCLIC_VOLTAMMETRY ───────────────


def test_cyclic_voltammetry_runs_through_potentiostat():
    pot = _FakePotentiostat()

    plan = MeasurementPlan(
        measurement_type=MeasurementType.CYCLIC_VOLTAMMETRY,
        x_axis=SweepAxis(label="Potential", unit="V", start=-0.2, stop=0.5, step=0.01, role="potentiostat"),
        y_channels=[DataChannel(label="Current", unit="A", role="potentiostat")],
        max_voltage_v=1.0,
        max_current_a=1e-3,
        settling_time_s=0.0,
    )
    object.__setattr__(plan, "scan_rate_mv_per_s", 100.0)
    object.__setattr__(plan, "n_cycles", 1)

    points = executor.execute(plan, "CYCLIC_VOLTAMMETRY", _reg_with(potentiostat=pot))
    # Fake potentiostat returns N forward + N backward; result must be non-empty
    assert len(points) > 0
    # Row layout: Potential & Current columns
    for p in points:
        assert "Potential (V)" in p
        assert "Current (A)" in p


# ─────────────── Registry coverage ───────────────


def test_supported_types_contains_p15_additions():
    expected = {"CV", "TRANSFER", "OUTPUT", "CYCLIC_VOLTAMMETRY"}
    assert expected.issubset(set(executor.supported_types()))

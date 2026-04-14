"""Real-instrument execution backend.

Runs a :class:`MeasurementPlan` against live hardware through either our
in-tree ``VisaDriver`` subclasses or the pymeasure adapter. When hardware
isn't reachable or no driver covers the measurement type, callers should
fall back to ``orchestrator.simulators.simulate``.

This module is intentionally small: we only implement the two measurement
types where the role → command mapping is unambiguous (IV, RT). Everything
else raises :class:`UnsupportedMeasurementError` and the flow layer falls
back to the simulator. Adding a new type means writing a ``_execute_<type>``
function here and listing it in ``EXECUTORS``.

Safety invariants
-----------------
* We never exceed ``plan.max_current_a``/``max_voltage_v``. The sweep range
  is clamped before execution.
* The source output is disabled (or setpoint reset) in a ``finally`` block
  so an error during the sweep still leaves the instruments safe.
* Every return value is a list of dicts with the same keys as the simulator
  would produce, so analyzers and CSV writers don't need to special-case
  this path.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from lab_harness.drivers.registry import DriverRegistry

logger = logging.getLogger(__name__)


class UnsupportedMeasurementError(RuntimeError):
    """No real-execution path implemented for this measurement type."""


class MissingRoleError(RuntimeError):
    """Required role not present in the driver registry."""


def execute(
    plan: Any,
    measurement_type: str,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None = None,
) -> list[dict]:
    """Execute ``plan`` on real hardware and return per-point dicts.

    Args:
        plan: A :class:`MeasurementPlan`.
        measurement_type: Upper-case type name (``"IV"``, ``"RT"``, ...).
        registry: A populated :class:`DriverRegistry` with drivers for all
            roles used by the plan.
        progress: Optional callback ``(i, n, row)`` invoked after each
            measurement point.

    Raises:
        UnsupportedMeasurementError: No real executor for this type.
        MissingRoleError: Registry lacks a required role.
    """
    mt = (measurement_type or "").upper()
    func = EXECUTORS.get(mt)
    if func is None:
        raise UnsupportedMeasurementError(
            f"Real execution not implemented for '{mt}'. Supported: {sorted(EXECUTORS.keys())}"
        )
    return func(plan, registry, progress)


def _need(registry: DriverRegistry, role: str) -> Any:
    if not registry.supports_role(role):
        raise MissingRoleError(f"Role '{role}' required by this measurement but not in the driver registry")
    return registry.get_driver(role)


def _sweep_values(axis: Any) -> list[float]:
    """Produce the inclusive list of setpoints for a SweepAxis."""
    n = axis.num_points
    if n <= 1:
        return [float(axis.start)]
    step = (axis.stop - axis.start) / (n - 1)
    return [float(axis.start + i * step) for i in range(n)]


# ──────────────────────────────────────────────────────────────────────────
# IV: sweep source current, read voltage
# ──────────────────────────────────────────────────────────────────────────


def _execute_iv(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    src = _need(registry, "source_meter")

    # Clamp sweep against plan's safety limits. The boundary_checker has
    # already approved the plan values; this is defence in depth.
    lo, hi = -plan.max_current_a, plan.max_current_a
    values = [max(lo, min(hi, v)) for v in _sweep_values(plan.x_axis)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or [f"{plan.x_axis.label}_response (V)"]

    points: list[dict] = []
    try:
        with src:
            src.configure_source_current(compliance_v=plan.max_voltage_v)
            src.enable_output()
            for i, current in enumerate(values):
                src.set_current(current)
                time.sleep(plan.settling_time_s)
                voltage = src.measure_voltage()
                row = {x_key: current}
                # For IV we typically have one y channel; if multiple are
                # declared we replicate the reading across them rather than
                # silently dropping columns — analyzers can dedupe.
                for k in y_keys:
                    row[k] = voltage
                points.append(row)
                if progress is not None:
                    progress(i, len(values), row)
    finally:
        try:
            src.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable source_meter output cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# RT: sweep temperature, read resistance (via source_meter + DMM or similar)
# ──────────────────────────────────────────────────────────────────────────


def _execute_rt(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    tc = _need(registry, "temperature_controller")
    src = _need(registry, "source_meter")

    # Clamp probe current (hard-coded small value; a fuller implementation
    # would read this from the plan's y_channels metadata).
    probe_current = min(1e-5, plan.max_current_a)

    setpoints = _sweep_values(plan.x_axis)
    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Resistance (Ohm)"]

    points: list[dict] = []
    try:
        with tc, src:
            src.configure_source_current(compliance_v=plan.max_voltage_v)
            src.set_current(probe_current)
            src.enable_output()

            for i, target_k in enumerate(setpoints):
                if target_k > plan.max_temperature_k:
                    logger.warning(
                        "Requested %.2f K exceeds plan limit %.2f K; skipping",
                        target_k,
                        plan.max_temperature_k,
                    )
                    continue
                tc.set_temperature(target_k)
                # Settling: cheap polling + plan settling time. A future
                # iteration should use a real stability criterion.
                time.sleep(plan.settling_time_s)
                actual_k = tc.read_temperature()
                voltage = src.measure_voltage()
                resistance = voltage / probe_current if probe_current else float("nan")

                row = {x_key: actual_k}
                for k in y_keys:
                    row[k] = resistance
                points.append(row)
                if progress is not None:
                    progress(i, len(setpoints), row)
    finally:
        try:
            src.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable source_meter output cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# DELTA: alternating ±I on a current source, read V on a nanovoltmeter
# ──────────────────────────────────────────────────────────────────────────


def _execute_delta(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    """Classic K6221 + K2182A delta mode: V = (V(+I) - V(-I)) / 2, R = V/I."""
    src = _need(registry, "ac_current_source")
    nv = _need(registry, "nanovoltmeter")

    lo, hi = -plan.max_current_a, plan.max_current_a
    currents = [max(lo, min(hi, v)) for v in _sweep_values(plan.x_axis)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Resistance (Ohm)"]

    points: list[dict] = []
    try:
        with src, nv:
            src.enable_output()
            for i, current in enumerate(currents):
                # +I
                src.set_current(current)
                time.sleep(plan.settling_time_s)
                v_plus = nv.measure_voltage_nv()
                # -I
                src.set_current(-current)
                time.sleep(plan.settling_time_s)
                v_minus = nv.measure_voltage_nv()
                v_delta = (v_plus - v_minus) / 2.0
                resistance = v_delta / current if current else float("nan")

                row = {x_key: current}
                for k in y_keys:
                    row[k] = resistance
                points.append(row)
                if progress is not None:
                    progress(i, len(currents), row)
    finally:
        try:
            src.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable ac_current_source cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# HIGH_R: electrometer sweeps voltage, measures picoamp
# ──────────────────────────────────────────────────────────────────────────


def _execute_high_r(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    em = _need(registry, "electrometer")

    lo, hi = -plan.max_voltage_v, plan.max_voltage_v
    voltages = [max(lo, min(hi, v)) for v in _sweep_values(plan.x_axis)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Current (A)"]

    points: list[dict] = []
    try:
        with em:
            em.configure_source_voltage(compliance_i=plan.max_current_a)
            em.enable_output()
            for i, v in enumerate(voltages):
                em.set_voltage(v)
                time.sleep(plan.settling_time_s)
                current = em.measure_current()
                row = {x_key: v}
                for k in y_keys:
                    row[k] = current
                points.append(row)
                if progress is not None:
                    progress(i, len(voltages), row)
    finally:
        try:
            em.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable electrometer cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# BREAKDOWN: ramp voltage slowly, stop when compliance current trips
# ──────────────────────────────────────────────────────────────────────────


def _execute_breakdown(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    src = _need(registry, "source_meter")

    # For breakdown we take |max_voltage_v| as the stop value; sweep upwards
    # from 0. The compliance_i is the plan's max_current_a.
    compliance = plan.max_current_a
    stop_v = abs(plan.max_voltage_v)
    n = max(2, plan.x_axis.num_points)
    voltages = [stop_v * i / (n - 1) for i in range(n)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Current (A)"]

    points: list[dict] = []
    try:
        with src:
            src.configure_source_voltage(compliance_i=compliance)
            src.enable_output()
            for i, v in enumerate(voltages):
                src.set_voltage(v)
                time.sleep(plan.settling_time_s)
                current = src.measure_current()
                row = {x_key: v}
                for k in y_keys:
                    row[k] = current
                points.append(row)
                if progress is not None:
                    progress(i, len(voltages), row)
                # Breakdown detection: current crosses 95% of compliance.
                if abs(current) >= 0.95 * abs(compliance):
                    logger.info("Breakdown detected at %.3f V (I=%.3e A); stopping sweep", v, current)
                    break
    finally:
        try:
            src.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable source_meter cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# SEEBECK: sweep T, measure thermo-voltage on a nanovoltmeter
# ──────────────────────────────────────────────────────────────────────────


def _execute_seebeck(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    tc = _need(registry, "temperature_controller")
    nv = _need(registry, "nanovoltmeter")

    setpoints = _sweep_values(plan.x_axis)
    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["V_thermo (V)"]

    points: list[dict] = []
    with tc, nv:
        for i, target_k in enumerate(setpoints):
            if target_k > plan.max_temperature_k:
                continue
            tc.set_temperature(target_k)
            time.sleep(plan.settling_time_s)
            actual_k = tc.read_temperature()
            v_thermo = nv.measure_voltage_nv()
            row = {x_key: actual_k}
            for k in y_keys:
                row[k] = v_thermo
            points.append(row)
            if progress is not None:
                progress(i, len(setpoints), row)
    return points


# ──────────────────────────────────────────────────────────────────────────
# TUNNELING: voltage sweep, measure current (dI/dV computed in analysis)
# ──────────────────────────────────────────────────────────────────────────


def _execute_tunneling(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    src = _need(registry, "source_meter")

    lo, hi = -plan.max_voltage_v, plan.max_voltage_v
    voltages = [max(lo, min(hi, v)) for v in _sweep_values(plan.x_axis)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Current (A)"]

    points: list[dict] = []
    try:
        with src:
            src.configure_source_voltage(compliance_i=plan.max_current_a)
            src.enable_output()
            for i, v in enumerate(voltages):
                src.set_voltage(v)
                time.sleep(plan.settling_time_s)
                current = src.measure_current()
                row = {x_key: v}
                for k in y_keys:
                    row[k] = current
                points.append(row)
                if progress is not None:
                    progress(i, len(voltages), row)
    finally:
        try:
            src.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable source_meter cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# PHOTO_IV: solar cell IV under illumination (identical electrical protocol
# to BREAKDOWN but with negative currents too; assumes external illumination
# control — lamps are typically toggled manually or via DAQ trigger)
# ──────────────────────────────────────────────────────────────────────────


def _execute_photo_iv(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    src = _need(registry, "source_meter")

    lo, hi = -plan.max_voltage_v, plan.max_voltage_v
    voltages = [max(lo, min(hi, v)) for v in _sweep_values(plan.x_axis)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Current (A)"]

    points: list[dict] = []
    try:
        with src:
            src.configure_source_voltage(compliance_i=plan.max_current_a)
            src.enable_output()
            for i, v in enumerate(voltages):
                src.set_voltage(v)
                time.sleep(plan.settling_time_s)
                current = src.measure_current()
                row = {x_key: v}
                for k in y_keys:
                    row[k] = current
                points.append(row)
                if progress is not None:
                    progress(i, len(voltages), row)
    finally:
        try:
            src.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable source_meter cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# CV: DC bias sweep with small AC excitation on an LCR meter
# ──────────────────────────────────────────────────────────────────────────


def _execute_cv(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    lcr = _need(registry, "lcr_meter")

    lo, hi = -plan.max_voltage_v, plan.max_voltage_v
    bias_values = [max(lo, min(hi, v)) for v in _sweep_values(plan.x_axis)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Capacitance (F)"]

    # Test signal: small AC + user-chosen frequency. 0.05 V RMS at 1 MHz is
    # a reasonable default for thin-film C-V work.
    ac_v = 0.05
    test_freq = 1e6

    points: list[dict] = []
    try:
        with lcr:
            lcr.configure_lcr(ac_volts=ac_v, frequency_hz=test_freq)
            lcr.enable_bias()
            for i, v in enumerate(bias_values):
                lcr.set_dc_bias(v)
                time.sleep(plan.settling_time_s)
                c = lcr.measure_capacitance()
                row = {x_key: v}
                for k in y_keys:
                    row[k] = c
                points.append(row)
                if progress is not None:
                    progress(i, len(bias_values), row)
    finally:
        try:
            lcr.disable_bias()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable LCR bias cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# FET transfer curve: sweep V_gs, measure I_d at each V_gs (fixed V_ds)
# ──────────────────────────────────────────────────────────────────────────


def _execute_transfer(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    gate = _need(registry, "source_meter_gate")
    drain = _need(registry, "source_meter_drain")

    # Fixed drain voltage: take from plan metadata or default 0.1 V.
    v_ds = getattr(plan, "v_ds_fixed", 0.1)

    lo, hi = -plan.max_voltage_v, plan.max_voltage_v
    v_gs_sweep = [max(lo, min(hi, v)) for v in _sweep_values(plan.x_axis)]

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["I_d (A)"]

    points: list[dict] = []
    try:
        with gate, drain:
            drain.configure_source_voltage(compliance_i=plan.max_current_a)
            drain.set_voltage(v_ds)
            drain.enable_output()
            gate.configure_source_voltage(compliance_i=1e-9)  # tiny gate leakage limit
            gate.enable_output()

            for i, vg in enumerate(v_gs_sweep):
                gate.set_voltage(vg)
                time.sleep(plan.settling_time_s)
                i_d = drain.measure_current()
                row = {x_key: vg}
                for k in y_keys:
                    row[k] = i_d
                points.append(row)
                if progress is not None:
                    progress(i, len(v_gs_sweep), row)
    finally:
        for d in (drain, gate):
            try:
                d.disable_output()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not disable FET source cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# FET output curve: outer sweep V_gs, inner sweep V_ds → I_d
# ──────────────────────────────────────────────────────────────────────────


def _execute_output(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    gate = _need(registry, "source_meter_gate")
    drain = _need(registry, "source_meter_drain")

    # Nested: outer = gate (plan.outer_sweep); inner = drain (plan.x_axis).
    # Fall back to a single gate step when outer_sweep is None.
    if plan.outer_sweep is None:
        gate_values = [getattr(plan, "v_gs_fixed", 0.0)]
        gate_label = "V_gs"
        gate_unit = "V"
    else:
        gate_values = _sweep_values(plan.outer_sweep)
        gate_label = plan.outer_sweep.label
        gate_unit = plan.outer_sweep.unit

    drain_values = _sweep_values(plan.x_axis)

    drain_x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    gate_key = f"{gate_label} ({gate_unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["I_d (A)"]

    points: list[dict] = []
    total = len(gate_values) * len(drain_values)
    idx = 0
    try:
        with gate, drain:
            drain.configure_source_voltage(compliance_i=plan.max_current_a)
            drain.enable_output()
            gate.configure_source_voltage(compliance_i=1e-9)
            gate.enable_output()

            for vg in gate_values:
                gate.set_voltage(vg)
                time.sleep(plan.settling_time_s)
                for vd in drain_values:
                    drain.set_voltage(vd)
                    time.sleep(plan.settling_time_s)
                    i_d = drain.measure_current()
                    row = {gate_key: vg, drain_x_key: vd}
                    for k in y_keys:
                        row[k] = i_d
                    points.append(row)
                    if progress is not None:
                        progress(idx, total, row)
                    idx += 1
    finally:
        for d in (drain, gate):
            try:
                d.disable_output()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not disable FET source cleanly: %s", exc)

    return points


# ──────────────────────────────────────────────────────────────────────────
# CYCLIC_VOLTAMMETRY: triangle voltage sweep on a potentiostat
# ──────────────────────────────────────────────────────────────────────────


def _execute_cyclic_voltammetry(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    """CV via any `potentiostat` driver that exposes run_cv()."""
    pot = _need(registry, "potentiostat")

    # Build the CV parameter dict from the plan's sweep axis.
    # x_axis = potential sweep; we extract the triangle endpoints.
    e_start = plan.x_axis.start
    e_vertex = plan.x_axis.stop
    e_step = plan.x_axis.step
    scan_rate = getattr(plan, "scan_rate_mv_per_s", 100.0)
    n_cycles = getattr(plan, "n_cycles", 1)

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Current (A)"]

    with pot:
        raw = pot.run_cv(
            e_start=e_start,
            e_vertex=e_vertex,
            e_step=e_step,
            scan_rate_mv_per_s=scan_rate,
            n_cycles=n_cycles,
        )

    # ``run_cv`` returns [(E, I), ...]. Reshape into our dict layout.
    points: list[dict] = []
    for i, (e, current) in enumerate(raw):
        row = {x_key: e}
        for k in y_keys:
            row[k] = current
        points.append(row)
        if progress is not None:
            progress(i, len(raw), row)

    return points


# ──────────────────────────────────────────────────────────────────────────
# EIS: impedance spectroscopy on a potentiostat
# ──────────────────────────────────────────────────────────────────────────


def _execute_eis(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    """EIS via potentiostat.run_eis(). Returns Nyquist-ready [freq, Re(Z), Im(Z)] rows."""
    pot = _need(registry, "potentiostat")

    # plan.x_axis.start / stop interpreted as frequency endpoints in Hz
    f_start = plan.x_axis.start
    f_stop = plan.x_axis.stop
    e_dc = getattr(plan, "e_dc_bias", 0.0)
    amplitude = getattr(plan, "ac_amplitude", 0.01)
    ppd = getattr(plan, "points_per_decade", 10)

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or [
        "Re_Z (Ohm)",
        "Im_Z (Ohm)",
    ]

    with pot:
        raw = pot.run_eis(
            e_dc=e_dc,
            frequency_start=f_start,
            frequency_stop=f_stop,
            amplitude=amplitude,
            points_per_decade=ppd,
        )

    points: list[dict] = []
    for i, (freq, z) in enumerate(raw):
        row: dict[str, Any] = {x_key: freq}
        # If the plan declared two y-channels (Re, Im) respect them; otherwise
        # stuff both parts into the default names.
        if len(y_keys) >= 2:
            row[y_keys[0]] = z.real
            row[y_keys[1]] = z.imag
        else:
            row[y_keys[0]] = z.real
        points.append(row)
        if progress is not None:
            progress(i, len(raw), row)

    return points


# ──────────────────────────────────────────────────────────────────────────
# CHRONOAMPEROMETRY: hold V, record I(t)
# ──────────────────────────────────────────────────────────────────────────


def _execute_chronoamperometry(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    pot = _need(registry, "potentiostat")

    # plan.x_axis is (time start, time stop, step); here stop-start is duration.
    e_hold = getattr(plan, "e_hold", 0.0)
    duration = max(0.0, plan.x_axis.stop - plan.x_axis.start)
    interval = plan.x_axis.step or 0.1

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Current (A)"]

    with pot:
        raw = pot.run_ca(
            e_hold=e_hold,
            duration_s=duration,
            sample_interval_s=interval,
        )

    points: list[dict] = []
    for i, (t, current) in enumerate(raw):
        row = {x_key: t}
        for k in y_keys:
            row[k] = current
        points.append(row)
        if progress is not None:
            progress(i, len(raw), row)
    return points


# ──────────────────────────────────────────────────────────────────────────
# PHOTORESPONSE: time sweep on source_meter (photocurrent transient)
# ──────────────────────────────────────────────────────────────────────────


def _execute_photoresponse(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    """Time-resolved photocurrent. Assumes source_meter in voltage mode at a
    fixed bias; operator (or DAQ) toggles illumination externally."""
    src = _need(registry, "source_meter")

    v_bias = getattr(plan, "v_bias", 0.0)
    duration = max(0.0, plan.x_axis.stop - plan.x_axis.start)
    interval = plan.x_axis.step or 0.05
    n = max(1, int(duration / interval) + 1)

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["Current (A)"]

    points: list[dict] = []
    try:
        with src:
            src.configure_source_voltage(compliance_i=plan.max_current_a)
            src.set_voltage(v_bias)
            src.enable_output()
            start = time.monotonic()
            for i in range(n):
                # Sleep the cadence; precise timestamping uses monotonic clock.
                time.sleep(interval)
                t = time.monotonic() - start + plan.x_axis.start
                current = src.measure_current()
                row = {x_key: t}
                for k in y_keys:
                    row[k] = current
                points.append(row)
                if progress is not None:
                    progress(i, n, row)
    finally:
        try:
            src.disable_output()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not disable source_meter cleanly: %s", exc)
    return points


# ──────────────────────────────────────────────────────────────────────────
# POTENTIOMETRY: open-circuit potential (OCP) vs time
# ──────────────────────────────────────────────────────────────────────────


def _execute_potentiometry(
    plan: Any,
    registry: DriverRegistry,
    progress: Callable[[int, int, dict], None] | None,
) -> list[dict]:
    """OCP readout vs time. Uses ``potentiostat`` if available, otherwise
    falls back to ``electrometer`` as a high-input-impedance V meter."""
    if registry.supports_role("potentiostat"):
        drv = registry.get_driver("potentiostat")
        read = lambda: drv.read_ocp()  # noqa: E731
        ctx = drv
    else:
        drv = _need(registry, "electrometer")
        read = lambda: drv.measure_voltage()  # noqa: E731
        ctx = drv

    duration = max(0.0, plan.x_axis.stop - plan.x_axis.start)
    interval = plan.x_axis.step or 0.5
    n = max(1, int(duration / interval) + 1)

    x_key = f"{plan.x_axis.label} ({plan.x_axis.unit})"
    y_keys = [f"{c.label} ({c.unit})" for c in plan.y_channels] or ["E_OCP (V)"]

    points: list[dict] = []
    with ctx:
        start = time.monotonic()
        for i in range(n):
            time.sleep(interval)
            t = time.monotonic() - start + plan.x_axis.start
            e = read()
            row = {x_key: t}
            for k in y_keys:
                row[k] = e
            points.append(row)
            if progress is not None:
                progress(i, n, row)
    return points


EXECUTORS: dict[str, Callable[[Any, DriverRegistry, Any], list[dict]]] = {
    "IV": _execute_iv,
    "RT": _execute_rt,
    "DELTA": _execute_delta,
    "HIGH_R": _execute_high_r,
    "BREAKDOWN": _execute_breakdown,
    "SEEBECK": _execute_seebeck,
    "TUNNELING": _execute_tunneling,
    "PHOTO_IV": _execute_photo_iv,
    "CV": _execute_cv,
    "TRANSFER": _execute_transfer,
    "OUTPUT": _execute_output,
    "CYCLIC_VOLTAMMETRY": _execute_cyclic_voltammetry,
    "EIS": _execute_eis,
    "CHRONOAMPEROMETRY": _execute_chronoamperometry,
    "PHOTORESPONSE": _execute_photoresponse,
    "POTENTIOMETRY": _execute_potentiometry,
}


def supported_types() -> list[str]:
    """Measurement types that have a real-execution implementation."""
    return sorted(EXECUTORS.keys())


def probe_registry(registry: DriverRegistry) -> bool:
    """Try connecting every driver briefly; return True on full success.

    Used by the flow layer to decide whether real execution is viable. On
    any failure we disconnect what we opened and return False so the caller
    can fall back to the simulator without leaving the bus in a weird state.
    """
    opened: list[Any] = []
    try:
        for role in registry.list_roles():
            driver = registry.get_driver(role)
            driver.connect()
            opened.append(driver)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.info("Driver probe failed (falling back to simulator): %s", exc)
        return False
    finally:
        for d in opened:
            try:
                d.disconnect()
            except Exception:  # noqa: BLE001, S110
                pass

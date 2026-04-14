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


EXECUTORS: dict[str, Callable[[Any, DriverRegistry, Any], list[dict]]] = {
    "IV": _execute_iv,
    "RT": _execute_rt,
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

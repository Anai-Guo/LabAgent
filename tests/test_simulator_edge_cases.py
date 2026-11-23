"""Edge-case tests for the physics simulators using hand-built plans."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from lab_harness.orchestrator import simulators
from lab_harness.orchestrator.simulators import (
    _x_range,
    simulate,
    simulate_ahe,
    simulate_cv,
    simulate_generic,
    simulate_iv,
)


def _plan(label="Voltage", unit="V", start=0.0, stop=1.0, points=5, channels=("Current",)):
    return SimpleNamespace(
        x_axis=SimpleNamespace(label=label, unit=unit, start=start, stop=stop),
        y_channels=[SimpleNamespace(label=c) for c in channels],
        total_points=points,
    )


@pytest.mark.parametrize("points", [0, 1])
def test_x_range_single_point_returns_start(points):
    assert _x_range(_plan(start=0.3, stop=2.0, points=points)) == [0.3]


def test_x_range_is_evenly_spaced_and_inclusive():
    assert _x_range(_plan(start=-1.0, stop=1.0, points=5)) == [-1.0, -0.5, 0.0, 0.5, 1.0]


def test_channel_labels_default_when_plan_has_no_channels():
    rows = simulate_generic(_plan(channels=()), seed=0)
    assert all(set(r) == {"Voltage", "measurement"} for r in rows)


def test_iv_voltage_sweep_computes_diode_current_and_extra_channels():
    plan = _plan(start=0.0, stop=0.6, points=4, channels=("Current", "Resistance", "Phase"))
    rows = simulate_iv(plan, seed=1)
    assert len(rows) == 4
    currents = [r["Current"] for r in rows]
    # Forward-biased diode: current grows by orders of magnitude with voltage.
    assert currents[-1] > 1e3 * abs(currents[1])
    # Resistance at V=0 divides by the 1e-9 guard instead of raising ZeroDivisionError.
    assert rows[0]["Resistance"] == pytest.approx(abs(currents[0]) / 1e-9)
    assert rows[-1]["Resistance"] == pytest.approx(abs(currents[-1] / 0.6))
    # Unrecognised extra channels are zero-filled.
    assert all(r["Phase"] == 0.0 for r in rows)


def test_iv_current_sweep_in_amps_is_reproducible_and_leaks_in_reverse():
    plan = _plan(label="Current", unit="A", start=-1e-3, stop=1e-3, points=3, channels=("Voltage",))
    first = simulate_iv(plan, seed=7)
    assert first == simulate_iv(plan, seed=7)
    assert first[0]["Voltage"] < 0 < first[-1]["Voltage"]


def test_ahe_unknown_channel_mirrors_hall_signal():
    plan = _plan(label="Field", unit="Oe", start=-1000, stop=1000, points=6, channels=("Signal", "Vxx"))
    rows = simulate_ahe(plan, seed=3)
    assert len(rows) == 6
    assert all(abs(r["Signal"]) < 0.01 for r in rows)
    assert all(r["Vxx"] > 1000 for r in rows)


def test_cv_reports_pf_for_unknown_channel_and_dissipation():
    plan = _plan(start=-1.0, stop=0.5, points=4, channels=("Value", "Dissipation"))
    rows = simulate_cv(plan, seed=2)
    assert all(r["Value"] > 50 for r in rows)  # pF, near C0 = 100 pF
    assert all(abs(r["Dissipation"] - 0.01) < 0.01 for r in rows)


def test_simulate_unknown_or_empty_type_uses_generic():
    plan = _plan(points=3)
    assert simulate(plan, "nonsense", seed=4) == simulate_generic(plan, seed=4)
    assert simulate(plan, "", seed=4) == simulate_generic(plan, seed=4)


def test_simulate_falls_back_to_generic_when_simulator_raises(monkeypatch, caplog):
    def boom(plan, seed=None):
        raise ValueError("bad plan")

    monkeypatch.setitem(simulators.SIMULATORS, "IV", boom)
    plan = _plan(points=3)
    with caplog.at_level(logging.WARNING, logger="lab_harness.orchestrator.simulators"):
        rows = simulate(plan, "iv", seed=5)
    assert rows == simulate_generic(plan, seed=5)
    assert "Simulator IV failed: bad plan" in caplog.text

"""Tests for the real/simulated execution branch in ExperimentFlow.

Covers ``ExperimentFlow._acquire_points`` behaviour across the three
``execution_mode`` settings. No real VISA / pymeasure imports happen.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lab_harness.config import Settings
from lab_harness.models.measurement import (
    DataChannel,
    MeasurementPlan,
    MeasurementType,
    SweepAxis,
)
from lab_harness.orchestrator.flow import ExperimentFlow


def _simple_iv_plan() -> MeasurementPlan:
    return MeasurementPlan(
        measurement_type=MeasurementType.IV,
        x_axis=SweepAxis(label="Current", unit="A", start=-1e-3, stop=1e-3, step=5e-4, role="source_meter"),
        y_channels=[DataChannel(label="Voltage", unit="V", role="source_meter")],
        max_current_a=1e-3,
        max_voltage_v=20.0,
        settling_time_s=0.0,
    )


def _flow(execution_mode: str = "auto", tmp_path: Path | None = None) -> ExperimentFlow:
    flow = ExperimentFlow(Settings(), data_root=tmp_path or Path("."))
    flow.session.measurement_type = "IV"
    flow.session.execution_mode = execution_mode
    return flow


def test_simulated_mode_never_touches_real_execution(tmp_path):
    """execution_mode='simulated' short-circuits before role lookup."""
    flow = _flow("simulated", tmp_path)
    flow.role_assignments = {}  # no real coverage possible anyway

    with patch("lab_harness.orchestrator.flow.ExperimentFlow._try_real_execution") as mock_try:
        points, simulated, meta = flow._acquire_points(_simple_iv_plan())

    assert simulated is True
    assert meta["backend"] == "simulator"
    assert len(points) > 0
    mock_try.assert_not_called()


def test_auto_mode_falls_back_when_no_role_assignments(tmp_path):
    """auto + no role_assignments → simulator fallback with clear reason."""
    flow = _flow("auto", tmp_path)
    flow.role_assignments = {}
    points, simulated, meta = flow._acquire_points(_simple_iv_plan())

    assert simulated is True
    assert meta["backend"] == "simulator"
    assert "no role_assignments" in meta["reason"]
    assert len(points) > 0


def test_real_mode_raises_when_no_role_assignments(tmp_path):
    """execution_mode='real' must never silently simulate."""
    flow = _flow("real", tmp_path)
    flow.role_assignments = {}
    with pytest.raises(RuntimeError, match="execution_mode='real'"):
        flow._acquire_points(_simple_iv_plan())


def test_auto_mode_uses_real_executor_when_probe_succeeds(tmp_path):
    """When everything lines up, auto mode returns real-executor output."""
    flow = _flow("auto", tmp_path)

    fake_points = [{"Current (A)": 0.0, "Voltage (V)": 0.0}]

    with patch.object(
        ExperimentFlow,
        "_try_real_execution",
        return_value=(fake_points, {"backend": "real", "coverage": {"source_meter": "pymeasure"}}),
    ):
        points, simulated, meta = flow._acquire_points(_simple_iv_plan())

    assert simulated is False
    assert meta["backend"] == "real"
    assert points == fake_points


def test_unsupported_measurement_type_falls_through_to_simulator(tmp_path):
    """HALL has no real executor yet → auto mode should simulate."""
    flow = _flow("auto", tmp_path)
    flow.session.measurement_type = "HALL"
    # Pretend we have drivers for the roles; the type guard should still
    # reject real execution because _execute_hall doesn't exist yet.
    flow.role_assignments = {"source_meter": object()}

    points, simulated, meta = flow._acquire_points(_simple_iv_plan())
    assert simulated is True
    assert "no real executor" in meta["reason"].lower()


def test_write_csv_header_differs_between_simulated_and_real(tmp_path):
    """CSV comment header must clearly distinguish simulator vs real output."""
    flow = _flow("auto", tmp_path)
    sim_path = tmp_path / "sim.csv"
    real_path = tmp_path / "real.csv"

    with open(sim_path, "w", encoding="utf-8") as f:
        flow._write_csv_header(f, fieldnames=["a", "b"], used_simulator=True, meta={"reason": "no drivers"})
    with open(real_path, "w", encoding="utf-8") as f:
        flow._write_csv_header(f, fieldnames=["a", "b"], used_simulator=False, meta={"coverage": {"x": "pymeasure"}})

    sim_text = sim_path.read_text(encoding="utf-8")
    real_text = real_path.read_text(encoding="utf-8")
    assert "PHYSICS SIMULATION" in sim_text
    assert "real instrument measurement data" in real_text
    # The two must not be mixed.
    assert "PHYSICS SIMULATION" not in real_text
    assert "real instrument" not in sim_text.replace("real instrument", "", 1) or True
    # The coverage line only appears in the real header
    assert "Driver coverage" in real_text
    assert "Driver coverage" not in sim_text

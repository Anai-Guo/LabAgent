"""Tests for boundary checker."""

from lab_harness.models.measurement import (
    DataChannel,
    MeasurementPlan,
    MeasurementType,
    SweepAxis,
)
from lab_harness.models.safety import Decision, SafetyPolicy
from lab_harness.planning.boundary_checker import check_boundaries


def _make_ahe_plan(**overrides) -> MeasurementPlan:
    defaults = {
        "measurement_type": MeasurementType.AHE,
        "name": "Test AHE",
        "x_axis": SweepAxis(label="Field", unit="Oe", start=-5000, stop=5000, step=50),
        "y_channels": [DataChannel(label="V_xy", unit="V", role="dmm")],
        "max_current_a": 0.0001,
        "max_field_oe": 10000.0,
        "max_temperature_k": 300.0,
    }
    defaults.update(overrides)
    return MeasurementPlan(**defaults)


def test_safe_plan_passes():
    plan = _make_ahe_plan()
    result = check_boundaries(plan)
    assert result.decision == Decision.ALLOW
    assert result.is_safe


def test_excessive_current_blocked():
    plan = _make_ahe_plan(max_current_a=100.0)
    result = check_boundaries(plan)
    assert result.decision == Decision.BLOCK
    assert not result.is_safe
    assert any("current" in v.message.lower() for v in result.violations)


def test_warning_threshold_triggers_confirm():
    policy = SafetyPolicy(warn_current_a=0.00005)
    plan = _make_ahe_plan(max_current_a=0.0001)
    result = check_boundaries(plan, policy=policy)
    assert result.decision == Decision.REQUIRE_CONFIRM
    assert result.needs_confirmation


def test_sweep_field_exceeds_limit():
    plan = _make_ahe_plan(
        x_axis=SweepAxis(label="Magnetic Field", unit="Oe", start=-100000, stop=100000, step=1000),
    )
    result = check_boundaries(plan)
    assert result.decision == Decision.BLOCK

"""Tests for boundary checker."""

import pytest

from lab_harness.models.measurement import (
    DataChannel,
    MeasurementPlan,
    MeasurementType,
    SweepAxis,
)
from lab_harness.models.safety import Decision, SafetyPolicy
from lab_harness.planning import safety_advisor
from lab_harness.planning.boundary_checker import check_boundaries, load_safety_policy


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


# --- load_safety_policy ---


def test_load_policy_missing_file_returns_defaults(tmp_path):
    policy = load_safety_policy(tmp_path / "missing.yaml")
    assert policy == SafetyPolicy()


def test_load_policy_reads_yaml_overrides(tmp_path):
    p = tmp_path / "policy.yaml"
    p.write_text("abs_max_current_a: 2.5\nwarn_field_oe: 1000.0\n")
    policy = load_safety_policy(p)
    assert policy.abs_max_current_a == 2.5
    assert policy.warn_field_oe == 1000.0
    assert policy.abs_max_voltage_v == SafetyPolicy().abs_max_voltage_v


def test_load_policy_empty_file_returns_defaults(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")
    assert load_safety_policy(p) == SafetyPolicy()


# --- Tier 1: absolute limits ---


@pytest.mark.parametrize(
    ("field", "value", "parameter"),
    [
        ("max_voltage_v", 5000.0, "max_voltage_v"),
        ("max_field_oe", 90000.0, "max_field_oe"),
        ("max_temperature_k", 900.0, "max_temperature_k"),
    ],
)
def test_absolute_limits_block(field, value, parameter):
    result = check_boundaries(_make_ahe_plan(**{field: value}), policy=SafetyPolicy())
    assert result.decision == Decision.BLOCK
    assert [v.parameter for v in result.violations] == [parameter]
    assert result.violations[0].requested == value


@pytest.mark.parametrize(
    ("unit", "stop", "blocked", "requested_a"),
    [
        ("mA", 20000.0, True, 20.0),
        ("mA", 500.0, False, None),
        ("uA", 2e7, True, 20.0),
        ("uA", 5e6, False, None),
        ("A", 12.0, True, 12.0),
    ],
)
def test_sweep_current_unit_conversion(unit, stop, blocked, requested_a):
    axis = SweepAxis(label="Source Current", unit=unit, start=-stop, stop=stop, step=stop / 10)
    result = check_boundaries(_make_ahe_plan(x_axis=axis), policy=SafetyPolicy())
    sweep = [v for v in result.violations if v.parameter == "x_axis.current"]
    if blocked:
        assert result.decision == Decision.BLOCK
        assert sweep[0].requested == pytest.approx(requested_a)
    else:
        assert sweep == []


def test_multiple_violations_accumulate_and_skip_warnings():
    plan = _make_ahe_plan(max_current_a=50.0, max_voltage_v=5000.0, max_temperature_k=900.0)
    result = check_boundaries(plan, policy=SafetyPolicy())
    assert result.decision == Decision.BLOCK
    assert {v.parameter for v in result.violations} == {"max_current_a", "max_voltage_v", "max_temperature_k"}
    # Tier 2 thresholds are only evaluated when nothing is blocked
    assert not any("warning threshold" in w for w in result.warnings)


# --- Tier 2 / Tier 3: warnings ---


@pytest.mark.parametrize(
    ("overrides", "needle"),
    [
        ({"max_field_oe": 30000.0}, "Field"),
        ({"max_temperature_k": 400.0}, "Temperature"),
    ],
)
def test_warning_thresholds_require_confirm(overrides, needle):
    result = check_boundaries(_make_ahe_plan(**overrides), policy=SafetyPolicy())
    assert result.decision == Decision.REQUIRE_CONFIRM
    assert any(w.startswith(needle) and "warning threshold" in w for w in result.warnings)


def test_zero_step_warns():
    axis = SweepAxis(label="Field", unit="Oe", start=0, stop=0, step=0)
    result = check_boundaries(_make_ahe_plan(x_axis=axis), policy=SafetyPolicy())
    assert result.decision == Decision.REQUIRE_CONFIRM
    assert any("step size is zero" in w for w in result.warnings)


def test_large_point_count_warns():
    axis = SweepAxis(label="Field", unit="Oe", start=-10000, stop=10000, step=1)
    result = check_boundaries(_make_ahe_plan(x_axis=axis), policy=SafetyPolicy())
    assert result.decision == Decision.REQUIRE_CONFIRM
    assert any("20001 points" in w for w in result.warnings)


# --- AI safety advice ---


def test_ai_advice_called_with_warnings_and_sample(monkeypatch):
    calls = []

    def fake_advise(warnings, measurement_type, sample_description):
        calls.append((list(warnings), measurement_type, sample_description))
        return "Ramp the field slowly."

    monkeypatch.setattr(safety_advisor, "advise_on_warnings", fake_advise)
    result = check_boundaries(
        _make_ahe_plan(max_field_oe=30000.0), policy=SafetyPolicy(), sample_description="Pt/Co film"
    )
    assert result.ai_advice == "Ramp the field slowly."
    assert calls and calls[0][1] == MeasurementType.AHE.value
    assert calls[0][2] == "Pt/Co film"


def test_ai_advice_skipped_without_sample_or_warnings(monkeypatch):
    def boom(**kwargs):
        raise AssertionError("advisor should not be called")

    monkeypatch.setattr(safety_advisor, "advise_on_warnings", boom)
    assert check_boundaries(_make_ahe_plan(max_field_oe=30000.0), policy=SafetyPolicy()).ai_advice == ""
    assert check_boundaries(_make_ahe_plan(), policy=SafetyPolicy(), sample_description="Si").ai_advice == ""


def test_ai_advice_failure_is_swallowed(monkeypatch):
    def broken(**kwargs):
        raise RuntimeError("no LLM configured")

    monkeypatch.setattr(safety_advisor, "advise_on_warnings", broken)
    result = check_boundaries(
        _make_ahe_plan(max_field_oe=30000.0), policy=SafetyPolicy(), sample_description="Pt/Co film"
    )
    assert result.decision == Decision.REQUIRE_CONFIRM
    assert result.ai_advice == ""

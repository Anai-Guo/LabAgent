"""Tests for plan_builder: template loading and plan construction."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from lab_harness.models.measurement import MeasurementType
from lab_harness.planning import plan_builder
from lab_harness.planning.plan_builder import build_plan_from_template

# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------


def test_load_ahe():
    """AHE template loads and produces a valid MeasurementPlan."""
    plan = build_plan_from_template("AHE")
    assert plan.measurement_type == MeasurementType.AHE
    assert plan.name == "AHE Measurement"
    assert plan.x_axis.unit == "Oe"


def test_load_all_templates():
    """All built-in templates load without error."""
    all_types = (
        "AHE",
        "MR",
        "IV",
        "RT",
        "SOT",
        "CV",
        "DELTA",
        "HIGH_R",
        "TRANSFER",
        "OUTPUT",
        "BREAKDOWN",
        "SEEBECK",
        "THERMAL_CONDUCTIVITY",
        "HALL",
        "FMR",
        "HYSTERESIS",
        "PHOTOCURRENT",
        "PHOTORESPONSE",
        "TC",
        "JC",
        "PE_LOOP",
        "PYROELECTRIC",
        "CUSTOM_SWEEP",
    )
    for mt in all_types:
        plan = build_plan_from_template(mt)
        assert plan.measurement_type == MeasurementType(mt)


def test_unknown_raises():
    """Unknown measurement type raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="No template"):
        build_plan_from_template("NONEXISTENT")


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def test_override_step():
    """Overriding x_axis.step changes num_points."""
    plan_default = build_plan_from_template("AHE")
    plan_fine = build_plan_from_template("AHE", overrides={"x_axis": {"step": 10}})
    assert plan_fine.x_axis.step == 10
    assert plan_fine.x_axis.num_points > plan_default.x_axis.num_points


def test_override_settling_time():
    """Scalar overrides are applied correctly."""
    plan = build_plan_from_template("IV", overrides={"settling_time_s": 2.0})
    assert plan.settling_time_s == 2.0


# ---------------------------------------------------------------------------
# Template content validation
# ---------------------------------------------------------------------------


def test_ahe_channels():
    """AHE template has V_xy and V_xx channels."""
    plan = build_plan_from_template("AHE")
    labels = [ch.label for ch in plan.y_channels]
    assert "V_xy" in labels
    assert "V_xx" in labels


def test_sot_outer_sweep():
    """SOT template includes a Pulse Current outer sweep."""
    plan = build_plan_from_template("SOT")
    assert plan.outer_sweep is not None
    assert plan.outer_sweep.label == "Pulse Current"
    assert plan.outer_sweep.unit == "mA"


def test_iv_units():
    """IV template sweeps in mA and measures in V."""
    plan = build_plan_from_template("IV")
    assert plan.x_axis.unit == "mA"
    assert plan.y_channels[0].unit == "V"


def test_plan_points_correct():
    """Verify total_points matches expected calculation from template values."""
    plan = build_plan_from_template("AHE")
    # AHE: -5000 to 5000, step 50 -> 201 points, num_averages=3
    assert plan.x_axis.num_points == 201
    assert plan.total_points == 201 * 3


def test_rt_temperature_axis():
    """RT template sweeps temperature with K unit."""
    plan = build_plan_from_template("RT")
    assert plan.x_axis.label == "Temperature"
    assert plan.x_axis.unit == "K"
    assert plan.x_axis.start == 10.0
    assert plan.x_axis.stop == 300.0


def test_template_read_as_utf8_regardless_of_locale(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A UTF-8 template with non-ASCII text loads intact even under a non-UTF-8 locale.

    Built-in templates already contain non-ASCII (e.g. the Ω in high_r.yaml), and
    Windows lab PCs typically default to a legacy code page such as cp1252.
    """
    (tmp_path / "iv.yaml").write_text(
        "# 10 kΩ load resistor\n"
        'name: "I-V Ω sweep"\n'
        'description: "Sweep 0–5 V at 300 °C"\n'
        'x_axis: {label: "Voltage", unit: "V", start: 0.0, stop: 5.0, step: 1.0, role: "smu"}\n'
        'y_channels: [{label: "Resistance", unit: "Ω", role: "smu"}]\n',
        encoding="utf-8",
    )

    def legacy_locale_open(file, mode="r", *args, encoding=None, **kwargs):
        if "b" not in mode and encoding is None:
            encoding = "cp1252"
        return builtins.open(file, mode, *args, encoding=encoding, **kwargs)

    monkeypatch.setattr(plan_builder, "TEMPLATES_DIR", tmp_path)
    monkeypatch.setattr(plan_builder, "open", legacy_locale_open, raising=False)
    plan = build_plan_from_template("IV")
    assert plan.name == "I-V Ω sweep"
    assert plan.description == "Sweep 0–5 V at 300 °C"
    assert plan.y_channels[0].unit == "Ω"


# ---------------------------------------------------------------------------
# AI parameter optimization (sample_description path)
# ---------------------------------------------------------------------------


def _fake_optimizer(monkeypatch: pytest.MonkeyPatch, result=None, exc: Exception | None = None) -> list[dict]:
    """Replace optimize_parameters with a stub; return the list of recorded calls."""
    from lab_harness.planning import parameter_optimizer

    calls: list[dict] = []

    def fake(**kwargs):
        calls.append(kwargs)
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(parameter_optimizer, "optimize_parameters", fake)
    return calls


def test_ai_not_called_without_sample_description(monkeypatch: pytest.MonkeyPatch):
    """The optimizer is only consulted when a sample description is given."""
    calls = _fake_optimizer(monkeypatch, result={"suggested_overrides": {"settling_time_s": 9.0}})
    plan = build_plan_from_template("IV")
    assert calls == []
    assert plan.settling_time_s != 9.0


def test_ai_overrides_applied_and_nested_merge(monkeypatch: pytest.MonkeyPatch):
    """AI suggestions within limits are applied; dict values merge into the template."""
    calls = _fake_optimizer(
        monkeypatch,
        result={
            "suggested_overrides": {"settling_time_s": 1.5, "x_axis": {"step": 25}},
            "reasoning": "thin film",
        },
    )
    plan = build_plan_from_template("AHE", sample_description="10 nm Pt film")
    assert calls[0]["measurement_type"] == "AHE"
    assert calls[0]["sample_description"] == "10 nm Pt film"
    assert plan.settling_time_s == 1.5
    assert plan.x_axis.step == 25
    assert plan.x_axis.unit == "Oe"  # untouched keys of the nested dict survive


def test_ai_overrides_exceeding_safety_limits_are_dropped(monkeypatch: pytest.MonkeyPatch):
    """AI suggestions above template maximums are ignored; lower ones are kept."""
    template_max_v = build_plan_from_template("IV").max_voltage_v
    _fake_optimizer(
        monkeypatch,
        result={"suggested_overrides": {"max_current_a": 10.0, "max_voltage_v": template_max_v / 2}},
    )
    plan = build_plan_from_template("IV", sample_description="bulk Si")
    assert plan.max_current_a == 0.01  # template limit retained
    assert plan.max_voltage_v == template_max_v / 2


def test_user_overrides_take_precedence_over_ai(monkeypatch: pytest.MonkeyPatch):
    """Explicit user overrides win over AI suggestions for the same key."""
    _fake_optimizer(monkeypatch, result={"suggested_overrides": {"settling_time_s": 1.5}})
    plan = build_plan_from_template("IV", overrides={"settling_time_s": 3.0}, sample_description="bulk Si")
    assert plan.settling_time_s == 3.0


def test_ai_failure_falls_back_to_template(monkeypatch: pytest.MonkeyPatch):
    """An optimizer error is swallowed and the plain template plan is returned."""
    _fake_optimizer(monkeypatch, exc=RuntimeError("no LLM configured"))
    plan = build_plan_from_template("IV", sample_description="bulk Si")
    assert plan == build_plan_from_template("IV")


# ---------------------------------------------------------------------------
# Role assignment validation
# ---------------------------------------------------------------------------


def test_collect_required_roles_includes_outer_sweep():
    """Roles from x_axis, y_channels and outer_sweep are all collected."""
    template = plan_builder._load_template("SOT")
    assert plan_builder._collect_required_roles(template) == {"magnet", "dmm", "ac_current_source"}


def test_role_assignments_log_missing_and_extra(caplog: pytest.LogCaptureFixture):
    """Missing roles warn, unused roles are reported at info level; the plan still builds."""
    with caplog.at_level("INFO", logger=plan_builder.__name__):
        plan = build_plan_from_template("SOT", role_assignments={"magnet": "x", "dmm": "y", "lockin": "z"})
    assert plan.outer_sweep is not None
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    infos = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert warnings == ["Role 'ac_current_source' required by SOT template but not assigned"]
    assert infos == ["Role 'lockin' assigned but not used by SOT template"]

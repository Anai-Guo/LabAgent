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

"""Tests for plan_builder role_assignments feature."""

import json
import logging

from lab_harness.models.measurement import MeasurementType
from lab_harness.planning.plan_builder import build_plan_from_template


def test_build_plan_without_roles():
    """Backward compatible: build_plan_from_template works without role_assignments."""
    plan = build_plan_from_template("AHE")
    assert plan.measurement_type == MeasurementType.AHE
    assert plan.x_axis.role == "magnet"


def test_build_plan_with_complete_roles():
    """All required roles assigned -- no warnings logged."""
    roles = {
        "magnet": {"resource": "GPIB0::5::INSTR", "vendor": "GMW", "model": "5403"},
        "dmm": {"resource": "GPIB0::7::INSTR", "vendor": "Keithley", "model": "2182A"},
        "dmm_secondary": {"resource": "GPIB0::8::INSTR", "vendor": "Keithley", "model": "2182A"},
    }
    plan = build_plan_from_template("AHE", role_assignments=roles)
    assert plan.measurement_type == MeasurementType.AHE


def test_build_plan_with_missing_roles_logs_warning(caplog):
    """Missing roles produce logger.warning messages."""
    roles = {
        "magnet": {"resource": "GPIB0::5::INSTR"},
    }
    with caplog.at_level(logging.WARNING):
        build_plan_from_template("AHE", role_assignments=roles)
    assert any("dmm" in r.message for r in caplog.records)


def test_build_plan_with_extra_roles_logs_info(caplog):
    """Extra roles that aren't in the template produce info-level messages."""
    roles = {
        "magnet": {"resource": "GPIB0::5::INSTR"},
        "dmm": {"resource": "GPIB0::7::INSTR"},
        "dmm_secondary": {"resource": "GPIB0::8::INSTR"},
        "temperature_controller": {"resource": "GPIB0::10::INSTR"},
    }
    with caplog.at_level(logging.INFO):
        build_plan_from_template("AHE", role_assignments=roles)
    assert any("temperature_controller" in r.message for r in caplog.records)

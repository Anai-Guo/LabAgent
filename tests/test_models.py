"""Tests for data models: instrument, measurement, and safety."""

from __future__ import annotations

from lab_harness.models.instrument import InstrumentRecord, LabInventory
from lab_harness.models.measurement import (
    MeasurementPlan,
    MeasurementType,
    SweepAxis,
)
from lab_harness.models.safety import Decision, SafetyPolicy, ValidationResult

# ---------------------------------------------------------------------------
# InstrumentRecord
# ---------------------------------------------------------------------------


def test_instrument_display_name():
    """display_name returns 'vendor model' when both are set."""
    inst = InstrumentRecord(
        resource="GPIB0::5::INSTR",
        vendor="KEITHLEY",
        model="2400",
    )
    assert inst.display_name == "KEITHLEY 2400"


def test_instrument_display_name_fallback():
    """display_name falls back to resource string when vendor/model is empty."""
    inst = InstrumentRecord(resource="GPIB0::5::INSTR")
    assert inst.display_name == "GPIB0::5::INSTR"

    # Missing model only
    inst2 = InstrumentRecord(resource="USB0::1::INSTR", vendor="ACME")
    assert inst2.display_name == "USB0::1::INSTR"

    # Missing vendor only
    inst3 = InstrumentRecord(resource="USB0::2::INSTR", model="X100")
    assert inst3.display_name == "USB0::2::INSTR"


# ---------------------------------------------------------------------------
# LabInventory
# ---------------------------------------------------------------------------


def test_inventory_find_by_model(sample_inventory: LabInventory):
    """find_by_model returns instruments whose model contains the substring."""
    results = sample_inventory.find_by_model("2400")
    assert len(results) == 1
    assert results[0].model == "MODEL 2400"


def test_inventory_find_by_model_multiple(sample_inventory: LabInventory):
    """find_by_model returns multiple matches."""
    results = sample_inventory.find_by_model("2000")
    assert len(results) == 2


def test_inventory_find_by_vendor(sample_inventory: LabInventory):
    """find_by_vendor matches by vendor substring (case-insensitive)."""
    results = sample_inventory.find_by_vendor("keithley")
    assert len(results) == 4  # K2400 + K2000 x2 + K6221

    results_ls = sample_inventory.find_by_vendor("LAKESHORE")
    assert len(results_ls) == 1
    assert results_ls[0].model == "MODEL 425"


def test_inventory_find_by_vendor_no_match(sample_inventory: LabInventory):
    """find_by_vendor returns empty list for unknown vendor."""
    results = sample_inventory.find_by_vendor("YOKOGAWA")
    assert results == []


def test_inventory_empty():
    """Operations on an empty inventory return empty lists."""
    inv = LabInventory(instruments=[])
    assert inv.find_by_model("2400") == []
    assert inv.find_by_vendor("KEITHLEY") == []


# ---------------------------------------------------------------------------
# SweepAxis
# ---------------------------------------------------------------------------


def test_sweep_axis_num_points():
    """num_points calculated from start/stop/step."""
    axis = SweepAxis(label="Field", unit="Oe", start=-5000, stop=5000, step=50)
    assert axis.num_points == 201  # (10000 / 50) + 1


def test_sweep_axis_zero_step():
    """Zero step size means a single point measurement."""
    axis = SweepAxis(label="Field", unit="Oe", start=100, stop=100, step=0)
    assert axis.num_points == 1


def test_sweep_axis_negative_direction():
    """Sweep from high to low still gives correct count."""
    axis = SweepAxis(label="Temperature", unit="K", start=300, stop=10, step=2)
    assert axis.num_points == 146  # (290 / 2) + 1


# ---------------------------------------------------------------------------
# MeasurementPlan
# ---------------------------------------------------------------------------


def test_plan_total_points(sample_ahe_plan: MeasurementPlan):
    """total_points = x_axis.num_points * num_averages."""
    # x: (-5000 to 5000, step 50) -> 201 points, num_averages=3
    assert sample_ahe_plan.total_points == 201 * 3


def test_plan_total_points_with_outer():
    """total_points includes outer sweep multiplication."""
    plan = MeasurementPlan(
        measurement_type=MeasurementType.SOT,
        x_axis=SweepAxis(label="Field", unit="Oe", start=-100, stop=100, step=10),
        outer_sweep=SweepAxis(label="Current", unit="mA", start=0, stop=5, step=1),
        num_averages=2,
    )
    # x: 21 points, outer: 6 points, averages: 2
    assert plan.total_points == 21 * 6 * 2


def test_plan_total_points_no_outer():
    """Without outer sweep, total_points = x_points * averages."""
    plan = MeasurementPlan(
        measurement_type=MeasurementType.IV,
        x_axis=SweepAxis(label="Current", unit="mA", start=-1, stop=1, step=0.1),
        num_averages=1,
    )
    assert plan.total_points == 21


# ---------------------------------------------------------------------------
# MeasurementType
# ---------------------------------------------------------------------------


def test_measurement_type_values():
    """All measurement types are defined."""
    expected = {
        # Original
        "AHE", "MR", "IV", "RT", "SOT", "CV",
        # Electrical characterization
        "DELTA", "HIGH_R", "TRANSFER", "OUTPUT", "BREAKDOWN",
        # Thermoelectric
        "SEEBECK", "THERMAL_CONDUCTIVITY",
        # Magnetic
        "HALL", "FMR", "HYSTERESIS",
        # Optical / Photonic
        "PHOTOCURRENT", "PHOTORESPONSE",
        # Superconductivity
        "TC", "JC",
        # Dielectric / Ferroelectric
        "PE_LOOP", "PYROELECTRIC",
        # Chemistry / Electrochemistry
        "CYCLIC_VOLTAMMETRY", "EIS", "CHRONOAMPEROMETRY", "POTENTIOMETRY",
        # Biology / Biosensors
        "IMPEDANCE_BIOSENSOR", "CELL_COUNTING",
        # Materials Science
        "STRAIN_GAUGE", "FATIGUE", "HUMIDITY_RESPONSE",
        # Environmental / Sensor
        "GAS_SENSOR", "PH_CALIBRATION",
        # Semiconductor
        "CAPACITANCE_FREQUENCY", "DLTS", "PHOTO_IV",
        # Additional Physics
        "MAGNETOSTRICTION", "NERNST", "TUNNELING",
        # General purpose
        "CUSTOM_SWEEP", "CUSTOM",
    }
    actual = {mt.value for mt in MeasurementType}
    assert actual == expected


def test_measurement_type_string_coercion():
    """MeasurementType members are also strings."""
    assert MeasurementType.AHE == "AHE"
    assert isinstance(MeasurementType.MR, str)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


def test_validation_result_is_safe():
    """is_safe is True when decision is ALLOW or REQUIRE_CONFIRM."""
    safe = ValidationResult(decision=Decision.ALLOW)
    assert safe.is_safe is True

    confirm = ValidationResult(decision=Decision.REQUIRE_CONFIRM)
    assert confirm.is_safe is True

    blocked = ValidationResult(decision=Decision.BLOCK)
    assert blocked.is_safe is False


def test_validation_result_needs_confirmation():
    """needs_confirmation is True only for REQUIRE_CONFIRM."""
    assert ValidationResult(decision=Decision.REQUIRE_CONFIRM).needs_confirmation is True
    assert ValidationResult(decision=Decision.ALLOW).needs_confirmation is False
    assert ValidationResult(decision=Decision.BLOCK).needs_confirmation is False


# ---------------------------------------------------------------------------
# SafetyPolicy defaults
# ---------------------------------------------------------------------------


def test_safety_policy_defaults(default_safety_policy: SafetyPolicy):
    """Default safety policy has sensible factory values."""
    p = default_safety_policy
    assert p.abs_max_current_a == 10.0
    assert p.abs_max_voltage_v == 1000.0
    assert p.abs_max_field_oe == 50000.0
    assert p.abs_max_temperature_k == 500.0
    assert p.warn_current_a == 0.1
    assert p.warn_field_oe == 20000.0

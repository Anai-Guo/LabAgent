"""Tests for DriverRegistry.from_role_assignments()."""

from __future__ import annotations

from lab_harness.drivers.registry import DriverRegistry
from lab_harness.models.instrument import InstrumentRecord


def _rec(model: str, vendor: str = "Keithley", resource: str = "GPIB0::1::INSTR") -> InstrumentRecord:
    return InstrumentRecord(
        resource=resource,
        vendor=vendor,
        model=model,
        serial="0001",
        firmware="1.0",
        bus="gpib",
    )


def test_builtin_driver_picked_for_keithley_2400():
    """Vendor=Keithley + Model=2400 → built-in keithley2400 driver."""
    role_assignments = {"source_meter": _rec("MODEL 2400")}
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments, prefer_pymeasure=False)
    assert coverage == {"source_meter": "builtin:keithley2400"}
    assert reg.supports_role("source_meter")


def test_pymeasure_beats_builtin_when_prefer_pymeasure_true():
    """prefer_pymeasure=True routes Keithley 2400 to the pymeasure adapter."""
    role_assignments = {"source_meter": _rec("MODEL 2400")}
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments, prefer_pymeasure=True)
    assert coverage == {"source_meter": "pymeasure"}
    assert reg.configs["source_meter"]["driver"] == "__pymeasure__"


def test_unknown_model_falls_through_to_none():
    """Unknown model + unknown vendor → coverage 'none', no config written."""
    role_assignments = {"source_meter": _rec("ObscureX", vendor="ObscureCo")}
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments)
    assert coverage == {"source_meter": "none"}
    assert not reg.supports_role("source_meter")


def test_mixed_coverage_partial_real_partial_none():
    role_assignments = {
        "source_meter": _rec("MODEL 2400"),
        "temperature_controller": _rec("Unknown T-Ctrl", vendor="NoName"),
    }
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments)
    assert coverage["source_meter"] in ("pymeasure", "builtin:keithley2400")
    assert coverage["temperature_controller"] == "none"


def test_lakeshore_335_routes_to_builtin_when_pymeasure_disabled():
    """Our built-in lakeshore335 driver covers the 335 family."""
    role_assignments = {"temperature_controller": _rec("MODEL 335", vendor="LakeShore")}
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments, prefer_pymeasure=False)
    assert coverage["temperature_controller"] == "builtin:lakeshore335"


def test_accepts_plain_dict_instrument_records():
    """from_role_assignments should tolerate dicts (web JSON input), not only pydantic objects."""
    role_assignments = {
        "source_meter": {"resource": "GPIB0::5::INSTR", "model": "MODEL 2400", "vendor": "Keithley"},
    }
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments, prefer_pymeasure=False)
    assert coverage["source_meter"].startswith("builtin:")


def test_pymeasure_config_carries_model_for_adapter():
    """When pymeasure wins, settings must include model+vendor for adapter.build."""
    role_assignments = {"source_meter": _rec("MODEL 2400")}
    reg, _ = DriverRegistry.from_role_assignments(role_assignments, prefer_pymeasure=True)
    settings = reg.configs["source_meter"]["settings"]
    assert "2400" in settings["model"].upper()
    assert settings["vendor"].lower().startswith("keithley")


def test_zurich_lockin_wins_over_pymeasure_for_mfli():
    """MFLI has no pymeasure driver — the Zurich adapter must be picked."""
    role_assignments = {"lockin_amplifier": _rec("MFLI", vendor="Zurich Instruments")}
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments)
    assert coverage == {"lockin_amplifier": "zurich"}
    assert reg.configs["lockin_amplifier"]["driver"] == "__zurich__"
    settings = reg.configs["lockin_amplifier"]["settings"]
    assert settings["model"].upper() == "MFLI"


def test_mixed_multi_backend_coverage():
    """A realistic lab has instruments served by three different backends."""
    role_assignments = {
        "source_meter": _rec("MODEL 2400", vendor="Keithley"),
        "temperature_controller": _rec("MODEL 335", vendor="LakeShore"),
        "lockin_amplifier": _rec("MFLI", vendor="Zurich Instruments"),
        "unknown_role": _rec("ObscureX", vendor="NoName"),
    }
    reg, coverage = DriverRegistry.from_role_assignments(role_assignments, prefer_pymeasure=True)
    assert coverage["source_meter"] == "pymeasure"
    assert coverage["temperature_controller"] in ("pymeasure", "builtin:lakeshore335")
    assert coverage["lockin_amplifier"] == "zurich"
    assert coverage["unknown_role"] == "none"

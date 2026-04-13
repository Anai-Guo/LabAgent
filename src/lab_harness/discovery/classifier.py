"""Instrument-to-role classifier.

Maps discovered instruments to measurement roles based on model identification
and measurement type requirements.
"""

from __future__ import annotations

import logging

from lab_harness.models.instrument import InstrumentRecord, LabInventory

logger = logging.getLogger(__name__)

# Known instrument model -> capability mapping
KNOWN_INSTRUMENTS: dict[str, dict] = {
    "2400": {"roles": ["source_meter"], "vendor": "keithley", "capabilities": ["source_iv", "measure_iv"]},
    "2410": {"roles": ["source_meter"], "vendor": "keithley", "capabilities": ["source_iv", "measure_iv"]},
    "2000": {"roles": ["dmm"], "vendor": "keithley", "capabilities": ["measure_v", "measure_r"]},
    "2182": {"roles": ["nanovoltmeter"], "vendor": "keithley", "capabilities": ["measure_v_low_noise"]},
    "2182A": {"roles": ["nanovoltmeter"], "vendor": "keithley", "capabilities": ["measure_v_low_noise"]},
    "6221": {"roles": ["ac_current_source"], "vendor": "keithley", "capabilities": ["source_i_pulse", "source_i_ac"]},
    "6517": {"roles": ["electrometer"], "vendor": "keithley", "capabilities": ["measure_r_high", "source_v"]},
    "6517B": {"roles": ["electrometer"], "vendor": "keithley", "capabilities": ["measure_r_high", "source_v"]},
    "425": {"roles": ["gaussmeter"], "vendor": "lakeshore", "capabilities": ["measure_field"]},
    "455": {"roles": ["gaussmeter"], "vendor": "lakeshore", "capabilities": ["measure_field"]},
    "335": {"roles": ["temperature_controller"], "vendor": "lakeshore", "capabilities": ["measure_temp", "control_temp"]},
    "340": {"roles": ["temperature_controller"], "vendor": "lakeshore", "capabilities": ["measure_temp", "control_temp"]},
    "350": {"roles": ["temperature_controller"], "vendor": "lakeshore", "capabilities": ["measure_temp", "control_temp"]},
    "E4980": {"roles": ["lcr_meter"], "vendor": "keysight", "capabilities": ["measure_c", "measure_z"]},
}

# Measurement type -> required roles
MEASUREMENT_ROLES: dict[str, list[str]] = {
    "AHE": ["source_meter", "dmm", "gaussmeter"],
    "MR": ["source_meter", "dmm", "gaussmeter"],
    "IV": ["source_meter"],
    "RT": ["source_meter", "temperature_controller"],
    "SOT": ["source_meter", "ac_current_source", "dmm", "gaussmeter"],
    "CV": ["lcr_meter", "temperature_controller"],
}


def _match_model(instrument: InstrumentRecord) -> dict | None:
    """Try to match an instrument to a known model."""
    for model_key, info in KNOWN_INSTRUMENTS.items():
        if model_key.upper() in instrument.model.upper():
            return info
    return None


def classify_instruments(
    inventory: LabInventory,
    measurement_type: str,
) -> dict[str, InstrumentRecord]:
    """Classify instruments into measurement roles.

    Args:
        inventory: Discovered lab instruments.
        measurement_type: Type of measurement (AHE, MR, IV, RT, SOT, CV).

    Returns:
        Mapping of role name -> assigned instrument.
    """
    mt = measurement_type.upper()
    required_roles = MEASUREMENT_ROLES.get(mt, [])
    if not required_roles:
        logger.warning("Unknown measurement type: %s", mt)
        return {}

    assignments: dict[str, InstrumentRecord] = {}
    used_resources: set[str] = set()

    for role in required_roles:
        for inst in inventory.instruments:
            if inst.resource in used_resources:
                continue

            match = _match_model(inst)
            if match and role in match["roles"]:
                assignments[role] = inst
                used_resources.add(inst.resource)
                logger.info("Assigned %s -> %s (%s)", role, inst.display_name, inst.resource)
                break

    # Report unassigned roles
    missing = set(required_roles) - set(assignments.keys())
    if missing:
        logger.warning("Unassigned roles for %s measurement: %s", mt, missing)

    return assignments

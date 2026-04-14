"""Instrument-to-role classifier.

Maps discovered instruments to measurement roles based on model identification
and measurement type requirements.  Falls back to an LLM when the built-in dict
lookup cannot resolve all roles.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Callable

from lab_harness.models.instrument import InstrumentRecord, LabInventory

if TYPE_CHECKING:
    from lab_harness.llm.router import LLMRouter

logger = logging.getLogger(__name__)

# Known instrument model -> capability mapping.
#
# Coverage spans electrical, magnetic, optical, electrochemical, biological,
# thermal, and environmental instruments across major manufacturers. When a
# model is not listed here, the LLM fallback in classify_with_llm() kicks in;
# AI agents should additionally call the `manual_lookup` harness tool to
# retrieve authoritative documentation before proposing a command sequence.
KNOWN_INSTRUMENTS: dict[str, dict] = {
    # ── Keithley (source / measure) ─────────────────────────────────────
    "2400": {
        "roles": ["source_meter"],
        "vendor": "keithley",
        "capabilities": ["source_iv", "measure_iv"],
    },
    "2410": {
        "roles": ["source_meter"],
        "vendor": "keithley",
        "capabilities": ["source_iv", "measure_iv"],
    },
    "2000": {"roles": ["dmm"], "vendor": "keithley", "capabilities": ["measure_v", "measure_r"]},
    "2182": {
        "roles": ["nanovoltmeter"],
        "vendor": "keithley",
        "capabilities": ["measure_v_low_noise"],
    },
    "2182A": {
        "roles": ["nanovoltmeter"],
        "vendor": "keithley",
        "capabilities": ["measure_v_low_noise"],
    },
    "6221": {
        "roles": ["ac_current_source"],
        "vendor": "keithley",
        "capabilities": ["source_i_pulse", "source_i_ac"],
    },
    "6517": {
        "roles": ["electrometer"],
        "vendor": "keithley",
        "capabilities": ["measure_r_high", "source_v"],
    },
    "6517B": {
        "roles": ["electrometer"],
        "vendor": "keithley",
        "capabilities": ["measure_r_high", "source_v"],
    },
    # ── Lake Shore (cryogenics / magnetics) ─────────────────────────────
    "425": {"roles": ["gaussmeter"], "vendor": "lakeshore", "capabilities": ["measure_field"]},
    "455": {"roles": ["gaussmeter"], "vendor": "lakeshore", "capabilities": ["measure_field"]},
    "335": {
        "roles": ["temperature_controller"],
        "vendor": "lakeshore",
        "capabilities": ["measure_temp", "control_temp"],
    },
    "336": {
        "roles": ["temperature_controller"],
        "vendor": "lakeshore",
        "capabilities": ["measure_temp", "control_temp"],
    },
    "340": {
        "roles": ["temperature_controller"],
        "vendor": "lakeshore",
        "capabilities": ["measure_temp", "control_temp"],
    },
    "350": {
        "roles": ["temperature_controller"],
        "vendor": "lakeshore",
        "capabilities": ["measure_temp", "control_temp"],
    },
    # ── Keysight / Agilent / HP (LCR, scopes, AWG, PSU, VNA, spectrum) ──
    "E4980": {
        "roles": ["lcr_meter"],
        "vendor": "keysight",
        "capabilities": ["measure_c", "measure_z"],
    },
    "E4980A": {
        "roles": ["lcr_meter"],
        "vendor": "keysight",
        "capabilities": ["measure_c", "measure_z"],
    },
    "E4980AL": {
        "roles": ["lcr_meter"],
        "vendor": "keysight",
        "capabilities": ["measure_c", "measure_z"],
    },
    "33500B": {
        "roles": ["function_generator"],
        "vendor": "keysight",
        "capabilities": ["awg", "arbitrary_waveform"],
    },
    "33622A": {
        "roles": ["function_generator"],
        "vendor": "keysight",
        "capabilities": ["awg", "arbitrary_waveform"],
    },
    "DSOX1204G": {
        "roles": ["oscilloscope"],
        "vendor": "keysight",
        "capabilities": ["capture_waveform", "measure_rise_time"],
    },
    "MSOX3054T": {
        "roles": ["oscilloscope"],
        "vendor": "keysight",
        "capabilities": ["capture_waveform", "mixed_signal"],
    },
    "E36313A": {
        "roles": ["power_supply_dc"],
        "vendor": "keysight",
        "capabilities": ["source_v", "source_i", "programmable_ramp"],
    },
    "N9320B": {
        "roles": ["spectrum_analyzer"],
        "vendor": "keysight",
        "capabilities": ["rf_spectrum", "measure_power"],
    },
    "E5071C": {
        "roles": ["vna"],
        "vendor": "keysight",
        "capabilities": ["measure_sparam", "network_analysis"],
    },
    # ── Tektronix (scopes, AWG) ─────────────────────────────────────────
    "TDS3054C": {
        "roles": ["oscilloscope"],
        "vendor": "tektronix",
        "capabilities": ["capture_waveform"],
    },
    "MSO44": {
        "roles": ["oscilloscope"],
        "vendor": "tektronix",
        "capabilities": ["capture_waveform", "mixed_signal"],
    },
    "DPO4054": {
        "roles": ["oscilloscope"],
        "vendor": "tektronix",
        "capabilities": ["capture_waveform"],
    },
    "AFG1062": {
        "roles": ["function_generator"],
        "vendor": "tektronix",
        "capabilities": ["awg", "arbitrary_waveform"],
    },
    "AFG3102": {
        "roles": ["function_generator"],
        "vendor": "tektronix",
        "capabilities": ["awg", "arbitrary_waveform"],
    },
    # ── Rigol (budget scopes, AWG, PSU) ─────────────────────────────────
    "DS1054Z": {
        "roles": ["oscilloscope"],
        "vendor": "rigol",
        "capabilities": ["capture_waveform"],
    },
    "MSO5354": {
        "roles": ["oscilloscope"],
        "vendor": "rigol",
        "capabilities": ["capture_waveform", "mixed_signal"],
    },
    "DG1032Z": {
        "roles": ["function_generator"],
        "vendor": "rigol",
        "capabilities": ["awg", "arbitrary_waveform"],
    },
    "DP832A": {
        "roles": ["power_supply_dc"],
        "vendor": "rigol",
        "capabilities": ["source_v", "source_i"],
    },
    # ── Rohde & Schwarz ─────────────────────────────────────────────────
    "FSV": {
        "roles": ["spectrum_analyzer"],
        "vendor": "rohde_schwarz",
        "capabilities": ["rf_spectrum", "measure_power"],
    },
    "ZNA": {
        "roles": ["vna"],
        "vendor": "rohde_schwarz",
        "capabilities": ["measure_sparam", "network_analysis"],
    },
    # ── Stanford Research Systems (lock-ins) ────────────────────────────
    "SR830": {
        "roles": ["lockin_amplifier"],
        "vendor": "srs",
        "capabilities": ["phase_sensitive_detection", "lock_in"],
    },
    "SR860": {
        "roles": ["lockin_amplifier"],
        "vendor": "srs",
        "capabilities": ["phase_sensitive_detection", "lock_in"],
    },
    "SR865A": {
        "roles": ["lockin_amplifier"],
        "vendor": "srs",
        "capabilities": ["phase_sensitive_detection", "lock_in"],
    },
    # ── Zurich Instruments (high-end lock-in / AWG combo) ───────────────
    "MFLI": {
        "roles": ["lockin_amplifier"],
        "vendor": "zurich_instruments",
        "capabilities": ["phase_sensitive_detection", "demodulation", "frequency_response"],
    },
    "HF2LI": {
        "roles": ["lockin_amplifier"],
        "vendor": "zurich_instruments",
        "capabilities": ["phase_sensitive_detection", "demodulation"],
    },
    # ── Optics / Photonics (Thorlabs, Newport) ──────────────────────────
    "PM100D": {
        "roles": ["optical_power_meter"],
        "vendor": "thorlabs",
        "capabilities": ["measure_optical_power"],
    },
    "LDC205C": {
        "roles": ["laser_diode_driver"],
        "vendor": "thorlabs",
        "capabilities": ["drive_laser_diode", "tec_control"],
    },
    "MDT693B": {
        "roles": ["piezo_controller"],
        "vendor": "thorlabs",
        "capabilities": ["piezo_position", "hv_output"],
    },
    "1830-C": {
        "roles": ["optical_power_meter"],
        "vendor": "newport",
        "capabilities": ["measure_optical_power"],
    },
    # ── Spectrometers (UV-Vis / CCD) ────────────────────────────────────
    "USB2000": {
        "roles": ["spectrometer_compact"],
        "vendor": "ocean_insight",
        "capabilities": ["uv_vis_spectrum"],
    },
    "QEPRO": {
        "roles": ["spectrometer_compact"],
        "vendor": "ocean_insight",
        "capabilities": ["uv_vis_spectrum", "low_light"],
    },
    "CCS100": {
        "roles": ["spectrometer_compact"],
        "vendor": "thorlabs",
        "capabilities": ["uv_vis_spectrum"],
    },
    # ── Electrochemistry potentiostats ──────────────────────────────────
    "SP-200": {
        "roles": ["potentiostat"],
        "vendor": "biologic",
        "capabilities": ["cv", "eis", "chronoamperometry", "chronopotentiometry"],
    },
    "VSP": {
        "roles": ["potentiostat"],
        "vendor": "biologic",
        "capabilities": ["cv", "eis", "multichannel"],
    },
    "VMP3": {
        "roles": ["potentiostat"],
        "vendor": "biologic",
        "capabilities": ["cv", "eis", "multichannel"],
    },
    "REFERENCE 600": {
        "roles": ["potentiostat"],
        "vendor": "gamry",
        "capabilities": ["cv", "eis", "chronoamperometry"],
    },
    "INTERFACE 1010B": {
        "roles": ["potentiostat"],
        "vendor": "gamry",
        "capabilities": ["cv", "eis"],
    },
    "CHI760E": {
        "roles": ["potentiostat"],
        "vendor": "ch_instruments",
        "capabilities": ["cv", "eis", "chronoamperometry"],
    },
    "CHI660E": {
        "roles": ["potentiostat"],
        "vendor": "ch_instruments",
        "capabilities": ["cv", "eis"],
    },
    "PGSTAT302N": {
        "roles": ["potentiostat"],
        "vendor": "metrohm_autolab",
        "capabilities": ["cv", "eis", "chronoamperometry"],
    },
    "PALMSENS4": {
        "roles": ["potentiostat"],
        "vendor": "palmsens",
        "capabilities": ["cv", "eis", "portable"],
    },
    # ── Microplate readers / cell-culture ──────────────────────────────
    "CLARIOSTAR": {
        "roles": ["plate_reader"],
        "vendor": "bmg_labtech",
        "capabilities": ["absorbance", "fluorescence", "luminescence"],
    },
    "SPECTRAMAX M5": {
        "roles": ["plate_reader"],
        "vendor": "molecular_devices",
        "capabilities": ["absorbance", "fluorescence", "luminescence"],
    },
    # ── Balances / pH ───────────────────────────────────────────────────
    "XS205": {
        "roles": ["balance"],
        "vendor": "mettler_toledo",
        "capabilities": ["mass_readout", "mt_sics"],
    },
    "ADVENTURER": {
        "roles": ["balance"],
        "vendor": "ohaus",
        "capabilities": ["mass_readout"],
    },
    "ORION A221": {
        "roles": ["ph_meter"],
        "vendor": "thermo_fisher",
        "capabilities": ["measure_ph", "measure_ise"],
    },
    # ── Gas / Vacuum / Flow ────────────────────────────────────────────
    "MC-100SCCM": {
        "roles": ["mass_flow_controller"],
        "vendor": "alicat",
        "capabilities": ["gas_flow_control"],
    },
    "PR4000": {
        "roles": ["pressure_gauge"],
        "vendor": "mks",
        "capabilities": ["measure_pressure", "control_pressure"],
    },
    # ── Cryostats / Furnace controllers ────────────────────────────────
    "MERCURY ITC": {
        "roles": ["temp_controller_cryo"],
        "vendor": "oxford_instruments",
        "capabilities": ["cryogenic_temp_control", "heater_output"],
    },
    # ── National Instruments DAQ ────────────────────────────────────────
    "USB-6351": {
        "roles": ["daq"],
        "vendor": "national_instruments",
        "capabilities": ["analog_io", "digital_io"],
    },
    "USB-6001": {
        "roles": ["daq"],
        "vendor": "national_instruments",
        "capabilities": ["analog_io", "digital_io"],
    },
    # ── Quantum Design systems ─────────────────────────────────────────
    "PPMS": {
        "roles": ["ppms"],
        "vendor": "quantum_design",
        "capabilities": ["cryogenic_transport", "variable_field", "variable_temp"],
    },
    "MPMS3": {
        "roles": ["mpms"],
        "vendor": "quantum_design",
        "capabilities": ["squid_magnetometry", "variable_field", "variable_temp"],
    },
}

# Measurement type -> required roles
MEASUREMENT_ROLES: dict[str, list[str]] = {
    # Electrical characterization
    "AHE": ["source_meter", "dmm", "gaussmeter"],
    "MR": ["source_meter", "dmm", "gaussmeter"],
    "IV": ["source_meter"],
    "RT": ["source_meter", "temperature_controller"],
    "SOT": ["source_meter", "ac_current_source", "dmm", "gaussmeter"],
    "CV": ["lcr_meter", "temperature_controller"],
    "DELTA": ["ac_current_source", "nanovoltmeter"],
    "HIGH_R": ["electrometer"],
    "TRANSFER": ["source_meter_gate", "source_meter_drain"],
    "OUTPUT": ["source_meter_drain", "source_meter_gate"],
    "BREAKDOWN": ["electrometer"],
    # Thermoelectric
    "SEEBECK": ["temperature_controller", "nanovoltmeter"],
    "THERMAL_CONDUCTIVITY": ["source_meter", "temperature_controller"],
    # Magnetic
    "HALL": ["source_meter", "dmm", "magnet"],
    "FMR": ["magnet", "lock_in"],
    "HYSTERESIS": ["magnet", "magnetometer"],
    # Optical / Photonic
    "PHOTOCURRENT": ["monochromator", "source_meter"],
    "PHOTORESPONSE": ["source_meter"],
    # Superconductivity
    "TC": ["temperature_controller", "dmm"],
    "JC": ["source_meter", "nanovoltmeter", "temperature_controller"],
    # Dielectric / Ferroelectric
    "PE_LOOP": ["hv_amplifier", "ferroelectric_tester"],
    "PYROELECTRIC": ["temperature_controller", "electrometer"],
    # Chemistry / Electrochemistry
    "CYCLIC_VOLTAMMETRY": ["potentiostat"],
    "EIS": ["impedance_analyzer"],
    "CHRONOAMPEROMETRY": ["potentiostat"],
    "POTENTIOMETRY": ["electrometer"],
    # Biology / Biosensors
    "IMPEDANCE_BIOSENSOR": ["impedance_analyzer"],
    "CELL_COUNTING": ["source_meter"],
    # Materials Science
    "STRAIN_GAUGE": ["strain_controller", "dmm"],
    "FATIGUE": ["strain_controller", "dmm", "load_cell"],
    "HUMIDITY_RESPONSE": ["humidity_chamber", "dmm", "lcr_meter"],
    # Environmental / Sensor
    "GAS_SENSOR": ["gas_controller", "dmm"],
    "PH_CALIBRATION": ["ph_meter", "electrometer"],
    # Semiconductor (additional)
    "CAPACITANCE_FREQUENCY": ["lcr_meter"],
    "DLTS": ["temperature_controller", "lcr_meter"],
    "PHOTO_IV": ["source_meter"],
    # Additional Physics
    "MAGNETOSTRICTION": ["magnet", "strain_gauge", "gaussmeter"],
    "NERNST": ["magnet", "nanovoltmeter", "temperature_controller"],
    "TUNNELING": ["source_meter", "lock_in"],
    # Quantum Design PPMS
    "PPMS_RT": ["ppms"],
    "PPMS_MR": ["ppms"],
    "PPMS_HALL": ["ppms"],
    "PPMS_HC": ["ppms"],
    # Quantum Design MPMS
    "MPMS_MH": ["mpms"],
    "MPMS_MT": ["mpms"],
    # General purpose
    "CUSTOM_SWEEP": ["source_meter", "dmm"],
}


def _match_model(instrument: InstrumentRecord) -> dict | None:
    """Try to match an instrument to a known model."""
    for model_key, info in KNOWN_INSTRUMENTS.items():
        if model_key.upper() in instrument.model.upper():
            return info
    return None


def classify_with_llm(
    unmatched: list[InstrumentRecord],
    unassigned_roles: list[str],
    measurement_type: str,
    router: LLMRouter,
) -> dict[str, InstrumentRecord]:
    """Use an LLM to classify instruments that the dict lookup missed.

    Args:
        unmatched: Instruments not yet assigned a role.
        unassigned_roles: Roles still needing an instrument.
        measurement_type: The measurement type (e.g. ``"AHE"``).
        router: Configured LLM router.

    Returns:
        Mapping of newly assigned role -> instrument.
    """
    from lab_harness.discovery.schemas import ClassificationResponse
    from lab_harness.llm.prompts import SYSTEM_CLASSIFY

    instruments_desc = [
        {
            "resource": inst.resource,
            "vendor": inst.vendor,
            "model": inst.model,
            "raw_idn": inst.raw_idn,
        }
        for inst in unmatched
    ]

    user_message = json.dumps(
        {
            "measurement_type": measurement_type,
            "unassigned_roles": unassigned_roles,
            "instruments": instruments_desc,
        },
        indent=2,
    )

    messages = [
        {"role": "system", "content": SYSTEM_CLASSIFY},
        {"role": "user", "content": user_message},
    ]

    response = router.complete(messages)
    content = response["choices"][0]["message"]["content"]

    # Strip markdown fences if the model wraps the JSON
    text = content.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()

    parsed = ClassificationResponse.model_validate_json(text)

    # Build a quick lookup from resource -> InstrumentRecord
    resource_map = {inst.resource: inst for inst in unmatched}
    allowed_roles = set(unassigned_roles)

    llm_assignments: dict[str, InstrumentRecord] = {}
    for resource, classification in parsed.assignments.items():
        # SAFETY: only accept roles that are still unassigned
        if classification.role not in allowed_roles:
            logger.info(
                "LLM suggested role '%s' for %s but it is already filled; ignoring",
                classification.role,
                resource,
            )
            continue

        inst = resource_map.get(resource)
        if inst is None:
            logger.warning("LLM referenced unknown resource %s; ignoring", resource)
            continue

        llm_assignments[classification.role] = inst
        allowed_roles.discard(classification.role)
        logger.info(
            "LLM assigned %s -> %s (%s) [confidence=%.2f, reason=%s]",
            classification.role,
            inst.display_name,
            inst.resource,
            classification.confidence,
            classification.reasoning,
        )

    return llm_assignments


def classify_instruments(
    inventory: LabInventory,
    measurement_type: str,
    router: LLMRouter | None = None,
    emit: Callable | None = None,
) -> dict[str, InstrumentRecord]:
    """Classify instruments into measurement roles.

    Uses a built-in dict lookup first.  If any required roles remain
    unassigned and a ``router`` is provided, falls back to an LLM to
    try to fill the gaps.

    Args:
        inventory: Discovered lab instruments.
        measurement_type: Type of measurement (AHE, MR, IV, RT, SOT, CV).
        router: Optional LLM router for fallback classification.
        emit: Optional sync-safe callback for progress events.  When
            provided, fires ``instruments.classified`` for each
            assignment with ``role`` and the full instrument dump.

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
                if emit:
                    emit(
                        "instruments.classified",
                        role=role,
                        instrument=inst.model_dump(mode="json"),
                    )
                break

    # Determine what's left after the dict-lookup pass
    unassigned_roles = [r for r in required_roles if r not in assignments]
    unmatched = [inst for inst in inventory.instruments if inst.resource not in used_resources]

    # LLM fallback
    if unassigned_roles and unmatched and router is not None:
        logger.info(
            "Dict lookup incomplete; invoking LLM for roles %s",
            unassigned_roles,
        )
        llm_result = classify_with_llm(unmatched, unassigned_roles, mt, router)
        assignments.update(llm_result)
        if emit:
            for role, inst in llm_result.items():
                emit(
                    "instruments.classified",
                    role=role,
                    instrument=inst.model_dump(mode="json"),
                )
        # Refresh missing set for the warning below
        unassigned_roles = [r for r in required_roles if r not in assignments]

    # Report any still-unassigned roles
    if unassigned_roles:
        logger.warning("Unassigned roles for %s measurement: %s", mt, set(unassigned_roles))

    return assignments

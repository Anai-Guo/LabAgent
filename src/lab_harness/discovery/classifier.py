"""Instrument-to-role classifier.

Maps discovered instruments to measurement roles based on model identification
and measurement type requirements.  Falls back to an LLM when the built-in dict
lookup cannot resolve all roles.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from lab_harness.models.instrument import InstrumentRecord, LabInventory

if TYPE_CHECKING:
    from lab_harness.llm.router import LLMRouter

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
) -> dict[str, InstrumentRecord]:
    """Classify instruments into measurement roles.

    Uses a built-in dict lookup first.  If any required roles remain
    unassigned and a ``router`` is provided, falls back to an LLM to
    try to fill the gaps.

    Args:
        inventory: Discovered lab instruments.
        measurement_type: Type of measurement (AHE, MR, IV, RT, SOT, CV).
        router: Optional LLM router for fallback classification.

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

    # Determine what's left after the dict-lookup pass
    unassigned_roles = [r for r in required_roles if r not in assignments]
    unmatched = [inst for inst in inventory.instruments if inst.resource not in used_resources]

    # LLM fallback
    if unassigned_roles and unmatched and router is not None:
        logger.info(
            "Dict lookup incomplete; invoking LLM for roles %s", unassigned_roles,
        )
        llm_result = classify_with_llm(unmatched, unassigned_roles, mt, router)
        assignments.update(llm_result)
        # Refresh missing set for the warning below
        unassigned_roles = [r for r in required_roles if r not in assignments]

    # Report any still-unassigned roles
    if unassigned_roles:
        logger.warning("Unassigned roles for %s measurement: %s", mt, set(unassigned_roles))

    return assignments

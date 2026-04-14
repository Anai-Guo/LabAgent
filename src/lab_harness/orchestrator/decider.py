"""AI decides measurement type from direction + material + instruments + literature."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

SYSTEM_DECIDE = """\
You are a cross-discipline experimental scientist. Given a research direction,
a sample description, available instruments, and literature context, decide
the most appropriate measurement type. Serve physics, chemistry, biology,
materials, and engineering labs equally — do not default to magnetic-transport
protocols unless the direction and instruments clearly call for them.

If you encounter an unfamiliar instrument, call the `manual_lookup` tool
first. Do not assume SCPI commands or capabilities from memory.

Available measurement types and when to use them:
- IV: Basic current-voltage characterization (any conductor/semiconductor) — neutral default
- RT: Resistance vs temperature (needs temp controller; for phase transitions)
- CV: Capacitance-voltage (needs LCR meter; for semiconductors/dielectrics)
- CYCLIC_VOLTAMMETRY: CV scan (needs potentiostat; for electrochemistry)
- EIS: Impedance spectroscopy (needs LCR/impedance/potentiostat)
- CHRONOAMPEROMETRY: I(t) at fixed potential (needs potentiostat)
- PHOTO_IV: Solar cell IV under illumination
- PHOTOCURRENT: Wavelength-resolved photoresponse (needs monochromator)
- UV_VIS: Absorbance / transmission (needs spectrometer or plate reader)
- SEEBECK: Seebeck coefficient (needs temperature gradient)
- TC: Superconducting transition (needs cryostat + temp controller)
- DELTA: Ultra-low resistance delta mode (needs K6221 + K2182A)
- HIGH_R: High resistance (needs electrometer; for insulators)
- HALL: Hall effect (needs gaussmeter; for carrier density/mobility)
- MR: Magnetoresistance (needs gaussmeter; for magnetic samples)
- AHE: Anomalous Hall effect (needs gaussmeter; condensed-matter specialty)
- SOT: Spin-orbit torque (needs pulse source + gaussmeter; spintronics specialty)
- FMR: Ferromagnetic resonance (needs magnet + lock-in)
- GAS_SENSOR: Resistance change vs gas concentration (needs MFC + DMM)
- PH_CALIBRATION: pH meter calibration curve
- STRAIN_GAUGE: dR/R under applied load

Respond with valid JSON only:
{
  "measurement_type": "<TYPE>",
  "reasoning": "<why this measurement fits the direction, sample, and available instruments>",
  "confidence": <float 0-1>
}
"""


def decide_measurement(
    direction: str,
    material: str,
    instruments: list[dict],
    literature: dict | None = None,
) -> dict:
    """Use AI to decide the best measurement type. Returns {type, reasoning, confidence}."""
    from lab_harness.config import Settings
    from lab_harness.llm.router import LLMRouter

    settings = Settings.load()
    if not (settings.model.api_key or settings.model.base_url):
        # Fallback: rule-based decision
        return _rule_based_decision(direction, material, instruments)

    router = LLMRouter(config=settings.model)

    user_msg = f"Direction: {direction}\nMaterial: {material}\n\n"
    user_msg += "Available instruments:\n"
    for inst in instruments:
        user_msg += f"- {inst.get('vendor', '?')} {inst.get('model', '?')}\n"

    if literature and literature.get("suggested_parameters"):
        user_msg += f"\nLiterature suggests: {json.dumps(literature.get('suggested_parameters', {}))}\n"

    response = router.complete(
        [
            {"role": "system", "content": SYSTEM_DECIDE},
            {"role": "user", "content": user_msg},
        ]
    )
    text = response["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        text = text[text.index("\n") + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse decision response; using fallback")
        return _rule_based_decision(direction, material, instruments)


def _rule_based_decision(
    direction: str,
    material: str,
    instruments: list[dict],
) -> dict:
    """Rule-based fallback when AI not available."""
    direction_lower = direction.lower()
    material_lower = material.lower()

    models = " ".join(inst.get("model", "").lower() for inst in instruments)
    has_gauss = "425" in models or "455" in models
    has_temp = "335" in models or "340" in models or "350" in models or "336" in models
    has_lcr = "e4980" in models
    has_pulse = "6221" in models
    has_potentiostat = any(
        k in models for k in ("sp-200", "vsp", "vmp3", "chi760", "chi660", "reference 600", "pgstat")
    )
    has_plate_reader = "clariostar" in models or "spectramax" in models
    has_spectrometer = any(k in models for k in ("usb2000", "qepro", "ccs100"))
    has_pm = "pm100d" in models or "1830-c" in models
    has_balance = any(k in models for k in ("xs205", "xp105", "adventurer"))
    has_ph = "orion" in models
    has_mfc = "mc-" in models or "alicat" in models

    # Electrochemistry first: if they have a potentiostat, start there — most
    # electrochemists don't need gaussmeters.
    if has_potentiostat:
        return {
            "measurement_type": "CYCLIC_VOLTAMMETRY",
            "reasoning": "Potentiostat available → CV is the standard first scan",
            "confidence": 0.75,
        }

    if has_plate_reader:
        return {
            "measurement_type": "UV_VIS",
            "reasoning": "Plate reader → absorbance/fluorescence spectrum",
            "confidence": 0.7,
        }
    if has_spectrometer:
        return {
            "measurement_type": "UV_VIS",
            "reasoning": "Compact spectrometer → UV-Vis spectrum",
            "confidence": 0.7,
        }
    if has_pm:
        return {
            "measurement_type": "PHOTOCURRENT",
            "reasoning": "Optical power meter → photoresponse characterization",
            "confidence": 0.6,
        }
    if has_ph:
        return {
            "measurement_type": "PH_CALIBRATION",
            "reasoning": "pH meter → calibration/titration curve",
            "confidence": 0.75,
        }
    if has_balance:
        return {
            "measurement_type": "CUSTOM_SWEEP",
            "reasoning": "Balance → user-defined mass / gravimetric sweep",
            "confidence": 0.55,
        }
    if has_mfc:
        return {
            "measurement_type": "GAS_SENSOR",
            "reasoning": "Mass flow controller → gas-concentration sensor response",
            "confidence": 0.65,
        }

    # Condensed-matter specialties only when the direction/material explicitly
    # call for them.
    if has_pulse and has_gauss and "spin" in direction_lower:
        return {
            "measurement_type": "SOT",
            "reasoning": "Pulse source + gaussmeter + spin direction → SOT",
            "confidence": 0.7,
        }
    if has_gauss and ("magnetic" in material_lower or "ferro" in material_lower or "magnetic" in direction_lower):
        return {"measurement_type": "AHE", "reasoning": "Gaussmeter + magnetic sample → AHE", "confidence": 0.7}
    if has_gauss:
        return {"measurement_type": "HALL", "reasoning": "Gaussmeter available → Hall effect", "confidence": 0.6}

    if has_temp:
        return {"measurement_type": "RT", "reasoning": "Temperature controller → R-T", "confidence": 0.6}
    if has_lcr:
        return {"measurement_type": "CV", "reasoning": "LCR meter → C-V", "confidence": 0.6}

    return {"measurement_type": "IV", "reasoning": "Default: basic IV characterization", "confidence": 0.5}

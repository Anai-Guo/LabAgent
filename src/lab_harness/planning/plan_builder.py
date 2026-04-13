"""Build measurement plans from templates.

Loads YAML templates for common measurement types, fills in parameters,
and returns a structured MeasurementPlan.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from lab_harness.models.measurement import (
    DataChannel,
    MeasurementPlan,
    MeasurementType,
    SweepAxis,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(measurement_type: str) -> dict:
    """Load a measurement template from YAML."""
    template_path = TEMPLATES_DIR / f"{measurement_type.lower()}.yaml"
    if not template_path.exists():
        raise FileNotFoundError(
            f"No template for measurement type '{measurement_type}'. "
            f"Available: {[p.stem for p in TEMPLATES_DIR.glob('*.yaml')]}"
        )

    with open(template_path) as f:
        return yaml.safe_load(f)


def build_plan_from_template(
    measurement_type: str,
    overrides: dict | None = None,
) -> MeasurementPlan:
    """Build a measurement plan from a template with optional overrides.

    Args:
        measurement_type: Type of measurement (AHE, MR, IV, RT).
        overrides: Optional dict of parameter overrides.

    Returns:
        A MeasurementPlan ready for validation and execution.
    """
    template = _load_template(measurement_type)

    if overrides:
        # Deep merge overrides
        for key, value in overrides.items():
            if key in template and isinstance(template[key], dict) and isinstance(value, dict):
                template[key].update(value)
            else:
                template[key] = value

    x_axis = SweepAxis(**template["x_axis"])
    y_channels = [DataChannel(**ch) for ch in template.get("y_channels", [])]

    outer_sweep = None
    if "outer_sweep" in template:
        outer_sweep = SweepAxis(**template["outer_sweep"])

    mt = MeasurementType(measurement_type.upper())

    return MeasurementPlan(
        measurement_type=mt,
        name=template.get("name", f"{mt.value} Measurement"),
        description=template.get("description", ""),
        x_axis=x_axis,
        y_channels=y_channels,
        outer_sweep=outer_sweep,
        max_current_a=template.get("max_current_a", 0.01),
        max_voltage_v=template.get("max_voltage_v", 20.0),
        max_field_oe=template.get("max_field_oe", 10000.0),
        max_temperature_k=template.get("max_temperature_k", 400.0),
        settling_time_s=template.get("settling_time_s", 0.5),
        num_averages=template.get("num_averages", 1),
        output_dir=template.get("output_dir", "./data"),
    )

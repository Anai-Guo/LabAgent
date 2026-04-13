"""Boundary checker for measurement plan validation.

Validates measurement plans against safety policies to prevent
instrument damage or sample destruction.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from lab_harness.models.measurement import MeasurementPlan
from lab_harness.models.safety import (
    BoundaryViolation,
    Decision,
    SafetyPolicy,
    ValidationResult,
)

logger = logging.getLogger(__name__)

DEFAULT_POLICY_PATH = Path(__file__).parent.parent.parent.parent / "configs" / "default_safety.yaml"


def load_safety_policy(path: Path | None = None) -> SafetyPolicy:
    """Load safety policy from YAML file."""
    p = path or DEFAULT_POLICY_PATH
    if p.exists():
        with open(p) as f:
            raw = yaml.safe_load(f) or {}
        return SafetyPolicy(**raw)
    return SafetyPolicy()


def check_boundaries(
    plan: MeasurementPlan,
    policy: SafetyPolicy | None = None,
) -> ValidationResult:
    """Validate a measurement plan against safety boundaries.

    Three-tier check:
    1. Absolute limits - hard block, never exceeded
    2. Warning thresholds - require operator confirmation
    3. Plan consistency - parameter sanity checks

    Args:
        plan: The measurement plan to validate.
        policy: Safety policy to check against. Uses defaults if not provided.

    Returns:
        ValidationResult with decision and any violations.
    """
    if policy is None:
        policy = load_safety_policy()

    violations: list[BoundaryViolation] = []
    warnings: list[str] = []

    # --- Tier 1: Absolute limits (BLOCK) ---
    if plan.max_current_a > policy.abs_max_current_a:
        violations.append(BoundaryViolation(
            parameter="max_current_a",
            limit=policy.abs_max_current_a,
            requested=plan.max_current_a,
            severity=Decision.BLOCK,
            message=f"Current {plan.max_current_a} A exceeds absolute limit {policy.abs_max_current_a} A",
        ))

    if plan.max_voltage_v > policy.abs_max_voltage_v:
        violations.append(BoundaryViolation(
            parameter="max_voltage_v",
            limit=policy.abs_max_voltage_v,
            requested=plan.max_voltage_v,
            severity=Decision.BLOCK,
            message=f"Voltage {plan.max_voltage_v} V exceeds absolute limit {policy.abs_max_voltage_v} V",
        ))

    if plan.max_field_oe > policy.abs_max_field_oe:
        violations.append(BoundaryViolation(
            parameter="max_field_oe",
            limit=policy.abs_max_field_oe,
            requested=plan.max_field_oe,
            severity=Decision.BLOCK,
            message=f"Field {plan.max_field_oe} Oe exceeds absolute limit {policy.abs_max_field_oe} Oe",
        ))

    if plan.max_temperature_k > policy.abs_max_temperature_k:
        violations.append(BoundaryViolation(
            parameter="max_temperature_k",
            limit=policy.abs_max_temperature_k,
            requested=plan.max_temperature_k,
            severity=Decision.BLOCK,
            message=f"Temperature {plan.max_temperature_k} K exceeds absolute limit {policy.abs_max_temperature_k} K",
        ))

    # Check sweep ranges against limits
    x = plan.x_axis
    if "field" in x.label.lower() or x.unit.lower() == "oe":
        max_field = max(abs(x.start), abs(x.stop))
        if max_field > policy.abs_max_field_oe:
            violations.append(BoundaryViolation(
                parameter="x_axis.field",
                limit=policy.abs_max_field_oe,
                requested=max_field,
                severity=Decision.BLOCK,
                message=f"Sweep field {max_field} Oe exceeds absolute limit",
            ))

    if "current" in x.label.lower() or x.unit.lower() in ("a", "ma", "ua"):
        max_current = max(abs(x.start), abs(x.stop))
        # Convert to amps if needed
        if x.unit.lower() == "ma":
            max_current /= 1000
        elif x.unit.lower() == "ua":
            max_current /= 1e6
        if max_current > policy.abs_max_current_a:
            violations.append(BoundaryViolation(
                parameter="x_axis.current",
                limit=policy.abs_max_current_a,
                requested=max_current,
                severity=Decision.BLOCK,
                message=f"Sweep current {max_current} A exceeds absolute limit",
            ))

    # --- Tier 2: Warning thresholds (REQUIRE_CONFIRM) ---
    if not violations:
        if plan.max_current_a > policy.warn_current_a:
            warnings.append(
                f"Current {plan.max_current_a} A exceeds warning threshold {policy.warn_current_a} A"
            )
        if plan.max_field_oe > policy.warn_field_oe:
            warnings.append(
                f"Field {plan.max_field_oe} Oe exceeds warning threshold {policy.warn_field_oe} Oe"
            )
        if plan.max_temperature_k > policy.warn_temperature_k:
            warnings.append(
                f"Temperature {plan.max_temperature_k} K exceeds warning threshold {policy.warn_temperature_k} K"
            )

    # --- Tier 3: Consistency checks ---
    if x.step == 0:
        warnings.append("Sweep step size is zero - only one point will be measured")
    if plan.total_points > 10000:
        warnings.append(f"Plan has {plan.total_points} points - measurement may take very long")

    # Determine decision
    if violations:
        decision = Decision.BLOCK
    elif warnings:
        decision = Decision.REQUIRE_CONFIRM
    else:
        decision = Decision.ALLOW

    return ValidationResult(
        decision=decision,
        violations=violations,
        warnings=warnings,
    )

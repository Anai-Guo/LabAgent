"""Safety boundary models for measurement validation."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Decision(str, Enum):
    """Safety decision for a plan or action."""
    ALLOW = "allow"
    REQUIRE_CONFIRM = "require_confirm"
    BLOCK = "block"


class BoundaryViolation(BaseModel):
    """A single boundary violation found during validation."""

    parameter: str          # e.g. "max_current_a"
    limit: float
    requested: float
    severity: Decision = Decision.BLOCK
    message: str = ""


class SafetyPolicy(BaseModel):
    """Safety policy with absolute limits."""

    # Absolute limits (never exceeded)
    abs_max_current_a: float = 10.0
    abs_max_voltage_v: float = 1000.0
    abs_max_field_oe: float = 50000.0
    abs_max_temperature_k: float = 500.0
    abs_max_pulse_width_s: float = 10.0

    # Warning thresholds (require confirmation)
    warn_current_a: float = 0.1
    warn_voltage_v: float = 50.0
    warn_field_oe: float = 20000.0
    warn_temperature_k: float = 350.0


class ValidationResult(BaseModel):
    """Result of boundary validation."""

    decision: Decision
    violations: list[BoundaryViolation] = []
    warnings: list[str] = []

    @property
    def is_safe(self) -> bool:
        return self.decision != Decision.BLOCK

    @property
    def needs_confirmation(self) -> bool:
        return self.decision == Decision.REQUIRE_CONFIRM

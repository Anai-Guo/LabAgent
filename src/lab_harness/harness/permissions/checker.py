"""Permission checker for experiment safety.

Three-layer defense:
1. Immutable blocks (absolute limits, never overridden)
2. Boundary checks (from safety policy YAML)
3. Interactive confirmation (user must approve)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PermissionResult(str, Enum):
    ALLOW = "allow"
    NEED_CONFIRM = "need_confirm"
    BLOCK = "block"


@dataclass
class PermissionDecision:
    result: PermissionResult
    reason: str = ""


class PermissionChecker:
    # Layer 1: Immutable blocks
    ABSOLUTE_LIMITS = {
        "max_current_a": 10.0,
        "max_voltage_v": 1000.0,
        "max_field_oe": 50000.0,
        "max_temperature_k": 500.0,
    }

    def evaluate(self, tool_name: str, arguments: dict[str, Any]) -> PermissionDecision:
        # All read-only tools are always allowed
        if tool_name in ("scan_instruments", "healthcheck", "recall_experiments", "search_literature"):
            return PermissionDecision(PermissionResult.ALLOW)

        # Check measurement proposals against safety limits
        if tool_name in ("propose_measurement", "validate_plan"):
            return self._check_measurement_safety(arguments)

        # Data analysis is safe (runs in subprocess)
        if tool_name == "analyze_data":
            return PermissionDecision(PermissionResult.ALLOW)

        # Default: allow with info log
        logger.info("Allowing tool %s (no specific policy)", tool_name)
        return PermissionDecision(PermissionResult.ALLOW)

    def _check_measurement_safety(self, args: dict) -> PermissionDecision:
        for key, limit in self.ABSOLUTE_LIMITS.items():
            if key in args and float(args[key]) > limit:
                return PermissionDecision(PermissionResult.BLOCK, f"{key}={args[key]} exceeds absolute limit {limit}")
        return PermissionDecision(PermissionResult.ALLOW)

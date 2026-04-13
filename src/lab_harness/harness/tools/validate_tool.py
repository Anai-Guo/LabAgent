"""Measurement plan validation tool."""

from __future__ import annotations

import json

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class ValidateInput(BaseModel):
    plan: dict
    sample_description: str = ""


class ValidatePlanTool(BaseTool):
    name = "validate_plan"
    description = (
        "Validate a measurement plan against safety boundaries. "
        "Returns decision (ALLOW / REQUIRE_CONFIRM / BLOCK) with violations and warnings"
    )
    input_model = ValidateInput

    async def execute(self, arguments: ValidateInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.models.measurement import MeasurementPlan
            from lab_harness.planning.boundary_checker import check_boundaries

            plan = MeasurementPlan(**arguments.plan)
            validation = check_boundaries(
                plan=plan,
                sample_description=arguments.sample_description,
            )

            result = {
                "decision": validation.decision.value,
                "violations": [
                    {"parameter": v.parameter, "limit": v.limit, "requested": v.requested, "message": v.message}
                    for v in validation.violations
                ],
                "warnings": validation.warnings,
                "ai_advice": validation.ai_advice,
            }
            output = json.dumps(result, indent=2)
            return ToolResult(
                output=f"Validation result: {validation.decision.value}\n\n{output}",
                metadata={"decision": validation.decision.value},
            )
        except Exception as e:
            return ToolResult(output=f"Validation failed: {e}", is_error=True)

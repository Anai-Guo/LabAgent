"""Measurement plan proposal tool."""

from __future__ import annotations

import json

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class ProposeInput(BaseModel):
    measurement_type: str
    overrides: dict | None = None
    sample_description: str = ""


class ProposeMeasurementTool(BaseTool):
    name = "propose_measurement"
    description = (
        "Build a measurement plan from a YAML template, validate it against "
        "safety boundaries, and return the plan with any violations or warnings"
    )
    input_model = ProposeInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return True

    async def execute(self, arguments: ProposeInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.planning.boundary_checker import check_boundaries
            from lab_harness.planning.plan_builder import build_plan_from_template

            plan = build_plan_from_template(
                measurement_type=arguments.measurement_type,
                overrides=arguments.overrides,
                sample_description=arguments.sample_description,
            )

            validation = check_boundaries(
                plan=plan,
                sample_description=arguments.sample_description,
            )

            plan_dict = json.loads(plan.model_dump_json())
            output_data = {
                "plan": plan_dict,
                "validation": {
                    "decision": validation.decision.value,
                    "violations": [
                        {"parameter": v.parameter, "limit": v.limit, "requested": v.requested, "message": v.message}
                        for v in validation.violations
                    ],
                    "warnings": validation.warnings,
                    "ai_advice": validation.ai_advice,
                },
            }
            output = json.dumps(output_data, indent=2)

            summary = (
                f"Plan for {arguments.measurement_type}: "
                f"{plan.total_points} points, "
                f"decision={validation.decision.value}"
            )
            if validation.warnings:
                summary += f", {len(validation.warnings)} warning(s)"
            if validation.violations:
                summary += f", {len(validation.violations)} violation(s)"

            return ToolResult(
                output=f"{summary}\n\n{output}",
                metadata={
                    "decision": validation.decision.value,
                    "total_points": plan.total_points,
                },
            )
        except Exception as e:
            return ToolResult(output=f"Plan proposal failed: {e}", is_error=True)

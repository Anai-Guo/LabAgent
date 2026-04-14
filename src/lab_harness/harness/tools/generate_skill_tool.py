"""Skill generation tool."""

from __future__ import annotations

import json

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class GenerateSkillInput(BaseModel):
    measurement_type: str
    sample_description: str = ""


class GenerateSkillTool(BaseTool):
    name = "generate_skill"
    description = (
        "Generate and save a new measurement protocol skill using AI. "
        "Creates a markdown skill file with YAML frontmatter describing "
        "a step-by-step measurement protocol for the given type"
    )
    input_model = GenerateSkillInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return False

    async def execute(self, arguments: GenerateSkillInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.skills.generator import generate_skill, save_skill

            content = generate_skill(
                measurement_type=arguments.measurement_type,
                sample_description=arguments.sample_description,
            )
            path = save_skill(arguments.measurement_type, content)
            result = {
                "measurement_type": arguments.measurement_type,
                "skill_path": str(path),
                "content": content,
            }
            output = json.dumps(result, indent=2)
            return ToolResult(
                output=f"Generated skill for {arguments.measurement_type}\n\n{output}",
                metadata={"skill_path": str(path)},
            )
        except Exception as e:
            return ToolResult(output=f"Skill generation failed: {e}", is_error=True)

"""Data analysis tool."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class AnalyzeInput(BaseModel):
    data_path: str
    measurement_type: str
    use_ai: bool = False
    interpret: bool = False
    custom_instructions: str = ""


class AnalyzeDataTool(BaseTool):
    name = "analyze_data"
    description = (
        "Analyze measurement data: generate analysis script from template or AI, "
        "run it, and optionally produce AI interpretation of results"
    )
    input_model = AnalyzeInput

    def is_read_only(self, arguments: BaseModel) -> bool:
        return False

    async def execute(self, arguments: AnalyzeInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.analysis.analyzer import Analyzer

            data_path = Path(arguments.data_path)
            if not data_path.is_absolute():
                data_path = context.cwd / data_path

            if not data_path.exists():
                return ToolResult(
                    output=f"Data file not found: {data_path}",
                    is_error=True,
                )

            analyzer = Analyzer()
            result = analyzer.analyze(
                data_path=data_path,
                measurement_type=arguments.measurement_type,
                use_ai=arguments.use_ai,
                custom_instructions=arguments.custom_instructions,
                interpret=arguments.interpret,
            )

            output_data = {
                "measurement_type": result.measurement_type,
                "script_path": result.script_path,
                "figures": result.figures,
                "extracted_values": result.extracted_values,
                "stdout": result.stdout,
            }
            if result.ai_interpretation:
                output_data["ai_interpretation"] = result.ai_interpretation

            output = json.dumps(output_data, indent=2)
            summary = (
                f"Analysis of {arguments.measurement_type}: "
                f"{len(result.figures)} figure(s), "
                f"{len(result.extracted_values)} extracted value(s)"
            )
            return ToolResult(
                output=f"{summary}\n\n{output}",
                metadata={
                    "figures": len(result.figures),
                    "values": len(result.extracted_values),
                },
            )
        except Exception as e:
            return ToolResult(output=f"Analysis failed: {e}", is_error=True)

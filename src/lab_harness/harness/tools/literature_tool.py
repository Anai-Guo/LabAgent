"""Literature search tool."""

from __future__ import annotations

import json

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class LiteratureInput(BaseModel):
    measurement_type: str
    sample_description: str = ""


class SearchLiteratureTool(BaseTool):
    name = "search_literature"
    description = (
        "Search scientific literature for measurement protocols and parameters "
        "relevant to a given measurement type and sample, via paper-pilot"
    )
    input_model = LiteratureInput

    async def execute(self, arguments: LiteratureInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.literature.paper_pilot_client import PaperPilotClient

            client = PaperPilotClient()
            lit_context = await client.search_for_protocol(
                measurement_type=arguments.measurement_type,
                sample_description=arguments.sample_description,
            )

            result = {
                "measurement_type": lit_context.measurement_type,
                "suggested_parameters": lit_context.suggested_parameters,
                "evidence_chunks": lit_context.evidence_chunks,
                "source_papers": lit_context.source_papers,
            }
            output = json.dumps(result, indent=2)

            n_papers = len(lit_context.source_papers)
            n_params = len(lit_context.suggested_parameters)
            summary = (
                f"Literature search for {arguments.measurement_type}: "
                f"{n_papers} paper(s), {n_params} suggested parameter(s)"
            )
            return ToolResult(
                output=f"{summary}\n\n{output}",
                metadata={"papers": n_papers, "parameters": n_params},
            )
        except Exception as e:
            return ToolResult(output=f"Literature search failed: {e}", is_error=True)

"""Client for paper-pilot MCP server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


class LiteratureContext(BaseModel):
    """Parsed literature results relevant to measurement planning."""

    measurement_type: str
    suggested_parameters: dict[str, Any] = {}
    evidence_chunks: list[str] = []
    source_papers: list[dict] = []


# Research question templates per measurement type
RESEARCH_QUESTIONS: dict[str, str] = {
    "AHE": (
        "What instruments, field ranges, current levels, and protocols are used "
        "for anomalous Hall effect measurement in metallic films?"
    ),
    "MR": (
        "What field sweep ranges, current bias levels, and configurations are used "
        "for magnetoresistance measurements in multilayer samples?"
    ),
    "SOT": (
        "What pulse current amplitudes, field ranges, and measurement sequences "
        "are used for spin-orbit torque characterization?"
    ),
    "IV": (
        "What current ranges, voltage compliance, and measurement procedures are "
        "used for I-V characterization of thin film devices?"
    ),
    "RT": (
        "What temperature ranges, sweep rates, and source current levels are used "
        "for resistance vs temperature measurements?"
    ),
    "CV": ("What DC bias ranges, frequencies, and procedures are used for capacitance-voltage measurements?"),
}


@dataclass
class PaperPilotClient:
    """Client that calls paper-pilot MCP tools for literature context."""

    enabled: bool = True

    async def search_for_protocol(
        self,
        measurement_type: str,
        sample_description: str = "",
    ) -> LiteratureContext:
        """Query paper-pilot for measurement protocol information.

        Currently returns a stub context. Full MCP client integration
        will connect to paper-pilot's deep_read_topic tool.
        """
        mt = measurement_type.upper()
        question = RESEARCH_QUESTIONS.get(mt, f"What measurement protocol is used for {mt}?")

        if sample_description:
            question = f"{question} Specifically for {sample_description}."

        # TODO: Connect to paper-pilot MCP server via mcp.client
        # For now, return empty context indicating no literature available
        return LiteratureContext(
            measurement_type=mt,
            suggested_parameters={},
            evidence_chunks=[],
            source_papers=[],
        )

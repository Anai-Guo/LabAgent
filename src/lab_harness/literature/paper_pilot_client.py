"""Client for paper-pilot MCP server with LLM-based fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


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

# System prompt for the LLM-based protocol suggestion fallback
_PROTOCOL_SYSTEM_PROMPT = """\
You are an expert in condensed matter physics transport measurements.
Given a measurement type and optional sample description, suggest a concrete
measurement protocol with instrument parameters.

Respond ONLY with valid JSON in this exact schema (no markdown fences):
{
  "suggested_parameters": {
    "<parameter_name>": "<value with units>"
  },
  "evidence_chunks": [
    "<brief justification sentence>"
  ],
  "instruments": [
    "<instrument role: typical model>"
  ]
}

Include typical numeric ranges, units, and common instrument models.
Be specific and practical -- these parameters will seed a measurement plan.\
"""


@dataclass
class PaperPilotClient:
    """Client that queries paper-pilot MCP or falls back to LLM-based suggestions."""

    enabled: bool = True

    async def search_for_protocol(
        self,
        measurement_type: str,
        sample_description: str = "",
        emit: Callable | None = None,
    ) -> LiteratureContext:
        """Query for measurement protocol information.

        Strategy:
        1. Try paper-pilot MCP server (if available and enabled).
        2. Fall back to LLM-based protocol suggestion via litellm.

        Returns a LiteratureContext with suggested parameters that can
        seed the measurement planning pipeline.
        """
        mt = measurement_type.upper()

        if emit:
            await emit("literature.start", measurement_type=mt, sample=sample_description)

        # Try 1: paper-pilot MCP
        if self.enabled:
            try:
                result = await self._try_paper_pilot(mt, sample_description, emit=emit)
                if result is not None:
                    if emit:
                        await emit(
                            "literature.complete",
                            paper_count=len(result.source_papers),
                        )
                    return result
            except Exception:
                logger.debug("paper-pilot MCP unavailable, falling back to LLM")

        # Try 2: LLM-based protocol suggestion
        result = await self._llm_fallback(mt, sample_description, emit=emit)
        if emit:
            await emit(
                "literature.complete",
                paper_count=len(result.source_papers),
            )
        return result

    # ------------------------------------------------------------------
    # paper-pilot MCP path
    # ------------------------------------------------------------------

    async def _try_paper_pilot(
        self,
        measurement_type: str,
        sample_description: str,
        emit: Callable | None = None,
    ) -> LiteratureContext | None:
        """Attempt to connect to paper-pilot MCP and query for protocols.

        Returns None if paper-pilot is not reachable so the caller can
        fall back to the LLM path.
        """
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            logger.debug("mcp package not installed; skipping paper-pilot")
            return None

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@anthropic-ai/paper-pilot"],
        )

        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    question = RESEARCH_QUESTIONS.get(
                        measurement_type,
                        f"What measurement protocol is used for {measurement_type}?",
                    )
                    if sample_description:
                        question = f"{question} Specifically for {sample_description}."

                    result = await session.call_tool(
                        "deep_read_topic",
                        arguments={"topic": question},
                    )

                    context = self._parse_mcp_result(measurement_type, result)
                    if emit:
                        for paper in context.source_papers:
                            title = paper.get("title") if isinstance(paper, dict) else str(paper)
                            await emit("literature.paper_found", title=title)
                    return context
        except Exception as exc:
            logger.debug("paper-pilot MCP call failed: %s", exc)
            return None

    @staticmethod
    def _parse_mcp_result(
        measurement_type: str,
        mcp_result: Any,
    ) -> LiteratureContext:
        """Parse an MCP tool result into LiteratureContext."""
        text = ""
        if hasattr(mcp_result, "content"):
            for block in mcp_result.content:
                if hasattr(block, "text"):
                    text += block.text
        else:
            text = str(mcp_result)

        return LiteratureContext(
            measurement_type=measurement_type,
            suggested_parameters={},
            evidence_chunks=[text[:500]] if text else [],
            source_papers=[],
        )

    # ------------------------------------------------------------------
    # LLM fallback path
    # ------------------------------------------------------------------

    async def _llm_fallback(
        self,
        measurement_type: str,
        sample_description: str,
        emit: Callable | None = None,
    ) -> LiteratureContext:
        """Use litellm to generate protocol suggestions from LLM knowledge."""
        from lab_harness.config import Settings
        from lab_harness.llm.router import LLMRouter

        question = RESEARCH_QUESTIONS.get(
            measurement_type,
            f"What measurement protocol is used for {measurement_type}?",
        )
        if sample_description:
            question = f"{question} Specifically for sample: {sample_description}."

        settings = Settings.load()
        router = LLMRouter(config=settings.model)

        messages = [
            {"role": "system", "content": _PROTOCOL_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        try:
            response = await router.acomplete(messages)
            content = response["choices"][0]["message"].get("content", "")
            context = self._parse_llm_response(measurement_type, content)
            if emit:
                for paper in context.source_papers:
                    title = paper.get("title") if isinstance(paper, dict) else str(paper)
                    if not title and isinstance(paper, dict):
                        title = paper.get("source") or "LLM-suggested reference"
                    await emit("literature.paper_found", title=title)
            return context
        except Exception as exc:
            logger.warning("LLM fallback failed: %s", exc)
            return LiteratureContext(
                measurement_type=measurement_type,
                suggested_parameters={},
                evidence_chunks=[f"LLM fallback error: {exc}"],
                source_papers=[],
            )

    @staticmethod
    def _parse_llm_response(
        measurement_type: str,
        content: str,
    ) -> LiteratureContext:
        """Parse the LLM JSON response into LiteratureContext."""
        # Strip markdown fences if the LLM included them despite instructions
        text = content.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = text.index("\n")
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[: -len("```")]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM response as JSON")
            return LiteratureContext(
                measurement_type=measurement_type,
                suggested_parameters={},
                evidence_chunks=[content[:500]],
                source_papers=[],
            )

        suggested = data.get("suggested_parameters", {})
        evidence = data.get("evidence_chunks", [])
        instruments = data.get("instruments", [])

        # Fold instrument suggestions into source_papers as pseudo-references
        source_papers = [{"source": "LLM knowledge", "instruments": instruments}] if instruments else []

        return LiteratureContext(
            measurement_type=measurement_type,
            suggested_parameters=suggested,
            evidence_chunks=evidence if isinstance(evidence, list) else [str(evidence)],
            source_papers=source_papers,
        )

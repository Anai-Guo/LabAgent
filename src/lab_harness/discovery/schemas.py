"""Pydantic models for LLM-based instrument classification responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InstrumentClassification(BaseModel):
    """LLM classification result for a single instrument."""

    role: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ClassificationResponse(BaseModel):
    """Full LLM classification response for a set of instruments.

    Keys in ``assignments`` are VISA resource strings
    (e.g. ``"GPIB0::5::INSTR"``).
    """

    assignments: dict[str, InstrumentClassification]

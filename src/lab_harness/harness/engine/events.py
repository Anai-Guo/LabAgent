"""Stream events emitted by the query engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StreamEvent:
    """Base class for all stream events."""

    pass


@dataclass
class TextDelta(StreamEvent):
    text: str


@dataclass
class ToolStart(StreamEvent):
    tool_name: str
    tool_input: dict[str, Any]


@dataclass
class ToolComplete(StreamEvent):
    tool_name: str
    output: str
    is_error: bool = False


@dataclass
class SafetyCheck(StreamEvent):
    decision: str  # "allow", "require_confirm", "block"
    message: str


@dataclass
class StatusUpdate(StreamEvent):
    message: str


@dataclass
class ErrorEvent(StreamEvent):
    message: str
    recoverable: bool = True


@dataclass
class TurnComplete(StreamEvent):
    text: str
    tool_calls_made: int = 0
    turns_used: int = 0
    turns_remaining: int = 0

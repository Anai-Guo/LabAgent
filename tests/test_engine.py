"""Tests for the harness query engine with mocked LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pydantic import BaseModel

from lab_harness.config import ModelConfig
from lab_harness.harness.engine.context import RuntimeContext
from lab_harness.harness.engine.events import ErrorEvent, TextDelta, ToolComplete, ToolStart, TurnComplete
from lab_harness.harness.engine.session import Session
from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolRegistry, ToolResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _EmptyInput(BaseModel):
    pass


class _StubTool(BaseTool):
    """A minimal tool for testing tool-call dispatch."""

    name = "scan_instruments"
    description = "Scan for lab instruments"
    input_model = _EmptyInput

    async def execute(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        return ToolResult(output='{"instruments": []}')


def _make_registry(tools: list[BaseTool] | None = None) -> ToolRegistry:
    registry = ToolRegistry()
    for t in tools or []:
        registry.register(t)
    return registry


def _make_context(
    registry: ToolRegistry | None = None,
    max_turns: int = 5,
) -> RuntimeContext:
    return RuntimeContext(
        tool_registry=registry or _make_registry(),
        model_config=ModelConfig(),
        max_turns=max_turns,
    )


def _text_response(text: str) -> dict:
    """Build a mock LLM response that contains only text (no tool calls)."""
    return {
        "choices": [
            {
                "message": {
                    "content": text,
                    "role": "assistant",
                },
            }
        ]
    }


def _tool_call_response(tool_name: str, arguments: str = "{}") -> dict:
    """Build a mock LLM response that requests a single tool call."""
    return {
        "choices": [
            {
                "message": {
                    "content": "",
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_001",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": arguments,
                            },
                        }
                    ],
                },
            }
        ]
    }


# ---------------------------------------------------------------------------
# Test 1: Simple text response (no tool calls)
# ---------------------------------------------------------------------------


async def test_text_only_response():
    """Mock LLM returns text only -- should yield TextDelta + TurnComplete."""
    ctx = _make_context()
    messages = [{"role": "user", "content": "Hello"}]

    with patch("lab_harness.llm.router.LLMRouter") as MockRouter:
        instance = MockRouter.return_value
        instance.acomplete = AsyncMock(return_value=_text_response("Hi there!"))

        from lab_harness.harness.engine.query import run_query

        events = [ev async for ev in run_query(ctx, messages)]

    # Should contain a StatusUpdate, a TextDelta, and a TurnComplete
    text_deltas = [e for e in events if isinstance(e, TextDelta)]
    turn_completes = [e for e in events if isinstance(e, TurnComplete)]

    assert len(text_deltas) == 1
    assert text_deltas[0].text == "Hi there!"
    assert len(turn_completes) == 1
    assert turn_completes[0].text == "Hi there!"


# ---------------------------------------------------------------------------
# Test 2: Tool call response
# ---------------------------------------------------------------------------


async def test_tool_call_response():
    """Mock LLM returns tool_calls for scan_instruments -- should yield ToolStart + ToolComplete."""
    stub = _StubTool()
    registry = _make_registry([stub])
    ctx = _make_context(registry=registry)
    messages = [{"role": "user", "content": "Scan my instruments"}]

    # First call returns a tool call; second call returns plain text (loop ends).
    mock_acomplete = AsyncMock(
        side_effect=[
            _tool_call_response("scan_instruments"),
            _text_response("Found 0 instruments."),
        ]
    )

    with patch("lab_harness.llm.router.LLMRouter") as MockRouter:
        MockRouter.return_value.acomplete = mock_acomplete

        from lab_harness.harness.engine.query import run_query

        events = [ev async for ev in run_query(ctx, messages)]

    tool_starts = [e for e in events if isinstance(e, ToolStart)]
    tool_completes = [e for e in events if isinstance(e, ToolComplete)]

    assert len(tool_starts) == 1
    assert tool_starts[0].tool_name == "scan_instruments"

    assert len(tool_completes) == 1
    assert tool_completes[0].tool_name == "scan_instruments"
    assert not tool_completes[0].is_error
    assert "instruments" in tool_completes[0].output


# ---------------------------------------------------------------------------
# Test 3: Turn budget exhaustion
# ---------------------------------------------------------------------------


async def test_turn_budget_exhaustion():
    """Set max_turns=1, mock LLM always returns tool calls -- should stop after 1 turn."""
    stub = _StubTool()
    registry = _make_registry([stub])
    ctx = _make_context(registry=registry, max_turns=1)
    messages = [{"role": "user", "content": "Keep scanning"}]

    mock_acomplete = AsyncMock(return_value=_tool_call_response("scan_instruments"))

    with patch("lab_harness.llm.router.LLMRouter") as MockRouter:
        MockRouter.return_value.acomplete = mock_acomplete

        from lab_harness.harness.engine.query import run_query

        events = [ev async for ev in run_query(ctx, messages)]

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert "budget" in error_events[0].message.lower() or "exhausted" in error_events[0].message.lower()


# ---------------------------------------------------------------------------
# Test 4: Session save / load
# ---------------------------------------------------------------------------


def test_session_save_load(tmp_path):
    """Create session, add messages, save to tmp_path, load back, verify."""
    session = Session.new(model="test-model")
    session.add_user_message("Hello")
    session.add_assistant_message("Hi there")
    session.metadata["experiment"] = "AHE"

    path = tmp_path / "sessions" / "test.json"
    session.save(path)

    loaded = Session.load(path)
    assert loaded.session_id == session.session_id
    assert loaded.model == "test-model"
    assert len(loaded.messages) == 2
    assert loaded.messages[0] == {"role": "user", "content": "Hello"}
    assert loaded.messages[1] == {"role": "assistant", "content": "Hi there"}
    assert loaded.metadata["experiment"] == "AHE"


# ---------------------------------------------------------------------------
# Test 5: RuntimeContext turn tracking
# ---------------------------------------------------------------------------


def test_runtime_context_turn_tracking():
    """tick_turn() increments counter, returns False when exhausted."""
    ctx = _make_context(max_turns=3)

    assert ctx.turns_remaining == 3

    assert ctx.tick_turn() is True  # turn 1 of 3
    assert ctx.turns_remaining == 2

    assert ctx.tick_turn() is True  # turn 2 of 3
    assert ctx.turns_remaining == 1

    assert ctx.tick_turn() is True  # turn 3 of 3
    assert ctx.turns_remaining == 0

    assert ctx.tick_turn() is False  # turn 4 -- over budget
    assert ctx.turns_remaining == 0

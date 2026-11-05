"""Tests for run_query error paths, memory injection and tool-dispatch failures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from lab_harness.config import ModelConfig
from lab_harness.harness.engine.context import RuntimeContext
from lab_harness.harness.engine.events import ErrorEvent, ToolComplete, ToolStart, TurnComplete
from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolRegistry, ToolResult


class _CountInput(BaseModel):
    count: int


class _CountTool(BaseTool):
    name = "count"
    description = "Echo a count"
    input_model = _CountInput

    async def execute(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        return ToolResult(output=f"count={arguments.count}")


class _BoomTool(BaseTool):
    name = "boom"
    description = "Always raises"
    input_model = _CountInput

    async def execute(self, arguments: BaseModel, context: ToolContext) -> ToolResult:
        raise RuntimeError("kaboom")


def _ctx(*tools: BaseTool, memory_store=None) -> RuntimeContext:
    registry = ToolRegistry()
    for t in tools:
        registry.register(t)
    return RuntimeContext(tool_registry=registry, model_config=ModelConfig(), memory_store=memory_store, max_turns=5)


def _text(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def _call(name: str, arguments: str) -> dict:
    tc = {"id": "call_1", "type": "function", "function": {"name": name, "arguments": arguments}}
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [tc]}}]}


async def _run(ctx: RuntimeContext, responses) -> tuple[list, AsyncMock]:
    acomplete = AsyncMock(side_effect=responses)
    with patch("lab_harness.llm.router.LLMRouter") as MockRouter:
        MockRouter.return_value.acomplete = acomplete
        from lab_harness.harness.engine.query import run_query

        events = [ev async for ev in run_query(ctx, [{"role": "user", "content": "hi"}])]
    return events, acomplete


async def test_llm_exception_yields_unrecoverable_error():
    events, _ = await _run(_ctx(), [RuntimeError("rate limited")])
    errors = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(errors) == 1
    assert errors[0].message == "LLM error: rate limited"
    assert errors[0].recoverable is False
    assert not any(isinstance(e, TurnComplete) for e in events)


@pytest.mark.parametrize(
    ("rendered", "injected"),
    [("- IV sweep on sample A", True), ("No previous experiments recorded.", False), ("", False)],
)
async def test_memory_snapshot_injection(rendered, injected):
    snapshot = MagicMock()
    snapshot.render_for_prompt.return_value = rendered
    store = object()
    with patch("lab_harness.memory.snapshot.MemorySnapshot.capture", return_value=snapshot) as capture:
        _, acomplete = await _run(_ctx(memory_store=store), [_text("ok")])

    capture.assert_called_once_with(store)
    system = acomplete.call_args.args[0][0]["content"]
    assert ("Experiment memory:" in system) is injected
    if injected:
        assert system.endswith(rendered)


async def test_tool_message_history_and_valid_arguments():
    events, acomplete = await _run(_ctx(_CountTool()), [_call("count", '{"count": 3}'), _text("done")])
    start = next(e for e in events if isinstance(e, ToolStart))
    done = next(e for e in events if isinstance(e, ToolComplete))
    assert start.tool_input == {"count": 3}
    assert (done.output, done.is_error) == ("count=3", False)

    second_messages = acomplete.call_args_list[1].args[0]
    assert second_messages[-2]["tool_calls"][0]["id"] == "call_1"
    assert second_messages[-1] == {"role": "tool", "tool_call_id": "call_1", "content": "count=3"}


async def test_malformed_json_arguments_fall_back_to_empty_dict():
    events, _ = await _run(_ctx(_CountTool()), [_call("count", "{not json"), _text("done")])
    start = next(e for e in events if isinstance(e, ToolStart))
    done = next(e for e in events if isinstance(e, ToolComplete))
    assert start.tool_input == {}
    # Empty args then fail pydantic validation (count is required) -> reported as a tool error.
    assert done.is_error is True
    assert done.output.startswith("Tool error:")


async def test_unknown_tool_reports_error_and_loop_continues():
    events, acomplete = await _run(_ctx(), [_call("missing", "{}"), _text("sorry")])
    done = next(e for e in events if isinstance(e, ToolComplete))
    assert (done.output, done.is_error) == ("Unknown tool: missing", True)
    assert acomplete.await_count == 2
    assert isinstance(events[-1], TurnComplete)


async def test_tool_execute_exception_is_captured():
    events, _ = await _run(_ctx(_BoomTool()), [_call("boom", '{"count": 1}'), _text("recovered")])
    done = next(e for e in events if isinstance(e, ToolComplete))
    assert (done.output, done.is_error) == ("Tool error: kaboom", True)
    assert events[-1].text == "recovered"

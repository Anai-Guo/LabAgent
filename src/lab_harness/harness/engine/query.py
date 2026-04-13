"""Core query engine — the agent loop.

Inspired by OpenHarness QueryEngine pattern:
message → LLM → tool calls → results → loop
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from lab_harness.harness.engine.context import RuntimeContext
from lab_harness.harness.engine.events import (
    ErrorEvent,
    StatusUpdate,
    StreamEvent,
    TextDelta,
    ToolComplete,
    ToolStart,
    TurnComplete,
)
from lab_harness.harness.tools.base import ToolContext, ToolResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are AI Harness for Lab — a fully automated lab assistant.
You help researchers plan, execute, and analyze scientific measurements.

You have access to tools for:
- Scanning and classifying lab instruments
- Generating measurement plans with safety validation
- Searching scientific literature for protocols
- Analyzing measurement data with AI interpretation
- Recalling past experiment parameters from memory

Always validate measurement plans before execution.
When safety boundaries are exceeded, explain the risk and suggest alternatives.
Be concise and actionable.
"""


async def run_query(
    context: RuntimeContext,
    messages: list[dict[str, Any]],
) -> AsyncGenerator[StreamEvent, None]:
    """Core agent loop: process user message, call tools, yield events.

    This is an async generator that yields StreamEvent objects.
    The caller (TUI or CLI) decides how to render them.
    """
    from lab_harness.llm.router import LLMRouter

    router = LLMRouter(config=context.model_config)
    tools_schema = context.tool_registry.to_api_schema()

    # Inject memory snapshot if available
    system = SYSTEM_PROMPT
    if context.memory_store:
        from lab_harness.memory.snapshot import MemorySnapshot

        snapshot = MemorySnapshot.capture(context.memory_store)
        memory_text = snapshot.render_for_prompt()
        if memory_text and "No previous" not in memory_text:
            system += f"\n\nExperiment memory:\n{memory_text}"

    full_messages = [{"role": "system", "content": system}] + messages

    while context.tick_turn():
        yield StatusUpdate(message=f"Turn {context._turns_used}/{context.max_turns}")

        try:
            response = await router.acomplete(full_messages, tools=tools_schema)
        except Exception as e:
            yield ErrorEvent(message=f"LLM error: {e}", recoverable=False)
            return

        choice = response["choices"][0]
        msg = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        # Yield text content
        text_content = msg.get("content") or ""
        if text_content:
            yield TextDelta(text=text_content)

        # Check for tool calls
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            yield TurnComplete(
                text=text_content,
                turns_used=context._turns_used,
                turns_remaining=context.turns_remaining,
            )
            return

        # Append assistant message to history
        full_messages.append(msg)

        # Execute each tool call
        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            try:
                tool_args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                tool_args = {}

            yield ToolStart(tool_name=tool_name, tool_input=tool_args)

            tool = context.tool_registry.get(tool_name)
            if not tool:
                result = ToolResult(output=f"Unknown tool: {tool_name}", is_error=True)
            else:
                try:
                    parsed = tool.input_model.model_validate(tool_args)
                    tool_ctx = ToolContext(metadata=context.metadata)
                    result = await tool.execute(parsed, tool_ctx)
                except Exception as e:
                    result = ToolResult(output=f"Tool error: {e}", is_error=True)

            yield ToolComplete(tool_name=tool_name, output=result.output, is_error=result.is_error)

            # Append tool result to messages
            full_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result.output,
                }
            )

    yield ErrorEvent(message="Turn budget exhausted", recoverable=False)

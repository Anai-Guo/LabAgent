"""Agent conversation loop - orchestrates the full measurement workflow."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from lab_harness.agent.budget import Budget
from lab_harness.config import Settings
from lab_harness.harness.tools.base import ToolContext, ToolRegistry, create_default_registry
from lab_harness.memory.snapshot import MemorySnapshot
from lab_harness.memory.store import MemoryStore
from lab_harness.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


@dataclass
class LabAgent:
    """AI agent that guides researchers through measurement workflows."""

    settings: Settings = field(default_factory=Settings.load)
    budget: Budget = field(default_factory=Budget)
    skill_registry: SkillRegistry = field(default_factory=SkillRegistry)
    history: list[dict[str, str]] = field(default_factory=list)
    memory_store: MemoryStore = field(default_factory=MemoryStore)
    tool_registry: ToolRegistry = field(default_factory=create_default_registry)
    _snapshot: MemorySnapshot | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.skill_registry.discover()
        self._snapshot = MemorySnapshot.capture(self.memory_store)

    async def run_conversation(self, user_message: str) -> str:
        """Process a user message through the agent loop.

        Steps:
        1. Load skill registry (progressive disclosure)
        2. Build system prompt with available tools
        3. Call LLM via litellm router with tool definitions
        4. If tool_calls -> execute tools -> append results -> call LLM again
        5. Repeat until LLM returns text (no tool_calls) or budget exhausted
        """
        if self.budget.exhausted:
            return "Budget exhausted. Please start a new session."

        self.history.append({"role": "user", "content": user_message})

        # Build system prompt with skill summaries
        skills = self.skill_registry.discover()
        skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)

        memory_context = self._snapshot.render_for_prompt() if self._snapshot else ""

        system_prompt = f"""You are Lab Harness, an AI assistant for physics transport measurements.

Available measurement protocols:
{skill_list}

Experiment memory:
{memory_context}

Guide the researcher through their measurement workflow step by step.
Use the provided tools to scan instruments, classify them, propose
measurement plans, search literature, and recall past experiments."""

        from lab_harness.llm.router import LLMRouter

        router = LLMRouter(config=self.settings.model)

        # Get tool definitions from the registry
        tool_schemas = self.tool_registry.to_api_schema()

        messages = [
            {"role": "system", "content": system_prompt},
            *self.history,
        ]

        # Agentic tool-calling loop
        while not self.budget.exhausted:
            response = await router.acomplete(messages, tools=tool_schemas)
            choice = response["choices"][0]
            msg = choice["message"]

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                # No tool calls - LLM returned a final text response
                content = msg.get("content", "")
                self.history.append({"role": "assistant", "content": content})
                self.budget.tick()
                self._maybe_record_measurement(content)
                return content

            # Append the assistant message (with tool_calls) to context
            messages.append(msg)

            # Execute each tool call via the registry
            for tc in tool_calls:
                fn = tc["function"]
                tool_name = fn["name"]
                try:
                    raw = fn["arguments"]
                    arguments = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                logger.info("Executing tool: %s(%s)", tool_name, arguments)
                result = await self._execute_tool(tool_name, arguments)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    }
                )

            self.budget.tick()

        return "Budget exhausted. Please start a new session."

    async def _execute_tool(self, name: str, arguments: dict) -> str:
        """Execute a tool via the ToolRegistry and return the result string."""
        tool = self.tool_registry.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            parsed_input = tool.input_model.model_validate(arguments)
            context = ToolContext()
            result = await tool.execute(parsed_input, context)
            return result.output
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return json.dumps({"error": f"{name} failed: {exc}"})

    def _maybe_record_measurement(self, response: str) -> None:
        """Detect completed measurements in the response and record them."""
        measurement_keywords = r"\b(measurement completed|data saved|scan finished|sweep completed)\b"
        if not re.search(measurement_keywords, response, re.IGNORECASE):
            return
        # Extract measurement type from response if possible
        type_match = re.search(r"\b(AHE|MR|IV|RT|SOT|CV)\b", response)
        mtype = type_match.group(1) if type_match else "UNKNOWN"
        record_id = self.memory_store.record_experiment(
            measurement_type=mtype,
            notes=response[:200],
        )
        logger.info("Auto-recorded experiment %d (type=%s)", record_id, mtype)

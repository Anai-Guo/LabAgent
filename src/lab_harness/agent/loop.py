"""Agent conversation loop - orchestrates the full measurement workflow."""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from lab_harness.agent.budget import Budget
from lab_harness.config import Settings
from lab_harness.memory.store import MemoryStore
from lab_harness.memory.snapshot import MemorySnapshot
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
    _snapshot: MemorySnapshot | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.skill_registry.discover()
        self._snapshot = MemorySnapshot.capture(self.memory_store)

    async def run_conversation(self, user_message: str) -> str:
        """Process a user message through the agent loop.

        Steps:
        1. Load skill registry (progressive disclosure)
        2. Build system prompt with available tools
        3. Call LLM via litellm router
        4. Parse response: tool calls or final text
        5. Check budget
        """
        if self.budget.exhausted:
            return "Budget exhausted. Please start a new session."

        self.history.append({"role": "user", "content": user_message})

        # Build system prompt with skill summaries
        skills = self.skill_registry.discover()
        skill_list = "\n".join(
            f"- {s.name}: {s.description}" for s in skills
        )

        memory_context = self._snapshot.render_for_prompt() if self._snapshot else ""

        system_prompt = f"""You are Lab Harness, an AI assistant for physics transport measurements.

Available measurement protocols:
{skill_list}

Available tools: scan_instruments, classify_instruments, propose_measurement, validate_plan, search_literature

Experiment memory:
{memory_context}

Guide the researcher through their measurement workflow step by step."""

        # Call LLM
        from lab_harness.llm.router import LLMRouter
        router = LLMRouter(config=self.settings.model)

        messages = [
            {"role": "system", "content": system_prompt},
            *self.history,
        ]

        response = router.complete(messages)
        content = response["choices"][0]["message"]["content"]

        self.history.append({"role": "assistant", "content": content})
        self.budget.tick()

        # Auto-record if response mentions a completed measurement
        self._maybe_record_measurement(content)

        return content

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

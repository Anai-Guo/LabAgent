"""Agent loop -- thin wrapper around harness engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from lab_harness.config import Settings
from lab_harness.harness.engine.context import RuntimeContext
from lab_harness.harness.engine.events import ErrorEvent, TextDelta, TurnComplete
from lab_harness.harness.engine.query import run_query
from lab_harness.harness.tools.base import create_default_registry

logger = logging.getLogger(__name__)


@dataclass
class LabAgent:
    """Conversational lab agent -- wraps the harness engine."""

    settings: Settings = field(default_factory=Settings.load)

    def __post_init__(self):
        self.registry = create_default_registry()
        self.context = RuntimeContext(
            tool_registry=self.registry,
            model_config=self.settings.model,
        )
        # Load memory if available
        try:
            from lab_harness.memory.store import MemoryStore

            self.context.memory_store = MemoryStore()
        except Exception:
            pass

    async def run_conversation(self, user_message: str) -> str:
        """Process a user message and return the assistant's response."""
        messages = [{"role": "user", "content": user_message}]

        response_parts = []
        async for event in run_query(self.context, messages):
            if isinstance(event, TextDelta):
                response_parts.append(event.text)
            elif isinstance(event, TurnComplete):
                if event.text:
                    response_parts.append(event.text)
            elif isinstance(event, ErrorEvent):
                response_parts.append(f"Error: {event.message}")

        return "".join(response_parts)

"""Runtime context for the agent engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lab_harness.config import ModelConfig
from lab_harness.harness.tools.base import ToolRegistry
from lab_harness.memory.store import MemoryStore


@dataclass
class RuntimeContext:
    tool_registry: ToolRegistry
    model_config: ModelConfig
    memory_store: MemoryStore | None = None
    session_id: str = ""
    max_turns: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)
    _turns_used: int = field(default=0, init=False)

    @property
    def turns_remaining(self) -> int:
        return max(0, self.max_turns - self._turns_used)

    def tick_turn(self) -> bool:
        self._turns_used += 1
        return self._turns_used <= self.max_turns

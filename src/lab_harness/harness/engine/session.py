"""Session management for experiment continuity."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Session:
    session_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant_message(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "model": self.model,
            "metadata": self.metadata,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Session saved to %s", path)

    @classmethod
    def load(cls, path: Path) -> Session:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    @classmethod
    def new(cls, model: str = "") -> Session:
        from uuid import uuid4

        return cls(session_id=f"exp-{uuid4().hex[:8]}", model=model)

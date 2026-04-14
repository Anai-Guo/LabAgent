"""Live session registry with asyncio event queues for SSE streaming."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from lab_harness.orchestrator.session import ExperimentSession

logger = logging.getLogger(__name__)


@dataclass
class LiveSession:
    """A running experiment session with an event queue for SSE."""

    session: ExperimentSession
    events: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    done: bool = False

    async def emit(self, event_type: str, **data: Any) -> None:
        """Push an event to the queue."""
        await self.events.put(
            {
                "type": event_type,
                "data": data,
                "ts": time.time(),
            }
        )

    def emit_sync(self, event_type: str, **data: Any) -> None:
        """Thread-safe synchronous emit (from sync code paths)."""
        try:
            self.events.put_nowait(
                {
                    "type": event_type,
                    "data": data,
                    "ts": time.time(),
                }
            )
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping %s", event_type)


class SessionRegistry:
    """Global registry of live experiment sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}

    def create(self) -> LiveSession:
        """Create a new live session."""
        session = ExperimentSession()
        live = LiveSession(session=session)
        self._sessions[session.session_id] = live
        logger.info("Created live session %s", session.session_id)
        return live

    def get(self, session_id: str) -> LiveSession | None:
        """Retrieve a live session by ID."""
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        """Remove a session (after completion)."""
        self._sessions.pop(session_id, None)


# Global singleton
_registry: SessionRegistry | None = None


def get_registry() -> SessionRegistry:
    """Return the global session registry."""
    global _registry
    if _registry is None:
        _registry = SessionRegistry()
    return _registry

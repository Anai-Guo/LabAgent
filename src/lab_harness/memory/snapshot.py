"""Frozen memory snapshot for agent sessions."""

from __future__ import annotations

from dataclasses import dataclass

from lab_harness.memory.store import ExperimentRecord, MemoryStore


@dataclass
class MemorySnapshot:
    """Frozen view of experiment history, loaded once at session start."""

    recent_experiments: list[ExperimentRecord]
    total_count: int

    @classmethod
    def capture(cls, store: MemoryStore, recent_limit: int = 5) -> MemorySnapshot:
        """Create a frozen snapshot from the memory store."""
        recent = store.get_recent(limit=recent_limit)
        with __import__("sqlite3").connect(store.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        return cls(recent_experiments=recent, total_count=total)

    def render_for_prompt(self) -> str:
        """Render snapshot as text for system prompt injection."""
        if not self.recent_experiments:
            return "No previous experiments recorded."
        lines = [f"Previous experiments ({self.total_count} total):"]
        for exp in self.recent_experiments:
            lines.append(f"- [{exp.timestamp[:10]}] {exp.measurement_type} on '{exp.sample}': {exp.notes[:80]}")
        return "\n".join(lines)

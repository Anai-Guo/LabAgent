"""Experiment memory recall tool."""

from __future__ import annotations

import json

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class RecallInput(BaseModel):
    query: str
    limit: int = 10


class RecallExperimentsTool(BaseTool):
    name = "recall_experiments"
    description = (
        "Search experiment memory (SQLite + FTS5) for past measurements "
        "matching a query. Returns matching experiment records with parameters and notes"
    )
    input_model = RecallInput

    async def execute(self, arguments: RecallInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.memory.store import MemoryStore

            store = MemoryStore()
            records = store.search(query=arguments.query, limit=arguments.limit)

            results = [
                {
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "sample": r.sample,
                    "measurement_type": r.measurement_type,
                    "parameters": r.parameters,
                    "result_path": r.result_path,
                    "notes": r.notes,
                }
                for r in records
            ]
            output = json.dumps(results, indent=2)
            return ToolResult(
                output=f"Found {len(records)} experiment(s) matching '{arguments.query}':\n{output}",
                metadata={"count": len(records)},
            )
        except Exception as e:
            return ToolResult(output=f"Memory recall failed: {e}", is_error=True)

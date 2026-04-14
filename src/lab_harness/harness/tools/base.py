"""Tool abstractions inspired by OpenHarness BaseTool pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel


@dataclass
class ToolContext:
    cwd: Path = field(default_factory=Path.cwd)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    name: str
    description: str
    input_model: type[BaseModel]

    @abstractmethod
    async def execute(self, arguments: BaseModel, context: ToolContext) -> ToolResult: ...

    def is_read_only(self, arguments: BaseModel) -> bool:
        return True

    def to_api_schema(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def to_api_schema(self) -> list[dict]:
        return [t.to_api_schema() for t in self._tools.values()]


def create_default_registry() -> ToolRegistry:
    """Create registry with all lab tools registered."""
    from lab_harness.harness.tools.analyze_tool import AnalyzeDataTool
    from lab_harness.harness.tools.classify_tool import ClassifyInstrumentsTool
    from lab_harness.harness.tools.generate_skill_tool import GenerateSkillTool
    from lab_harness.harness.tools.health_tool import HealthcheckTool
    from lab_harness.harness.tools.literature_tool import SearchLiteratureTool
    from lab_harness.harness.tools.manual_lookup_tool import ManualLookupTool
    from lab_harness.harness.tools.memory_tool import RecallExperimentsTool
    from lab_harness.harness.tools.propose_tool import ProposeMeasurementTool
    from lab_harness.harness.tools.scan_tool import ScanInstrumentsTool
    from lab_harness.harness.tools.validate_tool import ValidatePlanTool

    registry = ToolRegistry()
    for tool_cls in [
        ScanInstrumentsTool,
        ClassifyInstrumentsTool,
        ProposeMeasurementTool,
        ValidatePlanTool,
        SearchLiteratureTool,
        AnalyzeDataTool,
        RecallExperimentsTool,
        HealthcheckTool,
        GenerateSkillTool,
        ManualLookupTool,
    ]:
        registry.register(tool_cls())
    return registry

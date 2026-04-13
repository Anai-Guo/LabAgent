"""System healthcheck tool."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class HealthInput(BaseModel):
    verbose: bool = False


class HealthcheckTool(BaseTool):
    name = "healthcheck"
    description = "Check system health: PyVISA availability, measurement templates, LLM configuration, and memory store"
    input_model = HealthInput

    async def execute(self, arguments: HealthInput, context: ToolContext) -> ToolResult:
        checks: dict[str, dict] = {}

        # 1. PyVISA
        try:
            import pyvisa

            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()
            checks["pyvisa"] = {
                "ok": True,
                "detail": f"{len(resources)} resource(s) visible",
            }
        except ImportError:
            checks["pyvisa"] = {"ok": False, "detail": "pyvisa not installed"}
        except Exception as e:
            checks["pyvisa"] = {"ok": False, "detail": str(e)}

        # 2. Measurement templates
        templates_dir = Path(__file__).resolve().parents[2] / "planning" / "templates"
        templates = list(templates_dir.glob("*.yaml")) if templates_dir.exists() else []
        checks["templates"] = {
            "ok": len(templates) > 0,
            "detail": f"{len(templates)} template(s) in {templates_dir}",
        }

        # 3. LLM configuration
        try:
            from lab_harness.config import Settings

            settings = Settings.load()
            has_llm = bool(settings.model.api_key or settings.model.base_url)
            checks["llm"] = {
                "ok": has_llm,
                "detail": (
                    f"provider={settings.model.provider}, model={settings.model.model}"
                    if has_llm
                    else "No API key or base_url configured"
                ),
            }
        except Exception as e:
            checks["llm"] = {"ok": False, "detail": str(e)}

        # 4. Memory store
        try:
            from lab_harness.memory.store import MemoryStore

            store = MemoryStore()
            recent = store.get_recent(limit=1)
            checks["memory"] = {
                "ok": True,
                "detail": f"DB at {store.db_path}, {len(recent)} recent record(s)",
            }
        except Exception as e:
            checks["memory"] = {"ok": False, "detail": str(e)}

        all_ok = all(c["ok"] for c in checks.values())
        output = json.dumps(checks, indent=2)
        summary = "All checks passed" if all_ok else "Some checks failed"

        return ToolResult(
            output=f"{summary}\n\n{output}",
            metadata={"all_ok": all_ok, "checks": {k: v["ok"] for k, v in checks.items()}},
        )

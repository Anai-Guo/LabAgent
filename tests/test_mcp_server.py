"""Tests for the MCP server wrappers (harness tools replaced by recording fakes)."""

from __future__ import annotations

import json

import pytest

from lab_harness import server
from lab_harness.harness.tools import (
    analyze_tool,
    classify_tool,
    generate_skill_tool,
    health_tool,
    literature_tool,
    manual_lookup_tool,
    propose_tool,
    scan_tool,
    validate_tool,
)
from lab_harness.harness.tools.base import ToolResult

EXPECTED_TOOLS = {
    "scan_instruments",
    "classify_lab_instruments",
    "propose_measurement",
    "validate_plan",
    "search_literature",
    "analyze_data",
    "generate_skill",
    "manual_lookup",
    "healthcheck",
}


def _record_calls(monkeypatch: pytest.MonkeyPatch, tool_cls: type) -> list:
    """Replace ``tool_cls.execute`` with a fake that records its input model."""
    calls: list = []

    async def fake_execute(self, arguments, context):
        calls.append(arguments)
        return ToolResult(output=f"ran {self.name}", metadata={"ok": True})

    monkeypatch.setattr(tool_cls, "execute", fake_execute)
    return calls


async def test_all_tools_registered():
    tools = await server.mcp.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS
    assert all(t.description for t in tools)


async def test_scan_instruments_returns_output_and_metadata(monkeypatch):
    calls = _record_calls(monkeypatch, scan_tool.ScanInstrumentsTool)
    result = await server.scan_instruments()

    assert result == {"output": "ran scan_instruments", "metadata": {"ok": True}}
    assert len(calls) == 1


async def test_classify_without_inventory_passes_empty_list(monkeypatch):
    calls = _record_calls(monkeypatch, classify_tool.ClassifyInstrumentsTool)
    await server.classify_lab_instruments("IV")

    assert calls[0].measurement_type == "IV"
    assert calls[0].instrument_data == []


async def test_classify_parses_inventory_json(monkeypatch):
    calls = _record_calls(monkeypatch, classify_tool.ClassifyInstrumentsTool)
    inventory = {"instruments": [{"resource": "GPIB0::5::INSTR", "vendor": "KEITHLEY", "model": "2400"}]}
    await server.classify_lab_instruments("AHE", inventory_json=json.dumps(inventory))

    data = calls[0].instrument_data
    assert len(data) == 1
    assert data[0]["resource"] == "GPIB0::5::INSTR"
    assert data[0]["model"] == "2400"


async def test_propose_measurement_forwards_type(monkeypatch):
    calls = _record_calls(monkeypatch, propose_tool.ProposeMeasurementTool)
    await server.propose_measurement("RT")

    assert calls[0].measurement_type == "RT"


async def test_validate_plan_decodes_json(monkeypatch):
    calls = _record_calls(monkeypatch, validate_tool.ValidatePlanTool)
    plan = {"measurement_type": "IV", "max_current": 0.001}
    await server.validate_plan(json.dumps(plan))

    assert calls[0].plan == plan


async def test_validate_plan_rejects_invalid_json(monkeypatch):
    _record_calls(monkeypatch, validate_tool.ValidatePlanTool)
    with pytest.raises(json.JSONDecodeError):
        await server.validate_plan("{not json")


async def test_keyword_arguments_forwarded(monkeypatch):
    lit = _record_calls(monkeypatch, literature_tool.SearchLiteratureTool)
    ana = _record_calls(monkeypatch, analyze_tool.AnalyzeDataTool)
    gen = _record_calls(monkeypatch, generate_skill_tool.GenerateSkillTool)
    man = _record_calls(monkeypatch, manual_lookup_tool.ManualLookupTool)

    await server.search_literature("MR", sample_description="NiFe film")
    await server.analyze_data("d.csv", "IV", use_ai=True, custom_instructions="fit", interpret=True)
    await server.generate_skill("FMR", sample_description="YIG")
    await server.manual_lookup("Thorlabs", "PM100D", interface_or_topic="SCPI", search_web=False)

    assert (lit[0].measurement_type, lit[0].sample_description) == ("MR", "NiFe film")
    assert (ana[0].data_path, ana[0].use_ai, ana[0].custom_instructions, ana[0].interpret) == (
        "d.csv",
        True,
        "fit",
        True,
    )
    assert (gen[0].measurement_type, gen[0].sample_description) == ("FMR", "YIG")
    assert (man[0].make, man[0].model, man[0].interface_or_topic, man[0].search_web) == (
        "Thorlabs",
        "PM100D",
        "SCPI",
        False,
    )


async def test_healthcheck_wrapper(monkeypatch):
    calls = _record_calls(monkeypatch, health_tool.HealthcheckTool)
    result = await server.healthcheck()

    assert result["output"] == "ran healthcheck"
    assert len(calls) == 1


def test_run_server_starts_fastmcp(monkeypatch):
    started: list[bool] = []
    monkeypatch.setattr(server.mcp, "run", lambda: started.append(True))
    server.run_server()

    assert started == [True]

"""Tests for the propose_measurement harness tool."""

from __future__ import annotations

import json

from lab_harness.harness.tools.base import ToolContext, create_default_registry
from lab_harness.harness.tools.propose_tool import ProposeInput, ProposeMeasurementTool
from lab_harness.models.safety import Decision, ValidationResult
from lab_harness.planning import boundary_checker, plan_builder


def _payload(output: str) -> dict:
    """Parse the JSON body that follows the tool's one-line summary."""
    return json.loads(output.split("\n\n", 1)[1])


async def test_propose_default_template_allows():
    result = await ProposeMeasurementTool().execute(ProposeInput(measurement_type="RT"), ToolContext())

    assert not result.is_error
    assert result.metadata["decision"] == "allow"
    assert result.metadata["total_points"] > 0
    assert result.output.split("\n", 1)[0] == f"Plan for RT: {result.metadata['total_points']} points, decision=allow"
    body = _payload(result.output)
    assert set(body) == {"plan", "validation"}
    assert body["plan"]["measurement_type"] == "RT"
    assert set(body["validation"]) == {"decision", "violations", "warnings", "ai_advice"}
    assert body["validation"]["violations"] == []


async def test_propose_unsafe_override_blocks_and_reports_violation():
    args = ProposeInput(measurement_type="AHE", overrides={"max_current_a": 100.0})
    result = await ProposeMeasurementTool().execute(args, ToolContext())

    assert not result.is_error
    assert result.metadata["decision"] == "block"
    assert "violation(s)" in result.output.split("\n", 1)[0]
    body = _payload(result.output)
    assert body["plan"]["max_current_a"] == 100.0
    current = [v for v in body["validation"]["violations"] if v["parameter"] == "max_current_a"]
    assert len(current) == 1
    assert current[0]["requested"] == 100.0
    assert set(current[0]) == {"parameter", "limit", "requested", "message"}


async def test_propose_unknown_measurement_type_returns_error():
    args = ProposeInput(measurement_type="NOT_A_REAL_MEASUREMENT")
    result = await ProposeMeasurementTool().execute(args, ToolContext())

    assert result.is_error
    assert result.output.startswith("Plan proposal failed:")
    assert result.metadata == {}


async def test_propose_forwards_sample_description_and_counts_warnings(monkeypatch):
    real_build = plan_builder.build_plan_from_template
    seen: dict = {}

    def fake_build(measurement_type, overrides=None, sample_description=""):
        seen["build"] = (measurement_type, overrides, sample_description)
        return real_build(measurement_type, overrides=overrides)

    def fake_check(plan, sample_description=""):
        seen["check"] = sample_description
        return ValidationResult(
            decision=Decision.REQUIRE_CONFIRM,
            warnings=["field near limit", "long sweep"],
            ai_advice="ramp slowly",
        )

    monkeypatch.setattr(plan_builder, "build_plan_from_template", fake_build)
    monkeypatch.setattr(boundary_checker, "check_boundaries", fake_check)

    args = ProposeInput(measurement_type="AHE", overrides={"name": "custom"}, sample_description="10nm Pt film")
    result = await ProposeMeasurementTool().execute(args, ToolContext())

    assert not result.is_error
    assert seen == {"build": ("AHE", {"name": "custom"}, "10nm Pt film"), "check": "10nm Pt film"}
    assert result.metadata["decision"] == "require_confirm"
    assert result.output.split("\n", 1)[0].endswith("decision=require_confirm, 2 warning(s)")
    body = _payload(result.output)
    assert body["plan"]["name"] == "custom"
    assert body["validation"]["warnings"] == ["field near limit", "long sweep"]
    assert body["validation"]["ai_advice"] == "ramp slowly"


def test_propose_tool_is_read_only_and_registered():
    tool = ProposeMeasurementTool()

    assert tool.is_read_only(ProposeInput(measurement_type="AHE")) is True
    assert create_default_registry().get("propose_measurement") is not None
    params = tool.to_api_schema()["function"]["parameters"]
    assert params["required"] == ["measurement_type"]

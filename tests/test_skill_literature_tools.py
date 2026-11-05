"""Tests for the generate_skill and search_literature harness tools."""

from __future__ import annotations

import json

from lab_harness.harness.tools.base import ToolContext, create_default_registry
from lab_harness.harness.tools.generate_skill_tool import GenerateSkillInput, GenerateSkillTool
from lab_harness.harness.tools.literature_tool import LiteratureInput, SearchLiteratureTool
from lab_harness.literature import paper_pilot_client
from lab_harness.literature.paper_pilot_client import LiteratureContext
from lab_harness.skills import generator


def _payload(output: str) -> dict:
    """Parse the JSON body that follows the tool's one-line summary."""
    return json.loads(output.split("\n\n", 1)[1])


async def test_generate_skill_saves_and_reports_path(monkeypatch, tmp_path):
    seen: dict = {}

    def fake_generate(measurement_type, sample_description=""):
        seen["generate"] = (measurement_type, sample_description)
        return "---\nname: rt\n---\nStep 1"

    def fake_save(measurement_type, content):
        seen["save"] = (measurement_type, content)
        return tmp_path / f"{measurement_type.lower()}.md"

    monkeypatch.setattr(generator, "generate_skill", fake_generate)
    monkeypatch.setattr(generator, "save_skill", fake_save)

    args = GenerateSkillInput(measurement_type="RT", sample_description="Pt film")
    result = await GenerateSkillTool().execute(args, ToolContext())

    assert not result.is_error
    assert seen["generate"] == ("RT", "Pt film")
    assert seen["save"] == ("RT", "---\nname: rt\n---\nStep 1")
    expected_path = str(tmp_path / "rt.md")
    assert result.metadata == {"skill_path": expected_path}
    assert result.output.split("\n", 1)[0] == "Generated skill for RT"
    assert _payload(result.output) == {
        "measurement_type": "RT",
        "skill_path": expected_path,
        "content": "---\nname: rt\n---\nStep 1",
    }


async def test_generate_skill_failure_is_reported_as_error(monkeypatch):
    def boom(measurement_type, sample_description=""):
        raise RuntimeError("no LLM configured")

    monkeypatch.setattr(generator, "generate_skill", boom)

    result = await GenerateSkillTool().execute(GenerateSkillInput(measurement_type="RT"), ToolContext())

    assert result.is_error
    assert result.output == "Skill generation failed: no LLM configured"


def test_generate_skill_is_not_read_only_and_registered():
    tool = GenerateSkillTool()
    assert tool.is_read_only(GenerateSkillInput(measurement_type="RT")) is False
    assert isinstance(create_default_registry().get("generate_skill"), GenerateSkillTool)


async def test_search_literature_summarises_results(monkeypatch):
    seen: dict = {}

    async def fake_search(self, measurement_type, sample_description=""):
        seen["args"] = (measurement_type, sample_description)
        return LiteratureContext(
            measurement_type=measurement_type,
            suggested_parameters={"max_current_a": 1e-3, "temperature_k": 300},
            evidence_chunks=["Use 1 mA excitation."],
            source_papers=[{"title": "Paper A"}],
        )

    monkeypatch.setattr(paper_pilot_client.PaperPilotClient, "search_for_protocol", fake_search)

    args = LiteratureInput(measurement_type="AHE", sample_description="CoFeB")
    result = await SearchLiteratureTool().execute(args, ToolContext())

    assert not result.is_error
    assert seen["args"] == ("AHE", "CoFeB")
    assert result.metadata == {"papers": 1, "parameters": 2}
    assert result.output.split("\n", 1)[0] == "Literature search for AHE: 1 paper(s), 2 suggested parameter(s)"
    body = _payload(result.output)
    assert body["measurement_type"] == "AHE"
    assert body["suggested_parameters"] == {"max_current_a": 1e-3, "temperature_k": 300}
    assert body["evidence_chunks"] == ["Use 1 mA excitation."]
    assert body["source_papers"] == [{"title": "Paper A"}]


async def test_search_literature_empty_context(monkeypatch):
    async def fake_search(self, measurement_type, sample_description=""):
        return LiteratureContext(measurement_type=measurement_type)

    monkeypatch.setattr(paper_pilot_client.PaperPilotClient, "search_for_protocol", fake_search)

    result = await SearchLiteratureTool().execute(LiteratureInput(measurement_type="RT"), ToolContext())

    assert not result.is_error
    assert result.metadata == {"papers": 0, "parameters": 0}
    assert "0 paper(s), 0 suggested parameter(s)" in result.output


async def test_search_literature_failure_is_reported_as_error(monkeypatch):
    async def boom(self, measurement_type, sample_description=""):
        raise ConnectionError("paper-pilot unreachable")

    monkeypatch.setattr(paper_pilot_client.PaperPilotClient, "search_for_protocol", boom)

    result = await SearchLiteratureTool().execute(LiteratureInput(measurement_type="RT"), ToolContext())

    assert result.is_error
    assert result.output == "Literature search failed: paper-pilot unreachable"
    assert SearchLiteratureTool().is_read_only(LiteratureInput(measurement_type="RT")) is True

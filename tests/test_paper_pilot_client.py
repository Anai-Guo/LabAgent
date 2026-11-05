"""Tests for the paper-pilot literature client: response parsing, LLM fallback and dispatch."""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from lab_harness.literature.paper_pilot_client import LiteratureContext, PaperPilotClient

PAYLOAD = {
    "suggested_parameters": {"current_a": "1 mA"},
    "evidence_chunks": ["Typical AHE studies bias the Hall bar at 1 mA."],
    "instruments": ["sourcemeter: Keithley 2400"],
}


@pytest.mark.parametrize(
    "template",
    ["{}", "```json\n{}\n```", "```\n{}\n```", "```{}```"],
    ids=["bare", "json-fence", "plain-fence", "single-line-fence"],
)
def test_parse_llm_response_accepts_fence_variants(template):
    """A single-line fenced reply used to raise ValueError; every variant must parse."""
    ctx = PaperPilotClient._parse_llm_response("AHE", template.format(json.dumps(PAYLOAD)))

    assert ctx.suggested_parameters == PAYLOAD["suggested_parameters"]
    assert ctx.evidence_chunks == PAYLOAD["evidence_chunks"]
    assert ctx.source_papers == [{"source": "LLM knowledge", "instruments": PAYLOAD["instruments"]}]


@pytest.mark.parametrize("content", ["Use a four-probe geometry.", "```"], ids=["prose", "bare-fence"])
def test_parse_llm_response_non_json_keeps_raw_text_as_evidence(content):
    ctx = PaperPilotClient._parse_llm_response("IV", content)

    assert ctx.suggested_parameters == {}
    assert ctx.source_papers == []
    assert ctx.evidence_chunks == [content]


def test_parse_llm_response_wraps_scalar_evidence_and_omits_empty_instruments():
    ctx = PaperPilotClient._parse_llm_response("MR", json.dumps({"evidence_chunks": "one line"}))

    assert ctx.evidence_chunks == ["one line"]
    assert ctx.source_papers == []


def test_parse_mcp_result_concatenates_text_blocks_and_truncates():
    parse = PaperPilotClient._parse_mcp_result
    blocks = [MagicMock(text="a" * 400), MagicMock(spec=[]), MagicMock(text="b" * 400)]

    assert parse("RT", MagicMock(content=blocks)).evidence_chunks == ["a" * 400 + "b" * 100]
    assert parse("RT", MagicMock(content=[])).evidence_chunks == []
    assert parse("RT", 42).evidence_chunks == ["42"]


@pytest.fixture
def llm():
    """Stub Settings/LLMRouter so _llm_fallback never touches the network."""
    with patch("lab_harness.config.Settings.load"), patch("lab_harness.llm.router.LLMRouter") as cls:
        router = cls.return_value
        router.acomplete = AsyncMock()
        yield router


def _reply(router: MagicMock, content: str) -> None:
    router.acomplete.return_value = {"choices": [{"message": {"content": content}}]}


def _question(router: MagicMock) -> str:
    return router.acomplete.call_args[0][0][1]["content"]


async def test_llm_fallback_builds_question_and_emits_reference(llm):
    _reply(llm, json.dumps(PAYLOAD))
    emit = AsyncMock()

    ctx = await PaperPilotClient()._llm_fallback("AHE", "100nm NiFe film", emit=emit)

    assert ctx.suggested_parameters == PAYLOAD["suggested_parameters"]
    assert "anomalous Hall effect" in _question(llm)
    assert _question(llm).endswith("Specifically for sample: 100nm NiFe film.")
    emit.assert_awaited_once_with("literature.paper_found", title="LLM knowledge")


async def test_llm_fallback_unknown_type_uses_generic_question(llm):
    _reply(llm, "{}")

    ctx = await PaperPilotClient()._llm_fallback("XYZ", "")

    assert _question(llm) == "What measurement protocol is used for XYZ?"
    assert ctx == LiteratureContext(measurement_type="XYZ")


async def test_llm_fallback_router_error_is_reported_as_evidence(llm):
    llm.acomplete.side_effect = RuntimeError("no credentials")

    ctx = await PaperPilotClient()._llm_fallback("IV", "")

    assert ctx.evidence_chunks == ["LLM fallback error: no credentials"]
    assert ctx.source_papers == []


async def test_search_prefers_mcp_result_and_emits_lifecycle(monkeypatch):
    client = PaperPilotClient()
    found = LiteratureContext(measurement_type="AHE", source_papers=[{"title": "P1"}, {"title": "P2"}])
    monkeypatch.setattr(client, "_try_paper_pilot", AsyncMock(return_value=found))
    fallback = AsyncMock()
    monkeypatch.setattr(client, "_llm_fallback", fallback)
    emit = AsyncMock()

    assert await client.search_for_protocol("ahe", "film", emit=emit) is found

    fallback.assert_not_awaited()
    assert emit.await_args_list == [
        call("literature.start", measurement_type="AHE", sample="film"),
        call("literature.complete", paper_count=2),
    ]


@pytest.mark.parametrize(
    "mcp",
    [AsyncMock(return_value=None), AsyncMock(side_effect=OSError("npx missing"))],
    ids=["unreachable", "raises"],
)
async def test_search_falls_back_to_llm_when_mcp_unavailable(monkeypatch, mcp):
    client = PaperPilotClient()
    monkeypatch.setattr(client, "_try_paper_pilot", mcp)
    fallback_ctx = LiteratureContext(measurement_type="IV")
    monkeypatch.setattr(client, "_llm_fallback", AsyncMock(return_value=fallback_ctx))
    emit = AsyncMock()

    assert await client.search_for_protocol("IV", emit=emit) is fallback_ctx
    emit.assert_awaited_with("literature.complete", paper_count=0)


async def test_try_paper_pilot_returns_none_without_mcp_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "mcp", None)

    assert await PaperPilotClient()._try_paper_pilot("IV", "") is None

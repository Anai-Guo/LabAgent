"""Regression tests: decide_measurement must tolerate every fence shape an LLM may emit."""

from __future__ import annotations

import json

import pytest

from lab_harness import config as config_module
from lab_harness.config import ModelConfig, Settings
from lab_harness.llm import router as router_module
from lab_harness.orchestrator import decider

INSTRUMENTS = [{"vendor": "KEITHLEY", "model": "2400", "resource": "GPIB0::5::INSTR"}]
PAYLOAD = {"measurement_type": "IV_CURVE", "reasoning": "SMU available", "confidence": 0.9}


class _StubRouter:
    """Stands in for LLMRouter and returns a canned reply."""

    reply: str = ""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def complete(self, messages: list[dict[str, str]], tools=None) -> dict:
        return {"choices": [{"message": {"content": _StubRouter.reply}}]}


@pytest.fixture()
def stub_router(monkeypatch: pytest.MonkeyPatch) -> type[_StubRouter]:
    for name in ("LABHARNESS_API_KEY", "LABHARNESS_MODEL", "LABHARNESS_BASE_URL", "LABHARNESS_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        config_module.Settings,
        "load",
        classmethod(lambda cls, config_path=None: Settings(model=ModelConfig(api_key="test-key"))),
    )
    monkeypatch.setattr(router_module, "LLMRouter", _StubRouter)
    _StubRouter.reply = ""
    return _StubRouter


@pytest.mark.parametrize(
    "wrap",
    [
        pytest.param("```json\n{body}\n```", id="multi-line-json-fence"),
        pytest.param("```\n{body}\n```", id="multi-line-bare-fence"),
        pytest.param("```json{body}```", id="single-line-json-fence"),
        pytest.param("```{body}```", id="single-line-bare-fence"),
        pytest.param("```json\n{body}", id="unterminated-fence"),
    ],
)
def test_decide_strips_every_fence_shape(stub_router: type[_StubRouter], wrap: str):
    stub_router.reply = wrap.format(body=json.dumps(PAYLOAD))
    result = decider.decide_measurement("measure IV", "Si", INSTRUMENTS)
    assert result == PAYLOAD


def test_decide_single_line_fence_without_json_falls_back(stub_router: type[_StubRouter]):
    """A single-line fence wrapping garbage must degrade to the rule-based path, not raise."""
    stub_router.reply = "```not json at all```"
    result = decider.decide_measurement("measure IV", "Si", INSTRUMENTS)
    assert result == decider._rule_based_decision("measure IV", "Si", INSTRUMENTS)

"""Tests for the measurement-type decider (AI path with a stubbed router + rule-based fallback)."""

from __future__ import annotations

import json

import pytest

from lab_harness import config as config_module
from lab_harness.config import ModelConfig, Settings
from lab_harness.llm import router as router_module
from lab_harness.orchestrator import decider
from lab_harness.orchestrator.decider import _rule_based_decision, decide_measurement

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LABHARNESS_ENV_VARS = (
    "LABHARNESS_API_KEY",
    "LABHARNESS_MODEL",
    "LABHARNESS_BASE_URL",
    "LABHARNESS_PROVIDER",
    "LABHARNESS_DATA_DIR",
)

INSTRUMENTS = [
    {"vendor": "KEITHLEY", "model": "2400", "resource": "GPIB0::5::INSTR"},
    {"vendor": "LAKESHORE", "model": "425", "resource": "COM3"},
]


class _StubRouter:
    """Stands in for LLMRouter: records the request and returns a canned reply."""

    instances: list[_StubRouter] = []
    reply: str = ""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.messages: list[dict[str, str]] | None = None
        _StubRouter.instances.append(self)

    def complete(self, messages: list[dict[str, str]], tools=None) -> dict:
        self.messages = messages
        return {"choices": [{"message": {"content": _StubRouter.reply}}]}


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove LABHARNESS_* variables so ambient shell config cannot leak in."""
    for name in _LABHARNESS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture()
def stub_router(clean_env: pytest.MonkeyPatch) -> type[_StubRouter]:
    """Give the decider credentials and swap the real LLMRouter for the stub."""
    clean_env.setattr(
        config_module.Settings,
        "load",
        classmethod(lambda cls, config_path=None: Settings(model=ModelConfig(api_key="test-key"))),
    )
    clean_env.setattr(router_module, "LLMRouter", _StubRouter)
    _StubRouter.instances = []
    _StubRouter.reply = ""
    return _StubRouter


def _user_message(router: _StubRouter) -> str:
    assert router.messages is not None
    assert router.messages[0]["role"] == "system"
    assert router.messages[0]["content"] == decider.SYSTEM_DECIDE
    assert router.messages[1]["role"] == "user"
    return router.messages[1]["content"]


# ---------------------------------------------------------------------------
# decide_measurement — AI path
# ---------------------------------------------------------------------------


def test_decide_without_credentials_uses_rules(clean_env: pytest.MonkeyPatch):
    """No api_key and no base_url → rule-based decision, the router is never built."""

    def _explode(*args, **kwargs):
        raise AssertionError("LLMRouter must not be constructed without credentials")

    clean_env.setattr(
        config_module.Settings, "load", classmethod(lambda cls, config_path=None: Settings(model=ModelConfig()))
    )
    clean_env.setattr(router_module, "LLMRouter", _explode)

    decision = decide_measurement("transport", "silicon", INSTRUMENTS)
    assert decision == _rule_based_decision("transport", "silicon", INSTRUMENTS)


def test_decide_parses_json_reply(stub_router: type[_StubRouter]):
    stub_router.reply = json.dumps({"measurement_type": "RT", "reasoning": "phase transition", "confidence": 0.9})

    decision = decide_measurement("superconductivity", "NbN film", INSTRUMENTS)

    assert decision == {"measurement_type": "RT", "reasoning": "phase transition", "confidence": 0.9}
    router = stub_router.instances[0]
    assert router.config.api_key == "test-key"
    user_msg = _user_message(router)
    assert "Direction: superconductivity" in user_msg
    assert "Material: NbN film" in user_msg
    assert "- KEITHLEY 2400" in user_msg
    assert "- LAKESHORE 425" in user_msg
    assert "Literature suggests" not in user_msg


def test_decide_strips_markdown_fences(stub_router: type[_StubRouter]):
    payload = {"measurement_type": "CV", "reasoning": "dielectric", "confidence": 0.8}
    stub_router.reply = f"```json\n{json.dumps(payload)}\n```"

    assert decide_measurement("dielectrics", "HfO2", INSTRUMENTS) == payload


def test_decide_includes_literature_hint(stub_router: type[_StubRouter]):
    stub_router.reply = json.dumps({"measurement_type": "IV", "reasoning": "x", "confidence": 0.5})
    literature = {"suggested_parameters": {"max_current_a": 1e-3, "sweep": "bidirectional"}}

    decide_measurement("transport", "graphene", INSTRUMENTS, literature=literature)

    user_msg = _user_message(stub_router.instances[0])
    assert "Literature suggests:" in user_msg
    assert json.dumps(literature["suggested_parameters"]) in user_msg


def test_decide_ignores_literature_without_parameters(stub_router: type[_StubRouter]):
    stub_router.reply = json.dumps({"measurement_type": "IV", "reasoning": "x", "confidence": 0.5})

    decide_measurement("transport", "graphene", INSTRUMENTS, literature={"papers": ["a", "b"]})

    assert "Literature suggests" not in _user_message(stub_router.instances[0])


def test_decide_tolerates_instruments_missing_fields(stub_router: type[_StubRouter]):
    stub_router.reply = json.dumps({"measurement_type": "IV", "reasoning": "x", "confidence": 0.5})

    decide_measurement("transport", "sample", [{"resource": "GPIB0::7::INSTR"}])

    assert "- ? ?" in _user_message(stub_router.instances[0])


def test_decide_invalid_json_falls_back_to_rules(stub_router: type[_StubRouter]):
    stub_router.reply = "Sorry, I cannot decide."

    decision = decide_measurement("transport", "silicon", INSTRUMENTS)

    assert decision == _rule_based_decision("transport", "silicon", INSTRUMENTS)


# ---------------------------------------------------------------------------
# _rule_based_decision — remaining branches
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("models", "direction", "material", "expected"),
    [
        (["SP-200"], "electrochemistry", "LiFePO4", "CYCLIC_VOLTAMMETRY"),
        (["CLARIOstar"], "assay", "protein", "UV_VIS"),
        (["USB2000"], "optics", "dye", "UV_VIS"),
        (["PM100D"], "photonics", "perovskite", "PHOTOCURRENT"),
        (["Orion Star"], "titration", "buffer", "PH_CALIBRATION"),
        (["XS205"], "gravimetry", "powder", "CUSTOM_SWEEP"),
        (["Alicat MC-500"], "sensing", "SnO2", "GAS_SENSOR"),
        (["6221", "425"], "spin-orbit torque", "Pt/Co", "SOT"),
        (["6221", "425"], "transport", "Pt/Co", "HALL"),
        (["335"], "transport", "VO2", "RT"),
        (["E4980A"], "dielectrics", "SiO2", "CV"),
        (["2400"], "transport", "Si", "IV"),
    ],
)
def test_rule_based_decision_branches(models: list[str], direction: str, material: str, expected: str):
    instruments = [{"vendor": "ACME", "model": m} for m in models]
    decision = _rule_based_decision(direction, material, instruments)
    assert decision["measurement_type"] == expected
    assert decision["reasoning"]
    assert 0.0 < decision["confidence"] <= 1.0


def test_rule_based_potentiostat_wins_over_gaussmeter():
    """Electrochemistry hardware takes precedence over condensed-matter specialties."""
    instruments = [{"vendor": "BIOLOGIC", "model": "VSP"}, {"vendor": "LAKESHORE", "model": "425"}]
    decision = _rule_based_decision("magnetic", "ferromagnet", instruments)
    assert decision["measurement_type"] == "CYCLIC_VOLTAMMETRY"


def test_rule_based_gaussmeter_wins_over_temperature():
    instruments = [{"vendor": "LAKESHORE", "model": "425"}, {"vendor": "LAKESHORE", "model": "335"}]
    decision = _rule_based_decision("transport", "Si", instruments)
    assert decision["measurement_type"] == "HALL"


def test_rule_based_tolerates_instruments_missing_model():
    decision = _rule_based_decision("transport", "Si", [{"vendor": "ACME"}, {}])
    assert decision["measurement_type"] == "IV"

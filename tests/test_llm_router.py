"""Tests for the litellm-backed LLMRouter (no network calls)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import litellm
import pytest

from lab_harness.config import ModelConfig
from lab_harness.llm.router import LLMRouter


def _response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(model_dump=lambda: dict(payload))


@pytest.fixture
def isolated_litellm(monkeypatch):
    """Keep litellm globals and provider env vars from leaking between tests."""
    monkeypatch.setattr(litellm, "api_key", None, raising=False)
    monkeypatch.setattr(litellm, "api_base", None, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield


def test_init_without_key_leaves_globals_untouched(isolated_litellm):
    LLMRouter(config=ModelConfig(provider="anthropic", api_key=None, base_url=None))
    assert litellm.api_key is None
    assert litellm.api_base is None
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_init_with_key_sets_litellm_and_provider_env(isolated_litellm):
    LLMRouter(config=ModelConfig(provider="openai", model="gpt-4o", api_key="test-key"))
    assert litellm.api_key == "test-key"
    assert os.environ["OPENAI_API_KEY"] == "test-key"
    assert litellm.api_base is None


def test_init_with_base_url_sets_api_base(isolated_litellm):
    LLMRouter(config=ModelConfig(provider="ollama", model="llama3", base_url="http://localhost:11434"))
    assert litellm.api_base == "http://localhost:11434"
    assert litellm.api_key is None


@pytest.mark.parametrize(
    "provider, model, base_url, expected",
    [
        ("ollama", "llama3", "http://localhost:11434", "ollama/llama3"),
        ("ollama", "llama3", None, "llama3"),
        ("openai", "gpt-4o", "http://localhost:8000/v1", "gpt-4o"),
        ("anthropic", "claude-x", None, "claude-x"),
    ],
)
def test_model_id_prefixes_ollama_only_with_base_url(isolated_litellm, provider, model, base_url, expected):
    router = LLMRouter(config=ModelConfig(provider=provider, model=model, base_url=base_url))
    assert router.model_id == expected


def test_complete_forwards_config_and_omits_tools_when_none(isolated_litellm, monkeypatch):
    captured: dict = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _response({"choices": [{"message": {"content": "hi"}}]})

    monkeypatch.setattr(litellm, "completion", fake_completion)
    router = LLMRouter(config=ModelConfig(provider="openai", model="gpt-4o", temperature=0.3, max_tokens=99))
    messages = [{"role": "user", "content": "hello"}]

    result = router.complete(messages)

    assert result == {"choices": [{"message": {"content": "hi"}}]}
    assert captured == {"model": "gpt-4o", "messages": messages, "temperature": 0.3, "max_tokens": 99}


def test_complete_passes_tools_when_given(isolated_litellm, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(litellm, "completion", lambda **kw: (captured.update(kw), _response({}))[1])
    router = LLMRouter(config=ModelConfig(provider="openai", model="gpt-4o"))
    tools = [{"type": "function", "function": {"name": "noop"}}]

    router.complete([{"role": "user", "content": "x"}], tools=tools)

    assert captured["tools"] == tools


async def test_acomplete_awaits_litellm_and_dumps_response(isolated_litellm, monkeypatch):
    captured: dict = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _response({"ok": True})

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    router = LLMRouter(config=ModelConfig(provider="ollama", model="llama3", base_url="http://localhost:11434"))
    tools = [{"type": "function", "function": {"name": "noop"}}]

    result = await router.acomplete([{"role": "user", "content": "x"}], tools=tools)

    assert result == {"ok": True}
    assert captured["model"] == "ollama/llama3"
    assert captured["tools"] == tools

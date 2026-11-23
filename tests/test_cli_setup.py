"""Tests for the interactive ``labharness setup`` wizard (input and LLM stubbed)."""

from __future__ import annotations

import argparse
import builtins

import pytest

from lab_harness import cli
from lab_harness.config import Settings
from lab_harness.llm import router as router_mod


def _feed(monkeypatch, answers):
    """Answer successive ``input()`` prompts from *answers*, recording the prompts."""
    it = iter(answers)
    prompts = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        return next(it)

    monkeypatch.setattr(builtins, "input", fake_input)
    return prompts


def _stub_router(monkeypatch, reply="hello", error=None):
    """Replace the connection test's Settings/LLMRouter so no network call is made."""
    seen = {}

    class FakeRouter:
        def __init__(self, config):
            seen["config"] = config

        def complete(self, messages):
            seen["messages"] = messages
            if error is not None:
                raise error
            return {"choices": [{"message": {"content": reply}}]}

    monkeypatch.setattr(Settings, "load", classmethod(lambda cls, config_path=None: Settings()))
    monkeypatch.setattr(router_mod, "LLMRouter", FakeRouter)
    return seen


def _read_env(tmp_path):
    return (tmp_path / ".env").read_text(encoding="utf-8").splitlines()


def test_setup_skip_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _feed(monkeypatch, ["5"])
    cli.cmd_setup(argparse.Namespace(), None)
    assert not (tmp_path / ".env").exists()
    assert "Setup skipped" in capsys.readouterr().out


def test_setup_anthropic_with_key_writes_env_and_tests_connection(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    prompts = _feed(monkeypatch, ["1", "test-key-123"])
    seen = _stub_router(monkeypatch, reply="hello")
    cli.cmd_setup(argparse.Namespace(), None)

    assert _read_env(tmp_path) == [
        "LABHARNESS_PROVIDER=anthropic",
        "LABHARNESS_MODEL=claude-sonnet-4-20250514",
        "LABHARNESS_API_KEY=test-key-123",
    ]
    assert "ANTHROPIC API key" in prompts[1]
    assert seen["messages"][0]["role"] == "user"
    out = capsys.readouterr().out
    assert "Success! Model responded: hello" in out
    assert "Setup complete!" in out


@pytest.mark.parametrize(
    ("choice", "provider", "model"),
    [("2", "openai", "gpt-4o"), ("4", "deepseek", "deepseek/deepseek-chat")],
)
def test_setup_cloud_provider_without_key_omits_key_line(tmp_path, monkeypatch, choice, provider, model):
    monkeypatch.chdir(tmp_path)
    _feed(monkeypatch, [choice, ""])
    _stub_router(monkeypatch)
    cli.cmd_setup(argparse.Namespace(), None)
    assert _read_env(tmp_path) == [f"LABHARNESS_PROVIDER={provider}", f"LABHARNESS_MODEL={model}"]


def test_setup_ollama_uses_defaults_and_skips_key_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prompts = _feed(monkeypatch, ["3", "", ""])
    _stub_router(monkeypatch)
    cli.cmd_setup(argparse.Namespace(), None)

    assert _read_env(tmp_path) == [
        "LABHARNESS_PROVIDER=ollama",
        "LABHARNESS_MODEL=qwen3:32b",
        "LABHARNESS_BASE_URL=http://localhost:11434",
    ]
    assert len(prompts) == 3
    assert not any("API key" in p for p in prompts)


def test_setup_ollama_custom_model_and_url(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _feed(monkeypatch, ["3", "llama3:8b", "http://gpu-box:11434"])
    _stub_router(monkeypatch)
    cli.cmd_setup(argparse.Namespace(), None)
    env = _read_env(tmp_path)
    assert "LABHARNESS_MODEL=llama3:8b" in env
    assert "LABHARNESS_BASE_URL=http://gpu-box:11434" in env


def test_setup_unknown_choice_falls_back_to_anthropic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _feed(monkeypatch, ["9", ""])
    _stub_router(monkeypatch)
    cli.cmd_setup(argparse.Namespace(), None)
    assert _read_env(tmp_path)[0] == "LABHARNESS_PROVIDER=anthropic"


def test_setup_reports_failed_connection_test(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _feed(monkeypatch, ["1", ""])
    _stub_router(monkeypatch, error=RuntimeError("no network"))
    cli.cmd_setup(argparse.Namespace(), None)

    out = capsys.readouterr().out
    assert "Connection test failed: no network" in out
    assert "Setup complete!" in out
    assert (tmp_path / ".env").exists()

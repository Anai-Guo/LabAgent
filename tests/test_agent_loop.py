"""Tests for the conversational LabAgent wrapper (lab_harness.agent.loop)."""

from __future__ import annotations

import pytest

import lab_harness.agent.loop as loop_mod
from lab_harness.agent.loop import LabAgent
from lab_harness.config import ModelConfig, Settings
from lab_harness.harness.engine.events import (
    ErrorEvent,
    StatusUpdate,
    TextDelta,
    ToolComplete,
    ToolStart,
    TurnComplete,
)


class _BrokenStore:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("no memory backend")


@pytest.fixture
def settings() -> Settings:
    return Settings(model=ModelConfig(provider="openai", model="gpt-test"))


@pytest.fixture
def agent(settings, monkeypatch) -> LabAgent:
    # Keep tests hermetic: memory store construction fails, so no db file is created.
    monkeypatch.setattr("lab_harness.memory.store.MemoryStore", _BrokenStore)
    return LabAgent(settings=settings)


def _fake_query(events, captured=None):
    async def run_query(context, messages):
        if captured is not None:
            captured.append((context, messages))
        for event in events:
            yield event

    return run_query


def test_init_wires_registry_and_model_config(agent, settings):
    assert agent.context.tool_registry is agent.registry
    assert agent.context.model_config is settings.model


def test_init_swallows_memory_store_failure(agent):
    assert agent.context.memory_store is None


def test_init_attaches_memory_store_when_available(settings, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    agent = LabAgent(settings=settings)
    assert agent.context.memory_store is not None
    assert (tmp_path / "data" / "memory.db").exists()


async def test_run_conversation_joins_text_deltas_and_final_text(agent, monkeypatch):
    captured = []
    events = [TextDelta("Hello"), TextDelta(", "), TurnComplete(text="world")]
    monkeypatch.setattr(loop_mod, "run_query", _fake_query(events, captured))

    result = await agent.run_conversation("hi there")

    assert result == "Hello, world"
    context, messages = captured[0]
    assert context is agent.context
    assert messages == [{"role": "user", "content": "hi there"}]


async def test_run_conversation_skips_empty_turn_complete(agent, monkeypatch):
    events = [TextDelta("only delta"), TurnComplete(text="")]
    monkeypatch.setattr(loop_mod, "run_query", _fake_query(events))

    assert await agent.run_conversation("q") == "only delta"


async def test_run_conversation_formats_errors(agent, monkeypatch):
    events = [TextDelta("partial "), ErrorEvent(message="rate limited")]
    monkeypatch.setattr(loop_mod, "run_query", _fake_query(events))

    assert await agent.run_conversation("q") == "partial Error: rate limited"


async def test_run_conversation_ignores_non_text_events(agent, monkeypatch):
    events = [
        StatusUpdate(message="thinking"),
        ToolStart(tool_name="scan", tool_input={}),
        ToolComplete(tool_name="scan", output="GPIB0::24"),
        TurnComplete(text="done"),
    ]
    monkeypatch.setattr(loop_mod, "run_query", _fake_query(events))

    assert await agent.run_conversation("q") == "done"


async def test_run_conversation_with_no_events_returns_empty(agent, monkeypatch):
    monkeypatch.setattr(loop_mod, "run_query", _fake_query([]))

    assert await agent.run_conversation("q") == ""

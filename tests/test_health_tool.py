"""Tests for the healthcheck harness tool.

PyVISA, settings and the memory store are all stubbed so the checks run
without instruments, API keys or writing a database into the working tree.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

import lab_harness.config as config_module
import lab_harness.memory.store as store_module
from lab_harness.config import ModelConfig, Settings
from lab_harness.harness.tools.base import ToolContext
from lab_harness.harness.tools.health_tool import HealthcheckTool, HealthInput
from lab_harness.memory.store import MemoryStore


def _payload(output: str) -> dict:
    """Parse the JSON body that follows the tool's one-line summary."""
    return json.loads(output.split("\n\n", 1)[1])


def _fake_pyvisa(resources=(), error: Exception | None = None) -> types.ModuleType:
    module = types.ModuleType("pyvisa")

    class ResourceManager:
        def __init__(self):
            if error is not None:
                raise error

        def list_resources(self):
            return tuple(resources)

    module.ResourceManager = ResourceManager
    return module


@pytest.fixture
def healthy(monkeypatch, tmp_path):
    """Stub every dependency into a passing state."""
    monkeypatch.setitem(sys.modules, "pyvisa", _fake_pyvisa(["GPIB0::5::INSTR", "GPIB0::12::INSTR"]))
    settings = Settings(model=ModelConfig(provider="openai", model="gpt-test", api_key="dummy"))
    monkeypatch.setattr(config_module.Settings, "load", classmethod(lambda cls, *a, **k: settings))
    monkeypatch.setattr(store_module, "MemoryStore", lambda: MemoryStore(db_path=tmp_path / "memory.db"))
    return monkeypatch


async def _run() -> tuple[str, dict, dict]:
    result = await HealthcheckTool().execute(HealthInput(), ToolContext())
    assert not result.is_error
    return result.output, _payload(result.output), result.metadata


async def test_all_checks_pass(healthy, tmp_path):
    output, body, metadata = await _run()

    assert output.startswith("All checks passed")
    assert metadata == {
        "all_ok": True,
        "checks": {"pyvisa": True, "templates": True, "llm": True, "memory": True},
    }
    assert body["pyvisa"]["detail"] == "2 resource(s) visible"
    assert "template(s) in" in body["templates"]["detail"]
    assert body["llm"]["detail"] == "provider=openai, model=gpt-test"
    assert body["memory"]["detail"].endswith("0 recent record(s)")
    assert str(tmp_path) in body["memory"]["detail"]


async def test_pyvisa_missing_reports_not_installed(healthy):
    healthy.setitem(sys.modules, "pyvisa", None)  # makes `import pyvisa` raise ImportError

    output, body, metadata = await _run()

    assert output.startswith("Some checks failed")
    assert body["pyvisa"] == {"ok": False, "detail": "pyvisa not installed"}
    assert metadata["all_ok"] is False
    assert metadata["checks"]["pyvisa"] is False
    assert metadata["checks"]["memory"] is True


async def test_pyvisa_backend_error_is_reported(healthy):
    healthy.setitem(sys.modules, "pyvisa", _fake_pyvisa(error=OSError("no VISA backend")))

    _, body, _ = await _run()

    assert body["pyvisa"] == {"ok": False, "detail": "no VISA backend"}


async def test_base_url_alone_counts_as_llm_configured(healthy):
    local = Settings(model=ModelConfig(provider="ollama", model="llama3", base_url="http://localhost:11434"))
    healthy.setattr(config_module.Settings, "load", classmethod(lambda cls, *a, **k: local))

    _, body, metadata = await _run()

    assert metadata["checks"]["llm"] is True
    assert body["llm"]["detail"] == "provider=ollama, model=llama3"


async def test_missing_llm_credentials_fail_llm_check(healthy):
    bare = Settings(model=ModelConfig(api_key=None, base_url=None))
    healthy.setattr(config_module.Settings, "load", classmethod(lambda cls, *a, **k: bare))

    output, body, metadata = await _run()

    assert output.startswith("Some checks failed")
    assert body["llm"] == {"ok": False, "detail": "No API key or base_url configured"}
    assert metadata["checks"]["llm"] is False


async def test_settings_load_error_is_reported(healthy):
    def boom(cls, *args, **kwargs):
        raise ValueError("bad config")

    healthy.setattr(config_module.Settings, "load", classmethod(boom))

    _, body, _ = await _run()

    assert body["llm"] == {"ok": False, "detail": "bad config"}


async def test_memory_store_error_is_reported(healthy):
    def broken_store():
        raise RuntimeError("database locked")

    healthy.setattr(store_module, "MemoryStore", broken_store)

    _, body, metadata = await _run()

    assert body["memory"] == {"ok": False, "detail": "database locked"}
    assert metadata["checks"]["memory"] is False
    assert metadata["all_ok"] is False

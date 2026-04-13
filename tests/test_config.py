"""Tests for config module: Settings and ModelConfig."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_harness.config import ModelConfig, Settings

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_default_settings():
    """Settings() uses sensible defaults."""
    s = Settings()
    assert s.server_host == "127.0.0.1"
    assert s.server_port == 8400
    assert s.data_dir == Path("./data")
    assert s.fallback_model is None


def test_model_config_defaults():
    """ModelConfig defaults match expected values."""
    m = ModelConfig()
    assert m.provider == "anthropic"
    assert m.model == "claude-sonnet-4-20250514"
    assert m.api_key is None
    assert m.base_url is None
    assert m.temperature == 0.0
    assert m.max_tokens == 4096


# ---------------------------------------------------------------------------
# Environment overrides via Settings.load()
# ---------------------------------------------------------------------------


def test_env_override(monkeypatch: pytest.MonkeyPatch):
    """LABHARNESS_MODEL env var overrides the default model name."""
    monkeypatch.setenv("LABHARNESS_MODEL", "gpt-4o")
    s = Settings.load()
    assert s.model.model == "gpt-4o"


def test_env_override_provider(monkeypatch: pytest.MonkeyPatch):
    """LABHARNESS_PROVIDER env var overrides the default provider."""
    monkeypatch.setenv("LABHARNESS_PROVIDER", "openai")
    s = Settings.load()
    assert s.model.provider == "openai"


def test_env_override_data_dir(monkeypatch: pytest.MonkeyPatch):
    """LABHARNESS_DATA_DIR env var overrides the data directory."""
    monkeypatch.setenv("LABHARNESS_DATA_DIR", "/tmp/lab_output")
    s = Settings.load()
    assert s.data_dir == Path("/tmp/lab_output")


# ---------------------------------------------------------------------------
# Config file handling
# ---------------------------------------------------------------------------


def test_missing_config():
    """Loading from a non-existent config file returns defaults."""
    s = Settings.load(config_path=Path("/nonexistent/models.yaml"))
    assert s.model.provider == "anthropic"
    assert s.model.model == "claude-sonnet-4-20250514"


def test_load_no_args():
    """Settings.load() with no arguments returns valid defaults."""
    s = Settings.load()
    assert isinstance(s.model, ModelConfig)
    assert isinstance(s.data_dir, Path)

"""Tests for config module: Settings and ModelConfig."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from lab_harness import config as config_module
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


# ---------------------------------------------------------------------------
# Config file contents and precedence
# ---------------------------------------------------------------------------

_LABHARNESS_ENV_VARS = (
    "LABHARNESS_API_KEY",
    "LABHARNESS_MODEL",
    "LABHARNESS_BASE_URL",
    "LABHARNESS_PROVIDER",
    "LABHARNESS_DATA_DIR",
)


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove LABHARNESS_* variables so ambient shell config cannot leak in."""
    for name in _LABHARNESS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_config_file_model_section(clean_env: pytest.MonkeyPatch, tmp_path: Path):
    """The ``model:`` section of the config file populates ModelConfig."""
    path = _write_config(
        tmp_path,
        "model:\n"
        "  provider: ollama\n"
        "  model: qwen3:32b\n"
        "  base_url: http://localhost:11434\n"
        "  temperature: 0.2\n"
        "  max_tokens: 1024\n",
    )
    s = Settings.load(config_path=path)
    assert s.model.provider == "ollama"
    assert s.model.model == "qwen3:32b"
    assert s.model.base_url == "http://localhost:11434"
    assert s.model.temperature == 0.2
    assert s.model.max_tokens == 1024
    assert s.model.api_key is None


def test_config_file_partial_keeps_defaults(clean_env: pytest.MonkeyPatch, tmp_path: Path):
    """Fields missing from the config file fall back to ModelConfig defaults."""
    path = _write_config(tmp_path, "model:\n  model: gpt-4o\n")
    s = Settings.load(config_path=path)
    assert s.model.model == "gpt-4o"
    assert s.model.provider == ModelConfig().provider
    assert s.model.max_tokens == ModelConfig().max_tokens


@pytest.mark.parametrize("text", ["", "# only a comment\n", "other_section:\n  key: value\n"])
def test_config_file_without_model_section(clean_env: pytest.MonkeyPatch, tmp_path: Path, text: str):
    """Empty files or files without ``model:`` yield the default ModelConfig."""
    path = _write_config(tmp_path, text)
    s = Settings.load(config_path=path)
    assert s.model == ModelConfig()


def test_env_overrides_config_file(clean_env: pytest.MonkeyPatch, tmp_path: Path):
    """Environment variables take precedence over values from the config file."""
    path = _write_config(
        tmp_path,
        "model:\n  provider: anthropic\n  model: claude-sonnet-4-20250514\n  base_url: http://file-host:1\n",
    )
    clean_env.setenv("LABHARNESS_PROVIDER", "openai")
    clean_env.setenv("LABHARNESS_MODEL", "gpt-4o")
    clean_env.setenv("LABHARNESS_BASE_URL", "http://env-host:2")
    s = Settings.load(config_path=path)
    assert s.model.provider == "openai"
    assert s.model.model == "gpt-4o"
    assert s.model.base_url == "http://env-host:2"


def test_env_override_api_key_and_base_url(clean_env: pytest.MonkeyPatch):
    """LABHARNESS_API_KEY and LABHARNESS_BASE_URL populate the model config."""
    clean_env.setenv("LABHARNESS_API_KEY", "test-key-not-real")
    clean_env.setenv("LABHARNESS_BASE_URL", "http://localhost:8000/v1")
    s = Settings.load()
    assert s.model.api_key == "test-key-not-real"
    assert s.model.base_url == "http://localhost:8000/v1"


def test_empty_env_vars_are_ignored(clean_env: pytest.MonkeyPatch, tmp_path: Path):
    """Empty LABHARNESS_* values do not clobber values from the config file."""
    path = _write_config(tmp_path, "model:\n  model: gpt-4o\n")
    clean_env.setenv("LABHARNESS_MODEL", "")
    clean_env.setenv("LABHARNESS_API_KEY", "")
    s = Settings.load(config_path=path)
    assert s.model.model == "gpt-4o"
    assert s.model.api_key is None


def test_data_dir_default_without_env(clean_env: pytest.MonkeyPatch):
    """Without LABHARNESS_DATA_DIR the data directory defaults to ./data."""
    s = Settings.load()
    assert s.data_dir == Path("./data")


def test_config_file_read_as_utf8_regardless_of_locale(clean_env: pytest.MonkeyPatch, tmp_path: Path):
    """A UTF-8 models.yaml with non-ASCII text loads intact even under a non-UTF-8 locale.

    Windows lab PCs typically default to a legacy code page (e.g. cp1252), so the
    file must be opened with an explicit encoding rather than the locale default.
    """
    path = _write_config(tmp_path, "# temperature in °C\nmodel:\n  provider: ollama\n  model: qwen3-μ\n")

    def legacy_locale_open(file, mode="r", *args, encoding=None, **kwargs):
        if "b" not in mode and encoding is None:
            encoding = "cp1252"
        return builtins.open(file, mode, *args, encoding=encoding, **kwargs)

    clean_env.setattr(config_module, "open", legacy_locale_open, raising=False)
    s = Settings.load(config_path=path)
    assert s.model.provider == "ollama"
    assert s.model.model == "qwen3-μ"

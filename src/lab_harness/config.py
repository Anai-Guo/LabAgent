"""Configuration management for Lab Harness."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ModelConfig:
    """LLM model configuration."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None
    base_url: str | None = None  # For local models (Ollama, vLLM)
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass(frozen=True)
class Settings:
    """Application settings, loaded from environment and config files."""

    # Model routing
    model: ModelConfig = field(default_factory=ModelConfig)
    fallback_model: str | None = None

    # Data output
    data_dir: Path = field(default_factory=lambda: Path("./data"))

    # MCP server
    server_host: str = "127.0.0.1"
    server_port: int = 8400

    @classmethod
    def load(cls, config_path: Path | None = None) -> Settings:
        """Load settings from models.yaml + environment variables."""
        model_kwargs: dict = {}

        # Load from config file
        if config_path and config_path.exists():
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}
            if "model" in raw:
                model_kwargs = raw["model"]

        # Environment overrides
        if api_key := os.getenv("LABHARNESS_API_KEY"):
            model_kwargs["api_key"] = api_key
        if model := os.getenv("LABHARNESS_MODEL"):
            model_kwargs["model"] = model
        if base_url := os.getenv("LABHARNESS_BASE_URL"):
            model_kwargs["base_url"] = base_url
        if provider := os.getenv("LABHARNESS_PROVIDER"):
            model_kwargs["provider"] = provider

        data_dir = Path(os.getenv("LABHARNESS_DATA_DIR", "./data"))

        return cls(
            model=ModelConfig(**model_kwargs) if model_kwargs else ModelConfig(),
            data_dir=data_dir,
        )

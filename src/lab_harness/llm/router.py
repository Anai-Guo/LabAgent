"""Unified LLM router using litellm.

Supports cloud models (Claude, GPT, Gemini) and local models (Ollama, vLLM)
through a single interface.
"""

from __future__ import annotations

from dataclasses import dataclass

import litellm

from lab_harness.config import ModelConfig


@dataclass
class LLMRouter:
    """Routes LLM calls through litellm's unified API."""

    config: ModelConfig

    def __post_init__(self) -> None:
        if self.config.api_key:
            provider_key = f"{self.config.provider.upper()}_API_KEY"
            litellm.api_key = self.config.api_key
            import os
            os.environ[provider_key] = self.config.api_key

        if self.config.base_url:
            litellm.api_base = self.config.base_url

    @property
    def model_id(self) -> str:
        """Full model identifier for litellm."""
        if self.config.base_url and self.config.provider == "ollama":
            return f"ollama/{self.config.model}"
        return self.config.model

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> dict:
        """Send a completion request to the configured model.

        Args:
            messages: Chat messages in OpenAI format.
            tools: Optional tool definitions for function calling.

        Returns:
            The model's response as a dict.
        """
        kwargs: dict = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = litellm.completion(**kwargs)
        return response.model_dump()

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
    ) -> dict:
        """Async version of complete."""
        kwargs: dict = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = await litellm.acompletion(**kwargs)
        return response.model_dump()

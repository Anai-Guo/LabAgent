"""Tests for the LLM-backed measurement parameter optimizer."""

import json
from unittest.mock import MagicMock, patch

from lab_harness.planning.parameter_optimizer import SYSTEM_OPTIMIZE, optimize_parameters

SUGGESTION = {
    "suggested_overrides": {"max_current_a": 0.0001, "num_averages": 5},
    "reasoning": "Keep the bias low to avoid Joule heating.",
}


def _make_mock_router(response_text: str):
    router = MagicMock()
    router.complete.return_value = {
        "choices": [{"message": {"content": response_text}}],
    }
    return router


def test_optimize_returns_empty_without_llm_credentials():
    """No api_key and no base_url means no LLM, so no suggestion (and no crash)."""
    with patch("lab_harness.config.Settings.load") as mock_settings:
        mock_settings.return_value.model.api_key = ""
        mock_settings.return_value.model.base_url = ""
        assert optimize_parameters("IV") == {}


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_optimize_parses_plain_json(mock_router_cls, mock_settings):
    """A bare JSON reply is returned as a parsed dict."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    mock_router_cls.return_value = _make_mock_router(json.dumps(SUGGESTION))

    assert optimize_parameters("IV") == SUGGESTION


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_optimize_strips_markdown_fences(mock_router_cls, mock_settings):
    """Models often wrap JSON in ```json fences; those must not break parsing."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    fenced = f"```json\n{json.dumps(SUGGESTION)}\n```"
    mock_router_cls.return_value = _make_mock_router(fenced)

    assert optimize_parameters("IV") == SUGGESTION


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_optimize_falls_back_to_reasoning_on_unparseable_reply(mock_router_cls, mock_settings):
    """Prose instead of JSON degrades to a reasoning-only dict, never an exception."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    mock_router_cls.return_value = _make_mock_router("Use a smaller step size.")

    assert optimize_parameters("RT") == {"reasoning": "Use a smaller step size."}


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_optimize_puts_context_in_the_user_message(mock_router_cls, mock_settings):
    """Measurement type, sample description and current defaults all reach the model."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    router = _make_mock_router(json.dumps(SUGGESTION))
    mock_router_cls.return_value = router

    optimize_parameters(
        "AHE",
        sample_description="100nm NiFe film",
        current_params={"max_field_oe": 10000.0},
    )

    messages = router.complete.call_args[0][0]
    system_msg = next(m for m in messages if m["role"] == "system")["content"]
    user_msg = next(m for m in messages if m["role"] == "user")["content"]
    assert system_msg == SYSTEM_OPTIMIZE
    assert "Measurement: AHE" in user_msg
    assert "100nm NiFe film" in user_msg
    assert "max_field_oe" in user_msg


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_optimize_omits_optional_context_when_absent(mock_router_cls, mock_settings):
    """Without a sample or current defaults, those prompt sections are left out."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    router = _make_mock_router(json.dumps(SUGGESTION))
    mock_router_cls.return_value = router

    optimize_parameters("CYCLIC_VOLTAMMETRY")

    user_msg = next(m for m in router.complete.call_args[0][0] if m["role"] == "user")["content"]
    assert "Measurement: CYCLIC_VOLTAMMETRY" in user_msg
    assert "Sample:" not in user_msg
    assert "Current defaults:" not in user_msg


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_optimize_handles_single_line_fenced_reply(mock_router_cls, mock_settings):
    """A fenced reply with no newline used to raise ValueError; it must still parse."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    mock_router_cls.return_value = _make_mock_router(f"```{json.dumps(SUGGESTION)}```")

    assert optimize_parameters("IV") == SUGGESTION


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_optimize_bare_fence_reply_degrades_to_reasoning(mock_router_cls, mock_settings):
    """A reply that is only a fence marker falls back to reasoning instead of crashing."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    mock_router_cls.return_value = _make_mock_router("```")

    assert optimize_parameters("IV") == {"reasoning": "```"}

"""Tests for the LLM-backed safety advisor used by the boundary checker."""

from unittest.mock import MagicMock, patch

from lab_harness.planning.safety_advisor import SYSTEM_SAFETY, advise_on_warnings


def _make_mock_router(response_text: str):
    router = MagicMock()
    router.complete.return_value = {
        "choices": [{"message": {"content": response_text}}],
    }
    return router


def test_advise_returns_empty_without_llm_credentials():
    """No api_key and no base_url means no LLM, so no advice (and no router is built)."""
    with (
        patch("lab_harness.config.Settings.load") as mock_settings,
        patch("lab_harness.llm.router.LLMRouter") as mock_router_cls,
    ):
        mock_settings.return_value.model.api_key = ""
        mock_settings.return_value.model.base_url = ""
        assert advise_on_warnings(["Current too high"], "IV") == ""
        mock_router_cls.assert_not_called()


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_advise_works_with_base_url_only(mock_router_cls, mock_settings):
    """A local endpoint (base_url without api_key) is enough to ask for advice."""
    mock_settings.return_value.model.api_key = ""
    mock_settings.return_value.model.base_url = "http://localhost:11434"
    mock_router_cls.return_value = _make_mock_router("Lower the current.")

    assert advise_on_warnings(["Current too high"], "IV") == "Lower the current."


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_advise_strips_whitespace_from_reply(mock_router_cls, mock_settings):
    """Leading/trailing whitespace in the model reply is not passed on."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    mock_router_cls.return_value = _make_mock_router("\n  Keep bias under 1 mA.  \n")

    assert advise_on_warnings(["Current too high"], "IV") == "Keep bias under 1 mA."


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_advise_prompt_lists_measurement_sample_and_warnings(mock_router_cls, mock_settings):
    """The user message carries the measurement, the sample and every warning as a bullet."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    router = _make_mock_router("ok")
    mock_router_cls.return_value = router

    advise_on_warnings(["Current too high", "Field near limit"], "AHE", "Pt/CoFeB Hall bar")

    messages = router.complete.call_args.args[0]
    assert messages[0] == {"role": "system", "content": SYSTEM_SAFETY}
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == (
        "Measurement: AHE\nSample: Pt/CoFeB Hall bar\nWarnings triggered:\n- Current too high\n- Field near limit"
    )


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_advise_prompt_omits_sample_line_when_not_given(mock_router_cls, mock_settings):
    """Without a sample description there is no empty 'Sample:' line in the prompt."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    router = _make_mock_router("ok")
    mock_router_cls.return_value = router

    advise_on_warnings(["Voltage too high"], "IV")

    user_msg = router.complete.call_args.args[0][1]["content"]
    assert "Sample:" not in user_msg
    assert user_msg == "Measurement: IV\nWarnings triggered:\n- Voltage too high"

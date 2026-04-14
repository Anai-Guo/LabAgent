"""Test literature injection into analyzer."""

from unittest.mock import MagicMock, patch

from lab_harness.analysis.analyzer import AnalysisResult, Analyzer


def _make_mock_router(response_text: str):
    router = MagicMock()
    router.complete.return_value = {
        "choices": [{"message": {"content": response_text}}],
    }
    return router


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_interpret_with_literature_injects_context(mock_router_cls, mock_settings):
    """Literature papers should appear in the LLM user message."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    mock_router = _make_mock_router("Based on [1], the result is consistent.")
    mock_router_cls.return_value = mock_router

    analyzer = Analyzer()
    result = AnalysisResult(
        measurement_type="IV",
        script_path="fake.py",
        script_source="# fake",
        extracted_values={"R": 1000},
        stdout="R = 1000 Ohm",
    )
    literature = {
        "source_papers": [
            {"title": "Classic IV paper", "year": 2020, "authors": ["Smith"]},
        ],
        "evidence_chunks": ["Typical IV shows linear ohmic behavior"],
    }
    analyzer.interpret_results(result, literature=literature)

    # Check the user message contained literature
    call_args = mock_router.complete.call_args[0][0]
    user_msg = next(m for m in call_args if m["role"] == "user")["content"]
    assert "[1]" in user_msg
    assert "Classic IV paper" in user_msg
    assert "Typical IV shows" in user_msg


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_interpret_without_literature_no_error(mock_router_cls, mock_settings):
    """Without literature, interpret_results should still work (backward compat)."""
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    mock_router_cls.return_value = _make_mock_router("OK")

    analyzer = Analyzer()
    result = AnalysisResult(
        measurement_type="IV",
        script_path="fake.py",
        script_source="",
        extracted_values={},
    )
    # literature=None (default)
    interp = analyzer.interpret_results(result)
    assert interp == "OK"


def test_interpret_no_llm_returns_empty():
    """Without API key or base_url, should return empty string (not crash)."""
    from unittest.mock import patch

    analyzer = Analyzer()
    with patch("lab_harness.config.Settings.load") as mock_settings:
        mock_settings.return_value.model.api_key = ""
        mock_settings.return_value.model.base_url = ""
        result = AnalysisResult(measurement_type="IV", script_path="x", script_source="")
        assert analyzer.interpret_results(result, literature={"source_papers": []}) == ""

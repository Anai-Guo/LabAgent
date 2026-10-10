"""Tests for Analyzer AI-generation, interpretation and pipeline fallbacks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lab_harness.analysis.analyzer import AnalysisResult, Analyzer, _read_data_preview


def _router(content: str) -> MagicMock:
    router = MagicMock()
    router.complete.return_value = {"choices": [{"message": {"content": content}}]}
    return router


def _user_msg(router: MagicMock) -> str:
    messages = router.complete.call_args[0][0]
    return next(m for m in messages if m["role"] == "user")["content"]


@pytest.fixture
def llm_on():
    """Pretend an LLM is configured and capture the router instance."""
    with patch("lab_harness.config.Settings.load") as load, patch("lab_harness.llm.router.LLMRouter") as cls:
        load.return_value.model.api_key = "test"
        load.return_value.model.base_url = None
        yield cls


@pytest.fixture
def llm_off():
    with patch("lab_harness.config.Settings.load") as load:
        load.return_value.model.api_key = ""
        load.return_value.model.base_url = ""
        yield load


class TestReadDataPreview:
    def test_preview_truncates_to_max_rows(self, tmp_path: Path):
        csv = tmp_path / "run.csv"
        csv.write_text("x,y\n" + "\n".join(f"{i},{i * 2}" for i in range(30)), encoding="utf-8")
        preview = _read_data_preview(csv, max_rows=3)
        assert "File: run.csv" in preview
        assert "Columns: x,y" in preview
        assert "Total rows: 30" in preview
        assert "2,4" in preview and "3,6" not in preview

    def test_unreadable_path_returns_message(self, tmp_path: Path):
        assert _read_data_preview(tmp_path / "missing.csv").startswith("Could not read data")


class TestGenerateScriptWithAI:
    def test_without_llm_falls_back_to_template(self, llm_off):
        script = Analyzer().generate_script_with_ai(Path("/d/ahe.csv"), "AHE")
        assert "{{DATA_PATH}}" not in script and "/d/ahe.csv" in script

    def test_prompt_includes_preview_and_instructions(self, llm_on, tmp_path: Path):
        csv = tmp_path / "mr.csv"
        csv.write_text("B,R\n0,1\n", encoding="utf-8")
        router = _router("import numpy\n")
        llm_on.return_value = router
        script = Analyzer(output_dir=tmp_path).generate_script_with_ai(csv, "MR", "fit a parabola")
        assert script == "import numpy"
        msg = _user_msg(router)
        assert "Measurement type: MR" in msg
        assert "Columns: B,R" in msg
        assert "Additional instructions:\nfit a parabola" in msg

    @pytest.mark.parametrize(
        "raw",
        ["```python\nimport numpy\nprint(1)\n```", "```\nimport numpy\nprint(1)\n```", "import numpy\nprint(1)"],
    )
    def test_markdown_fences_are_stripped(self, llm_on, tmp_path: Path, raw: str):
        llm_on.return_value = _router(raw)
        script = Analyzer().generate_script_with_ai(tmp_path / "x.csv", "IV")
        assert script == "import numpy\nprint(1)"


class TestInterpretResults:
    def test_data_path_preview_in_context(self, llm_on, tmp_path: Path):
        csv = tmp_path / "iv.csv"
        csv.write_text("V,I\n0,0\n1,2\n", encoding="utf-8")
        router = _router("fine")
        llm_on.return_value = router
        result = AnalysisResult(measurement_type="IV", script_path="x", script_source="", stdout="R = 0.5")
        assert Analyzer().interpret_results(result, data_path=csv) == "fine"
        msg = _user_msg(router)
        assert "Data preview:" in msg and "Columns: V,I" in msg and "Script output:\nR = 0.5" in msg

    def test_citation_with_year_but_no_authors(self, llm_on):
        router = _router("ok")
        llm_on.return_value = router
        result = AnalysisResult(measurement_type="IV", script_path="x", script_source="")
        literature = {"source_papers": [{"source": "arxiv:1234", "year": 2021}], "evidence_chunks": []}
        Analyzer().interpret_results(result, literature=literature)
        assert "[1] arxiv:1234 (2021)" in _user_msg(router)


class TestRunScript:
    def test_failing_script_raises_with_stderr(self, tmp_path: Path):
        script = tmp_path / "bad_analysis.py"
        script.write_text("raise SystemExit('boom')\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="Analysis failed: .*boom"):
            Analyzer(output_dir=tmp_path).run_script(script)


class TestAnalyzePipeline:
    @pytest.fixture
    def pipeline(self, tmp_path: Path):
        analyzer = Analyzer(output_dir=tmp_path)
        fake = AnalysisResult(measurement_type="x", script_path="x", script_source="")
        with (
            patch.object(Analyzer, "run_script", return_value=fake) as run,
            patch.object(Analyzer, "generate_script_with_ai", return_value="print(1)\n") as ai,
            patch.object(Analyzer, "interpret_results", return_value="insight") as interp,
        ):
            yield analyzer, run, ai, interp

    def test_use_ai_skips_template(self, pipeline, tmp_path: Path):
        analyzer, run, ai, interp = pipeline
        result = analyzer.analyze(tmp_path / "d.csv", "AHE", use_ai=True, custom_instructions="hint")
        ai.assert_called_once_with(tmp_path / "d.csv", "AHE", "hint")
        assert (tmp_path / "ahe_analysis.py").read_text(encoding="utf-8") == "print(1)\n"
        assert result.ai_interpretation == "" and not interp.called

    def test_missing_template_falls_back_to_ai_and_interprets(self, pipeline, tmp_path: Path):
        analyzer, run, ai, interp = pipeline
        lit = {"source_papers": []}
        result = analyzer.analyze(tmp_path / "d.csv", "NONEXISTENT", interpret=True, literature=lit)
        ai.assert_called_once_with(tmp_path / "d.csv", "NONEXISTENT", "")
        interp.assert_called_once_with(result, tmp_path / "d.csv", literature=lit)
        assert result.ai_interpretation == "insight"

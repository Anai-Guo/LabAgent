"""Tests for the analyze_data harness tool."""

from __future__ import annotations

import json

from lab_harness.analysis import analyzer
from lab_harness.analysis.analyzer import AnalysisResult
from lab_harness.harness.tools.analyze_tool import AnalyzeDataTool, AnalyzeInput
from lab_harness.harness.tools.base import ToolContext, create_default_registry


def _payload(output: str) -> dict:
    """Parse the JSON body that follows the tool's one-line summary."""
    return json.loads(output.split("\n\n", 1)[1])


class _FakeAnalyzer:
    calls: list[dict] = []
    result = AnalysisResult(measurement_type="IV", script_path="s.py", script_source="")

    def analyze(self, **kwargs):
        _FakeAnalyzer.calls.append(kwargs)
        return _FakeAnalyzer.result


def _install_fake(monkeypatch, result: AnalysisResult) -> list[dict]:
    _FakeAnalyzer.calls = []
    _FakeAnalyzer.result = result
    monkeypatch.setattr(analyzer, "Analyzer", _FakeAnalyzer)
    return _FakeAnalyzer.calls


async def test_missing_file_is_error(tmp_path):
    args = AnalyzeInput(data_path="nope.csv", measurement_type="IV")
    result = await AnalyzeDataTool().execute(args, ToolContext(cwd=tmp_path))

    assert result.is_error
    assert result.output == f"Data file not found: {tmp_path / 'nope.csv'}"


async def test_relative_path_resolved_against_cwd(monkeypatch, tmp_path):
    (tmp_path / "iv.csv").write_text("V,I\n0,0\n")
    calls = _install_fake(
        monkeypatch,
        AnalysisResult(
            measurement_type="IV",
            script_path="analyze_iv.py",
            script_source="print(1)",
            figures=["iv.png"],
            extracted_values={"R": 10.0, "Vth": 0.3},
            stdout="done",
        ),
    )

    args = AnalyzeInput(data_path="iv.csv", measurement_type="IV", use_ai=True, custom_instructions="log scale")
    result = await AnalyzeDataTool().execute(args, ToolContext(cwd=tmp_path))

    assert not result.is_error
    assert calls == [
        {
            "data_path": tmp_path / "iv.csv",
            "measurement_type": "IV",
            "use_ai": True,
            "custom_instructions": "log scale",
            "interpret": False,
        }
    ]
    assert result.output.split("\n", 1)[0] == "Analysis of IV: 1 figure(s), 2 extracted value(s)"
    assert result.metadata == {"figures": 1, "values": 2}
    assert _payload(result.output) == {
        "measurement_type": "IV",
        "script_path": "analyze_iv.py",
        "figures": ["iv.png"],
        "extracted_values": {"R": 10.0, "Vth": 0.3},
        "stdout": "done",
    }


async def test_absolute_path_and_interpretation(monkeypatch, tmp_path):
    data = tmp_path / "rt.csv"
    data.write_text("T,R\n300,1\n")
    calls = _install_fake(
        monkeypatch,
        AnalysisResult(measurement_type="RT", script_path="rt.py", script_source="", ai_interpretation="Metallic"),
    )

    args = AnalyzeInput(data_path=str(data), measurement_type="RT", interpret=True)
    result = await AnalyzeDataTool().execute(args, ToolContext(cwd=tmp_path / "elsewhere"))

    assert not result.is_error
    assert calls[0]["data_path"] == data
    assert calls[0]["interpret"] is True
    assert _payload(result.output)["ai_interpretation"] == "Metallic"
    assert result.metadata == {"figures": 0, "values": 0}


async def test_interpretation_omitted_when_empty(monkeypatch, tmp_path):
    (tmp_path / "d.csv").write_text("x\n1\n")
    _install_fake(monkeypatch, AnalysisResult(measurement_type="IV", script_path="s.py", script_source=""))

    result = await AnalyzeDataTool().execute(
        AnalyzeInput(data_path="d.csv", measurement_type="IV"), ToolContext(tmp_path)
    )

    assert "ai_interpretation" not in _payload(result.output)


async def test_analyzer_exception_is_reported_as_error(monkeypatch, tmp_path):
    (tmp_path / "d.csv").write_text("x\n1\n")

    class Boom:
        def analyze(self, **kwargs):
            raise ValueError("bad columns")

    monkeypatch.setattr(analyzer, "Analyzer", Boom)

    result = await AnalyzeDataTool().execute(
        AnalyzeInput(data_path="d.csv", measurement_type="IV"), ToolContext(tmp_path)
    )

    assert result.is_error
    assert result.output == "Analysis failed: bad columns"


def test_tool_is_not_read_only_and_registered():
    tool = AnalyzeDataTool()
    assert tool.is_read_only(AnalyzeInput(data_path="x", measurement_type="IV")) is False
    assert isinstance(create_default_registry().get("analyze_data"), AnalyzeDataTool)

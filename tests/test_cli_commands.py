"""In-process tests for CLI command handlers (heavy dependencies stubbed)."""

from __future__ import annotations

import argparse
import sys
import types

import pytest

from lab_harness import cli
from lab_harness.analysis.analyzer import AnalysisResult


def test_main_without_command_prints_help_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["labharness"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert "usage: labharness" in capsys.readouterr().out


def test_main_dispatches_to_command(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, path: "settings"))
    monkeypatch.setattr(cli, "cmd_propose", lambda args, settings: calls.append((args.measurement_type, settings)))
    monkeypatch.setattr(sys, "argv", ["labharness", "propose", "IV"])
    cli.main()
    assert calls == [("IV", "settings")]


def test_cmd_propose_prints_plan_json(capsys):
    cli.cmd_propose(argparse.Namespace(measurement_type="IV"), None)
    assert '"measurement_type": "IV"' in capsys.readouterr().out


def test_cmd_analyze_missing_file_exits(tmp_path, capsys):
    args = argparse.Namespace(data_file=str(tmp_path / "nope.csv"), type="IV", output=None)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_analyze(args, None)
    assert exc.value.code == 1
    assert "data file not found" in capsys.readouterr().out


def test_cmd_analyze_passes_options_and_prints_result(tmp_path, monkeypatch, capsys):
    from lab_harness.analysis import analyzer

    data = tmp_path / "iv.csv"
    data.write_text("V,I\n0,0\n", encoding="utf-8")
    seen = {}

    class FakeAnalyzer:
        def __init__(self, output_dir):
            seen["output_dir"] = output_dir

        def analyze(self, path, mtype, **kwargs):
            seen.update(path=path, mtype=mtype, **kwargs)
            return AnalysisResult(
                measurement_type=mtype,
                script_path="s.py",
                script_source="",
                figures=["a.png", "b.png"],
                extracted_values={"R": 1.5},
                ai_interpretation="Ohmic",
                stdout="done",
            )

    monkeypatch.setattr(analyzer, "Analyzer", FakeAnalyzer)
    args = argparse.Namespace(
        data_file=str(data), type="IV", output=str(tmp_path / "out"), ai=True, interpret=True, instructions=None
    )
    cli.cmd_analyze(args, None)

    assert seen["output_dir"] == tmp_path / "out"
    assert seen["mtype"] == "IV"
    assert seen["use_ai"] is True and seen["interpret"] is True
    assert seen["custom_instructions"] == ""
    out = capsys.readouterr().out
    for text in ("Script: s.py", "done", "Figures: a.png, b.png", '"R": 1.5', "AI Interpretation:\nOhmic"):
        assert text in out


def test_cmd_generate_skill_saves_content(monkeypatch, capsys):
    from lab_harness.skills import generator

    monkeypatch.setattr(generator, "generate_skill", lambda measurement_type, sample_description: "# skill")
    monkeypatch.setattr(generator, "save_skill", lambda mtype, content: f"skills/{mtype.lower()}.md")
    cli.cmd_generate_skill(argparse.Namespace(measurement_type="MR", sample=None), None)
    out = capsys.readouterr().out
    assert "# skill" in out
    assert "Saved to skills/mr.md" in out


def test_cmd_chat_loops_until_exit(monkeypatch, capsys):
    from lab_harness.agent import loop

    class FakeAgent:
        def __init__(self, settings):
            pass

        async def run_conversation(self, text):
            return f"echo {text}"

    replies = iter(["hello", "   ", "quit"])
    monkeypatch.setattr(loop, "LabAgent", FakeAgent)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(replies))
    cli.cmd_chat(argparse.Namespace(), None)
    out = capsys.readouterr().out
    assert out.count("echo") == 1 and "echo hello" in out
    assert out.rstrip().endswith("Goodbye")


def test_cmd_chat_stops_on_eof(monkeypatch, capsys):
    from lab_harness.agent import loop

    def raise_eof(prompt=""):
        raise EOFError

    monkeypatch.setattr(loop, "LabAgent", lambda settings: object())
    monkeypatch.setattr("builtins.input", raise_eof)
    cli.cmd_chat(argparse.Namespace(), None)
    assert "Goodbye" in capsys.readouterr().out


def test_cmd_panel_without_textual_exits(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "lab_harness.harness.tui.app", None)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_panel(argparse.Namespace(model=None), None)
    assert exc.value.code == 1
    assert "textual is required" in capsys.readouterr().out


def test_cmd_web_forwards_host_and_port(monkeypatch):
    calls = []
    fake = types.ModuleType("lab_harness.web.app")
    fake.run_web = lambda host, port: calls.append((host, port))
    monkeypatch.setitem(sys.modules, "lab_harness.web.app", fake)
    cli.cmd_web(argparse.Namespace(host="0.0.0.0", port=9000), None)
    assert calls == [("0.0.0.0", 9000)]

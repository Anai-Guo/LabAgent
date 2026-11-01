"""Tests for ExperimentFlow real-execution fallbacks, analysis and next-step paths.

The driver registry, executor, analyzer and LLM router are all stubbed, so
no instrument or network access happens.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from lab_harness.config import ModelConfig, Settings
from lab_harness.drivers.registry import DriverRegistry
from lab_harness.orchestrator import executor
from lab_harness.orchestrator.flow import ExperimentFlow


def _flow(tmp_path: Path, api_key: str | None = None) -> ExperimentFlow:
    flow = ExperimentFlow(Settings(model=ModelConfig(api_key=api_key)), data_root=tmp_path)
    flow.session.measurement_type = "IV"
    flow.session.material = "Pt film"
    flow.role_assignments = {"source_meter": object()}
    return flow


def _patch_registry(coverage: dict):
    return patch.object(DriverRegistry, "from_role_assignments", return_value=(MagicMock(), coverage))


def test_incomplete_driver_coverage_falls_back(tmp_path):
    flow = _flow(tmp_path)
    with _patch_registry({"source_meter": "none"}), patch.object(executor, "probe_registry") as probe:
        points, meta = flow._try_real_execution(plan=None)
    assert points is None
    assert "incomplete driver coverage" in meta["reason"]
    assert flow.session.driver_coverage == {"source_meter": "none"}
    probe.assert_not_called()


def test_probe_failure_falls_back(tmp_path):
    flow = _flow(tmp_path)
    with _patch_registry({"source_meter": "pymeasure"}), patch.object(executor, "probe_registry", return_value=False):
        points, meta = flow._try_real_execution(plan=None)
    assert points is None
    assert meta == {"backend": "simulator", "reason": "driver probe failed"}


def test_execution_error_falls_back_with_reason(tmp_path):
    flow = _flow(tmp_path)
    with (
        _patch_registry({"source_meter": "pymeasure"}),
        patch.object(executor, "probe_registry", return_value=True),
        patch.object(executor, "execute", side_effect=RuntimeError("bus timeout")),
    ):
        points, meta = flow._try_real_execution(plan=None)
    assert points is None
    assert meta["backend"] == "simulator"
    assert "bus timeout" in meta["reason"]


def test_successful_real_execution_reports_coverage(tmp_path):
    flow = _flow(tmp_path)
    rows = [{"Current (A)": 0.0, "Voltage (V)": 0.0}]
    progress = MagicMock()
    with (
        _patch_registry({"source_meter": "pymeasure"}),
        patch.object(executor, "probe_registry", return_value=True),
        patch.object(executor, "execute", return_value=rows) as execute,
    ):
        points, meta = flow._try_real_execution(plan="PLAN", progress=progress)
    assert points == rows
    assert meta == {"backend": "real", "coverage": {"source_meter": "pymeasure"}}
    assert execute.call_args.args[0] == "PLAN"
    assert execute.call_args.kwargs["progress"] is progress


async def test_analyze_failure_is_reported_and_suggestions_still_run(tmp_path, capsys):
    flow = _flow(tmp_path)
    flow._suggest_next_steps = MagicMock()
    with patch("lab_harness.analysis.analyzer.Analyzer") as analyzer_cls:
        analyzer_cls.return_value.analyze.side_effect = ValueError("bad csv")
        await flow._analyze(tmp_path / "raw_data.csv", tmp_path)
    assert "bad csv" in capsys.readouterr().out
    flow._suggest_next_steps.assert_called_once_with(tmp_path)


def test_suggest_next_steps_without_credentials_does_nothing(tmp_path):
    flow = _flow(tmp_path)
    with patch("lab_harness.llm.router.LLMRouter") as router_cls:
        flow._suggest_next_steps(tmp_path)
    router_cls.assert_not_called()
    assert not (tmp_path / "next_steps.md").exists()


def test_suggest_next_steps_writes_file_with_literature(tmp_path):
    flow = _flow(tmp_path, api_key="test-key")
    flow.session.literature = {"source_papers": [{"title": "Spin Hall review"}, {"source": "arXiv:1234"}, {}]}
    reply = {"choices": [{"message": {"content": "  1. Vary thickness [1]\n"}}]}
    with patch("lab_harness.llm.router.LLMRouter") as router_cls:
        router_cls.return_value.complete.return_value = reply
        flow._suggest_next_steps(tmp_path)
    prompt = router_cls.return_value.complete.call_args.args[0][1]["content"]
    assert "IV measurement on Pt film" in prompt
    assert "[1] Spin Hall review" in prompt
    assert "[2] arXiv:1234" in prompt
    assert "[3] paper 3" in prompt
    assert flow.session.next_step_suggestions == "1. Vary thickness [1]"
    assert (tmp_path / "next_steps.md").read_text(encoding="utf-8") == "1. Vary thickness [1]"


def test_suggest_next_steps_swallows_router_errors(tmp_path):
    flow = _flow(tmp_path, api_key="test-key")
    with patch("lab_harness.llm.router.LLMRouter") as router_cls:
        router_cls.return_value.complete.side_effect = RuntimeError("rate limited")
        flow._suggest_next_steps(tmp_path)
    assert not (tmp_path / "next_steps.md").exists()

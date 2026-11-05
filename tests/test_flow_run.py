"""Tests for the CLI guided flow ``ExperimentFlow.run`` and ``_classify``.

Literature search, instrument scanning, measurement and analysis are
replaced with stubs so no network, VISA or LLM access happens. Plan
building and boundary checking use the real YAML templates.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from lab_harness.config import Settings
from lab_harness.orchestrator.flow import ExperimentFlow


def _flow(tmp_path: Path, *, literature=None, instruments=None) -> ExperimentFlow:
    flow = ExperimentFlow(Settings(), data_root=tmp_path)

    async def fake_literature(emit=None):
        if isinstance(literature, Exception):
            raise literature
        return literature if literature is not None else {}

    async def fake_scan():
        if isinstance(instruments, Exception):
            raise instruments
        return instruments if instruments is not None else []

    async def fake_measure(plan, folder):
        data_file = folder / "raw_data.csv"
        data_file.write_text("x,y\n0,0\n", encoding="utf-8")
        return data_file

    async def fake_analyze(data_file, folder):
        return None

    flow._search_literature = fake_literature
    flow._scan_instruments = fake_scan
    flow._run_measurement = fake_measure
    flow._analyze = fake_analyze
    flow._classify = lambda emit=None: None
    return flow


def _run(flow: ExperimentFlow, decision: dict, answers: list[str]):
    with (
        patch("lab_harness.orchestrator.flow.decide_measurement", return_value=decision) as decide,
        patch("lab_harness.orchestrator.flow.open_folder") as opener,
        patch("builtins.input", side_effect=answers),
    ):
        session = asyncio.run(flow.run(direction="transport", material="Si wafer"))
    return session, decide, opener


class TestRun:
    def test_happy_path_fills_session_and_opens_folder(self, tmp_path: Path, capsys):
        instruments = [{"vendor": "Keithley", "model": "2400", "resource": "GPIB0::24::INSTR"}]
        literature = {"source_papers": [{"title": "p1"}, {"title": "p2"}]}
        flow = _flow(tmp_path, literature=literature, instruments=instruments)

        session, decide, opener = _run(flow, {"measurement_type": "IV", "reasoning": "two-terminal sweep"}, ["", ""])

        decide.assert_called_once_with("transport", "Si wafer", instruments, literature)
        assert session.measurement_type == "IV"
        assert session.measurement_reason == "two-terminal sweep"
        assert session.plan["measurement_type"] == "IV"
        assert "decision" in session.validation
        assert session.measurement_completed is True
        folder = Path(session.data_folder)
        assert folder.parent == tmp_path
        assert Path(session.data_file) == folder / "raw_data.csv"
        opener.assert_called_once_with(folder)
        summary = json.loads((folder / "experiment_summary.json").read_text(encoding="utf-8"))
        assert summary["measurement_type"] == "IV"
        out = capsys.readouterr().out
        assert "Found 1 instrument(s)" in out
        assert "Found 2 relevant reference(s)" in out
        assert "Keithley 2400 at GPIB0::24::INSTR" in out

    def test_prompts_for_missing_direction_and_material(self, tmp_path: Path):
        flow = _flow(tmp_path)
        with (
            patch("lab_harness.orchestrator.flow.decide_measurement", return_value={}) as decide,
            patch("lab_harness.orchestrator.flow.open_folder"),
            patch("builtins.input", side_effect=["  optics ", " GaAs ", "", "n"]),
        ):
            session = asyncio.run(flow.run())
        assert session.direction == "optics"
        assert session.material == "GaAs"
        assert decide.call_args.args[:2] == ("optics", "GaAs")
        # Empty decision falls back to IV.
        assert session.measurement_type == "IV"

    def test_discovery_failures_degrade_to_empty(self, tmp_path: Path, capsys):
        flow = _flow(tmp_path, literature=RuntimeError("offline"), instruments=OSError("no VISA"))
        session, decide, opener = _run(flow, {"measurement_type": "IV"}, ["", "n"])
        opener.assert_not_called()  # user answered "n"
        assert session.literature == {}
        assert session.instruments == []
        assert decide.call_args.args[2:] == ([], {})
        out = capsys.readouterr().out
        assert "Found 0 instrument(s)" in out
        assert "Literature context ready" in out

    def test_unknown_measurement_type_falls_back_to_iv(self, tmp_path: Path, capsys):
        flow = _flow(tmp_path)
        session, _, _ = _run(flow, {"measurement_type": "NOT_A_TEMPLATE"}, ["", "n"])
        assert session.measurement_type == "IV"
        assert session.plan["measurement_type"] == "IV"
        assert "No template for NOT_A_TEMPLATE" in capsys.readouterr().out


class TestClassify:
    def test_no_instruments_clears_assignments(self, tmp_path: Path):
        flow = ExperimentFlow(Settings(), data_root=tmp_path)
        flow.role_assignments = {"stale": object()}
        with patch("lab_harness.discovery.classifier.classify_instruments") as classify:
            flow._classify()
        assert flow.role_assignments == {}
        classify.assert_not_called()

    def test_bad_records_skipped_and_type_forwarded(self, tmp_path: Path):
        flow = ExperimentFlow(Settings(), data_root=tmp_path)
        flow.session.measurement_type = ""
        flow.session.instruments = [
            {"resource": "GPIB0::5::INSTR", "vendor": "Keithley", "model": "2182A"},
            {"vendor": "missing resource"},
        ]
        with patch("lab_harness.discovery.classifier.classify_instruments", return_value={"dmm": "x"}) as classify:
            flow._classify()
        assert flow.role_assignments == {"dmm": "x"}
        inventory, mtype = classify.call_args.args
        assert mtype == "IV"  # empty type defaults to IV
        assert [r.resource for r in inventory.instruments] == ["GPIB0::5::INSTR"]
        assert classify.call_args.kwargs["router"] is None

    def test_classifier_error_disables_real_execution(self, tmp_path: Path):
        flow = ExperimentFlow(Settings(), data_root=tmp_path)
        flow.session.instruments = [{"resource": "GPIB0::5::INSTR"}]
        with patch("lab_harness.discovery.classifier.classify_instruments", side_effect=ValueError("boom")):
            flow._classify()
        assert flow.role_assignments == {}

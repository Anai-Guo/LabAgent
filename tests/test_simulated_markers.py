"""Tests that simulated output is clearly marked everywhere.

The simulator-produced CSV, README, session state, and JSON summary must all
carry a clear SIMULATED marker so nobody ever confuses a sim run with real
instrument data.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lab_harness.orchestrator.session import ExperimentSession
from lab_harness.web.session_registry import SessionRegistry


def test_session_simulated_field_default_true():
    """A fresh ExperimentSession is simulated until proven otherwise."""
    session = ExperimentSession()
    assert session.simulated is True


def test_readme_has_warning_banner(tmp_path: Path):
    """save_summary writes a bold 'SIMULATED DATA' banner at the top of README.md."""
    session = ExperimentSession()
    session.direction = "transport"
    session.material = "Si wafer"
    session.measurement_type = "IV"
    session.save_summary(tmp_path)

    readme_text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "SIMULATED DATA" in readme_text
    # Banner must be near the top (before the Date line).
    banner_idx = readme_text.index("SIMULATED DATA")
    date_idx = readme_text.index("Date")
    assert banner_idx < date_idx


def test_json_summary_has_simulated_field(tmp_path: Path):
    """experiment_summary.json carries simulated=true so downstream tools can detect it."""
    session = ExperimentSession()
    session.material = "Si"
    session.measurement_type = "IV"
    session.save_summary(tmp_path)

    summary = json.loads((tmp_path / "experiment_summary.json").read_text(encoding="utf-8"))
    assert summary.get("simulated") is True


@pytest.mark.asyncio
async def test_csv_has_simulated_comments():
    """After run_phased, raw_data.csv begins with '# ... SIMULATED ...' comment lines."""
    from lab_harness.config import ModelConfig, Settings
    from lab_harness.orchestrator.flow import ExperimentFlow

    settings = Settings(model=ModelConfig())
    reg = SessionRegistry()
    live = reg.create()
    live.session.direction = "transport"
    live.session.material = "silicon"
    live.session.folder_confirmed = True  # auto-confirm so the flow doesn't wait

    with tempfile.TemporaryDirectory() as tmp:
        flow = ExperimentFlow(settings, data_root=Path(tmp))
        flow.session = live.session
        live.session.parent_dir = tmp

        with patch(
            "lab_harness.discovery.visa_scanner.scan_visa_instruments",
            return_value=[],
        ):
            await flow.run_phased(live)

        csv_path = Path(live.session.data_file)
        assert csv_path.exists(), f"expected CSV at {csv_path}"
        text = csv_path.read_text(encoding="utf-8")
        first_lines = text.splitlines()[:7]

        # At least one of the leading lines must start with '#' and contain SIMULATED.
        assert any(line.startswith("#") for line in first_lines), (
            "CSV should start with '#' comment lines; got: " + repr(first_lines)
        )
        assert any("SIMULATED" in line.upper() or "SIMULATION" in line.upper() for line in first_lines), (
            "CSV comment header should mention SIMULATED/SIMULATION; got: " + repr(first_lines)
        )

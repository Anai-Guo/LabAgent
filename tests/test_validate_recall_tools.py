"""Tests for the validate_plan and recall_experiments harness tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab_harness.harness.tools.base import ToolContext
from lab_harness.harness.tools.memory_tool import RecallExperimentsTool, RecallInput
from lab_harness.harness.tools.validate_tool import ValidateInput, ValidatePlanTool
from lab_harness.memory.store import MemoryStore


def _ahe_plan_dict(**overrides) -> dict:
    plan = {
        "measurement_type": "AHE",
        "name": "Test AHE",
        "x_axis": {"label": "Field", "unit": "Oe", "start": -5000, "stop": 5000, "step": 50},
        "y_channels": [{"label": "V_xy", "unit": "V", "role": "dmm"}],
        "max_current_a": 0.0001,
        "max_field_oe": 10000.0,
        "max_temperature_k": 300.0,
    }
    plan.update(overrides)
    return plan


def _payload(output: str) -> dict:
    """Parse the JSON body that follows the tool's one-line header."""
    return json.loads(output.split("\n\n", 1)[1])


# ---------------------------------------------------------------------------
# validate_plan
# ---------------------------------------------------------------------------


async def test_validate_safe_plan_allows():
    result = await ValidatePlanTool().execute(ValidateInput(plan=_ahe_plan_dict()), ToolContext())

    assert not result.is_error
    assert result.metadata == {"decision": "allow"}
    assert result.output.startswith("Validation result: allow")
    body = _payload(result.output)
    assert body["decision"] == "allow"
    assert body["violations"] == []
    assert set(body) == {"decision", "violations", "warnings", "ai_advice"}


async def test_validate_excessive_current_blocks_with_violation_details():
    result = await ValidatePlanTool().execute(ValidateInput(plan=_ahe_plan_dict(max_current_a=100.0)), ToolContext())

    assert not result.is_error
    assert result.metadata["decision"] == "block"
    body = _payload(result.output)
    current = [v for v in body["violations"] if v["parameter"] == "max_current_a"]
    assert len(current) == 1
    assert current[0]["requested"] == 100.0
    assert current[0]["limit"] < 100.0
    assert "current" in current[0]["message"].lower()


async def test_validate_invalid_plan_returns_error_result():
    """A malformed plan must surface as an error result, not raise."""
    result = await ValidatePlanTool().execute(ValidateInput(plan={"name": "missing fields"}), ToolContext())

    assert result.is_error
    assert result.output.startswith("Validation failed:")


def test_validate_tool_schema():
    schema = ValidatePlanTool().to_api_schema()
    assert schema["function"]["name"] == "validate_plan"
    assert "plan" in schema["function"]["parameters"]["required"]


# ---------------------------------------------------------------------------
# recall_experiments
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run in a temp cwd so the tool's default ./data/memory.db is isolated."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


async def test_recall_finds_matching_records(memory_cwd: Path):
    store = MemoryStore()
    rec_id = store.record_experiment(
        measurement_type="HALL",
        sample="Si-wafer-001",
        parameters={"temperature": 300},
        result_path="hall_001.csv",
        notes="Anomalous Hall effect at room temperature",
    )
    store.record_experiment(measurement_type="MR", sample="NiFe-20nm", notes="Magnetoresistance sweep")

    result = await RecallExperimentsTool().execute(RecallInput(query="Hall"), ToolContext())

    assert not result.is_error
    assert result.metadata == {"count": 1}
    assert "Found 1 experiment(s) matching 'Hall'" in result.output
    records = json.loads(result.output.split(":\n", 1)[1])
    assert records[0]["id"] == rec_id
    assert records[0]["sample"] == "Si-wafer-001"
    assert records[0]["measurement_type"] == "HALL"
    assert records[0]["parameters"] == {"temperature": 300}
    assert records[0]["result_path"] == "hall_001.csv"


async def test_recall_empty_store_returns_zero(memory_cwd: Path):
    result = await RecallExperimentsTool().execute(RecallInput(query="nothing"), ToolContext())

    assert not result.is_error
    assert result.metadata == {"count": 0}
    assert result.output.endswith("[]")
    assert (memory_cwd / "data" / "memory.db").exists()


async def test_recall_respects_limit(memory_cwd: Path):
    store = MemoryStore()
    for i in range(3):
        store.record_experiment(measurement_type="RT", sample=f"sample-{i}", notes="resistance cooldown")

    result = await RecallExperimentsTool().execute(RecallInput(query="cooldown", limit=2), ToolContext())

    assert result.metadata == {"count": 2}


async def test_recall_store_failure_returns_error_result(memory_cwd: Path, monkeypatch: pytest.MonkeyPatch):
    def _boom(self, query: str, limit: int = 10):
        raise RuntimeError("db locked")

    monkeypatch.setattr(MemoryStore, "search", _boom)

    result = await RecallExperimentsTool().execute(RecallInput(query="x"), ToolContext())

    assert result.is_error
    assert result.output == "Memory recall failed: db locked"

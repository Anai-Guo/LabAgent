"""Tests for the experiment-history learning helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lab_harness.memory.learning import suggest_parameters_from_history, summarize_experiment_history
from lab_harness.memory.store import ExperimentRecord, MemoryStore


@dataclass
class _FakeStore:
    """Deterministic stand-in for MemoryStore (records returned newest first)."""

    records: list[ExperimentRecord] = field(default_factory=list)
    calls: list[tuple] = field(default_factory=list)

    def get_by_type(self, measurement_type: str, limit: int = 20) -> list[ExperimentRecord]:
        self.calls.append(("get_by_type", measurement_type, limit))
        return self.records[:limit]

    def get_recent(self, limit: int = 10) -> list[ExperimentRecord]:
        self.calls.append(("get_recent", limit))
        return self.records[:limit]


def _record(ts: str, sample: str, params: dict | None, notes: str = "", mtype: str = "HALL") -> ExperimentRecord:
    return ExperimentRecord(timestamp=ts, sample=sample, measurement_type=mtype, parameters=params, notes=notes)


def test_suggest_no_history_real_store(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "mem.db")
    result = suggest_parameters_from_history(store, "HALL")
    assert result == {"past_parameters": [], "suggestion": "No prior experiments found."}


def test_suggest_uses_matching_type_from_real_store(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "mem.db")
    store.record_experiment("HALL", sample="Si-001", parameters={"temperature": 300}, notes="ok")
    store.record_experiment("MR", sample="NiFe", parameters={"field": 1.0})

    result = suggest_parameters_from_history(store, "hall")

    assert len(result["past_parameters"]) == 1
    entry = result["past_parameters"][0]
    assert entry["sample"] == "Si-001"
    assert entry["parameters"] == {"temperature": 300}
    assert entry["notes"] == "ok"
    assert len(entry["date"]) == 10


def test_suggest_skips_records_without_parameters_and_truncates_notes():
    store = _FakeStore(
        records=[
            _record("2026-03-02T10:00:00", "B", {"current": 1e-6}, notes="x" * 250),
            _record("2026-03-01T09:00:00", "A", {}),
            _record("2026-02-28T08:00:00", "C", None, notes="no params"),
        ]
    )

    result = suggest_parameters_from_history(store, "HALL", limit=3)

    assert store.calls == [("get_by_type", "HALL", 3)]
    assert [p["sample"] for p in result["past_parameters"]] == ["B"]
    assert result["past_parameters"][0]["date"] == "2026-03-02"
    assert result["past_parameters"][0]["notes"] == "x" * 100
    assert result["suggestion"] == "Found 1 prior HALL experiment(s). Most recent on 2026-03-02 for 'B'."


def test_suggest_all_records_lack_parameters():
    store = _FakeStore(records=[_record("2026-03-01T09:00:00", "A", {})])

    result = suggest_parameters_from_history(store, "IV")

    assert result["past_parameters"] == []
    assert result["suggestion"] == "Found 0 prior IV experiment(s). "


def test_summarize_empty_history(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "mem.db")
    assert summarize_experiment_history(store) == "No experiments recorded yet."


def test_summarize_lists_records_with_first_three_params():
    store = _FakeStore(
        records=[
            _record("2026-03-02T10:00:00", "B", {"a": 1, "b": 2, "c": 3, "d": 4}, mtype="MR"),
            _record("2026-03-01T09:00:00", "A", {}),
        ]
    )

    summary = summarize_experiment_history(store, limit=5)

    assert store.calls == [("get_recent", 5)]
    lines = summary.splitlines()
    assert lines[0] == "Experiment history (2 most recent):"
    assert lines[1] == "  [2026-03-02] MR on 'B' | params: {'a': 1, 'b': 2, 'c': 3}"
    assert lines[2] == "  [2026-03-01] HALL on 'A'"

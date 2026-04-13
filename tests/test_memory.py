"""Tests for experiment memory store and snapshot."""

from pathlib import Path

from lab_harness.memory.snapshot import MemorySnapshot
from lab_harness.memory.store import MemoryStore


def test_record_and_retrieve(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "test.db")
    rec_id = store.record_experiment(
        measurement_type="HALL",
        sample="CoFeB-10nm",
        parameters={"field_range": [-1, 1], "temperature": 300},
        result_path="/data/hall_001.csv",
        notes="Room temperature Hall measurement",
    )
    assert rec_id is not None

    recent = store.get_recent(limit=5)
    assert len(recent) == 1
    rec = recent[0]
    assert rec.id == rec_id
    assert rec.sample == "CoFeB-10nm"
    assert rec.measurement_type == "HALL"
    assert rec.parameters == {"field_range": [-1, 1], "temperature": 300}
    assert rec.result_path == "/data/hall_001.csv"
    assert rec.notes == "Room temperature Hall measurement"


def test_search_fts(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "test.db")
    store.record_experiment(
        measurement_type="HALL",
        sample="CoFeB-10nm",
        notes="Anomalous Hall effect at room temperature",
    )
    store.record_experiment(
        measurement_type="MR",
        sample="NiFe-20nm",
        notes="Magnetoresistance sweep",
    )
    store.record_experiment(
        measurement_type="HALL",
        sample="Pt/Co",
        notes="Hall measurement at low temperature",
    )

    results = store.search("Hall")
    assert len(results) == 2
    samples = {r.sample for r in results}
    assert "CoFeB-10nm" in samples
    assert "Pt/Co" in samples

    results_mr = store.search("Magnetoresistance")
    assert len(results_mr) == 1
    assert results_mr[0].sample == "NiFe-20nm"


def test_get_by_type(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "test.db")
    store.record_experiment(measurement_type="HALL", sample="A")
    store.record_experiment(measurement_type="MR", sample="B")
    store.record_experiment(measurement_type="HALL", sample="C")

    hall = store.get_by_type("hall")
    assert len(hall) == 2
    assert all(r.measurement_type == "HALL" for r in hall)


def test_snapshot_render(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "test.db")

    # Empty store
    snap_empty = MemorySnapshot.capture(store)
    assert snap_empty.total_count == 0
    assert "No previous experiments" in snap_empty.render_for_prompt()

    # With records
    store.record_experiment(
        measurement_type="HALL",
        sample="CoFeB-10nm",
        notes="First Hall measurement",
    )
    store.record_experiment(
        measurement_type="MR",
        sample="NiFe-20nm",
        notes="MR sweep at 10K",
    )

    snap = MemorySnapshot.capture(store, recent_limit=5)
    assert snap.total_count == 2
    assert len(snap.recent_experiments) == 2

    rendered = snap.render_for_prompt()
    assert "2 total" in rendered
    assert "HALL" in rendered
    assert "CoFeB-10nm" in rendered
    assert "MR" in rendered

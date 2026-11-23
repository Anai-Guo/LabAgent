"""Tests for HDF5 export and remaining DataExporter branches.

h5py and numpy are optional (not installed in CI), so the HDF5 path is
exercised against lightweight in-memory stand-ins injected via sys.modules.
"""

from __future__ import annotations

import re
import sys
import types

import pytest

from lab_harness.export.exporter import DataExporter, ExportConfig


class _FakeH5File:
    """Minimal h5py.File stand-in recording attrs and datasets."""

    instances: list[_FakeH5File] = []

    def __init__(self, path, mode):
        self.path = path
        self.mode = mode
        self.attrs: dict[str, str] = {}
        self.datasets: dict[str, list] = {}
        _FakeH5File.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def create_dataset(self, key, data):
        self.datasets[key] = list(data)


def _fake_array(values, dtype):
    # Mirrors numpy's behaviour of raising ValueError on non-numeric strings.
    return [dtype(v) for v in values]


@pytest.fixture()
def fake_hdf5(monkeypatch):
    _FakeH5File.instances = []
    monkeypatch.setitem(sys.modules, "h5py", types.SimpleNamespace(File=_FakeH5File))
    monkeypatch.setitem(sys.modules, "numpy", types.SimpleNamespace(array=_fake_array))
    return _FakeH5File.instances


@pytest.fixture()
def exporter(tmp_path) -> DataExporter:
    return DataExporter(ExportConfig(output_dir=tmp_path, timestamp_prefix=False))


def test_export_hdf5_numeric_and_string_columns(exporter, fake_hdf5, tmp_path):
    data = [
        {"field_oe": -100, "sample": "A"},
        {"field_oe": 100, "sample": "B"},
    ]
    path = exporter.export_hdf5(data, name="run", metadata={"temperature_k": 300})

    assert path == tmp_path / "run.h5"
    (f,) = fake_hdf5
    assert f.mode == "w"
    assert f.attrs["temperature_k"] == "300"
    assert "exported" in f.attrs
    assert f.datasets["field_oe"] == [-100.0, 100.0]
    # Non-numeric column falls back to stored strings
    assert f.datasets["sample"] == ["A", "B"]


def test_export_hdf5_missing_keys_default_to_zero(exporter, fake_hdf5):
    exporter.export_hdf5([{"x": 1, "y": 2}, {"x": 3}], name="sparse")
    assert fake_hdf5[0].datasets["y"] == [2.0, 0.0]


def test_export_hdf5_empty_data_writes_only_attrs(exporter, fake_hdf5):
    exporter.export_hdf5([], name="empty")
    (f,) = fake_hdf5
    assert f.datasets == {}
    assert list(f.attrs) == ["exported"]


def test_export_hdf5_without_h5py_raises_helpful_error(exporter, monkeypatch):
    monkeypatch.setitem(sys.modules, "h5py", None)
    with pytest.raises(ImportError, match="pip install h5py"):
        exporter.export_hdf5([{"x": 1}])


def test_export_dispatches_hdf5_and_uses_config_default(tmp_path, fake_hdf5):
    exp = DataExporter(ExportConfig(output_dir=tmp_path, format="hdf5", timestamp_prefix=False))
    assert exp.export([{"x": 1}], name="d").suffix == ".h5"
    assert len(fake_hdf5) == 1


def test_timestamp_prefix_in_filename(tmp_path):
    exp = DataExporter(ExportConfig(output_dir=tmp_path))
    path = exp.export_json([{"x": 1}], name="iv")
    assert re.fullmatch(r"\d{8}_\d{6}_iv\.json", path.name)


def test_init_creates_missing_output_dir(tmp_path):
    out = tmp_path / "nested" / "exports"
    DataExporter(ExportConfig(output_dir=out))
    assert out.is_dir()


def test_export_csv_empty_data_keeps_metadata_only(exporter):
    path = exporter.export_csv([], name="empty", metadata={"sample": "S1"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# sample: S1"
    assert lines[-1] == "#"


def test_export_csv_metadata_suppressed_when_disabled(tmp_path):
    exp = DataExporter(ExportConfig(output_dir=tmp_path, include_metadata=False, timestamp_prefix=False))
    path = exp.export_csv([{"x": 1}], name="plain", metadata={"sample": "S1"})
    assert path.read_text(encoding="utf-8").splitlines() == ["x", "1"]

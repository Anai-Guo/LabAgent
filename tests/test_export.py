"""Tests for the data export module."""

from __future__ import annotations

import json

import pytest

from lab_harness.export.exporter import DataExporter, ExportConfig


@pytest.fixture()
def sample_data() -> list[dict]:
    return [
        {"field_oe": -5000, "voltage_v": 0.0012, "current_a": 0.0001},
        {"field_oe": 0, "voltage_v": 0.0001, "current_a": 0.0001},
        {"field_oe": 5000, "voltage_v": -0.0011, "current_a": 0.0001},
    ]


@pytest.fixture()
def exporter(tmp_path) -> DataExporter:
    config = ExportConfig(output_dir=tmp_path, timestamp_prefix=False)
    return DataExporter(config)


def test_export_csv(exporter, sample_data, tmp_path):
    path = exporter.export_csv(sample_data, name="test")
    assert path.exists()
    assert path.suffix == ".csv"

    content = path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    # Header + 3 data rows
    assert len(lines) == 4
    assert "field_oe" in lines[0]


def test_export_json(exporter, sample_data, tmp_path):
    path = exporter.export_json(sample_data, name="test")
    assert path.exists()
    assert path.suffix == ".json"

    output = json.loads(path.read_text(encoding="utf-8"))
    assert "metadata" in output
    assert "data" in output
    assert output["metadata"]["points"] == 3
    assert len(output["data"]) == 3


def test_export_csv_with_metadata(exporter, sample_data, tmp_path):
    metadata = {"sample": "NiFe 10nm", "temperature_k": 300}
    path = exporter.export_csv(sample_data, name="test", metadata=metadata)

    content = path.read_text(encoding="utf-8")
    assert "# sample: NiFe 10nm" in content
    assert "# temperature_k: 300" in content
    assert "# exported:" in content


def test_export_dispatches_format(exporter, sample_data, tmp_path):
    csv_path = exporter.export(sample_data, name="a", fmt="csv")
    json_path = exporter.export(sample_data, name="b", fmt="json")
    assert csv_path.suffix == ".csv"
    assert json_path.suffix == ".json"

    with pytest.raises(ValueError, match="Unknown format"):
        exporter.export(sample_data, name="c", fmt="parquet")

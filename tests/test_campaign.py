"""Tests for the batch campaign module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab_harness.campaign.batch import Campaign, preview_campaign


def test_campaign_creation():
    campaign = Campaign.create(
        measurement_type="AHE",
        sweep_parameters={"field_oe": [-5000, 0, 5000], "current_a": [0.0001, 0.001]},
    )
    assert campaign.total_points == 6  # 3 x 2
    assert campaign.campaign_id.startswith("campaign-")
    assert campaign.measurement_type == "AHE"


def test_point_generation_with_fixed():
    campaign = Campaign.create(
        measurement_type="MR",
        sweep_parameters={"field_oe": [0, 1000, 2000]},
        fixed_parameters={"settling_time_s": 0.5},
    )
    assert campaign.total_points == 3
    for pt in campaign.points:
        assert pt.parameters["settling_time_s"] == 0.5
        assert "field_oe" in pt.parameters


def test_save_and_load(tmp_path):
    campaign = Campaign.create(
        measurement_type="AHE",
        sweep_parameters={"field_oe": [-1000, 0, 1000]},
        fixed_parameters={"current_a": 0.0001},
    )
    # Mark one point completed
    campaign.points[0].status = "completed"

    save_path = tmp_path / "campaign.json"
    campaign.save(save_path)
    assert save_path.exists()

    loaded = Campaign.load(save_path)
    assert loaded.campaign_id == campaign.campaign_id
    assert loaded.total_points == 3
    assert loaded.points[0].status == "completed"
    assert loaded.fixed_parameters["current_a"] == 0.0001


def test_load_hand_edited_utf8_under_cp1252_locale(tmp_path, monkeypatch):
    """A hand-edited UTF-8 campaign file must load intact even when the locale default is cp1252."""
    real_read = Path.read_text
    monkeypatch.setattr(
        Path, "read_text", lambda self, encoding=None, errors=None: real_read(self, encoding or "cp1252", errors)
    )
    campaign = Campaign.create(
        measurement_type="AHE",
        sweep_parameters={"field_oe": [0, 1000]},
        fixed_parameters={"current_a": 0.0001},
    )
    save_path = tmp_path / "campaign.json"
    campaign.save(save_path)
    data = json.loads(save_path.read_text(encoding="utf-8"))
    data["fixed_parameters"]["note"] = "R(Ω) at 10 µA"
    save_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    loaded = Campaign.load(save_path)
    assert loaded.fixed_parameters["note"] == "R(Ω) at 10 µA"
    assert loaded.total_points == 2


def test_progress_tracking():
    campaign = Campaign.create(
        measurement_type="IV",
        sweep_parameters={"voltage_v": [0, 1, 2, 3]},
    )
    assert campaign.progress == 0.0

    campaign.points[0].status = "completed"
    campaign.points[1].status = "completed"
    assert campaign.completed_points == 2
    assert campaign.progress == pytest.approx(0.5)

    # next_pending skips completed
    nxt = campaign.next_pending()
    assert nxt is not None
    assert nxt.index == 2


def test_preview_campaign():
    text = preview_campaign(
        measurement_type="AHE",
        sweep_parameters={"field_oe": [-5000, 0, 5000], "current_a": [0.0001, 0.001]},
        fixed_parameters={"settling_time_s": 0.5},
    )
    assert "Total points: 6" in text
    assert "field_oe" in text
    assert "settling_time_s" in text

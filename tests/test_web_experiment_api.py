"""Tests for the guided-experiment start, SSE events and configure Web endpoints."""

import json

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from httpx import ASGITransport, AsyncClient

from lab_harness.orchestrator import decider
from lab_harness.orchestrator.flow import ExperimentFlow
from lab_harness.web import session_registry
from lab_harness.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def registry(monkeypatch):
    """Isolated global registry so tests never share sessions."""
    reg = session_registry.SessionRegistry()
    monkeypatch.setattr(session_registry, "_registry", reg)
    return reg


def _stub_flow(monkeypatch, literature, instruments):
    """Replace network/VISA lookups; values that are exceptions get raised."""

    async def fake_lit(self, emit=None):
        if isinstance(literature, Exception):
            raise literature
        return literature

    async def fake_scan(self):
        if isinstance(instruments, Exception):
            raise instruments
        return instruments

    monkeypatch.setattr(ExperimentFlow, "_search_literature", fake_lit)
    monkeypatch.setattr(ExperimentFlow, "_scan_instruments", fake_scan)


async def test_start_experiment_builds_validated_plan(client, monkeypatch):
    instruments = [{"resource": "GPIB0::5::INSTR", "model": "2400"}]
    _stub_flow(monkeypatch, {"papers": []}, instruments)
    seen = {}

    def fake_decide(direction, material, insts, lit):
        seen.update(direction=direction, material=material, insts=insts, lit=lit)
        return {"measurement_type": "IV", "reasoning": "stub reason"}

    monkeypatch.setattr(decider, "decide_measurement", fake_decide)

    resp = await client.post("/api/experiment/start", params={"direction": "transport", "material": "Pt film"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["measurement_type"] == "IV"
    assert data["reasoning"] == "stub reason"
    assert data["instruments"] == instruments
    assert data["plan"]["measurement_type"] == "IV"
    assert data["plan"]["description"]
    assert "decision" in data["validation"]
    assert data["session_id"]
    assert data["folder_name"]
    assert seen == {"direction": "transport", "material": "Pt film", "insts": instruments, "lit": {"papers": []}}


async def test_start_experiment_tolerates_lookup_failures_and_unknown_type(client, monkeypatch):
    _stub_flow(monkeypatch, RuntimeError("offline"), OSError("no VISA"))
    seen = {}

    def fake_decide(direction, material, insts, lit):
        seen.update(insts=insts, lit=lit)
        return {"measurement_type": "NO_SUCH_TEMPLATE"}

    monkeypatch.setattr(decider, "decide_measurement", fake_decide)

    resp = await client.post("/api/experiment/start", params={"direction": "x", "material": "y"})
    assert resp.status_code == 200
    data = resp.json()
    # Failed lookups degrade to empty results instead of a 500.
    assert seen == {"insts": [], "lit": {}}
    assert data["instruments"] == []
    # Unknown template falls back to IV.
    assert data["measurement_type"] == "IV"
    assert data["plan"]["measurement_type"] == "IV"
    assert data["reasoning"] == ""


async def test_events_stream_until_done(client, registry):
    live = registry.create()
    live.emit_sync("phase", name="literature")
    live.emit_sync("done")
    live.emit_sync("phase", name="never-sent")

    resp = await client.get(f"/api/experiment/{live.session.session_id}/events")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[len("data: ") :]) for line in resp.text.splitlines() if line.startswith("data: ")]
    assert [e["type"] for e in events] == ["phase", "done"]
    assert events[0]["data"] == {"name": "literature"}


async def test_configure_applies_overrides(client):
    resp = await client.post(
        "/api/configure",
        json={
            "measurement_type": "IV",
            "x_start": -0.5,
            "x_stop": 0.5,
            "x_step": 0.1,
            "settling_time_s": 0.2,
            "num_averages": 3,
            "sample_description": "test sample",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    plan = data["plan"]
    assert plan["x_axis"]["start"] == -0.5
    assert plan["x_axis"]["stop"] == 0.5
    assert plan["x_axis"]["step"] == 0.1
    assert plan["settling_time_s"] == 0.2
    assert plan["num_averages"] == 3
    assert data["total_points"] >= 11
    assert "decision" in data["validation"]


async def test_configure_without_overrides_uses_template_defaults(client):
    resp = await client.post("/api/configure", json={"measurement_type": "IV"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"]["measurement_type"] == "IV"
    assert data["total_points"] > 0

"""Tests for the remaining Web GUI paths: background start, helper endpoints and WebSocket stream."""

import asyncio
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from fastapi import WebSocketDisconnect
from httpx import ASGITransport, AsyncClient

from lab_harness.discovery import visa_scanner
from lab_harness.models.instrument import InstrumentRecord
from lab_harness.orchestrator import folder as folder_module
from lab_harness.orchestrator.flow import ExperimentFlow
from lab_harness.web import app as app_module
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


async def test_start_async_runs_flow_on_the_registry_session(client, registry, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    seen = {}

    async def fake_run_phased(self, live):
        seen["same_session"] = self.session is live.session
        return live.session

    monkeypatch.setattr(ExperimentFlow, "run_phased", fake_run_phased)

    resp = await client.post("/api/experiment/start_async", params={"direction": "spintronics", "material": "NiFe"})

    assert resp.status_code == 200
    live = registry.get(resp.json()["session_id"])
    await live.task
    assert seen == {"same_session": True}
    assert (live.session.direction, live.session.material) == ("spintronics", "NiFe")


async def test_events_stream_ends_when_queue_stays_idle(client, registry, monkeypatch):
    live = registry.create()

    async def fake_wait_for(awaitable, timeout):
        awaitable.close()
        assert timeout == 300
        raise asyncio.TimeoutError

    monkeypatch.setattr(app_module.asyncio, "wait_for", fake_wait_for)

    resp = await client.get(f"/api/experiment/{live.session.session_id}/events")

    assert resp.status_code == 200
    assert resp.text == ""


async def test_open_folder_reports_helper_result(client, monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(folder_module, "open_folder", lambda path: opened.append(path) or False)

    resp = await client.post("/api/experiment/open-folder", params={"folder_path": str(tmp_path)})

    assert resp.json() == {"opened": False, "path": str(tmp_path)}
    assert opened == [tmp_path]


async def test_instruments_endpoint_serializes_scan(client, monkeypatch):
    record = InstrumentRecord(resource="GPIB0::5::INSTR", vendor="KEITHLEY", model="2400")
    monkeypatch.setattr(visa_scanner, "scan_visa_instruments", lambda: [record])

    body = (await client.get("/api/instruments")).json()

    assert body["count"] == 1
    assert body["instruments"][0]["resource"] == "GPIB0::5::INSTR"
    assert body["instruments"][0]["model"] == "2400"


async def test_plan_endpoint_applies_overrides_and_validates(client):
    resp = await client.post("/api/plan", params={"measurement_type": "IV"}, json={"settling_time_s": 0.25})

    body = resp.json()
    assert resp.status_code == 200
    assert body["plan"]["settling_time_s"] == 0.25
    assert "decision" in body["validation"]


async def test_health_counts_visa_resources_when_pyvisa_works(client, monkeypatch):
    manager = SimpleNamespace(list_resources=lambda: ("GPIB0::1::INSTR", "GPIB0::2::INSTR"))
    monkeypatch.setitem(sys.modules, "pyvisa", SimpleNamespace(ResourceManager=lambda: manager))

    body = (await client.get("/api/health")).json()

    assert body["visa_available"] is True
    assert body["instruments_found"] == 2


def test_load_html_names_the_missing_template(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "TEMPLATES_HTML_DIR", tmp_path)

    with pytest.raises(FileNotFoundError, match="nope.html"):
        app_module._load_html("nope.html")


async def test_ws_stream_sends_frames_until_client_disconnects(monkeypatch):
    frames = []

    class FakeSocket:
        accepted = False

        async def accept(self):
            self.accepted = True

        async def send_json(self, data):
            if len(frames) == 2:
                raise WebSocketDisconnect()
            frames.append(data)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(app_module.asyncio, "sleep", no_sleep)
    socket = FakeSocket()

    await app_module.ws_stream(socket)

    assert socket.accepted
    assert len(frames) == 2
    assert set(frames[0]) == {"timestamp", "voltage", "current", "resistance", "temperature", "field"}

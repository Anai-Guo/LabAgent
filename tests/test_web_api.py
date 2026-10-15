"""Tests for Web API endpoints."""

import builtins

import pytest

# Need httpx for async testing
pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from httpx import ASGITransport, AsyncClient

from lab_harness.planning import plan_builder
from lab_harness.web import app as web_app
from lab_harness.web.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "templates_available" in data


@pytest.mark.asyncio
async def test_list_templates(client):
    resp = await client.get("/api/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 46
    assert "iv" in data["templates"]


@pytest.mark.asyncio
async def test_get_template(client):
    resp = await client.get("/api/templates/iv")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "IV Measurement"


@pytest.mark.asyncio
async def test_get_template_not_found(client):
    resp = await client.get("/api/templates/nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_dashboard_page(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "LabAgent" in resp.text or "labharness" in resp.text.lower()


@pytest.mark.asyncio
async def test_monitor_page(client):
    resp = await client.get("/monitor")
    assert resp.status_code == 200
    assert "Monitor" in resp.text or "monitor" in resp.text.lower()


@pytest.fixture
def legacy_locale_templates(monkeypatch, tmp_path):
    """A UTF-8 template with non-ASCII text, served under a simulated cp1252 locale."""
    (tmp_path / "iv.yaml").write_text(
        'name: "I-V Ω sweep"\ndescription: "Sweep 0–5 V at 300 °C"\n',
        encoding="utf-8",
    )

    def legacy_locale_open(file, mode="r", *args, encoding=None, **kwargs):
        if "b" not in mode and encoding is None:
            encoding = "cp1252"
        return builtins.open(file, mode, *args, encoding=encoding, **kwargs)

    monkeypatch.setattr(plan_builder, "TEMPLATES_DIR", tmp_path)
    monkeypatch.setattr(web_app, "open", legacy_locale_open, raising=False)


@pytest.mark.asyncio
async def test_templates_read_as_utf8_regardless_of_locale(client, legacy_locale_templates):
    listed = (await client.get("/api/templates")).json()["templates"]["iv"]
    assert listed["name"] == "I-V Ω sweep"
    assert listed["description"] == "Sweep 0–5 V at 300 °C"

    detail = (await client.get("/api/templates/iv")).json()
    assert detail["name"] == "I-V Ω sweep"

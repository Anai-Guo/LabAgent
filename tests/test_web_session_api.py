"""Tests for the per-session Web API endpoints (status, set-folder, figure)."""

from pathlib import Path

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from httpx import ASGITransport, AsyncClient

from lab_harness.web import session_registry
from lab_harness.web.app import app


@pytest.fixture
def registry(monkeypatch):
    """Isolated global registry so tests never share sessions."""
    reg = session_registry.SessionRegistry()
    monkeypatch.setattr(session_registry, "_registry", reg)
    return reg


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/experiment/missing/status"),
        ("get", "/api/experiment/missing/events"),
        ("post", "/api/experiment/missing/set-folder"),
        ("get", "/api/experiment/missing/figure/plot.png"),
    ],
)
async def test_unknown_session_returns_404(client, registry, method, path):
    resp = await getattr(client, method)(path)
    assert resp.status_code == 404


async def test_status_snapshot_reports_session_fields(client, registry):
    live = registry.create()
    s = live.session
    s.direction = "spintronics"
    s.material = "Pt"
    s.measurement_type = "AHE"
    s.analysis_result = {
        "figures": ["/some/dir/fig_a.png", "/other/fig_b.pdf"],
        "extracted_values": {"Rxy": 1.5},
    }

    resp = await client.get(f"/api/experiment/{s.session_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == s.session_id
    assert data["direction"] == "spintronics"
    assert data["measurement_type"] == "AHE"
    # Only bare filenames are exposed, never the full server-side path.
    assert data["figures"] == ["fig_a.png", "fig_b.pdf"]
    assert data["extracted_values"] == {"Rxy": 1.5}
    assert data["simulated"] is True
    assert data["done"] is False


async def test_status_without_analysis_has_empty_figures(client, registry):
    live = registry.create()
    data = (await client.get(f"/api/experiment/{live.session.session_id}/status")).json()
    assert data["figures"] == []
    assert data["extracted_values"] == {}


async def test_set_folder_sanitizes_name_and_confirms(client, registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    live = registry.create()
    sid = live.session.session_id
    parent = tmp_path / "runs"

    resp = await client.post(
        f"/api/experiment/{sid}/set-folder",
        params={"folder_name": "  ../evil/name\\x  ", "parent_dir": str(parent)},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    safe = live.session.folder_name_override
    assert "/" not in safe and "\\" not in safe and ".." not in safe
    assert live.session.parent_dir == str(parent.resolve())
    assert live.session.folder_confirmed is True
    assert Path(resp.json()["folder"]) == parent.resolve() / safe


async def test_set_folder_rejects_parent_outside_cwd_and_home(client, registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    live = registry.create()
    outside = Path(tmp_path.anchor) / "labagent-not-allowed"

    resp = await client.post(
        f"/api/experiment/{live.session.session_id}/set-folder",
        params={"parent_dir": str(outside)},
    )
    assert resp.status_code == 200
    # Falls back to ./data under the current working directory.
    assert live.session.parent_dir == str((tmp_path / "data").resolve())
    # Empty name keeps the auto-generated folder name.
    assert live.session.folder_name_override == ""
    assert Path(resp.json()["folder"]).name == live.session.folder_name


async def test_figure_requires_data_folder(client, registry):
    live = registry.create()
    resp = await client.get(f"/api/experiment/{live.session.session_id}/figure/plot.png")
    assert resp.status_code == 404


async def test_figure_served_with_media_type(client, registry, tmp_path):
    live = registry.create()
    live.session.data_folder = str(tmp_path)
    (tmp_path / "plot.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "report.pdf").write_bytes(b"%PDF fake")
    sid = live.session.session_id

    png = await client.get(f"/api/experiment/{sid}/figure/plot.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.content == b"\x89PNG fake"

    pdf = await client.get(f"/api/experiment/{sid}/figure/report.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"


async def test_figure_missing_file_and_traversal_name(client, registry, tmp_path):
    folder = tmp_path / "session"
    folder.mkdir()
    (tmp_path / "secret.png").write_bytes(b"outside")
    live = registry.create()
    live.session.data_folder = str(folder)
    sid = live.session.session_id

    assert (await client.get(f"/api/experiment/{sid}/figure/nope.png")).status_code == 404
    # "..secret.png" is neutralised to "_secret.png" and never escapes the folder.
    resp = await client.get(f"/api/experiment/{sid}/figure/..secret.png")
    assert resp.status_code == 404
    assert resp.content != b"outside"

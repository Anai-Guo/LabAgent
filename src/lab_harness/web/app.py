"""Web GUI for LabAgent.

Adaptive interface that dynamically generates measurement forms
from YAML templates — supports 46+ measurement types without
hardcoded pages.

HTML templates are in web/templates/:
  dashboard.html — measurement template configurator
  monitor.html   — real-time multi-panel data monitor
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import time
from pathlib import Path
from pathlib import Path as _Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LabAgent",
    description="Adaptive measurement interface",
    version="0.1.0",
)

TEMPLATES_HTML_DIR = Path(__file__).parent / "templates"


@app.on_event("startup")
async def start_cleanup():
    """Periodic session cleanup every 5 minutes."""

    async def cleanup_loop():
        from lab_harness.web.session_registry import get_registry

        while True:
            try:
                await asyncio.sleep(300)  # 5 min
                removed = get_registry().cleanup()
                if removed > 0:
                    logging.getLogger(__name__).info("Cleaned up %d done sessions", removed)
            except Exception:
                pass

    asyncio.create_task(cleanup_loop())


# ---------------------------------------------------------------------------
# HTML page routes
# ---------------------------------------------------------------------------


def _load_html(name: str) -> str:
    """Load an HTML template from the templates directory."""
    path = TEMPLATES_HTML_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"HTML template not found: {path}")
    return path.read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the adaptive measurement dashboard."""
    return _load_html("dashboard.html")


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    """Serve the multi-panel real-time monitor."""
    return _load_html("monitor.html")


@app.get("/experiment", response_class=HTMLResponse)
async def experiment_page():
    """Serve the guided experiment page."""
    return _load_html("experiment.html")


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.post("/api/experiment/start")
async def start_experiment(direction: str, material: str):
    """Start a guided experiment flow asynchronously."""
    from pathlib import Path

    from lab_harness.config import Settings
    from lab_harness.orchestrator.flow import ExperimentFlow

    settings = Settings.load()
    flow = ExperimentFlow(settings, data_root=Path("./data"))

    # Run steps up to measurement prep (no interactive prompts)
    flow.session.direction = direction
    flow.session.material = material

    # Parallel: literature + instruments
    import asyncio

    literature, instruments = await asyncio.gather(
        flow._search_literature(),
        flow._scan_instruments(),
        return_exceptions=True,
    )
    if isinstance(literature, Exception):
        literature = {}
    if isinstance(instruments, Exception):
        instruments = []
    flow.session.literature = literature if isinstance(literature, dict) else {}
    flow.session.instruments = instruments if isinstance(instruments, list) else []

    # Decide measurement type
    from lab_harness.orchestrator.decider import decide_measurement

    decision = decide_measurement(direction, material, flow.session.instruments, flow.session.literature)
    flow.session.measurement_type = decision.get("measurement_type", "IV")
    flow.session.measurement_reason = decision.get("reasoning", "")

    # Build plan
    from lab_harness.planning.boundary_checker import check_boundaries
    from lab_harness.planning.plan_builder import build_plan_from_template

    try:
        plan = build_plan_from_template(flow.session.measurement_type, sample_description=material)
    except FileNotFoundError:
        flow.session.measurement_type = "IV"
        plan = build_plan_from_template("IV", sample_description=material)
    validation = check_boundaries(plan)
    flow.session.plan = plan.model_dump()
    flow.session.validation = validation.model_dump()

    return {
        "session_id": flow.session.session_id,
        "measurement_type": flow.session.measurement_type,
        "reasoning": flow.session.measurement_reason,
        "instruments": flow.session.instruments,
        "plan": flow.session.plan,
        "validation": flow.session.validation,
        "folder_name": flow.session.folder_name,
    }


@app.post("/api/experiment/start_async")
async def start_experiment_async(direction: str, material: str):
    """Start an experiment flow asynchronously, return session_id immediately.

    The full phased flow runs in the background and emits events via the
    session's event queue; the UI consumes them through
    ``/api/experiment/{session_id}/events`` (SSE).
    """
    from lab_harness.config import Settings
    from lab_harness.orchestrator.flow import ExperimentFlow
    from lab_harness.web.session_registry import get_registry

    registry = get_registry()
    live = registry.create()
    live.session.direction = direction
    live.session.material = material

    settings = Settings.load()
    flow = ExperimentFlow(settings, data_root=_Path("./data"))
    flow.session = live.session  # share the registry's session

    live.task = asyncio.create_task(flow.run_phased(live))
    return {"session_id": live.session.session_id}


@app.get("/api/experiment/{session_id}/events")
async def experiment_events(session_id: str):
    """Server-Sent Events stream for a live experiment session."""
    from lab_harness.web.session_registry import get_registry

    registry = get_registry()
    live = registry.get(session_id)
    if not live:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_gen():
        while True:
            try:
                evt = await asyncio.wait_for(live.events.get(), timeout=300)
            except asyncio.TimeoutError:
                break
            yield f"data: {json.dumps(evt)}\n\n"
            if evt.get("type") == "done":
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/experiment/{session_id}/status")
async def experiment_status(session_id: str):
    """Full snapshot of the current session state."""
    from lab_harness.web.session_registry import get_registry

    registry = get_registry()
    live = registry.get(session_id)
    if not live:
        raise HTTPException(status_code=404, detail="Session not found")

    s = live.session
    figures = []
    if s.analysis_result and s.analysis_result.get("figures"):
        figures = [_Path(f).name for f in s.analysis_result["figures"]]

    return {
        "session_id": s.session_id,
        "direction": s.direction,
        "material": s.material,
        "measurement_type": s.measurement_type,
        "reasoning": s.measurement_reason,
        "instruments": s.instruments,
        "literature": s.literature,
        "plan": s.plan,
        "validation": s.validation,
        "data_folder": s.data_folder,
        "data_file": s.data_file,
        "measurement_completed": s.measurement_completed,
        "ai_interpretation": s.ai_interpretation,
        "next_step_suggestions": s.next_step_suggestions,
        "figures": figures,
        "extracted_values": (s.analysis_result or {}).get("extracted_values", {}),
        "folder_name": s.folder_name,
        "parent_dir": s.parent_dir,
        "folder_confirmed": s.folder_confirmed,
        "simulated": s.simulated,
        "done": live.done,
    }


@app.post("/api/experiment/{session_id}/set-folder")
async def set_folder(session_id: str, folder_name: str = "", parent_dir: str = ""):
    """User-customized data save location prior to measurement."""
    from lab_harness.web.session_registry import get_registry

    registry = get_registry()
    live = registry.get(session_id)
    if not live:
        raise HTTPException(status_code=404, detail="Session not found")

    # Path validation: only allow parents under CWD or HOME
    parent = _Path(parent_dir).resolve() if parent_dir else (_Path.cwd() / "data").resolve()
    cwd_root = str(_Path.cwd().resolve())
    home_root = str(_Path.home().resolve())
    if not (str(parent).startswith(cwd_root) or str(parent).startswith(home_root)):
        parent = (_Path.cwd() / "data").resolve()

    # Sanitize folder_name — disallow path traversal / separators
    safe_name = folder_name.strip().replace("/", "_").replace("\\", "_").replace("..", "_")

    if safe_name:
        live.session.folder_name_override = safe_name
    live.session.parent_dir = str(parent)
    live.session.folder_confirmed = True

    return {"ok": True, "folder": str(parent / (safe_name or live.session.folder_name))}


@app.get("/api/experiment/{session_id}/figure/{name}")
async def experiment_figure(session_id: str, name: str):
    """Serve a figure from the session's data folder (path-traversal safe)."""
    from lab_harness.web.session_registry import get_registry

    registry = get_registry()
    live = registry.get(session_id)
    if not live or not live.session.data_folder:
        raise HTTPException(status_code=404, detail="Session or folder not found")

    safe_name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
    folder = _Path(live.session.data_folder).resolve()
    file_path = (folder / safe_name).resolve()

    if not str(file_path).startswith(str(folder)):
        raise HTTPException(status_code=403, detail="Path traversal detected")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Figure not found")

    media = "image/png" if safe_name.lower().endswith(".png") else "application/pdf"
    return FileResponse(file_path, media_type=media)


@app.post("/api/experiment/open-folder")
async def api_open_folder(folder_path: str):
    """Open a data folder in the OS file explorer."""
    from pathlib import Path

    from lab_harness.orchestrator.folder import open_folder

    ok = open_folder(Path(folder_path))
    return {"opened": ok, "path": folder_path}


@app.get("/api/templates")
async def list_templates():
    """List all available measurement templates grouped by discipline."""
    import yaml

    from lab_harness.planning.plan_builder import TEMPLATES_DIR

    templates = {}
    for path in sorted(TEMPLATES_DIR.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        templates[path.stem] = {
            "name": data.get("name", path.stem),
            "description": data.get("description", ""),
            "x_axis": data.get("x_axis", {}),
            "y_channels": data.get("y_channels", []),
            "has_outer_sweep": "outer_sweep" in data,
        }
    return {"count": len(templates), "templates": templates}


@app.get("/api/templates/{measurement_type}")
async def get_template(measurement_type: str):
    """Get full template config for dynamic form generation."""
    import yaml

    from lab_harness.planning.plan_builder import TEMPLATES_DIR

    path = TEMPLATES_DIR / f"{measurement_type.lower()}.yaml"
    if not path.exists():
        return {"error": f"Template '{measurement_type}' not found"}

    with open(path) as f:
        data = yaml.safe_load(f)
    return data


@app.get("/api/instruments")
async def scan_instruments():
    """Scan for connected instruments."""
    from lab_harness.discovery.visa_scanner import scan_visa_instruments

    instruments = scan_visa_instruments()
    return {
        "count": len(instruments),
        "instruments": [i.model_dump() for i in instruments],
    }


@app.post("/api/plan")
async def create_plan(measurement_type: str, overrides: dict | None = None):
    """Generate a measurement plan from template."""
    from lab_harness.planning.boundary_checker import check_boundaries
    from lab_harness.planning.plan_builder import build_plan_from_template

    plan = build_plan_from_template(measurement_type, overrides=overrides)
    validation = check_boundaries(plan)
    return {
        "plan": plan.model_dump(),
        "validation": validation.model_dump(),
    }


class MeasurementRequest(BaseModel):
    measurement_type: str
    x_start: float | None = None
    x_stop: float | None = None
    x_step: float | None = None
    settling_time_s: float | None = None
    num_averages: int | None = None
    sample_description: str = ""


@app.post("/api/configure")
async def configure_measurement(request: MeasurementRequest):
    """Accept measurement configuration from dashboard form, return validated plan."""
    overrides = {}
    if request.x_start is not None:
        overrides["x_axis"] = {
            "start": request.x_start,
            "stop": request.x_stop,
            "step": request.x_step,
        }
    if request.settling_time_s is not None:
        overrides["settling_time_s"] = request.settling_time_s
    if request.num_averages is not None:
        overrides["num_averages"] = request.num_averages

    from lab_harness.planning.boundary_checker import check_boundaries
    from lab_harness.planning.plan_builder import build_plan_from_template

    plan = build_plan_from_template(
        request.measurement_type,
        overrides=overrides,
        sample_description=request.sample_description,
    )
    validation = check_boundaries(plan)

    return {
        "plan": plan.model_dump(),
        "validation": validation.model_dump(),
        "total_points": plan.total_points,
    }


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time measurement data streaming."""
    await websocket.accept()
    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            # Simulated data (replace with real instrument reads later)
            data = {
                "timestamp": t,
                "voltage": 0.5 * (1 + 0.8 * math.sin(t * 0.3)) + random.gauss(0, 0.01),
                "current": 1e-4 * (1 + 0.5 * math.sin(t * 0.3)) + random.gauss(0, 1e-6),
                "resistance": 5000 + 200 * math.sin(t * 0.1) + random.gauss(0, 5),
                "temperature": 300 + 0.5 * math.sin(t * 0.05) + random.gauss(0, 0.1),
                "field": 2000 * math.sin(t * 0.2),
            }
            await websocket.send_json(data)
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, Exception):
        pass


@app.get("/api/health")
async def health():
    """System health check."""
    from lab_harness.planning.plan_builder import TEMPLATES_DIR

    visa_ok = False
    instrument_count = 0
    try:
        import pyvisa

        rm = pyvisa.ResourceManager()
        instrument_count = len(rm.list_resources())
        visa_ok = True
    except Exception:
        pass

    templates = [p.stem for p in TEMPLATES_DIR.glob("*.yaml")]

    return {
        "status": "ok",
        "visa_available": visa_ok,
        "instruments_found": instrument_count,
        "templates_available": len(templates),
        "template_list": templates,
    }


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def run_web(host: str = "127.0.0.1", port: int = 8080):
    """Start the web GUI server."""
    import uvicorn

    print(f"Starting LabAgent at http://{host}:{port}")
    print(f"  Dashboard:  http://{host}:{port}/")
    print(f"  Monitor:    http://{host}:{port}/monitor")
    print(f"  Experiment: http://{host}:{port}/experiment")
    uvicorn.run(app, host=host, port=port)

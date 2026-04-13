"""Web GUI for LabAgent.

Adaptive interface that dynamically generates measurement forms
from YAML templates — supports 46+ measurement types without
hardcoded pages.

HTML templates are in web/templates/:
  dashboard.html — measurement template configurator
  monitor.html   — real-time multi-panel data monitor
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="LabAgent",
    description="Adaptive measurement interface",
    version="0.1.0",
)

TEMPLATES_HTML_DIR = Path(__file__).parent / "templates"


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


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


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
    print(f"  Dashboard: http://{host}:{port}/")
    print(f"  Monitor:   http://{host}:{port}/monitor")
    uvicorn.run(app, host=host, port=port)

"""Web GUI for AI Harness for Lab.

Adaptive interface that dynamically generates measurement forms
from YAML templates — supports 40+ measurement types without
hardcoded pages.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Harness for Lab",
    description="Adaptive measurement interface",
    version="0.1.0",
)

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/api/templates")
async def list_templates():
    """List all available measurement templates grouped by discipline."""
    from lab_harness.planning.plan_builder import TEMPLATES_DIR
    import yaml

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
    from lab_harness.planning.plan_builder import TEMPLATES_DIR
    import yaml

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
    from lab_harness.planning.plan_builder import build_plan_from_template
    from lab_harness.planning.boundary_checker import check_boundaries

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


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the adaptive measurement dashboard."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return _embedded_dashboard()


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    """Serve the multi-panel monitor with user-selectable axes."""
    return _embedded_monitor()


def _embedded_dashboard() -> str:
    """Embedded HTML dashboard — no external files needed."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Harness for Lab</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
.header { background: linear-gradient(135deg, #1e1b4b, #312e81); padding: 24px 32px; border-bottom: 2px solid #4f46e5; }
.header h1 { font-size: 28px; font-weight: 700; }
.header h1 span { color: #a78bfa; }
.header p { color: #94a3b8; margin-top: 4px; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.grid { display: grid; grid-template-columns: 300px 1fr; gap: 24px; }
.sidebar { background: #1e293b; border-radius: 12px; padding: 16px; max-height: calc(100vh - 160px); overflow-y: auto; }
.sidebar h3 { color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin: 16px 0 8px; }
.sidebar h3:first-child { margin-top: 0; }
.template-btn { display: block; width: 100%; text-align: left; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 12px; margin-bottom: 6px; color: #e2e8f0; cursor: pointer; transition: all 0.2s; font-size: 13px; }
.template-btn:hover { border-color: #6366f1; background: #1e1b4b; }
.template-btn.active { border-color: #6366f1; background: #312e81; }
.template-btn .desc { color: #64748b; font-size: 11px; margin-top: 2px; }
.main { background: #1e293b; border-radius: 12px; padding: 24px; }
.main h2 { margin-bottom: 16px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
.field input, .field select { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 8px 12px; color: #e2e8f0; font-size: 14px; }
.field input:focus { outline: none; border-color: #6366f1; }
.safety-box { background: #1c1917; border: 1px solid #854d0e; border-radius: 8px; padding: 12px; margin-top: 16px; }
.safety-box h4 { color: #fbbf24; font-size: 13px; margin-bottom: 8px; }
.safety-box .limit { color: #a3a3a3; font-size: 12px; }
.channels { margin-top: 16px; }
.channel-tag { display: inline-block; background: #312e81; border-radius: 12px; padding: 4px 12px; font-size: 12px; margin: 4px 4px 4px 0; color: #c4b5fd; }
.btn-row { margin-top: 20px; display: flex; gap: 12px; }
.btn { padding: 10px 24px; border-radius: 8px; border: none; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
.btn-primary { background: #6366f1; color: white; }
.btn-primary:hover { background: #4f46e5; }
.btn-secondary { background: #334155; color: #e2e8f0; }
.btn-secondary:hover { background: #475569; }
.status-bar { background: #1e293b; border-radius: 8px; padding: 12px 16px; margin-top: 16px; font-size: 13px; color: #94a3b8; }
.status-bar .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.dot-green { background: #22c55e; }
.dot-red { background: #ef4444; }
.empty-state { text-align: center; padding: 60px; color: #64748b; }
.empty-state h3 { font-size: 18px; margin-bottom: 8px; color: #94a3b8; }
#result { margin-top: 16px; background: #0f172a; border-radius: 8px; padding: 16px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; display: none; white-space: pre-wrap; }
</style>
</head>
<body>
<div class="header">
  <h1><span>AI</span> Harness for Lab</h1>
  <p>Fully Automated Lab Assistant &mdash; Select a measurement template to begin</p>
</div>
<div class="container">
  <div class="grid">
    <div class="sidebar" id="sidebar">
      <p style="color:#64748b;font-size:13px;">Loading templates...</p>
    </div>
    <div class="main" id="main">
      <div class="empty-state">
        <h3>Select a measurement template</h3>
        <p>Choose from the sidebar to configure your measurement</p>
      </div>
    </div>
  </div>
  <div class="status-bar" id="statusBar">
    <span class="dot dot-green"></span> System ready
  </div>
</div>

<script>
let templates = {};
let currentTemplate = null;

async function loadTemplates() {
  const res = await fetch("/api/templates");
  const data = await res.json();
  templates = data.templates;
  renderSidebar();
}

function renderSidebar() {
  const sidebar = document.getElementById("sidebar");
  const groups = {};

  // Group templates by category
  for (const [key, t] of Object.entries(templates)) {
    let cat = "General";
    if (key.startsWith("ppms_") || key.startsWith("mpms_")) cat = "Quantum Design";
    else if (["ahe","mr","sot","hall","fmr","hysteresis","magnetostriction","nernst"].includes(key)) cat = "Magnetic";
    else if (["iv","rt","delta","high_r","transfer","output","breakdown","tunneling"].includes(key)) cat = "Electrical";
    else if (["tc","jc"].includes(key)) cat = "Superconductivity";
    else if (["cv","pe_loop","pyroelectric","capacitance_frequency","dlts","eis"].includes(key)) cat = "Dielectric / Electrochem";
    else if (["seebeck","thermal_conductivity"].includes(key)) cat = "Thermoelectric";
    else if (["photocurrent","photoresponse","photo_iv"].includes(key)) cat = "Optical / Solar";
    else if (["cyclic_voltammetry","chronoamperometry","potentiometry"].includes(key)) cat = "Chemistry";
    else if (["gas_sensor","ph_calibration","humidity_response","impedance_biosensor","cell_counting"].includes(key)) cat = "Sensors / Bio";
    else if (["strain_gauge","fatigue"].includes(key)) cat = "Materials";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push({key, ...t});
  }

  let html = "";
  for (const [cat, items] of Object.entries(groups).sort()) {
    html += `<h3>${cat} (${items.length})</h3>`;
    for (const item of items) {
      html += `<button class="template-btn" onclick="selectTemplate('${item.key}')" id="btn-${item.key}">
        ${item.name}
        <div class="desc">${item.description.substring(0,60)}</div>
      </button>`;
    }
  }
  sidebar.innerHTML = html;
}

async function selectTemplate(key) {
  document.querySelectorAll(".template-btn").forEach(b => b.classList.remove("active"));
  document.getElementById("btn-"+key)?.classList.add("active");

  const res = await fetch(`/api/templates/${key}`);
  currentTemplate = await res.json();
  currentTemplate._key = key;
  renderForm(currentTemplate);
}

function renderForm(t) {
  const main = document.getElementById("main");
  const x = t.x_axis || {};
  const channels = (t.y_channels || []).map(c =>
    `<span class="channel-tag">${c.label} (${c.unit})</span>`
  ).join("");

  let outerHtml = "";
  if (t.outer_sweep) {
    const o = t.outer_sweep;
    outerHtml = `
      <div class="field"><label>Outer: ${o.label} Start (${o.unit})</label><input type="number" value="${o.start}" id="outer_start"></div>
      <div class="field"><label>Outer: ${o.label} Stop (${o.unit})</label><input type="number" value="${o.stop}" id="outer_stop"></div>
      <div class="field"><label>Outer Step (${o.unit})</label><input type="number" value="${o.step}" id="outer_step"></div>
    `;
  }

  main.innerHTML = `
    <h2>${t.name || t._key}</h2>
    <p style="color:#94a3b8;margin-bottom:16px;">${t.description || ""}</p>

    <div class="form-grid">
      <div class="field"><label>X: ${x.label} Start (${x.unit})</label><input type="number" value="${x.start}" id="x_start"></div>
      <div class="field"><label>X: ${x.label} Stop (${x.unit})</label><input type="number" value="${x.stop}" id="x_stop"></div>
      <div class="field"><label>Step (${x.unit})</label><input type="number" value="${x.step}" id="x_step"></div>
      <div class="field"><label>Settling Time (s)</label><input type="number" value="${t.settling_time_s || 0.5}" id="settling"></div>
      <div class="field"><label>Averages</label><input type="number" value="${t.num_averages || 1}" id="averages"></div>
      ${outerHtml}
    </div>

    <div class="channels">
      <label style="font-size:12px;color:#94a3b8;text-transform:uppercase;">Data Channels</label><br>
      ${channels || '<span style="color:#64748b">No channels defined</span>'}
    </div>

    <div class="safety-box">
      <h4>Safety Limits</h4>
      <div class="limit">Max Current: ${t.max_current_a ? (t.max_current_a*1000).toFixed(1)+" mA" : "N/A"}</div>
      <div class="limit">Max Voltage: ${t.max_voltage_v || "N/A"} V</div>
      <div class="limit">Max Field: ${t.max_field_oe ? (t.max_field_oe/1000).toFixed(0)+" kOe" : "N/A"}</div>
      <div class="limit">Max Temperature: ${t.max_temperature_k || "N/A"} K</div>
    </div>

    <div class="btn-row">
      <button class="btn btn-primary" onclick="validatePlan()">Validate Plan</button>
      <button class="btn btn-secondary" onclick="generatePlan()">Generate Plan JSON</button>
    </div>

    <div id="result"></div>
  `;
}

async function validatePlan() {
  if (!currentTemplate) return;
  const overrides = {
    x_axis: {
      start: parseFloat(document.getElementById("x_start").value),
      stop: parseFloat(document.getElementById("x_stop").value),
      step: parseFloat(document.getElementById("x_step").value),
    },
    settling_time_s: parseFloat(document.getElementById("settling").value),
    num_averages: parseInt(document.getElementById("averages").value),
  };
  const res = await fetch("/api/plan?measurement_type=" + currentTemplate._key, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(overrides),
  });
  const data = await res.json();
  const el = document.getElementById("result");
  el.style.display = "block";
  const v = data.validation;
  let color = v.decision === "allow" ? "#22c55e" : v.decision === "require_confirm" ? "#fbbf24" : "#ef4444";
  el.innerHTML = `<span style="color:${color};font-weight:bold;">${v.decision.toUpperCase()}</span>\\n`;
  if (v.warnings?.length) el.innerHTML += "Warnings:\\n" + v.warnings.map(w=>"  - "+w).join("\\n") + "\\n";
  if (v.violations?.length) el.innerHTML += "Violations:\\n" + v.violations.map(v=>"  - "+v.message).join("\\n") + "\\n";
  el.innerHTML += "\\nTotal points: " + data.plan.x_axis.num_points;
  if (v.ai_advice) el.innerHTML += "\\n\\nAI Advice: " + v.ai_advice;
}

async function generatePlan() {
  if (!currentTemplate) return;
  const el = document.getElementById("result");
  el.style.display = "block";
  const res = await fetch(`/api/templates/${currentTemplate._key}`);
  el.textContent = JSON.stringify(await res.json(), null, 2);
}

// Init
loadTemplates();
fetch("/api/health").then(r=>r.json()).then(d=>{
  const bar = document.getElementById("statusBar");
  bar.innerHTML = `<span class="dot ${d.visa_available?'dot-green':'dot-red'}"></span>` +
    `VISA: ${d.visa_available?'Connected':'Not available'} | ` +
    `Instruments: ${d.instruments_found} | ` +
    `Templates: ${d.templates_available}`;
});
</script>
</body>
</html>'''


def _embedded_monitor() -> str:
    """Embedded multi-panel real-time monitor with Genshin-themed design."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Harness for Lab — Monitor</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
/* ── CSS Variables ── */
:root {
  --bg-primary: #0f0f1e;
  --bg-card: #151530;
  --bg-sidebar: #12122a;
  --border-gold: #c8a96e;
  --gold: #c8a96e;
  --gold-dim: #8a7345;
  --gold-glow: rgba(200,169,110,0.3);
  --text-primary: #e8e4dc;
  --text-secondary: #9a9580;
  --electro: #c882ff;
  --cryo: #9cf0ff;
  --pyro: #ff6b4a;
  --hydro: #4cc2ff;
  --dendro: #7bc639;
  --geo: #f0b232;
  --anemo: #74d4a0;
  --font-genshin: 'Cinzel', serif;
}

/* ── Reset & Base ── */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  min-height: 100vh;
  overflow-x: hidden;
}

/* ── Starfield Background ── */
.starfield {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  z-index: 0; pointer-events: none; overflow: hidden;
}
.star {
  position: absolute;
  background: #fff;
  border-radius: 50%;
  animation: twinkle var(--dur) ease-in-out infinite alternate;
}
@keyframes twinkle {
  0% { opacity: var(--op-min); transform: scale(1); }
  100% { opacity: var(--op-max); transform: scale(1.3); }
}

/* ── Layout ── */
.app-wrapper {
  position: relative; z-index: 1;
  display: grid;
  grid-template-rows: auto 1fr;
  grid-template-columns: 260px 1fr;
  grid-template-areas:
    "header header"
    "sidebar main";
  min-height: 100vh;
}

/* ── Header ── */
.header {
  grid-area: header;
  background: linear-gradient(135deg, #1a1640 0%, #0f0f1e 50%, #1a1640 100%);
  border-bottom: 2px solid var(--border-gold);
  padding: 14px 28px;
  display: flex; align-items: center; justify-content: space-between;
  position: relative;
}
.header::before, .header::after {
  content: '';
  position: absolute; width: 24px; height: 24px;
  border-color: var(--gold); border-style: solid;
}
.header::before { top: 6px; left: 6px; border-width: 2px 0 0 2px; }
.header::after { top: 6px; right: 6px; border-width: 2px 2px 0 0; }
.header-left { display: flex; align-items: center; gap: 16px; }
.header h1 {
  font-family: var(--font-genshin);
  font-size: 20px; font-weight: 700;
  color: var(--gold);
  text-shadow: 0 0 20px var(--gold-glow);
  letter-spacing: 2px;
}
.header-badge {
  background: rgba(200,169,110,0.12);
  border: 1px solid var(--gold-dim);
  border-radius: 12px;
  padding: 2px 12px; font-size: 11px;
  color: var(--gold); font-family: var(--font-genshin);
}
.header-right { display: flex; align-items: center; gap: 16px; }
.header-right a {
  color: var(--text-secondary); text-decoration: none; font-size: 13px;
  transition: color 0.2s;
}
.header-right a:hover { color: var(--gold); }
.header-corner-bl, .header-corner-br {
  position: absolute; bottom: -1px; width: 24px; height: 24px;
  border-color: var(--gold); border-style: solid;
}
.header-corner-bl { left: 6px; border-width: 0 0 2px 2px; }
.header-corner-br { right: 6px; border-width: 0 2px 2px 0; }

/* ── Sidebar ── */
.sidebar {
  grid-area: sidebar;
  background: var(--bg-sidebar);
  border-right: 1px solid rgba(200,169,110,0.2);
  overflow-y: auto;
  padding: 0;
}
.sidebar-section {
  border-bottom: 1px solid rgba(200,169,110,0.1);
}
.sidebar-section-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; cursor: pointer;
  font-family: var(--font-genshin); font-size: 11px;
  color: var(--gold); letter-spacing: 1.5px;
  text-transform: uppercase;
  user-select: none;
  transition: background 0.2s;
}
.sidebar-section-header:hover { background: rgba(200,169,110,0.06); }
.sidebar-section-header .chevron {
  transition: transform 0.25s; font-size: 10px; color: var(--gold-dim);
}
.sidebar-section-header.collapsed .chevron { transform: rotate(-90deg); }
.sidebar-section-body { padding: 0 12px 12px 12px; }
.sidebar-section-header.collapsed + .sidebar-section-body { display: none; }

.channel-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 8px; margin-bottom: 2px;
  border-radius: 6px;
  transition: background 0.15s;
}
.channel-row:hover { background: rgba(255,255,255,0.03); }
.channel-label {
  font-size: 12px; color: var(--text-secondary);
  display: flex; align-items: center; gap: 6px;
}
.channel-dot {
  width: 7px; height: 7px; border-radius: 50%;
  display: inline-block; flex-shrink: 0;
}
.channel-value {
  font-family: 'Courier New', monospace;
  font-size: 13px; font-weight: 600;
  text-align: right;
}

/* Sweep progress */
.sweep-progress-wrap { padding: 4px 8px 8px; }
.sweep-progress-label {
  font-size: 11px; color: var(--text-secondary);
  margin-bottom: 4px; display: flex; justify-content: space-between;
}
.sweep-progress-bar {
  height: 6px; background: rgba(200,169,110,0.15);
  border-radius: 3px; overflow: hidden;
}
.sweep-progress-fill {
  height: 100%; border-radius: 3px;
  background: linear-gradient(90deg, var(--gold-dim), var(--gold));
  transition: width 0.4s ease;
}

/* Sidebar buttons */
.sidebar-btn-row {
  padding: 12px 16px; display: flex; gap: 8px;
  border-top: 1px solid rgba(200,169,110,0.1);
}
.btn-stop, .btn-abort {
  flex: 1; padding: 8px; border: none; border-radius: 6px;
  font-size: 12px; font-weight: 600; cursor: pointer;
  font-family: var(--font-genshin); letter-spacing: 1px;
  transition: all 0.2s;
}
.btn-stop {
  background: rgba(200,169,110,0.15); color: var(--gold);
  border: 1px solid var(--gold-dim);
}
.btn-stop:hover { background: rgba(200,169,110,0.25); }
.btn-abort {
  background: rgba(255,107,74,0.15); color: var(--pyro);
  border: 1px solid rgba(255,107,74,0.3);
}
.btn-abort:hover { background: rgba(255,107,74,0.25); }

/* ── Main Content ── */
.main-content {
  grid-area: main;
  padding: 16px;
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 16px;
}

/* ── Metric Cards ── */
.metric-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}
.metric-card {
  background: var(--bg-card);
  border: 1px solid rgba(200,169,110,0.15);
  border-radius: 10px;
  padding: 14px 16px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.metric-card:hover {
  border-color: var(--card-accent, var(--gold-dim));
  box-shadow: 0 0 16px rgba(200,169,110,0.08);
}
.metric-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: var(--card-accent, var(--gold));
  opacity: 0.7;
}
.metric-card-label {
  font-size: 10px; text-transform: uppercase;
  letter-spacing: 1.2px; color: var(--text-secondary);
  font-family: var(--font-genshin);
  margin-bottom: 6px;
}
.metric-card-value {
  font-family: 'Courier New', monospace;
  font-size: 22px; font-weight: 700;
  color: var(--card-accent, var(--text-primary));
  line-height: 1;
}
.metric-card-unit {
  font-size: 12px; color: var(--text-secondary);
  margin-left: 4px; font-weight: 400;
}
.metric-card-delta {
  font-size: 10px; margin-top: 4px;
  color: var(--text-secondary);
}

/* ── Charts Grid ── */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  flex: 1; min-height: 0;
}
.chart-panel {
  background: var(--bg-card);
  border: 1px solid rgba(200,169,110,0.12);
  border-radius: 10px;
  display: flex; flex-direction: column;
  min-height: 280px;
  overflow: hidden;
}
.chart-panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(200,169,110,0.08);
  background: rgba(0,0,0,0.2);
}
.chart-panel-title {
  font-family: var(--font-genshin);
  font-size: 12px; color: var(--gold);
  letter-spacing: 1px;
}
.chart-panel-controls {
  display: flex; gap: 6px; align-items: center;
}
.chart-panel-controls select {
  background: var(--bg-primary); border: 1px solid rgba(200,169,110,0.2);
  border-radius: 4px; padding: 3px 8px;
  color: var(--text-primary); font-size: 11px;
}
.chart-panel-controls label {
  font-size: 10px; color: var(--text-secondary);
}
.chart-panel-body {
  flex: 1; padding: 8px 10px; position: relative;
  min-height: 0;
}
.chart-panel-body canvas { width: 100% !important; height: 100% !important; }

/* ── Extra panel add button ── */
.add-panel-btn {
  background: var(--bg-card);
  border: 2px dashed rgba(200,169,110,0.2);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  min-height: 280px;
  cursor: pointer;
  color: var(--gold-dim);
  font-family: var(--font-genshin);
  font-size: 14px; letter-spacing: 1px;
  transition: all 0.3s;
}
.add-panel-btn:hover {
  border-color: var(--gold);
  color: var(--gold);
  background: rgba(200,169,110,0.04);
}

/* ── Bottom Tabs ── */
.bottom-tabs {
  background: var(--bg-card);
  border: 1px solid rgba(200,169,110,0.12);
  border-radius: 10px;
  min-height: 160px;
  display: flex; flex-direction: column;
}
.tab-bar {
  display: flex;
  border-bottom: 1px solid rgba(200,169,110,0.1);
}
.tab-btn {
  padding: 10px 24px;
  background: none; border: none;
  font-family: var(--font-genshin);
  font-size: 12px; letter-spacing: 1px;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.tab-btn:hover { color: var(--text-primary); }
.tab-btn.active {
  color: var(--gold);
  border-bottom-color: var(--gold);
}
.tab-content {
  flex: 1; padding: 12px 16px;
  overflow-y: auto; max-height: 200px;
}
.tab-pane { display: none; }
.tab-pane.active { display: block; }
.log-line {
  font-family: 'Courier New', monospace;
  font-size: 12px; padding: 2px 0;
  color: var(--text-secondary);
  border-bottom: 1px solid rgba(255,255,255,0.02);
}
.log-line .log-time { color: var(--gold-dim); margin-right: 8px; }
.log-line.log-warn { color: var(--geo); }
.log-line.log-error { color: var(--pyro); }
.log-line.log-ok { color: var(--dendro); }

.status-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 8px;
}
.status-item {
  display: flex; justify-content: space-between;
  padding: 6px 10px; background: rgba(0,0,0,0.2);
  border-radius: 6px; font-size: 12px;
}
.status-item-label { color: var(--text-secondary); }
.status-item-value { color: var(--text-primary); font-family: 'Courier New', monospace; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--gold-dim); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--gold); }

/* ── Responsive ── */
@media (max-width: 900px) {
  .app-wrapper {
    grid-template-columns: 1fr;
    grid-template-areas: "header" "main";
  }
  .sidebar { display: none; }
  .charts-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<!-- Starfield -->
<div class="starfield" id="starfield"></div>

<div class="app-wrapper">

  <!-- Header -->
  <div class="header">
    <div class="header-corner-bl"></div>
    <div class="header-corner-br"></div>
    <div class="header-left">
      <h1>AI Harness &mdash; Monitor</h1>
      <span class="header-badge">LIVE</span>
    </div>
    <div class="header-right">
      <span style="font-size:12px;color:var(--text-secondary);" id="headerClock">--:--:--</span>
      <a href="/">Back to Dashboard</a>
    </div>
  </div>

  <!-- Sidebar -->
  <div class="sidebar">

    <!-- Channels Section -->
    <div class="sidebar-section">
      <div class="sidebar-section-header" onclick="toggleSection(this)">
        <span>Channels</span>
        <span class="chevron">&#9660;</span>
      </div>
      <div class="sidebar-section-body" id="sidebarChannels">
        <!-- populated by JS -->
      </div>
    </div>

    <!-- Sweep Section -->
    <div class="sidebar-section">
      <div class="sidebar-section-header" onclick="toggleSection(this)">
        <span>Sweep</span>
        <span class="chevron">&#9660;</span>
      </div>
      <div class="sidebar-section-body">
        <div class="sweep-progress-wrap">
          <div class="sweep-progress-label">
            <span>Progress</span>
            <span id="sweepPct">0%</span>
          </div>
          <div class="sweep-progress-bar">
            <div class="sweep-progress-fill" id="sweepFill" style="width:0%"></div>
          </div>
        </div>
        <div class="channel-row" style="margin-top:8px;">
          <span class="channel-label">Step</span>
          <span class="channel-value" style="color:var(--text-primary)" id="sweepStep">0 / 0</span>
        </div>
        <div class="channel-row">
          <span class="channel-label">Elapsed</span>
          <span class="channel-value" style="color:var(--text-primary)" id="sweepElapsed">00:00</span>
        </div>
        <div class="channel-row">
          <span class="channel-label">ETA</span>
          <span class="channel-value" style="color:var(--text-primary)" id="sweepEta">--:--</span>
        </div>
      </div>
    </div>

    <!-- Settings Section -->
    <div class="sidebar-section">
      <div class="sidebar-section-header" onclick="toggleSection(this)">
        <span>Settings</span>
        <span class="chevron">&#9660;</span>
      </div>
      <div class="sidebar-section-body">
        <div class="channel-row">
          <span class="channel-label">Refresh Rate</span>
          <select id="refreshRate" style="background:var(--bg-primary);border:1px solid rgba(200,169,110,0.2);border-radius:4px;padding:3px 6px;color:var(--text-primary);font-size:11px;">
            <option value="1000">1 Hz</option>
            <option value="500">2 Hz</option>
            <option value="2000">0.5 Hz</option>
          </select>
        </div>
        <div class="channel-row">
          <span class="channel-label">Max Points</span>
          <input type="number" id="maxPoints" value="200" min="50" max="2000"
            style="width:60px;background:var(--bg-primary);border:1px solid rgba(200,169,110,0.2);border-radius:4px;padding:3px 6px;color:var(--text-primary);font-size:11px;text-align:right;">
        </div>
      </div>
    </div>

    <!-- Control Buttons -->
    <div class="sidebar-btn-row">
      <button class="btn-stop" onclick="togglePause()">&#9646;&#9646; PAUSE</button>
      <button class="btn-abort" onclick="clearAllData()">CLEAR</button>
    </div>
  </div>

  <!-- Main Content -->
  <div class="main-content">

    <!-- Toolbar -->
    <div class="toolbar" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 14px;background:var(--bg-card);border:1px solid rgba(200,169,110,0.12);border-radius:10px;">
      <label style="font-family:var(--font-genshin);font-size:11px;color:var(--gold);letter-spacing:1px;">Template:</label>
      <select id="templateSelect" style="background:var(--bg-primary);border:1px solid rgba(200,169,110,0.2);border-radius:4px;padding:4px 8px;color:var(--text-primary);font-size:12px;min-width:140px;">
        <option value="">-- None --</option>
      </select>
      <div style="border-left:1px solid rgba(200,169,110,0.15);height:24px;margin:0 4px;"></div>
      <button onclick="savePreset()" class="toolbar-btn" style="background:rgba(200,169,110,0.12);border:1px solid var(--gold-dim);border-radius:6px;padding:4px 12px;color:var(--gold);font-size:11px;font-family:var(--font-genshin);letter-spacing:1px;cursor:pointer;">Save Preset</button>
      <select id="presetList" style="background:var(--bg-primary);border:1px solid rgba(200,169,110,0.2);border-radius:4px;padding:4px 8px;color:var(--text-primary);font-size:12px;min-width:120px;">
        <option value="">-- Presets --</option>
      </select>
      <button onclick="loadSelectedPreset()" class="toolbar-btn" style="background:rgba(200,169,110,0.12);border:1px solid var(--gold-dim);border-radius:6px;padding:4px 12px;color:var(--gold);font-size:11px;font-family:var(--font-genshin);letter-spacing:1px;cursor:pointer;">Load</button>
      <button onclick="deleteSelectedPreset()" class="toolbar-btn" style="background:rgba(255,107,74,0.12);border:1px solid rgba(255,107,74,0.3);border-radius:6px;padding:4px 12px;color:var(--pyro);font-size:11px;font-family:var(--font-genshin);letter-spacing:1px;cursor:pointer;">Del</button>
    </div>

    <!-- Metric Cards -->
    <div class="metric-cards" id="metricCards"></div>

    <!-- Charts 2x2 Grid -->
    <div class="charts-grid" id="chartsGrid">
      <!-- Chart 1 -->
      <div class="chart-panel">
        <div class="chart-panel-header">
          <span class="chart-panel-title">Chart 1</span>
          <div class="chart-panel-controls">
            <label>X:</label>
            <select id="chart0_x" onchange="updateChartAxis(0)"></select>
            <label>Y:</label>
            <select id="chart0_y" onchange="updateChartAxis(0)"></select>
          </div>
        </div>
        <div class="chart-panel-body">
          <canvas id="chart0"></canvas>
        </div>
      </div>
      <!-- Chart 2 -->
      <div class="chart-panel">
        <div class="chart-panel-header">
          <span class="chart-panel-title">Chart 2</span>
          <div class="chart-panel-controls">
            <label>X:</label>
            <select id="chart1_x" onchange="updateChartAxis(1)"></select>
            <label>Y:</label>
            <select id="chart1_y" onchange="updateChartAxis(1)"></select>
          </div>
        </div>
        <div class="chart-panel-body">
          <canvas id="chart1"></canvas>
        </div>
      </div>
      <!-- Chart 3 -->
      <div class="chart-panel">
        <div class="chart-panel-header">
          <span class="chart-panel-title">Chart 3</span>
          <div class="chart-panel-controls">
            <label>X:</label>
            <select id="chart2_x" onchange="updateChartAxis(2)"></select>
            <label>Y:</label>
            <select id="chart2_y" onchange="updateChartAxis(2)"></select>
          </div>
        </div>
        <div class="chart-panel-body">
          <canvas id="chart2"></canvas>
        </div>
      </div>
      <!-- Chart 4 -->
      <div class="chart-panel">
        <div class="chart-panel-header">
          <span class="chart-panel-title">Chart 4</span>
          <div class="chart-panel-controls">
            <label>X:</label>
            <select id="chart3_x" onchange="updateChartAxis(3)"></select>
            <label>Y:</label>
            <select id="chart3_y" onchange="updateChartAxis(3)"></select>
          </div>
        </div>
        <div class="chart-panel-body">
          <canvas id="chart3"></canvas>
        </div>
      </div>
    </div>

    <!-- Add Panel Button (outside grid, appended dynamically) -->
    <div style="display:flex;justify-content:center;padding:4px 0;">
      <button class="add-panel-btn" style="min-height:48px;width:100%;max-width:300px;border-radius:8px;"
        onclick="addCustomPanel()">+ Add Panel</button>
    </div>

    <!-- Bottom Tabs -->
    <div class="bottom-tabs">
      <div class="tab-bar">
        <button class="tab-btn active" onclick="switchTab(this,'tabLog')">Log</button>
        <button class="tab-btn" onclick="switchTab(this,'tabStatus')">Status</button>
      </div>
      <div class="tab-content">
        <div class="tab-pane active" id="tabLog"></div>
        <div class="tab-pane" id="tabStatus">
          <div class="status-grid" id="statusGrid"></div>
        </div>
      </div>
    </div>

  </div><!-- /main-content -->
</div><!-- /app-wrapper -->

<script>
/* ═══════════════════════════════════════════
   Configuration & Channel Definitions
   ═══════════════════════════════════════════ */
const CHANNELS = [
  { id:"time",        label:"Time",           unit:"s",   element:"geo"    },
  { id:"voltage",     label:"Voltage",        unit:"V",   element:"electro"},
  { id:"current",     label:"Current",        unit:"A",   element:"electro"},
  { id:"resistance",  label:"Resistance",     unit:"\\u03a9", element:"geo" },
  { id:"temperature", label:"Temperature",    unit:"K",   element:"cryo"   },
  { id:"field",       label:"Magnetic Field", unit:"Oe",  element:"hydro"  },
  { id:"capacitance", label:"Capacitance",    unit:"pF",  element:"dendro" },
  { id:"frequency",   label:"Frequency",      unit:"Hz",  element:"anemo"  },
  { id:"magnetization",label:"Magnetization", unit:"emu", element:"hydro"  },
  { id:"power",       label:"Power",          unit:"W",   element:"pyro"   },
  { id:"hall_voltage", label:"Hall Voltage",  unit:"V",   element:"electro"},
  { id:"seebeck",     label:"Seebeck V",      unit:"\\u03bcV",element:"pyro"},
  { id:"impedance_r", label:"Z Real",         unit:"\\u03a9", element:"geo" },
  { id:"impedance_i", label:"Z Imag",         unit:"\\u03a9", element:"hydro"},
  { id:"pressure",    label:"Pressure",       unit:"Torr",element:"anemo"  },
  { id:"strain",      label:"Strain",         unit:"\\u03bc\\u03b5", element:"geo"},
  { id:"ph",          label:"pH",             unit:"",    element:"dendro" },
];

const ELEMENT_COLORS = {
  electro: "#c882ff",
  cryo:    "#9cf0ff",
  pyro:    "#ff6b4a",
  hydro:   "#4cc2ff",
  dendro:  "#7bc639",
  geo:     "#f0b232",
  anemo:   "#74d4a0",
};

/* Metric cards config: which channels to show as top-line metrics (mutable for template switching) */
let METRIC_DEFS = [
  { ch:"voltage",     element:"electro" },
  { ch:"current",     element:"electro" },
  { ch:"resistance",  element:"geo"     },
  { ch:"temperature", element:"cryo"    },
  { ch:"field",       element:"hydro"   },
  { ch:"power",       element:"pyro"    },
];

/* Default metrics backup */
const DEFAULT_METRIC_DEFS = [...METRIC_DEFS];

/* ═══════════════════════════════════════════
   State
   ═══════════════════════════════════════════ */
let simData = {};          // channel-id -> [values]
let simTime = [];          // time points
let paused = false;
let charts = {};           // chart index -> Chart.js instance
let customPanelCount = 0;
const startTime = Date.now();
let sweepProgress = 0;
let sweepTotal = 200;
let sweepCurrent = 0;

/* ═══════════════════════════════════════════
   Starfield
   ═══════════════════════════════════════════ */
(function createStars() {
  const sf = document.getElementById("starfield");
  for (let i = 0; i < 120; i++) {
    const s = document.createElement("div");
    s.className = "star";
    const size = Math.random() * 2.5 + 0.5;
    s.style.width = size + "px";
    s.style.height = size + "px";
    s.style.left = Math.random() * 100 + "%";
    s.style.top = Math.random() * 100 + "%";
    s.style.setProperty("--dur", (2 + Math.random() * 4) + "s");
    s.style.setProperty("--op-min", (0.1 + Math.random() * 0.2).toFixed(2));
    s.style.setProperty("--op-max", (0.5 + Math.random() * 0.5).toFixed(2));
    s.style.animationDelay = (Math.random() * 5) + "s";
    sf.appendChild(s);
  }
})();

/* ═══════════════════════════════════════════
   Sidebar: Channel Rows
   ═══════════════════════════════════════════ */
function buildSidebarChannels() {
  const el = document.getElementById("sidebarChannels");
  let html = "";
  CHANNELS.forEach(ch => {
    if (ch.id === "time") return;
    const col = ELEMENT_COLORS[ch.element] || "#888";
    html += `<div class="channel-row">
      <span class="channel-label">
        <span class="channel-dot" style="background:${col}"></span>
        ${ch.label}
      </span>
      <span class="channel-value" style="color:${col}" id="side_${ch.id}">--</span>
    </div>`;
  });
  el.innerHTML = html;
}

function toggleSection(header) {
  header.classList.toggle("collapsed");
}

/* ═══════════════════════════════════════════
   Metric Cards
   ═══════════════════════════════════════════ */
function buildMetricCards() {
  const el = document.getElementById("metricCards");
  let html = "";
  METRIC_DEFS.forEach((m, i) => {
    const ch = CHANNELS.find(c => c.id === m.ch);
    if (!ch) return;
    const col = ELEMENT_COLORS[m.element];
    html += `<div class="metric-card" style="--card-accent:${col}">
      <div class="metric-card-label">${ch.label}</div>
      <div class="metric-card-value" id="metric_${ch.id}">--<span class="metric-card-unit">${ch.unit}</span></div>
      <div class="metric-card-delta" id="metricDelta_${ch.id}"></div>
    </div>`;
  });
  el.innerHTML = html;
}

/* ═══════════════════════════════════════════
   Chart.js Helpers
   ═══════════════════════════════════════════ */
const CHART_LINE_COLORS = ["#c882ff","#9cf0ff","#ff6b4a","#4cc2ff","#7bc639","#f0b232","#74d4a0"];

function channelOptions(selectId, defaultVal) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  sel.innerHTML = "";
  CHANNELS.forEach(ch => {
    const opt = document.createElement("option");
    opt.value = ch.id;
    opt.textContent = ch.label + (ch.unit ? " (" + ch.unit + ")" : "");
    if (ch.id === defaultVal) opt.selected = true;
    sel.appendChild(opt);
  });
}

function makeChartConfig(xLabel, yLabel, color) {
  return {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        data: [],
        borderColor: color,
        backgroundColor: color + "18",
        borderWidth: 1.8,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 0 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#151530ee",
          titleColor: "#c8a96e",
          bodyColor: "#e8e4dc",
          borderColor: "#c8a96e44",
          borderWidth: 1,
        }
      },
      scales: {
        x: {
          title: { display: true, text: xLabel, color: "#9a9580", font: { size: 10 } },
          grid: { color: "rgba(200,169,110,0.06)" },
          ticks: { color: "#9a9580", font: { size: 9 }, maxTicksLimit: 8 },
        },
        y: {
          title: { display: true, text: yLabel, color: "#9a9580", font: { size: 10 } },
          grid: { color: "rgba(200,169,110,0.06)" },
          ticks: { color: "#9a9580", font: { size: 9 }, maxTicksLimit: 6 },
        }
      },
      elements: { line: { borderJoinStyle: "round" } },
    }
  };
}

/* Default X/Y selections for the 4 base charts */
const CHART_DEFAULTS = [
  { x: "time", y: "voltage" },
  { x: "time", y: "current" },
  { x: "time", y: "resistance" },
  { x: "field", y: "hall_voltage" },
];

function initCharts() {
  CHART_DEFAULTS.forEach((def, idx) => {
    channelOptions("chart" + idx + "_x", def.x);
    channelOptions("chart" + idx + "_y", def.y);
    const xCh = CHANNELS.find(c => c.id === def.x);
    const yCh = CHANNELS.find(c => c.id === def.y);
    const col = ELEMENT_COLORS[yCh?.element] || CHART_LINE_COLORS[idx % CHART_LINE_COLORS.length];
    charts[idx] = new Chart(
      document.getElementById("chart" + idx),
      makeChartConfig(
        xCh ? xCh.label + " (" + xCh.unit + ")" : def.x,
        yCh ? yCh.label + " (" + yCh.unit + ")" : def.y,
        col
      )
    );
  });
}

function updateChartAxis(idx) {
  const chart = charts[idx];
  if (!chart) return;
  const xId = document.getElementById("chart" + idx + "_x")?.value || "time";
  const yId = document.getElementById("chart" + idx + "_y")?.value || "voltage";
  const yCh = CHANNELS.find(c => c.id === yId);
  const xCh = CHANNELS.find(c => c.id === xId);
  const col = ELEMENT_COLORS[yCh?.element] || "#c882ff";
  chart.data.labels = [];
  chart.data.datasets[0].data = [];
  chart.data.datasets[0].borderColor = col;
  chart.data.datasets[0].backgroundColor = col + "18";
  chart.options.scales.x.title.text = xCh ? xCh.label + " (" + xCh.unit + ")" : xId;
  chart.options.scales.y.title.text = yCh ? yCh.label + " (" + yCh.unit + ")" : yId;
  chart.update("none");
}

/* ═══════════════════════════════════════════
   Custom Panel (+ Add Panel)
   ═══════════════════════════════════════════ */
function addCustomPanel() {
  customPanelCount++;
  const idx = 3 + customPanelCount;
  const grid = document.getElementById("chartsGrid");
  const div = document.createElement("div");
  div.className = "chart-panel";
  div.id = "customPanel_" + idx;
  div.innerHTML = `
    <div class="chart-panel-header">
      <span class="chart-panel-title">Custom ${customPanelCount + 1}</span>
      <div class="chart-panel-controls">
        <label>X:</label>
        <select id="chart${idx}_x" onchange="updateChartAxis(${idx})"></select>
        <label>Y:</label>
        <select id="chart${idx}_y" onchange="updateChartAxis(${idx})"></select>
        <button onclick="removeCustomPanel(${idx})" style="background:none;border:none;color:var(--pyro);cursor:pointer;font-size:14px;margin-left:4px;">&times;</button>
      </div>
    </div>
    <div class="chart-panel-body">
      <canvas id="chart${idx}"></canvas>
    </div>
  `;
  grid.appendChild(div);
  channelOptions("chart" + idx + "_x", "time");
  channelOptions("chart" + idx + "_y", "temperature");
  const chY = CHANNELS.find(c => c.id === "temperature");
  charts[idx] = new Chart(
    document.getElementById("chart" + idx),
    makeChartConfig("Time (s)", chY.label + " (" + chY.unit + ")", ELEMENT_COLORS[chY.element])
  );
}

function removeCustomPanel(idx) {
  const el = document.getElementById("customPanel_" + idx);
  if (el) el.remove();
  if (charts[idx]) { charts[idx].destroy(); delete charts[idx]; }
}

/* ═══════════════════════════════════════════
   Tabs
   ═══════════════════════════════════════════ */
function switchTab(btn, paneId) {
  btn.parentElement.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  btn.closest(".bottom-tabs").querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
  document.getElementById(paneId).classList.add("active");
}

/* ═══════════════════════════════════════════
   Logging
   ═══════════════════════════════════════════ */
let logLines = [];
function addLog(msg, level) {
  const now = new Date();
  const ts = now.toTimeString().substring(0, 8);
  const cls = level === "warn" ? "log-warn" : level === "error" ? "log-error" : level === "ok" ? "log-ok" : "";
  logLines.push({ ts, msg, cls });
  if (logLines.length > 200) logLines.shift();
  const el = document.getElementById("tabLog");
  // append only the latest
  el.innerHTML += `<div class="log-line ${cls}"><span class="log-time">${ts}</span>${msg}</div>`;
  el.scrollTop = el.scrollHeight;
}

/* ═══════════════════════════════════════════
   Status Tab
   ═══════════════════════════════════════════ */
function updateStatusTab() {
  const el = document.getElementById("statusGrid");
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
  const totalPts = simTime.length;
  el.innerHTML = `
    <div class="status-item"><span class="status-item-label">Uptime</span><span class="status-item-value">${formatTime(parseInt(elapsed))}</span></div>
    <div class="status-item"><span class="status-item-label">Data Points</span><span class="status-item-value">${totalPts}</span></div>
    <div class="status-item"><span class="status-item-label">Channels</span><span class="status-item-value">${CHANNELS.length - 1}</span></div>
    <div class="status-item"><span class="status-item-label">Refresh</span><span class="status-item-value">${document.getElementById("refreshRate").value} ms</span></div>
    <div class="status-item"><span class="status-item-label">Sweep</span><span class="status-item-value">${sweepCurrent} / ${sweepTotal}</span></div>
    <div class="status-item"><span class="status-item-label">Status</span><span class="status-item-value" style="color:${paused?"var(--geo)":"var(--dendro)"}">${paused?"PAUSED":"RUNNING"}</span></div>
  `;
}

function formatTime(s) {
  const m = Math.floor(s / 60);
  const ss = s % 60;
  return (m < 10 ? "0" : "") + m + ":" + (ss < 10 ? "0" : "") + ss;
}

/* ═══════════════════════════════════════════
   Clock
   ═══════════════════════════════════════════ */
function updateClock() {
  document.getElementById("headerClock").textContent = new Date().toTimeString().substring(0, 8);
}

/* ═══════════════════════════════════════════
   Pause / Clear
   ═══════════════════════════════════════════ */
function togglePause() {
  paused = !paused;
  const btn = document.querySelector(".btn-stop");
  if (paused) {
    btn.innerHTML = "&#9654; RESUME";
    addLog("Data acquisition paused", "warn");
  } else {
    btn.innerHTML = "&#9646;&#9646; PAUSE";
    addLog("Data acquisition resumed", "ok");
  }
}

function clearAllData() {
  for (const chId in simData) simData[chId] = [];
  simTime = [];
  sweepCurrent = 0;
  for (const idx in charts) {
    charts[idx].data.labels = [];
    charts[idx].data.datasets[0].data = [];
    charts[idx].update("none");
  }
  addLog("All data cleared", "warn");
}

/* ═══════════════════════════════════════════
   Simulation (Demo Data)
   ═══════════════════════════════════════════ */
function initSimData() {
  CHANNELS.forEach(ch => { simData[ch.id] = []; });
}

function generatePoint() {
  const maxPts = parseInt(document.getElementById("maxPoints").value) || 200;
  const t = (Date.now() - startTime) / 1000;
  sweepCurrent++;
  if (sweepCurrent > sweepTotal) sweepCurrent = 1;

  simTime.push(t);
  if (simTime.length > maxPts) simTime.shift();

  // Realistic-ish simulated values
  const noise = () => (Math.random() - 0.5) * 0.02;
  const vals = {
    time:        t,
    voltage:     0.5 * Math.sin(t * 0.3) + 1.2 + noise(),
    current:     (0.5 * Math.sin(t * 0.3) + 1.2) / 1000 + noise() * 0.001,
    resistance:  1200 + 50 * Math.sin(t * 0.1) + noise() * 10,
    temperature: 300 + 0.5 * Math.sin(t * 0.02) + noise() * 0.2,
    field:       5000 * Math.sin(t * 0.05),
    capacitance: 47.3 + 0.2 * Math.cos(t * 0.15) + noise() * 0.1,
    frequency:   1000,
    magnetization: 0.003 * Math.tanh(5000 * Math.sin(t * 0.05) / 3000) + noise() * 0.0002,
    power:       0.0006 + noise() * 0.0001,
    hall_voltage: 5e-5 * 5000 * Math.sin(t * 0.05) + noise() * 0.001,
    seebeck:     -42 + 0.5 * Math.sin(t * 0.08) + noise() * 0.3,
    impedance_r: 500 + 20 * Math.cos(t * 0.12) + noise() * 5,
    impedance_i: -120 + 10 * Math.sin(t * 0.12) + noise() * 3,
    pressure:    5e-6 + noise() * 1e-7,
    strain:      120 + 5 * Math.sin(t * 0.07) + noise() * 2,
    ph:          7.0 + 0.1 * Math.sin(t * 0.04) + noise() * 0.02,
  };

  for (const chId in vals) {
    if (!simData[chId]) simData[chId] = [];
    simData[chId].push(vals[chId]);
    if (simData[chId].length > maxPts) simData[chId].shift();
  }

  return vals;
}

function formatValue(val, chId) {
  if (val === undefined || val === null) return "--";
  const abs = Math.abs(val);
  if (abs === 0) return "0.000";
  if (abs >= 1e6) return (val / 1e6).toFixed(3) + "M";
  if (abs >= 1e3) return (val / 1e3).toFixed(3) + "k";
  if (abs >= 1)   return val.toFixed(4);
  if (abs >= 1e-3) return (val * 1e3).toFixed(3) + "m";
  if (abs >= 1e-6) return (val * 1e6).toFixed(3) + "\\u03bc";
  return val.toExponential(3);
}

/* ═══════════════════════════════════════════
   Template Selector
   ═══════════════════════════════════════════ */
const ELEMENT_CYCLE = ["electro","cryo","pyro","hydro","dendro","geo","anemo"];

async function loadTemplateList() {
  try {
    const res = await fetch("/api/templates");
    const data = await res.json();
    const sel = document.getElementById("templateSelect");
    if (!sel) return;
    for (const [key, info] of Object.entries(data.templates || {})) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = info.name || key;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", function() {
      if (this.value) {
        applyTemplate(this.value);
      } else {
        resetToDefaults();
      }
    });
  } catch(e) {
    addLog("Could not fetch templates: " + e.message, "warn");
  }
}

async function applyTemplate(templateKey) {
  try {
    const res = await fetch("/api/templates/" + templateKey);
    const tpl = await res.json();
    if (tpl.error) {
      addLog("Template error: " + tpl.error, "error");
      return;
    }
    addLog("Applying template: " + (tpl.name || templateKey), "ok");

    // Build metric defs from template channels
    const yChannels = tpl.y_channels || [];
    const xAxis = tpl.x_axis || {};
    const newMetrics = [];

    // Add x_axis channel if it maps to a known CHANNELS entry
    if (xAxis.label) {
      const xMatch = CHANNELS.find(c => c.label.toLowerCase() === xAxis.label.toLowerCase()
        || c.id === (xAxis.label || "").toLowerCase().replace(/[\\s_]+/g, "_"));
      if (xMatch) {
        newMetrics.push({ ch: xMatch.id, element: ELEMENT_CYCLE[newMetrics.length % ELEMENT_CYCLE.length] });
      }
    }

    // Add y_channels
    yChannels.forEach((yCh, i) => {
      // Try to match by label or by constructing an ID
      const yLabel = (yCh.label || "").toLowerCase();
      const yId = yLabel.replace(/[\\s]+/g, "_");
      let match = CHANNELS.find(c => c.id === yId || c.label.toLowerCase() === yLabel);
      if (match) {
        newMetrics.push({ ch: match.id, element: match.element || ELEMENT_CYCLE[(newMetrics.length) % ELEMENT_CYCLE.length] });
      }
    });

    if (newMetrics.length > 0) {
      METRIC_DEFS = newMetrics;
      buildMetricCards();
    }

    // Set chart defaults based on template
    // Chart 1: x_axis vs first y_channel
    // Chart 2: x_axis vs second y_channel (if available)
    // Chart 3: time vs first y_channel
    // Chart 4: custom (keep as-is or x_axis vs last y_channel)
    const xId = findChannelId(xAxis.label) || "time";
    const yIds = yChannels.map(yc => findChannelId(yc.label)).filter(Boolean);

    const chartAssignments = [
      { x: xId, y: yIds[0] || "voltage" },
      { x: xId, y: yIds[1] || yIds[0] || "current" },
      { x: "time", y: yIds[0] || "resistance" },
      { x: xId, y: yIds[yIds.length - 1] || "hall_voltage" },
    ];

    chartAssignments.forEach((def, idx) => {
      const xSel = document.getElementById("chart" + idx + "_x");
      const ySel = document.getElementById("chart" + idx + "_y");
      if (xSel) xSel.value = def.x;
      if (ySel) ySel.value = def.y;
      updateChartAxis(idx);
    });

    addLog("Template applied — " + newMetrics.length + " metric cards, " + yChannels.length + " y-channels", "ok");
  } catch(e) {
    addLog("Failed to apply template: " + e.message, "error");
  }
}

function findChannelId(label) {
  if (!label) return null;
  const lower = label.toLowerCase();
  const id = lower.replace(/[\\s]+/g, "_");
  const match = CHANNELS.find(c => c.id === id || c.label.toLowerCase() === lower);
  return match ? match.id : null;
}

function resetToDefaults() {
  METRIC_DEFS = [...DEFAULT_METRIC_DEFS];
  buildMetricCards();
  CHART_DEFAULTS.forEach((def, idx) => {
    const xSel = document.getElementById("chart" + idx + "_x");
    const ySel = document.getElementById("chart" + idx + "_y");
    if (xSel) xSel.value = def.x;
    if (ySel) ySel.value = def.y;
    updateChartAxis(idx);
  });
  addLog("Reset to default configuration", "ok");
}

/* ═══════════════════════════════════════════
   Preset Save / Load (localStorage)
   ═══════════════════════════════════════════ */
function savePreset() {
  const name = prompt("Preset name:");
  if (!name) return;
  const config = {
    template: document.getElementById("templateSelect")?.value || "",
    charts: [0,1,2,3].map(i => ({
      x: document.getElementById("chart" + i + "_x")?.value || "time",
      y: document.getElementById("chart" + i + "_y")?.value || "voltage",
    })),
    refreshRate: document.getElementById("refreshRate").value,
    maxPoints: document.getElementById("maxPoints").value,
    metricDefs: METRIC_DEFS.map(m => ({ ch: m.ch, element: m.element })),
  };
  const presets = JSON.parse(localStorage.getItem("labharness_presets") || "{}");
  presets[name] = config;
  localStorage.setItem("labharness_presets", JSON.stringify(presets));
  updatePresetList();
  addLog("Preset saved: " + name, "ok");
}

function loadPreset(name) {
  const presets = JSON.parse(localStorage.getItem("labharness_presets") || "{}");
  const config = presets[name];
  if (!config) { addLog("Preset not found: " + name, "error"); return; }

  // Apply template selector
  const tplSel = document.getElementById("templateSelect");
  if (tplSel && config.template) {
    tplSel.value = config.template;
  } else if (tplSel) {
    tplSel.value = "";
  }

  // Apply metric defs
  if (config.metricDefs && config.metricDefs.length > 0) {
    METRIC_DEFS = config.metricDefs;
    buildMetricCards();
  }

  // Apply chart axes
  if (config.charts) {
    config.charts.forEach((c, idx) => {
      const xSel = document.getElementById("chart" + idx + "_x");
      const ySel = document.getElementById("chart" + idx + "_y");
      if (xSel) xSel.value = c.x;
      if (ySel) ySel.value = c.y;
      updateChartAxis(idx);
    });
  }

  // Apply refresh rate
  if (config.refreshRate) {
    const rr = document.getElementById("refreshRate");
    if (rr) {
      rr.value = config.refreshRate;
      clearInterval(simInterval);
      simInterval = setInterval(updateAll, parseInt(config.refreshRate));
    }
  }

  // Apply max points
  if (config.maxPoints) {
    const mp = document.getElementById("maxPoints");
    if (mp) mp.value = config.maxPoints;
  }

  addLog("Preset loaded: " + name, "ok");
}

function loadSelectedPreset() {
  const sel = document.getElementById("presetList");
  if (sel && sel.value) loadPreset(sel.value);
}

function deleteSelectedPreset() {
  const sel = document.getElementById("presetList");
  if (!sel || !sel.value) return;
  const name = sel.value;
  const presets = JSON.parse(localStorage.getItem("labharness_presets") || "{}");
  delete presets[name];
  localStorage.setItem("labharness_presets", JSON.stringify(presets));
  updatePresetList();
  addLog("Preset deleted: " + name, "warn");
}

function updatePresetList() {
  const sel = document.getElementById("presetList");
  if (!sel) return;
  const presets = JSON.parse(localStorage.getItem("labharness_presets") || "{}");
  sel.innerHTML = '<option value="">-- Presets --</option>';
  for (const name of Object.keys(presets).sort()) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  }
}

/* ═══════════════════════════════════════════
   Main Update Loop
   ═══════════════════════════════════════════ */
function updateAll() {
  if (paused) return;

  const vals = generatePoint();
  const maxPts = parseInt(document.getElementById("maxPoints").value) || 200;

  // Sidebar channel values
  CHANNELS.forEach(ch => {
    if (ch.id === "time") return;
    const el = document.getElementById("side_" + ch.id);
    if (el) el.textContent = formatValue(vals[ch.id], ch.id) + " " + ch.unit;
  });

  // Metric cards
  METRIC_DEFS.forEach(m => {
    const el = document.getElementById("metric_" + m.ch);
    const ch = CHANNELS.find(c => c.id === m.ch);
    if (el && ch) {
      el.innerHTML = formatValue(vals[m.ch], m.ch) + '<span class="metric-card-unit">' + ch.unit + '</span>';
    }
    // Delta
    const dEl = document.getElementById("metricDelta_" + m.ch);
    if (dEl && simData[m.ch] && simData[m.ch].length > 2) {
      const prev = simData[m.ch][simData[m.ch].length - 2];
      const delta = vals[m.ch] - prev;
      const sign = delta >= 0 ? "+" : "";
      dEl.textContent = sign + delta.toExponential(2) + " /step";
    }
  });

  // Sweep progress
  sweepProgress = (sweepCurrent / sweepTotal) * 100;
  document.getElementById("sweepFill").style.width = sweepProgress.toFixed(1) + "%";
  document.getElementById("sweepPct").textContent = sweepProgress.toFixed(1) + "%";
  document.getElementById("sweepStep").textContent = sweepCurrent + " / " + sweepTotal;

  const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
  document.getElementById("sweepElapsed").textContent = formatTime(elapsedSec);
  if (sweepCurrent > 0) {
    const etaSec = Math.floor(elapsedSec / sweepCurrent * (sweepTotal - sweepCurrent));
    document.getElementById("sweepEta").textContent = formatTime(etaSec);
  }

  // Update charts — all charts use the same X/Y selector logic
  const timeLabels = simTime.map(t => t.toFixed(1));
  const maxChartIdx = Math.max(3, 3 + customPanelCount);
  for (let idx = 0; idx <= maxChartIdx; idx++) {
    if (!charts[idx]) continue;
    const cx = document.getElementById("chart" + idx + "_x")?.value || "time";
    const cy = document.getElementById("chart" + idx + "_y")?.value || "voltage";
    if (cx === "time") {
      charts[idx].config.type = "line";
      charts[idx].data.labels = timeLabels;
      charts[idx].data.datasets[0].data = simData[cy]?.slice() || [];
      charts[idx].data.datasets[0].showLine = undefined;
    } else {
      const cxd = simData[cx] || [];
      const cyd = simData[cy] || [];
      charts[idx].config.type = "scatter";
      charts[idx].data.labels = [];
      charts[idx].data.datasets[0].data = cxd.map((xv, i) => ({ x: xv, y: cyd[i] || 0 }));
      charts[idx].data.datasets[0].showLine = true;
    }
    charts[idx].update("none");
  }

  // Status tab
  updateStatusTab();
}

/* ═══════════════════════════════════════════
   Init
   ═══════════════════════════════════════════ */
initSimData();
buildSidebarChannels();
buildMetricCards();
initCharts();
updateClock();
setInterval(updateClock, 1000);

// Load template list and preset list
loadTemplateList();
updatePresetList();

// Initial log entries
addLog("Monitor initialized", "ok");
addLog("Channels configured: " + (CHANNELS.length - 1), "");
addLog("Demo mode active -- simulated data", "warn");

// Main loop
let simInterval = setInterval(updateAll, 1000);
document.getElementById("refreshRate").addEventListener("change", function() {
  clearInterval(simInterval);
  simInterval = setInterval(updateAll, parseInt(this.value));
  addLog("Refresh rate changed to " + this.value + " ms", "");
});

// Resize
window.addEventListener("resize", () => {
  for (const idx in charts) charts[idx]?.resize();
});
</script>
</body>
</html>'''


# CLI integration
def run_web(host: str = "127.0.0.1", port: int = 8080):
    """Start the web GUI server."""
    import uvicorn
    print(f"Starting AI Harness for Lab at http://{host}:{port}")
    print(f"  Dashboard: http://{host}:{port}/")
    print(f"  Monitor:   http://{host}:{port}/monitor")
    uvicorn.run(app, host=host, port=port)

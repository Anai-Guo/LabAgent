# GUI Development Guide

> For AI assistants and developers who need to modify the Web GUI.

## Architecture Overview

The Web GUI is a **single-file embedded HTML application** inside
`src/lab_harness/web/app.py`. There are NO external HTML/CSS/JS files —
everything is returned as a Python string from two functions:

```
_embedded_dashboard()  → GET /       (measurement template configurator)
_embedded_monitor()    → GET /monitor (real-time data monitoring)
```

### Why Single-File?

- Zero static file dependencies — works anywhere Python runs
- No build step (no webpack, no npm)
- Easy to modify — just edit the Python string
- Keeps deployment simple — `pip install` and done

### Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | FastAPI | API endpoints in `app.py` |
| Charts | Chart.js 4.x | Loaded from CDN |
| Styling | Inline CSS | Genshin-inspired dark theme |
| State | JavaScript + localStorage | Presets saved locally |
| Data | Simulated | Replace with real WebSocket in production |

## File Structure

```
src/lab_harness/web/
  __init__.py
  app.py          ← Everything is here
    ├── API endpoints (lines ~27-120)
    │   GET /api/templates
    │   GET /api/templates/{type}
    │   GET /api/instruments
    │   POST /api/plan
    │   GET /api/health
    │
    ├── _embedded_dashboard() (lines ~130-360)
    │   Template configurator page
    │
    └── _embedded_monitor() (lines ~365-end)
        Real-time monitoring page
```

## How to Modify the Monitor Page

### Adding a New Data Channel

1. Find the `CHANNELS` array in the JavaScript section of `_embedded_monitor()`:
```javascript
const CHANNELS = [
  {id:"time", label:"Time", unit:"s", element:"geo"},
  {id:"voltage", label:"Voltage", unit:"V", element:"hydro"},
  // ... add your new channel here:
  {id:"my_new_channel", label:"My Sensor", unit:"mV", element:"dendro"},
];
```

2. The channel automatically appears in:
   - Chart X/Y axis dropdowns
   - Metric card options
   - Sidebar channel list

3. Add simulated data in the `simulateData()` function:
```javascript
newPoint.my_new_channel = Math.random() * 100;
```

### Adding a New Metric Card

Metric cards are driven by `METRIC_DEFS` array. To add one:
```javascript
METRIC_DEFS.push({ch: "my_new_channel", element: "dendro"});
renderMetricCards();
```

Or let the template selector handle it automatically — when a user
selects a template, `applyTemplate()` rebuilds metric cards from
the template's `y_channels`.

### Changing the Color Scheme

All colors are CSS variables at the top of the `<style>` block:
```css
:root {
  --bg-primary: #0f0f1e;    /* Main background */
  --bg-card: #151530;        /* Card background */
  --border-gold: #c8a96e;    /* Gold accent border */
  --electro: #c882ff;        /* Purple (electrical) */
  --cryo: #9cf0ff;           /* Blue (cryo/temperature) */
  --pyro: #ff6b4a;           /* Red (warning/thermal) */
  --hydro: #4cc2ff;          /* Blue (voltage/current) */
  --dendro: #7bc639;         /* Green (bio/chem) */
  --geo: #f0b232;            /* Gold (field/mechanical) */
}
```

### Adding a New Chart Panel

The `addPanel()` function creates a new chart dynamically.
Each chart gets:
- Unique canvas element
- X/Y dropdown selectors
- Close button
- Its own data buffer

To add a chart programmatically:
```javascript
addPanel("field", "resistance");  // X=field, Y=resistance
```

### Template-Driven Configuration

When user selects a measurement template:
1. `applyTemplate(key)` fetches `/api/templates/{key}`
2. Extracts `x_axis` and `y_channels` from the YAML
3. Rebuilds `METRIC_DEFS` to show relevant channels
4. Sets chart defaults (Chart 0 → template's primary sweep)
5. Metric cards auto-update with template-specific channels

To add template awareness for a new measurement type, just create
the YAML template in `src/lab_harness/planning/templates/`. The GUI
picks it up automatically — no code changes needed.

### Presets System

Users can save/load monitor configurations:
```javascript
// Save
savePreset();  // Prompts for name, stores in localStorage

// Load
loadPreset("my_ahe_setup");

// Data structure stored:
{
  template: "ahe",
  charts: [{x:"field", y:"hall_voltage"}, ...],
  refreshRate: "500",
  maxPoints: "300",
  metricDefs: [{ch:"voltage", element:"hydro"}, ...]
}
```

Storage key: `labharness_presets` in `localStorage`.

## How to Connect Real Data

Currently the monitor uses `simulateData()` for demo purposes.
To connect real instruments:

### Option 1: WebSocket (Recommended)

1. Add a WebSocket endpoint to `app.py`:
```python
@app.websocket("/ws/data")
async def ws_data(websocket: WebSocket):
    await websocket.accept()
    while True:
        # Read from instruments
        data = read_all_channels()
        await websocket.send_json(data)
        await asyncio.sleep(0.5)
```

2. In the monitor JavaScript, replace `simulateData()`:
```javascript
const ws = new WebSocket("ws://" + location.host + "/ws/data");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Update charts and metrics with real data
  pushDataPoint(data);
};
```

### Option 2: Polling

Replace `setInterval(simulateData, ...)` with:
```javascript
async function fetchData() {
  const res = await fetch("/api/live-data");
  const data = await res.json();
  pushDataPoint(data);
}
setInterval(fetchData, parseInt(refreshRate));
```

## Common Modification Patterns

### "I want to change the chart colors"

In `initCharts()`, modify the `borderColor` and `backgroundColor`:
```javascript
borderColor: "rgba(200, 130, 255, 1)",  // Change this
backgroundColor: "rgba(200, 130, 255, 0.1)",
```

### "I want more than 4 default charts"

In the HTML section, add more `<div class="chart-panel">` blocks.
In `initCharts()`, extend the `CHART_DEFAULTS` array.

### "I want to change the sidebar layout"

The sidebar HTML is in the `<div class="sidebar">` section.
Add new `<div class="sidebar-section">` blocks for new groups.

### "I want to add a control panel (not just monitoring)"

Add a new route and function:
```python
@app.get("/control", response_class=HTMLResponse)
async def control_page():
    return _embedded_control_panel()
```

Then create `_embedded_control_panel()` with forms for instrument
control (set current, set temperature, etc.).

## Testing the GUI

```bash
# Install web dependencies
pip install -e ".[web]"

# Start the server
labharness web --port 8080

# Open in browser
# Dashboard: http://localhost:8080/
# Monitor:   http://localhost:8080/monitor
```

No automated GUI tests — verify visually in browser.

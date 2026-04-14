# Web GUI

LabAgent includes a browser-based interface with two main views: a **Dashboard** for configuring and launching measurements, and a **Monitor** for real-time data visualization. The GUI is built on FastAPI and uses WebSocket streaming for live updates.

## Getting Started

```bash
# Start the web server
labharness web

# Custom host and port
labharness web --host 0.0.0.0 --port 9090
```

Open your browser to `http://localhost:8080` (default). The server provides:

- **Dashboard** at `/` -- measurement template configurator
- **Monitor** at `/monitor` -- real-time multi-panel data display
- **REST API** at `/api/...` -- programmatic access to all features
- **WebSocket** at `/ws/stream` -- live data streaming

## Dashboard (Template Configurator)

The dashboard provides an adaptive measurement configuration interface. Rather than having a separate page for each of the 46 measurement types, a single form dynamically reconfigures itself based on the selected template.

### How It Works

1. Select a measurement type from the dropdown (all 46 templates available)
2. The form loads the template's parameters: sweep axis (start/stop/step), data channels, safety limits
3. Adjust parameters as needed -- the form validates inputs against safety boundaries in real time
4. Optionally provide a sample description for AI parameter optimization
5. Submit to generate and validate the measurement plan

The dashboard calls the `/api/configure` endpoint, which:

- Builds a plan from the selected template with your overrides
- Runs the boundary checker to validate safety
- Returns the full plan and validation result
- Displays warnings or blocks unsafe configurations before any instrument communication

### Template Browser

The `/api/templates` endpoint lists all available measurement templates grouped by discipline, with their descriptions, sweep axis definitions, and data channels. The `/api/templates/{type}` endpoint returns the full YAML configuration for a specific template.

## Monitor (Real-Time Charts)

The monitor view displays live instrument readings in a multi-panel layout. Each panel shows a streaming chart for a different measured quantity.

### Default Panels

| Panel | Quantity | Typical Use |
|-------|----------|-------------|
| Voltage | V | Sample voltage during sweep |
| Current | A | Source current readback |
| Resistance | Ohm | Computed R = V/I |
| Temperature | K | Cryostat or sample temperature |
| Field | Oe | Magnetic field from gaussmeter |

### WebSocket Streaming

The monitor connects to `/ws/stream` via WebSocket for sub-second data updates. The server pushes JSON objects at ~2 Hz (configurable) with all measured quantities:

```json
{
  "timestamp": 12.5,
  "voltage": 0.4523,
  "current": 0.000105,
  "resistance": 4307.14,
  "temperature": 300.12,
  "field": 1250.0
}
```

The WebSocket connection handles disconnects gracefully -- the monitor automatically reconnects if the connection drops.

## REST API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard HTML page |
| GET | `/monitor` | Monitor HTML page |
| GET | `/api/templates` | List all templates with metadata |
| GET | `/api/templates/{type}` | Get full template configuration |
| GET | `/api/instruments` | Scan connected instruments |
| POST | `/api/plan` | Generate plan from template |
| POST | `/api/configure` | Configure measurement with validation |
| WS | `/ws/stream` | Real-time data streaming |
| GET | `/api/health` | System health check |

### Health Check

The `/api/health` endpoint reports:

- Whether PyVISA is available
- Number of connected instruments
- Number and list of available measurement templates

This is useful for verifying that the system is properly configured before starting measurements.

## Terminal Panel (TUI)

For users who prefer a terminal-based interface, LabAgent also offers a Textual-based TUI panel that provides a conversational interface for experiment control:

```bash
# Requires the tui extra
pip install "lab-agent[tui]"
labharness panel
```

The terminal panel supports interactive chat with the LabAgent, allowing you to issue commands, ask questions about your data, and monitor measurements without leaving the terminal.

## Presets and Configuration

The web GUI reads measurement presets directly from the YAML template files. Any changes to templates in `src/lab_harness/planning/templates/` are immediately reflected in the dashboard dropdown without server restart.

Safety validation in the GUI uses the same `check_boundaries()` function as the CLI and Python API, ensuring consistent safety behavior across all interfaces.

## Architecture

The web layer is intentionally thin -- it delegates all logic to the core modules:

- **Plan building** -- `lab_harness.planning.plan_builder`
- **Safety validation** -- `lab_harness.planning.boundary_checker`
- **Instrument scanning** -- `lab_harness.discovery.visa_scanner`
- **Data streaming** -- direct instrument reads (simulated in development mode)

This means the web GUI and the CLI/MCP interfaces always produce identical results for the same inputs. For details on the CLI commands and MCP tool interface, see the [AI Guide](https://github.com/Anai-Guo/LabAgent/blob/main/AI_GUIDE.md).

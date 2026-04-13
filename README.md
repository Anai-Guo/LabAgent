<p align="center">
  <img src="assets/hero.svg" alt="AI Harness for Lab — Fully Automated Lab Assistant" width="700">
</p>

<p align="center">
  <a href="https://github.com/Anai-Guo/AIharnessforlab/actions/workflows/ci.yml"><img src="https://github.com/Anai-Guo/AIharnessforlab/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/tests-94%20passed-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/templates-46-orange.svg" alt="Templates">
  <img src="https://img.shields.io/badge/AI%20models-6%20providers-purple.svg" alt="Models">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
</p>

---

## The Problem

Most research labs have powerful instruments but terrible automation software. Researchers waste weeks writing one-off LabVIEW scripts or Python wrappers for every new measurement, with no safety net when things go wrong. When a student graduates, their measurement code leaves with them.

## The Solution

**AI Harness for Lab** is an open-source framework that connects AI to your lab instruments. Tell it what you want to measure, and it handles the rest:

- **Searches the literature** for proven measurement protocols before you start
- **Scans your lab** and identifies every connected instrument automatically
- **Maps instruments to roles** using AI classification of unknown devices
- **Generates measurement plans** with 3-tier safety boundaries that protect your samples
- **Analyzes your data** and explains the physics with publication-ready figures

## Quick Start

```bash
pip install git+https://github.com/Anai-Guo/AIharnessforlab.git

# Scan your lab instruments
labharness scan

# Generate a measurement plan with safety checks
labharness propose AHE

# Launch the adaptive Web GUI
labharness web
```

## Features at a Glance

| Feature | Details |
|---------|---------|
| **46 Measurement Templates** | Ready-to-use YAML templates across 9 scientific disciplines |
| **AI at Every Step** | 8 AI capabilities: classification, optimization, safety advisory, script generation, result interpretation, skill generation, agent chat, experiment memory |
| **Adaptive Web GUI** | Real-time dashboard and multi-panel monitor that dynamically generates forms from templates — no hardcoded pages |
| **6 AI Model Providers** | Claude, GPT-4o, Gemini, Ollama, vLLM, DeepSeek — switch with one config line |
| **Safety-First Design** | 3-tier boundary validation (block / require confirmation / allow) prevents dangerous configurations |
| **Instrument Drivers** | GPIB, USB, and serial instrument scanning with auto-retry and AI-powered classification of unknown devices |
| **Experiment Memory** | SQLite + FTS5 full-text search remembers your successful parameters and learns from history |
| **MCP Server** | Expose all tools to Claude Code, Cursor, or any MCP-compatible AI IDE |

<p align="center">
  <img src="assets/workflow.svg" alt="How it works" width="750">
</p>

## Web GUI

Start the adaptive measurement interface with a single command:

```bash
labharness web --port 8080
```

- **Dashboard** (`/`) — Browse all 46 templates grouped by discipline, configure sweep parameters, set safety limits, and generate validated measurement plans
- **Monitor** (`/monitor`) — Multi-panel real-time data display with user-selectable X/Y axes and WebSocket streaming

The GUI dynamically generates measurement forms from YAML templates. Adding a new template file automatically makes it available in the web interface — no frontend code changes needed.

## Supported Disciplines

| Discipline | Count | Example Measurements |
|-----------|:-----:|---------------------|
| Electrical Characterization | 7 | IV curve, R-T, delta mode, high resistance, FET transfer/output, breakdown |
| Magnetic Measurements | 8 | AHE, magnetoresistance, SOT loop shift, Hall effect, FMR, hysteresis, magnetostriction, Nernst |
| Thermoelectric | 2 | Seebeck coefficient, thermal conductivity |
| Superconductivity | 2 | Tc transition, critical current density (Jc) |
| Electrochemistry | 4 | Cyclic voltammetry, EIS, chronoamperometry, potentiometry |
| Dielectric & Ferroelectric | 4 | C-V, P-E loop, pyroelectric current, capacitance-frequency |
| Semiconductor & Optoelectronics | 5 | Solar cell IV, DLTS, photocurrent spectroscopy, photoresponse, tunneling |
| Sensors & Materials | 7 | Gas sensor, humidity, impedance biosensor, cell counting, pH calibration, strain gauge, fatigue |
| Quantum Design PPMS/MPMS | 6 | PPMS R-T, PPMS MR, PPMS Hall, PPMS heat capacity, MPMS M-H, MPMS M-T ZFC/FC |

Plus a universal **custom sweep** template for user-defined X-Y measurements (46 total).

## Supported Instruments

Works out of the box with standard lab equipment:

| Instrument | Models | Role |
|-----------|--------|------|
| Keithley Source Meters | 2400, 2410, 2420, 2440 | Source + measure I/V |
| Keithley DMMs | 2000, 2001, 2002 | Voltage, resistance, current |
| Keithley Nanovoltmeters | 2182, 2182A | Ultra-low-noise voltage |
| Keithley Current Sources | 6221 | AC/pulse/DC current |
| Keithley Electrometers | 6517, 6517A, 6517B | High resistance, low current |
| Lakeshore Gaussmeters | 425, 455, 475 | Magnetic field |
| Lakeshore Temp Controllers | 335, 336, 340, 350 | Temperature control |
| Keysight LCR Meters | E4980, E4980A, E4980AL | Impedance, capacitance |
| NI DAQ | USB-6351, USB-6001, USB-6009 | Analog/digital I/O |

Don't see your instrument? The AI classifier handles unknown instruments from their `*IDN?` response.

## AI at Every Step

| Capability | How AI Helps |
|-----------|-------------|
| **Instrument Classification** | LLM identifies unknown instruments from `*IDN?` responses and maps them to measurement roles |
| **Parameter Optimization** | Suggests optimal sweep ranges based on your sample type and literature references |
| **Safety Advisory** | Explains *why* a limit exists and suggests safer alternatives when boundaries are hit |
| **Script Generation** | Creates custom analysis scripts with publication-ready plots (PNG 300 dpi + PDF) |
| **Result Interpretation** | Extracts physical quantities and explains them with context |
| **Skill Generation** | Creates new measurement protocol skills from existing examples |
| **Agent Chat** | Multi-turn conversation with tool calling for guided measurement workflows |
| **Experiment Memory** | Learns from your history to improve parameter suggestions for future measurements |

## Choose Your AI Model

One config line switches between cloud and local models:

```yaml
# Best quality (cloud)
model:
  provider: "anthropic"
  model: "claude-sonnet-4-20250514"

# Free & private (local)
model:
  provider: "ollama"
  model: "qwen3:32b"
  base_url: "http://localhost:11434"
```

Supported providers: **Claude** | **GPT-4o** | **Gemini** | **Ollama** | **vLLM** | **DeepSeek**

## CLI Commands

| Command | Description |
|---------|-------------|
| `labharness scan` | Scan for connected instruments via GPIB/USB/serial |
| `labharness classify <type>` | Classify instruments into measurement roles |
| `labharness propose <type>` | Generate a measurement plan with safety validation |
| `labharness literature <type>` | Search literature for measurement protocols |
| `labharness generate-skill <type>` | Generate a new measurement protocol skill with AI |
| `labharness analyze <file>` | Analyze measurement data with AI interpretation |
| `labharness chat` | Interactive AI chat for guided measurement workflows |
| `labharness procedures` | List PICA reference instrument procedures |
| `labharness web` | Start the adaptive Web GUI (dashboard + monitor) |
| `labharness serve` | Start MCP server for AI IDE integration |

## MCP Server Tools

Run as an MCP server for integration with Claude Code, Cursor, or any MCP client:

```bash
labharness serve
```

| Tool | Description |
|------|-------------|
| `scan_instruments` | Discover all connected lab instruments |
| `classify_lab_instruments` | Map instruments to measurement roles |
| `propose_measurement` | Generate a validated measurement plan |
| `validate_plan` | Check a plan against safety boundaries |
| `search_literature` | Find published measurement protocols |
| `analyze_data` | Run analysis with AI interpretation |
| `generate_skill` | Create new measurement protocol skills |
| `healthcheck` | Verify system status and available templates |

## Compared to Alternatives

| | AI Harness for Lab | LabVIEW | PyMeasure | PICA | Custom Scripts |
|---|---|---|---|---|---|
| **AI-guided** | Yes (6 providers) | No | No | No | No |
| **Setup time** | Minutes | Weeks | Hours | Hours | Days |
| **Safety checks** | 3-tier auto | Manual | None | Manual | Manual |
| **Templates** | 46 across 9 disciplines | Rebuild each | Code each | ~10 | Code each |
| **Literature search** | Built-in | No | No | No | No |
| **Web GUI** | Adaptive dashboard | Desktop only | No | No | No |
| **MCP integration** | Native | No | No | No | No |
| **Cost** | Free & open source | $$$$ license | Free | Free | Free |
| **Learning curve** | Natural language | Steep | Moderate | Moderate | Steep |

## Architecture

<p align="center">
  <img src="assets/architecture.svg" alt="Architecture" width="750">
</p>

## Roadmap

- [x] 46 measurement templates across 9 disciplines
- [x] AI-powered instrument classification, parameter optimization, safety advisory
- [x] Agent loop with tool calling and experiment memory
- [x] MCP server for Claude Code / Cursor integration
- [x] Adaptive Web GUI with real-time monitoring
- [x] Quantum Design PPMS/MPMS integration (MultiPyVu)
- [ ] Real-time measurement execution (PyMeasure driver integration)
- [ ] Community template marketplace
- [ ] PyPI package release

## Contributing

We are building the future of AI-powered laboratory automation. Whether you work in physics, chemistry, biology, or materials science, your measurement templates and instrument drivers make this project better for everyone.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and [CATALOG.md](CATALOG.md) for the full template catalog with 46 templates and 16 instrument reference procedures.

## Acknowledgments

- Measurement procedures adapted from [PICA](https://github.com/prathameshnium/PICA-Python-Instrument-Control-and-Automation) (MIT License)
- Agent architecture inspired by [Hermes Agent](https://github.com/nousresearch/hermes-agent) patterns

## License

MIT

# AI Guide: How to Use AI Harness for Lab

> This document is written for AI assistants (Claude, GPT, Gemini, Copilot, etc.).
> After reading this file, you should be able to fully guide a researcher through
> setting up, configuring, and using AI Harness for Lab for any measurement type.

---

## 1. What This System Does

AI Harness for Lab is a Python framework that connects AI to laboratory instruments.
It automates the full measurement workflow:

```
Research Question → Literature Search → Instrument Discovery → 
Classification → Measurement Planning → Safety Validation → 
Data Analysis → AI Interpretation
```

The system has **46 measurement templates** across 9 disciplines (physics, chemistry,
biology, materials science, semiconductor, thermoelectric, superconductivity,
dielectric, environmental/sensors) and supports **any GPIB/USB/serial instrument**.

---

## 2. Installation

```bash
# Basic install
pip install git+https://github.com/Anai-Guo/AIharnessforlab.git

# With instrument drivers
pip install "ai-harness-for-lab[execution]"

# With web GUI
pip install "ai-harness-for-lab[web]"

# For development
pip install -e ".[dev]"
```

---

## 3. Core Commands (CLI)

| Command | What It Does |
|---------|-------------|
| `labharness scan` | Scan GPIB/USB/serial for connected instruments |
| `labharness classify <TYPE>` | Map instruments to measurement roles |
| `labharness propose <TYPE>` | Generate a measurement plan from template |
| `labharness literature <TYPE> --sample "..."` | Search literature for protocols |
| `labharness analyze <file> --type <TYPE>` | Analyze data with template script |
| `labharness analyze <file> --type <TYPE> --ai` | AI-generated analysis script |
| `labharness analyze <file> --type <TYPE> --interpret` | Add AI physics interpretation |
| `labharness generate-skill <TYPE>` | AI creates a new measurement protocol |
| `labharness procedures` | List SCPI reference procedures |
| `labharness chat` | Interactive AI-guided measurement session |
| `labharness web` | Launch adaptive web GUI at localhost:8080 |
| `labharness serve` | Start MCP server for Claude Code / Cursor |

---

## 4. Measurement Types

When a user mentions a measurement, map it to one of these template keys:

### Physics & Electrical
| User Says | Template Key | Description |
|-----------|-------------|-------------|
| "IV curve", "current-voltage" | `iv` | Source current sweep, measure voltage |
| "resistance vs temperature", "R-T" | `rt` | Temperature sweep, measure resistance |
| "Hall effect", "carrier density" | `hall` | Field sweep, measure Hall voltage |
| "magnetoresistance", "MR" | `mr` | Field sweep, measure longitudinal R |
| "anomalous Hall", "AHE" | `ahe` | Field sweep, measure transverse R |
| "spin-orbit torque", "SOT" | `sot` | Field sweep at each pulse current |
| "FMR", "ferromagnetic resonance" | `fmr` | Field sweep, lock-in absorption |
| "hysteresis loop", "M-H" | `hysteresis` | Field sweep, measure magnetization |
| "tunneling", "dI/dV" | `tunneling` | Voltage sweep, differential conductance |
| "Nernst effect" | `nernst` | Field sweep, transverse thermoelectric V |
| "magnetostriction" | `magnetostriction` | Field sweep, measure strain |
| "delta mode", "low resistance" | `delta` | K6221+K2182A ultra-low resistance |
| "high resistance", "electrometer" | `high_r` | K6517B, voltage sweep, picoamp |
| "breakdown voltage" | `breakdown` | Voltage ramp to failure |

### Semiconductor
| User Says | Template Key |
|-----------|-------------|
| "FET transfer curve", "gate sweep" | `transfer` |
| "FET output curve", "drain sweep" | `output` |
| "solar cell IV", "photovoltaic" | `photo_iv` |
| "DLTS", "deep level" | `dlts` |
| "C-f", "capacitance frequency" | `capacitance_frequency` |
| "photocurrent", "spectral response" | `photocurrent` |
| "photoresponse", "transient" | `photoresponse` |

### Chemistry & Electrochemistry
| User Says | Template Key |
|-----------|-------------|
| "cyclic voltammetry", "CV scan" | `cyclic_voltammetry` |
| "impedance spectroscopy", "EIS" | `eis` |
| "chronoamperometry", "CA" | `chronoamperometry` |
| "open circuit potential", "OCP" | `potentiometry` |

### Quantum Design Systems
| User Says | Template Key |
|-----------|-------------|
| "PPMS R-T", "PPMS resistivity" | `ppms_rt` |
| "PPMS magnetoresistance" | `ppms_mr` |
| "PPMS Hall" | `ppms_hall` |
| "PPMS heat capacity", "specific heat" | `ppms_hc` |
| "MPMS M-H", "SQUID magnetization" | `mpms_mh` |
| "MPMS M-T", "ZFC/FC" | `mpms_mt` |

### Other
| User Says | Template Key |
|-----------|-------------|
| "Seebeck coefficient" | `seebeck` |
| "thermal conductivity" | `thermal_conductivity` |
| "superconducting Tc" | `tc` |
| "critical current" | `jc` |
| "C-V", "capacitance-voltage" | `cv` |
| "P-E loop", "ferroelectric" | `pe_loop` |
| "pyroelectric current" | `pyroelectric` |
| "gas sensor" | `gas_sensor` |
| "pH calibration" | `ph_calibration` |
| "humidity sensor" | `humidity_response` |
| "biosensor impedance" | `impedance_biosensor` |
| "strain gauge" | `strain_gauge` |
| "fatigue test" | `fatigue` |
| "custom measurement" | `custom_sweep` |

---

## 5. Typical Workflow (Guide the User Through This)

### Step 1: Discover Instruments
```bash
labharness scan
```
This returns a list of connected instruments with VISA addresses and model numbers.

### Step 2: Classify for Measurement
```bash
labharness classify hall
```
Maps discovered instruments to roles (source_meter, dmm, gaussmeter, etc.).

### Step 3: Generate Plan
```bash
labharness propose hall
```
Creates a measurement plan from template with default parameters.
The AI can optimize parameters if a sample description is provided.

### Step 4: Validate Safety
The plan is automatically validated against three-tier safety boundaries:
- **Block**: Exceeds absolute instrument limits → cannot proceed
- **Require Confirm**: Exceeds warning thresholds → ask user
- **Allow**: Within safe range → proceed

### Step 5: Analyze Data
```bash
labharness analyze data.csv --type hall --interpret
```
Generates analysis script, runs it, produces figures (PNG 300dpi + PDF),
and provides AI interpretation of the physics.

---

## 6. Configuration

### AI Model Selection
Edit `configs/models.yaml` or use environment variables:

```bash
export LABHARNESS_PROVIDER=anthropic
export LABHARNESS_MODEL=claude-sonnet-4-20250514
export LABHARNESS_API_KEY=sk-...
```

Supported providers: `anthropic`, `openai`, `ollama`, `gemini`, `deepseek`

For local/private models:
```bash
export LABHARNESS_PROVIDER=ollama
export LABHARNESS_MODEL=qwen3:32b
export LABHARNESS_BASE_URL=http://localhost:11434
```

### Instrument Configuration
Create `configs/instruments/mylab.yaml`:
```yaml
instruments:
  source_meter:
    driver: keithley2400
    resource: "GPIB0::5::INSTR"
    settings:
      compliance_v: 20.0
  temperature_controller:
    driver: lakeshore335
    resource: "GPIB0::10::INSTR"
```

---

## 7. MCP Server Integration

For use with Claude Code, Cursor, or any MCP client:
```bash
labharness serve
```

Available MCP tools:
- `scan_instruments()` → discover lab instruments
- `classify_lab_instruments(measurement_type)` → map to roles
- `propose_measurement(measurement_type, roles_json?)` → generate plan
- `validate_plan(plan_json)` → safety check
- `search_literature(measurement_type, sample_description?)` → find protocols
- `analyze_data(data_path, measurement_type, use_ai?, interpret?)` → analyze
- `generate_skill(measurement_type, sample_description?)` → create protocol
- `healthcheck()` → system status

---

## 8. Web GUI

```bash
pip install "ai-harness-for-lab[web]"
labharness web
```

Opens at `http://localhost:8080`. The GUI dynamically generates measurement
forms from YAML templates — one adaptive interface for all 46+ measurement types.

---

## 9. Key Architecture Concepts

- **Templates** (`src/lab_harness/planning/templates/*.yaml`): Define what to measure
- **Drivers** (`src/lab_harness/drivers/`): How to talk to instruments (VISA/GPIB)
- **Skills** (`skills/*.md`): Step-by-step measurement protocols (Markdown + YAML frontmatter)
- **Memory** (`src/lab_harness/memory/`): SQLite experiment history, learns from past measurements
- **Safety** (`src/lab_harness/planning/boundary_checker.py`): Three-tier validation, AI safety advisor
- **Analysis** (`src/lab_harness/analysis/`): Template + AI script generation, AI result interpretation
- **Agent** (`src/lab_harness/agent/`): Conversational loop with tool calling and budget management

---

## 10. When Things Go Wrong

| Problem | Solution |
|---------|----------|
| No instruments found | Check GPIB cable, install NI-VISA driver, verify `pyvisa` installed |
| Unknown instrument | AI classifier handles it automatically via LLM fallback |
| No template for measurement | Use `labharness generate-skill <TYPE>` to create one with AI |
| Safety boundary blocked | Review limits in `configs/default_safety.yaml`, or provide sample description for AI advice |
| LLM not responding | Check API key, try a different provider, or use local model (Ollama) |
| Analysis script fails | Use `--ai` flag for AI-generated script, or `--instructions "..."` for custom guidance |

---

## 11. Adding New Capabilities

### New Measurement Template (5 minutes)
1. Create `src/lab_harness/planning/templates/<type>.yaml`
2. Add to `MeasurementType` enum in `models/measurement.py`
3. Add to `MEASUREMENT_ROLES` in `discovery/classifier.py`

### New Instrument Driver
1. Subclass `VisaDriver` in `src/lab_harness/drivers/<name>.py`
2. Register in `drivers/registry.py` DRIVER_MAP
3. Add example config in `configs/instruments/`

### New Analysis Template
1. Create `src/lab_harness/analysis/templates/<type>.py`
2. Use `{{DATA_PATH}}` and `{{OUTPUT_DIR}}` placeholders

### Modifying the Web GUI
See `docs/GUI_DEVELOPMENT.md` for the complete GUI modification guide.
Key points:
- GUI is a single embedded HTML in `src/lab_harness/web/app.py`
- Two pages: `_embedded_dashboard()` (template config) and `_embedded_monitor()` (real-time charts)
- Adding a channel: add to `CHANNELS` array in JavaScript
- Template-driven: metric cards auto-configure from YAML templates
- Presets: saved to localStorage, restored on next session
- Charts: all use Chart.js, all have selectable X/Y axes

See `CATALOG.md` for the full catalog and contributor guide.

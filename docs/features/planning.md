# Measurement Planning

LabAgent generates complete, validated measurement plans from YAML templates. Rather than letting an AI freely invent measurement parameters, the system uses curated templates as a safety-anchored starting point and applies optional AI optimization on top. This design ensures reproducibility and prevents dangerous parameter choices.

## Template System

Every measurement plan starts from a YAML template that defines:

- **Sweep axis** -- parameter to sweep (label, unit, start/stop/step, instrument role)
- **Data channels** -- quantities to record at each sweep point
- **Safety limits** -- maximum current, voltage, field, and temperature
- **Execution parameters** -- settling time, number of averages, output directory
- **Outer sweep** (optional) -- secondary sweep for 2D measurements (e.g., temperature loop around a field sweep)

### Example: IV Template

```yaml
name: "IV Measurement"
description: "Sweep source current and measure voltage"

x_axis:
  label: "Source Current"
  unit: "mA"
  start: -1.0
  stop: 1.0
  step: 0.01
  role: "source_meter"

y_channels:
  - label: "Voltage"
    unit: "V"
    role: "source_meter"

max_current_a: 0.01
max_voltage_v: 20.0
settling_time_s: 0.1
num_averages: 1
```

### Building a Plan

```bash
# Generate a plan from template defaults
labharness propose IV

# The Python API supports overrides and sample-aware optimization
from lab_harness.planning.plan_builder import build_plan_from_template

plan = build_plan_from_template(
    "AHE",
    overrides={"x_axis": {"start": -5000, "stop": 5000, "step": 50}},
    sample_description="20nm CoFeB/MgO thin film",
)
```

User-provided overrides are deep-merged into the template, with user values taking precedence over both template defaults and AI suggestions.

## 46 Templates Across 9 Disciplines

LabAgent ships with 46 built-in measurement templates organized by scientific discipline:

| Discipline | Templates | Examples |
|-----------|-----------|----------|
| Electrical Characterization | 11 | IV, AHE, MR, RT, SOT, CV, Delta, High-R, Transfer, Output, Breakdown |
| Thermoelectric | 2 | Seebeck, Thermal Conductivity |
| Magnetic | 3 | Hall, FMR, Hysteresis |
| Optical / Photonic | 2 | Photocurrent, Photoresponse |
| Superconductivity | 2 | Tc, Jc |
| Dielectric / Ferroelectric | 2 | P-E Loop, Pyroelectric |
| Chemistry / Electrochemistry | 4 | Cyclic Voltammetry, EIS, Chronoamperometry, Potentiometry |
| Biology / Biosensors | 2 | Impedance Biosensor, Cell Counting |
| Materials Science / Environmental | 7 | Strain Gauge, Fatigue, Humidity Response, Gas Sensor, pH Calibration, DLTS, Capacitance-Frequency |
| Semiconductor (additional) | 2 | Photo-IV, Tunneling |
| Quantum Design Integration | 6 | PPMS-RT, PPMS-MR, PPMS-Hall, PPMS-HC, MPMS-MH, MPMS-MT |
| General Purpose | 2 | Custom Sweep, Custom |

Each template defines safe defaults for its measurement type. For the full machine-readable catalog, see [CATALOG.md](https://github.com/Anai-Guo/LabAgent/blob/main/CATALOG.md).

## AI Parameter Optimization

When a `sample_description` is provided, the plan builder invokes an LLM to suggest optimized parameters for the specific material. The AI considers:

- Material properties (film thickness, composition, expected resistance range)
- Instrument capabilities and typical operating ranges
- Signal-to-noise tradeoffs (source current vs. sample damage risk)
- Literature-typical ranges for the measurement type

The optimizer returns suggested overrides with reasoning. Critical safety constraint: **AI suggestions are clamped to template safety limits and can never exceed them.** If the AI suggests `max_current_a = 0.5` but the template maximum is `0.01`, the suggestion is silently dropped.

The override priority chain is:

1. Template defaults (base)
2. AI-suggested optimizations (applied on top, clamped to safety limits)
3. User overrides (highest priority, applied last)

## Role Validation

When instrument role assignments are provided, the plan builder validates them against the template's requirements. It warns about:

- **Missing roles** -- roles required by the template but not assigned to any instrument
- **Extra roles** -- instruments assigned roles not used by this template

This ensures you have the right equipment connected before starting a measurement.

## Batch Campaigns

For systematic studies, the campaign system generates multiple measurement plans by sweeping parameters:

```bash
# Create a campaign sweeping temperature and field
labharness campaign AHE \
  --sweep "temperature=10,50,100,200,300" \
  --sweep "max_field_oe=1000,5000,10000" \
  --preview
```

Each combination produces a validated plan, and the full set is saved as a campaign JSON file for sequential execution.

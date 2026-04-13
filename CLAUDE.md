# Lab Harness

AI-guided laboratory automation framework for physics transport measurements.

## Project Structure

```
src/lab_harness/
  server.py         - MCP server entry (FastMCP)
  cli.py            - Standalone CLI entry
  config.py         - Settings + model config
  llm/
    router.py       - litellm unified model routing
    prompts.py      - System prompts per phase
  models/
    instrument.py   - InstrumentRecord, LabInventory
    measurement.py  - MeasurementPlan, SweepAxis, DataChannel
    safety.py       - SafetyPolicy, BoundaryViolation, ValidationResult
  discovery/
    visa_scanner.py - PyVISA instrument scanning
    classifier.py   - Model-to-role classification
  planning/
    plan_builder.py     - Build plans from YAML templates
    boundary_checker.py - Safety boundary validation
    templates/          - Measurement type templates (AHE, MR, IV, RT)
configs/
  models.yaml             - LLM provider selection
  default_safety.yaml     - Safety limits
  common_instruments.yaml - Known instrument database
```

## Key Design Decisions

- Dual entry: MCP server (for Claude Code/Cursor) + standalone CLI (with litellm routing)
- Safety-first: Three-tier boundary checking (block / require_confirm / allow)
- Template-based measurement planning, not free-form AI generation
- PyVISA for instrument communication, PyMeasure for high-level drivers

## Development

```bash
pip install -e ".[dev]"
labharness scan          # Scan instruments
labharness classify AHE  # Classify for AHE measurement
labharness propose AHE   # Generate measurement plan
labharness serve         # Start MCP server
```

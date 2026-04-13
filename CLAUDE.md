# Lab Harness

AI-guided laboratory automation framework for physics transport measurements.

## Project Structure

```
src/lab_harness/
  server.py         - MCP server entry (FastMCP, 7 tools)
  cli.py            - Standalone CLI entry (6 subcommands)
  config.py         - Settings + model config (env var overrides)
  agent/
    loop.py         - LabAgent: conversational agent with skill registry + memory
    budget.py       - Iteration budget with 70%/90% warnings
  analysis/
    analyzer.py     - Script generation + subprocess execution
    templates/      - Per-type analysis scripts (ahe, iv, mr, rt)
  discovery/
    visa_scanner.py - PyVISA GPIB/USB instrument scanning
    serial_scanner.py - pyserial COM port scanning
    classifier.py   - AI + rule-based instrument-to-role classification
    schemas.py      - Classifier output schemas
  literature/
    paper_pilot_client.py - paper-pilot MCP client for protocol search
  llm/
    router.py       - litellm unified model routing
    prompts.py      - System prompts per measurement phase
  memory/
    store.py        - SQLite + FTS5 experiment history
    snapshot.py     - Frozen memory snapshot for agent system prompt
  models/
    instrument.py   - InstrumentRecord, LabInventory, InstrumentBus
    measurement.py  - MeasurementPlan, SweepAxis, DataChannel
    safety.py       - SafetyPolicy, BoundaryViolation, ValidationResult
  planning/
    plan_builder.py     - Build plans from YAML templates
    boundary_checker.py - Safety boundary validation
    templates/          - YAML templates (ahe, mr, iv, rt, sot, cv)
  skills/
    registry.py     - Skill discovery + progressive disclosure (Level 0/1)
skills/
  ahe.md            - AHE measurement protocol skill
  sot.md            - SOT loop shift protocol skill
configs/
  models.yaml             - LLM provider selection
  default_safety.yaml     - Safety limits
  common_instruments.yaml - Known instrument database
tests/
  11 test files covering models, planning, discovery, memory, analysis, skills, budget
```

## Key Design Decisions

- **Dual entry**: MCP server (Claude Code/Cursor) + standalone CLI (with litellm routing)
- **Safety-first**: Three-tier boundary checking (block / require_confirm / allow)
- **Template-based**: Measurement plans from YAML templates, not free-form AI generation
- **Model-agnostic**: litellm routes to any provider; env vars override config file
- **Hermes patterns adopted**:
  - Skill registry with progressive disclosure (Level 0 metadata / Level 1 full body)
  - Agent loop with iteration budget (50 max, warnings at 70%/90%)
  - Memory snapshots frozen at session start, injected into system prompt
- **PyVISA + pyserial**: Covers GPIB/USB and serial instruments
- **Analysis pipeline**: Template scripts with placeholder substitution, subprocess execution with timeout

## Development

```bash
pip install -e ".[dev]"

# CLI commands
labharness scan                          # Scan instruments
labharness classify AHE                  # Classify for measurement
labharness propose AHE                   # Generate measurement plan
labharness literature AHE --sample "CoFeB/MgO"  # Search literature
labharness analyze data.csv --type AHE   # Analyze data
labharness serve                         # Start MCP server

# Testing
pytest tests/ -v                         # Run all tests
ruff check src/ tests/                   # Lint
ruff format --check src/ tests/          # Format check
```

## CI

GitHub Actions runs on push/PR to main: ruff lint + format check + pytest across Python 3.10/3.11/3.12.

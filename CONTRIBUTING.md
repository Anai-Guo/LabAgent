# Contributing to Lab Harness

## Development Setup

```bash
git clone https://github.com/Anai-Guo/LabAgent.git
cd labharness
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
ruff check src/ tests/       # Lint
ruff format src/ tests/      # Format
```

## Adding a New Measurement Template

1. Create a YAML file in `src/lab_harness/planning/templates/` (e.g., `my_measurement.yaml`)
2. Define: `x_axis`, `y_channels`, safety limits, and execution parameters
3. See existing templates (ahe.yaml, mr.yaml) for reference
4. Add the measurement type to `MeasurementType` enum in `models/measurement.py`

## Adding a New Instrument

1. Add the instrument model to `KNOWN_INSTRUMENTS` in `src/lab_harness/discovery/classifier.py`
2. Add the instrument spec to `configs/common_instruments.yaml`
3. If the measurement type requires this instrument, update `MEASUREMENT_ROLES`

## Project Structure

```
src/lab_harness/
  server.py       - MCP server (FastMCP)
  cli.py          - Standalone CLI
  llm/            - LLM routing (litellm)
  models/         - Pydantic data models
  discovery/      - Instrument scanning & classification
  planning/       - Measurement plan templates & safety validation
```

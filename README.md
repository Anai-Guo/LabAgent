# Lab Harness

[![CI](https://github.com/Anai-Guo/labharness/actions/workflows/ci.yml/badge.svg)](https://github.com/Anai-Guo/labharness/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

AI-guided laboratory automation framework for physics transport measurements.

> The first tool that uses AI to guide physicists from research question through literature search, measurement planning, execution, and data analysis -- with built-in safety guarantees at every step.

## Features

- **Model-agnostic AI** -- Switch between Claude, GPT, Ollama, vLLM with one config line (via litellm)
- **Dual interface** -- MCP server (Claude Code, Cursor) + standalone CLI
- **Instrument discovery** -- Auto-scan GPIB/USB/serial instruments via PyVISA and pyserial
- **Smart classification** -- AI maps instruments to measurement roles with rule-based fallback
- **Template-based planning** -- AHE, MR, IV, RT, SOT, CV measurement templates with parameter filling
- **Safety boundaries** -- Three-tier validation (block / confirm / allow) prevents instrument damage
- **Literature integration** -- Query paper-pilot for published protocols and instrument settings
- **Data analysis** -- Template-based analysis scripts for AHE, MR, IV, RT with auto-execution
- **Agent loop** -- Conversational agent with budget management and progressive skill disclosure
- **Skill registry** -- Markdown-based measurement protocol skills with YAML frontmatter
- **Experiment memory** -- SQLite + FTS5 experiment history with frozen snapshots for agent context

## Quick Start

```bash
pip install labharness

# Scan connected instruments
labharness scan

# Classify instruments for a measurement type
labharness classify AHE

# Generate a measurement plan
labharness propose AHE

# Search literature for measurement protocols
labharness literature AHE --sample "CoFeB/MgO"

# Analyze measurement data
labharness analyze data.csv --type AHE

# Start MCP server (for Claude Code / Cursor)
labharness serve
```

## Architecture

```
Phase -1: Model Router ────────── litellm: choose AI backend (Claude/GPT/Ollama/vLLM)
Phase  0: Research Planning ───── literature search via paper-pilot MCP
Phase  1: Equipment Discovery ─── PyVISA scan + serial scan + *IDN?
Phase  2: Role Classification ─── AI maps instruments to roles (with rule fallback)
Phase  3: Measurement Design ──── YAML template + safety boundary check
Phase  4: Measurement Execution ─ (future: PyMeasure / NI-DAQmx drivers)
Phase  5: Data Analysis ───────── template-based scripts + auto-execution
```

### Modules

| Module | Purpose |
|---|---|
| `agent/` | Conversational agent loop with iteration budget |
| `analysis/` | Data analysis orchestrator + per-type templates (AHE, MR, IV, RT) |
| `discovery/` | VISA scanner, serial scanner, AI instrument classifier |
| `literature/` | Paper-pilot MCP client for protocol literature search |
| `llm/` | litellm router, system prompt templates per phase |
| `memory/` | SQLite+FTS5 experiment store, frozen snapshots for agent context |
| `models/` | Pydantic data models (instrument, measurement plan, safety policy) |
| `planning/` | Plan builder from YAML templates, safety boundary checker |
| `skills/` | Markdown skill registry with progressive disclosure |

### Hermes-inspired patterns

- **Skill registry with progressive disclosure** -- Level 0 (metadata only) shown to LLM by default; full skill body loaded on demand
- **Agent loop with budget** -- Iteration counter with 70%/90% warnings; prevents runaway conversations
- **Memory snapshots** -- Frozen experiment history injected into system prompt at session start

## Configuration

Edit `configs/models.yaml` to choose your AI backend:

```yaml
model:
  provider: "anthropic"          # or "openai", "ollama"
  model: "claude-sonnet-4-20250514"  # or "gpt-4o", "qwen3:32b"
  # base_url: "http://localhost:11434"  # for local models
```

Environment variable overrides: `LABHARNESS_API_KEY`, `LABHARNESS_MODEL`, `LABHARNESS_PROVIDER`, `LABHARNESS_BASE_URL`.

## MCP Server Tools

When running as an MCP server (`labharness serve`), the following tools are exposed:

| Tool | Description |
|---|---|
| `scan_instruments` | Discover instruments on VISA bus |
| `classify_lab_instruments` | Map instruments to measurement roles |
| `propose_measurement` | Generate and validate a measurement plan |
| `validate_plan` | Check a plan against safety boundaries |
| `search_literature` | Query paper-pilot for protocol references |
| `analyze_data` | Generate and run analysis scripts |
| `healthcheck` | System status (VISA, templates, LLM config) |

## Project Stats

- **9 modules** in `src/lab_harness/`
- **6 measurement templates** (AHE, MR, IV, RT, SOT, CV)
- **4 analysis templates** (AHE, MR, IV, RT)
- **2 skill files** (AHE, SOT)
- **11 test files** in `tests/`
- **CI**: lint (ruff) + format check + pytest on Python 3.10/3.11/3.12

## License

MIT

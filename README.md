<p align="center">
  <img src="assets/hero.svg" alt="AI Harness for Lab — Fully Automated Lab Assistant" width="700">
</p>

<p align="center">
  <a href="https://github.com/Anai-Guo/AIharnessforlab/actions/workflows/ci.yml"><img src="https://github.com/Anai-Guo/AIharnessforlab/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/tests-88%20passed-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/AI%20models-6%20providers-purple.svg" alt="Models">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
</p>

---

Most physics labs have powerful instruments but terrible software. Researchers waste weeks writing LabVIEW scripts or Python wrappers from scratch for every new measurement. When something goes wrong, there's no safety net.

**AI Harness for Lab** changes this. Tell it what you want to measure, and it:

1. Searches the literature for proven measurement protocols
2. Scans your lab and identifies every connected instrument
3. Maps instruments to measurement roles using AI
4. Generates a measurement plan with safety boundaries
5. Analyzes your data and explains the physics

All with built-in safety guarantees that prevent you from frying your samples.

<p align="center">
  <img src="assets/workflow.svg" alt="How it works" width="750">
</p>

## Quick Start

```bash
pip install git+https://github.com/Anai-Guo/AIharnessforlab.git

# Scan your lab instruments
labharness scan

# "What do I need for an AHE measurement?"
labharness classify AHE

# Generate a measurement plan with safety checks
labharness propose AHE

# Search literature for measurement protocols
labharness literature RT --sample "silicon wafer"

# Analyze data with AI interpretation
labharness analyze data.csv --type AHE --interpret

# Generate a new measurement protocol with AI
labharness generate-skill MR --sample "NiFe thin film"

# List PICA reference measurement procedures
labharness procedures

# Interactive AI chat for guided measurements
labharness chat

# Start MCP server (for Claude Code / Cursor)
labharness serve
```

## Why AI Harness for Lab?

| Problem | Our Solution |
|---------|-------------|
| "I don't know what parameters to use" | AI suggests optimal parameters based on your sample and literature |
| "Will this damage my sample?" | 3-tier safety boundaries block dangerous configurations |
| "I have 5 instruments, which does what?" | AI auto-classifies instruments into measurement roles |
| "How do I analyze this data?" | AI generates analysis scripts and explains the physics |
| "I forgot what worked last time" | Experiment memory remembers your successful parameters |
| "I need a new measurement type" | AI generates protocol skills from existing examples |

## Architecture

<p align="center">
  <img src="assets/architecture.svg" alt="Architecture" width="750">
</p>

## Supported Instruments

Works out of the box with standard physics lab equipment:

| Instrument | Role | Interface |
|-----------|------|-----------|
| Keithley 2400/2410 | Source Meter | GPIB |
| Keithley 2000/2001 | Digital Multimeter | GPIB |
| Keithley 2182/2182A | Nanovoltmeter | GPIB |
| Keithley 6221 | AC/Pulse Current Source | GPIB |
| Keithley 6517B | Electrometer | GPIB |
| Lakeshore 425/455 | Gaussmeter | Serial |
| Lakeshore 335/340/350 | Temperature Controller | GPIB |
| Keysight E4980A | LCR Meter | GPIB |
| NI USB-6351 | DAQ (Magnet Control) | USB |

Don't see your instrument? The AI classifier handles unknown instruments too.

## AI at Every Step

| Feature | How AI Helps |
|---------|-------------|
| **Instrument Classification** | LLM identifies unknown instruments from *IDN? responses |
| **Parameter Optimization** | Suggests optimal sweep ranges based on sample + literature |
| **Safety Advisory** | Explains *why* a limit exists and suggests safer alternatives |
| **Script Generation** | Creates custom analysis scripts for any measurement type |
| **Result Interpretation** | Explains extracted values with physics context |
| **Skill Generation** | Creates new measurement protocols from examples |
| **Agent Chat** | Multi-turn conversation with tool calling for guided workflows |
| **Experiment Memory** | Learns from history to improve future measurements |

## Choose Your AI

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

Supported: **Claude** | **GPT-4o** | **Gemini** | **Ollama** | **vLLM** | **DeepSeek**

## MCP Server

Run as an MCP server for integration with Claude Code, Cursor, or any MCP client:

```bash
labharness serve
```

Exposes 8 tools: `scan_instruments`, `classify_lab_instruments`, `propose_measurement`, `validate_plan`, `search_literature`, `analyze_data`, `generate_skill`, `healthcheck`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Acknowledgments

- Measurement procedures adapted from [PICA](https://github.com/prathameshnium/PICA-Python-Instrument-Control-and-Automation) (MIT License, UGC-DAE CSR Mumbai)
- Agent architecture inspired by [Hermes Agent](https://github.com/nousresearch/hermes-agent) patterns

## License

MIT

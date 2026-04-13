# Lab Harness

AI-guided laboratory automation framework for physics transport measurements.

> The first tool that uses AI to guide physicists from research question through measurement planning with built-in safety guarantees, incorporating literature context automatically.

## Features

- **Model-agnostic AI**: Switch between Claude, GPT, Ollama, vLLM with one config line (via litellm)
- **Dual interface**: MCP server (Claude Code, Cursor) + standalone CLI
- **Instrument discovery**: Auto-scan GPIB/USB/serial instruments via PyVISA
- **Smart classification**: AI maps instruments to measurement roles
- **Template-based planning**: AHE, MR, IV, RT measurement templates with parameter filling
- **Safety boundaries**: Three-tier validation (block / confirm / allow) prevents instrument damage

## Quick Start

```bash
pip install labharness

# Scan connected instruments
labharness scan

# Classify instruments for AHE measurement
labharness classify AHE

# Generate a measurement plan
labharness propose AHE

# Start MCP server (for Claude Code / Cursor)
labharness serve
```

## Configuration

Edit `configs/models.yaml` to choose your AI backend:

```yaml
model:
  provider: "anthropic"          # or "openai", "ollama"
  model: "claude-sonnet-4-20250514"  # or "gpt-4o", "qwen3:32b"
  # base_url: "http://localhost:11434"  # for local models
```

## Architecture

```
Phase -1: Model Router (litellm) ── choose AI backend
Phase  0: Research Planning ────── literature search (paper-pilot)
Phase  1: Equipment Discovery ──── PyVISA scan + *IDN?
Phase  2: Role Classification ──── AI maps instruments to roles
Phase  3: Measurement Design ───── template + boundary check
Phase  4: Measurement Execution ── (future: PyMeasure drivers)
Phase  5: Data Analysis ────────── AI-generated analysis scripts
```

## License

MIT

# Hacker News Post Draft

**Title:** Show HN: LabAgent – Open-source AI assistant for automating lab measurements

**URL:** https://github.com/Anai-Guo/LabAgent

**Text (for comment):**

I built an open-source Python framework that connects LLMs to lab instruments for automated scientific measurements.

The problem: researchers worldwide waste enormous time writing one-off measurement scripts (often in LabVIEW), with no safety checks and no institutional memory of what parameters worked before.

LabAgent solves this by putting AI at every step of the measurement workflow:

1. Describe what you want to measure in natural language
2. AI scans your instruments via PyVISA (GPIB/USB/serial)
3. AI classifies instruments into measurement roles
4. Generates a plan from 46 templates with 3-tier safety validation
5. Analyzes results and explains the physics

Technical highlights:
- Agent harness architecture (inspired by OpenHarness) with async query loop
- 8 standardized tools with Pydantic input validation
- litellm for model-agnostic routing (Claude, GPT, Gemini, Ollama, vLLM, DeepSeek)
- FastAPI web GUI that dynamically generates forms from YAML templates
- Textual-based terminal panel (think Claude Code for lab instruments)
- SQLite + FTS5 experiment memory with frozen snapshots
- MCP server compatible with Claude Code / Cursor

Supports 46 measurement types across 9 disciplines — from basic IV curves to PPMS magnetoresistance to cyclic voltammetry.

MIT licensed. Looking for contributors who want to add templates for their measurement types.

https://github.com/Anai-Guo/LabAgent

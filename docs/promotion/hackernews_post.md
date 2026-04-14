# Hacker News Post Draft

**Title:** Show HN: LabAgent – Open-source AI assistant for automating lab measurements

**URL:** https://github.com/Anai-Guo/LabAgent

**Text (for comment):**

I built an open-source Python framework that connects LLMs to lab instruments for automated scientific measurements across physics, chemistry, biology, materials, and engineering labs.

The problem: researchers waste enormous time writing one-off measurement scripts (often in LabVIEW), with no safety checks and no institutional memory of what parameters worked before. Every discipline has the same pain — electrochemists hand-writing CV macros, biologists scripting plate-reader sequences, physicists re-inventing IV sweeps for each new sample.

LabAgent addresses this by putting AI at every step of the workflow:

1. Describe what you want to measure in natural language
2. AI scans your instruments via PyVISA / serial (GPIB, USB-TMC, RS-232)
3. AI classifies instruments into measurement roles
4. Generates a plan from 46 templates with 3-tier safety validation
5. Analyzes results and gives domain-specific interpretation

One nice detail: a `manual_lookup` tool that forces the AI to fetch the manufacturer's programming manual the moment it meets an unknown instrument, instead of inventing SCPI commands from its training data. Curated docs for ~25 vendors, with DuckDuckGo fallback when the vendor isn't in the index.

Technical highlights:
- Agent harness architecture (inspired by OpenHarness) with async query loop
- 9 standardized tools with Pydantic input validation
- litellm for model-agnostic routing (Claude, GPT, Gemini, Ollama, vLLM, DeepSeek)
- FastAPI web GUI that dynamically generates forms from YAML templates
- Textual-based terminal panel (think Claude Code for lab instruments)
- SQLite + FTS5 experiment memory with frozen snapshots
- MCP server compatible with Claude Code / Cursor

Covered instruments span the usual electrical/transport lineup (Keithley, Lakeshore, NI DAQ) plus Tektronix/Keysight/Rigol scopes+AWGs+PSUs, SRS/Zurich lock-ins, R&S and Keysight spectrum/VNAs, Thorlabs/Newport optical power meters and laser drivers, Ocean Insight spectrometers, BioLogic/Gamry/CH Instruments/Autolab/Palmsens potentiostats, BMG/Molecular Devices plate readers, Mettler/Ohaus balances, Orion pH meters, Alicat/MKS flow and pressure controllers, Oxford cryogenics, Quantum Design PPMS/MPMS. ~50 models across 15+ vendors.

46 measurement types across 9 disciplines — IV curves, R-T, cyclic voltammetry, EIS, UV-Vis absorbance, gas sensor response, Hall effect, PPMS magnetoresistance, and more.

MIT licensed. Looking for contributors who want to add templates or drivers for their specific measurement types.

https://github.com/Anai-Guo/LabAgent

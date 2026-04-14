---
title: 'LabAgent: An Open-Source AI-Guided Framework for Automated Scientific Measurements'
tags:
  - Python
  - laboratory automation
  - artificial intelligence
  - instrument control
  - measurement planning
authors:
  - name: Anai Guo
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 13 April 2026
bibliography: paper.bib
---

# Summary

LabAgent is an open-source Python framework that connects large language models (LLMs) to laboratory instruments for automated scientific measurements. The framework provides AI-guided measurement planning, instrument discovery and classification, safety boundary validation, data analysis with domain-specific interpretation, and experiment memory — covering 46 measurement types across 9 scientific disciplines and ~50 instrument models across 15+ manufacturers.

# Statement of Need

High-precision laboratory measurements in physics, chemistry, biology, and materials science require complex instrument orchestration, parameter optimization, and data analysis. Researchers currently face a choice between expensive proprietary software (e.g., LabVIEW) or writing custom measurement scripts from scratch for each experiment. Both approaches are time-consuming, error-prone, and lack safety guarantees.

While instrument control libraries such as PyVISA [@pyvisa] and PyMeasure [@pymeasure] provide foundational drivers, and measurement suites like PICA [@pica] offer hardcoded GUIs for specific instruments, no existing tool combines AI reasoning with instrument control in a unified, extensible framework.

LabAgent addresses this gap by placing AI at every step of the measurement workflow: from literature-informed protocol discovery to adaptive measurement planning with three-tier safety validation, to AI-generated data analysis with domain-specific scientific interpretation.

# Architecture

The framework follows an agent harness architecture inspired by OpenHarness [@openharness], with four core subsystems:

1. **Tool Registry**: Eight standardized tools (scan, classify, propose, validate, literature search, analyze, memory recall, healthcheck), each following a `BaseTool` abstract interface with Pydantic input validation.

2. **Agent Engine**: An asynchronous query loop that processes user messages, invokes LLMs via litellm [@litellm] for model-agnostic routing, detects tool calls, executes them with permission checks, and streams results back to the user.

3. **Permission System**: A three-layer safety model with immutable absolute limits (e.g., maximum current 10 A), boundary checks loaded from YAML policies, and interactive user confirmation for potentially dangerous operations.

4. **Multiple Interfaces**: A Model Context Protocol (MCP) server for AI IDE integration, a command-line interface with 11 subcommands, a FastAPI web GUI with adaptive measurement forms, and a Textual-based terminal panel for interactive sessions.

## Measurement Coverage

The framework includes 46 YAML-based measurement templates spanning:

- **Electrical characterization**: IV curves, R-T, delta mode, high resistance, FET transfer/output, breakdown voltage
- **Electrochemistry**: Cyclic voltammetry, EIS, chronoamperometry, potentiometry
- **Semiconductor**: Solar cell IV, DLTS, photocurrent spectroscopy, C-f analysis, tunneling spectroscopy
- **Optics and photonics**: Optical power measurement, UV-Vis absorbance, photoresponse transients
- **Biological / analytical**: Plate-reader absorbance / fluorescence / luminescence, biosensor impedance, mass weighing, pH and ISE readout
- **Environmental and sensor**: Gas sensor, humidity response, strain gauge, fatigue, mass flow, pressure control
- **Thermoelectric**: Seebeck coefficient, thermal conductivity
- **Magnetic and transport (condensed-matter specialty)**: Hall effect, magnetoresistance, anomalous Hall effect, FMR, hysteresis loops, magnetostriction, Nernst effect, SOT loop shift
- **Superconductivity**: Tc transition, critical current density
- **Dielectric / ferroelectric**: P-E loop, pyroelectric current
- **Quantum Design systems**: PPMS R-T / MR / Hall / heat capacity, MPMS M-H / M-T with MultiPyVu integration

## AI Capabilities

The framework provides eight distinct AI capabilities:

1. **Instrument Classification**: Dictionary-based lookup with LLM fallback for unknown instruments
2. **Parameter Optimization**: LLM suggests optimal sweep ranges based on sample description and literature
3. **Safety Advisory**: LLM explains why limits exist and suggests safer alternatives
4. **Script Generation**: LLM creates custom analysis scripts for arbitrary measurement types
5. **Result Interpretation**: LLM provides domain-specific scientific insights on extracted values (physics, electrochemistry, spectroscopy, etc.)
6. **Skill Generation**: LLM creates new measurement protocols from existing examples
7. **Agent Chat**: Multi-turn conversation with autonomous tool calling
8. **Experiment Memory**: SQLite with FTS5 full-text search, frozen snapshots injected into agent context

# Acknowledgements

Measurement procedures reference patterns from the PICA project [@pica]. Agent architecture is inspired by OpenHarness [@openharness] and Hermes Agent [@hermes]. The framework uses litellm [@litellm] for model routing and PyVISA [@pyvisa] for instrument communication.

# References

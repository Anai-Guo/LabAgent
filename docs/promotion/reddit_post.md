# Reddit Post Draft

**Subreddits:** r/Physics, r/CondensedMatter, r/MaterialsScience, r/chemistry, r/labautomation, r/Python

---

**Title:** I built an open-source AI assistant that automates lab measurements — 46 templates, 9 disciplines, works with any GPIB instrument

**Body:**

Hey everyone,

I got tired of writing measurement scripts from scratch every time I needed a new IV curve, Hall effect measurement, or cyclic voltammetry run. So I built **LabAgent** — an open-source framework that uses AI to guide you through the entire measurement workflow.

**What it does:**
- You tell it what you want to measure in plain English
- It scans your lab instruments (Keithley, Lakeshore, Keysight, NI-DAQ, PPMS/MPMS)
- AI classifies instruments into measurement roles
- Generates a measurement plan with safety boundaries (so you don't fry your samples)
- Analyzes your data and explains the physics

**Key features:**
- 46 measurement templates (IV, R-T, Hall, MR, EIS, solar cell IV, DLTS, and many more)
- Covers 9 disciplines: physics, chemistry, biology, materials science, semiconductor, thermoelectric, superconductivity, dielectric, environmental sensors
- Works with 6 AI providers (Claude, GPT, Gemini, Ollama for local/private)
- Web GUI with real-time monitoring panels
- Terminal panel (like Claude Code but for lab instruments)
- 3-tier safety system that prevents dangerous configurations
- MCP server for integration with Claude Code / Cursor

**Install:**
```
pip install git+https://github.com/Anai-Guo/LabAgent.git
labharness scan          # discover your instruments
labharness propose hall  # generate a Hall effect plan
labharness web           # launch the web GUI
labharness panel         # Claude Code-style terminal
```

GitHub: https://github.com/Anai-Guo/LabAgent

It's MIT licensed and we're actively looking for contributors — especially people who can add templates for their specific measurement types. If you use instruments that aren't covered yet, open an issue and we'll add support.

Would love feedback from people who actually do lab measurements daily. What would make this more useful for your workflow?

# Reddit Post Draft

**Subreddits:** r/labautomation, r/Python, r/chemistry, r/Physics, r/MaterialsScience, r/bioinformatics, r/electrochemistry, r/photonics

---

**Title:** I built an open-source AI assistant that automates lab measurements — 46 templates across physics, chemistry, biology, and more

**Body:**

Hey everyone,

I got tired of watching researchers in every discipline write one-off measurement scripts from scratch — chemists writing CV macros in Gamry, biologists scripting plate-reader sequences, physicists re-inventing IV sweeps, optics folks hand-coding PM100D loops. Every lab, same pain. So I built **LabAgent** — an open-source framework that uses AI to guide you through the entire measurement workflow.

**What it does:**
- You tell it what you want to measure in plain English
- It scans your lab instruments over GPIB / USB-TMC / RS-232
- AI classifies instruments into measurement roles
- Generates a measurement plan with safety boundaries (so you don't fry your samples)
- Analyzes your data and explains what the results mean

**Coverage (~50 models across 15+ vendors):**
- Electrical/transport: Keithley 2400/6221/2182A/6517, NI DAQ, Lakeshore cryogenics
- Signals & RF: Tektronix / Keysight / Rigol scopes + AWGs, SRS & Zurich lock-ins, R&S and Keysight spectrum/VNAs
- Optics/photonics: Thorlabs PM100D / LDC205C / MDT693B, Newport 1830-C, Ocean Insight spectrometers
- Electrochemistry: BioLogic SP-200/VSP, Gamry Reference 600+, CH Instruments CHI760E, Autolab PGSTAT, Palmsens4
- Biology: BMG CLARIOstar, Molecular Devices SpectraMax plate readers
- Analytical: Mettler/Ohaus balances, Orion pH meters, Alicat MFCs, MKS pressure controllers
- Condensed-matter specialty: Quantum Design PPMS/MPMS

**Key features:**
- 46 measurement templates: IV, R-T, CV, EIS, chronoamperometry, UV-Vis absorbance, gas sensor response, photocurrent, Hall effect, and many more
- Works with 6 AI providers (Claude, GPT, Gemini, Ollama for local/private, vLLM, DeepSeek)
- Mandatory "look up the manual online" rule — the AI fetches the manufacturer's programming guide instead of guessing SCPI commands
- Web GUI with real-time monitoring panels
- Terminal panel (like Claude Code but for lab instruments)
- 3-tier safety system that prevents dangerous configurations
- MCP server for integration with Claude Code / Cursor

**Install:**
```
pip install git+https://github.com/Anai-Guo/LabAgent.git
labharness scan          # discover your instruments
labharness propose iv    # generate an IV curve plan
labharness web           # launch the web GUI
labharness panel         # Claude Code-style terminal
```

GitHub: https://github.com/Anai-Guo/LabAgent

MIT licensed; contributors welcome — if your instrument isn't covered yet, open an issue with its `*IDN?` string and a manual link. Especially looking for more chemistry, biology, and photonics measurement templates.

Would love feedback from anyone who does lab measurements daily. What would make this more useful for your workflow?

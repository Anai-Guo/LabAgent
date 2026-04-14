# Twitter/X Thread Draft

---

**Tweet 1 (Hook):**

🧪 I just open-sourced LabAgent — a framework that connects AI directly to your lab instruments.

46 measurement templates. ~50 instrument models. 9 disciplines — physics, chemistry, biology, materials, optics, more.

No more writing scripts from scratch. No more LabVIEW.

🧵👇

---

**Tweet 2 (Problem):**

The problem every lab researcher knows:

❌ Write a new Python script for every measurement
❌ AI hallucinates SCPI commands that don't exist on your model
❌ No safety checks (hope you don't fry the sample)
❌ Forget what parameters worked last time
❌ Hours of manual data analysis

---

**Tweet 3 (Solution):**

LabAgent fixes this:

✅ Tell AI what to measure → it plans everything
✅ Mandatory manual_lookup tool — AI fetches the real programming manual before writing SCPI
✅ 3-tier safety boundaries (block/confirm/allow)
✅ Experiment memory (learns what worked)
✅ AI-generated analysis + domain-specific interpretation

---

**Tweet 4 (Demo):**

```
labharness scan         → finds your instruments
labharness propose iv   → generates a plan
labharness analyze …    → figures + interpretation
labharness web          → adaptive GUI
labharness panel        → Claude Code-style terminal
```

Works with ~50 models from 15+ vendors.

---

**Tweet 5 (Disciplines & instruments):**

46 templates across 9 disciplines:

⚡ Electrical: IV, R-T, delta-mode (Keithley, NI)
🧪 Electrochemistry: CV, EIS, CA (BioLogic, Gamry, CHI, Autolab)
💡 Optics: power, UV-Vis, photoresponse (Thorlabs, Ocean Insight)
🧬 Biology: plate-reader absorbance/fluorescence (BMG, Molecular Devices)
📡 RF/signals: scopes, AWGs, lock-ins, VNAs (Tek, Keysight, R&S, Zurich, SRS)
🌡️ Analytical: balance, pH, MFC (Mettler, Orion, Alicat)
❄️ Cryogenic: Lakeshore, Oxford, Quantum Design PPMS/MPMS
+ semiconductor, dielectric, sensor templates

---

**Tweet 6 (AI Models):**

Works with ANY AI model:

☁️ Claude Sonnet 4 (best quality)
☁️ GPT-4o (fast)
🏠 Ollama/Qwen3 (local, free, private)
🏠 vLLM (self-hosted)

Switch with one config line. Your data stays private.

---

**Tweet 7 (CTA):**

⭐ Star on GitHub: https://github.com/Anai-Guo/LabAgent

Install: pip install git+https://github.com/Anai-Guo/LabAgent.git

MIT licensed. Contributions welcome — add your measurement template or instrument in 5 minutes.

What measurement do YOU want to automate?

---

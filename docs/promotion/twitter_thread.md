# Twitter/X Thread Draft

---

**Tweet 1 (Hook):**

🧪 I just open-sourced LabAgent — the first framework that connects AI directly to your lab instruments.

46 measurement templates. 9 disciplines. Works with Claude, GPT, or local models.

No more writing scripts from scratch. No more LabVIEW.

🧵👇

---

**Tweet 2 (Problem):**

The problem every lab researcher knows:

❌ Write a new Python script for every measurement
❌ No safety checks (hope you don't fry the sample)
❌ Forget what parameters worked last time
❌ Hours of manual data analysis

---

**Tweet 3 (Solution):**

LabAgent fixes this:

✅ Tell AI what to measure → it plans everything
✅ 3-tier safety boundaries (block/confirm/allow)
✅ Experiment memory (learns what worked)
✅ AI-generated analysis scripts + physics interpretation

---

**Tweet 4 (Demo):**

```
labharness scan        → finds your instruments
labharness propose IV  → generates measurement plan
labharness web         → adaptive GUI
labharness panel       → Claude Code-style terminal
```

Works with Keithley, Lakeshore, Keysight, NI-DAQ, PPMS, MPMS.

---

**Tweet 5 (Disciplines):**

46 templates across 9 disciplines:

⚡ Physics (IV, Hall, MR, FMR, tunneling)
🧪 Chemistry (CV, EIS, chronoamperometry)
💡 Semiconductor (solar cell, DLTS, FET curves)
❄️ Superconductivity (Tc, Jc)
🔋 Dielectric (P-E loop, pyroelectric)
🌡️ Thermoelectric (Seebeck, thermal conductivity)
🧬 Biology (biosensor impedance)
🔧 Materials (strain, fatigue, humidity)
🔬 Quantum Design (PPMS/MPMS)

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

MIT licensed. Contributions welcome — add your measurement template in 5 minutes.

What measurement do YOU want to automate?

---

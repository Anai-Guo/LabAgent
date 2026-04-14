# Installation

## Basic Install
```bash
pip install git+https://github.com/Anai-Guo/LabAgent.git
```

## With Optional Features
```bash
# Web GUI
pip install "lab-agent[web]"

# Terminal panel
pip install "lab-agent[tui]"

# Instrument drivers
pip install "lab-agent[execution]"

# All features
pip install "lab-agent[web,tui,execution]"

# Development
pip install -e ".[dev]"
```

## Requirements
- Python 3.10+
- NI-VISA driver (for GPIB instruments)
- An AI API key (or local Ollama)

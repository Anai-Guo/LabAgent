"""Reference measurement procedures adapted from PICA project.

These are standard instrument control sequences for common measurement types,
based on patterns from the PICA project (MIT License, UGC-DAE CSR Mumbai).
Reference: https://github.com/prathameshnium/PICA-Python-Instrument-Control-and-Automation
"""

from __future__ import annotations

# Keithley 2400 SourceMeter control sequences
K2400_INIT_SEQUENCE = [
    "*RST",  # Reset to defaults
    ":SOUR:FUNC CURR",  # Source current mode
    ":SOUR:CURR:RANG:AUTO ON",  # Auto-range
    ":SENS:FUNC 'VOLT'",  # Measure voltage
    ":SENS:VOLT:PROT {compliance}",  # Set compliance voltage
    ":SENS:VOLT:RANG:AUTO ON",  # Auto-range sense
    ":FORM:ELEM VOLT,CURR",  # Return V and I
]

K2400_IV_SWEEP = [
    ":SOUR:CURR {current}",  # Set source current
    ":OUTP ON",  # Enable output
    # ... wait settling_time ...
    ":READ?",  # Trigger and read
]

K2400_SHUTDOWN = [
    ":SOUR:CURR 0",  # Zero current
    ":OUTP OFF",  # Disable output
]

# Keithley 6221 + 2182A Delta Mode (Ultra-low resistance)
K6221_DELTA_INIT = [
    "*RST",
    ":SYST:COMM:SER:SEND ':SENS:FUNC \"VOLT\"'",  # Configure 2182A
    ":SYST:COMM:SER:SEND ':SENS:VOLT:CHAN1:RANG:AUTO ON'",
    ":SOUR:DELT:HIGH {current}",  # High current
    ":SOUR:DELT:LOW {low_current}",  # Low current (negative)
    ":SOUR:DELT:DEL {delay}",  # Delay between pulses
    ":SOUR:DELT:COUN {count}",  # Number of readings
]

# Lakeshore 350 Temperature Control
LS350_TEMP_SEQUENCE = [
    "SETP {loop},{setpoint}",  # Set target temperature
    "RANGE {loop},{range}",  # Set heater range
    "RAMP {loop},1,{rate}",  # Enable ramp at rate K/min
    # ... poll KRDG? until stable ...
    "KRDG? {input}",  # Read temperature
]

# Keysight E4980A LCR Meter
E4980A_CV_SEQUENCE = [
    "*RST",
    ":FUNC:IMP CPD",  # Capacitance + Dissipation
    ":FREQ {frequency}",  # Set test frequency
    ":VOLT:LEV {ac_voltage}",  # AC test voltage
    ":BIAS:VOLT:LEV {dc_bias}",  # DC bias voltage
    ":TRIG:SOUR BUS",  # Bus trigger
    ":INIT",  # Initialize
    ":TRIG",  # Trigger measurement
    ":FETC?",  # Fetch result
]

# Measurement procedure templates
PROCEDURES = {
    "IV_K2400": {
        "description": "IV curve using Keithley 2400 SourceMeter",
        "init": K2400_INIT_SEQUENCE,
        "measure": K2400_IV_SWEEP,
        "shutdown": K2400_SHUTDOWN,
        "parameters": {
            "compliance": "20",  # V
            "current_start": "-1e-3",
            "current_stop": "1e-3",
            "current_step": "1e-5",
            "settling_time": "0.1",
        },
    },
    "DELTA_K6221": {
        "description": "Ultra-low resistance via K6221+K2182A delta mode",
        "init": K6221_DELTA_INIT,
        "parameters": {
            "current": "1e-3",
            "low_current": "-1e-3",
            "delay": "0.002",
            "count": "100",
        },
    },
    "RT_LS350": {
        "description": "R-T measurement with Lakeshore 350 temperature control",
        "init": LS350_TEMP_SEQUENCE,
        "parameters": {
            "loop": "1",
            "setpoint": "300",
            "range": "3",
            "rate": "2",
            "input": "A",
        },
    },
    "CV_E4980A": {
        "description": "C-V measurement with Keysight E4980A",
        "init": E4980A_CV_SEQUENCE,
        "parameters": {
            "frequency": "1E3",
            "ac_voltage": "0.5",
            "dc_bias": "0",
        },
    },
}


def get_procedure(name: str) -> dict | None:
    """Get a reference measurement procedure by name."""
    return PROCEDURES.get(name)


def list_procedures() -> list[str]:
    """List all available reference procedures."""
    return list(PROCEDURES.keys())

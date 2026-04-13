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

# Keithley 6517B Electrometer (High Resistance)
K6517B_INIT = [
    "*RST",
    ":SENS:FUNC 'CURR'",  # Measure current
    ":SENS:CURR:RANG:AUTO ON",  # Auto-range
    ":SOUR:VOLT:RANG {voltage_range}",  # Source voltage range
    ":SOUR:VOLT {voltage}",  # Source voltage
    ":FORM:ELEM READ",  # Return reading only
]

K6517B_MEASURE = [
    ":OUTP ON",  # Enable voltage source
    # ... wait settling_time ...
    ":READ?",  # Trigger and read
]

K6517B_SHUTDOWN = [
    ":SOUR:VOLT 0",  # Zero voltage
    ":OUTP OFF",  # Disable output
]

# Keithley 2182A Nanovoltmeter
K2182A_INIT = [
    "*RST",
    ":SENS:FUNC 'VOLT'",  # Measure voltage
    ":SENS:VOLT:CHAN1:RANG:AUTO ON",  # Auto-range
    ":SENS:VOLT:NPLC 5",  # 5 power line cycles for low noise
    ":SYST:FAZ ON",  # Front autozero
]

K2182A_MEASURE = [
    ":INIT",  # Initialize measurement
    ":FETC?",  # Fetch reading
]

# Keithley 2000 Multimeter
K2000_INIT = [
    "*RST",
    ":SENS:FUNC 'VOLT:DC'",  # DC voltage mode
    ":SENS:VOLT:DC:RANG:AUTO ON",  # Auto-range
    ":SENS:VOLT:DC:NPLC 10",  # 10 NPLC for high accuracy
]

K2000_MEASURE = [
    ":INIT",  # Initialize measurement
    ":FETC?",  # Fetch reading
]

# Stanford Research SR830 Lock-In Amplifier
SR830_INIT = [
    "OUTX 1",  # GPIB output
    "SENS {sensitivity}",  # Sensitivity
    "OFLT {time_constant}",  # Time constant
    "RMOD 1",  # R, theta output
]

SR830_MEASURE = [
    "SNAP? 3,4",  # Read R, theta simultaneously
]

# Agilent 34401A / Keysight 34461A Multimeter
A34401_INIT = [
    "*RST",
    "CONF:VOLT:DC {range}",  # Configure DC voltage
    "VOLT:DC:NPLC {nplc}",  # Integration time
    "TRIG:SOUR IMM",  # Immediate trigger
]

A34401_MEASURE = [
    "READ?",  # Trigger and read
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
    "HIGH_R_K6517B": {
        "description": "High resistance measurement with Keithley 6517B electrometer",
        "init": K6517B_INIT,
        "measure": K6517B_MEASURE,
        "shutdown": K6517B_SHUTDOWN,
        "parameters": {
            "voltage_range": "100",  # V
            "voltage": "10",  # V
            "settling_time": "2.0",  # s (high-R needs longer settling)
        },
    },
    "NANOVOLT_K2182A": {
        "description": "Low-noise nanovoltage measurement with Keithley 2182A",
        "init": K2182A_INIT,
        "measure": K2182A_MEASURE,
        "parameters": {
            "nplc": "5",  # power line cycles
        },
    },
    "DMM_K2000": {
        "description": "General-purpose DC voltage/resistance with Keithley 2000",
        "init": K2000_INIT,
        "measure": K2000_MEASURE,
        "parameters": {
            "nplc": "10",  # power line cycles
        },
    },
    "LOCKIN_SR830": {
        "description": "AC measurement with Stanford Research SR830 lock-in amplifier",
        "init": SR830_INIT,
        "measure": SR830_MEASURE,
        "parameters": {
            "sensitivity": "10",  # index: 10 = 50 mV
            "time_constant": "8",  # index: 8 = 100 ms
        },
    },
    "DMM_A34401": {
        "description": "General-purpose DMM with Agilent 34401A / Keysight 34461A",
        "init": A34401_INIT,
        "measure": A34401_MEASURE,
        "parameters": {
            "range": "10",  # V
            "nplc": "10",  # power line cycles
        },
    },
}


def get_procedure(name: str) -> dict | None:
    """Get a reference measurement procedure by name."""
    return PROCEDURES.get(name)


def list_procedures() -> list[str]:
    """List all available reference procedures."""
    return list(PROCEDURES.keys())

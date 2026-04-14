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

# Quantum Design PPMS (via MultiPyVu)
PPMS_INIT = [
    "# pip install MultiPyVu",
    "# import MultiPyVu as mpv",
    "# client = mpv.Client()",
    "# client.open()",
]

PPMS_TEMP_SEQUENCE = [
    "client.set_temperature({setpoint}, {rate}, client.temperature.approach_mode.fast_settle)",
    "client.wait_for(0, 0, client.subsystem.temperature)",  # Wait for stable
    "temp, status = client.get_temperature()",
]

PPMS_FIELD_SEQUENCE = [
    "client.set_field({field}, {rate}, client.field.approach_mode.linear, client.field.mode.persistent)",
    "client.wait_for(0, 0, client.subsystem.field)",  # Wait for stable
    "field, status = client.get_field()",
]

# Quantum Design MPMS3 (via MultiPyVu)
MPMS_MEASURE = [
    "client.set_field({field}, {rate})",
    "client.wait_for(0, 0, client.subsystem.field)",
    "# Read DC magnetization from MPMS data file",
]

# ── Tektronix TDS3000 / DPO / MSO series oscilloscope ──────────────────
# Manual: https://www.tek.com/en/manual/tds3000-series-programmer-manual
TEK_SCOPE_INIT = [
    "*RST",
    "HEADER OFF",
    "DATA:SOURCE CH{channel}",
    "DATA:WIDTH 2",
    "DATA:ENC RIBINARY",
    "ACQUIRE:MODE SAMPLE",
    "HORIZONTAL:SCALE {timebase}",
    "CH{channel}:SCALE {vscale}",
]

TEK_SCOPE_CAPTURE = [
    "ACQUIRE:STATE RUN",
    # ... wait for trigger ...
    "CURVE?",  # Returns binary waveform
    "WFMPRE?",  # Preamble with scaling info
]

# ── Keysight InfiniiVision DSOX / MSOX oscilloscope ────────────────────
# Manual: https://www.keysight.com/us/en/assets/9018-07252/programming-guides/9018-07252.pdf
KEYSIGHT_SCOPE_INIT = [
    "*RST",
    ":CHAN{channel}:DISP ON",
    ":CHAN{channel}:SCALE {vscale}",
    ":TIM:SCALE {timebase}",
    ":TRIG:MODE EDGE",
    ":TRIG:EDGE:SOUR CHAN{channel}",
    ":TRIG:EDGE:LEV {trigger_level}",
]

KEYSIGHT_SCOPE_CAPTURE = [
    ":DIG CHAN{channel}",
    ":WAV:SOUR CHAN{channel}",
    ":WAV:FORM WORD",
    ":WAV:DATA?",
    ":WAV:PRE?",
]

# ── Keysight 33500B / 33622A function generator (SCPI) ─────────────────
KEYSIGHT_FGEN_INIT = [
    "*RST",
    ":SOUR{channel}:FUNC {shape}",  # SIN, SQU, RAMP, PULS, NOIS, ARB
    ":SOUR{channel}:FREQ {frequency}",
    ":SOUR{channel}:VOLT {amplitude}",
    ":SOUR{channel}:VOLT:OFFS {offset}",
    ":OUTP{channel} ON",
]

KEYSIGHT_FGEN_SHUTDOWN = [
    ":OUTP{channel} OFF",
]

# ── Rigol / Tektronix AFG / Keysight 33500B modulation add-on ──────────
FGEN_MODULATION_SETUP = [
    ":SOUR{channel}:AM:STAT ON",
    ":SOUR{channel}:AM:DEPT {depth_percent}",
    ":SOUR{channel}:AM:INT:FREQ {mod_frequency}",
]

# ── Keysight E36300 programmable DC power supply ───────────────────────
E36313A_INIT = [
    "*RST",
    ":INST:SEL CH{channel}",
    ":VOLT {voltage}",
    ":CURR {current_limit}",
    ":OUTP ON",
]

E36313A_MEASURE = [
    ":MEAS:VOLT? CH{channel}",
    ":MEAS:CURR? CH{channel}",
]

E36313A_SHUTDOWN = [
    ":OUTP OFF",
    ":VOLT 0",
]

# ── SR860 / SR865A lock-in amplifier (SCPI-style) ──────────────────────
SR860_INIT = [
    "*RST",
    "TBMODE 0",  # Time constant
    "SCAL {sensitivity}",  # Sensitivity index
    "OFLT {time_constant}",  # Time constant index
    "FREQ {frequency}",  # Internal reference frequency
    "SLVL {amplitude}",  # Sine output amplitude
]

SR860_MEASURE = [
    "SNAP? 1,2,3,4",  # X, Y, R, theta simultaneously
]

# ── Zurich Instruments MFLI (Python API, zhinst-toolkit) ───────────────
# Not SCPI — uses Data Server over TCP. Document the equivalent Python.
ZURICH_MFLI_INIT = [
    "# pip install zhinst-toolkit",
    "from zhinst.toolkit import Session",
    "session = Session('{host}')",
    "device = session.connect_device('{device_serial}')",
    "device.demods[0].enable(True)",
    "device.demods[0].rate({rate_hz})",
    "device.demods[0].timeconstant({time_constant_s})",
    "device.oscs[0].freq({frequency_hz})",
]

ZURICH_MFLI_MEASURE = [
    "sample = device.demods[0].sample()",
    "# sample['x'], sample['y'], sample['r'] available",
]

# ── Thorlabs PM100D optical power meter (USB-TMC SCPI) ─────────────────
# Manual: https://www.thorlabs.com/drawings/e7aed74fde84d4b0-PM100D-Manual.pdf
PM100D_INIT = [
    "*RST",
    "CONF:POW",  # Configure for optical power
    "SENS:CORR:WAV {wavelength_nm}",  # Set wavelength for responsivity
    "SENS:POW:UNIT W",  # Units: watts
    "SENS:POW:RANG:AUTO ON",  # Auto-range
    "AVER {average_count}",  # Number of readings to average
]

PM100D_MEASURE = [
    "READ?",  # Trigger and return optical power
]

# ── Ocean Insight spectrometer (python-seabreeze) ──────────────────────
# Not SCPI — USB binary protocol via seabreeze.
OCEAN_INSIGHT_INIT = [
    "# pip install seabreeze",
    "import seabreeze.spectrometers as sb",
    "spec = sb.Spectrometer.from_first_available()",
    "spec.integration_time_micros({integration_us})",
    "# For dark-corrected reading: spec.spectrum(correct_dark_counts=True)",
]

OCEAN_INSIGHT_MEASURE = [
    "wavelengths = spec.wavelengths()",
    "intensities = spec.intensities()",
]

# ── BioLogic potentiostat (easy-biologic wrapper around EClib DLL) ─────
# EClib is a C DLL; use the easy-biologic Python wrapper.
BIOLOGIC_CV_INIT = [
    "# pip install easy-biologic",
    "import easy_biologic as ebl",
    "device = ebl.BiologicDevice('{ip_or_usb_address}')",
    "device.connect()",
    "technique = ebl.programs.CV(",
    "    device,",
    "    params={{",
    "        'start': {e_begin},",
    "        'end': {e_vertex},",
    "        'step': {e_step},",
    "        'rate': {scan_rate_mV_per_s},",
    "        'n_cycles': {n_cycles},",
    "    }},",
    "    channels=[0],",
    ")",
]

BIOLOGIC_CV_MEASURE = [
    "technique.run()",
    "data = technique.data[0]",
]

# ── Gamry potentiostat (COM/ActiveX automation) ────────────────────────
# Use pywin32 to drive Gamry Framework's COM object.
GAMRY_CV_INIT = [
    "# pip install pywin32",
    "import win32com.client",
    "framework = win32com.client.Dispatch('GamryFramework.Application')",
    "pstat = framework.Devices.Pstats(0)",
    "pstat.Open()",
    "pstat.SetCell(GamryCOM.CellOn)",
]

GAMRY_CV_MEASURE = [
    "# Run CV via Gamry's pre-defined experiment DTA file or script",
    "experiment.Run()",
    "# Results read from output .DTA file",
]

# ── CH Instruments potentiostat (macro .mcr file driven) ───────────────
# Use the `hardpotato` wrapper which writes macro files and invokes the CLI.
CHI_CV_INIT = [
    "# pip install hardpotato",
    "import hardpotato as hp",
    "setup = hp.potentiostat.Setup('CHI760E', path='C:/CH Instruments/chi760e.exe')",
    "cv = hp.experiments.CV(",
    "    eini={e_begin},",
    "    ev1={e_vertex1},",
    "    ev2={e_vertex2},",
    "    efin={e_final},",
    "    sr={scan_rate_V_per_s},",
    "    dE={e_step},",
    "    nSweeps={n_cycles},",
    ")",
]

CHI_CV_MEASURE = [
    "cv.run(fileName='{output_file}', header='{title}')",
]

# ── Alicat mass flow controller (ASCII-line over RS-232/485) ───────────
# Manual: https://www.alicat.com/documents/
ALICAT_INIT = [
    "# Use numat/alicat Python driver or pyserial directly",
    "# Default address 'A' on RS-232/485",
    "# Commands are ASCII, terminated with \\r",
]

ALICAT_SET_FLOW = [
    "A S{setpoint_sccm}\r",  # Set flow setpoint (replace A with address)
    "A\r",  # Read current state: pressure, temp, flow, setpoint, gas
]

ALICAT_SHUTDOWN = [
    "A S0\r",  # Flow setpoint to 0
]

# ── Mettler Toledo balance (MT-SICS ASCII over RS-232/USB) ─────────────
# Manual: MT-SICS Interface Commands manual (any Mettler XS/XP series)
METTLER_INIT = [
    "# RS-232: 9600 8N1 or USB serial. Commands terminated with CR+LF.",
    "I0",  # Get software version string
    "S",  # Stable weight value (kg/g per balance config)
]

METTLER_READ_WEIGHT = [
    "S",  # Returns "S S 12.345 g" when stable
    # For immediate (possibly unstable) read: "SI"
]

METTLER_ZERO = [
    "Z",  # Zero after stability
]

# ── Ohaus balance (simple ASCII over RS-232) ───────────────────────────
OHAUS_READ_WEIGHT = [
    "IP\r\n",  # Immediate print (any stability)
    # Alternative: "P\r\n" for stable-only
]

# ── Thermo Scientific Orion Star A221 pH meter (ASCII over RS-232) ─────
ORION_READ = [
    "GETMEAS",  # Return current measurement: pH, mV, T
]

# ── Oxford Instruments Mercury iTC (SCPI-like over GPIB/LAN) ───────────
OXFORD_ITC_INIT = [
    "READ:DEV:MB0.T1:TEMP:SIG:TEMP",  # Read mainboard sensor 1 temp
    "SET:DEV:MB0.H1:HTR:SIG:POWR:{power}",  # Set heater power (%)
    "SET:DEV:MB0.T1:TEMP:LOOP:TSET:{setpoint}",  # Set target temperature
]

OXFORD_ITC_READ = [
    "READ:DEV:MB0.T1:TEMP:SIG:TEMP",
]

# ── National Instruments DAQ (nidaqmx) ─────────────────────────────────
# Not SCPI — uses NI-DAQmx driver via nidaqmx-python.
NIDAQ_ANALOG_OUT = [
    "# pip install nidaqmx",
    "import nidaqmx",
    "with nidaqmx.Task() as task:",
    "    task.ao_channels.add_ao_voltage_chan('{device}/ao{channel}')",
    "    task.write({voltage})",
]

NIDAQ_ANALOG_IN = [
    "import nidaqmx",
    "with nidaqmx.Task() as task:",
    "    task.ai_channels.add_ai_voltage_chan('{device}/ai{channel}')",
    "    value = task.read()",
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
    "PPMS_RT": {
        "description": "R-T measurement with Quantum Design PPMS via MultiPyVu",
        "init": PPMS_INIT,
        "measure": PPMS_TEMP_SEQUENCE,
        "parameters": {
            "setpoint": "300",
            "rate": "2",  # K/min
        },
    },
    "PPMS_MR": {
        "description": "Magnetoresistance measurement with Quantum Design PPMS",
        "init": PPMS_INIT,
        "measure": PPMS_FIELD_SEQUENCE,
        "parameters": {
            "field": "90000",  # Oe
            "rate": "100",  # Oe/s
        },
    },
    "PPMS_HALL": {
        "description": "Hall effect measurement with Quantum Design PPMS",
        "init": PPMS_INIT,
        "measure": PPMS_FIELD_SEQUENCE,
        "parameters": {
            "field": "90000",  # Oe
            "rate": "100",  # Oe/s
        },
    },
    "PPMS_HC": {
        "description": "Heat capacity measurement with Quantum Design PPMS",
        "init": PPMS_INIT,
        "measure": PPMS_TEMP_SEQUENCE,
        "parameters": {
            "setpoint": "300",
            "rate": "2",  # K/min
        },
    },
    "MPMS_MH": {
        "description": "M-H loop measurement with Quantum Design MPMS/SQUID",
        "init": PPMS_INIT,
        "measure": MPMS_MEASURE,
        "parameters": {
            "field": "70000",  # Oe
            "rate": "100",  # Oe/s
        },
    },
    "MPMS_MT": {
        "description": "M-T (ZFC/FC) measurement with Quantum Design MPMS/SQUID",
        "init": PPMS_INIT,
        "measure": PPMS_TEMP_SEQUENCE,
        "parameters": {
            "setpoint": "400",
            "rate": "2",  # K/min
        },
    },
    # ── Oscilloscopes ──────────────────────────────────────────────────
    "SCOPE_CAPTURE_TEK": {
        "description": "Capture a waveform on Tektronix TDS/DPO/MSO oscilloscope",
        "init": TEK_SCOPE_INIT,
        "measure": TEK_SCOPE_CAPTURE,
        "parameters": {
            "channel": "1",
            "timebase": "1e-3",  # s/div
            "vscale": "1.0",  # V/div
        },
    },
    "SCOPE_CAPTURE_KEYSIGHT": {
        "description": "Capture a waveform on Keysight DSOX/MSOX oscilloscope",
        "init": KEYSIGHT_SCOPE_INIT,
        "measure": KEYSIGHT_SCOPE_CAPTURE,
        "parameters": {
            "channel": "1",
            "timebase": "1e-3",
            "vscale": "1.0",
            "trigger_level": "0.5",
        },
    },
    # ── Function generators ────────────────────────────────────────────
    "FGEN_KEYSIGHT": {
        "description": "Drive a Keysight 33500B/33622A function generator",
        "init": KEYSIGHT_FGEN_INIT,
        "shutdown": KEYSIGHT_FGEN_SHUTDOWN,
        "parameters": {
            "channel": "1",
            "shape": "SIN",  # SIN, SQU, RAMP, PULS, NOIS, ARB
            "frequency": "1E3",
            "amplitude": "1.0",  # Vpp
            "offset": "0.0",
        },
    },
    # ── DC power supplies ─────────────────────────────────────────────
    "PSU_KEYSIGHT_E36300": {
        "description": "Programmable DC output on Keysight E36313A triple-output PSU",
        "init": E36313A_INIT,
        "measure": E36313A_MEASURE,
        "shutdown": E36313A_SHUTDOWN,
        "parameters": {
            "channel": "1",
            "voltage": "5.0",
            "current_limit": "0.5",
        },
    },
    # ── Lock-in amplifiers ────────────────────────────────────────────
    "LOCKIN_SR860": {
        "description": "SR860/SR865A lock-in amplifier (successor to SR830)",
        "init": SR860_INIT,
        "measure": SR860_MEASURE,
        "parameters": {
            "sensitivity": "16",  # index
            "time_constant": "10",  # index
            "frequency": "1000",  # Hz (internal reference)
            "amplitude": "0.1",  # V sine output
        },
    },
    "LOCKIN_ZURICH_MFLI": {
        "description": "Zurich Instruments MFLI via zhinst-toolkit Python API",
        "init": ZURICH_MFLI_INIT,
        "measure": ZURICH_MFLI_MEASURE,
        "parameters": {
            "host": "localhost",
            "device_serial": "dev3000",
            "rate_hz": "1000",
            "time_constant_s": "0.01",
            "frequency_hz": "10000",
        },
    },
    # ── Optics / Photonics ────────────────────────────────────────────
    "OPTICAL_POWER_PM100D": {
        "description": "Optical power measurement with Thorlabs PM100D / PM400",
        "init": PM100D_INIT,
        "measure": PM100D_MEASURE,
        "parameters": {
            "wavelength_nm": "633",
            "average_count": "10",
        },
    },
    "UV_VIS_OCEAN_INSIGHT": {
        "description": "UV-Vis absorbance/transmission spectrum with Ocean Insight spectrometer",
        "init": OCEAN_INSIGHT_INIT,
        "measure": OCEAN_INSIGHT_MEASURE,
        "parameters": {
            "integration_us": "100000",  # 100 ms
        },
    },
    # ── Electrochemistry ──────────────────────────────────────────────
    "CV_BIOLOGIC": {
        "description": "Cyclic voltammetry on BioLogic SP-200/VSP/VMP3 via easy-biologic",
        "init": BIOLOGIC_CV_INIT,
        "measure": BIOLOGIC_CV_MEASURE,
        "parameters": {
            "ip_or_usb_address": "192.168.1.100",
            "e_begin": "-0.5",
            "e_vertex": "0.5",
            "e_step": "0.001",
            "scan_rate_mV_per_s": "100",
            "n_cycles": "3",
        },
    },
    "CV_GAMRY": {
        "description": "Cyclic voltammetry on Gamry Reference 600+/Interface 1010B via COM",
        "init": GAMRY_CV_INIT,
        "measure": GAMRY_CV_MEASURE,
        "parameters": {},
    },
    "CV_CHI": {
        "description": "Cyclic voltammetry on CH Instruments CHI760E/CHI660E via hardpotato",
        "init": CHI_CV_INIT,
        "measure": CHI_CV_MEASURE,
        "parameters": {
            "e_begin": "-0.5",
            "e_vertex1": "0.5",
            "e_vertex2": "-0.5",
            "e_final": "-0.5",
            "scan_rate_V_per_s": "0.1",
            "e_step": "0.001",
            "n_cycles": "3",
            "output_file": "cv_run_1",
            "title": "CV sweep",
        },
    },
    # ── Gas / Flow / Pressure ─────────────────────────────────────────
    "GAS_FLOW_ALICAT": {
        "description": "Set gas flow on Alicat MC-series mass flow controller",
        "init": ALICAT_INIT,
        "measure": ALICAT_SET_FLOW,
        "shutdown": ALICAT_SHUTDOWN,
        "parameters": {
            "setpoint_sccm": "100",
        },
    },
    # ── Balances ──────────────────────────────────────────────────────
    "WEIGH_METTLER": {
        "description": "Read stable mass from Mettler Toledo XS/XP balance via MT-SICS",
        "init": METTLER_INIT,
        "measure": METTLER_READ_WEIGHT,
        "parameters": {},
    },
    "WEIGH_OHAUS": {
        "description": "Read weight from Ohaus Adventurer balance over RS-232",
        "init": [],
        "measure": OHAUS_READ_WEIGHT,
        "parameters": {},
    },
    # ── pH / ISE ──────────────────────────────────────────────────────
    "PH_ORION": {
        "description": "Read pH/mV/temperature from Thermo Orion Star A221 meter",
        "init": [],
        "measure": ORION_READ,
        "parameters": {},
    },
    # ── Cryogenic temperature control ─────────────────────────────────
    "TEMP_OXFORD_ITC": {
        "description": "Set cryostat temperature on Oxford Mercury iTC",
        "init": OXFORD_ITC_INIT,
        "measure": OXFORD_ITC_READ,
        "parameters": {
            "setpoint": "4.2",  # K
            "power": "50",  # % heater
        },
    },
    # ── NI DAQ ────────────────────────────────────────────────────────
    "DAQ_NI_AO": {
        "description": "Write analog voltage on NI USB-6351/6001/6009 DAQ",
        "init": [],
        "measure": NIDAQ_ANALOG_OUT,
        "parameters": {
            "device": "Dev1",
            "channel": "0",
            "voltage": "1.0",
        },
    },
    "DAQ_NI_AI": {
        "description": "Read analog voltage on NI USB-6351/6001/6009 DAQ",
        "init": [],
        "measure": NIDAQ_ANALOG_IN,
        "parameters": {
            "device": "Dev1",
            "channel": "0",
        },
    },
}


def get_procedure(name: str) -> dict | None:
    """Get a reference measurement procedure by name."""
    return PROCEDURES.get(name)


def list_procedures() -> list[str]:
    """List all available reference procedures."""
    return list(PROCEDURES.keys())

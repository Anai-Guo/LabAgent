# LabAgent - Catalog

## Measurement Templates

Templates define what to measure. Located in `src/lab_harness/planning/templates/`.

### Electrical Characterization
| Template | Description | Instruments |
|----------|-------------|-------------|
| `iv.yaml` | Current-Voltage curve | Source meter |
| `rt.yaml` | Resistance vs Temperature | Source meter + temp controller |
| `delta.yaml` | Ultra-low resistance (delta mode) | K6221 + K2182A |
| `high_r.yaml` | High resistance (>1 GΩ) | Electrometer |
| `transfer.yaml` | FET transfer curve | Source meter (2 channels) |
| `output.yaml` | FET output curve | Source meter (2 channels) |
| `breakdown.yaml` | Dielectric breakdown | Source meter |

### Magnetic Measurements
| Template | Description | Instruments |
|----------|-------------|-------------|
| `ahe.yaml` | Anomalous Hall Effect | Source meter + DMM + gaussmeter |
| `mr.yaml` | Magnetoresistance | Source meter + DMM + gaussmeter |
| `sot.yaml` | Spin-Orbit Torque loop shift | + pulse source |
| `hall.yaml` | Standard Hall effect | Source meter + DMM + gaussmeter |
| `fmr.yaml` | Ferromagnetic resonance | Lock-in + gaussmeter |
| `hysteresis.yaml` | Magnetic hysteresis (VSM/SQUID) | Magnetometer + gaussmeter |

### Thermoelectric
| Template | Description | Instruments |
|----------|-------------|-------------|
| `seebeck.yaml` | Seebeck coefficient | DMM + temp controller |
| `thermal_conductivity.yaml` | Thermal conductivity | Heater + temp controller |

### Superconductivity
| Template | Description | Instruments |
|----------|-------------|-------------|
| `tc.yaml` | Superconducting Tc | Source meter + temp controller |
| `jc.yaml` | Critical current density | Source meter + temp controller |

### Electrochemistry
| Template | Description | Instruments |
|----------|-------------|-------------|
| `cyclic_voltammetry.yaml` | Cyclic voltammetry | Potentiostat |
| `eis.yaml` | Electrochemical impedance | LCR meter |
| `chronoamperometry.yaml` | Chronoamperometry | Potentiostat |

### Dielectric & Ferroelectric
| Template | Description | Instruments |
|----------|-------------|-------------|
| `cv.yaml` | Capacitance-Voltage | LCR meter |
| `pe_loop.yaml` | P-E hysteresis loop | HV source + charge amp |
| `pyroelectric.yaml` | Pyroelectric current | Electrometer + temp controller |

### Semiconductor
| Template | Description | Instruments |
|----------|-------------|-------------|
| `photo_iv.yaml` | Solar cell IV | Source meter + lamp |
| `dlts.yaml` | Deep Level Transient Spectroscopy | LCR + temp controller |

### Sensors
| Template | Description | Instruments |
|----------|-------------|-------------|
| `gas_sensor.yaml` | Gas sensor response | DMM + gas controller |
| `humidity_response.yaml` | Humidity sensor | DMM + humidity chamber |

### Quantum Design PPMS/MPMS
| Template | Description | Instruments |
|----------|-------------|-------------|
| `ppms_rt.yaml` | PPMS R-T (four-probe) | PPMS (MultiPyVu) |
| `ppms_mr.yaml` | PPMS Magnetoresistance | PPMS (MultiPyVu) |
| `ppms_hall.yaml` | PPMS Hall Effect | PPMS (MultiPyVu) |
| `ppms_hc.yaml` | PPMS Heat Capacity | PPMS (MultiPyVu) |
| `mpms_mh.yaml` | MPMS M-H Loop (SQUID) | MPMS (MultiPyVu) |
| `mpms_mt.yaml` | MPMS M-T ZFC/FC | MPMS (MultiPyVu) |

### General Purpose
| Template | Description | Instruments |
|----------|-------------|-------------|
| `custom_sweep.yaml` | User-defined X-Y sweep | Any |

---

## Instrument Reference Procedures

Command sequences (SCPI, ASCII-line, or vendor-API) for common instruments. Located
in `src/lab_harness/reference/instrument_procedures.py`. Currently 33 procedures
spanning electrical, signals/RF, optics, electrochemistry, biology/analytical,
gas/flow, and cryogenic instruments.

### Electrical / source-measure / DMM
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `IV_K2400` | Keithley 2400 | Standard IV curve |
| `DELTA_K6221` | K6221 + K2182A | Ultra-low resistance |
| `HIGH_R_K6517B` | Keithley 6517B | High impedance materials |
| `NANOVOLT_K2182A` | Keithley 2182A | Low-noise voltage |
| `DMM_K2000` | Keithley 2000 | General voltage/resistance |
| `DMM_A34401` | Agilent 34401A / Keysight 34461A | General purpose DMM |

### Signals / RF / waveform
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `SCOPE_CAPTURE_TEK` | Tektronix TDS/DPO/MSO | Waveform capture |
| `SCOPE_CAPTURE_KEYSIGHT` | Keysight DSOX/MSOX | Waveform capture |
| `FGEN_KEYSIGHT` | Keysight 33500B/33622A | Arbitrary waveform output |
| `PSU_KEYSIGHT_E36300` | Keysight E36313A | Programmable DC supply |
| `LOCKIN_SR830` | SRS SR830 | AC / small-signal detection |
| `LOCKIN_SR860` | SRS SR860/SR865A | AC / small-signal detection (SCPI) |
| `LOCKIN_ZURICH_MFLI` | Zurich Instruments MFLI | High-end lock-in via zhinst-toolkit |

### Optics / photonics / spectroscopy
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `OPTICAL_POWER_PM100D` | Thorlabs PM100D / PM400 | Optical power at wavelength |
| `UV_VIS_OCEAN_INSIGHT` | Ocean Insight USB2000/QEPro | UV-Vis absorbance spectrum |

### Electrochemistry
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `CV_E4980A` | Keysight E4980A | Capacitance characterization |
| `CV_BIOLOGIC` | BioLogic SP-200/VSP/VMP3 | Cyclic voltammetry via easy-biologic |
| `CV_GAMRY` | Gamry Reference 600+/Interface 1010B | CV via COM/ActiveX |
| `CV_CHI` | CH Instruments CHI760E/CHI660E | CV via hardpotato macro driver |

### Gas / flow / pressure
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `GAS_FLOW_ALICAT` | Alicat MC-series MFC | Gas flow setpoint |

### Analytical / biology
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `WEIGH_METTLER` | Mettler Toledo XS/XP | Stable mass readout (MT-SICS) |
| `WEIGH_OHAUS` | Ohaus Adventurer | Mass readout over RS-232 |
| `PH_ORION` | Thermo Orion Star A221 | pH / ISE / mV readout |

### Temperature / cryogenic
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `RT_LS350` | Lakeshore 350 | Temperature-dependent measurements |
| `TEMP_OXFORD_ITC` | Oxford Mercury iTC | Cryostat temperature control |

### DAQ
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `DAQ_NI_AO` | NI USB-6351/6001/6009 | Analog voltage output |
| `DAQ_NI_AI` | NI USB-6351/6001/6009 | Analog voltage input |

### Condensed-matter specialty (Quantum Design)
| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `PPMS_RT` | QD PPMS (MultiPyVu) | R-T measurement |
| `PPMS_MR` | QD PPMS (MultiPyVu) | Magnetoresistance |
| `PPMS_HALL` | QD PPMS (MultiPyVu) | Hall effect |
| `PPMS_HC` | QD PPMS (MultiPyVu) | Heat capacity |
| `MPMS_MH` | QD MPMS (MultiPyVu) | M-H loop (SQUID) |
| `MPMS_MT` | QD MPMS (MultiPyVu) | M-T ZFC/FC |

**Can't find your instrument?** Call the `manual_lookup` MCP tool (or
`labharness`'s AI chat) with the make and model — it will return the
manufacturer's programming manual URL plus any open-source Python driver it
knows about, before writing new command sequences.

---

## How to Contribute

### Add a New Measurement Template
1. Create a YAML file in `src/lab_harness/planning/templates/`
2. Follow the format of existing templates (see `iv.yaml` for reference)
3. Add the measurement type to `MeasurementType` enum in `src/lab_harness/models/measurement.py`
4. Add required roles to `MEASUREMENT_ROLES` in `src/lab_harness/discovery/classifier.py`
5. Submit a pull request

### Add an Instrument Driver Reference
1. Add SCPI sequences to `src/lab_harness/reference/instrument_procedures.py`
2. Include init, measure, and shutdown sequences
3. Document default parameters
4. Submit a pull request

### Add an Analysis Template
1. Create a Python script in `src/lab_harness/analysis/templates/`
2. Use `{{DATA_PATH}}` and `{{OUTPUT_DIR}}` placeholders
3. Save figures as PNG (300 dpi) and PDF
4. Submit a pull request

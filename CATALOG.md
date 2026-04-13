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

SCPI command sequences for common instruments. Located in `src/lab_harness/reference/instrument_procedures.py`.

| Procedure | Instruments | Use Case |
|-----------|------------|----------|
| `IV_K2400` | Keithley 2400 | Standard IV curve |
| `DELTA_K6221` | K6221 + K2182A | Ultra-low resistance |
| `RT_LS350` | Lakeshore 350 | Temperature-dependent measurements |
| `CV_E4980A` | Keysight E4980A | Capacitance characterization |
| `HIGH_R_K6517B` | Keithley 6517B | High impedance materials |
| `NANOVOLT_K2182A` | Keithley 2182A | Low-noise voltage |
| `DMM_K2000` | Keithley 2000 | General voltage/resistance |
| `LOCKIN_SR830` | SR830 | AC measurements, FMR |
| `DMM_A34401` | Agilent 34401A | General purpose DMM |
| `PPMS_RT` | QD PPMS (MultiPyVu) | R-T measurement |
| `PPMS_MR` | QD PPMS (MultiPyVu) | Magnetoresistance |
| `PPMS_HALL` | QD PPMS (MultiPyVu) | Hall effect |
| `PPMS_HC` | QD PPMS (MultiPyVu) | Heat capacity |
| `MPMS_MH` | QD MPMS (MultiPyVu) | M-H loop (SQUID) |
| `MPMS_MT` | QD MPMS (MultiPyVu) | M-T ZFC/FC |

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

# Instrument Discovery

LabAgent automatically discovers laboratory instruments connected via GPIB, USB, serial, and TCP/IP buses. The discovery pipeline scans all available communication interfaces, queries each instrument for its identity, and classifies instruments into measurement roles using a two-stage approach: deterministic dictionary lookup followed by an optional LLM fallback.

## How Scanning Works

### PyVISA Bus Scanning

The primary scanner uses PyVISA to enumerate all VISA resources on the system. For each discovered resource, it sends a standard IEEE 488.2 `*IDN?` query and parses the four-field response (vendor, model, serial number, firmware version).

```bash
labharness scan
```

Supported bus types detected from the resource string:

| Bus Type | Resource Pattern | Example |
|----------|-----------------|---------|
| GPIB | `GPIB0::N::INSTR` | `GPIB0::5::INSTR` |
| USB | `USB0::...::INSTR` | `USB0::0x05E6::0x2400::INSTR` |
| Serial (VISA) | `ASRL` or `COM` | `ASRL1::INSTR` |
| Ethernet | `TCPIP::...` | `TCPIP0::192.168.1.10::INSTR` |

The scanner is configurable with a timeout (default 2000 ms per instrument) and can optionally skip the `*IDN?` query if you only need resource enumeration.

### Serial Port Scanning

For instruments that do not appear on the VISA bus (standalone serial devices, Arduino-based controllers, custom hardware), a separate serial scanner enumerates all available COM ports using pyserial. Serial scanning is non-invasive: it lists ports and their metadata (manufacturer, description, serial number) without sending any commands, since probing serial devices can interfere with running equipment.

```bash
# Serial ports are included automatically in the scan
labharness scan
```

### Scan Output

Each discovered instrument is represented as an `InstrumentRecord` containing:

- **resource** -- VISA resource string or COM port path
- **vendor** -- manufacturer name (e.g., KEITHLEY, Lakeshore)
- **model** -- model number (e.g., MODEL 2400, 335)
- **serial** -- instrument serial number
- **firmware** -- firmware version
- **bus** -- communication bus type (gpib, usb, serial, ethernet)

You can save the full inventory to a JSON file for reuse:

```bash
labharness scan -o inventory.json
```

## AI Instrument Classifier

After scanning, the classifier maps instruments to measurement roles. This is a two-stage process.

### Stage 1: Dictionary Lookup

A built-in database of ~68 known instruments across 26 vendors provides instant,
deterministic classification. Selected highlights (see
`src/lab_harness/discovery/classifier.py` for the full list):

| Models | Vendor | Assigned Roles |
|--------|--------|----------------|
| 2400, 2410, 2420, 2440 | Keithley | source_meter |
| 2000, 2001, 2002 | Keithley | dmm |
| 2182, 2182A | Keithley | nanovoltmeter |
| 6221 | Keithley | ac_current_source |
| 6517, 6517A, 6517B | Keithley | electrometer |
| 425, 455, 475 | Lakeshore | gaussmeter |
| 335, 336, 340, 350 | Lakeshore | temperature_controller |
| Mercury iTC | Oxford Instruments | temp_controller_cryo |
| E4980A, DSOX1204G, MSOX3054T, 33500B/33622A, E36313A, N9320B, E5071C | Keysight | lcr_meter / oscilloscope / function_generator / power_supply_dc / spectrum_analyzer / vna |
| TDS3054C, MSO44, AFG1062/AFG3102 | Tektronix | oscilloscope / function_generator |
| DS1054Z, MSO5354, DG1032Z, DP832A | Rigol | oscilloscope / function_generator / power_supply_dc |
| FSV, ZNA | Rohde & Schwarz | spectrum_analyzer / vna |
| SR830, SR860, SR865A | SRS | lockin_amplifier |
| MFLI, HF2LI | Zurich Instruments | lockin_amplifier |
| PM100D, LDC205C, MDT693B | Thorlabs | optical_power_meter / laser_diode_driver / piezo_controller |
| 1830-C | Newport | optical_power_meter |
| USB2000, QEPro, CCS100 | Ocean Insight / Thorlabs | spectrometer_compact |
| SP-200, VSP, VMP3 | BioLogic | potentiostat |
| Reference 600+, Interface 1010B | Gamry | potentiostat |
| CHI760E, CHI660E | CH Instruments | potentiostat |
| PGSTAT302N | Metrohm Autolab | potentiostat |
| PalmSens4 | Palmsens | potentiostat |
| CLARIOstar, SpectraMax M5 | BMG / Molecular Devices | plate_reader |
| XS205, Adventurer | Mettler Toledo / Ohaus | balance |
| Orion A221 | Thermo Fisher | ph_meter |
| MC-series | Alicat | mass_flow_controller |
| PR4000 | MKS | pressure_gauge |
| USB-6351, USB-6001, USB-6009 | National Instruments | daq |
| PPMS, MPMS3 | Quantum Design | ppms / mpms |

### Stage 2: LLM Fallback

When the dictionary lookup cannot assign all required roles for a measurement type, the classifier invokes an LLM. The LLM receives the list of unmatched instruments (with their `*IDN?` responses) and the list of still-needed roles. It returns structured JSON with role assignments, confidence scores, and reasoning.

Safety guardrails ensure the LLM can only assign roles that are genuinely unassigned -- it cannot override dictionary-based assignments or assign duplicate roles.

```bash
# Classify instruments for an AHE measurement
labharness classify AHE

# Use a saved inventory file
labharness classify AHE --inventory inventory.json
```

### Measurement Role Requirements

Each measurement type defines its required instrument roles. Example configurations:

| Measurement | Required Roles |
|-------------|---------------|
| IV | source_meter |
| AHE | source_meter, dmm, gaussmeter |
| MR | source_meter, dmm, gaussmeter |
| RT | source_meter, temperature_controller |
| SOT | source_meter, ac_current_source, dmm, gaussmeter |
| CV | lcr_meter, temperature_controller |
| Hall | source_meter, dmm, magnet |
| PPMS_RT | ppms |

The full classifier supports 40+ measurement types across electrical, magnetic, thermoelectric, optical, superconducting, electrochemical, and biosensor disciplines.

## Extending the Instrument Database

To add support for new instruments, update the `KNOWN_INSTRUMENTS` dictionary in `src/lab_harness/discovery/classifier.py` with the model string, vendor, assignable roles, and capabilities. Instruments not in the database will be handled by the LLM fallback if an API key is configured.

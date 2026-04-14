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

A built-in database of known instruments provides instant, deterministic classification. The database covers common lab equipment from Keithley, Lakeshore, and Keysight:

| Model | Vendor | Assigned Roles | Capabilities |
|-------|--------|----------------|--------------|
| 2400, 2410 | Keithley | source_meter | source/measure IV |
| 2000 | Keithley | dmm | measure V, R |
| 2182, 2182A | Keithley | nanovoltmeter | low-noise V measurement |
| 6221 | Keithley | ac_current_source | pulse/AC current source |
| 6517, 6517B | Keithley | electrometer | high-R measurement |
| 425, 455 | Lakeshore | gaussmeter | magnetic field measurement |
| 335, 340, 350 | Lakeshore | temperature_controller | temperature control |
| E4980 | Keysight | lcr_meter | capacitance/impedance |

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

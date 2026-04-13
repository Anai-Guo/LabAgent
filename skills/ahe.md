---
name: AHE Measurement
description: Anomalous Hall Effect measurement protocol 
measurement_type: AHE
instruments: [source_meter, dmm, gaussmeter]
version: "1.0"
---

## Protocol

1. **Connect** instruments and verify identity via *IDN?
2. **Configure** source meter: DC current mode, set compliance voltage
3. **Set** source current to {current} A (typical: 100 uA for thin films)
4. **Sweep** magnetic field from {field_start} to {field_stop} Oe in {step} Oe steps
5. At each field point:
   - Wait {settling_time} s for field stabilization
   - Read transverse voltage V_xy (Hall voltage)
   - Read longitudinal voltage V_xx (optional, for MR)
   - Record field readback from gaussmeter
6. **Reverse** sweep direction and repeat
7. **Zero** magnetic field
8. **Disable** source meter output
9. **Save** data to {output_dir} as CSV

## Expected Output

- R_xy vs H hysteresis loop
- Coercive field H_c from zero-crossings
- Anomalous Hall resistance R_AHE = (R_xy_max - R_xy_min) / 2

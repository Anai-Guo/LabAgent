"""IV Measurement Demo — End-to-end workflow with simulated data.

Demonstrates: scan → classify → propose → validate → execute (simulated) → export → analyze

Run: python examples/iv_demo.py
"""
import json
import math
import random
from pathlib import Path

def main():
    print("=" * 60)
    print("  LabAgent — IV Measurement Demo (Simulated)")
    print("=" * 60)

    # Step 1: Simulate instrument scan
    print("\n[Step 1] Scanning instruments...")
    instruments = [
        {"resource": "GPIB0::5::INSTR", "vendor": "KEITHLEY", "model": "MODEL 2400"},
        {"resource": "GPIB0::2::INSTR", "vendor": "KEITHLEY", "model": "MODEL 2000"},
    ]
    for inst in instruments:
        print(f"  Found: {inst['vendor']} {inst['model']} at {inst['resource']}")

    # Step 2: Classify instruments
    print("\n[Step 2] Classifying for IV measurement...")
    roles = {"source_meter": instruments[0], "dmm": instruments[1]}
    for role, inst in roles.items():
        print(f"  {role:20s} → {inst['model']} ({inst['resource']})")

    # Step 3: Load measurement template
    print("\n[Step 3] Loading IV measurement template...")
    from lab_harness.planning.plan_builder import build_plan_from_template
    plan = build_plan_from_template("IV")
    print(f"  Sweep: {plan.x_axis.label} from {plan.x_axis.start} to {plan.x_axis.stop} {plan.x_axis.unit}")
    print(f"  Step: {plan.x_axis.step} {plan.x_axis.unit}")
    print(f"  Total points: {plan.total_points}")

    # Step 4: Validate safety
    print("\n[Step 4] Safety validation...")
    from lab_harness.planning.boundary_checker import check_boundaries
    validation = check_boundaries(plan)
    print(f"  Decision: {validation.decision.value.upper()}")
    if validation.warnings:
        for w in validation.warnings:
            print(f"  Warning: {w}")
    else:
        print("  All parameters within safe limits ✓")

    # Step 5: Execute measurement (simulated)
    print("\n[Step 5] Executing measurement (simulated)...")
    data = []
    for i in range(plan.total_points):
        current_ma = plan.x_axis.start + i * plan.x_axis.step
        current_a = current_ma / 1000
        # Simulate a diode-like IV curve with noise
        if current_a >= 0:
            voltage = 0.7 * (1 - math.exp(-current_a / 0.0001)) + random.gauss(0, 0.001)
        else:
            voltage = -0.01 * current_a + random.gauss(0, 0.0005)
        resistance = voltage / current_a if abs(current_a) > 1e-9 else float('inf')

        data.append({
            "current_mA": round(current_ma, 4),
            "voltage_V": round(voltage, 6),
            "resistance_Ohm": round(resistance, 2) if resistance != float('inf') else "inf",
        })

        if i % 50 == 0 or i == plan.total_points - 1:
            print(f"  Point {i+1}/{plan.total_points}: I={current_ma:.3f} mA, V={voltage:.4f} V")

    # Step 6: Export data
    print("\n[Step 6] Exporting data...")
    output_dir = Path("examples/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    from lab_harness.export.exporter import DataExporter, ExportConfig
    exporter = DataExporter(ExportConfig(output_dir=output_dir, timestamp_prefix=False))

    csv_path = exporter.export_csv(data, name="iv_demo", metadata={
        "measurement": "IV curve",
        "sample": "Simulated diode",
        "source_meter": "Keithley 2400 (GPIB0::5)",
    })
    print(f"  CSV saved: {csv_path}")

    json_path = exporter.export_json(data, name="iv_demo", metadata={
        "measurement": "IV curve",
    })
    print(f"  JSON saved: {json_path}")

    # Step 7: Summary
    print("\n[Step 7] Summary")
    print(f"  Points measured: {len(data)}")
    print(f"  Current range: {data[0]['current_mA']} to {data[-1]['current_mA']} mA")
    v_max = max(d['voltage_V'] for d in data)
    v_min = min(d['voltage_V'] for d in data)
    print(f"  Voltage range: {v_min:.4f} to {v_max:.4f} V")
    print(f"  Output directory: {output_dir}")

    print("\n" + "=" * 60)
    print("  Demo complete! LabAgent can guide your real measurements.")
    print("  Try: labharness scan  |  labharness propose IV")
    print("=" * 60)

if __name__ == "__main__":
    main()

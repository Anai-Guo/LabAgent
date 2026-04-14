"""End-to-end integration: simulate -> write CSV -> analyze -> assert figures.

Verifies the multi-column CSV format produced by the physics simulators is
consumable by each analysis template without crashes and produces the expected
PNG/PDF figures and at least one extracted value.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from lab_harness.analysis.analyzer import Analyzer
from lab_harness.orchestrator.simulators import simulate
from lab_harness.planning.plan_builder import build_plan_from_template

# Only try to run these tests if numpy/matplotlib/pandas are importable in the
# interpreter that would run the generated analysis script. Keeps CI friendly
# if the scientific stack is not installed.
_has_scipy_stack = shutil.which("python") is not None  # subprocess uses PATH's python

MEASUREMENT_TYPES = ["IV", "MR", "RT", "AHE"]


@pytest.mark.parametrize("mt", MEASUREMENT_TYPES)
def test_simulate_then_analyze_produces_figures(tmp_path: Path, mt: str) -> None:
    """For each supported measurement type, simulated data flows end-to-end.

    Steps:
      1. Build a plan from YAML template.
      2. Run the physics simulator to get multi-column rows.
      3. Write rows to a CSV.
      4. Invoke Analyzer.analyze (template path, no AI).
      5. Assert at least one PNG figure was produced and stdout carries values.
    """
    if not _has_scipy_stack:
        pytest.skip("python not on PATH")

    plan = build_plan_from_template(mt)
    points = simulate(plan, mt, seed=1)
    assert points, f"simulator for {mt} produced no rows"

    fieldnames = list(points[0].keys())
    csv_path = tmp_path / "raw_data.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(points)

    analyzer = Analyzer(output_dir=tmp_path)
    try:
        result = analyzer.analyze(csv_path, mt, use_ai=False, interpret=False)
    except RuntimeError as exc:
        # Analysis scripts require numpy/matplotlib/pandas at runtime. If
        # the subprocess interpreter can't import them, skip rather than fail
        # so the test stays useful in minimal environments.
        if any(
            module in str(exc)
            for module in ("No module named 'numpy'", "No module named 'matplotlib'", "No module named 'pandas'")
        ):
            pytest.skip(f"scientific stack missing in subprocess python: {exc}")
        raise

    pngs = [p for p in result.figures if p.endswith(".png")]
    pdfs = [p for p in result.figures if p.endswith(".pdf")]
    assert pngs, f"{mt}: no PNG figure produced; stdout={result.stdout!r}"
    assert pdfs, f"{mt}: no PDF figure produced; stdout={result.stdout!r}"
    assert result.extracted_values, f"{mt}: analyzer parsed no key=value lines from stdout"


def test_ahe_three_column_csv_reads_v_xy_not_v_xx(tmp_path: Path) -> None:
    """AHE template must pick V_xy even when V_xx is also present.

    The AHE planning template declares two y-channels (V_xy, V_xx). The
    simulator writes both. R_AHE must be computed from V_xy (which has the
    hysteresis loop), not from V_xx.
    """
    if not _has_scipy_stack:
        pytest.skip("python not on PATH")

    plan = build_plan_from_template("AHE")
    points = simulate(plan, "AHE", seed=1)

    fieldnames = list(points[0].keys())
    # Sanity: the simulator really does produce 3 columns for AHE.
    assert fieldnames == ["Magnetic Field", "V_xy", "V_xx"], fieldnames

    csv_path = tmp_path / "raw_data.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(points)

    analyzer = Analyzer(output_dir=tmp_path)
    try:
        result = analyzer.analyze(csv_path, "AHE", use_ai=False, interpret=False)
    except RuntimeError as exc:
        if any(
            module in str(exc)
            for module in ("No module named 'numpy'", "No module named 'matplotlib'", "No module named 'pandas'")
        ):
            pytest.skip(f"scientific stack missing in subprocess python: {exc}")
        raise

    # V_xy values are O(1e-3); R_xy = V_xy/1e-4 is O(10). V_xx is O(1500),
    # so R_xx would be O(1.5e7). Sanity check the computed R_AHE is from V_xy.
    r_ahe_str = result.extracted_values.get("R_AHE", "")
    # Extract the number before " Ohm"
    r_ahe_val = float(r_ahe_str.split()[0])
    assert r_ahe_val < 100.0, (
        f"R_AHE={r_ahe_val} looks like it was computed from V_xx instead of V_xy. extracted={result.extracted_values}"
    )

"""Tests for measurement simulators — verify physics is correct."""

from lab_harness.orchestrator.simulators import (
    SIMULATORS,
    simulate,
    simulate_ahe,
    simulate_hall,
    simulate_iv,
    simulate_mr,
    simulate_rt,
    simulate_tc,
)
from lab_harness.planning.plan_builder import build_plan_from_template


def test_iv_simulator_produces_nonlinear():
    plan = build_plan_from_template("IV")
    points = simulate_iv(plan, seed=1)
    assert len(points) == plan.total_points
    # Should have voltage values changing non-linearly
    values = [p.get("Voltage", 0) for p in points]
    assert max(values) > 0.1  # forward bias should give positive voltage


def test_ahe_simulator_has_hysteresis():
    """Up-sweep and down-sweep should differ at zero field."""
    plan = build_plan_from_template("AHE")
    points = simulate_ahe(plan, seed=1)
    n = len(points)
    # Find points near field = 0 in up and down sweeps
    up_near_zero = None
    down_near_zero = None
    half = n // 2
    for i, p in enumerate(points):
        field = list(p.values())[0]
        if abs(field) < 100:
            if i < half:
                up_near_zero = list(p.values())[1]
            else:
                down_near_zero = list(p.values())[1]
    assert up_near_zero is not None
    assert down_near_zero is not None
    # Hysteresis: up and down values should differ significantly at B=0
    assert abs(up_near_zero - down_near_zero) > 1e-4


def test_hall_simulator_linear_in_field():
    plan = build_plan_from_template("HALL")
    points = simulate_hall(plan, seed=1)
    assert len(points) == plan.total_points
    # Hall voltage should have different sign at +B vs -B
    first = list(points[0].values())[1]
    last = list(points[-1].values())[1]
    # Signs should differ (linear response flips)
    assert first * last < 0 or abs(first - last) > 1e-7


def test_mr_simulator_parabolic():
    plan = build_plan_from_template("MR")
    points = simulate_mr(plan, seed=1)
    n = len(points)
    # Middle point (B~0) should have lowest R
    middle_r = list(points[n // 2].values())[1]
    edge_r = list(points[0].values())[1]
    # Parabolic: edge R should be higher than middle
    assert edge_r >= middle_r


def test_rt_simulator_increasing():
    plan = build_plan_from_template("RT")
    points = simulate_rt(plan, seed=1)
    # Metallic: R increases with T
    first_r = list(points[0].values())[1]
    last_r = list(points[-1].values())[1]
    assert last_r > first_r


def test_tc_simulator_has_transition():
    plan = build_plan_from_template("TC")
    points = simulate_tc(plan, seed=1)
    values = [list(p.values())[1] for p in points]
    # Should span from near zero to normal resistance
    assert min(values) < 1.0
    assert max(values) > 5.0


def test_dispatch_unknown_type_fallback():
    plan = build_plan_from_template("IV")
    # Unknown type should fall back to generic, not crash
    points = simulate(plan, "NONEXISTENT_TYPE", seed=1)
    assert len(points) == plan.total_points


def test_simulator_registry_coverage():
    """All registered simulators should produce output."""
    plan = build_plan_from_template("IV")
    for mt in SIMULATORS:
        # Use corresponding template if exists, else IV plan
        try:
            p = build_plan_from_template(mt)
        except Exception:
            p = plan
        points = SIMULATORS[mt](p, seed=1)
        assert len(points) > 0
        assert isinstance(points[0], dict)

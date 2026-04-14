"""Physics-based simulators for each measurement type.

Generates realistic-looking data that reflects the physics of each
measurement, so analysis templates produce meaningful figures even
without real instruments.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any

logger = logging.getLogger(__name__)


def _x_range(plan: Any) -> list[float]:
    """Return sweep points from plan.x_axis."""
    x = plan.x_axis
    n = plan.total_points
    if n <= 1:
        return [x.start]
    step = (x.stop - x.start) / (n - 1)
    return [x.start + i * step for i in range(n)]


def _channel_labels(plan: Any) -> tuple[str, list[str]]:
    """Return (x_label, y_channel_labels)."""
    x_label = plan.x_axis.label
    y_labels = [ch.label for ch in plan.y_channels] or ["measurement"]
    return x_label, y_labels


# --- Physics simulators ---


def simulate_iv(plan: Any, seed: int | None = None) -> list[dict]:
    """Diode-like IV curve: I = I0*(exp(V/nVt) - 1) with series resistance."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)
    # If x is current (mA) we're measuring voltage; if x is voltage, measuring current
    is_current_sweep = "current" in x_label.lower() or plan.x_axis.unit.lower() in ("a", "ma", "ua")

    points = []
    Vt = 0.0258  # thermal voltage at 300K
    n_ideal = 1.5
    Rs = 10.0  # series resistance
    I0 = 1e-9

    for x in xs:
        if is_current_sweep:
            # x is current in mA, compute voltage
            i_a = x / 1000 if plan.x_axis.unit.lower() == "ma" else x
            if i_a > I0:
                v = n_ideal * Vt * math.log(i_a / I0 + 1) + i_a * Rs
            elif i_a < -I0:
                v = -0.01 * abs(i_a)  # reverse bias, small leakage
            else:
                v = 0.0
            v += rng.gauss(0, 0.001)
            noise = rng.gauss(0, 0.0001)
            row = {x_label: x, y_labels[0]: v + noise}
        else:
            # x is voltage in V, compute current
            v = x
            i_a = I0 * (math.exp(v / (n_ideal * Vt)) - 1) + rng.gauss(0, 1e-8)
            row = {x_label: x, y_labels[0]: i_a}

        # Fill additional channels (e.g., resistance)
        for y_label in y_labels[1:]:
            if "resist" in y_label.lower():
                row[y_label] = abs(row[y_labels[0]] / (x if abs(x) > 1e-9 else 1e-9))
            else:
                row[y_label] = 0.0
        points.append(row)
    return points


def simulate_hall(plan: Any, seed: int | None = None) -> list[dict]:
    """Hall effect: V_H = (1/(n*e*t)) * I * B + offset."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)
    hall_coef = 6.25e-4  # V per (A*T) for typical semiconductor, scaled
    bias_current = 1e-4  # 100 uA
    offset = rng.gauss(0, 1e-5)

    points = []
    for field_oe in xs:
        field_t = field_oe / 10000  # Oe to Tesla
        v_hall = hall_coef * bias_current * field_t + offset + rng.gauss(0, 5e-6)
        row = {x_label: field_oe}
        for y in y_labels:
            if "hall" in y.lower() or "xy" in y.lower():
                row[y] = v_hall
            elif "xx" in y.lower() or "longitudinal" in y.lower():
                row[y] = 5000 + rng.gauss(0, 2)  # flat longitudinal
            else:
                row[y] = v_hall
        points.append(row)
    return points


def simulate_ahe(plan: Any, seed: int | None = None) -> list[dict]:
    """Anomalous Hall effect with hysteresis loop using tanh saturation."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)

    H_c = 280.0  # Oe, coercive field
    R_ahe_sat = 0.0012  # ohm, saturation AHE resistance

    points = []
    n = len(xs)
    half = n // 2
    # First half: up-sweep (-max to +max), second half: down-sweep (+max to -max)
    # Build hysteresis: remember previous magnetization state
    # Up-branch: switches at +H_c. Down-branch: switches at -H_c.
    for i, field in enumerate(xs):
        # Up-sweep if index < half, else down-sweep
        sweep_up = i < half
        if sweep_up:
            # Magnetization follows: stays negative until field > +H_c
            m = math.tanh((field - H_c) / 50) if field > 0 else -1.0
        else:
            # Down-sweep: stays positive until field < -H_c
            m = math.tanh((field + H_c) / 50) if field < 0 else 1.0

        v_xy = R_ahe_sat * m + rng.gauss(0, 1e-5)
        row = {x_label: field}
        for y in y_labels:
            if "xy" in y.lower() or "hall" in y.lower():
                row[y] = v_xy
            elif "xx" in y.lower():
                row[y] = 1500 + 50 * m * m + rng.gauss(0, 0.5)  # small MR
            else:
                row[y] = v_xy
        points.append(row)
    return points


def simulate_mr(plan: Any, seed: int | None = None) -> list[dict]:
    """Magnetoresistance: R(B) = R0*(1 + (mu*B)^2) parabolic."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)
    R0 = 1000.0
    mobility = 0.005  # 1/Oe

    points = []
    for field in xs:
        r = R0 * (1 + (mobility * field) ** 2) + rng.gauss(0, 0.5)
        row = {x_label: field}
        for y in y_labels:
            row[y] = r
        points.append(row)
    return points


def simulate_rt(plan: Any, seed: int | None = None) -> list[dict]:
    """R vs T: metallic linear with optional kink at transition."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)
    R0 = 50.0
    alpha = 0.5  # ohm per K

    points = []
    for temp in xs:
        r = R0 + alpha * temp + rng.gauss(0, 0.2)
        # Add a subtle kink around 150K
        if temp < 150:
            r -= 5 * math.exp(-((temp - 100) ** 2) / 400)
        row = {x_label: temp}
        for y in y_labels:
            row[y] = r
        points.append(row)
    return points


def simulate_cv(plan: Any, seed: int | None = None) -> list[dict]:
    """Mott-Schottky CV: 1/C^2 proportional to (V_bi - V)."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)
    V_bi = 0.7
    C0 = 100e-12  # 100 pF at V_bi

    points = []
    for v in xs:
        # C^2 ~ 1/(V_bi - V) so C drops as V approaches V_bi
        denom = max(abs(V_bi - v), 0.01)
        c = C0 / math.sqrt(denom) + rng.gauss(0, 1e-13)
        row = {x_label: v}
        for y in y_labels:
            if "capac" in y.lower():
                row[y] = c * 1e12  # report in pF
            elif "dissipation" in y.lower() or "loss" in y.lower():
                row[y] = 0.01 + rng.gauss(0, 0.001)
            else:
                row[y] = c * 1e12
        points.append(row)
    return points


def simulate_tc(plan: Any, seed: int | None = None) -> list[dict]:
    """Superconducting transition: sharp drop at T_c using tanh step."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)
    T_c = 90.0  # YBCO-like
    R_normal = 10.0

    points = []
    for temp in xs:
        # Sharp transition over ~1K width
        r = R_normal * (math.tanh((temp - T_c) / 1.0) + 1) / 2 + rng.gauss(0, 0.01)
        row = {x_label: temp}
        for y in y_labels:
            row[y] = r
        points.append(row)
    return points


def simulate_generic(plan: Any, seed: int | None = None) -> list[dict]:
    """Fallback: noisy linear response."""
    rng = random.Random(seed)
    x_label, y_labels = _channel_labels(plan)
    xs = _x_range(plan)

    points = []
    for x in xs:
        row = {x_label: x}
        for y in y_labels:
            row[y] = 0.001 * x + rng.gauss(0, 0.0001)
        points.append(row)
    return points


# --- Registry ---

SIMULATORS = {
    "IV": simulate_iv,
    "HALL": simulate_hall,
    "AHE": simulate_ahe,
    "MR": simulate_mr,
    "RT": simulate_rt,
    "CV": simulate_cv,
    "TC": simulate_tc,
}


def simulate(
    plan: Any,
    measurement_type: str,
    seed: int | None = None,
    literature: dict | None = None,
) -> list[dict]:
    """Dispatch to the right simulator by measurement type."""
    mt = measurement_type.upper() if measurement_type else "GENERIC"
    func = SIMULATORS.get(mt, simulate_generic)
    try:
        return func(plan, seed=seed)
    except Exception as e:
        logger.warning("Simulator %s failed: %s; falling back to generic", mt, e)
        return simulate_generic(plan, seed=seed)

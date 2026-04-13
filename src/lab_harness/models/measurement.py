"""Data models for measurement plans."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class MeasurementType(str, Enum):
    """Supported measurement types."""

    AHE = "AHE"  # Anomalous Hall Effect
    MR = "MR"  # Magnetoresistance
    IV = "IV"  # Current-Voltage characteristic
    RT = "RT"  # Resistance vs Temperature
    SOT = "SOT"  # Spin-Orbit Torque loop shift
    CV = "CV"  # Capacitance-Voltage
    CUSTOM = "CUSTOM"


class SweepAxis(BaseModel):
    """Definition of a sweep axis (X or Y)."""

    label: str  # e.g. "Magnetic Field", "Source Current"
    unit: str  # e.g. "Oe", "mA", "K"
    start: float
    stop: float
    step: float
    role: str = ""  # Instrument role responsible for this axis

    @property
    def num_points(self) -> int:
        if self.step == 0:
            return 1
        return int(abs(self.stop - self.start) / abs(self.step)) + 1


class DataChannel(BaseModel):
    """A data channel to record during measurement."""

    label: str  # e.g. "V_xy", "V_xx", "Temperature"
    unit: str  # e.g. "V", "Ohm", "K"
    role: str  # Instrument role that provides this reading


class MeasurementPlan(BaseModel):
    """A complete measurement plan."""

    measurement_type: MeasurementType
    name: str = ""
    description: str = ""

    # Sweep configuration
    x_axis: SweepAxis
    y_channels: list[DataChannel] = []

    # Optional secondary sweep (e.g., temperature loop around field sweep)
    outer_sweep: SweepAxis | None = None

    # Safety limits
    max_current_a: float = 0.01  # Default 10 mA
    max_voltage_v: float = 20.0  # Default 20 V
    max_field_oe: float = 10000.0  # Default 10 kOe
    max_temperature_k: float = 400.0  # Default 400 K

    # Execution parameters
    settling_time_s: float = 0.5
    num_averages: int = 1
    output_dir: str = "./data"
    output_format: str = "csv"

    @property
    def total_points(self) -> int:
        n = self.x_axis.num_points
        if self.outer_sweep:
            n *= self.outer_sweep.num_points
        return n * self.num_averages

"""PyMeasure adapter: reuse the upstream driver ecosystem.

pymeasure (https://github.com/pymeasure/pymeasure, MIT) ships vetted drivers
for ~100 instruments. Instead of re-writing each one, we map our
`InstrumentRecord` (vendor + model) to a pymeasure `Instrument` subclass and
wrap it in a thin adapter so the rest of LabAgent can use a single API.

Design rules
------------
1. **pymeasure is an optional dependency.** Import lazily inside `build()`.
   Tests and normal CLI commands must keep working without pymeasure
   installed.
2. **Unknown instruments fail loudly.** If the model is not in
   ``PYMEASURE_MODEL_MAP`` we raise ``UnsupportedInstrumentError`` so the
   caller can fall back to the simulator. We never guess an adapter class
   from vendor alone.
3. **The adapter exposes a small, role-oriented surface**
   (``set_source_current``, ``measure_voltage``, ``set_temperature``,
   ``read_temperature``, etc.) rather than leaking the pymeasure class
   directly — that way the executor can stay pymeasure-agnostic.

Extending
---------
To add a new model, append a row to ``PYMEASURE_MODEL_MAP`` with the
pymeasure dotted path. If that pymeasure class uses a different method
spelling than ours, add a small role-specific wrapper subclass below.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class UnsupportedInstrumentError(RuntimeError):
    """Raised when no pymeasure driver is available for this model."""


class PyMeasureUnavailableError(RuntimeError):
    """Raised when pymeasure is not importable (missing optional dep)."""


# Mapping: uppercase substring of model name -> (pymeasure dotted class, role hint)
#
# The key is matched with `.upper() in instrument.model.upper()` to be tolerant
# of suffixes like "MODEL 2400" or "2400B". More specific (longer) keys should
# come first.
PYMEASURE_MODEL_MAP: dict[str, tuple[str, str]] = {
    # Keithley source-measure / DMM / electrometer
    "2400": ("pymeasure.instruments.keithley.Keithley2400", "source_meter"),
    "2410": ("pymeasure.instruments.keithley.Keithley2400", "source_meter"),
    "2450": ("pymeasure.instruments.keithley.Keithley2450", "source_meter"),
    "2000": ("pymeasure.instruments.keithley.Keithley2000", "dmm"),
    "2182": ("pymeasure.instruments.keithley.Keithley2182", "nanovoltmeter"),
    "6221": ("pymeasure.instruments.keithley.Keithley6221", "ac_current_source"),
    "6517": ("pymeasure.instruments.keithley.Keithley6517B", "electrometer"),
    # Keysight / Agilent
    "34410": ("pymeasure.instruments.agilent.Agilent34410A", "dmm"),
    "34461": ("pymeasure.instruments.keysight.KeysightDSOX1102G", "dmm"),
    "33500": ("pymeasure.instruments.agilent.Agilent33500", "function_generator"),
    "33622": ("pymeasure.instruments.agilent.Agilent33500", "function_generator"),
    "E4980": ("pymeasure.instruments.agilent.AgilentE4980", "lcr_meter"),
    # Stanford Research Systems
    "SR830": ("pymeasure.instruments.srs.SR830", "lockin_amplifier"),
    "SR860": ("pymeasure.instruments.srs.SR860", "lockin_amplifier"),
    # Lake Shore — temperature
    "335": ("pymeasure.instruments.lakeshore.LakeShore421", "temperature_controller"),
    "425": ("pymeasure.instruments.lakeshore.LakeShore421", "gaussmeter"),
    # Rohde & Schwarz
    # (R&S drivers usually live in vendor's RsInstrument package, not pymeasure,
    # so they're intentionally omitted here.)
}


@dataclass
class PyMeasureDriver:
    """Thin, role-aware wrapper around a pymeasure ``Instrument`` instance.

    Exposes the small subset of operations LabAgent's executor needs. Methods
    that don't make sense for a given role raise ``NotImplementedError`` —
    callers should route commands to the right adapter.
    """

    resource: str
    model: str
    vendor: str
    role: str
    _pm_instrument: Any = field(default=None, repr=False)  # pymeasure.Instrument
    _connected: bool = False

    # ── lifecycle ───────────────────────────────────────────────────────

    def connect(self) -> None:
        """Instantiate the pymeasure driver (which opens the VISA resource)."""
        if self._connected:
            return
        # Lazy import so importing this module doesn't require pymeasure.
        try:
            importlib.import_module("pymeasure")
        except ImportError as exc:
            raise PyMeasureUnavailableError(
                "pymeasure is not installed. Run `pip install lab-agent[execution]`."
            ) from exc

        dotted = _resolve_pymeasure_class(self.model)
        cls = _import_class(dotted)
        # All pymeasure Instrument subclasses accept (adapter, ...) as first arg;
        # passing a VISA resource string works when the VISAAdapter is the
        # default (i.e. pyvisa is installed).
        self._pm_instrument = cls(self.resource)
        self._connected = True
        logger.info("PyMeasure driver %s connected at %s", cls.__name__, self.resource)

    def disconnect(self) -> None:
        if not self._connected:
            return
        adapter = getattr(self._pm_instrument, "adapter", None)
        if adapter is not None:
            close = getattr(adapter, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Error closing %s: %s", self.model, exc)
        self._pm_instrument = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def __enter__(self) -> PyMeasureDriver:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.disconnect()

    # ── source_meter operations (IV, RT) ────────────────────────────────

    def configure_source_current(self, compliance_v: float = 20.0) -> None:
        """Put a source-meter into current-source, voltage-measure mode."""
        self._require_role("source_meter")
        inst = self._pm_instrument
        # pymeasure Keithley2400: high-level setters
        if hasattr(inst, "apply_current"):
            inst.apply_current()
        if hasattr(inst, "compliance_voltage"):
            inst.compliance_voltage = compliance_v
        if hasattr(inst, "measure_voltage"):
            inst.measure_voltage()

    def set_current(self, amps: float) -> None:
        self._require_role("source_meter")
        inst = self._pm_instrument
        if hasattr(inst, "source_current"):
            inst.source_current = amps
        elif hasattr(inst, "current"):
            inst.current = amps
        else:
            raise NotImplementedError(f"{type(inst).__name__} has no current setter we know")

    def enable_output(self) -> None:
        self._require_role("source_meter")
        inst = self._pm_instrument
        if hasattr(inst, "enable_source"):
            inst.enable_source()
        elif hasattr(inst, "output_enabled"):
            inst.output_enabled = True

    def disable_output(self) -> None:
        if not self._connected:
            return
        inst = self._pm_instrument
        if hasattr(inst, "disable_source"):
            inst.disable_source()
        elif hasattr(inst, "output_enabled"):
            inst.output_enabled = False

    def measure_voltage(self) -> float:
        inst = self._pm_instrument
        if hasattr(inst, "voltage"):
            return float(inst.voltage)
        if hasattr(inst, "read"):
            return float(inst.read())
        raise NotImplementedError(f"{type(inst).__name__} has no voltage reader we know")

    # ── temperature_controller operations (RT) ──────────────────────────

    def read_temperature(self, channel: str = "A") -> float:
        self._require_role("temperature_controller", "gaussmeter")
        inst = self._pm_instrument
        # Lake Shore drivers expose channel properties directly
        if hasattr(inst, "input_A") and channel.upper() == "A":
            return float(inst.input_A.kelvin)
        if hasattr(inst, "input_B") and channel.upper() == "B":
            return float(inst.input_B.kelvin)
        if hasattr(inst, "temperature"):
            return float(inst.temperature)
        raise NotImplementedError(f"{type(inst).__name__} temperature readout unknown")

    def set_temperature(self, target_k: float, loop: int = 1) -> None:
        self._require_role("temperature_controller")
        inst = self._pm_instrument
        if hasattr(inst, "set_temperature_setpoint"):
            inst.set_temperature_setpoint(loop, target_k)
        elif hasattr(inst, "setpoint"):
            inst.setpoint = target_k

    # ── electrometer / source_meter voltage-source mode (HIGH_R) ────────

    def configure_source_voltage(self, compliance_i: float = 1e-6) -> None:
        """Put a source-meter/electrometer into voltage-source, current-measure mode."""
        self._require_role("source_meter", "electrometer")
        inst = self._pm_instrument
        if hasattr(inst, "apply_voltage"):
            inst.apply_voltage()
        if hasattr(inst, "compliance_current"):
            inst.compliance_current = compliance_i
        if hasattr(inst, "measure_current"):
            inst.measure_current()

    def set_voltage(self, volts: float) -> None:
        self._require_role("source_meter", "electrometer")
        inst = self._pm_instrument
        if hasattr(inst, "source_voltage"):
            inst.source_voltage = volts
        elif hasattr(inst, "voltage"):
            # Only assign if it's not a read-only property.
            try:
                inst.voltage = volts
            except AttributeError as exc:
                raise NotImplementedError(f"{type(inst).__name__} has no voltage setter we know") from exc
        else:
            raise NotImplementedError(f"{type(inst).__name__} has no voltage setter we know")

    def measure_current(self) -> float:
        """Read current. Used by electrometer (picoamp) and source_meter roles."""
        self._require_role("source_meter", "electrometer", "dmm")
        inst = self._pm_instrument
        if hasattr(inst, "current"):
            return float(inst.current)
        if hasattr(inst, "read"):
            return float(inst.read())
        raise NotImplementedError(f"{type(inst).__name__} has no current reader we know")

    # ── nanovoltmeter / DMM (DELTA, SEEBECK) ────────────────────────────

    def measure_voltage_nv(self) -> float:
        """Low-noise voltage readout for K2182A / nanovoltmeter-class DMMs."""
        self._require_role("nanovoltmeter", "dmm")
        inst = self._pm_instrument
        if hasattr(inst, "voltage"):
            return float(inst.voltage)
        if hasattr(inst, "read"):
            return float(inst.read())
        raise NotImplementedError(f"{type(inst).__name__} nanovolt readout unknown")

    # ── lcr_meter (CV, capacitance-frequency) ───────────────────────────

    def configure_lcr(self, ac_volts: float = 0.05, frequency_hz: float = 1e6) -> None:
        """Configure an LCR meter for capacitance measurement."""
        self._require_role("lcr_meter")
        inst = self._pm_instrument
        # pymeasure Agilent E4980 exposes these as properties
        if hasattr(inst, "mode"):
            inst.mode = "CPD"  # parallel capacitance + dissipation
        if hasattr(inst, "ac_voltage"):
            inst.ac_voltage = ac_volts
        if hasattr(inst, "frequency"):
            inst.frequency = frequency_hz

    def set_dc_bias(self, volts: float) -> None:
        self._require_role("lcr_meter")
        inst = self._pm_instrument
        if hasattr(inst, "bias_voltage"):
            inst.bias_voltage = volts
        elif hasattr(inst, "dc_bias"):
            inst.dc_bias = volts
        else:
            raise NotImplementedError(f"{type(inst).__name__} has no DC bias setter we know")

    def enable_bias(self) -> None:
        self._require_role("lcr_meter")
        inst = self._pm_instrument
        if hasattr(inst, "bias_enabled"):
            inst.bias_enabled = True

    def disable_bias(self) -> None:
        if not self._connected:
            return
        inst = self._pm_instrument
        if hasattr(inst, "bias_enabled"):
            inst.bias_enabled = False

    def measure_capacitance(self) -> float:
        """Return the primary parameter (C). Dissipation is dropped here."""
        self._require_role("lcr_meter")
        inst = self._pm_instrument
        if hasattr(inst, "impedance"):
            # AgilentE4980.impedance returns (primary, secondary)
            primary, _ = inst.impedance
            return float(primary)
        if hasattr(inst, "capacitance"):
            return float(inst.capacitance)
        raise NotImplementedError(f"{type(inst).__name__} capacitance readout unknown")

    # ── internals ───────────────────────────────────────────────────────

    def _require_role(self, *allowed: str) -> None:
        if self.role not in allowed:
            raise NotImplementedError(f"Operation not supported for role '{self.role}' (needs one of {list(allowed)})")


def _resolve_pymeasure_class(model: str) -> str:
    """Return the pymeasure dotted path for a model, or raise."""
    model_upper = (model or "").upper()
    for key in sorted(PYMEASURE_MODEL_MAP.keys(), key=len, reverse=True):
        if key.upper() in model_upper:
            return PYMEASURE_MODEL_MAP[key][0]
    raise UnsupportedInstrumentError(
        f"No pymeasure driver mapped for model '{model}'. "
        f"See PYMEASURE_MODEL_MAP in drivers/pymeasure_adapter.py to extend."
    )


def _role_hint(model: str) -> str | None:
    """Return the expected role for a model, or None."""
    model_upper = (model or "").upper()
    for key in sorted(PYMEASURE_MODEL_MAP.keys(), key=len, reverse=True):
        if key.upper() in model_upper:
            return PYMEASURE_MODEL_MAP[key][1]
    return None


def _import_class(dotted: str) -> type:
    module_path, class_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build(
    resource: str,
    model: str,
    vendor: str,
    role: str,
) -> PyMeasureDriver:
    """Factory: produce a PyMeasureDriver or raise UnsupportedInstrumentError.

    Does NOT call connect() — caller decides when to open the VISA resource.
    """
    # Probe the mapping up front so we fail fast if the model is unsupported.
    _resolve_pymeasure_class(model)
    return PyMeasureDriver(resource=resource, model=model, vendor=vendor, role=role)


def is_supported(model: str) -> bool:
    """Quick predicate: does pymeasure have a driver for this model?"""
    try:
        _resolve_pymeasure_class(model)
        return True
    except UnsupportedInstrumentError:
        return False


def list_supported_models() -> list[tuple[str, str, str]]:
    """Return `(model_key, pymeasure_class, role)` rows for every mapped model."""
    return [(k, v[0], v[1]) for k, v in PYMEASURE_MODEL_MAP.items()]

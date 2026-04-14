"""Zurich Instruments lock-in adapter (MFLI / HF2LI / SHFQA).

Uses the upstream `zhinst-toolkit` package (Apache-2.0). Like
``pymeasure_adapter``, the import is lazy so the absence of
``zhinst-toolkit`` at import time is not fatal — the dependency only
becomes mandatory when ``.connect()`` is called.

This adapter is intentionally narrow: it exposes the lock-in operations
the executor actually needs (frequency, time constant, R+θ readout) rather
than the full zhinst API surface. Extend when the executor grows FMR or
lockin-based IV support.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class ZurichUnavailableError(RuntimeError):
    """zhinst-toolkit not installed."""


class UnsupportedZurichModelError(RuntimeError):
    """Model isn't in the supported list for this adapter."""


# Supported devices: key is uppercase substring match against the model.
SUPPORTED_MODELS: dict[str, str] = {
    "MFLI": "Zurich Instruments MFLI lock-in amplifier",
    "HF2LI": "Zurich Instruments HF2LI lock-in amplifier",
    "SHFQA": "Zurich Instruments SHFQA signal analyzer",
}


def is_supported(model: str) -> bool:
    model_upper = (model or "").upper()
    return any(k in model_upper for k in SUPPORTED_MODELS)


@dataclass
class ZurichLockinDriver:
    """Thin wrapper over a ``zhinst.toolkit.Session`` for one device."""

    resource: str  # Data-server host, e.g. "localhost" or "192.168.1.10"
    model: str
    vendor: str = "zurich_instruments"
    role: str = "lockin_amplifier"
    device_serial: str = ""
    _session: Any = field(default=None, repr=False)
    _device: Any = field(default=None, repr=False)
    _connected: bool = False

    # ── lifecycle ───────────────────────────────────────────────────────

    def connect(self) -> None:
        if self._connected:
            return
        try:
            toolkit = importlib.import_module("zhinst.toolkit")
        except ImportError as exc:
            raise ZurichUnavailableError(
                "zhinst-toolkit is not installed. Install with `pip install zhinst-toolkit`."
            ) from exc
        if not is_supported(self.model):
            raise UnsupportedZurichModelError(
                f"Model '{self.model}' not in Zurich supported list: {list(SUPPORTED_MODELS)}"
            )

        Session = toolkit.Session  # type: ignore[attr-defined]
        self._session = Session(self.resource)
        serial = self.device_serial or self._infer_serial(self.model)
        self._device = self._session.connect_device(serial)
        self._connected = True
        logger.info("Zurich %s connected (serial=%s, host=%s)", self.model, serial, self.resource)

    def disconnect(self) -> None:
        # zhinst Session closes on garbage collection; drop references so
        # any __del__ / finalizer gets triggered promptly.
        self._device = None
        self._session = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def __enter__(self) -> ZurichLockinDriver:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.disconnect()

    # ── lockin_amplifier operations ─────────────────────────────────────

    def set_frequency(self, hz: float, oscillator: int = 0) -> None:
        self._require_connected()
        self._device.oscs[oscillator].freq(hz)

    def set_time_constant(self, seconds: float, demod: int = 0) -> None:
        self._require_connected()
        self._device.demods[demod].timeconstant(seconds)

    def set_drive_amplitude(self, vrms: float, output: int = 0) -> None:
        self._require_connected()
        # zhinst API varies slightly by model; ``sigouts`` exists on MFLI/HF2LI
        if hasattr(self._device, "sigouts"):
            self._device.sigouts[output].amplitudes[0](vrms)

    def read_xy(self, demod: int = 0) -> tuple[float, float]:
        self._require_connected()
        sample = self._device.demods[demod].sample()
        return float(sample["x"]), float(sample["y"])

    def read_r_theta(self, demod: int = 0) -> tuple[float, float]:
        import math

        x, y = self.read_xy(demod)
        r = math.hypot(x, y)
        theta = math.degrees(math.atan2(y, x))
        return r, theta

    # ── internals ───────────────────────────────────────────────────────

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Zurich driver not connected (call .connect() first)")

    @staticmethod
    def _infer_serial(model: str) -> str:
        """zhinst serials look like 'dev1234'. Fallback when the user hasn't
        set ``device_serial`` — the session will fail loudly if wrong."""
        return "dev0000"


def build(
    resource: str,
    model: str,
    vendor: str = "zurich_instruments",
    role: str = "lockin_amplifier",
    device_serial: str = "",
) -> ZurichLockinDriver:
    """Factory — probe the model map, return an unconnected driver."""
    if not is_supported(model):
        raise UnsupportedZurichModelError(f"Model '{model}' not supported. Known: {list(SUPPORTED_MODELS)}")
    return ZurichLockinDriver(
        resource=resource,
        model=model,
        vendor=vendor,
        role=role,
        device_serial=device_serial,
    )


def list_supported_models() -> list[tuple[str, str]]:
    return [(k, v) for k, v in SUPPORTED_MODELS.items()]

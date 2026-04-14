"""BioLogic potentiostat adapter (SP-200 / VSP / VMP3 via easy-biologic).

Wraps `easy-biologic` (https://github.com/bicarlsen/easy-biologic, MIT),
which itself wraps BioLogic's native EClib DLL. Provides the minimum
surface the LabAgent executor needs for cyclic voltammetry:

- `connect()` / `disconnect()` lifecycle
- `run_cv(...)` — execute a CV experiment and return `[(E, I), ...]`

The dependency is **optional** and **Windows-only** (EClib is a Windows
DLL). On import we never touch easy-biologic; the actual import happens
inside `connect()` so the module is safe to load in Linux CI.

Extending
---------
Adding EIS / chronoamperometry is a matter of wrapping the corresponding
``easy_biologic.programs.*`` classes — follow the shape of ``run_cv``.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class BioLogicUnavailableError(RuntimeError):
    """easy-biologic not installed or EClib DLL missing."""


class UnsupportedBioLogicModelError(RuntimeError):
    """Requested model isn't a BioLogic we support."""


# Known BioLogic models the adapter can drive. All go through the same
# easy-biologic entry point (`BiologicDevice`).
SUPPORTED_MODELS: dict[str, str] = {
    "SP-200": "BioLogic SP-200 potentiostat/galvanostat",
    "SP-300": "BioLogic SP-300 potentiostat/galvanostat",
    "VSP": "BioLogic VSP multi-channel",
    "VMP3": "BioLogic VMP3 multi-channel",
}


def is_supported(model: str) -> bool:
    model_upper = (model or "").upper()
    return any(k.upper() in model_upper for k in SUPPORTED_MODELS)


@dataclass
class BioLogicDriver:
    """Thin wrapper around `easy_biologic.BiologicDevice`."""

    resource: str  # IP address or USB descriptor
    model: str
    vendor: str = "biologic"
    role: str = "potentiostat"
    _device: Any = field(default=None, repr=False)
    _connected: bool = False

    # ── lifecycle ───────────────────────────────────────────────────────

    def connect(self) -> None:
        if self._connected:
            return
        try:
            ebl = importlib.import_module("easy_biologic")
        except ImportError as exc:
            raise BioLogicUnavailableError(
                "easy-biologic is not installed. Install with `pip install easy-biologic` (Windows only)."
            ) from exc
        if not is_supported(self.model):
            raise UnsupportedBioLogicModelError(
                f"Model '{self.model}' not in the BioLogic supported list: {list(SUPPORTED_MODELS)}"
            )
        BiologicDevice = ebl.BiologicDevice  # type: ignore[attr-defined]
        self._device = BiologicDevice(self.resource)
        self._device.connect()
        self._connected = True
        logger.info("BioLogic %s connected at %s", self.model, self.resource)

    def disconnect(self) -> None:
        if not self._connected:
            return
        disconn = getattr(self._device, "disconnect", None)
        if callable(disconn):
            try:
                disconn()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error disconnecting BioLogic: %s", exc)
        self._device = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def __enter__(self) -> BioLogicDriver:
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.disconnect()

    # ── potentiostat operations ─────────────────────────────────────────

    def run_cv(
        self,
        e_start: float,
        e_vertex: float,
        e_step: float = 0.001,
        scan_rate_mv_per_s: float = 100.0,
        n_cycles: int = 1,
        channels: tuple[int, ...] = (0,),
    ) -> list[tuple[float, float]]:
        """Run a triangular voltage sweep and return [(E, I), ...].

        The actual protocol is delegated to ``easy_biologic.programs.CV`` so
        all timing / safety interlocks enforced by BioLogic's own firmware
        are preserved.
        """
        self._require_connected()
        try:
            ebl = importlib.import_module("easy_biologic")
            programs = importlib.import_module("easy_biologic.programs")
        except ImportError as exc:
            raise BioLogicUnavailableError("easy-biologic missing") from exc

        _ = ebl  # module is required by the programs module
        cv_cls = programs.CV  # type: ignore[attr-defined]
        technique = cv_cls(
            self._device,
            params={
                "start": float(e_start),
                "end": float(e_vertex),
                "step": float(e_step),
                "rate": float(scan_rate_mv_per_s),
                "n_cycles": int(n_cycles),
            },
            channels=list(channels),
        )
        technique.run()
        data = technique.data[channels[0]]
        # easy-biologic returns per-record dicts; pull E & I in order.
        points: list[tuple[float, float]] = []
        for rec in data:
            e = rec.get("Ewe") if isinstance(rec, dict) else getattr(rec, "Ewe", None)
            i = rec.get("I") if isinstance(rec, dict) else getattr(rec, "I", None)
            if e is None or i is None:
                continue
            points.append((float(e), float(i)))
        return points

    # ── internals ───────────────────────────────────────────────────────

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("BioLogic driver not connected (call .connect() first)")


def build(
    resource: str,
    model: str,
    vendor: str = "biologic",
    role: str = "potentiostat",
) -> BioLogicDriver:
    """Factory — probe the model list, return an unconnected driver."""
    if not is_supported(model):
        raise UnsupportedBioLogicModelError(f"Model '{model}' not in BioLogic supported list: {list(SUPPORTED_MODELS)}")
    return BioLogicDriver(resource=resource, model=model, vendor=vendor, role=role)


def list_supported_models() -> list[tuple[str, str]]:
    return [(k, v) for k, v in SUPPORTED_MODELS.items()]

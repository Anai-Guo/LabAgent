"""Driver registry: discovers and instantiates instrument drivers from config.

Inspired by PyGMI's configuration-driven instrument initialization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lab_harness.drivers.base import InstrumentDriver

logger = logging.getLogger(__name__)

# Map driver names to classes (lazy imports)
DRIVER_MAP: dict[str, str] = {
    "keithley2400": "lab_harness.drivers.keithley2400:Keithley2400",
    "keithley6221": "lab_harness.drivers.keithley6221:Keithley6221",
    "lakeshore335": "lab_harness.drivers.lakeshore335:Lakeshore335",
}


def _import_driver(driver_spec: str) -> type[InstrumentDriver]:
    """Import a driver class from a 'module:ClassName' spec."""
    module_path, class_name = driver_spec.rsplit(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@dataclass
class DriverRegistry:
    """Registry of configured instrument drivers.

    Loads instrument configurations from YAML and provides
    lazy instantiation of driver objects.
    """

    configs: dict[str, dict] = field(default_factory=dict)
    _instances: dict[str, Any] = field(default_factory=dict, init=False)

    @classmethod
    def from_yaml(cls, path: Path) -> DriverRegistry:
        """Load instrument config from YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        instruments = raw.get("instruments", {})
        return cls(configs=instruments)

    def get_driver(self, role: str) -> Any:
        """Get or create a driver instance for the given role.

        Returns either an ``InstrumentDriver`` (built-in VisaDriver subclass)
        or a ``PyMeasureDriver`` adapter — both duck-type the same
        lifecycle API (``connect``/``disconnect``/``connected``/context-manager).

        Drivers come from one of two backends:
          * ``__pymeasure__`` (sentinel) — use ``pymeasure_adapter.build``
          * any key in ``DRIVER_MAP`` — our built-in VisaDriver subclasses
        """
        if role in self._instances:
            return self._instances[role]

        if role not in self.configs:
            raise KeyError(f"No instrument configured for role '{role}'")

        config = self.configs[role]
        driver_name = config["driver"]
        resource = config["resource"]
        settings = config.get("settings", {})

        if driver_name == "__pymeasure__":
            from lab_harness.drivers import pymeasure_adapter as pm

            instance = pm.build(
                resource=resource,
                model=settings.get("model", ""),
                vendor=settings.get("vendor", ""),
                role=settings.get("role", role),
            )
        elif driver_name in DRIVER_MAP:
            driver_cls = _import_driver(DRIVER_MAP[driver_name])
            instance = driver_cls(resource=resource, **settings)
        else:
            raise ValueError(
                f"Unknown driver '{driver_name}'. Available: {list(DRIVER_MAP.keys()) + ['__pymeasure__']}"
            )

        self._instances[role] = instance
        logger.info("Created %s driver for role '%s' at %s", driver_name, role, resource)
        return instance

    def connect_all(self) -> dict[str, Any]:
        """Connect all configured instruments."""
        connected = {}
        for role in self.configs:
            try:
                driver = self.get_driver(role)
                driver.connect()
                connected[role] = driver
            except Exception as e:
                logger.error("Failed to connect %s: %s", role, e)
        return connected

    def disconnect_all(self) -> None:
        """Safely disconnect all instruments."""
        for role, driver in self._instances.items():
            try:
                driver.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting %s: %s", role, e)
        self._instances.clear()

    def list_roles(self) -> list[str]:
        """List all configured instrument roles."""
        return list(self.configs.keys())

    # ------------------------------------------------------------------
    # Auto-build from classification output
    # ------------------------------------------------------------------

    @classmethod
    def from_role_assignments(
        cls,
        role_assignments: dict[str, Any],
        prefer_pymeasure: bool = True,
    ) -> tuple[DriverRegistry, dict[str, str]]:
        """Build a registry directly from classifier output.

        For each (role -> InstrumentRecord) pair, pick the most capable
        available driver:

        1. PyMeasure adapter (if ``prefer_pymeasure`` and the model is in
           ``PYMEASURE_MODEL_MAP``).
        2. Our built-in driver in ``DRIVER_MAP`` (by model substring lookup).
        3. Otherwise: skip — caller can fall back to the simulator for
           this role.

        Args:
            role_assignments: ``{role: InstrumentRecord-like}``. Each value
                must expose ``resource``, ``model``, and ``vendor``
                attributes (pydantic model or plain object).
            prefer_pymeasure: When True, pymeasure wins over our built-in
                driver for models that are in both maps. Set False to test
                only the in-tree drivers.

        Returns:
            ``(registry, coverage)`` where ``coverage`` is
            ``{role: backend_name}`` describing which driver was picked
            (``"pymeasure"``, ``"builtin:<name>"``, or ``"none"``).
        """
        from lab_harness.drivers import pymeasure_adapter as pm

        configs: dict[str, dict] = {}
        coverage: dict[str, str] = {}

        for role, inst in role_assignments.items():
            resource = _attr(inst, "resource")
            model = _attr(inst, "model", default="")
            vendor = _attr(inst, "vendor", default="")

            # 1. pymeasure
            if prefer_pymeasure and pm.is_supported(model):
                configs[role] = {
                    "driver": "__pymeasure__",
                    "resource": resource,
                    "settings": {"model": model, "vendor": vendor, "role": role},
                }
                coverage[role] = "pymeasure"
                continue

            # 2. Built-in driver (substring match on model against DRIVER_MAP
            #    keys is not useful because DRIVER_MAP keys are vendor-model
            #    slugs like "keithley2400". We probe by a small vendor+model
            #    table.)
            builtin = _pick_builtin(vendor, model)
            if builtin is not None:
                configs[role] = {
                    "driver": builtin,
                    "resource": resource,
                    "settings": {},
                }
                coverage[role] = f"builtin:{builtin}"
                continue

            coverage[role] = "none"
            logger.info(
                "No driver available for role '%s' (%s %s); caller should fall back",
                role,
                vendor,
                model,
            )

        return cls(configs=configs), coverage

    def supports_role(self, role: str) -> bool:
        return role in self.configs


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Grab an attribute from either a pydantic model or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# Vendor+model substring -> DRIVER_MAP key. Intentionally narrow; only lists
# the three hand-written drivers we actually ship. If a model isn't here, the
# registry falls through to pymeasure or to the simulator.
_BUILTIN_LOOKUP: list[tuple[str, str, str]] = [
    # (vendor substring, model substring, DRIVER_MAP key)
    ("keithley", "2400", "keithley2400"),
    ("keithley", "2410", "keithley2400"),
    ("keithley", "6221", "keithley6221"),
    ("lakeshore", "335", "lakeshore335"),
    ("lakeshore", "336", "lakeshore335"),
]


def _pick_builtin(vendor: str, model: str) -> str | None:
    v = (vendor or "").lower()
    m = (model or "").upper()
    for vendor_sub, model_sub, key in _BUILTIN_LOOKUP:
        if vendor_sub in v and model_sub.upper() in m:
            return key
    return None

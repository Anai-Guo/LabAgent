"""VISA instrument bus scanner.

Wraps PyVISA to discover instruments on GPIB, USB, and serial buses.
"""

from __future__ import annotations

import logging

from lab_harness.models.instrument import InstrumentBus, InstrumentRecord

logger = logging.getLogger(__name__)


def _detect_bus(resource: str) -> InstrumentBus:
    """Detect the bus type from a VISA resource string."""
    r = resource.upper()
    if "GPIB" in r:
        return InstrumentBus.GPIB
    if "USB" in r:
        return InstrumentBus.USB
    if "ASRL" in r or "COM" in r:
        return InstrumentBus.SERIAL
    if "TCPIP" in r:
        return InstrumentBus.ETHERNET
    return InstrumentBus.UNKNOWN


def _parse_idn(idn: str) -> dict[str, str]:
    """Parse a standard IEEE 488.2 *IDN? response.

    Format: <vendor>,<model>,<serial>,<firmware>
    """
    parts = [p.strip() for p in idn.split(",")]
    return {
        "vendor": parts[0] if len(parts) > 0 else "",
        "model": parts[1] if len(parts) > 1 else "",
        "serial": parts[2] if len(parts) > 2 else "",
        "firmware": parts[3] if len(parts) > 3 else "",
    }


def scan_visa_instruments(
    timeout_ms: int = 2000,
    query_idn: bool = True,
) -> list[InstrumentRecord]:
    """Scan the VISA bus and identify all connected instruments.

    Args:
        timeout_ms: Timeout for each instrument query in milliseconds.
        query_idn: Whether to send *IDN? to each resource.

    Returns:
        List of discovered instruments with identity info.
    """
    try:
        import pyvisa
    except ImportError:
        logger.error("PyVISA not installed. Run: pip install pyvisa")
        return []

    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    logger.info("Found %d VISA resource(s)", len(resources))

    instruments: list[InstrumentRecord] = []

    for resource in resources:
        bus = _detect_bus(resource)
        record = InstrumentRecord(resource=resource, bus=bus)

        if query_idn:
            try:
                inst = rm.open_resource(resource, timeout=timeout_ms)
                idn = inst.query("*IDN?").strip()
                inst.close()

                parsed = _parse_idn(idn)
                record = InstrumentRecord(
                    resource=resource,
                    bus=bus,
                    raw_idn=idn,
                    **parsed,
                )
                logger.info("  %s -> %s %s", resource, parsed["vendor"], parsed["model"])
            except Exception as e:
                logger.warning("  %s -> query failed: %s", resource, e)

        instruments.append(record)

    return instruments

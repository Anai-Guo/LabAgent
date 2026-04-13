"""Serial port scanner for instruments not on VISA bus."""

from __future__ import annotations

import logging

from lab_harness.models.instrument import InstrumentBus, InstrumentRecord

logger = logging.getLogger(__name__)


def scan_serial_ports() -> list[InstrumentRecord]:
    """Scan serial/COM ports for connected instruments.

    Detects available COM ports using pyserial. Does not probe instruments
    (serial probing can interfere with running devices).

    Returns:
        List of discovered serial port records.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        logger.warning("pyserial not installed. Run: pip install pyserial")
        return []

    instruments: list[InstrumentRecord] = []
    ports = list_ports.comports()
    logger.info("Found %d serial port(s)", len(ports))

    for port in ports:
        record = InstrumentRecord(
            resource=port.device,
            bus=InstrumentBus.SERIAL,
            vendor=port.manufacturer or "",
            model=port.description or "",
            serial=port.serial_number or "",
        )
        instruments.append(record)
        logger.info("  %s: %s (%s)", port.device, port.description, port.manufacturer)

    return instruments

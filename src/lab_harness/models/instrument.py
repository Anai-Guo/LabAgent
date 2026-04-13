"""Data models for lab instruments and inventory."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class InstrumentBus(str, Enum):
    """Communication bus type."""

    GPIB = "gpib"
    USB = "usb"
    SERIAL = "serial"
    ETHERNET = "ethernet"
    NIDAQMX = "nidaqmx"
    UNKNOWN = "unknown"


class InstrumentRecord(BaseModel):
    """A single discovered instrument."""

    resource: str  # VISA resource string, e.g. "GPIB0::5::INSTR"
    vendor: str = ""
    model: str = ""
    serial: str = ""
    firmware: str = ""
    bus: InstrumentBus = InstrumentBus.UNKNOWN
    raw_idn: str = ""

    @property
    def display_name(self) -> str:
        if self.vendor and self.model:
            return f"{self.vendor} {self.model}"
        return self.resource


class LabInventory(BaseModel):
    """Collection of all discovered instruments in a lab."""

    instruments: list[InstrumentRecord] = []

    def find_by_model(self, model_substr: str) -> list[InstrumentRecord]:
        """Find instruments whose model name contains the given substring."""
        return [inst for inst in self.instruments if model_substr.upper() in inst.model.upper()]

    def find_by_vendor(self, vendor_substr: str) -> list[InstrumentRecord]:
        """Find instruments by vendor name."""
        return [inst for inst in self.instruments if vendor_substr.upper() in inst.vendor.upper()]

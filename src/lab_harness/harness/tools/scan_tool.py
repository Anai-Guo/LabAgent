"""Instrument scanning tool."""

from __future__ import annotations

import json

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class ScanInput(BaseModel):
    timeout_ms: int = 2000


class ScanInstrumentsTool(BaseTool):
    name = "scan_instruments"
    description = "Scan lab for connected GPIB/USB/serial instruments via PyVISA"
    input_model = ScanInput

    async def execute(self, arguments: ScanInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.discovery.visa_scanner import scan_visa_instruments

            instruments = scan_visa_instruments(timeout_ms=arguments.timeout_ms)
            output = json.dumps(
                [{"resource": i.resource, "vendor": i.vendor, "model": i.model} for i in instruments],
                indent=2,
            )
            return ToolResult(
                output=f"Found {len(instruments)} instrument(s):\n{output}",
                metadata={"count": len(instruments)},
            )
        except Exception as e:
            return ToolResult(output=f"Scan failed: {e}", is_error=True)

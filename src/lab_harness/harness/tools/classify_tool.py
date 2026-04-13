"""Instrument classification tool."""

from __future__ import annotations

import json

from pydantic import BaseModel

from lab_harness.harness.tools.base import BaseTool, ToolContext, ToolResult


class ClassifyInput(BaseModel):
    measurement_type: str
    instrument_data: list[dict] = []


class ClassifyInstrumentsTool(BaseTool):
    name = "classify_instruments"
    description = (
        "Classify discovered instruments into measurement roles "
        "(e.g. source_meter, dmm, gaussmeter) for a given measurement type"
    )
    input_model = ClassifyInput

    async def execute(self, arguments: ClassifyInput, context: ToolContext) -> ToolResult:
        try:
            from lab_harness.discovery.classifier import classify_instruments
            from lab_harness.models.instrument import InstrumentRecord, LabInventory

            # Build inventory from provided data or scan live
            if arguments.instrument_data:
                records = [InstrumentRecord(**d) for d in arguments.instrument_data]
            else:
                from lab_harness.discovery.visa_scanner import scan_visa_instruments

                records = scan_visa_instruments()

            inventory = LabInventory(instruments=records)
            assignments = classify_instruments(
                inventory=inventory,
                measurement_type=arguments.measurement_type,
            )

            result = {
                role: {"resource": inst.resource, "vendor": inst.vendor, "model": inst.model}
                for role, inst in assignments.items()
            }
            output = json.dumps(result, indent=2)
            return ToolResult(
                output=f"Role assignments for {arguments.measurement_type}:\n{output}",
                metadata={"roles_assigned": len(assignments)},
            )
        except Exception as e:
            return ToolResult(output=f"Classification failed: {e}", is_error=True)

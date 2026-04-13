"""MCP server entry point for Lab Harness.

Exposes lab automation tools via the Model Context Protocol,
compatible with Claude Code, Cursor, and other MCP clients.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from lab_harness.discovery.visa_scanner import scan_visa_instruments
from lab_harness.discovery.classifier import classify_instruments
from lab_harness.models.instrument import LabInventory

mcp = FastMCP(
    "Lab Harness",
    description="AI-guided laboratory automation for physics transport measurements",
)


@mcp.tool()
async def scan_instruments() -> dict:
    """Scan all connected lab instruments via GPIB/USB/serial.

    Discovers instruments on the VISA bus and returns their identity,
    resource address, and detected capabilities.
    """
    instruments = scan_visa_instruments()
    return {
        "count": len(instruments),
        "instruments": [inst.model_dump() for inst in instruments],
    }


@mcp.tool()
async def classify_lab_instruments(
    measurement_type: str,
    inventory_json: str | None = None,
) -> dict:
    """Classify discovered instruments into measurement roles.

    Args:
        measurement_type: Type of measurement (e.g., "AHE", "MR", "IV", "RT").
        inventory_json: Optional JSON string of previously scanned instruments.
            If not provided, performs a fresh scan.
    """
    if inventory_json:
        inventory = LabInventory.model_validate_json(inventory_json)
    else:
        instruments = scan_visa_instruments()
        inventory = LabInventory(instruments=instruments)

    assignments = classify_instruments(inventory, measurement_type)
    return {
        "measurement_type": measurement_type,
        "role_assignments": {
            role: inst.model_dump() for role, inst in assignments.items()
        },
    }


@mcp.tool()
async def propose_measurement(
    measurement_type: str,
    roles_json: str | None = None,
) -> dict:
    """Propose a measurement plan based on type and available instruments.

    Args:
        measurement_type: Type of measurement (e.g., "AHE", "MR", "IV", "RT").
        roles_json: Optional JSON of role assignments from classify_lab_instruments.
    """
    from lab_harness.planning.plan_builder import build_plan_from_template

    plan = build_plan_from_template(measurement_type)
    return plan.model_dump()


@mcp.tool()
async def validate_plan(plan_json: str) -> dict:
    """Validate a measurement plan against safety boundaries.

    Args:
        plan_json: JSON string of the measurement plan to validate.
    """
    from lab_harness.models.measurement import MeasurementPlan
    from lab_harness.planning.boundary_checker import check_boundaries

    plan = MeasurementPlan.model_validate_json(plan_json)
    result = check_boundaries(plan)
    return result.model_dump()


def run_server():
    """Start the MCP server."""
    mcp.run()

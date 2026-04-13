"""MCP server entry point for Lab Harness.

Exposes lab automation tools via the Model Context Protocol,
compatible with Claude Code, Cursor, and other MCP clients.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from lab_harness.config import Settings
from lab_harness.discovery.visa_scanner import scan_visa_instruments
from lab_harness.discovery.classifier import classify_instruments
from lab_harness.llm.router import LLMRouter
from lab_harness.models.instrument import InstrumentRecord, LabInventory

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Lab Harness",
    instructions="AI-guided laboratory automation for physics transport measurements",
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

    # Build LLM router from settings when an API key is available
    router: LLMRouter | None = None
    try:
        settings = Settings.load()
        if settings.model.api_key or settings.model.base_url:
            router = LLMRouter(config=settings.model)
    except Exception as exc:
        logger.debug("LLM router not available for classification fallback: %s", exc)

    assignments = classify_instruments(inventory, measurement_type, router=router)
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

    Returns both the plan and its safety validation result.

    Args:
        measurement_type: Type of measurement (e.g., "AHE", "MR", "IV", "RT").
        roles_json: Optional JSON of role assignments from classify_lab_instruments.
            Expected format: ``{"role_name": {InstrumentRecord fields}, ...}``
    """
    from lab_harness.planning.boundary_checker import check_boundaries
    from lab_harness.planning.plan_builder import build_plan_from_template

    # Parse role assignments if provided
    role_assignments: dict[str, InstrumentRecord] | None = None
    if roles_json:
        raw: dict = json.loads(roles_json)
        role_assignments = {
            role: InstrumentRecord.model_validate(data)
            for role, data in raw.items()
        }

    plan = build_plan_from_template(
        measurement_type,
        role_assignments=role_assignments,
    )
    validation = check_boundaries(plan)

    return {
        "plan": plan.model_dump(),
        "validation": validation.model_dump(),
    }


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


@mcp.tool()
async def healthcheck() -> dict:
    """Check Lab Harness system status.

    Returns availability of PyVISA, available measurement templates,
    LLM configuration, and overall system readiness.
    """
    from pathlib import Path

    status: dict = {
        "version": "0.1.0",
        "visa_available": False,
        "visa_instruments": 0,
        "templates": [],
        "llm_configured": False,
        "llm_provider": None,
        "llm_model": None,
    }

    # Check PyVISA availability
    try:
        import pyvisa

        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        status["visa_available"] = True
        status["visa_instruments"] = len(resources)
    except Exception as exc:
        logger.debug("PyVISA not available: %s", exc)

    # Check available templates
    templates_dir = Path(__file__).parent / "planning" / "templates"
    if templates_dir.is_dir():
        status["templates"] = sorted(p.stem for p in templates_dir.glob("*.yaml"))

    # Check LLM configuration
    try:
        settings = Settings.load()
        status["llm_provider"] = settings.model.provider
        status["llm_model"] = settings.model.model
        status["llm_configured"] = bool(
            settings.model.provider and settings.model.model
        )
    except Exception as exc:
        logger.debug("LLM config not available: %s", exc)

    return status


def run_server():
    """Start the MCP server."""
    mcp.run()

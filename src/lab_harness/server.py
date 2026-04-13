"""MCP server entry point for Lab Harness.

Exposes lab automation tools via the Model Context Protocol,
compatible with Claude Code, Cursor, and other MCP clients.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from lab_harness.config import Settings
from lab_harness.discovery.classifier import classify_instruments
from lab_harness.discovery.visa_scanner import scan_visa_instruments
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
        "role_assignments": {role: inst.model_dump() for role, inst in assignments.items()},
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
        role_assignments = {role: InstrumentRecord.model_validate(data) for role, data in raw.items()}

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
async def search_literature(
    measurement_type: str,
    sample_description: str = "",
) -> dict:
    """Search literature for measurement protocol references.

    Queries the paper-pilot MCP server for published protocols,
    instrument settings, and field/current ranges relevant to the
    requested measurement type.

    Args:
        measurement_type: Type of measurement (e.g., "AHE", "MR", "SOT", "IV", "RT", "CV").
        sample_description: Optional sample details (e.g., "silicon wafer").
    """
    from lab_harness.literature.paper_pilot_client import PaperPilotClient

    client = PaperPilotClient()
    ctx = await client.search_for_protocol(measurement_type, sample_description)
    return ctx.model_dump()


@mcp.tool()
async def analyze_data(
    data_path: str,
    measurement_type: str,
    output_dir: str = "./data/analysis",
    use_ai: bool = False,
    custom_instructions: str = "",
    interpret: bool = False,
) -> dict:
    """Analyze measurement data with template or AI-generated scripts.

    Three analysis tiers:
    1. Template-based (default): built-in scripts for AHE, MR, IV, RT
    2. AI-generated (use_ai=True): LLM creates custom analysis script
    3. AI-interpreted (interpret=True): LLM explains results with physics insights

    If no template exists for the measurement type, automatically falls back to AI.

    Args:
        data_path: Path to the measurement data CSV file.
        measurement_type: Type of measurement (AHE, MR, IV, RT, SOT, CV, or custom).
        output_dir: Directory for output scripts and figures.
        use_ai: Force AI script generation instead of template.
        custom_instructions: Extra instructions for AI analysis (e.g. "focus on coercivity").
        interpret: Add AI interpretation of results with physics insights.
    """
    from pathlib import Path as _Path

    from lab_harness.analysis.analyzer import Analyzer

    analyzer = Analyzer(output_dir=_Path(output_dir))
    dp = _Path(data_path)
    if not dp.exists():
        return {"error": f"Data file not found: {data_path}"}

    try:
        result = analyzer.analyze(
            dp,
            measurement_type,
            use_ai=use_ai,
            custom_instructions=custom_instructions,
            interpret=interpret,
        )
        return result.model_dump()
    except (FileNotFoundError, RuntimeError) as exc:
        return {"error": str(exc)}


@mcp.tool()
async def generate_skill(
    measurement_type: str,
    sample_description: str = "",
) -> dict:
    """Generate and save a new measurement protocol skill using AI.

    Creates a markdown skill file with YAML frontmatter describing
    a step-by-step measurement protocol for the given type.
    Uses existing skills as examples for style consistency.

    Args:
        measurement_type: Type of measurement to generate a skill for
            (e.g., "MR", "AHE", "SOT", "FMR").
        sample_description: Optional sample context to tailor the protocol
            (e.g., "NiFe thin film", "GaAs wafer").
    """
    from lab_harness.skills.generator import generate_skill as _generate
    from lab_harness.skills.generator import save_skill

    try:
        content = _generate(
            measurement_type=measurement_type,
            sample_description=sample_description,
        )
        path = save_skill(measurement_type, content)
        return {
            "measurement_type": measurement_type,
            "skill_path": str(path),
            "content": content,
        }
    except RuntimeError as exc:
        return {"error": str(exc)}


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
        status["llm_configured"] = bool(settings.model.provider and settings.model.model)
    except Exception as exc:
        logger.debug("LLM config not available: %s", exc)

    return status


def run_server():
    """Start the MCP server."""
    mcp.run()

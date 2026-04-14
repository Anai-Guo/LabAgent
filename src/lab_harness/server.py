"""MCP server entry point for Lab Harness.

Exposes lab automation tools via the Model Context Protocol,
compatible with Claude Code, Cursor, and other MCP clients.

Each MCP tool is a thin wrapper around a harness tool from
lab_harness.harness.tools.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from lab_harness.harness.tools.base import ToolContext

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
    from lab_harness.harness.tools.scan_tool import ScanInput, ScanInstrumentsTool

    tool = ScanInstrumentsTool()
    result = await tool.execute(ScanInput(), ToolContext())
    return {"output": result.output, "metadata": result.metadata}


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
    from lab_harness.harness.tools.classify_tool import ClassifyInput, ClassifyInstrumentsTool

    instrument_data: list[dict] = []
    if inventory_json:
        from lab_harness.models.instrument import LabInventory

        inventory = LabInventory.model_validate_json(inventory_json)
        instrument_data = [inst.model_dump() for inst in inventory.instruments]

    tool = ClassifyInstrumentsTool()
    result = await tool.execute(
        ClassifyInput(measurement_type=measurement_type, instrument_data=instrument_data),
        ToolContext(),
    )
    return {"output": result.output, "metadata": result.metadata}


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
    from lab_harness.harness.tools.propose_tool import ProposeInput, ProposeMeasurementTool

    tool = ProposeMeasurementTool()
    result = await tool.execute(
        ProposeInput(measurement_type=measurement_type),
        ToolContext(),
    )
    return {"output": result.output, "metadata": result.metadata}


@mcp.tool()
async def validate_plan(plan_json: str) -> dict:
    """Validate a measurement plan against safety boundaries.

    Args:
        plan_json: JSON string of the measurement plan to validate.
    """
    from lab_harness.harness.tools.validate_tool import ValidateInput, ValidatePlanTool

    plan_dict = json.loads(plan_json)
    tool = ValidatePlanTool()
    result = await tool.execute(
        ValidateInput(plan=plan_dict),
        ToolContext(),
    )
    return {"output": result.output, "metadata": result.metadata}


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
    from lab_harness.harness.tools.literature_tool import LiteratureInput, SearchLiteratureTool

    tool = SearchLiteratureTool()
    result = await tool.execute(
        LiteratureInput(
            measurement_type=measurement_type,
            sample_description=sample_description,
        ),
        ToolContext(),
    )
    return {"output": result.output, "metadata": result.metadata}


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
    from lab_harness.harness.tools.analyze_tool import AnalyzeDataTool, AnalyzeInput

    tool = AnalyzeDataTool()
    result = await tool.execute(
        AnalyzeInput(
            data_path=data_path,
            measurement_type=measurement_type,
            use_ai=use_ai,
            custom_instructions=custom_instructions,
            interpret=interpret,
        ),
        ToolContext(),
    )
    return {"output": result.output, "metadata": result.metadata}


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
    from lab_harness.harness.tools.generate_skill_tool import GenerateSkillInput, GenerateSkillTool

    tool = GenerateSkillTool()
    result = await tool.execute(
        GenerateSkillInput(
            measurement_type=measurement_type,
            sample_description=sample_description,
        ),
        ToolContext(),
    )
    return {"output": result.output, "metadata": result.metadata}


@mcp.tool()
async def healthcheck() -> dict:
    """Check Lab Harness system status.

    Returns availability of PyVISA, available measurement templates,
    LLM configuration, and overall system readiness.
    """
    from lab_harness.harness.tools.health_tool import HealthcheckTool, HealthInput

    tool = HealthcheckTool()
    result = await tool.execute(HealthInput(), ToolContext())
    return {"output": result.output, "metadata": result.metadata}


def run_server():
    """Start the MCP server."""
    mcp.run()

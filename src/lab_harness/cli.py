"""CLI entry point for Lab Harness (standalone mode, no MCP client needed)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lab_harness.config import Settings


def cmd_scan(args: argparse.Namespace, settings: Settings) -> None:
    """Scan for connected instruments."""
    from lab_harness.discovery.visa_scanner import scan_visa_instruments

    instruments = scan_visa_instruments()
    print(f"Found {len(instruments)} instrument(s):\n")
    for inst in instruments:
        print(f"  [{inst.resource}] {inst.vendor} {inst.model} (S/N: {inst.serial})")

    if args.output:
        from lab_harness.models.instrument import LabInventory

        inventory = LabInventory(instruments=instruments)
        Path(args.output).write_text(inventory.model_dump_json(indent=2))
        print(f"\nSaved to {args.output}")


def cmd_classify(args: argparse.Namespace, settings: Settings) -> None:
    """Classify instruments into measurement roles."""
    from lab_harness.discovery.classifier import classify_instruments
    from lab_harness.discovery.visa_scanner import scan_visa_instruments
    from lab_harness.models.instrument import LabInventory

    if args.inventory:
        inventory = LabInventory.model_validate_json(Path(args.inventory).read_text())
    else:
        instruments = scan_visa_instruments()
        inventory = LabInventory(instruments=instruments)

    assignments = classify_instruments(inventory, args.measurement_type)
    print(f"\nRole assignments for '{args.measurement_type}' measurement:\n")
    for role, inst in assignments.items():
        print(f"  {role:24s} -> {inst.vendor} {inst.model} ({inst.resource})")


def cmd_propose(args: argparse.Namespace, settings: Settings) -> None:
    """Propose a measurement plan."""
    from lab_harness.planning.plan_builder import build_plan_from_template

    plan = build_plan_from_template(args.measurement_type)
    print(json.dumps(plan.model_dump(), indent=2))


def cmd_literature(args: argparse.Namespace, settings: Settings) -> None:
    """Search literature for measurement protocols."""
    import asyncio

    from lab_harness.literature.paper_pilot_client import PaperPilotClient

    client = PaperPilotClient()
    ctx = asyncio.run(client.search_for_protocol(args.measurement_type, args.sample or ""))
    print(json.dumps(ctx.model_dump(), indent=2))


def cmd_analyze(args: argparse.Namespace, settings: Settings) -> None:
    """Analyze measurement data."""
    from lab_harness.analysis.analyzer import Analyzer

    data_path = Path(args.data_file)
    if not data_path.exists():
        print(f"Error: data file not found: {data_path}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else Path("./data/analysis")
    analyzer = Analyzer(output_dir=output_dir)
    use_ai = getattr(args, "ai", False)
    interpret = getattr(args, "interpret", False)
    instructions = getattr(args, "instructions", "") or ""

    result = analyzer.analyze(
        data_path,
        args.type,
        use_ai=use_ai,
        custom_instructions=instructions,
        interpret=interpret,
    )

    print(f"Script: {result.script_path}")
    if result.stdout:
        print(f"\n{result.stdout}")
    if result.figures:
        print(f"Figures: {', '.join(result.figures)}")
    if result.extracted_values:
        print(f"Extracted: {json.dumps(result.extracted_values, indent=2)}")
    if result.ai_interpretation:
        print(f"\nAI Interpretation:\n{result.ai_interpretation}")


def cmd_generate_skill(args: argparse.Namespace, settings: Settings) -> None:
    """Generate a measurement protocol skill using AI."""
    from lab_harness.skills.generator import generate_skill, save_skill

    print(f"Generating skill for '{args.measurement_type}'...")
    content = generate_skill(
        measurement_type=args.measurement_type,
        sample_description=args.sample or "",
    )
    print(f"\n{content}\n")

    path = save_skill(args.measurement_type, content)
    print(f"Saved to {path}")


def cmd_chat(args: argparse.Namespace, settings: Settings) -> None:
    """Interactive chat with the Lab Harness agent."""
    import asyncio

    from lab_harness.agent.loop import LabAgent

    agent = LabAgent(settings=settings)
    print("Lab Harness interactive chat (type 'exit' or 'quit' to leave)")

    try:
        while True:
            try:
                user_input = input("> ")
            except EOFError:
                break
            if user_input.strip().lower() in ("exit", "quit"):
                break
            if not user_input.strip():
                continue
            response = asyncio.run(agent.run_conversation(user_input))
            print(response)
    except KeyboardInterrupt:
        pass

    print("Goodbye")


def cmd_procedures(args: argparse.Namespace, settings: Settings) -> None:
    """List PICA reference measurement procedures."""
    from lab_harness.reference.instrument_procedures import PROCEDURES

    print("Available reference procedures:\n")
    for name, proc in PROCEDURES.items():
        desc = proc["description"]
        params = proc.get("parameters", {})
        print(f"  {name}")
        print(f"    {desc}")
        if params:
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            print(f"    Defaults: {param_str}")
        print()


def cmd_web(args: argparse.Namespace, settings: Settings) -> None:
    """Start the adaptive Web GUI."""
    from lab_harness.web.app import run_web

    run_web(host=args.host, port=args.port)


def cmd_panel(args: argparse.Namespace, settings: Settings) -> None:
    """Launch the Claude Code-style terminal panel."""
    try:
        from lab_harness.harness.tui.app import run_panel
    except ImportError:
        print("Error: textual is required for the terminal panel.")
        print("Install it with:  pip install lab-agent[tui]")
        sys.exit(1)

    run_panel(model=args.model)


def cmd_serve(args: argparse.Namespace, settings: Settings) -> None:
    """Start the MCP server."""
    from lab_harness.server import run_server

    run_server()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="labharness",
        description="AI-guided laboratory automation framework",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/models.yaml"),
        help="Path to configuration file",
    )
    sub = parser.add_subparsers(dest="command")

    # scan
    p_scan = sub.add_parser("scan", help="Scan for connected instruments")
    p_scan.add_argument("-o", "--output", help="Save inventory to JSON file")

    # classify
    p_classify = sub.add_parser("classify", help="Classify instruments into roles")
    p_classify.add_argument("measurement_type", help="Measurement type (AHE, MR, IV, RT)")
    p_classify.add_argument("--inventory", help="Path to inventory JSON file")

    # propose
    p_propose = sub.add_parser("propose", help="Propose a measurement plan")
    p_propose.add_argument("measurement_type", help="Measurement type (AHE, MR, IV, RT)")

    # literature
    p_lit = sub.add_parser("literature", help="Search literature for measurement protocols")
    p_lit.add_argument("measurement_type", help="Measurement type (AHE, MR, SOT, IV, RT, CV)")
    p_lit.add_argument("--sample", help="Sample description (e.g. 'silicon wafer')")

    # generate-skill
    p_genskill = sub.add_parser("generate-skill", help="Generate a measurement skill using AI")
    p_genskill.add_argument("measurement_type", help="Measurement type (e.g. MR, AHE, SOT)")
    p_genskill.add_argument("--sample", help="Sample description (e.g. 'NiFe thin film')")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze measurement data")
    p_analyze.add_argument("data_file", help="Path to measurement data CSV file")
    p_analyze.add_argument("--type", required=True, help="Measurement type (AHE, MR, IV, RT)")
    p_analyze.add_argument("--output", help="Output directory (default: ./data/analysis)")
    p_analyze.add_argument("--ai", action="store_true", help="Use AI to generate analysis script")
    p_analyze.add_argument("--interpret", action="store_true", help="Add AI interpretation of results")
    p_analyze.add_argument("--instructions", help="Custom analysis instructions for AI")

    # chat
    sub.add_parser("chat", help="Interactive chat with the agent")

    # procedures
    sub.add_parser("procedures", help="List PICA reference measurement procedures")

    # web
    p_web = sub.add_parser("web", help="Start the adaptive Web GUI")
    p_web.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    p_web.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")

    # panel
    p_panel = sub.add_parser("panel", help="Launch the terminal panel (TUI)")
    p_panel.add_argument("--model", help="Override model name (e.g. claude-sonnet-4-20250514)")

    # serve
    sub.add_parser("serve", help="Start MCP server")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    settings = Settings.load(args.config)
    cmd_map = {
        "scan": cmd_scan,
        "classify": cmd_classify,
        "propose": cmd_propose,
        "literature": cmd_literature,
        "generate-skill": cmd_generate_skill,
        "analyze": cmd_analyze,
        "procedures": cmd_procedures,
        "chat": cmd_chat,
        "panel": cmd_panel,
        "web": cmd_web,
        "serve": cmd_serve,
    }
    cmd_map[args.command](args, settings)


if __name__ == "__main__":
    main()

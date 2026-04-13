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
    ctx = asyncio.run(
        client.search_for_protocol(args.measurement_type, args.sample or "")
    )
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

    script = analyzer.generate_script(data_path, args.type)
    script_path = analyzer.save_script(script, args.type.lower())
    print(f"Generated analysis script: {script_path}")

    if not args.no_run:
        print("Running analysis...")
        result = analyzer.run_script(script_path)
        print(f"\nMeasurement type: {result.measurement_type}")
        if result.figures:
            print(f"Figures: {', '.join(result.figures)}")
    else:
        print("Skipped execution (--no-run). Run manually with:")
        print(f"  python {script_path}")


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
    p_lit.add_argument("--sample", help="Sample description (e.g. 'CoFeB/MgO')")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Analyze measurement data")
    p_analyze.add_argument("data_file", help="Path to measurement data CSV file")
    p_analyze.add_argument("--type", required=True, help="Measurement type (AHE, MR, IV, RT)")
    p_analyze.add_argument("--output", help="Output directory (default: ./data/analysis)")
    p_analyze.add_argument("--no-run", action="store_true", help="Generate script only, don't execute")

    # chat
    sub.add_parser("chat", help="Interactive chat with the agent")

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
        "analyze": cmd_analyze,
        "chat": cmd_chat,
        "serve": cmd_serve,
    }
    cmd_map[args.command](args, settings)


if __name__ == "__main__":
    main()

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
        "serve": cmd_serve,
    }
    cmd_map[args.command](args, settings)


if __name__ == "__main__":
    main()

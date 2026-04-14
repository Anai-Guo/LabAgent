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


def cmd_setup(args: argparse.Namespace, settings: Settings) -> None:
    """Interactive setup wizard for first-time configuration."""
    from pathlib import Path

    print("╔══════════════════════════════════════╗")
    print("║   LabAgent — Setup Wizard            ║")
    print("╚══════════════════════════════════════╝")
    print()

    # Step 1: Choose provider
    print("Step 1: Choose your AI provider\n")
    providers = [
        ("1", "anthropic", "Claude (recommended, best for science)"),
        ("2", "openai", "OpenAI GPT-4o"),
        ("3", "ollama", "Ollama (local, free, private)"),
        ("4", "deepseek", "DeepSeek"),
        ("5", "skip", "Skip for now"),
    ]
    for num, _, desc in providers:
        print(f"  {num}. {desc}")

    choice = input("\nSelect [1-5]: ").strip()
    provider = "anthropic"
    model = "claude-sonnet-4-20250514"
    api_key = ""
    base_url = ""

    for num, prov, _ in providers:
        if choice == num:
            provider = prov
            break

    if provider == "skip":
        print("\nSetup skipped. You can configure later in configs/models.yaml")
        return

    # Step 2: Model selection
    if provider == "anthropic":
        model = "claude-sonnet-4-20250514"
    elif provider == "openai":
        model = "gpt-4o"
    elif provider == "ollama":
        model = input("Ollama model name [qwen3:32b]: ").strip() or "qwen3:32b"
        base_url = input("Ollama URL [http://localhost:11434]: ").strip() or "http://localhost:11434"
    elif provider == "deepseek":
        model = "deepseek/deepseek-chat"

    # Step 3: API key (for cloud providers)
    if provider in ("anthropic", "openai", "deepseek"):
        api_key = input(f"\n{provider.upper()} API key (or press Enter to skip): ").strip()

    # Step 4: Write .env file
    env_path = Path(".env")
    lines = []
    lines.append(f"LABHARNESS_PROVIDER={provider}")
    lines.append(f"LABHARNESS_MODEL={model}")
    if api_key:
        lines.append(f"LABHARNESS_API_KEY={api_key}")
    if base_url:
        lines.append(f"LABHARNESS_BASE_URL={base_url}")

    env_path.write_text("\n".join(lines) + "\n")
    print(f"\nConfiguration saved to {env_path}")

    # Step 5: Test connection
    print("\nTesting connection...")
    try:
        from lab_harness.config import Settings as S

        s = S.load()
        from lab_harness.llm.router import LLMRouter

        router = LLMRouter(config=s.model)
        result = router.complete([{"role": "user", "content": "Say 'hello' in one word."}])
        reply = result["choices"][0]["message"]["content"]
        print(f"Success! Model responded: {reply}")
    except Exception as e:
        print(f"Connection test failed: {e}")
        print("You can fix this later by editing .env or configs/models.yaml")

    print("\nSetup complete! Try: labharness scan")


def cmd_export(args: argparse.Namespace, settings: Settings) -> None:
    """Export measurement data to CSV, JSON, or HDF5."""
    import csv as csv_mod

    from lab_harness.export.exporter import DataExporter, ExportConfig

    data_path = Path(args.data_file)
    if not data_path.exists():
        print(f"Error: data file not found: {data_path}")
        sys.exit(1)

    # Read source CSV
    with open(data_path, newline="", encoding="utf-8") as f:
        # Skip comment lines
        lines = [line for line in f if not line.startswith("#")]

    if not lines:
        print("Error: data file is empty")
        sys.exit(1)

    import io

    reader = csv_mod.DictReader(io.StringIO("".join(lines)))
    data = list(reader)
    if not data:
        print("Error: no data rows found")
        sys.exit(1)

    # Convert numeric strings to floats where possible
    for row in data:
        for key, val in row.items():
            try:
                row[key] = float(val)
            except (ValueError, TypeError):
                pass

    fmt = args.format or "csv"
    name = args.name or data_path.stem
    config = ExportConfig(format=fmt, timestamp_prefix=True)
    exporter = DataExporter(config)
    path = exporter.export(data, name=name, metadata={"source": str(data_path)}, fmt=fmt)
    print(f"Exported {len(data)} rows to {path}")


def cmd_campaign(args: argparse.Namespace, settings: Settings) -> None:
    """Create or preview a batch campaign."""
    from lab_harness.campaign.batch import Campaign, preview_campaign

    # Parse --sweep arguments: "param=val1,val2,val3"
    sweep_params: dict[str, list] = {}
    for s in args.sweep or []:
        if "=" not in s:
            print(f"Error: --sweep must be 'param=val1,val2,...', got: {s}")
            sys.exit(1)
        key, vals_str = s.split("=", 1)
        vals = []
        for v in vals_str.split(","):
            v = v.strip()
            try:
                vals.append(float(v))
            except ValueError:
                vals.append(v)
        sweep_params[key.strip()] = vals

    if not sweep_params:
        print("Error: at least one --sweep parameter is required")
        sys.exit(1)

    # Parse --fixed arguments: "param=value"
    fixed_params: dict[str, object] = {}
    for f in args.fixed or []:
        if "=" not in f:
            print(f"Error: --fixed must be 'param=value', got: {f}")
            sys.exit(1)
        key, val = f.split("=", 1)
        try:
            fixed_params[key.strip()] = float(val.strip())
        except ValueError:
            fixed_params[key.strip()] = val.strip()

    if args.preview:
        print(preview_campaign(args.measurement_type, sweep_params, fixed_params))
        return

    campaign = Campaign.create(args.measurement_type, sweep_params, fixed_params)
    save_path = Path(f"./data/campaigns/{campaign.campaign_id}.json")
    campaign.save(save_path)
    print(f"Campaign {campaign.campaign_id}: {campaign.total_points} points")
    print(f"Saved to {save_path}")


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

    # export
    p_export = sub.add_parser("export", help="Export measurement data")
    p_export.add_argument("data_file", help="Path to measurement data CSV file")
    p_export.add_argument(
        "--format",
        choices=["csv", "json", "hdf5"],
        default="csv",
        help="Output format (default: csv)",
    )
    p_export.add_argument("--name", help="Base name for output file (default: input stem)")

    # campaign
    p_campaign = sub.add_parser("campaign", help="Create a batch measurement campaign")
    p_campaign.add_argument("measurement_type", help="Measurement type (AHE, MR, IV, RT)")
    p_campaign.add_argument(
        "--sweep",
        action="append",
        help="Sweep parameter: 'param=val1,val2,...' (repeatable)",
    )
    p_campaign.add_argument(
        "--fixed",
        action="append",
        help="Fixed parameter: 'param=value' (repeatable)",
    )
    p_campaign.add_argument(
        "--preview",
        action="store_true",
        help="Preview campaign without creating it",
    )

    # setup
    sub.add_parser("setup", help="Interactive setup wizard")

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
        "export": cmd_export,
        "campaign": cmd_campaign,
        "procedures": cmd_procedures,
        "chat": cmd_chat,
        "panel": cmd_panel,
        "web": cmd_web,
        "setup": cmd_setup,
        "serve": cmd_serve,
    }
    cmd_map[args.command](args, settings)


if __name__ == "__main__":
    main()

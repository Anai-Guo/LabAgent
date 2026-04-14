"""End-to-end experiment flow orchestrator."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from lab_harness.config import Settings
from lab_harness.orchestrator.decider import decide_measurement
from lab_harness.orchestrator.folder import open_folder, prepare_data_folder
from lab_harness.orchestrator.session import ExperimentSession

logger = logging.getLogger(__name__)


class ExperimentFlow:
    """Guides a user through a complete experiment from question to data."""

    def __init__(self, settings: Settings, data_root: Path | None = None):
        self.settings = settings
        self.data_root = data_root or Path("./data")
        self.session = ExperimentSession()

    async def run(self, direction: str = "", material: str = "") -> ExperimentSession:
        """Run the full experiment flow. Returns the completed session."""
        print("\n" + "=" * 60)
        print("  LabAgent — Guided Experiment")
        print("=" * 60 + "\n")

        # Step 1: Check API key
        if not (self.settings.model.api_key or self.settings.model.base_url):
            print("⚠  No AI model configured. Run: labharness setup\n")
            print("Continuing with rule-based fallback...\n")

        # Step 2: Gather user input
        self.session.direction = direction or input("Research direction (e.g. 'transport', 'photovoltaics'): ").strip()
        self.session.material = material or input("Sample material (e.g. 'Si wafer', 'Fe/MgO'): ").strip()

        # Step 3: Parallel — literature search + instrument scan
        print("\n[Step 1/6] Searching literature and scanning instruments (parallel)...")
        literature, instruments = await asyncio.gather(
            self._search_literature(),
            self._scan_instruments(),
            return_exceptions=True,
        )
        if isinstance(literature, Exception):
            logger.warning("Literature search failed: %s", literature)
            literature = {}
        if isinstance(instruments, Exception):
            logger.warning("Instrument scan failed: %s", instruments)
            instruments = []
        self.session.literature = literature if isinstance(literature, dict) else {}
        self.session.instruments = instruments if isinstance(instruments, list) else []

        print(f"  ✓ Found {len(self.session.instruments)} instrument(s)")
        if self.session.literature.get("source_papers"):
            print(f"  ✓ Found {len(self.session.literature['source_papers'])} relevant reference(s)")
        else:
            print("  ✓ Literature context ready")

        # Step 4: AI decides measurement type
        print("\n[Step 2/6] AI deciding measurement type...")
        decision = decide_measurement(
            self.session.direction,
            self.session.material,
            self.session.instruments,
            self.session.literature,
        )
        self.session.measurement_type = decision.get("measurement_type", "IV")
        self.session.measurement_reason = decision.get("reasoning", "")
        print(f"  → {self.session.measurement_type}")
        print(f"  Reasoning: {self.session.measurement_reason}")

        # Step 5: Generate plan
        print("\n[Step 3/6] Generating measurement plan...")
        from lab_harness.planning.boundary_checker import check_boundaries
        from lab_harness.planning.plan_builder import build_plan_from_template

        try:
            plan = build_plan_from_template(
                self.session.measurement_type,
                sample_description=self.session.material,
            )
            validation = check_boundaries(plan)
            self.session.plan = plan.model_dump()
            self.session.validation = validation.model_dump()
            print(f"  ✓ {plan.total_points} points, safety: {validation.decision.value.upper()}")
        except FileNotFoundError:
            print(f"  ⚠  No template for {self.session.measurement_type}, falling back to IV")
            self.session.measurement_type = "IV"
            plan = build_plan_from_template("IV", sample_description=self.session.material)
            validation = check_boundaries(plan)
            self.session.plan = plan.model_dump()
            self.session.validation = validation.model_dump()

        # Step 6: Prepare data folder
        folder = prepare_data_folder(self.data_root, self.session.folder_name)
        self.session.data_folder = str(folder)
        print(f"\n[Step 4/6] Data folder: {folder}")

        # Step 7: Wait for user to set up circuit
        print("\n[Step 5/6] Please connect your instruments as follows:")
        for inst in self.session.instruments[:5]:
            print(f"  - {inst.get('vendor', '?')} {inst.get('model', '?')} at {inst.get('resource', '?')}")
        input("\nPress Enter when your circuit is ready... ")

        # Step 8: Launch measurement (simulated for now)
        print("\n[Step 6/6] Running measurement...")
        data_file = await self._run_measurement(plan, folder)
        self.session.data_file = str(data_file)
        self.session.measurement_completed = True
        print(f"  ✓ Saved: {data_file}")

        # Step 9: Analyze with literature context
        print("\n[Analysis] Analyzing results with literature context...")
        await self._analyze(data_file, folder)

        # Step 10: Save summary + offer to open folder
        self.session.save_summary(folder)
        print("\n" + "=" * 60)
        print(f"  Experiment complete! Data in: {folder}")
        print("=" * 60 + "\n")

        if input("Open data folder? [Y/n]: ").strip().lower() != "n":
            open_folder(folder)

        return self.session

    async def _search_literature(self, emit=None) -> dict:
        from lab_harness.literature.paper_pilot_client import PaperPilotClient

        client = PaperPilotClient()
        # Use direction as measurement hint
        ctx = await client.search_for_protocol(
            self.session.direction or "IV",
            self.session.material,
            emit=emit,
        )
        return ctx.model_dump() if hasattr(ctx, "model_dump") else dict(ctx.__dict__)

    async def _scan_instruments(self) -> list[dict]:
        from lab_harness.discovery.visa_scanner import scan_visa_instruments

        loop = asyncio.get_event_loop()
        instruments = await loop.run_in_executor(None, scan_visa_instruments)
        return [i.model_dump() for i in instruments]

    # ------------------------------------------------------------------
    # Phased flow for Web GUI (SSE event emission)
    # ------------------------------------------------------------------

    async def run_phased(self, live_session) -> ExperimentSession:
        """Phased flow for Web GUI that emits events at each milestone.

        ``live_session`` is expected to be a ``LiveSession`` providing
        ``emit`` (async) and ``emit_sync`` (thread-safe) callbacks.
        """
        emit = live_session.emit
        emit_sync = live_session.emit_sync

        # 1. Literature + Scan (parallel)
        await emit("phase", name="discovery", message="Searching literature + scanning instruments")
        literature_task = self._search_literature(emit=emit)

        async def scan_with_emit():
            loop = asyncio.get_event_loop()
            from lab_harness.discovery.visa_scanner import scan_visa_instruments

            return await loop.run_in_executor(None, lambda: scan_visa_instruments(emit=emit_sync))

        instruments_task = scan_with_emit()

        literature, instruments = await asyncio.gather(
            literature_task,
            instruments_task,
            return_exceptions=True,
        )
        if isinstance(literature, Exception):
            logger.warning("Literature search failed: %s", literature)
            literature = {}
        if isinstance(instruments, Exception):
            logger.warning("Instrument scan failed: %s", instruments)
            instruments = []

        self.session.literature = literature if isinstance(literature, dict) else {}
        self.session.instruments = [
            i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in (instruments or [])
        ]

        # 2. AI decision
        await emit("phase", name="decision", message="AI deciding measurement type")
        from lab_harness.orchestrator.decider import decide_measurement

        decision = decide_measurement(
            self.session.direction,
            self.session.material,
            self.session.instruments,
            self.session.literature,
        )
        self.session.measurement_type = decision.get("measurement_type", "IV")
        self.session.measurement_reason = decision.get("reasoning", "")
        await emit(
            "decision.complete",
            measurement_type=self.session.measurement_type,
            reasoning=self.session.measurement_reason,
        )

        # 3. Build plan
        from lab_harness.planning.boundary_checker import check_boundaries
        from lab_harness.planning.plan_builder import build_plan_from_template

        try:
            plan = build_plan_from_template(
                self.session.measurement_type,
                sample_description=self.session.material,
            )
        except FileNotFoundError:
            self.session.measurement_type = "IV"
            plan = build_plan_from_template("IV", sample_description=self.session.material)
        validation = check_boundaries(plan)
        self.session.plan = plan.model_dump()
        self.session.validation = validation.model_dump()
        await emit(
            "plan.complete",
            plan=self.session.plan,
            validation=self.session.validation,
            folder_suggestion=self.session.folder_name,
        )

        # 4. Wait for folder confirmation from the UI
        await emit("await_folder_confirm", default_folder=self.session.folder_name)
        for _ in range(300):  # 5 min max
            if self.session.folder_confirmed:
                break
            await asyncio.sleep(1)

        # 5. Prepare folder
        from pathlib import Path

        from lab_harness.orchestrator.folder import prepare_data_folder

        parent = Path(self.session.parent_dir) if self.session.parent_dir else self.data_root
        folder = prepare_data_folder(parent, self.session.folder_name)
        self.session.data_folder = str(folder)
        await emit("folder.ready", path=str(folder))

        # 6. Run measurement (simulated, streaming progress)
        await emit("measurement.start", total_points=plan.total_points)
        data_file = await self._run_measurement_streaming(plan, folder, emit)
        self.session.data_file = str(data_file)
        self.session.measurement_completed = True
        await emit("measurement.complete", data_file=str(data_file))

        # 7. Analysis with literature context
        await emit("phase", name="analysis", message="Analyzing with literature context")
        await self._analyze(data_file, folder)
        figures = self.session.analysis_result.get("figures", []) if self.session.analysis_result else []
        await emit(
            "analysis.complete",
            figures=[Path(f).name for f in figures],
            extracted_values=(
                self.session.analysis_result.get("extracted_values", {}) if self.session.analysis_result else {}
            ),
            interpretation=self.session.ai_interpretation,
        )

        # 8. Next steps
        if self.session.next_step_suggestions:
            await emit("next_steps.ready", text=self.session.next_step_suggestions)

        # 9. Save summary
        self.session.save_summary(folder)
        await emit("done", folder=str(folder))
        live_session.done = True

        return self.session

    async def _run_measurement_streaming(self, plan, folder: Path, emit) -> Path:
        """Streaming version of ``_run_measurement`` that emits progress events."""
        import csv

        from lab_harness.orchestrator.simulators import simulate

        data_file = folder / "raw_data.csv"
        points = simulate(
            plan,
            self.session.measurement_type,
            seed=42,
            literature=self.session.literature,
        )
        if not points:
            return data_file

        fieldnames = list(points[0].keys())
        emit_every = max(1, len(points) // 20)
        with open(data_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for i, row in enumerate(points):
                writer.writerow(row)
                if i % emit_every == 0 or i == len(points) - 1:
                    values = list(row.values())
                    await emit(
                        "measurement.point",
                        index=i,
                        total=len(points),
                        x=values[0] if values else 0,
                        y=values[1] if len(values) > 1 else 0,
                    )
                    await asyncio.sleep(0.01)

        return data_file

    async def _run_measurement(self, plan, folder: Path) -> Path:
        """Run measurement using physics-based simulator for realistic data."""
        import csv

        from lab_harness.orchestrator.simulators import simulate

        data_file = folder / "raw_data.csv"

        # Generate realistic data for this measurement type
        points = simulate(
            plan,
            self.session.measurement_type,
            seed=42,  # deterministic for reproducibility
            literature=self.session.literature,
        )

        if not points:
            return data_file

        # Write multi-column CSV matching plan.x_axis + y_channels
        fieldnames = list(points[0].keys())
        with open(data_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(points)

        return data_file

    async def _analyze(self, data_file: Path, folder: Path) -> None:
        """Run analysis with literature-aware interpretation."""
        from lab_harness.analysis.analyzer import Analyzer

        analyzer = Analyzer(output_dir=folder)
        try:
            result = analyzer.analyze(
                data_file,
                self.session.measurement_type,
                use_ai=False,
                interpret=True,
                literature=self.session.literature,
            )
            self.session.analysis_result = result.model_dump()
            self.session.ai_interpretation = result.ai_interpretation
            print(f"  ✓ Analysis script: {Path(result.script_path).name}")
            if result.figures:
                print(f"  ✓ Figures: {len(result.figures)}")
            if result.ai_interpretation:
                print("\n  AI Interpretation:")
                print(f"  {result.ai_interpretation[:300]}...")
        except Exception as e:
            logger.warning("Analysis failed: %s", e)
            print(f"  ⚠  Analysis encountered an issue: {e}")

        # Generate next-step suggestions
        self._suggest_next_steps(folder)

    def _suggest_next_steps(self, folder: Path) -> None:
        """AI-generated suggestions for next experiments with literature context."""
        if not (self.settings.model.api_key or self.settings.model.base_url):
            return
        try:
            from lab_harness.llm.router import LLMRouter

            router = LLMRouter(config=self.settings.model)

            # Build prompt with literature context
            lit_block = ""
            if self.session.literature:
                papers = self.session.literature.get("source_papers", [])
                if papers:
                    lit_block = "\n\nRelevant literature:\n"
                    for i, p in enumerate(papers[:5], 1):
                        title = p.get("title") or p.get("source") or f"paper {i}"
                        lit_block += f"[{i}] {title}\n"
                    lit_block += "\nCite papers by [N] where relevant."

            prompt = (
                f"Based on this {self.session.measurement_type} measurement on {self.session.material}, "
                f"suggest 3 concrete follow-up experiments. Be brief (under 150 words).{lit_block}"
            )
            resp = router.complete(
                [
                    {"role": "system", "content": "You are a helpful experimental scientist."},
                    {"role": "user", "content": prompt},
                ]
            )
            text = resp["choices"][0]["message"]["content"].strip()
            self.session.next_step_suggestions = text
            (folder / "next_steps.md").write_text(text, encoding="utf-8")
            print("\n  Next step suggestions saved to next_steps.md")
        except Exception:
            pass

"""Data analysis orchestrator.

Generates and optionally runs analysis scripts from measurement data.
Three-tier approach:
  1. Template-based: built-in scripts for known measurement types
  2. AI-generated: LLM creates custom analysis scripts
  3. AI-interpreted: LLM explains results and provides physics insights
"""
from __future__ import annotations

import csv
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class AnalysisResult(BaseModel):
    """Result of data analysis."""

    measurement_type: str
    script_path: str
    script_source: str
    figures: list[str] = []
    extracted_values: dict[str, Any] = {}
    ai_interpretation: str = ""  # LLM-generated physics insights
    stdout: str = ""  # Script output


def _read_data_preview(data_path: Path, max_rows: int = 20) -> str:
    """Read a preview of the data file for LLM context."""
    try:
        text = data_path.read_text(encoding="utf-8", errors="replace")
        lines = text.strip().splitlines()
        header = lines[0] if lines else ""
        sample = lines[1 : max_rows + 1]
        preview = f"File: {data_path.name}\n"
        preview += f"Columns: {header}\n"
        preview += f"Total rows: {len(lines) - 1}\n"
        preview += f"Sample data:\n{header}\n" + "\n".join(sample)
        return preview
    except Exception as e:
        return f"Could not read data: {e}"


@dataclass
class Analyzer:
    """Data analysis orchestrator with template and AI capabilities."""

    output_dir: Path = Path("./data/analysis")

    # --- Tier 1: Template-based analysis ---

    def generate_script(
        self,
        data_path: Path,
        measurement_type: str,
    ) -> str:
        """Generate analysis script from built-in template."""
        template_path = TEMPLATES_DIR / f"{measurement_type.lower()}.py"
        if not template_path.exists():
            raise FileNotFoundError(
                f"No analysis template for '{measurement_type}'. "
                f"Available: {[p.stem for p in TEMPLATES_DIR.glob('*.py')]}"
            )

        template = template_path.read_text()
        script = template.replace("{{DATA_PATH}}", str(data_path))
        script = script.replace("{{OUTPUT_DIR}}", str(self.output_dir))
        return script

    # --- Tier 2: AI-generated analysis ---

    def generate_script_with_ai(
        self,
        data_path: Path,
        measurement_type: str,
        custom_instructions: str = "",
    ) -> str:
        """Generate a custom analysis script using LLM.

        Uses the data preview and measurement type to create a tailored
        analysis script. Falls back to template if LLM is unavailable.

        Args:
            data_path: Path to measurement data file.
            measurement_type: Type of measurement.
            custom_instructions: Additional analysis instructions from user.
        """
        from lab_harness.config import Settings
        from lab_harness.llm.router import LLMRouter

        settings = Settings.load()
        if not (settings.model.api_key or settings.model.base_url):
            logger.warning("No LLM configured, falling back to template")
            return self.generate_script(data_path, measurement_type)

        router = LLMRouter(config=settings.model)
        data_preview = _read_data_preview(data_path)

        system_prompt = (
            "You are a data analysis expert for condensed matter physics experiments.\n"
            "Generate a COMPLETE, self-contained Python analysis script.\n\n"
            "Requirements:\n"
            "- Use numpy, matplotlib, scipy as needed\n"
            "- Use matplotlib.use('Agg') for non-interactive backend\n"
            "- Load data from the exact path provided\n"
            "- Save figures to the output directory as PNG (300 dpi) and PDF\n"
            "- Print extracted physical quantities with units\n"
            "- Add appropriate axis labels, titles, and legends\n"
            "- Handle edge cases (empty data, NaN values)\n\n"
            "Output ONLY the Python script, no markdown fences or explanation."
        )

        user_msg = (
            f"Measurement type: {measurement_type}\n"
            f"Data file: {data_path}\n"
            f"Output directory: {self.output_dir}\n\n"
            f"Data preview:\n{data_preview}\n"
        )
        if custom_instructions:
            user_msg += f"\nAdditional instructions:\n{custom_instructions}\n"

        response = router.complete([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ])
        script = response["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if present
        if script.startswith("```"):
            first_nl = script.index("\n")
            script = script[first_nl + 1 :]
            if script.endswith("```"):
                script = script[:-3]
            script = script.strip()

        return script

    # --- Tier 3: AI interpretation of results ---

    def interpret_results(
        self,
        result: AnalysisResult,
        data_path: Path | None = None,
    ) -> str:
        """Use LLM to interpret analysis results and provide physics insights.

        Args:
            result: The analysis result to interpret.
            data_path: Optional path to original data for context.

        Returns:
            AI-generated interpretation with physics insights.
        """
        from lab_harness.config import Settings
        from lab_harness.llm.router import LLMRouter

        settings = Settings.load()
        if not (settings.model.api_key or settings.model.base_url):
            return ""

        router = LLMRouter(config=settings.model)

        system_prompt = (
            "You are an expert condensed matter physicist analyzing transport measurement data.\n"
            "Given the analysis results, provide a concise interpretation including:\n"
            "1. What the extracted values tell us about the sample\n"
            "2. Whether the results look physically reasonable\n"
            "3. Comparison with typical values in literature\n"
            "4. Any anomalies or concerns\n"
            "5. Suggested follow-up measurements if applicable\n\n"
            "Keep the response under 200 words. Be specific and quantitative."
        )

        context = f"Measurement type: {result.measurement_type}\n"
        if result.extracted_values:
            context += f"Extracted values: {result.extracted_values}\n"
        if result.stdout:
            context += f"Script output:\n{result.stdout}\n"
        if data_path:
            preview = _read_data_preview(data_path, max_rows=5)
            context += f"\nData preview:\n{preview}\n"

        response = router.complete([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ])
        return response["choices"][0]["message"]["content"].strip()

    # --- Common methods ---

    def save_script(self, script: str, name: str) -> Path:
        """Save generated script to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        script_path = self.output_dir / f"{name}_analysis.py"
        script_path.write_text(script)
        logger.info("Saved analysis script to %s", script_path)
        return script_path

    def run_script(self, script_path: Path, timeout: int = 120) -> AnalysisResult:
        """Execute analysis script in subprocess with timeout."""
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(script_path.parent),
        )

        if result.returncode != 0:
            logger.error("Analysis script failed:\n%s", result.stderr)
            raise RuntimeError(f"Analysis failed: {result.stderr[:500]}")

        # Parse extracted values from stdout (lines matching "key = value")
        extracted = {}
        for line in result.stdout.strip().splitlines():
            if "=" in line and not line.startswith("#"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    extracted[key] = val

        figures = list(self.output_dir.glob("*.png")) + list(self.output_dir.glob("*.pdf"))

        return AnalysisResult(
            measurement_type=script_path.stem.replace("_analysis", ""),
            script_path=str(script_path),
            script_source=script_path.read_text(),
            figures=[str(f) for f in figures],
            extracted_values=extracted,
            stdout=result.stdout,
        )

    def analyze(
        self,
        data_path: Path,
        measurement_type: str,
        use_ai: bool = False,
        custom_instructions: str = "",
        interpret: bool = False,
    ) -> AnalysisResult:
        """Full analysis pipeline: generate script → run → optionally interpret.

        Args:
            data_path: Path to measurement data CSV.
            measurement_type: Measurement type (AHE, MR, IV, RT, etc.)
            use_ai: If True, use LLM to generate script instead of template.
            custom_instructions: Extra instructions for AI script generation.
            interpret: If True, add AI interpretation of results.

        Returns:
            AnalysisResult with script, figures, values, and optional interpretation.
        """
        if use_ai:
            script = self.generate_script_with_ai(
                data_path, measurement_type, custom_instructions
            )
        else:
            try:
                script = self.generate_script(data_path, measurement_type)
            except FileNotFoundError:
                logger.info(
                    "No template for '%s', falling back to AI generation",
                    measurement_type,
                )
                script = self.generate_script_with_ai(
                    data_path, measurement_type, custom_instructions
                )

        script_path = self.save_script(script, measurement_type.lower())
        result = self.run_script(script_path)

        if interpret:
            result.ai_interpretation = self.interpret_results(result, data_path)

        return result

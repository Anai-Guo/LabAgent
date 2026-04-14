"""Experiment session: holds all state for a complete experiment flow."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4


@dataclass
class ExperimentSession:
    """State for an end-to-end guided experiment."""

    session_id: str = field(default_factory=lambda: uuid4().hex[:8])
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # User input
    direction: str = ""  # research direction (e.g. "transport")
    material: str = ""  # sample/material (e.g. "Si wafer")

    # Discovered
    instruments: list[dict] = field(default_factory=list)
    literature: dict = field(default_factory=dict)

    # AI decisions
    measurement_type: str = ""  # decided measurement type
    measurement_reason: str = ""  # AI's reasoning
    plan: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)

    # Execution
    data_folder: str = ""
    data_file: str = ""
    measurement_completed: bool = False

    # Analysis
    analysis_result: dict = field(default_factory=dict)
    ai_interpretation: str = ""
    next_step_suggestions: str = ""

    # User-controlled folder placement (Web flow)
    folder_name_override: str = ""
    folder_confirmed: bool = False
    parent_dir: str = "./data"

    # Simulation flag — True means data came from the physics simulator rather
    # than real instruments. Default True reflects current reality; real driver
    # integration will flip this to False.
    simulated: bool = True

    @property
    def folder_name(self) -> str:
        """Generate organized folder name: date_material_type/.

        If ``folder_name_override`` has been set (typically by the user
        via the Web UI), it takes precedence over the auto-generated
        name.
        """
        if self.folder_name_override:
            return self.folder_name_override
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        mat = self._slug(self.material) or "sample"
        mtype = self.measurement_type or "measurement"
        return f"{ts}_{mat}_{mtype}"

    @staticmethod
    def _slug(text: str, max_len: int = 20) -> str:
        """Convert text to filesystem-safe slug."""
        import re

        s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
        return s[:max_len]

    def to_dict(self) -> dict:
        """Serialize to dict (for saving to JSON)."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "direction": self.direction,
            "material": self.material,
            "measurement_type": self.measurement_type,
            "measurement_reason": self.measurement_reason,
            "instruments_count": len(self.instruments),
            "data_folder": self.data_folder,
            "data_file": self.data_file,
            "measurement_completed": self.measurement_completed,
            "ai_interpretation": self.ai_interpretation,
            "next_step_suggestions": self.next_step_suggestions,
            "simulated": self.simulated,
        }

    def save_summary(self, folder: Path) -> None:
        """Save experiment summary to folder as README + JSON."""
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "experiment_summary.json").write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

        # Human-readable README
        readme = [
            f"# Experiment: {self.material} — {self.measurement_type}",
            "",
        ]
        if self.simulated:
            readme += [
                "> ⚠️ **SIMULATED DATA** — This experiment was run with LabAgent's",
                "> physics simulator, NOT real instruments. For publication, re-run",
                "> with actual instruments connected.",
                "",
            ]
        readme += [
            f"**Date**: {self.started_at}",
            f"**Direction**: {self.direction}",
            f"**Material**: {self.material}",
            f"**Measurement**: {self.measurement_type}",
            "",
            "## AI Reasoning",
            self.measurement_reason or "(not recorded)",
            "",
            "## Instruments Used",
        ]
        for inst in self.instruments:
            readme.append(f"- {inst.get('vendor', '?')} {inst.get('model', '?')} ({inst.get('resource', '?')})")

        if self.ai_interpretation:
            readme += ["", "## AI Analysis", self.ai_interpretation]
        if self.next_step_suggestions:
            readme += ["", "## Suggested Next Steps", self.next_step_suggestions]

        (folder / "README.md").write_text("\n".join(readme), encoding="utf-8")

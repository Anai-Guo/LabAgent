"""Batch campaign mode for automated parameter sweeps.

Generates all combinations of parameters and creates a measurement
plan for each combination.
"""

from __future__ import annotations

import itertools
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CampaignPoint:
    """A single measurement point in a campaign."""

    index: int
    parameters: dict[str, Any]
    measurement_type: str
    status: str = "pending"  # pending, running, completed, failed
    result_path: str = ""


@dataclass
class Campaign:
    """A batch campaign with multiple measurement points."""

    campaign_id: str
    measurement_type: str
    sweep_parameters: dict[str, list[Any]]
    fixed_parameters: dict[str, Any] = field(default_factory=dict)
    points: list[CampaignPoint] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def total_points(self) -> int:
        return len(self.points)

    @property
    def completed_points(self) -> int:
        return sum(1 for p in self.points if p.status == "completed")

    @property
    def progress(self) -> float:
        if not self.points:
            return 0.0
        return self.completed_points / self.total_points

    def generate_points(self) -> None:
        """Generate all parameter combinations."""
        keys = list(self.sweep_parameters.keys())
        values = [self.sweep_parameters[k] for k in keys]

        self.points = []
        for i, combo in enumerate(itertools.product(*values)):
            params = dict(zip(keys, combo))
            params.update(self.fixed_parameters)
            self.points.append(
                CampaignPoint(
                    index=i,
                    parameters=params,
                    measurement_type=self.measurement_type,
                )
            )

        logger.info(
            "Campaign %s: generated %d points from %d parameters",
            self.campaign_id,
            len(self.points),
            len(keys),
        )

    def next_pending(self) -> CampaignPoint | None:
        """Get the next pending measurement point."""
        for p in self.points:
            if p.status == "pending":
                return p
        return None

    def save(self, path: Path) -> None:
        """Save campaign state to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "campaign_id": self.campaign_id,
            "measurement_type": self.measurement_type,
            "sweep_parameters": self.sweep_parameters,
            "fixed_parameters": self.fixed_parameters,
            "created_at": self.created_at,
            "points": [
                {
                    "index": p.index,
                    "parameters": p.parameters,
                    "measurement_type": p.measurement_type,
                    "status": p.status,
                    "result_path": p.result_path,
                }
                for p in self.points
            ],
        }
        path.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Campaign saved to %s", path)

    @classmethod
    def load(cls, path: Path) -> Campaign:
        """Load campaign from JSON."""
        data = json.loads(path.read_text())
        campaign = cls(
            campaign_id=data["campaign_id"],
            measurement_type=data["measurement_type"],
            sweep_parameters=data["sweep_parameters"],
            fixed_parameters=data.get("fixed_parameters", {}),
            created_at=data.get("created_at", ""),
        )
        campaign.points = [CampaignPoint(**p) for p in data.get("points", [])]
        return campaign

    @classmethod
    def create(
        cls,
        measurement_type: str,
        sweep_parameters: dict[str, list[Any]],
        fixed_parameters: dict[str, Any] | None = None,
    ) -> Campaign:
        """Create a new campaign and generate all measurement points."""
        from uuid import uuid4

        campaign = cls(
            campaign_id=f"campaign-{uuid4().hex[:8]}",
            measurement_type=measurement_type,
            sweep_parameters=sweep_parameters,
            fixed_parameters=fixed_parameters or {},
        )
        campaign.generate_points()
        return campaign


def preview_campaign(
    measurement_type: str,
    sweep_parameters: dict[str, list[Any]],
    fixed_parameters: dict[str, Any] | None = None,
) -> str:
    """Preview a campaign without creating it."""
    total = 1
    for vals in sweep_parameters.values():
        total *= len(vals)

    lines = [f"Campaign preview: {measurement_type}"]
    lines.append(f"  Total points: {total}")
    lines.append("  Sweep parameters:")
    for k, v in sweep_parameters.items():
        lines.append(f"    {k}: {len(v)} values ({v[0]} ... {v[-1]})")
    if fixed_parameters:
        lines.append("  Fixed parameters:")
        for k, v in fixed_parameters.items():
            lines.append(f"    {k}: {v}")
    return "\n".join(lines)

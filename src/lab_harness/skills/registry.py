"""Skill registry - discovers and loads measurement protocol skills."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"


@dataclass
class SkillMeta:
    """Level 0: skill metadata only (for progressive disclosure)."""

    name: str
    description: str
    measurement_type: str
    instruments: list[str]
    version: str
    path: Path


@dataclass
class Skill:
    """Level 1: full skill content."""

    meta: SkillMeta
    steps: str  # markdown body


def load_skill_meta(path: Path) -> SkillMeta | None:
    """Parse YAML frontmatter from a skill markdown file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.index("---", 3)
    front = yaml.safe_load(text[3:end])
    return SkillMeta(
        name=front.get("name", path.stem),
        description=front.get("description", ""),
        measurement_type=front.get("measurement_type", ""),
        instruments=front.get("instruments", []),
        version=front.get("version", "1.0"),
        path=path,
    )


def load_skill(path: Path) -> Skill | None:
    """Load full skill content."""
    meta = load_skill_meta(path)
    if meta is None:
        return None
    text = path.read_text(encoding="utf-8")
    end = text.index("---", 3) + 3
    body = text[end:].strip()
    return Skill(meta=meta, steps=body)


class SkillRegistry:
    """Discovers and manages measurement protocol skills."""

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._cache: dict[str, SkillMeta] = {}

    def discover(self) -> list[SkillMeta]:
        """Level 0: discover all skills, return metadata only."""
        self._cache.clear()
        if not self.skills_dir.exists():
            logger.warning("Skills directory not found: %s", self.skills_dir)
            return []
        for path in sorted(self.skills_dir.glob("*.md")):
            meta = load_skill_meta(path)
            if meta:
                self._cache[meta.measurement_type] = meta
        return list(self._cache.values())

    def get_skill(self, measurement_type: str) -> Skill | None:
        """Level 1: load full skill by measurement type."""
        meta = self._cache.get(measurement_type.upper())
        if meta is None:
            return None
        return load_skill(meta.path)

    def list_types(self) -> list[str]:
        """Return available measurement types."""
        if not self._cache:
            self.discover()
        return list(self._cache.keys())

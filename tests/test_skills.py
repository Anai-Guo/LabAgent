"""Tests for the skill registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from lab_harness.skills.registry import SkillRegistry, load_skill, load_skill_meta

# The project-root skills/ directory contains ahe.md and sot.md.
SKILLS_DIR = Path(__file__).parent.parent / "skills"


# ------------------------------------------------------------------
# load_skill_meta / load_skill (standalone functions)
# ------------------------------------------------------------------

class TestLoadSkillMeta:
    def test_load_skill_meta(self):
        """load_skill_meta parses YAML frontmatter correctly."""
        meta = load_skill_meta(SKILLS_DIR / "ahe.md")
        assert meta is not None
        assert meta.name == "AHE Measurement"
        assert meta.measurement_type == "AHE"
        assert "source_meter" in meta.instruments
        assert meta.version == "1.0"
        assert meta.path == SKILLS_DIR / "ahe.md"

    def test_load_full_skill(self):
        """load_skill returns both meta and body."""
        skill = load_skill(SKILLS_DIR / "ahe.md")
        assert skill is not None
        assert skill.meta.measurement_type == "AHE"
        # Body should contain protocol steps, not frontmatter delimiters
        assert "## Protocol" in skill.steps
        assert "---" not in skill.steps

    def test_load_skill_meta_no_frontmatter(self, tmp_path: Path):
        """Returns None when file has no YAML frontmatter."""
        bad = tmp_path / "bad.md"
        bad.write_text("# No frontmatter here\n", encoding="utf-8")
        assert load_skill_meta(bad) is None

    def test_load_skill_no_frontmatter(self, tmp_path: Path):
        """load_skill also returns None for files without frontmatter."""
        bad = tmp_path / "bad.md"
        bad.write_text("# Nothing\n", encoding="utf-8")
        assert load_skill(bad) is None


# ------------------------------------------------------------------
# SkillRegistry
# ------------------------------------------------------------------

class TestSkillRegistry:
    def test_discover_skills(self):
        """SkillRegistry discovers skills from the skills/ directory."""
        reg = SkillRegistry(skills_dir=SKILLS_DIR)
        skills = reg.discover()
        types = {s.measurement_type for s in skills}
        assert "AHE" in types
        assert "SOT" in types
        assert len(skills) >= 2

    def test_get_skill_by_type(self):
        """registry.get_skill('AHE') returns the AHE skill."""
        reg = SkillRegistry(skills_dir=SKILLS_DIR)
        reg.discover()
        skill = reg.get_skill("AHE")
        assert skill is not None
        assert skill.meta.name == "AHE Measurement"
        assert "## Protocol" in skill.steps

    def test_get_skill_case_insensitive(self):
        """get_skill uppercases the key, so 'ahe' should also work."""
        reg = SkillRegistry(skills_dir=SKILLS_DIR)
        reg.discover()
        assert reg.get_skill("ahe") is not None

    def test_list_types(self):
        """list_types returns available measurement types."""
        reg = SkillRegistry(skills_dir=SKILLS_DIR)
        reg.discover()
        types = reg.list_types()
        assert "AHE" in types
        assert "SOT" in types

    def test_missing_skill(self):
        """get_skill for unknown type returns None."""
        reg = SkillRegistry(skills_dir=SKILLS_DIR)
        reg.discover()
        assert reg.get_skill("NONEXISTENT") is None

    def test_discover_empty_dir(self, tmp_path: Path):
        """Discover on an empty directory returns an empty list."""
        reg = SkillRegistry(skills_dir=tmp_path)
        assert reg.discover() == []

    def test_discover_missing_dir(self, tmp_path: Path):
        """Discover on a non-existent directory returns empty and logs warning."""
        reg = SkillRegistry(skills_dir=tmp_path / "no_such_dir")
        assert reg.discover() == []

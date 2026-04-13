"""AI-powered measurement skill generator."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"

SYSTEM_GENERATE_SKILL = """\
You are an expert in condensed matter physics measurement protocols.
Generate a measurement protocol skill in markdown format with YAML frontmatter.

The skill must follow this exact format:
---
name: <Descriptive Name>
description: <One-line description>
measurement_type: <TYPE>
instruments: [<list of required instrument roles>]
version: "1.0"
---

## Protocol

1. **Connect** instruments and verify identity
2. <step-by-step measurement procedure>
...

## Expected Output

- <what data/plots this measurement produces>
- <key parameters to extract>

Use the example skills as reference for style and detail level.
"""


def generate_skill(
    measurement_type: str,
    sample_description: str = "",
    example_skills: list[str] | None = None,
) -> str:
    """Generate a new measurement protocol skill using LLM.

    Args:
        measurement_type: The measurement type to create a skill for.
        sample_description: Optional sample context.
        example_skills: Optional list of existing skill contents as examples.

    Returns:
        Generated skill content as markdown string.
    """
    from lab_harness.config import Settings
    from lab_harness.llm.router import LLMRouter

    settings = Settings.load()
    if not (settings.model.api_key or settings.model.base_url):
        raise RuntimeError("LLM not configured. Set LABHARNESS_API_KEY.")

    router = LLMRouter(config=settings.model)

    # Load existing skills as examples
    if example_skills is None:
        example_skills = []
        for skill_path in sorted(SKILLS_DIR.glob("*.md"))[:2]:
            example_skills.append(skill_path.read_text())

    user_msg = f"Generate a measurement protocol skill for: {measurement_type}\n"
    if sample_description:
        user_msg += f"Sample context: {sample_description}\n"
    if example_skills:
        user_msg += "\nExample skills for reference:\n"
        for i, ex in enumerate(example_skills):
            user_msg += f"\n--- Example {i + 1} ---\n{ex}\n"

    response = router.complete(
        [
            {"role": "system", "content": SYSTEM_GENERATE_SKILL},
            {"role": "user", "content": user_msg},
        ]
    )
    content = response["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if present
    if content.startswith("```"):
        content = content[content.index("\n") + 1 :]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    return content


def save_skill(measurement_type: str, content: str) -> Path:
    """Save a generated skill to the skills directory."""
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    path = SKILLS_DIR / f"{measurement_type.lower()}.md"
    path.write_text(content)
    logger.info("Saved skill to %s", path)
    return path

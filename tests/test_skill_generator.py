"""Tests for the LLM-backed measurement skill generator."""

from unittest.mock import MagicMock, patch

import pytest

from lab_harness.skills import generator
from lab_harness.skills.generator import SYSTEM_GENERATE_SKILL, generate_skill, save_skill

SKILL_MD = """---
name: Hall Effect
description: Carrier density from Hall voltage
measurement_type: HALL
instruments: [source_meter, voltmeter]
version: "1.0"
---

## Protocol

1. **Connect** instruments and verify identity"""


def _make_mock_router(response_text: str):
    router = MagicMock()
    router.complete.return_value = {
        "choices": [{"message": {"content": response_text}}],
    }
    return router


def _configure(mock_settings, mock_router_cls, response_text: str):
    mock_settings.return_value.model.api_key = "test"
    mock_settings.return_value.model.base_url = None
    router = _make_mock_router(response_text)
    mock_router_cls.return_value = router
    return router


def test_generate_raises_without_llm_credentials():
    """Unlike the advisory helpers, skill generation has no fallback and must fail loudly."""
    with patch("lab_harness.config.Settings.load") as mock_settings:
        mock_settings.return_value.model.api_key = ""
        mock_settings.return_value.model.base_url = ""
        with pytest.raises(RuntimeError, match="LLM not configured"):
            generate_skill("HALL", example_skills=[])


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_generate_returns_plain_reply_stripped(mock_router_cls, mock_settings):
    """A bare markdown reply is returned with surrounding whitespace removed."""
    _configure(mock_settings, mock_router_cls, f"\n  {SKILL_MD}  \n")

    assert generate_skill("HALL", example_skills=[]) == SKILL_MD


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_generate_strips_markdown_fences(mock_router_cls, mock_settings):
    """Models often wrap the skill in ```markdown fences; the fences must be removed."""
    _configure(mock_settings, mock_router_cls, f"```markdown\n{SKILL_MD}\n```")

    assert generate_skill("HALL", example_skills=[]) == SKILL_MD


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_generate_prompt_includes_context_and_examples(mock_router_cls, mock_settings):
    """The system prompt, measurement type, sample context and examples all reach the LLM."""
    router = _configure(mock_settings, mock_router_cls, SKILL_MD)

    generate_skill("HALL", sample_description="GaAs wafer", example_skills=["EXAMPLE-A", "EXAMPLE-B"])

    messages = router.complete.call_args[0][0]
    assert messages[0] == {"role": "system", "content": SYSTEM_GENERATE_SKILL}
    user_msg = messages[1]["content"]
    assert messages[1]["role"] == "user"
    assert "Generate a measurement protocol skill for: HALL" in user_msg
    assert "Sample context: GaAs wafer" in user_msg
    assert "--- Example 1 ---\nEXAMPLE-A" in user_msg
    assert "--- Example 2 ---\nEXAMPLE-B" in user_msg


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_generate_omits_optional_sections_when_empty(mock_router_cls, mock_settings):
    """No sample description and an explicit empty example list add no extra sections."""
    router = _configure(mock_settings, mock_router_cls, SKILL_MD)

    generate_skill("HALL", example_skills=[])

    user_msg = router.complete.call_args[0][0][1]["content"]
    assert "Sample context" not in user_msg
    assert "Example skills" not in user_msg


@patch("lab_harness.config.Settings.load")
@patch("lab_harness.llm.router.LLMRouter")
def test_generate_loads_first_two_skills_as_default_examples(mock_router_cls, mock_settings, tmp_path, monkeypatch):
    """With example_skills=None, the first two skills (sorted by name) are used as examples."""
    for name in ("c_skill", "a_skill", "b_skill"):
        (tmp_path / f"{name}.md").write_text(f"CONTENT-{name}")
    monkeypatch.setattr(generator, "SKILLS_DIR", tmp_path)
    router = _configure(mock_settings, mock_router_cls, SKILL_MD)

    generate_skill("HALL")

    user_msg = router.complete.call_args[0][0][1]["content"]
    assert "--- Example 1 ---\nCONTENT-a_skill" in user_msg
    assert "--- Example 2 ---\nCONTENT-b_skill" in user_msg
    assert "CONTENT-c_skill" not in user_msg


def test_save_skill_writes_lowercase_file_and_creates_dir(tmp_path, monkeypatch):
    """save_skill creates the skills directory and names the file after the lowercased type."""
    skills_dir = tmp_path / "skills"
    monkeypatch.setattr(generator, "SKILLS_DIR", skills_dir)

    path = save_skill("HALL", SKILL_MD)

    assert path == skills_dir / "hall.md"
    assert path.read_text() == SKILL_MD

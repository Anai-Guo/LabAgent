"""AI-powered contextual safety advisor."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SYSTEM_SAFETY = """\
You are a laboratory safety advisor for materials science and physics experiments.
When measurement parameters trigger safety warnings, provide:
1. WHY this limit exists (specific damage mechanism)
2. What could happen if exceeded (sample damage, instrument damage)
3. A safer alternative that still gets useful data
4. Whether the warning is critical or just cautionary

Be concise (under 100 words). Be specific to the material and measurement type.
Respond in plain text, not JSON.
"""


def advise_on_warnings(
    warnings: list[str],
    measurement_type: str,
    sample_description: str = "",
) -> str:
    """Generate context-aware safety advice for boundary warnings.

    Args:
        warnings: List of warning messages from boundary checker
        measurement_type: The measurement type
        sample_description: Optional sample info for context

    Returns:
        AI-generated safety advice string, or empty if LLM unavailable.
    """
    from lab_harness.config import Settings
    from lab_harness.llm.router import LLMRouter

    settings = Settings.load()
    if not (settings.model.api_key or settings.model.base_url):
        return ""

    router = LLMRouter(config=settings.model)

    user_msg = f"Measurement: {measurement_type}\n"
    if sample_description:
        user_msg += f"Sample: {sample_description}\n"
    user_msg += "Warnings triggered:\n" + "\n".join(f"- {w}" for w in warnings)

    response = router.complete(
        [
            {"role": "system", "content": SYSTEM_SAFETY},
            {"role": "user", "content": user_msg},
        ]
    )
    return response["choices"][0]["message"]["content"].strip()

"""AI-powered measurement parameter optimization."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_OPTIMIZE = """\
You are an expert in condensed matter physics transport measurements.
Given a measurement type and sample description, suggest optimal measurement parameters.

Consider:
- Material properties (thin film thickness, composition, expected resistance range)
- Instrument capabilities and typical operating ranges
- Signal-to-noise optimization (source current vs sample damage risk)
- Literature-typical ranges for this measurement type

Respond with JSON only:
{
  "suggested_overrides": {
    "x_axis": {"start": ..., "stop": ..., "step": ...},
    "max_current_a": ...,
    "settling_time_s": ...,
    "num_averages": ...
  },
  "reasoning": "brief explanation of why these values"
}
"""


def optimize_parameters(
    measurement_type: str,
    sample_description: str = "",
    current_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Use LLM to suggest optimal measurement parameters.

    Args:
        measurement_type: Type of measurement (AHE, MR, etc.)
        sample_description: Material/sample info (e.g. "10nm CoFeB/MgO")
        current_params: Current template parameters for context

    Returns:
        Dict with "suggested_overrides" and "reasoning" keys.
        Returns empty dict if LLM is unavailable.
    """
    from lab_harness.config import Settings
    from lab_harness.llm.router import LLMRouter

    settings = Settings.load()
    if not (settings.model.api_key or settings.model.base_url):
        return {}

    router = LLMRouter(config=settings.model)

    user_msg = f"Measurement: {measurement_type}\n"
    if sample_description:
        user_msg += f"Sample: {sample_description}\n"
    if current_params:
        user_msg += f"Current defaults:\n{json.dumps(current_params, indent=2)}\n"
    user_msg += "\nSuggest optimized parameters."

    response = router.complete(
        [
            {"role": "system", "content": SYSTEM_OPTIMIZE},
            {"role": "user", "content": user_msg},
        ]
    )
    content = response["choices"][0]["message"]["content"].strip()

    # Parse JSON from response (strip markdown fences if present)
    text = content
    if text.startswith("```"):
        text = text[text.index("\n") + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Could not parse optimizer response as JSON")
        return {"reasoning": content}

"""Learning engine - extracts reusable insights from experiment history."""

from __future__ import annotations

import logging

from lab_harness.memory.store import MemoryStore

logger = logging.getLogger(__name__)


def suggest_parameters_from_history(
    store: MemoryStore,
    measurement_type: str,
    sample: str = "",
    limit: int = 5,
) -> dict:
    """Query experiment history for successful parameters.

    Searches past experiments of the same type and extracts
    parameters that were used, to inform future measurements.

    Returns:
        Dict with "past_parameters" list and "suggestion" string.
    """
    experiments = store.get_by_type(measurement_type, limit=limit)
    if not experiments:
        return {"past_parameters": [], "suggestion": "No prior experiments found."}

    past_params = []
    for exp in experiments:
        if exp.parameters:
            past_params.append(
                {
                    "date": exp.timestamp[:10],
                    "sample": exp.sample,
                    "parameters": exp.parameters,
                    "notes": exp.notes[:100] if exp.notes else "",
                }
            )

    suggestion = f"Found {len(past_params)} prior {measurement_type} experiment(s). "
    if past_params:
        latest = past_params[0]
        suggestion += f"Most recent on {latest['date']} for '{latest['sample']}'."

    return {"past_parameters": past_params, "suggestion": suggestion}


def summarize_experiment_history(store: MemoryStore, limit: int = 20) -> str:
    """Generate a human-readable summary of recent experiments.

    Uses LLM if available, otherwise returns a simple listing.
    """
    experiments = store.get_recent(limit=limit)
    if not experiments:
        return "No experiments recorded yet."

    lines = [f"Experiment history ({len(experiments)} most recent):"]
    for exp in experiments:
        params_str = ""
        if exp.parameters:
            key_params = {k: v for k, v in list(exp.parameters.items())[:3]}
            params_str = f" | params: {key_params}"
        lines.append(f"  [{exp.timestamp[:10]}] {exp.measurement_type} on '{exp.sample}'{params_str}")
    return "\n".join(lines)

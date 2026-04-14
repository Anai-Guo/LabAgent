"""Test phased experiment flow emits events in correct order."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lab_harness.web.session_registry import SessionRegistry


@pytest.mark.asyncio
async def test_session_registry_works():
    """Basic sanity test for registry."""
    reg = SessionRegistry()
    live = reg.create()
    await live.emit("test", msg="hi")
    evt = live.events.get_nowait()
    assert evt["type"] == "test"
    assert evt["data"]["msg"] == "hi"


@pytest.mark.asyncio
async def test_phased_flow_emits_core_events():
    """The phased flow should emit discovery → decision → plan → measurement → done events."""
    from lab_harness.config import ModelConfig, Settings
    from lab_harness.orchestrator.flow import ExperimentFlow

    settings = Settings(model=ModelConfig())
    reg = SessionRegistry()
    live = reg.create()
    live.session.direction = "transport"
    live.session.material = "silicon"
    live.session.folder_confirmed = True  # auto-confirm for test

    with tempfile.TemporaryDirectory() as tmp:
        flow = ExperimentFlow(settings, data_root=Path(tmp))
        flow.session = live.session

        # Mock instrument scanning (runs in thread) and literature lookup
        with patch(
            "lab_harness.discovery.visa_scanner.scan_visa_instruments",
            return_value=[],
        ):
            # Point parent_dir inside the temp directory so nothing lands in the repo
            live.session.parent_dir = tmp
            await flow.run_phased(live)

    # Collect all emitted events
    events = []
    while not live.events.empty():
        events.append(live.events.get_nowait())

    event_types = [e["type"] for e in events]

    # Verify key phased events are present
    assert "decision.complete" in event_types
    assert "plan.complete" in event_types
    assert "measurement.start" in event_types
    assert "measurement.complete" in event_types
    assert "analysis.complete" in event_types
    assert "done" in event_types

    # Verify done is last
    assert event_types[-1] == "done"

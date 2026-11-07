"""Tests for the synchronous emit path and singleton of the web session registry."""

import asyncio
import logging

from lab_harness.web import session_registry
from lab_harness.web.session_registry import LiveSession, SessionRegistry, get_registry


def test_emit_sync_enqueues_event():
    live = SessionRegistry().create()
    live.emit_sync("phase.start", phase="plan", step=1)

    evt = live.events.get_nowait()
    assert evt["type"] == "phase.start"
    assert evt["data"] == {"phase": "plan", "step": 1}
    assert isinstance(evt["ts"], float)


def test_emit_sync_drops_event_when_queue_full(caplog):
    live = SessionRegistry().create()
    live.events = asyncio.Queue(maxsize=1)
    live.emit_sync("first")

    with caplog.at_level(logging.WARNING, logger="lab_harness.web.session_registry"):
        live.emit_sync("second")

    assert live.events.qsize() == 1
    assert live.events.get_nowait()["type"] == "first"
    assert "dropping second" in caplog.text


def test_live_session_defaults():
    live = SessionRegistry().create()
    assert live.done is False
    assert live.task is None
    assert live.completed_at is None
    assert live.created_at > 0
    assert isinstance(live, LiveSession)


def test_mark_done_sets_timestamp():
    reg = SessionRegistry()
    live = reg.create()
    reg.mark_done(live.session.session_id)
    assert live.done is True
    assert live.completed_at is not None
    assert live.completed_at >= live.created_at


def test_mark_done_and_delete_unknown_id_are_noops():
    reg = SessionRegistry()
    live = reg.create()
    reg.mark_done("missing")
    reg.delete("missing")
    assert reg.get(live.session.session_id) is live
    assert live.done is False


def test_cleanup_ignores_done_session_without_timestamp():
    reg = SessionRegistry(done_ttl_seconds=0)
    live = reg.create()
    live.done = True  # done but completed_at never recorded
    assert reg.cleanup() == 0
    assert reg.get(live.session.session_id) is live


def test_get_registry_returns_singleton(monkeypatch):
    monkeypatch.setattr(session_registry, "_registry", None)
    first = get_registry()
    second = get_registry()
    assert isinstance(first, SessionRegistry)
    assert first is second

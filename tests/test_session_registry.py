"""Tests for session registry."""

import asyncio

import pytest

from lab_harness.web.session_registry import SessionRegistry


@pytest.mark.asyncio
async def test_create_and_get():
    reg = SessionRegistry()
    live = reg.create()
    assert live.session.session_id
    retrieved = reg.get(live.session.session_id)
    assert retrieved is live


@pytest.mark.asyncio
async def test_emit_and_consume():
    reg = SessionRegistry()
    live = reg.create()
    await live.emit("test.event", key="value", count=42)
    evt = await asyncio.wait_for(live.events.get(), timeout=1.0)
    assert evt["type"] == "test.event"
    assert evt["data"]["key"] == "value"
    assert evt["data"]["count"] == 42
    assert "ts" in evt


def test_delete():
    reg = SessionRegistry()
    live = reg.create()
    sid = live.session.session_id
    reg.delete(sid)
    assert reg.get(sid) is None


def test_get_missing():
    reg = SessionRegistry()
    assert reg.get("nonexistent") is None

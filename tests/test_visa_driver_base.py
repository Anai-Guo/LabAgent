"""Tests for VisaDriver lifecycle, reconnect and health-check logic (no hardware)."""

from __future__ import annotations

import pytest

from lab_harness.drivers import base
from lab_harness.drivers.base import VisaDriver


class _FakeInstrument:
    """Stand-in for a pyvisa resource; optionally fails every call."""

    def __init__(self, reply: str = "FAKE,MODEL,1\n", fail: bool = False):
        self.reply = reply
        self.fail = fail
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.closed = False

    def query(self, command: str) -> str:
        if self.fail:
            raise ConnectionError("bus error")
        self.queries.append(command)
        return self.reply

    def write(self, command: str) -> None:
        if self.fail:
            raise ConnectionError("bus error")
        self.writes.append(command)

    def close(self) -> None:
        self.closed = True


class _StubDriver(VisaDriver):
    """VisaDriver whose connect() installs instruments from a queue instead of pyvisa."""

    def __init__(self, *instruments: _FakeInstrument, auto_reconnect: bool = True):
        super().__init__(resource="GPIB0::9::INSTR")
        self._queue = list(instruments)
        self.auto_reconnect = auto_reconnect
        self.connect_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1
        self._instrument = self._queue.pop(0)
        self._connected = True


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)


def test_context_manager_connects_and_disconnects():
    inst = _FakeInstrument()
    drv = _StubDriver(inst)
    with drv as entered:
        assert entered is drv
        assert drv.connected is True
    assert drv.connected is False
    assert inst.closed is True
    assert drv._instrument is None


def test_disconnect_swallows_close_error():
    inst = _FakeInstrument()
    inst.close = lambda: (_ for _ in ()).throw(RuntimeError("already closed"))
    drv = _StubDriver(inst)
    drv.connect()
    drv.disconnect()
    assert drv.connected is False
    assert drv._instrument is None


def test_identity_reset_and_read_float_delegate():
    inst = _FakeInstrument(reply=" 3.25 ")
    drv = _StubDriver(inst)
    drv.connect()
    assert drv.identity() == "3.25"
    assert drv.read_float(":READ?") == pytest.approx(3.25)
    drv.reset()
    assert inst.queries == ["*IDN?", ":READ?"]
    assert inst.writes == ["*RST"]


def test_query_reconnects_after_retries_exhausted():
    bad, good = _FakeInstrument(fail=True), _FakeInstrument(reply="OK\n")
    drv = _StubDriver(bad, good)
    drv.connect()
    assert drv.query("*OPC?") == "OK"
    assert bad.closed is True
    assert drv.connect_calls == 2
    assert drv._instrument is good


def test_query_raises_when_auto_reconnect_disabled():
    bad = _FakeInstrument(fail=True)
    drv = _StubDriver(bad, auto_reconnect=False)
    drv.connect()
    with pytest.raises(ConnectionError):
        drv.query("*OPC?")
    assert drv.connect_calls == 1
    assert bad.closed is False


def test_write_reconnects_after_retries_exhausted():
    bad, good = _FakeInstrument(fail=True), _FakeInstrument()
    drv = _StubDriver(bad, good)
    drv.connect()
    drv.write(":OUTP ON")
    assert good.writes == [":OUTP ON"]
    assert drv.connect_calls == 2


def test_write_raises_when_auto_reconnect_disabled():
    drv = _StubDriver(_FakeInstrument(fail=True), auto_reconnect=False)
    drv.connect()
    with pytest.raises(ConnectionError):
        drv.write(":OUTP ON")
    assert drv.connect_calls == 1


def test_is_connected_branches():
    inst = _FakeInstrument()
    drv = _StubDriver(inst)
    assert drv.is_connected() is False  # never connected
    drv.connect()
    assert drv.is_connected() is True
    assert inst.queries == ["*IDN?"]
    inst.fail = True
    assert drv.is_connected() is False
    assert drv.connected is False  # flag cleared on failure

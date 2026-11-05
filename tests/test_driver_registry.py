"""Tests for DriverRegistry config loading, driver dispatch and lifecycle."""

from __future__ import annotations

import pytest

from lab_harness.drivers import biologic_adapter, pymeasure_adapter, zurich_adapter
from lab_harness.drivers.keithley2400 import Keithley2400
from lab_harness.drivers.registry import DriverRegistry, _import_driver


class _FakeDriver:
    def __init__(self, fail_connect: bool = False, fail_disconnect: bool = False):
        self.fail_connect = fail_connect
        self.fail_disconnect = fail_disconnect
        self.connected = False
        self.disconnects = 0

    def connect(self) -> None:
        if self.fail_connect:
            raise RuntimeError("no instrument")
        self.connected = True

    def disconnect(self) -> None:
        self.disconnects += 1
        if self.fail_disconnect:
            raise RuntimeError("bus error")


def _recording_build(calls: list[dict]):
    def build(**kwargs):
        calls.append(kwargs)
        return _FakeDriver()

    return build


def test_from_yaml_reads_instruments_section(tmp_path):
    cfg = tmp_path / "instruments.yaml"
    cfg.write_text(
        "instruments:\n  source_meter:\n    driver: keithley2400\n    resource: GPIB0::24::INSTR\n",
        encoding="utf-8",
    )
    reg = DriverRegistry.from_yaml(cfg)
    assert reg.list_roles() == ["source_meter"]
    assert reg.supports_role("source_meter")
    assert not reg.supports_role("dmm")


def test_from_yaml_empty_file_gives_empty_registry(tmp_path):
    cfg = tmp_path / "empty.yaml"
    cfg.write_text("", encoding="utf-8")
    assert DriverRegistry.from_yaml(cfg).list_roles() == []


def test_import_driver_resolves_module_class_spec():
    assert _import_driver("lab_harness.drivers.keithley2400:Keithley2400") is Keithley2400


def test_get_driver_builtin_passes_settings_and_caches():
    reg = DriverRegistry(
        configs={"sm": {"driver": "keithley2400", "resource": "GPIB0::24::INSTR", "settings": {"compliance_v": 5.0}}}
    )
    drv = reg.get_driver("sm")
    assert isinstance(drv, Keithley2400)
    assert drv.resource == "GPIB0::24::INSTR"
    assert drv.compliance_v == 5.0
    assert reg.get_driver("sm") is drv


@pytest.mark.parametrize(
    ("sentinel", "module", "extra"),
    [
        ("__pymeasure__", pymeasure_adapter, {}),
        ("__zurich__", zurich_adapter, {"device_serial": "dev1234"}),
        ("__biologic__", biologic_adapter, {}),
    ],
)
def test_get_driver_adapter_sentinels_call_build(monkeypatch, sentinel, module, extra):
    calls: list[dict] = []
    monkeypatch.setattr(module, "build", _recording_build(calls))
    settings = {"model": "M1", "vendor": "V1", **extra}
    reg = DriverRegistry(configs={"r": {"driver": sentinel, "resource": "RES", "settings": settings}})
    reg.get_driver("r")
    assert calls == [{"resource": "RES", "model": "M1", "vendor": "V1", "role": "r", **extra}]


def test_get_driver_unknown_role_raises_key_error():
    with pytest.raises(KeyError, match="nope"):
        DriverRegistry().get_driver("nope")


def test_get_driver_unknown_driver_lists_available():
    reg = DriverRegistry(configs={"r": {"driver": "mystery", "resource": "RES"}})
    with pytest.raises(ValueError, match="__pymeasure__"):
        reg.get_driver("r")


def test_connect_all_skips_failing_instruments(monkeypatch):
    reg = DriverRegistry(configs={"ok": {}, "bad": {}})
    drivers = {"ok": _FakeDriver(), "bad": _FakeDriver(fail_connect=True)}
    monkeypatch.setattr(reg, "get_driver", lambda role: drivers[role])
    connected = reg.connect_all()
    assert connected == {"ok": drivers["ok"]}
    assert drivers["ok"].connected


def test_disconnect_all_tolerates_errors_and_clears_instances():
    reg = DriverRegistry()
    good, bad = _FakeDriver(), _FakeDriver(fail_disconnect=True)
    reg._instances.update({"bad": bad, "good": good})
    reg.disconnect_all()
    assert bad.disconnects == 1
    assert good.disconnects == 1
    assert reg._instances == {}

"""Tests for drivers/zurich_adapter.py.

zhinst-toolkit is an optional dep. These tests never import it — they
verify model dispatch, the unsupported-model guard, and the lazy-import
ImportError path.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lab_harness.drivers import zurich_adapter as zi


def test_is_supported_recognizes_mfli():
    assert zi.is_supported("Zurich Instruments MFLI")
    assert zi.is_supported("mfli")  # case insensitive
    assert zi.is_supported("HF2LI")
    assert zi.is_supported("SHFQA")


def test_is_supported_rejects_unknown():
    assert not zi.is_supported("Keithley 2400")
    assert not zi.is_supported("")


def test_build_rejects_unsupported_model():
    with pytest.raises(zi.UnsupportedZurichModelError):
        zi.build(resource="localhost", model="Keithley 2400")


def test_build_returns_unconnected_driver():
    drv = zi.build(resource="localhost", model="MFLI", device_serial="dev3000")
    assert isinstance(drv, zi.ZurichLockinDriver)
    assert drv.connected is False
    assert drv.device_serial == "dev3000"


def test_connect_raises_if_zhinst_missing():
    drv = zi.build(resource="localhost", model="MFLI")
    with patch.object(zi.importlib, "import_module", side_effect=ImportError("no zhinst")):
        with pytest.raises(zi.ZurichUnavailableError):
            drv.connect()


def test_connect_success_with_mocked_session():
    """When zhinst-toolkit imports cleanly, connect() builds Session+Device."""
    mock_toolkit = MagicMock()
    fake_device = MagicMock()
    mock_toolkit.Session.return_value.connect_device.return_value = fake_device

    drv = zi.build(resource="localhost", model="MFLI", device_serial="dev1234")
    with patch.object(zi.importlib, "import_module", return_value=mock_toolkit):
        drv.connect()

    assert drv.connected is True
    mock_toolkit.Session.assert_called_once_with("localhost")
    mock_toolkit.Session.return_value.connect_device.assert_called_once_with("dev1234")
    assert drv._device is fake_device


def test_disconnect_drops_references():
    drv = zi.build(resource="localhost", model="MFLI")
    drv._session = MagicMock()
    drv._device = MagicMock()
    drv._connected = True
    drv.disconnect()
    assert drv._session is None
    assert drv._device is None
    assert drv.connected is False


def test_lockin_operations_route_to_device_subsystems():
    """set_frequency / set_time_constant / read_xy must call the right zhinst paths."""
    drv = zi.build(resource="localhost", model="MFLI")
    # Wire up a fake device exposing the standard zhinst-toolkit tree.
    fake_device = MagicMock()
    drv._device = fake_device
    drv._connected = True

    drv.set_frequency(12345.0, oscillator=0)
    fake_device.oscs[0].freq.assert_called_once_with(12345.0)

    drv.set_time_constant(0.01, demod=0)
    fake_device.demods[0].timeconstant.assert_called_once_with(0.01)

    fake_device.demods[0].sample.return_value = {"x": 3.0, "y": 4.0}
    x, y = drv.read_xy(demod=0)
    assert x == 3.0 and y == 4.0

    r, theta = drv.read_r_theta(demod=0)
    assert r == pytest.approx(5.0)  # hypot(3,4) = 5
    assert theta == pytest.approx(53.13, abs=0.1)  # atan2(4,3) ≈ 53.13°


def test_operations_fail_when_not_connected():
    drv = zi.build(resource="localhost", model="MFLI")
    with pytest.raises(RuntimeError, match="not connected"):
        drv.set_frequency(1000.0)


def test_context_manager_round_trip():
    drv = zi.build(resource="localhost", model="MFLI")
    connect_calls, disconnect_calls = [], []
    drv.connect = lambda: connect_calls.append(1) or setattr(drv, "_connected", True)
    drv.disconnect = lambda: disconnect_calls.append(1) or setattr(drv, "_connected", False)
    with drv:
        assert drv.connected
    assert len(connect_calls) == 1 and len(disconnect_calls) == 1


def test_list_supported_models_has_entries():
    rows = zi.list_supported_models()
    assert len(rows) >= 3
    keys = {k for k, _ in rows}
    assert "MFLI" in keys

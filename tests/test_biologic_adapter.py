"""Tests for drivers/biologic_adapter.py.

easy-biologic is a Windows-only optional dep. These tests never import it
— they verify model dispatch, the unsupported-model guard, and the
lazy-import ImportError path.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lab_harness.drivers import biologic_adapter as biolo


def test_is_supported_recognizes_sp200():
    assert biolo.is_supported("BioLogic SP-200")
    assert biolo.is_supported("sp-200")
    assert biolo.is_supported("VMP3")
    assert biolo.is_supported("VSP")


def test_is_supported_rejects_unknown():
    assert not biolo.is_supported("Gamry Reference 600")
    assert not biolo.is_supported("")


def test_build_rejects_unsupported():
    with pytest.raises(biolo.UnsupportedBioLogicModelError):
        biolo.build(resource="10.0.0.1", model="Gamry Reference 600")


def test_build_returns_unconnected_driver():
    drv = biolo.build(resource="10.0.0.1", model="SP-200")
    assert isinstance(drv, biolo.BioLogicDriver)
    assert drv.connected is False


def test_connect_raises_if_easy_biologic_missing():
    drv = biolo.build(resource="10.0.0.1", model="SP-200")
    with patch.object(biolo.importlib, "import_module", side_effect=ImportError("no easy_biologic")):
        with pytest.raises(biolo.BioLogicUnavailableError):
            drv.connect()


def test_connect_success_with_mocked_library():
    """When easy_biologic imports cleanly, connect() builds a BiologicDevice."""
    mock_ebl = MagicMock()
    fake_device = MagicMock()
    mock_ebl.BiologicDevice.return_value = fake_device

    drv = biolo.build(resource="10.0.0.1", model="SP-200")
    with patch.object(biolo.importlib, "import_module", return_value=mock_ebl):
        drv.connect()

    assert drv.connected is True
    mock_ebl.BiologicDevice.assert_called_once_with("10.0.0.1")
    fake_device.connect.assert_called_once()


def test_disconnect_clears_device_reference():
    drv = biolo.build(resource="10.0.0.1", model="SP-200")
    drv._device = MagicMock()
    drv._connected = True
    drv.disconnect()
    assert drv._device is None
    assert drv.connected is False


def test_run_cv_calls_cv_technique_and_returns_points():
    """run_cv delegates to easy_biologic.programs.CV and parses the data."""

    def fake_import(name):
        if name == "easy_biologic":
            return MagicMock()  # imported but not used for data parsing
        if name == "easy_biologic.programs":
            m = MagicMock()
            # Fake technique that records .run() and exposes .data[0]
            fake_tech = MagicMock()
            fake_tech.data = {
                0: [
                    {"Ewe": -0.1, "I": 1e-7},
                    {"Ewe": 0.0, "I": 2e-7},
                    {"Ewe": 0.1, "I": 3e-7},
                ]
            }
            m.CV.return_value = fake_tech
            return m
        raise ImportError(name)

    drv = biolo.build(resource="10.0.0.1", model="SP-200")
    drv._connected = True
    drv._device = MagicMock()

    with patch.object(biolo.importlib, "import_module", side_effect=fake_import):
        points = drv.run_cv(
            e_start=-0.2,
            e_vertex=0.3,
            e_step=0.001,
            scan_rate_mv_per_s=100,
            n_cycles=1,
        )

    assert points == [(-0.1, 1e-7), (0.0, 2e-7), (0.1, 3e-7)]


def test_run_cv_requires_connection():
    drv = biolo.build(resource="10.0.0.1", model="SP-200")
    with pytest.raises(RuntimeError, match="not connected"):
        drv.run_cv(e_start=0, e_vertex=1)


def test_context_manager_round_trip():
    drv = biolo.build(resource="10.0.0.1", model="SP-200")
    connect_calls, disconnect_calls = [], []
    drv.connect = lambda: connect_calls.append(1) or setattr(drv, "_connected", True)
    drv.disconnect = lambda: disconnect_calls.append(1) or setattr(drv, "_connected", False)
    with drv:
        assert drv.connected
    assert connect_calls and disconnect_calls


def test_list_supported_models_has_all_entries():
    rows = biolo.list_supported_models()
    keys = {k for k, _ in rows}
    assert "SP-200" in keys
    assert "VMP3" in keys

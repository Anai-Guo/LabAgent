"""Tests for Lakeshore335.is_stable() and Lakeshore335.shutdown().

Uses a mocked PyVISA ResourceManager; no hardware is required.
"""

from unittest.mock import MagicMock, patch

import pytest

from lab_harness.drivers.lakeshore335 import Lakeshore335


def _connected_controller(responses):
    """Return a connected Lakeshore335 whose instrument answers queries from ``responses``."""
    mock_rm = MagicMock()
    mock_inst = MagicMock()
    mock_inst.query.side_effect = lambda cmd: responses[cmd]
    mock_rm.open_resource.return_value = mock_inst
    with patch("pyvisa.ResourceManager", return_value=mock_rm):
        ls = Lakeshore335(resource="GPIB0::10::INSTR")
        ls.connect()
    return ls, mock_inst


@pytest.mark.parametrize(
    ("temp", "setpoint", "expected"),
    [
        ("300.05", "300.0", True),
        ("299.96", "300.0", True),
        ("300.20", "300.0", False),
        ("299.50", "300.0", False),
    ],
)
def test_is_stable_compares_reading_with_setpoint(temp, setpoint, expected):
    ls, mock_inst = _connected_controller({"KRDG? A": temp, "SETP? 1": setpoint})

    assert ls.is_stable("A", tolerance_k=0.1) is expected
    queried = [c.args[0] for c in mock_inst.query.call_args_list]
    assert queried == ["KRDG? A", "SETP? 1"]


def test_is_stable_uses_requested_channel_and_tolerance():
    ls, mock_inst = _connected_controller({"KRDG? B": "10.4", "SETP? 1": "10.0"})

    assert ls.is_stable("B", tolerance_k=0.5) is True
    assert ls.is_stable("B", tolerance_k=0.3) is False
    assert mock_inst.query.call_args_list[0].args[0] == "KRDG? B"


def test_is_stable_boundary_is_exclusive():
    ls, _ = _connected_controller({"KRDG? A": "4.5", "SETP? 1": "4.0"})

    assert ls.is_stable("A", tolerance_k=0.5) is False


def test_shutdown_turns_heater_off_then_disconnects():
    ls, mock_inst = _connected_controller({})

    ls.shutdown()

    mock_inst.write.assert_called_once_with("RANGE 1,0")
    mock_inst.close.assert_called_once()
    assert ls.connected is False


def test_shutdown_still_disconnects_when_heater_command_fails():
    ls, mock_inst = _connected_controller({})

    with patch.object(Lakeshore335, "set_heater_range", side_effect=RuntimeError("bus error")) as heater:
        ls.shutdown()

    heater.assert_called_once_with(0)
    mock_inst.close.assert_called_once()
    assert ls.connected is False

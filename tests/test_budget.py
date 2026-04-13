"""Tests for the iteration budget system."""
from __future__ import annotations

import logging

import pytest

from lab_harness.agent.budget import Budget


class TestBudget:
    def test_budget_tick(self):
        """tick increments counter and returns True when under limit."""
        b = Budget(max_iterations=10)
        assert b.current == 0
        result = b.tick()
        assert result is True
        assert b.current == 1

    def test_budget_exhausted(self):
        """Returns False when budget is used up."""
        b = Budget(max_iterations=3)
        assert b.tick() is True   # 1/3
        assert b.tick() is True   # 2/3
        assert b.tick() is False  # 3/3 -> exhausted
        assert b.exhausted is True

    def test_budget_remaining(self):
        """remaining property is correct after ticks."""
        b = Budget(max_iterations=5)
        assert b.remaining == 5
        b.tick()
        assert b.remaining == 4
        # Exhaust fully
        for _ in range(4):
            b.tick()
        assert b.remaining == 0

    def test_budget_remaining_never_negative(self):
        """remaining stays at 0 even if tick called past exhaustion."""
        b = Budget(max_iterations=1)
        b.tick()
        b.tick()  # past limit
        assert b.remaining == 0

    def test_budget_70_warning(self, caplog: pytest.LogCaptureFixture):
        """Logs warning at 70% usage."""
        b = Budget(max_iterations=10)
        with caplog.at_level(logging.WARNING, logger="lab_harness.agent.budget"):
            for _ in range(7):
                b.tick()
        assert any("70%" in msg for msg in caplog.messages)

    def test_budget_90_warning(self, caplog: pytest.LogCaptureFixture):
        """Logs warning at 90% usage."""
        b = Budget(max_iterations=10)
        with caplog.at_level(logging.WARNING, logger="lab_harness.agent.budget"):
            for _ in range(9):
                b.tick()
        assert any("90%" in msg for msg in caplog.messages)

    def test_warnings_fire_only_once(self, caplog: pytest.LogCaptureFixture):
        """Each threshold warning fires at most once."""
        b = Budget(max_iterations=10)
        with caplog.at_level(logging.WARNING, logger="lab_harness.agent.budget"):
            for _ in range(10):
                b.tick()
        warn_70 = [m for m in caplog.messages if "70%" in m]
        warn_90 = [m for m in caplog.messages if "90%" in m]
        assert len(warn_70) == 1
        assert len(warn_90) == 1

    def test_exhausted_property(self):
        """exhausted is False before limit, True at or after."""
        b = Budget(max_iterations=2)
        assert b.exhausted is False
        b.tick()
        assert b.exhausted is False
        b.tick()
        assert b.exhausted is True

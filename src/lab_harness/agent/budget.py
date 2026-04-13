"""Iteration budget management for agent loops."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Budget:
    """Tracks iteration count with progressive warnings."""

    max_iterations: int = 50
    current: int = 0
    _warned_70: bool = False
    _warned_90: bool = False

    def tick(self) -> bool:
        """Increment counter. Returns False if budget exhausted."""
        self.current += 1
        pct = self.current / self.max_iterations
        if pct >= 0.9 and not self._warned_90:
            logger.warning("Budget 90%% used (%d/%d)", self.current, self.max_iterations)
            self._warned_90 = True
        elif pct >= 0.7 and not self._warned_70:
            logger.warning("Budget 70%% used (%d/%d)", self.current, self.max_iterations)
            self._warned_70 = True
        return self.current < self.max_iterations

    @property
    def exhausted(self) -> bool:
        return self.current >= self.max_iterations

    @property
    def remaining(self) -> int:
        return max(0, self.max_iterations - self.current)

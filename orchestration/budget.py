"""Per-run model-call budget: decrement and refuse beyond the configured max (NFR-OPS-001).

One `RunBudget` lives for one streamed run (never across requests). Every graph node consumes
exactly one unit *before* its model call; a node that cannot consume fails honestly instead.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


class BudgetExceededError(RuntimeError):
    """The run has no model calls left (`BudgetExceeded`)."""


@dataclass
class RunBudget:
    max_calls: int
    used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def consume(self) -> None:
        """Reserve one model call or raise `BudgetExceededError`."""
        with self._lock:
            if self.used >= self.max_calls:
                raise BudgetExceededError("The run's model-call budget is exhausted.")
            self.used += 1

    def snapshot(self) -> dict[str, int]:
        """The contract `budget` payload: `{max, used}`."""
        with self._lock:
            return {"max": self.max_calls, "used": self.used}


__all__ = ["BudgetExceededError", "RunBudget"]

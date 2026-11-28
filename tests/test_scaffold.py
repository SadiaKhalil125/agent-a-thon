"""Smoke test: the package skeleton imports cleanly.

Replaced/extended by real suites in TASK-006 (solver), TASK-010 (run steps),
TASK-021 (security).
"""

from __future__ import annotations

import importlib


def test_packages_import() -> None:
    for pkg in (
        "twin",
        "twin.model",
        "twin.seed",
        "twin.solver",
        "agents",
        "agents.llm",
        "agents.nodes",
        "agents.roles",
        "orchestration",
        "orchestration.state",
        "orchestration.graph",
        "orchestration.budget",
        "api",
        "api.state",
        "api.run",
        "api.execute",
    ):
        assert importlib.import_module(pkg) is not None

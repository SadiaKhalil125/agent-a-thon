"""Build the LangGraph StateGraph: register the role nodes, wire the edges
(incl. the one-time Verifier -> Planner conditional edge) and enforce the
per-run node/call budget.

Filled in TASK-009/013.
"""

from __future__ import annotations

__all__: list[str] = []

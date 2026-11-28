"""LangGraph node functions for the six core roles: Impact, HR/Resource,
Finance, Planner, Verifier, Execution.

Filled in TASK-010/011/012/013/014. Each node builds its prompt (roles.py) from
the graph State + solver facts, invokes the chat model (llm.py), and parses the
judgment/narrative + chosen option. Nodes NEVER compute numbers (twin.solver does).
"""

from __future__ import annotations

__all__: list[str] = []

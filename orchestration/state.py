"""LangGraph graph State and the per-run context (TASK-009).

State lives in memory for one streamed run only (NFR-REL-001). Nothing here is shared between
requests. The `RunContext` carries the twin, the model and the budget into nodes through the
LangGraph `config`, so the compiled graph itself holds no per-run data.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel

from orchestration.budget import RunBudget
from twin.model import Twin

MAX_REVISIONS = 1  # the Verifier -> Planner loop runs at most once (rules section 3)


def merge_outputs(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Reducer so parallel nodes can each contribute their own entry."""
    return {**(left or {}), **(right or {})}


class RunState(TypedDict, total=False):
    runId: str
    presetId: str
    outputs: Annotated[dict[str, Any], merge_outputs]  # node id -> that node's latest output
    failed: Annotated[bool, operator.or_]  # a node failed honestly: stop, send no `done`
    plans: tuple[Any, ...]  # plans under review (twin.results.Plan)
    recommendedPlanId: str | None
    rejectedPlanIds: tuple[str, ...]
    objection: str | None  # the Verifier's reason, handed to the revising Planner
    revisions: int
    verdict: dict[str, Any] | None
    finalPlans: tuple[Any, ...]  # every plan with its final status, for `done`


@dataclass(frozen=True)
class RunContext:
    run_id: str
    preset_id: str
    twin: Twin
    model: BaseChatModel
    budget: RunBudget


__all__ = ["MAX_REVISIONS", "RunContext", "RunState", "merge_outputs"]

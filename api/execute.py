"""POST /api/execute (approval-gated), POST /api/outcome and POST /api/reset (TASK-014).

The human approval gate is enforced here, server-side, as a request boundary: nothing is applied
unless the caller names a specific plan (`approvedPlanId`) that is valid for the preset and passes
the engine's independent feasibility check. A plan the Verifier rejected can never be approved.

These endpoints are self-contained and stateless (no server memory between requests, no model call,
no outbound network): the result is a pure function of `(presetId, approvedPlanId)`, so executing
the same plan twice returns the same twin and a reset just returns the seed.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.errors import ApiError
from api.event import AnyEvent, twin_for
from api.state import StateResponse, build_state
from twin import solver
from twin.model import Twin
from twin.results import AppliedState, Plan
from twin.seed import get_twin

router = APIRouter()

MAX_TWIN_SEGMENTS = 50  # a real applied schedule has a handful of segments

_Id = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")]


class ApprovalRequest(BaseModel):
    presetId: _Id
    approvedPlanId: _Id
    event: AnyEvent | None = None  # set when the plan belongs to a typed event


class OutcomeRequest(ApprovalRequest):
    # Optional: the applied twin the client holds (from `/api/execute`). Only its schedule is
    # trusted; everything else is re-derived, so a tampered twin shows up as a mismatch.
    twin: AppliedState | None = None


def approved_plan(twin: Twin, preset_id: str, plan_id: str) -> Plan:
    """The approval gate: a known plan for this preset that the engine finds feasible."""
    try:
        plan = solver.find_plan(twin, preset_id, plan_id)
    except KeyError:  # unknown preset or plan id
        raise ApiError(400, "ValidationError", "Unknown presetId or approvedPlanId.") from None
    if solver.plan_conflicts(twin, preset_id, plan):
        raise ApiError(
            409,
            "PlanRejected",
            "This plan was rejected by the verifier and cannot be approved.",
        )
    return plan


def _check_schedule(twin: Twin, applied: AppliedState) -> None:
    """Refuse a client-supplied twin that references things the company does not have."""
    if len(applied.schedule) > MAX_TWIN_SEGMENTS:
        raise ApiError(400, "ValidationError", "The supplied twin is not valid.")
    task_ids = {t.id for t in twin.tasks}
    person_ids = {p.id for p in twin.people}
    for seg in applied.schedule:
        if (
            seg.taskId not in task_ids
            or seg.personId not in person_ids
            or not 1 <= seg.startDay <= seg.endDay <= twin.horizonDays
        ):
            raise ApiError(400, "ValidationError", "The supplied twin is not valid.")


@router.post("/api/execute")
def execute(req: ApprovalRequest) -> dict[str, Any]:
    twin = twin_for(req.presetId, req.event)
    plan = approved_plan(twin, req.presetId, req.approvedPlanId)
    applied = solver.apply_plan(twin, req.presetId, plan.id)
    return {"applied": True, "twin": applied.model_dump(mode="json")}


@router.post("/api/outcome")
def outcome(req: OutcomeRequest) -> dict[str, Any]:
    twin = twin_for(req.presetId, req.event)
    plan = approved_plan(twin, req.presetId, req.approvedPlanId)
    if req.twin is not None:
        _check_schedule(solver.effective_twin(twin, req.presetId), req.twin)
    check = solver.verify_outcome(twin, req.presetId, plan.id, req.twin)
    return check.model_dump(mode="json")


@router.post("/api/reset", response_model=StateResponse)
def reset() -> StateResponse:
    """Back to the seeded initial state (same shape as `GET /api/state`); nothing to undo."""
    return build_state(get_twin())


__all__ = ["approved_plan", "router"]

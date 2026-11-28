"""GET /api/state: the seeded initial twin (read-only facts), per docs/contracts.md (TASK-A3).

The response is built only from the validated seed and the solver's dependency chain; nothing
here calls a model and nothing is taken from the client.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from twin import solver
from twin.model import (
    Budget,
    ChainNode,
    Commitment,
    Company,
    ContractorOption,
    DayWindow,
    DemandEvent,
    Invoice,
    Milestone,
    PresetSource,
    Project,
    Twin,
    Unavailability,
)
from twin.seed import get_twin

router = APIRouter()


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskOut(_Out):
    id: str
    projectId: str
    name: str
    type: str
    days: int
    dependsOn: list[str]
    requiredSkill: str


class AssignmentOut(_Out):
    taskId: str
    startDay: int
    endDay: int


class PersonOut(_Out):
    id: str
    name: str
    role: str
    kind: str
    skills: list[str]
    availability: list[DayWindow]
    assignments: list[AssignmentOut]


class DemandOut(_Out):
    """New client work from a meeting, summarised for display (the solver holds the full detail)."""

    taskId: str
    taskName: str
    days: int
    requiredSkill: str
    defaultAssigneeId: str
    customerId: str
    dueDay: int
    commitment: str
    invoiceAmount: int
    currency: str


class PresetEvent(_Out):
    unavailable: list[Unavailability]
    demand: DemandOut | None = None  # additive: only client-meeting scenarios carry it


class PresetOut(_Out):
    id: str
    label: str
    description: str
    event: PresetEvent
    source: PresetSource


class StateResponse(_Out):
    company: Company
    horizonDays: int
    customers: list[dict[str, str]]
    projects: list[Project]
    tasks: list[TaskOut]
    people: list[PersonOut]
    milestones: list[Milestone]
    commitments: list[Commitment]
    invoices: list[Invoice]
    budget: Budget
    contractor: ContractorOption
    chain: list[ChainNode]
    presets: list[PresetOut]


def _demand_out(demand: DemandEvent | None) -> DemandOut | None:
    if demand is None:
        return None
    return DemandOut(
        taskId=demand.task.id,
        taskName=demand.task.name,
        days=demand.task.days,
        requiredSkill=demand.task.requiredSkill,
        defaultAssigneeId=demand.task.defaultAssigneeId,
        customerId=demand.project.customerId,
        dueDay=demand.milestone.dueDay,
        commitment=demand.commitment.description,
        invoiceAmount=demand.invoice.amount,
        currency=demand.invoice.currency,
    )


def build_state(twin: Twin) -> StateResponse:
    """The initial-state view of the twin. `chain` is the impact chain of the primary preset."""
    primary = twin.presets[0]
    return StateResponse(
        company=twin.company,
        horizonDays=twin.horizonDays,
        customers=[{"id": c.id, "name": c.name} for c in twin.customers],
        projects=list(twin.projects),
        tasks=[
            TaskOut(
                id=t.id,
                projectId=t.projectId,
                name=t.name,
                type=t.type,
                days=t.days,
                dependsOn=list(t.dependsOn),
                requiredSkill=t.requiredSkill,
            )
            for t in twin.tasks
        ],
        people=[
            PersonOut(
                id=p.id,
                name=p.name,
                role=p.role,
                kind=p.kind,
                skills=list(p.skills),
                availability=list(p.availability),
                assignments=[
                    AssignmentOut(taskId=a.taskId, startDay=a.startDay, endDay=a.endDay)
                    for a in twin.assignments
                    if a.personId == p.id
                ],
            )
            for p in twin.people
        ],
        milestones=list(twin.milestones),
        commitments=list(twin.commitments),
        invoices=list(twin.invoices),
        budget=twin.budget,
        contractor=twin.contractor,
        chain=list(solver.impact_report(twin, primary.id).chain),
        presets=[
            PresetOut(
                id=p.id,
                label=p.label,
                description=p.description,
                event=PresetEvent(
                    unavailable=list(p.event.unavailable),
                    demand=_demand_out(p.event.demand),
                ),
                source=p.source,
            )
            for p in twin.presets
        ],
    )


@router.get("/api/state", response_model=StateResponse)
def get_state() -> StateResponse:
    return build_state(get_twin())


__all__ = ["StateResponse", "build_state", "router"]

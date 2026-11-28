"""Twin domain entities and dependency graph (TASK-005).

Pure data and graph traversal. No I/O, no model calls and no numbers beyond what is
stored in the seed: scheduling, completion, cost and eligibility live in `twin.solver`.

Day numbers are working-day integers (day 1 is the first working day).
"""

from __future__ import annotations

from collections import deque
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ChainNodeType = Literal["task", "milestone", "commitment", "invoice"]


class _HasId(Protocol):
    @property
    def id(self) -> str: ...


_T = TypeVar("_T", bound=_HasId)


class _Frozen(BaseModel):
    """Base for immutable seed entities; unknown fields are rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Company(_Frozen):
    id: str
    name: str
    description: str


class SourceRef(_Frozen):
    """Where this record lives in a (simulated) enterprise system, e.g. hris / HR-1001."""

    system: Literal["hris", "tracker", "erp", "crm", "calendar"]
    externalId: str = Field(min_length=1)


class Customer(_Frozen):
    id: str
    name: str
    source: SourceRef | None = None


class Project(_Frozen):
    id: str
    name: str
    customerId: str


class DayWindow(_Frozen):
    """Inclusive range of working days."""

    startDay: int = Field(ge=1)
    endDay: int = Field(ge=1)

    def contains(self, day: int) -> bool:
        return self.startDay <= day <= self.endDay

    def days(self) -> range:
        return range(self.startDay, self.endDay + 1)


class Person(_Frozen):
    id: str
    name: str
    role: str
    kind: Literal["employee", "contractor"]
    skills: tuple[str, ...]
    availability: tuple[DayWindow, ...]
    source: SourceRef | None = None

    def is_available(self, day: int) -> bool:
        return any(window.contains(day) for window in self.availability)


class Task(_Frozen):
    id: str
    projectId: str
    name: str
    type: Literal["integration", "qa"]
    days: int = Field(ge=1)
    dependsOn: tuple[str, ...]
    requiredSkill: str
    defaultAssigneeId: str
    source: SourceRef | None = None


class Assignment(_Frozen):
    """A fixed, pre-existing booking of a person on a task for specific days."""

    taskId: str
    personId: str
    startDay: int = Field(ge=1)
    endDay: int = Field(ge=1)

    def days(self) -> range:
        return range(self.startDay, self.endDay + 1)


class Milestone(_Frozen):
    id: str
    projectId: str
    name: str
    dueDay: int = Field(ge=1)
    gatedByTaskIds: tuple[str, ...]


class Commitment(_Frozen):
    id: str
    customerId: str
    milestoneId: str
    description: str
    source: SourceRef | None = None


class Invoice(_Frozen):
    id: str
    milestoneId: str
    amount: int = Field(ge=0)
    currency: str
    description: str
    source: SourceRef | None = None


class Budget(_Frozen):
    recoveryBudget: int = Field(ge=0)
    currency: str


class ContractorOption(_Frozen):
    personId: str
    fixedCost: int = Field(ge=0)
    currency: str


class Unavailability(_Frozen):
    personId: str
    startDay: int = Field(ge=1)
    endDay: int = Field(ge=1)


class DemandEvent(_Frozen):
    """New client work agreed in a business meeting and logged in the CRM.

    Business Development records the outcome; Sales (the value), HR (the capacity) and Finance
    (the invoice) then work from the same record. It carries the new project, task, milestone,
    commitment and invoice so the solver can test whether the company can accept it.
    """

    project: Project
    task: Task
    milestone: Milestone
    commitment: Commitment
    invoice: Invoice


class DisruptionEvent(_Frozen):
    """What happens to the company: people become unavailable and/or the client asks for more."""

    unavailable: tuple[Unavailability, ...] = ()
    demand: DemandEvent | None = None


class PresetSource(_Frozen):
    """The simulated enterprise system the event arrives from (docs/contracts.md section 3)."""

    system: str
    eventType: str
    payload: dict[str, object]


class Preset(_Frozen):
    id: str
    label: str
    description: str
    event: DisruptionEvent
    source: PresetSource


class ChainNode(_Frozen):
    id: str
    type: ChainNodeType
    label: str


class Twin(_Frozen):
    """The whole fictional company as loaded from `data/seed/northstar.json`."""

    company: Company
    horizonDays: int = Field(ge=1)
    customers: tuple[Customer, ...]
    projects: tuple[Project, ...]
    people: tuple[Person, ...]
    tasks: tuple[Task, ...]
    assignments: tuple[Assignment, ...]
    milestones: tuple[Milestone, ...]
    commitments: tuple[Commitment, ...]
    invoices: tuple[Invoice, ...]
    budget: Budget
    contractor: ContractorOption
    presets: tuple[Preset, ...]

    # ---- lookups -------------------------------------------------------------------

    def person(self, person_id: str) -> Person:
        return _find(self.people, person_id, "person")

    def task(self, task_id: str) -> Task:
        return _find(self.tasks, task_id, "task")

    def project(self, project_id: str) -> Project:
        return _find(self.projects, project_id, "project")

    def customer(self, customer_id: str) -> Customer:
        return _find(self.customers, customer_id, "customer")

    def milestone(self, milestone_id: str) -> Milestone:
        return _find(self.milestones, milestone_id, "milestone")

    def preset(self, preset_id: str) -> Preset:
        return _find(self.presets, preset_id, "preset")

    def with_demand(self, demand: DemandEvent) -> Twin:
        """This company plus the new client work (idempotent: merging twice changes nothing)."""
        if demand.task in self.tasks:  # the very same task: already merged. A clash still merges
            return self  # so seed validation reports the duplicate id
        return self.model_copy(
            update={
                "projects": (*self.projects, demand.project),
                "tasks": (*self.tasks, demand.task),
                "milestones": (*self.milestones, demand.milestone),
                "commitments": (*self.commitments, demand.commitment),
                "invoices": (*self.invoices, demand.invoice),
            }
        )

    # ---- dependency graph ----------------------------------------------------------

    def dependent_tasks(self, task_id: str) -> tuple[Task, ...]:
        """Tasks that directly depend on `task_id`."""
        return tuple(t for t in self.tasks if task_id in t.dependsOn)

    def downstream_tasks(self, task_id: str) -> tuple[Task, ...]:
        """All tasks transitively depending on `task_id`, breadth-first, without duplicates."""
        seen: set[str] = {task_id}
        ordered: list[Task] = []
        queue: deque[str] = deque([task_id])
        while queue:
            current = queue.popleft()
            for dependent in self.dependent_tasks(current):
                if dependent.id not in seen:
                    seen.add(dependent.id)
                    ordered.append(dependent)
                    queue.append(dependent.id)
        return tuple(ordered)

    def milestones_gated_by(self, task_ids: set[str]) -> tuple[Milestone, ...]:
        return tuple(m for m in self.milestones if task_ids.intersection(m.gatedByTaskIds))

    def commitments_for(self, milestone_id: str) -> tuple[Commitment, ...]:
        return tuple(c for c in self.commitments if c.milestoneId == milestone_id)

    def invoices_for(self, milestone_id: str) -> tuple[Invoice, ...]:
        return tuple(i for i in self.invoices if i.milestoneId == milestone_id)

    def dependency_chain(self, task_id: str) -> tuple[ChainNode, ...]:
        """Ordered impact chain starting at `task_id`.

        Structure only (no numbers): the task, its downstream tasks, the milestones those
        tasks gate, the customer commitments on those milestones and the invoices gated by
        them. For the primary scenario: integration -> QA -> milestone -> commitment -> invoice.
        """
        start = self.task(task_id)
        tasks = (start, *self.downstream_tasks(task_id))
        nodes: list[ChainNode] = [ChainNode(id=t.id, type="task", label=t.name) for t in tasks]

        milestones = self.milestones_gated_by({t.id for t in tasks})
        nodes.extend(ChainNode(id=m.id, type="milestone", label=m.name) for m in milestones)
        for milestone in milestones:
            for commitment in self.commitments_for(milestone.id):
                customer = self.customer(commitment.customerId)
                nodes.append(
                    ChainNode(
                        id=commitment.id,
                        type="commitment",
                        label=f"{customer.name}: {commitment.description}",
                    )
                )
            for invoice in self.invoices_for(milestone.id):
                nodes.append(
                    ChainNode(
                        id=invoice.id,
                        type="invoice",
                        label=f"{invoice.id}: {invoice.amount} {invoice.currency}",
                    )
                )
        return tuple(nodes)


def _find(items: tuple[_T, ...], item_id: str, kind: str) -> _T:
    for item in items:
        if item.id == item_id:
            return item
    raise KeyError(f"unknown {kind} id: {item_id}")


__all__ = [
    "Assignment",
    "Budget",
    "ChainNode",
    "Commitment",
    "Company",
    "ContractorOption",
    "Customer",
    "DayWindow",
    "DemandEvent",
    "DisruptionEvent",
    "Invoice",
    "Milestone",
    "Person",
    "Preset",
    "SourceRef",
    "PresetSource",
    "Project",
    "Task",
    "Twin",
    "Unavailability",
]

"""Result shapes produced by `twin.solver` (TASK-006/007).

These mirror docs/contracts.md (`Plan`, derived facts, outcome). They are plain immutable data:
the solver is the only code that fills them in, and agents/nodes only narrate them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from twin.model import ChainNode

FactTag = Literal["fact", "calculated", "estimate"]
PlanStatus = Literal["proposed", "rejected", "revised", "verified"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Segment(_Frozen):
    """One contiguous block of working days a person spends on a task (Gantt bar)."""

    taskId: str
    personId: str
    startDay: int
    endDay: int


class DeadlineResult(_Frozen):
    name: str
    dueDay: int
    met: bool


class Plan(_Frozen):
    id: str
    name: str
    summary: str
    status: PlanStatus
    revisesPlanId: str | None = None
    projectCompletion: dict[str, int | None]
    deadlines: tuple[DeadlineResult, ...]
    incrementalCost: int
    budgetFit: bool
    invoiceEligible: bool
    violatedConstraints: tuple[str, ...]
    schedule: tuple[Segment, ...]


class DerivedFact(_Frozen):
    label: str
    value: str
    tag: FactTag


class MilestoneSlip(_Frozen):
    milestoneId: str
    name: str
    dueDay: int
    baselineDay: int | None
    disruptedDay: int | None
    daysLate: int
    met: bool


class InvoiceExposure(_Frozen):
    invoiceId: str
    amount: int
    currency: str
    milestoneId: str
    eligibleOnTime: bool


class ImpactReport(_Frozen):
    presetId: str
    affectedTaskIds: tuple[str, ...]
    chain: tuple[ChainNode, ...]
    slips: tuple[MilestoneSlip, ...]
    commitmentsAtRisk: tuple[str, ...]
    invoices: tuple[InvoiceExposure, ...]
    invoiceAtRisk: int
    recoveryBudget: int
    contractorCost: int
    facts: tuple[DerivedFact, ...]


class PersonCapacity(_Frozen):
    personId: str
    name: str
    kind: Literal["employee", "contractor"]
    freeDays: tuple[int, ...]
    bookedDays: tuple[int, ...]
    unavailableDays: tuple[int, ...]
    note: str


class ResourceReport(_Frozen):
    presetId: str
    requiredSkill: str
    windowEndDay: int
    candidates: tuple[PersonCapacity, ...]
    facts: tuple[DerivedFact, ...]


class PlanFinance(_Frozen):
    planId: str
    incrementalCost: int
    budgetFit: bool
    invoiceEligible: bool
    invoiceAtRisk: int


class FinanceReport(_Frozen):
    presetId: str
    recoveryBudget: int
    invoiceAmount: int
    plans: tuple[PlanFinance, ...]
    facts: tuple[DerivedFact, ...]


class AppliedMilestone(_Frozen):
    milestoneId: str
    dueDay: int
    completionDay: int | None
    met: bool


class AppliedState(_Frozen):
    """The working twin after an approved plan is applied (contract: `twin` in /api/execute)."""

    presetId: str
    planId: str
    schedule: tuple[Segment, ...]
    projectCompletion: dict[str, int | None]
    milestones: tuple[AppliedMilestone, ...]
    invoiceEligible: bool
    incrementalCost: int
    budgetRemaining: int
    conflicts: tuple[str, ...]


class Delta(_Frozen):
    field: str
    expected: str
    actual: str


class OutcomeCheck(_Frozen):
    match: bool
    expected: dict[str, object]
    actual: dict[str, object]
    deltas: tuple[Delta, ...]


__all__ = [
    "AppliedMilestone",
    "AppliedState",
    "DeadlineResult",
    "Delta",
    "DerivedFact",
    "FactTag",
    "FinanceReport",
    "ImpactReport",
    "InvoiceExposure",
    "MilestoneSlip",
    "OutcomeCheck",
    "PersonCapacity",
    "Plan",
    "PlanFinance",
    "PlanStatus",
    "ResourceReport",
    "Segment",
]

"""Load and validate data/seed/northstar.json into the twin model (TASK-004).

The seed is the single source of hard facts (read-only, committed, fabricated). Validation is
strict so every downstream number can trust the data: every invoice links to a milestone, every
milestone is gated by at least one task, dependencies are acyclic and availability windows are
well formed.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from twin.model import DayWindow, DemandEvent, Twin

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed" / "northstar.json"


class SeedValidationError(ValueError):
    """The seed is malformed or internally inconsistent. `problems` lists every issue found."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def load_seed(path: Path | None = None) -> Twin:
    """Read, parse and validate a seed file; raise `SeedValidationError` on any problem."""
    return parse_seed(json.loads((path or SEED_PATH).read_text(encoding="utf-8")))


def parse_seed(data: dict[str, Any]) -> Twin:
    """Build and validate a `Twin` from an already-parsed seed document."""
    try:
        twin = Twin.model_validate(data)
    except ValidationError as exc:
        problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise SeedValidationError(problems) from exc
    validate_twin(twin)
    return twin


@lru_cache(maxsize=1)
def get_twin() -> Twin:
    """The committed seed, loaded once per process (the model is immutable, so sharing is safe)."""
    return load_seed()


def validate_twin(twin: Twin) -> None:
    """Cross-entity consistency checks. Raises `SeedValidationError` listing all problems."""
    problems: list[str] = []

    for name, ids in (
        ("customers", [c.id for c in twin.customers]),
        ("projects", [p.id for p in twin.projects]),
        ("people", [p.id for p in twin.people]),
        ("tasks", [t.id for t in twin.tasks]),
        ("milestones", [m.id for m in twin.milestones]),
        ("commitments", [c.id for c in twin.commitments]),
        ("invoices", [i.id for i in twin.invoices]),
        ("presets", [p.id for p in twin.presets]),
    ):
        problems.extend(_duplicates(name, ids))

    customer_ids = {c.id for c in twin.customers}
    project_ids = {p.id for p in twin.projects}
    person_ids = {p.id for p in twin.people}
    task_ids = {t.id for t in twin.tasks}
    milestone_ids = {m.id for m in twin.milestones}
    horizon = twin.horizonDays

    for project in twin.projects:
        if project.customerId not in customer_ids:
            problems.append(f"project {project.id}: unknown customer {project.customerId}")

    for person in twin.people:
        problems.extend(_check_windows(f"person {person.id} availability", person.availability))
        for window in person.availability:
            if window.endDay > horizon:
                problems.append(f"person {person.id}: availability beyond horizon {horizon}")

    people_by_id = {p.id: p for p in twin.people}
    for task in twin.tasks:
        if task.projectId not in project_ids:
            problems.append(f"task {task.id}: unknown project {task.projectId}")
        for dep in task.dependsOn:
            if dep not in task_ids:
                problems.append(f"task {task.id}: unknown dependency {dep}")
            if dep == task.id:
                problems.append(f"task {task.id}: depends on itself")
        assignee = people_by_id.get(task.defaultAssigneeId)
        if assignee is None:
            problems.append(f"task {task.id}: unknown default assignee {task.defaultAssigneeId}")
        elif task.requiredSkill not in assignee.skills:
            problems.append(
                f"task {task.id}: default assignee {assignee.id} lacks skill {task.requiredSkill}"
            )
    problems.extend(_dependency_cycles(twin))

    booked: dict[str, set[int]] = {}
    for assignment in twin.assignments:
        label = f"assignment {assignment.taskId}/{assignment.personId}"
        if assignment.taskId not in task_ids:
            problems.append(f"{label}: unknown task")
        if assignment.personId not in person_ids:
            problems.append(f"{label}: unknown person")
            continue
        if assignment.startDay > assignment.endDay:
            problems.append(f"{label}: startDay after endDay")
            continue
        person = people_by_id[assignment.personId]
        for day in assignment.days():
            if not person.is_available(day):
                problems.append(f"{label}: day {day} is outside the person's availability")
            if day in booked.setdefault(person.id, set()):
                problems.append(f"{label}: person {person.id} is double-booked on day {day}")
            booked[person.id].add(day)

    for milestone in twin.milestones:
        if milestone.projectId not in project_ids:
            problems.append(f"milestone {milestone.id}: unknown project {milestone.projectId}")
        if not milestone.gatedByTaskIds:
            problems.append(f"milestone {milestone.id}: gated by no task")
        for task_id in milestone.gatedByTaskIds:
            if task_id not in task_ids:
                problems.append(f"milestone {milestone.id}: unknown gating task {task_id}")
        if milestone.dueDay > horizon:
            problems.append(f"milestone {milestone.id}: dueDay beyond horizon {horizon}")

    for commitment in twin.commitments:
        if commitment.customerId not in customer_ids:
            problems.append(f"commitment {commitment.id}: unknown customer")
        if commitment.milestoneId not in milestone_ids:
            problems.append(f"commitment {commitment.id}: unknown milestone")

    for invoice in twin.invoices:
        if invoice.milestoneId not in milestone_ids:
            problems.append(f"invoice {invoice.id}: not linked to a known milestone")

    contractor = people_by_id.get(twin.contractor.personId)
    if contractor is None:
        problems.append(f"contractor: unknown person {twin.contractor.personId}")
    elif contractor.kind != "contractor":
        problems.append(f"contractor: person {contractor.id} is not of kind contractor")

    for preset in twin.presets:
        demand = preset.event.demand
        if not preset.event.unavailable and demand is None:
            problems.append(f"preset {preset.id}: event has no unavailability and no demand")
        for item in preset.event.unavailable:
            if item.personId not in person_ids:
                problems.append(f"preset {preset.id}: unknown person {item.personId}")
            if item.startDay > item.endDay or item.endDay > horizon:
                problems.append(f"preset {preset.id}: malformed unavailability window")
        if demand is not None:
            problems.extend(_check_demand(twin, preset.id, demand))

    problems.extend(_check_sources(twin))

    if problems:
        raise SeedValidationError(problems)


def _check_demand(twin: Twin, preset_id: str, demand: DemandEvent) -> list[str]:
    """A client demand must be consistent on its own and with the company it joins.

    Reuses every normal check by validating the company with the demand merged in (presets are
    dropped from the copy so the check cannot recurse). New ids must not collide with seed ids.
    """
    problems: list[str] = []
    if demand.task.projectId != demand.project.id:
        problems.append(f"preset {preset_id}: demand task is not in the demand project")
    if demand.milestone.projectId != demand.project.id:
        problems.append(f"preset {preset_id}: demand milestone is not in the demand project")
    if demand.milestone.gatedByTaskIds != (demand.task.id,):
        problems.append(f"preset {preset_id}: demand milestone must be gated by the demand task")
    if demand.commitment.milestoneId != demand.milestone.id:
        problems.append(f"preset {preset_id}: demand commitment is not on the demand milestone")
    if demand.invoice.milestoneId != demand.milestone.id:
        problems.append(f"preset {preset_id}: demand invoice is not on the demand milestone")
    if demand.commitment.customerId != demand.project.customerId:
        problems.append(f"preset {preset_id}: demand commitment and project differ in customer")
    merged = twin.with_demand(demand).model_copy(update={"presets": ()})
    try:
        validate_twin(merged)
    except SeedValidationError as exc:
        problems.extend(f"preset {preset_id} demand: {p}" for p in exc.problems)
    return problems


def _check_sources(twin: Twin) -> list[str]:
    """Each record's source system must fit its kind; external ids are unique per system."""
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    kinds: tuple[tuple[str, str, Iterable[Any]], ...] = (
        ("person", "hris", twin.people),
        ("task", "tracker", twin.tasks),
        ("invoice", "erp", twin.invoices),
        ("commitment", "crm", twin.commitments),
        ("customer", "crm", twin.customers),
    )
    for kind, system, items in kinds:
        for item in items:
            if item.source is None:
                continue
            if item.source.system != system:
                problems.append(f"{kind} {item.id}: source system must be {system}")
            key = (item.source.system, item.source.externalId)
            if key in seen:
                problems.append(f"{kind} {item.id}: duplicate source id {item.source.externalId}")
            seen.add(key)
    return problems


def _duplicates(name: str, ids: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in ids:
        if item in seen:
            out.append(f"{name}: duplicate id {item}")
        seen.add(item)
    return out


def _check_windows(label: str, windows: Iterable[DayWindow]) -> list[str]:
    problems: list[str] = []
    ordered = sorted(windows, key=lambda w: w.startDay)
    for window in ordered:
        if window.startDay > window.endDay:
            problems.append(f"{label}: startDay {window.startDay} after endDay {window.endDay}")
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if later.startDay <= earlier.endDay:
            problems.append(f"{label}: overlapping windows")
    return problems


def _dependency_cycles(twin: Twin) -> list[str]:
    graph = {t.id: [d for d in t.dependsOn if d != t.id] for t in twin.tasks}
    state: dict[str, int] = {}  # 1 = visiting, 2 = done
    problems: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        for dep in graph.get(node, []):
            if dep not in graph:
                continue
            if state.get(dep) == 1:
                problems.append(f"dependency cycle involving {node} and {dep}")
            elif dep not in state:
                visit(dep)
        state[node] = 2

    for node in graph:
        if node not in state:
            visit(node)
    return problems


__all__ = [
    "SEED_PATH",
    "SeedValidationError",
    "get_twin",
    "load_seed",
    "parse_seed",
    "validate_twin",
]

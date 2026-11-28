"""Turn a typed event ("Camila is on leave for 6 working days") into a `Twin` for the agents.

The recovery engine (`twin/solver.py`, the agents, the approval gate) works on a small, validated
company model with working-day numbers. This module builds that model from the big company
database for one event, so the same engine can answer events about real people, tickets,
projects, commitments and invoices instead of only the four hand-written scenarios. Everything is
derived by code from database rows; nothing here calls a model.

Working day 1 is the company's "today" (`meta.as_of`); weekends and company holidays are not
days. The model covers `HORIZON` working days.

Scope (honest): one event kind, `leave` (a person is out for N working days). The affected work
is the person's most urgent open tickets on active projects. Anything the database cannot support
raises an `EventError` whose message is safe to show.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from datahub import db
from twin import solver
from twin.model import (
    Assignment,
    Budget,
    Commitment,
    Company,
    ContractorOption,
    Customer,
    DayWindow,
    DisruptionEvent,
    Invoice,
    Milestone,
    Person,
    Preset,
    PresetSource,
    Project,
    SourceRef,
    Task,
    Twin,
    Unavailability,
)
from twin.model import DemandEvent as ModelDemand
from twin.seed import validate_twin

HORIZON = 20  # working days in the model
MAX_AFFECTED_TICKETS = 3  # the person's most urgent open tickets that enter the model
BACKUP_TICKETS = 2  # the backup's own booked work (what a careless reassignment would collide with)
MAX_TASK_DAYS = 3
MAX_EVENT_DAYS = 15
RESERVE_PERCENT = 5  # recovery budget = 5% of the person's department's monthly budget
WORKING_DAYS_PER_MONTH = 21
PRESET_ID = "event-leave"
DEMAND_PRESET_ID = "event-demand"
MAX_DEMAND_DAYS = 10
OPEN_STATUSES = ("todo", "in_progress", "in_review", "blocked")
_PRIORITY = (
    "CASE k.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END"
)


class EventError(ValueError):
    """The event cannot be modelled. The message is safe to show to the user."""


class NoImpactError(EventError):
    """The event does not disrupt any scheduled work, so there is nothing to recover."""


class LeaveEvent(BaseModel):
    """A person is out for `workingDays` working days starting on `startDate`."""

    model_config = ConfigDict(extra="forbid")

    personId: int = Field(ge=1)
    startDate: date
    workingDays: int = Field(ge=1, le=MAX_EVENT_DAYS)


def working_calendar() -> list[date]:
    """The model's working days: `HORIZON` weekdays from the company's today, minus holidays."""
    holidays = {r["date"] for r in db.query("SELECT date FROM holidays")}
    days: list[date] = []
    current = db.as_of()
    while len(days) < HORIZON:
        if current.weekday() < 5 and current.isoformat() not in holidays:
            days.append(current)
        current += timedelta(days=1)
    return days


def day_number(calendar: list[date], when: date) -> int | None:
    """The first working day on or after `when` (1-based), or None if it is past the horizon."""
    for index, day in enumerate(calendar, start=1):
        if day >= when:
            return index
    return None


def _windows(days: set[int]) -> tuple[DayWindow, ...]:
    out: list[DayWindow] = []
    start: int | None = None
    for day in range(1, HORIZON + 2):
        if day in days and start is None:
            start = day
        elif day not in days and start is not None:
            out.append(DayWindow(startDay=start, endDay=day - 1))
            start = None
    return tuple(out)


def _leave_days(employee_id: int, calendar: list[date]) -> set[int]:
    rows = db.query(
        "SELECT start_date, end_date FROM leave_requests WHERE employee_id = ? "
        "AND status = 'approved' AND end_date >= ? AND start_date <= ?",
        (employee_id, calendar[0].isoformat(), calendar[-1].isoformat()),
    )
    away: set[int] = set()
    for row in rows:
        lo, hi = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
        away.update(i for i, d in enumerate(calendar, start=1) if lo <= d <= hi)
    return away


def _person(row: dict[str, Any], skills: list[str], calendar: list[date]) -> Person:
    away = _leave_days(row["id"], calendar)
    return Person(
        id=f"PER-{row['id']}",
        name=row["name"],
        role=row["role"],
        kind="contractor" if row["employment_type"] == "contractor" else "employee",
        skills=tuple(skills),
        availability=_windows(set(range(1, HORIZON + 1)) - away),
        source=SourceRef(system="hris", externalId=f"HR-{row['id']}"),
    )


def _skills(employee_id: int) -> list[str]:
    return [
        r["skill"]
        for r in db.query(
            "SELECT skill FROM skills WHERE employee_id = ? ORDER BY skill", (employee_id,)
        )
    ]


def _open_tickets(employee_id: int, limit: int) -> list[dict[str, Any]]:
    marks = ",".join("?" * len(OPEN_STATUSES))
    return db.query(
        "SELECT k.id, k.key, k.title, k.priority, k.estimate_days, k.due_date, "  # noqa: S608
        "k.blocked_by_ticket_id, p.id AS project_id, p.code, p.name AS project_name, "
        "p.target_date, p.account_id "
        "FROM tickets k JOIN projects p ON p.id = k.project_id "
        f"WHERE k.assignee_id = ? AND k.status IN ({marks}) AND p.status = 'active' "
        f"ORDER BY (k.due_date IS NULL), k.due_date, {_PRIORITY}, k.id LIMIT ?",
        (employee_id, *OPEN_STATUSES, limit),
    )


def _task(
    ticket: dict[str, Any], assignee: str, skill: str, task_type: str, deps: tuple[str, ...]
) -> Task:
    return Task(
        id=ticket["key"],
        projectId=f"P-{ticket['code']}",
        name=ticket["title"],
        type="qa" if task_type == "qa" else "integration",
        days=max(1, min(MAX_TASK_DAYS, math.ceil(float(ticket["estimate_days"])))),
        dependsOn=deps,
        requiredSkill=skill,
        defaultAssigneeId=assignee,
        source=SourceRef(system="tracker", externalId=ticket["key"]),
    )


def _pick_skill(person_id: int, department_id: int, skills: list[str]) -> str:
    """The person's skill that the most colleagues in the department share (a backup must exist)."""
    if not skills:
        raise EventError("This person has no recorded skills, so a cover cannot be matched.")
    marks = ",".join("?" * len(skills))
    rows = db.query(
        f"SELECT s.skill, COUNT(*) AS n FROM skills s JOIN employees e ON e.id = s.employee_id "  # noqa: S608
        f"WHERE s.skill IN ({marks}) AND e.id != ? AND e.department_id = ? "
        "AND e.employment_type = 'employee' AND e.status = 'active' "
        "GROUP BY s.skill ORDER BY n DESC, s.skill LIMIT 1",
        (*skills, person_id, department_id),
    )
    if not rows:
        raise EventError("Nobody else in the department has a matching skill to cover the work.")
    return str(rows[0]["skill"])


def _pick_backup(person_id: int, department_id: int, skill: str) -> dict[str, Any]:
    marks = ",".join("?" * len(OPEN_STATUSES))
    rows = db.query(
        "SELECT e.id, e.name, e.role, e.employment_type, "  # noqa: S608
        "(SELECT COALESCE(SUM(percent), 0) FROM allocations a WHERE a.employee_id = e.id) AS load, "
        "(SELECT COUNT(*) FROM tickets k JOIN projects p ON p.id = k.project_id "
        f"WHERE k.assignee_id = e.id AND k.status IN ({marks}) AND p.status = 'active') "
        "AS open_work "
        "FROM employees e JOIN skills s ON s.employee_id = e.id AND s.skill = ? "
        "WHERE e.id != ? AND e.department_id = ? AND e.employment_type = 'employee' "
        "AND e.status = 'active' ORDER BY (open_work = 0), load, e.name LIMIT 1",
        (*OPEN_STATUSES, skill, person_id, department_id),
    )
    if not rows:
        raise EventError("Nobody else in the department has the skill to cover the work.")
    return rows[0]


def _contractor(skill: str) -> dict[str, Any]:
    rows = db.query(
        "SELECT e.id, e.name, e.role, e.employment_type, e.monthly_cost_usd FROM employees e "
        "WHERE e.employment_type = 'contractor' ORDER BY "
        "(SELECT COUNT(*) FROM skills s WHERE s.employee_id = e.id AND s.skill = ?) DESC, e.id "
        "LIMIT 1",
        (skill,),
    )
    if not rows:
        raise EventError("No contractor is on file to bring in.")
    return rows[0]


def _free_block(taken: set[int], away: set[int], length: int) -> tuple[int, int] | None:
    """The earliest run of `length` consecutive working days that is free and not on leave."""
    for start in range(1, HORIZON - length + 2):
        run = range(start, start + length)
        if all(d not in taken and d not in away for d in run):
            return start, start + length - 1
    return None


def _budget(department_id: int) -> Budget:
    month = db.as_of().isoformat()[:7]
    rows = db.query(
        "SELECT budget_usd FROM budgets WHERE department_id = ? AND month <= ? "
        "ORDER BY month DESC LIMIT 1",
        (department_id, month),
    )
    monthly = int(rows[0]["budget_usd"]) if rows else 0
    return Budget(recoveryBudget=monthly * RESERVE_PERCENT // 100, currency="USD")


@dataclass
class _Parts:
    """The company around one engineer: their work, a backup, a contractor, and the money."""

    skill: str
    people: list[Person]  # [owner, backup, contractor]
    tasks: list[Task]
    assignments: list[Assignment]
    projects: list[Project]
    customers: dict[str, Customer]
    milestones: list[Milestone]
    commitments: list[Commitment]
    invoices: list[Invoice]
    contractor_row: dict[str, Any]


def _gather(
    person: dict[str, Any],
    calendar: list[date],
    tickets: list[dict[str, Any]],
    skill_override: str | None,
) -> _Parts:
    """Build the model around `person`'s open `tickets` (shared by every event kind)."""
    skills = _skills(person["id"])
    skill = skill_override or _pick_skill(person["id"], person["department_id"], skills)
    backup_row = _pick_backup(person["id"], person["department_id"], skill)
    contractor_row = _contractor(skill)

    people = [
        _person(person, skills, calendar),
        _person(backup_row, _skills(backup_row["id"]), calendar),
        _person(contractor_row, _skills(contractor_row["id"]), calendar),
    ]
    owner_id, backup_id, _ = (p.id for p in people)

    tasks: list[Task] = []
    chosen_ids = {t["id"] for t in tickets}
    for ticket in tickets:
        dep = ticket["blocked_by_ticket_id"]
        deps: tuple[str, ...] = ()
        if dep in chosen_ids:
            deps = (next(t["key"] for t in tickets if t["id"] == dep),)
        tasks.append(
            _task(ticket, owner_id, skill, "qa" if "QA" in person["role"] else "task", deps)
        )

    # The backup's own booked work: what a careless reassignment would run into.
    backup_tickets = _open_tickets(backup_row["id"], BACKUP_TICKETS)
    backup_away = _leave_days(backup_row["id"], calendar)
    taken: set[int] = set()
    assignments: list[Assignment] = []
    for ticket in backup_tickets:
        if ticket["key"] in {t.id for t in tasks}:
            continue
        task = _task(ticket, backup_id, skill, "task", ())
        block = _free_block(taken, backup_away, task.days)
        if block is None:
            continue
        tasks.append(task)
        taken.update(range(block[0], block[1] + 1))
        assignments.append(
            Assignment(taskId=task.id, personId=backup_id, startDay=block[0], endDay=block[1])
        )

    # Projects, customers, milestones, commitments and invoices around the affected work.
    project_ids = {t["project_id"] for t in tickets} | {t["project_id"] for t in backup_tickets}
    projects, customers, milestones, commitments, invoices = [], {}, [], [], []
    for pid in sorted(project_ids):
        prow = db.query(
            "SELECT p.id, p.code, p.name, p.target_date, p.account_id, a.name AS account "
            "FROM projects p LEFT JOIN accounts a ON a.id = p.account_id WHERE p.id = ?",
            (pid,),
        )[0]
        cid = f"CUS-{prow['account_id'] or 0}"
        customers[cid] = Customer(
            id=cid,
            name=prow["account"] or "Internal",
            source=SourceRef(system="crm", externalId=f"ACC-{prow['account_id'] or 0}"),
        )
        projects.append(Project(id=f"P-{prow['code']}", name=prow["name"], customerId=cid))
        if pid not in {t["project_id"] for t in tickets}:
            continue
        gated = tuple(t["key"] for t in tickets if t["project_id"] == pid)
        due = day_number(calendar, date.fromisoformat(prow["target_date"])) or HORIZON
        milestone = Milestone(
            id=f"M-{prow['code']}",
            projectId=f"P-{prow['code']}",
            name=f"{prow['name']}: delivery",
            dueDay=due,
            gatedByTaskIds=gated,
        )
        milestones.append(milestone)
        for crow in db.query(
            "SELECT id, description FROM commitments WHERE project_id = ? AND status = 'open' "
            "ORDER BY due_date, id LIMIT 2",
            (pid,),
        ):
            commitments.append(
                Commitment(
                    id=f"COM-{crow['id']}",
                    customerId=cid,
                    milestoneId=milestone.id,
                    description=crow["description"],
                    source=SourceRef(system="crm", externalId=f"COM-{crow['id']}"),
                )
            )
        for irow in db.query(
            "SELECT number, amount_usd FROM invoices WHERE project_id = ? "
            "AND status IN ('draft', 'sent') ORDER BY amount_usd DESC, id LIMIT 1",
            (pid,),
        ):
            invoices.append(
                Invoice(
                    id=irow["number"],
                    milestoneId=milestone.id,
                    amount=int(irow["amount_usd"]),
                    currency="USD",
                    description=f"{prow['name']} delivery invoice",
                    source=SourceRef(system="erp", externalId=irow["number"]),
                )
            )
    return _Parts(
        skill,
        people,
        tasks,
        assignments,
        projects,
        customers,
        milestones,
        commitments,
        invoices,
        contractor_row,
    )


def _finish(parts: _Parts, preset: Preset, person: dict[str, Any], extra_days: int) -> Twin:
    """Add the money and the preset, validate, and prove the engine finds something to recover."""
    owner_id = parts.people[0].id
    contractor_id = parts.people[2].id
    daily = int(parts.contractor_row["monthly_cost_usd"]) // WORKING_DAYS_PER_MONTH
    engaged_days = sum(t.days for t in parts.tasks if t.defaultAssigneeId == owner_id) + extra_days
    fixed_cost = math.ceil(daily * engaged_days / 50) * 50

    twin = Twin(
        company=Company(
            id="northstar",
            name=str(db.meta("company") or "Northstar Systems"),
            description="Fictional company (event view built from the company database).",
        ),
        horizonDays=HORIZON,
        customers=tuple(parts.customers.values()),
        projects=tuple(parts.projects),
        people=tuple(parts.people),
        tasks=tuple(parts.tasks),
        assignments=tuple(parts.assignments),
        milestones=tuple(parts.milestones),
        commitments=tuple(parts.commitments),
        invoices=tuple(parts.invoices),
        budget=_budget(person["department_id"]),
        contractor=ContractorOption(personId=contractor_id, fixedCost=fixed_cost, currency="USD"),
        presets=(preset,),
    )
    validate_twin(twin)
    try:
        solver.candidate_plans(twin, preset.id)
    except ValueError:
        raise NoImpactError(
            f"{person['name']} is out on days when no scheduled work of theirs is planned, so "
            "nothing is disrupted."
            if preset.event.demand is None
            else "The request does not disturb any scheduled work."
        ) from None
    return twin


def build_leave_twin(event: LeaveEvent) -> Twin:
    """The company model for "this person is out for N working days". Raises `EventError`."""
    calendar = working_calendar()
    employee = db.query(
        "SELECT e.*, d.name AS department FROM employees e "
        "JOIN departments d ON d.id = e.department_id WHERE e.id = ?",
        (event.personId,),
    )
    if not employee:
        raise EventError("That person is not in the company records.")
    person = employee[0]
    if event.startDate < calendar[0]:
        raise EventError("The event starts in the past; give a date from today onward.")
    start_day = day_number(calendar, event.startDate)
    if start_day is None:
        raise EventError(f"The event starts after the {HORIZON} working days that are planned.")
    end_day = min(HORIZON, start_day + event.workingDays - 1)

    tickets = _open_tickets(person["id"], MAX_AFFECTED_TICKETS)
    if not tickets:
        raise NoImpactError(
            f"{person['name']} has no open tickets on active projects, so an absence does not "
            "disrupt any scheduled delivery work."
        )
    parts = _gather(person, calendar, tickets, None)
    first, last = calendar[start_day - 1], calendar[end_day - 1]
    preset = Preset(
        id=PRESET_ID,
        label=f"{person['name']} is out",
        description=(
            f"{person['name']} ({person['role']}) is out for {end_day - start_day + 1} working "
            f"days ({first.isoformat()} to {last.isoformat()}) and their open work is at risk."
        ),
        event=DisruptionEvent(
            unavailable=(
                Unavailability(personId=parts.people[0].id, startDay=start_day, endDay=end_day),
            )
        ),
        source=PresetSource(
            system="hris",
            eventType="leave.reported",
            payload={
                "employee": person["name"],
                "from": first.isoformat(),
                "to": last.isoformat(),
                "workingDays": end_day - start_day + 1,
            },
        ),
    )
    return _finish(parts, preset, person, extra_days=0)


class ClientRequest(BaseModel):
    """A client asks for new work: `days` of `skill` work for `account`, due `dueDate`, `amount`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["demand"]
    accountId: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=80)
    skill: str = Field(min_length=1, max_length=40)
    days: int = Field(ge=1, le=MAX_DEMAND_DAYS)
    dueDate: date
    amount: int = Field(ge=1, le=1_000_000)


def _demand_owner(skill: str, calendar: list[date]) -> dict[str, Any]:
    """The engineer who would naturally get the work: has the skill, is busy, is not away."""
    marks = ",".join("?" * len(OPEN_STATUSES))
    rows = db.query(
        "SELECT e.*, (SELECT COUNT(*) FROM tickets k JOIN projects p ON p.id = k.project_id "  # noqa: S608
        f"WHERE k.assignee_id = e.id AND k.status IN ({marks}) AND p.status = 'active') "
        "AS open_work "
        "FROM employees e JOIN skills s ON s.employee_id = e.id AND s.skill = ? "
        "WHERE e.employment_type = 'employee' AND e.status = 'active' "
        "ORDER BY open_work DESC, e.id LIMIT 20",
        (*OPEN_STATUSES, skill),
    )
    for row in rows:
        if row["open_work"] >= 2 and not _leave_days(row["id"], calendar) & set(range(1, 9)):
            return row
    raise EventError(f"Nobody with the '{skill}' skill is available to take the work.")


def build_demand_twin(req: ClientRequest) -> Twin:
    """The company model for "a client asks for new work". Raises `EventError`."""
    calendar = working_calendar()
    account = db.query("SELECT id, name FROM accounts WHERE id = ?", (req.accountId,))
    if not account:
        raise EventError("That client is not in the company records.")
    if not db.query("SELECT 1 FROM skills WHERE skill = ? LIMIT 1", (req.skill,)):
        raise EventError(f"'{req.skill}' is not a skill the company has.")
    if req.dueDate < calendar[0]:
        raise EventError("The requested due date is in the past.")
    due = day_number(calendar, req.dueDate)
    if due is None:
        raise EventError(f"The due date is after the {HORIZON} working days that are planned.")

    owner = _demand_owner(req.skill, calendar)
    tickets = _open_tickets(owner["id"], MAX_AFFECTED_TICKETS)
    parts = _gather(owner, calendar, tickets, req.skill)
    owner_id = parts.people[0].id
    client = f"CUS-{account[0]['id']}"
    name = account[0]["name"]
    demand = ModelDemand(
        project=Project(id="P-REQ", name=req.title, customerId=client),
        task=Task(
            id="REQ-1",
            projectId="P-REQ",
            name=req.title,
            type="integration",
            days=req.days,
            dependsOn=(),
            requiredSkill=req.skill,
            defaultAssigneeId=owner_id,
            source=SourceRef(system="tracker", externalId="REQ-1"),
        ),
        milestone=Milestone(
            id="M-REQ",
            projectId="P-REQ",
            name=f"{req.title}: delivery",
            dueDay=due,
            gatedByTaskIds=("REQ-1",),
        ),
        commitment=Commitment(
            id="COM-REQ",
            customerId=client,
            milestoneId="M-REQ",
            description=(
                f"{name}: {req.title} delivered by {req.dueDate.isoformat()} (client request)"
            ),
            source=SourceRef(system="crm", externalId="COM-REQ"),
        ),
        invoice=Invoice(
            id="INV-REQ",
            milestoneId="M-REQ",
            amount=req.amount,
            currency="USD",
            description=f"{req.title} invoice, eligible once the milestone is accepted",
            source=SourceRef(system="erp", externalId="INV-REQ"),
        ),
    )
    parts.customers[client] = Customer(
        id=client, name=name, source=SourceRef(system="crm", externalId=f"ACC-{account[0]['id']}")
    )
    preset = Preset(
        id=DEMAND_PRESET_ID,
        label=f"New client work: {req.title}",
        description=(
            f"{name} asks for '{req.title}': {req.days} working days of {req.skill} work, due "
            f"{req.dueDate.isoformat()}, worth {req.amount} USD. Can Northstar say yes without "
            "breaking its other commitments?"
        ),
        event=DisruptionEvent(demand=demand),
        source=PresetSource(
            system="crm",
            eventType="client.request",
            payload={
                "account": name,
                "request": req.title,
                "estimateDays": req.days,
                "dueDate": req.dueDate.isoformat(),
                "quotedValue": req.amount,
            },
        ),
    )
    return _finish(parts, preset, owner, extra_days=req.days)


def preset_id_for(event: LeaveEvent | ClientRequest) -> str:
    return DEMAND_PRESET_ID if isinstance(event, ClientRequest) else PRESET_ID


def build_twin(event: LeaveEvent | ClientRequest) -> Twin:
    return build_demand_twin(event) if isinstance(event, ClientRequest) else build_leave_twin(event)


def count_working_days(start: date, end: date) -> int:
    """Working days (company calendar) from `start` to `end`, both included."""
    if end < start:
        raise EventError("The end date is before the start date.")
    return sum(1 for d in working_calendar() if start <= d <= end)


def leave_between(person_id: int, start: date, end: date) -> LeaveEvent:
    """A leave from `start` to `end` (inclusive), capped at the longest leave the model covers."""
    days = count_working_days(start, end)
    if days == 0:
        raise EventError("That period has no working days in the planned window.")
    return LeaveEvent(personId=person_id, startDate=start, workingDays=min(days, MAX_EVENT_DAYS))


def calendar_dates() -> list[str]:
    """ISO date of each working day number (index 0 is day 1)."""
    return [d.isoformat() for d in working_calendar()]


def resolve_leave(person: str, start_date: str | None, working_days: int) -> LeaveEvent:
    """Match a typed name (and optional start date) to a `LeaveEvent`.

    The name must identify exactly one employee: a full name (any case) or a first or last name
    that only one employee has. Otherwise an `EventError` asks the user to be specific. With no
    start date the leave starts on the company's today (or the next working day).
    """
    name = " ".join(person.split())
    if not 1 <= working_days <= MAX_EVENT_DAYS:
        raise EventError(f"I can model a leave of 1 to {MAX_EVENT_DAYS} working days.")
    if not name:
        raise EventError("Which employee is this about? Please give a name.")
    rows = db.query("SELECT id, name FROM employees WHERE lower(name) = lower(?)", (name,))
    if not rows:
        like = f"%{name.lower().replace('%', '').replace('_', '')}%"
        rows = db.query(
            "SELECT id, name FROM employees WHERE lower(name) LIKE ? ORDER BY name LIMIT 6", (like,)
        )
    if not rows:
        raise EventError(f"I could not find an employee called '{name}'. Please check the name.")
    if len(rows) > 1:
        shown = ", ".join(r["name"] for r in rows[:5])
        raise EventError(f"More than one employee matches '{name}' ({shown}). Which one?")
    try:
        start = date.fromisoformat(start_date) if start_date else db.as_of()
    except ValueError:
        raise EventError("I could not read the start date. Please give it as YYYY-MM-DD.") from None
    return LeaveEvent(personId=rows[0]["id"], startDate=start, workingDays=working_days)


__all__ = [
    "DEMAND_PRESET_ID",
    "HORIZON",
    "PRESET_ID",
    "ClientRequest",
    "EventError",
    "LeaveEvent",
    "NoImpactError",
    "build_demand_twin",
    "build_leave_twin",
    "build_twin",
    "calendar_dates",
    "count_working_days",
    "day_number",
    "leave_between",
    "preset_id_for",
    "resolve_leave",
    "working_calendar",
]

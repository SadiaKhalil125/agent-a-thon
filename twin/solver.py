"""Deterministic solver: scheduling, completion, cost, eligibility, outcome (TASK-006/007).

Pure functions over the twin model; no I/O, no model calls, no randomness. This module is the
single authority for every number shown in the app (ADR-001): agents narrate these results, the
API recomputes them server-side, and the UI only displays them.

Scheduling model: each person works one task per working day. A task needs `days` working days
from people who are available that day (seed availability minus the disruption window) and not
already booked. A dependent task cannot start before every dependency has finished.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from twin.model import Assignment, DemandEvent, Task, Twin
from twin.results import (
    AppliedMilestone,
    AppliedState,
    DeadlineResult,
    Delta,
    DerivedFact,
    FactTag,
    FinanceReport,
    ImpactReport,
    InvoiceExposure,
    MilestoneSlip,
    OutcomeCheck,
    PersonCapacity,
    Plan,
    PlanFinance,
    ResourceReport,
    Segment,
)

PLAN_WAIT = "plan-wait"
PLAN_BACKUP = "plan-backup"
PLAN_CONTRACTOR = "plan-contractor"
PLAN_BACKUP_REVISED = "plan-backup-revised"

RESOURCE_WINDOW_DAYS = 10  # planning window shown in resource facts (working days 1..10)

_Day = tuple[str, int]  # (person id, working day)


class PlanNotFoundError(KeyError):
    """The plan id is not a known plan for this preset (the approval gate relies on this)."""


def _demand_of(twin: Twin, preset_id: str) -> DemandEvent | None:
    return twin.preset(preset_id).event.demand


def effective_twin(twin: Twin, preset_id: str) -> Twin:
    """The company as this scenario sees it.

    A client-meeting preset adds the new project, task, milestone, commitment and invoice to the
    company; every other preset returns the twin unchanged. Safe to call more than once.
    """
    demand = _demand_of(twin, preset_id)
    return twin if demand is None else twin.with_demand(demand)


# ---------------------------------------------------------------------------------------
# Availability and allocation primitives
# ---------------------------------------------------------------------------------------


def _blocked_days(twin: Twin, preset_id: str | None) -> dict[str, set[int]]:
    blocked: dict[str, set[int]] = {p.id: set() for p in twin.people}
    if preset_id is None:
        return blocked
    for item in twin.preset(preset_id).event.unavailable:
        blocked[item.personId].update(range(item.startDay, item.endDay + 1))
    return blocked


def _availability(twin: Twin, blocked: dict[str, set[int]]) -> dict[str, set[int]]:
    return {
        p.id: {
            day
            for day in range(1, twin.horizonDays + 1)
            if p.is_available(day) and day not in blocked[p.id]
        }
        for p in twin.people
    }


def _topological_tasks(twin: Twin) -> list[Task]:
    remaining = list(twin.tasks)
    done: set[str] = set()
    ordered: list[Task] = []
    while remaining:
        ready = [t for t in remaining if all(d in done for d in t.dependsOn)]
        if not ready:  # cycles are rejected by seed validation; guard anyway
            raise ValueError("task dependencies contain a cycle")
        for task in ready:
            ordered.append(task)
            done.add(task.id)
            remaining.remove(task)
    return ordered


def _allocate(
    days_needed: int,
    candidates: list[str],
    earliest: int,
    avail: dict[str, set[int]],
    busy: dict[str, set[int]],
    horizon: int,
) -> list[_Day] | None:
    """Give `days_needed` working days to the first free candidate each day; mark them busy."""
    taken: list[_Day] = []
    for day in range(earliest, horizon + 1):
        for person_id in candidates:
            if day in avail[person_id] and day not in busy[person_id]:
                busy[person_id].add(day)
                taken.append((person_id, day))
                break
        if len(taken) == days_needed:
            return taken
    for person_id, day in taken:  # not enough capacity inside the horizon: undo
        busy[person_id].discard(day)
    return None


@dataclass
class _Schedule:
    allocated: dict[str, list[_Day]] = field(default_factory=dict)  # task id -> (person, day)
    conflicts: list[tuple[str, str, tuple[int, ...]]] = field(default_factory=list)
    # conflicts: (person id, displaced task id, double-booked days)


def _schedule(
    twin: Twin,
    blocked: dict[str, set[int]],
    overrides: dict[str, list[str]],
    honor_bookings: bool,
) -> _Schedule:
    """Schedule every task.

    `overrides` maps a task id to the people who should do it (default: its default assignee).
    With `honor_bookings=False`, fixed bookings of the overriding people are released first and
    rescheduled afterwards: that models a plan that double-books someone (the verifier's target).
    """
    avail = _availability(twin, blocked)
    busy: dict[str, set[int]] = {p.id: set() for p in twin.people}
    result = _Schedule()

    override_people = {p for people in overrides.values() for p in people}
    displaced: list[Assignment] = []
    for booking in twin.assignments:
        if not honor_bookings and booking.personId in override_people:
            displaced.append(booking)
            continue
        result.allocated[booking.taskId] = [(booking.personId, d) for d in booking.days()]
        busy[booking.personId].update(booking.days())

    for task in _topological_tasks(twin):
        if task.id in result.allocated or any(b.taskId == task.id for b in displaced):
            continue
        dep_days = [d for dep in task.dependsOn for _, d in result.allocated.get(dep, [])]
        deps_ready = all(result.allocated.get(dep) for dep in task.dependsOn)
        earliest = (max(dep_days) + 1) if dep_days else 1
        candidates = overrides.get(task.id, [task.defaultAssigneeId])
        taken = (
            _allocate(task.days, candidates, earliest, avail, busy, twin.horizonDays)
            if deps_ready
            else None
        )
        result.allocated[task.id] = taken or []

    for booking in displaced:
        needed = booking.endDay - booking.startDay + 1
        taken = _allocate(
            needed, [booking.personId], booking.startDay, avail, busy, twin.horizonDays
        )
        result.allocated[booking.taskId] = taken or []
        recovery_days = {
            d
            for tid, days in result.allocated.items()
            if tid != booking.taskId
            for person, d in days
            if person == booking.personId
        }
        clash = tuple(d for d in booking.days() if d in recovery_days)
        if clash:
            result.conflicts.append((booking.personId, booking.taskId, clash))
    return result


def _segments(twin: Twin, allocated: dict[str, list[_Day]]) -> tuple[Segment, ...]:
    out: list[Segment] = []
    for task in twin.tasks:
        days = sorted(allocated.get(task.id, []), key=lambda pd: (pd[1], pd[0]))
        current: Segment | None = None
        for person_id, day in days:
            if current and current.personId == person_id and current.endDay + 1 == day:
                current = current.model_copy(update={"endDay": day})
                out[-1] = current
            else:
                current = Segment(taskId=task.id, personId=person_id, startDay=day, endDay=day)
                out.append(current)
    return tuple(out)


def _end_by_task(segments: tuple[Segment, ...]) -> dict[str, int]:
    ends: dict[str, int] = {}
    for seg in segments:
        ends[seg.taskId] = max(ends.get(seg.taskId, 0), seg.endDay)
    return ends


def _task_completion(twin: Twin, task_id: str, segments: tuple[Segment, ...]) -> int | None:
    """Last working day of a task, or None if it is not fully scheduled."""
    task = twin.task(task_id)
    worked = sum(s.endDay - s.startDay + 1 for s in segments if s.taskId == task_id)
    ends = _end_by_task(segments)
    return ends.get(task_id) if worked >= task.days else None


def _milestone_completion(
    twin: Twin, milestone_id: str, segments: tuple[Segment, ...]
) -> int | None:
    ends = [
        _task_completion(twin, t, segments) for t in twin.milestone(milestone_id).gatedByTaskIds
    ]
    if any(e is None for e in ends):
        return None
    return max(e for e in ends if e is not None)


def _project_key(project_id: str) -> str:
    return project_id.removeprefix("P-")


def _project_completion(twin: Twin, segments: tuple[Segment, ...]) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for project in twin.projects:
        ends = [
            _task_completion(twin, t.id, segments) for t in twin.tasks if t.projectId == project.id
        ]
        result[_project_key(project.id)] = (
            None if any(e is None for e in ends) else max(e for e in ends if e is not None)
        )
    return result


def _cost(twin: Twin, segments: tuple[Segment, ...]) -> int:
    used = any(s.personId == twin.contractor.personId for s in segments)
    return twin.contractor.fixedCost if used else 0


def _days_text(days: tuple[int, ...] | list[int]) -> str:
    if not days:
        return "none"
    ordered = sorted(days)
    runs: list[str] = []
    start = prev = ordered[0]
    for day in ordered[1:]:
        if day == prev + 1:
            prev = day
            continue
        runs.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = day
    runs.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(runs)


# ---------------------------------------------------------------------------------------
# Plans (TASK-006)
# ---------------------------------------------------------------------------------------


def _evaluate(
    twin: Twin,
    schedule: _Schedule,
    *,
    plan_id: str,
    name: str,
    summary: str,
    status: str = "proposed",
    revises: str | None = None,
) -> Plan:
    segments = _segments(twin, schedule.allocated)
    deadlines: list[DeadlineResult] = []
    violated: list[str] = []

    for person_id, task_id, clash in schedule.conflicts:
        person = twin.person(person_id)
        task = twin.task(task_id)
        project = twin.project(task.projectId)
        done = _task_completion(twin, task_id, segments)
        due = next((m.dueDay for m in twin.milestones if task_id in m.gatedByTaskIds), None)
        tail = (
            f", which then finishes on day {done} against its due day {due}"
            if done is not None and due is not None
            else ""
        )
        violated.append(
            f"Double-books {person.name} on day(s) {_days_text(clash)}: already assigned to "
            f"{task.name} ({project.name}){tail}"
        )

    for milestone in twin.milestones:
        completion = _milestone_completion(twin, milestone.id, segments)
        met = completion is not None and completion <= milestone.dueDay
        deadlines.append(DeadlineResult(name=milestone.name, dueDay=milestone.dueDay, met=met))
        if not met:
            when = (
                f"finishes on day {completion}"
                if completion is not None
                else f"cannot finish within the {twin.horizonDays}-day horizon"
            )
            violated.append(f"{milestone.name} (due day {milestone.dueDay}) is missed: {when}")

    invoice_eligible = True
    for invoice in twin.invoices:
        completion = _milestone_completion(twin, invoice.milestoneId, segments)
        milestone = twin.milestone(invoice.milestoneId)
        if completion is None or completion > milestone.dueDay:
            invoice_eligible = False
            violated.append(
                f"Invoice {invoice.id} ({invoice.amount} {invoice.currency}) is not eligible by "
                f"day {milestone.dueDay}"
            )

    cost = _cost(twin, segments)
    budget_fit = cost <= twin.budget.recoveryBudget
    if not budget_fit:
        violated.append(
            f"Incremental cost {cost} {twin.budget.currency} exceeds the recovery budget "
            f"{twin.budget.recoveryBudget} {twin.budget.currency}"
        )

    return Plan.model_validate(
        {
            "id": plan_id,
            "name": name,
            "summary": summary,
            "status": status,
            "revisesPlanId": revises,
            "projectCompletion": _project_completion(twin, segments),
            "deadlines": deadlines,
            "incrementalCost": cost,
            "budgetFit": budget_fit,
            "invoiceEligible": invoice_eligible,
            "violatedConstraints": violated,
            "schedule": segments,
        }
    )


def _directly_affected(twin: Twin, preset_id: str) -> list[Task]:
    """Tasks whose baseline working days overlap the person's disruption window.

    For a client-meeting preset nobody is out: the task to place is the newly requested one.
    """
    twin = effective_twin(twin, preset_id)
    demand = _demand_of(twin, preset_id)
    if demand is not None:
        return [twin.task(demand.task.id)]
    blocked = _blocked_days(twin, preset_id)
    baseline = _schedule(twin, _blocked_days(twin, None), {}, True)
    affected: list[Task] = []
    for task in _topological_tasks(twin):
        if any(day in blocked[person] for person, day in baseline.allocated.get(task.id, [])):
            affected.append(task)
    return affected


def _recovery_task(twin: Twin, preset_id: str) -> Task:
    affected = _directly_affected(twin, preset_id)
    if not affected:
        raise ValueError(f"preset {preset_id} does not disrupt any task")
    return affected[0]


def _backup_person_id(twin: Twin, task: Task) -> str:
    for person in twin.people:
        if (
            person.kind == "employee"
            and person.id != task.defaultAssigneeId
            and task.requiredSkill in person.skills
        ):
            return person.id
    raise ValueError(f"no qualified backup for task {task.id}")


def candidate_plans(twin: Twin, preset_id: str) -> tuple[Plan, ...]:
    """The three canonical options for a preset: wait, reassign to backup, contractor.

    For a client-meeting preset "wait" means queueing the new work behind the owner's current work.
    """
    twin = effective_twin(twin, preset_id)
    demand = _demand_of(twin, preset_id) is not None
    blocked = _blocked_days(twin, preset_id)
    task = _recovery_task(twin, preset_id)
    owner = twin.person(task.defaultAssigneeId)
    backup = twin.person(_backup_person_id(twin, task))
    contractor = twin.person(twin.contractor.personId)
    move = "Give" if demand else "Move"

    wait = _evaluate(
        twin,
        _schedule(twin, blocked, {}, True),
        plan_id=PLAN_WAIT,
        name=f"Queue behind {owner.name}'s current work" if demand else f"Wait for {owner.name}",
        summary=(
            f"Keep {task.name} with {owner.name} and start as soon as their current work is done."
            if demand
            else f"Keep {task.name} with {owner.name} and start when they are available again."
        ),
    )
    backup_plan = _evaluate(
        twin,
        _schedule(twin, blocked, {task.id: [backup.id]}, False),
        plan_id=PLAN_BACKUP,
        name=f"Reassign to {backup.name}",
        summary=(
            f"{move} {task.name} to {backup.name} from their first free day, without regard to "
            "their existing bookings."
        ),
    )
    contractor_plan = _evaluate(
        twin,
        _schedule(twin, blocked, {task.id: [contractor.id]}, True),
        plan_id=PLAN_CONTRACTOR,
        name=f"Bring in {contractor.name}",
        summary=(
            f"Assign {task.name} to {contractor.name} from their first available day at a fixed "
            "incremental cost."
        ),
    )
    return (wait, backup_plan, contractor_plan)


def revise_plan(twin: Twin, preset_id: str, rejected_plan_id: str) -> Plan:
    """Revise a rejected plan so it respects the objection (no double-booking). Only the backup
    reassignment is revisable; everything else is a caller error."""
    if rejected_plan_id != PLAN_BACKUP:
        raise ValueError(f"plan {rejected_plan_id} has no revision")
    twin = effective_twin(twin, preset_id)
    move = "Give" if _demand_of(twin, preset_id) is not None else "Move"
    blocked = _blocked_days(twin, preset_id)
    task = _recovery_task(twin, preset_id)
    backup = twin.person(_backup_person_id(twin, task))
    return _evaluate(
        twin,
        _schedule(twin, blocked, {task.id: [backup.id]}, True),
        plan_id=PLAN_BACKUP_REVISED,
        name=f"Reassign to {backup.name}, honoring existing bookings",
        summary=(
            f"{move} {task.name} to {backup.name} only on days they are actually free, keeping "
            "their existing commitments intact."
        ),
        status="revised",
        revises=PLAN_BACKUP,
    )


def all_plans(twin: Twin, preset_id: str) -> tuple[Plan, ...]:
    """Candidate plans plus the revision of the rejectable one (used for server-side lookup)."""
    return (*candidate_plans(twin, preset_id), revise_plan(twin, preset_id, PLAN_BACKUP))


def plan_conflicts(twin: Twin, preset_id: str, plan: Plan) -> tuple[str, ...]:
    """Feasibility problems found by re-checking a plan's own schedule (the Verifier's evidence).

    Independent of how the plan was built: existing bookings must be honored, nobody works two
    tasks on one day, and nobody works while unavailable. Missing a deadline is NOT a conflict;
    that is a trade-off the plan already reports in `violatedConstraints`.
    """
    twin = effective_twin(twin, preset_id)
    blocked = _blocked_days(twin, preset_id)
    available = _availability(twin, blocked)
    issues: list[str] = []

    for booking in twin.assignments:
        booked = list(booking.days())
        if any(day in blocked[booking.personId] for day in booked):
            continue  # the disruption itself displaces this booking; not the plan's doing
        planned = sorted(
            day
            for seg in plan.schedule
            if seg.taskId == booking.taskId and seg.personId == booking.personId
            for day in range(seg.startDay, seg.endDay + 1)
        )
        if planned != booked:
            person = twin.person(booking.personId)
            task = twin.task(booking.taskId)
            project = twin.project(task.projectId)
            moved = _days_text(planned) if planned else "none"
            issues.append(
                f"Displaces {person.name}'s existing booking on {task.name} ({project.name}), "
                f"day(s) {_days_text(booked)}: the plan moves that work to day(s) {moved}"
            )

    worked: dict[str, dict[int, int]] = {}
    for seg in plan.schedule:
        counts = worked.setdefault(seg.personId, {})
        for day in range(seg.startDay, seg.endDay + 1):
            counts[day] = counts.get(day, 0) + 1
    for person_id, counts in worked.items():
        name = twin.person(person_id).name
        doubled = sorted(day for day, n in counts.items() if n > 1)
        away = sorted(day for day in counts if day not in available[person_id])
        if doubled:
            issues.append(f"{name} is scheduled on two tasks on day(s) {_days_text(doubled)}")
        if away:
            issues.append(f"{name} is scheduled while unavailable on day(s) {_days_text(away)}")
    return tuple(issues)


def find_plan(twin: Twin, preset_id: str, plan_id: str) -> Plan:
    for plan in all_plans(twin, preset_id):
        if plan.id == plan_id:
            return plan
    raise PlanNotFoundError(plan_id)


# ---------------------------------------------------------------------------------------
# Investigation facts (impact, resources, finance)
# ---------------------------------------------------------------------------------------


def impact_report(twin: Twin, preset_id: str) -> ImpactReport:
    """Trace the disruption: affected tasks, the downstream chain, slips, exposure.

    For a client-meeting preset the "disruption" is the new work: it is placed with its default
    assignee and the report shows what that does to every commitment, old and new.
    """
    twin = effective_twin(twin, preset_id)
    demand = _demand_of(twin, preset_id)
    blocked = _blocked_days(twin, preset_id)
    baseline = _segments(twin, _schedule(twin, _blocked_days(twin, None), {}, True).allocated)
    disrupted = _segments(twin, _schedule(twin, blocked, {}, True).allocated)

    direct = _directly_affected(twin, preset_id)
    first = direct[0]
    affected_ids: list[str] = []
    for task in (*direct, *twin.downstream_tasks(first.id)):
        if task.id not in affected_ids:
            affected_ids.append(task.id)

    slips: list[MilestoneSlip] = []
    for milestone in twin.milestones:
        base = _milestone_completion(twin, milestone.id, baseline)
        after = _milestone_completion(twin, milestone.id, disrupted)
        met = after is not None and after <= milestone.dueDay
        late = 0 if met else ((after if after is not None else twin.horizonDays) - milestone.dueDay)
        slips.append(
            MilestoneSlip(
                milestoneId=milestone.id,
                name=milestone.name,
                dueDay=milestone.dueDay,
                baselineDay=base,
                disruptedDay=after,
                daysLate=late,
                met=met,
            )
        )

    missed = {s.milestoneId for s in slips if not s.met}
    commitments = tuple(c.id for c in twin.commitments if c.milestoneId in missed)
    invoices = tuple(
        InvoiceExposure(
            invoiceId=i.id,
            amount=i.amount,
            currency=i.currency,
            milestoneId=i.milestoneId,
            eligibleOnTime=i.milestoneId not in missed,
        )
        for i in twin.invoices
    )
    at_risk = sum(i.amount for i in invoices if not i.eligibleOnTime)
    owner = twin.person(first.defaultAssigneeId)
    preset = twin.preset(preset_id)
    window = preset.event.unavailable
    out_text = "; ".join(
        f"{twin.person(u.personId).name} out days "
        f"{_days_text(list(range(u.startDay, u.endDay + 1)))}"
        for u in window
    )

    facts: list[DerivedFact]
    if demand is not None:
        payload = preset.source.payload
        facts = [
            DerivedFact(label="Client request", value=demand.commitment.description, tag="fact"),
            DerivedFact(
                label="New work to place",
                value=(
                    f"{first.name}: {first.days} working days, due day {demand.milestone.dueDay}, "
                    f"default assignee {owner.name}"
                ),
                tag="fact",
            ),
            DerivedFact(
                label="Quoted value",
                value=f"{demand.invoice.amount} {demand.invoice.currency}",
                tag="fact",
            ),
        ]
        if payload.get("loggedBy"):
            by = f"{payload.get('loggedByRole', 'Staff')} ({payload['loggedBy']})"
            facts.append(DerivedFact(label="Logged in the CRM by", value=by, tag="fact"))
        shared = payload.get("sharedWith")
        if isinstance(shared, list) and shared:
            facts.append(
                DerivedFact(
                    label="Shared with", value=", ".join(str(s) for s in shared), tag="fact"
                )
            )
    else:
        facts = [
            DerivedFact(label="Disruption", value=out_text, tag="fact"),
            DerivedFact(
                label="Directly affected task",
                value=f"{first.name} (assignee {owner.name})",
                tag="calculated",
            ),
        ]
    facts.append(
        DerivedFact(
            label="Dependent work",
            value=", ".join(twin.task(t).name for t in affected_ids if t != first.id) or "none",
            tag="calculated",
        )
    )
    for slip in slips:
        facts.append(DerivedFact(label=f"{slip.name} due", value=f"day {slip.dueDay}", tag="fact"))
        facts.append(
            DerivedFact(
                label=f"{slip.name} finish with no action",
                value=f"day {slip.disruptedDay}" if slip.disruptedDay else "not within horizon",
                tag="calculated",
            )
        )
    for invoice in invoices:
        facts.append(
            DerivedFact(
                label=f"Invoice {invoice.invoiceId} eligible on time",
                value=(
                    f"{'yes' if invoice.eligibleOnTime else 'no'} "
                    f"({invoice.amount} {invoice.currency})"
                ),
                tag="calculated",
            )
        )
    facts.append(
        DerivedFact(
            label="Recovery budget",
            value=f"{twin.budget.recoveryBudget} {twin.budget.currency}",
            tag="fact",
        )
    )

    return ImpactReport(
        presetId=preset_id,
        affectedTaskIds=tuple(affected_ids),
        chain=twin.dependency_chain(first.id),
        slips=tuple(slips),
        commitmentsAtRisk=commitments,
        invoices=invoices,
        invoiceAtRisk=at_risk,
        recoveryBudget=twin.budget.recoveryBudget,
        contractorCost=twin.contractor.fixedCost,
        facts=tuple(facts),
    )


def resource_report(twin: Twin, preset_id: str) -> ResourceReport:
    """Who can actually take the disrupted work, given bookings and availability."""
    twin = effective_twin(twin, preset_id)
    demand = _demand_of(twin, preset_id)
    blocked = _blocked_days(twin, preset_id)
    avail = _availability(twin, blocked)
    task = _recovery_task(twin, preset_id)
    window = range(1, RESOURCE_WINDOW_DAYS + 1)
    booked: dict[str, set[int]] = {p.id: set() for p in twin.people}
    committed: dict[str, set[str]] = {p.id: set() for p in twin.people}  # tasks holding the days
    for booking in twin.assignments:
        booked[booking.personId].update(booking.days())
        committed[booking.personId].add(booking.taskId)
    if demand is not None:
        # New work competes with everything already scheduled, not just fixed bookings.
        baseline = _schedule(twin, _blocked_days(twin, None), {}, True)
        for task_id, allocated in baseline.allocated.items():
            if task_id == demand.task.id:
                continue
            for person_id, day in allocated:
                booked[person_id].add(day)
                committed[person_id].add(task_id)
    booking_tag: FactTag = "calculated" if demand is not None else "fact"

    candidates: list[PersonCapacity] = []
    facts: list[DerivedFact] = []
    for person in twin.people:
        if task.requiredSkill not in person.skills:
            continue
        unavailable = tuple(d for d in window if d not in avail[person.id])
        booked_days = tuple(d for d in window if d in booked[person.id] and d in avail[person.id])
        free = tuple(d for d in window if d in avail[person.id] and d not in booked[person.id])
        note = (
            f"free {_days_text(free)}; booked {_days_text(booked_days)}; "
            f"out {_days_text(unavailable)}"
        )
        candidates.append(
            PersonCapacity(
                personId=person.id,
                name=person.name,
                kind=person.kind,
                freeDays=free,
                bookedDays=booked_days,
                unavailableDays=unavailable,
                note=note,
            )
        )
        facts.append(
            DerivedFact(
                label=f"{person.name} free working days (1-{RESOURCE_WINDOW_DAYS})",
                value=_days_text(free),
                tag="calculated",
            )
        )
        if booked_days:
            project_names = sorted(
                {twin.project(twin.task(t).projectId).name for t in committed[person.id]}
            )
            facts.append(
                DerivedFact(
                    label=f"{person.name} existing bookings",
                    value=f"days {_days_text(booked_days)} on {', '.join(project_names)}",
                    tag=booking_tag,
                )
            )
    return ResourceReport(
        presetId=preset_id,
        requiredSkill=task.requiredSkill,
        windowEndDay=RESOURCE_WINDOW_DAYS,
        candidates=tuple(candidates),
        facts=tuple(facts),
    )


def finance_report(twin: Twin, preset_id: str) -> FinanceReport:
    """Money view: invoice exposure and budget fit per candidate plan."""
    twin = effective_twin(twin, preset_id)
    plans = candidate_plans(twin, preset_id)
    invoice_total = sum(i.amount for i in twin.invoices)

    def at_risk(plan: Plan) -> int:
        """Value of the invoices whose milestone this plan does not deliver on time."""
        total = 0
        for invoice in twin.invoices:
            done = _milestone_completion(twin, invoice.milestoneId, plan.schedule)
            if done is None or done > twin.milestone(invoice.milestoneId).dueDay:
                total += invoice.amount
        return total

    rows = tuple(
        PlanFinance(
            planId=p.id,
            incrementalCost=p.incrementalCost,
            budgetFit=p.budgetFit,
            invoiceEligible=p.invoiceEligible,
            invoiceAtRisk=at_risk(p),
        )
        for p in plans
    )
    currency = twin.budget.currency
    if len(twin.invoices) == 1:
        invoice_fact = DerivedFact(
            label="Invoice gated by the milestone", value=f"{invoice_total} {currency}", tag="fact"
        )
    else:
        listed = "; ".join(f"{i.id} {i.amount} {currency}" for i in twin.invoices)
        invoice_fact = DerivedFact(
            label="Invoices gated by milestones",
            value=f"{listed} (total {invoice_total} {currency})",
            tag="fact",
        )
    facts: list[DerivedFact] = [
        invoice_fact,
        DerivedFact(
            label="Recovery budget", value=f"{twin.budget.recoveryBudget} {currency}", tag="fact"
        ),
    ]
    for plan, row in zip(plans, rows, strict=True):
        facts.append(
            DerivedFact(
                label=f"{plan.name}: incremental cost",
                value=(
                    f"{row.incrementalCost} {currency} "
                    f"({'within' if row.budgetFit else 'over'} budget)"
                ),
                tag="calculated",
            )
        )
        facts.append(
            DerivedFact(
                label=f"{plan.name}: invoice eligible on time",
                value="yes"
                if row.invoiceEligible
                else f"no ({row.invoiceAtRisk} {currency} at risk)",
                tag="calculated",
            )
        )
    return FinanceReport(
        presetId=preset_id,
        recoveryBudget=twin.budget.recoveryBudget,
        invoiceAmount=invoice_total,
        plans=rows,
        facts=tuple(facts),
    )


# ---------------------------------------------------------------------------------------
# Apply a plan and verify the outcome (TASK-007)
# ---------------------------------------------------------------------------------------


def _state_from_schedule(
    twin: Twin, preset_id: str, plan_id: str, segments: tuple[Segment, ...]
) -> AppliedState:
    """Derive the resulting state purely from a schedule (independent of how it was produced)."""
    blocked = _blocked_days(twin, preset_id)
    avail = _availability(twin, blocked)
    milestones = []
    for m in twin.milestones:
        completion = _milestone_completion(twin, m.id, segments)
        milestones.append(
            AppliedMilestone(
                milestoneId=m.id,
                dueDay=m.dueDay,
                completionDay=completion,
                met=completion is not None and completion <= m.dueDay,
            )
        )
    by_id = {m.milestoneId: m for m in milestones}
    eligible = all(by_id[i.milestoneId].met for i in twin.invoices)

    conflicts: list[str] = []
    seen: dict[_Day, str] = {}
    for seg in segments:
        for day in range(seg.startDay, seg.endDay + 1):
            key = (seg.personId, day)
            if key in seen and seen[key] != seg.taskId:
                person = twin.person(seg.personId)
                conflicts.append(f"{person.name} is double-booked on day {day}")
            seen[key] = seg.taskId
            if day not in avail[seg.personId]:
                person = twin.person(seg.personId)
                conflicts.append(f"{person.name} is scheduled on day {day} while unavailable")

    worked: dict[str, list[int]] = {}
    for seg in segments:
        worked.setdefault(seg.taskId, []).extend(range(seg.startDay, seg.endDay + 1))
    for task in twin.tasks:
        days = worked.get(task.id, [])
        if days and len(days) != task.days:
            conflicts.append(
                f"{task.name} has {len(days)} of {task.days} required working days scheduled"
            )
        for dep_id in task.dependsOn:
            dep_days = worked.get(dep_id)
            if days and dep_days and min(days) <= max(dep_days):
                conflicts.append(
                    f"{task.name} starts on day {min(days)} before "
                    f"{twin.task(dep_id).name} finishes on day {max(dep_days)}"
                )

    cost = _cost(twin, segments)
    return AppliedState(
        presetId=preset_id,
        planId=plan_id,
        schedule=segments,
        projectCompletion=_project_completion(twin, segments),
        milestones=tuple(milestones),
        invoiceEligible=eligible,
        incrementalCost=cost,
        budgetRemaining=twin.budget.recoveryBudget - cost,
        conflicts=tuple(conflicts),
    )


def apply_plan(twin: Twin, preset_id: str, plan_id: str) -> AppliedState:
    """Apply an approved plan to the working twin. The plan is looked up and recomputed here:
    nothing the client sends is trusted. Unknown ids raise `PlanNotFoundError`."""
    twin = effective_twin(twin, preset_id)
    plan = find_plan(twin, preset_id, plan_id)
    return _state_from_schedule(twin, preset_id, plan.id, plan.schedule)


def verify_outcome(
    twin: Twin, preset_id: str, plan_id: str, applied: AppliedState | None = None
) -> OutcomeCheck:
    """Compare the state reached after execution with what the selected plan promised."""
    twin = effective_twin(twin, preset_id)
    plan = find_plan(twin, preset_id, plan_id)
    state = applied or apply_plan(twin, preset_id, plan_id)
    actual_state = _state_from_schedule(twin, preset_id, plan_id, state.schedule)

    expected: dict[str, object] = {
        "projectCompletion": dict(plan.projectCompletion),
        "deadlines": {d.name: d.met for d in plan.deadlines},
        "incrementalCost": plan.incrementalCost,
        "invoiceEligible": plan.invoiceEligible,
    }
    actual: dict[str, object] = {
        "projectCompletion": dict(actual_state.projectCompletion),
        "deadlines": {twin.milestone(m.milestoneId).name: m.met for m in actual_state.milestones},
        "incrementalCost": actual_state.incrementalCost,
        "invoiceEligible": actual_state.invoiceEligible,
    }

    deltas: list[Delta] = []
    for key in ("incrementalCost", "invoiceEligible"):
        if expected[key] != actual[key]:
            deltas.append(Delta(field=key, expected=str(expected[key]), actual=str(actual[key])))
    exp_pc = expected["projectCompletion"]
    act_pc = actual["projectCompletion"]
    assert isinstance(exp_pc, dict) and isinstance(act_pc, dict)
    for project in sorted(set(exp_pc) | set(act_pc)):
        if exp_pc.get(project) != act_pc.get(project):
            deltas.append(
                Delta(
                    field=f"projectCompletion.{project}",
                    expected=str(exp_pc.get(project)),
                    actual=str(act_pc.get(project)),
                )
            )
    exp_dl = expected["deadlines"]
    act_dl = actual["deadlines"]
    assert isinstance(exp_dl, dict) and isinstance(act_dl, dict)
    for name in sorted(set(exp_dl) | set(act_dl)):
        if exp_dl.get(name) != act_dl.get(name):
            deltas.append(
                Delta(
                    field=f"deadline.{name}",
                    expected=str(exp_dl.get(name)),
                    actual=str(act_dl.get(name)),
                )
            )
    for conflict in actual_state.conflicts:
        deltas.append(Delta(field="conflict", expected="none", actual=conflict))

    return OutcomeCheck(
        match=not deltas,
        expected=expected,
        actual=actual,
        deltas=tuple(deltas),
    )


__all__ = [
    "PLAN_BACKUP",
    "PLAN_BACKUP_REVISED",
    "PLAN_CONTRACTOR",
    "PLAN_WAIT",
    "PlanNotFoundError",
    "all_plans",
    "apply_plan",
    "candidate_plans",
    "effective_twin",
    "finance_report",
    "find_plan",
    "impact_report",
    "resource_report",
    "revise_plan",
    "verify_outcome",
]

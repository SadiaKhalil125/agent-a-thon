"""A typed leave event becomes a validated company model for the recovery agents."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from datahub import db
from datahub.event_twin import (
    DEMAND_PRESET_ID,
    HORIZON,
    MAX_EVENT_DAYS,
    PRESET_ID,
    ClientRequest,
    EventError,
    LeaveEvent,
    NoImpactError,
    build_demand_twin,
    build_leave_twin,
    calendar_dates,
    leave_between,
    working_calendar,
)
from twin import solver
from twin.seed import validate_twin


def person_id(name: str) -> int:
    return int(db.query("SELECT id FROM employees WHERE name = ?", (name,))[0]["id"])


def leave(name: str, start: str = "2026-12-01", days: int = 5) -> LeaveEvent:
    return LeaveEvent(
        personId=person_id(name), startDate=date.fromisoformat(start), workingDays=days
    )


def test_calendar_starts_today_and_skips_weekends_and_holidays() -> None:
    days = working_calendar()
    assert days[0] == date(2026, 12, 1) and len(days) == HORIZON
    assert all(d.weekday() < 5 for d in days)
    holidays = {r["date"] for r in db.query("SELECT date FROM holidays")}
    assert not holidays & {d.isoformat() for d in days}
    assert calendar_dates()[0] == "2026-12-01"


def test_dana_leave_builds_a_valid_twin_from_real_records() -> None:
    twin = build_leave_twin(leave("Dana Reyes"))
    validate_twin(twin)
    assert [p.name for p in twin.people][0] == "Dana Reyes"
    assert twin.people[2].kind == "contractor" and twin.contractor.personId == twin.people[2].id
    assert {t.id for t in twin.tasks} >= {"LOYALTY-8", "LOYALTY-33", "LOYALTY-11"}
    assert twin.milestones and twin.commitments and twin.invoices
    event = twin.preset(PRESET_ID).event.unavailable[0]
    assert (event.startDay, event.endDay) == (1, 5)


def test_the_four_plans_behave_like_the_recovery_flow() -> None:
    twin = build_leave_twin(leave("Dana Reyes"))
    plans = {p.id: p for p in solver.all_plans(twin, PRESET_ID)}
    assert set(plans) == {"plan-wait", "plan-backup", "plan-contractor", "plan-backup-revised"}
    assert plans["plan-wait"].deadlines[0].met is False  # waiting misses the delivery date
    assert solver.plan_conflicts(twin, PRESET_ID, plans["plan-backup"])  # naive cover double-books
    assert not solver.plan_conflicts(twin, PRESET_ID, plans["plan-backup-revised"])
    assert not solver.plan_conflicts(twin, PRESET_ID, plans["plan-contractor"])
    assert plans["plan-contractor"].incrementalCost == twin.contractor.fixedCost > 0
    assert plans["plan-contractor"].budgetFit is (
        twin.contractor.fixedCost <= twin.budget.recoveryBudget
    )


def test_every_number_is_derived_the_same_way_each_time() -> None:
    assert build_leave_twin(leave("Dana Reyes")) == build_leave_twin(leave("Dana Reyes"))


def test_a_later_start_maps_to_the_right_working_day_and_dates() -> None:
    twin = build_leave_twin(leave("Leo Tanaka", "2026-12-04", 3))  # Friday
    event = twin.preset(PRESET_ID).event.unavailable[0]
    assert (event.startDay, event.endDay) == (4, 6)  # Fri, Mon, Tue (weekend is not a day)
    assert twin.preset(PRESET_ID).source.payload["from"] == "2026-12-04"
    assert twin.preset(PRESET_ID).source.payload["to"] == "2026-12-08"


def test_existing_approved_leave_removes_that_persons_days() -> None:
    # Camila Kamara has approved leave 2026-12-02..04 in the records (working days 2..4).
    twin = build_leave_twin(leave("Camila Kamara", "2026-12-02", 6))
    camila = twin.people[0]
    assert all(not camila.is_available(d) for d in (2, 3, 4))
    assert camila.is_available(1)


def test_a_person_with_no_delivery_work_has_no_impact() -> None:
    with pytest.raises(NoImpactError, match="no open tickets"):
        build_leave_twin(leave("Caleb Zhang"))  # a sales person


def test_an_absence_after_the_work_is_done_has_no_impact() -> None:
    with pytest.raises(NoImpactError):
        build_leave_twin(leave("Dana Reyes", "2026-12-28", 1))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"startDate": date(2026, 11, 20)}, "past"),
        ({"startDate": date(2027, 3, 1)}, "after"),
    ],
)
def test_dates_outside_the_planned_window_are_refused(
    kwargs: dict[str, date], message: str
) -> None:
    event = LeaveEvent(personId=person_id("Dana Reyes"), workingDays=3, **kwargs)
    with pytest.raises(EventError, match=message):
        build_leave_twin(event)


def test_unknown_person_and_bad_lengths_are_refused() -> None:
    with pytest.raises(EventError, match="not in the company"):
        build_leave_twin(LeaveEvent(personId=99999, startDate=date(2026, 12, 2), workingDays=2))
    for days in (0, 16):
        with pytest.raises(ValidationError):
            LeaveEvent(personId=1, startDate=date(2026, 12, 2), workingDays=days)
    with pytest.raises(ValidationError):
        LeaveEvent.model_validate(
            {"personId": 1, "startDate": "2026-12-02", "workingDays": 2, "x": 1}
        )


# ---- a client asks for new work ---------------------------------------------------------


def request(**overrides: object) -> ClientRequest:
    base: dict[str, object] = {
        "kind": "demand",
        "accountId": 1,
        "title": "Audit-log export",
        "skill": "security",
        "days": 4,
        "dueDate": date(2026, 12, 10),
        "amount": 7500,
    }
    return ClientRequest(**{**base, **overrides})  # type: ignore[arg-type]


def test_a_client_request_becomes_a_valid_model_with_the_new_work_in_it() -> None:
    twin = build_demand_twin(request())
    validate_twin(twin)
    demand = twin.preset(DEMAND_PRESET_ID).event.demand
    assert demand is not None and demand.task.days == 4 and demand.invoice.amount == 7500
    assert demand.milestone.dueDay == 8  # Thursday 10 Dec is working day 8
    assert demand.task.defaultAssigneeId == twin.people[0].id
    assert demand.task.requiredSkill in twin.people[0].skills


def test_the_request_plans_differ_the_way_the_story_says() -> None:
    twin = build_demand_twin(request())
    plans = {p.id: p for p in solver.all_plans(twin, DEMAND_PRESET_ID)}
    conflicts = {k: solver.plan_conflicts(twin, DEMAND_PRESET_ID, p) for k, p in plans.items()}
    new_work_met = {k: [d.met for d in p.deadlines][-1] for k, p in plans.items()}
    assert new_work_met["plan-wait"] is False  # queued behind the owner's current work
    assert new_work_met["plan-backup"] is True and conflicts["plan-backup"]  # but it collides
    assert new_work_met["plan-backup-revised"] is True and not conflicts["plan-backup-revised"]
    assert plans["plan-contractor"].incrementalCost > 0


def test_the_request_model_is_deterministic() -> None:
    assert build_demand_twin(request()) == build_demand_twin(request())


def test_a_request_that_cannot_be_modelled_is_refused_in_plain_words() -> None:
    with pytest.raises(EventError, match="not in the company records"):
        build_demand_twin(request(accountId=999999))
    with pytest.raises(EventError, match="not a skill"):
        build_demand_twin(request(skill="juggling"))
    with pytest.raises(EventError, match="in the past"):
        build_demand_twin(request(dueDate=date(2026, 11, 1)))
    with pytest.raises(EventError, match="after the"):
        build_demand_twin(request(dueDate=date(2027, 3, 1)))
    with pytest.raises(ValidationError):
        request(days=11)


def test_leave_between_counts_working_days_and_caps_long_absences() -> None:
    pid = person_id("Marcus Lee")
    event = leave_between(pid, date(2026, 12, 3), date(2026, 12, 9))
    assert event.workingDays == 5  # Thu, Fri, Mon, Tue, Wed
    assert leave_between(pid, date(2026, 12, 1), date(2026, 12, 29)).workingDays == MAX_EVENT_DAYS
    with pytest.raises(EventError, match="no working days"):
        leave_between(pid, date(2026, 12, 5), date(2026, 12, 6))  # a weekend
    with pytest.raises(EventError, match="before the start"):
        leave_between(pid, date(2026, 12, 9), date(2026, 12, 3))

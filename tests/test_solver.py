"""TASK-006/007: deterministic solver (AT-IMP-001/002/003, AT-PLAN-001/002, AT-EXEC-002/003)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from twin import solver
from twin.results import AppliedState, Plan, Segment
from twin.seed import get_twin

PRIMARY = "dev-out-1-5"
SHORT = "dev-out-1-3"
LATE_CONTRACTOR = "dev-out-contractor-late"
FIXTURES = Path(__file__).parent / "fixtures"


def _plans(preset: str = PRIMARY) -> dict[str, Plan]:
    return {p.id: p for p in solver.candidate_plans(get_twin(), preset)}


# ---- impact chain (AT-IMP-001-01) ------------------------------------------------------


def test_impact_chain_covers_task_qa_milestone_commitment_invoice() -> None:
    report = solver.impact_report(get_twin(), PRIMARY)
    assert [(n.type, n.id) for n in report.chain] == [
        ("task", "T-A-INT"),
        ("task", "T-A-QA"),
        ("milestone", "M-A"),
        ("commitment", "CM-1"),
        ("invoice", "INV-1"),
    ]
    assert report.affectedTaskIds == ("T-A-INT", "T-A-QA")
    assert report.commitmentsAtRisk == ("CM-1",)


def test_impact_numbers_for_primary_preset() -> None:
    report = solver.impact_report(get_twin(), PRIMARY)
    slip_a = next(s for s in report.slips if s.milestoneId == "M-A")
    assert (slip_a.baselineDay, slip_a.disruptedDay, slip_a.dueDay) == (6, 11, 6)
    assert slip_a.daysLate == 5 and not slip_a.met
    slip_b = next(s for s in report.slips if s.milestoneId == "M-B")
    assert slip_b.met and slip_b.daysLate == 0
    assert report.invoiceAtRisk == 8000
    assert report.recoveryBudget == 2000
    assert {f.tag for f in report.facts} <= {"fact", "calculated", "estimate"}


def test_shorter_absence_slips_less() -> None:
    slip = next(s for s in solver.impact_report(get_twin(), SHORT).slips if s.milestoneId == "M-A")
    assert slip.disruptedDay == 9 and slip.daysLate == 3


# ---- plans (AT-PLAN-001/002, AT-IMP-002/003) -------------------------------------------


def test_three_distinct_plans_with_comparable_fields() -> None:
    plans = solver.candidate_plans(get_twin(), PRIMARY)
    assert [p.id for p in plans] == [solver.PLAN_WAIT, solver.PLAN_BACKUP, solver.PLAN_CONTRACTOR]
    assert len({p.name for p in plans}) == 3
    for plan in plans:
        assert set(plan.projectCompletion) == {"A", "B"}
        assert plan.deadlines and plan.schedule
        assert isinstance(plan.incrementalCost, int)


def test_wait_plan_numbers() -> None:
    plan = _plans()[solver.PLAN_WAIT]
    assert plan.projectCompletion == {"A": 11, "B": 3}
    assert plan.incrementalCost == 0 and plan.budgetFit
    assert not plan.invoiceEligible
    assert [d.met for d in plan.deadlines] == [False, True]


def test_contractor_plan_meets_deadline_within_budget() -> None:
    plan = _plans()[solver.PLAN_CONTRACTOR]
    assert plan.projectCompletion == {"A": 6, "B": 3}
    assert plan.incrementalCost == 1500 and plan.budgetFit
    assert plan.invoiceEligible
    assert plan.violatedConstraints == ()
    assert plan.schedule[0] == Segment(taskId="T-A-INT", personId="PER-CTR", startDay=1, endDay=4)


def test_backup_plan_double_books_project_b_and_is_rejectable() -> None:
    plan = _plans()[solver.PLAN_BACKUP]
    assert plan.projectCompletion == {"A": 7, "B": 7}
    assert not plan.invoiceEligible
    assert any("Double-books Marcus Lee" in v for v in plan.violatedConstraints)
    assert any("Project B" in v for v in plan.violatedConstraints)
    assert [d.met for d in plan.deadlines] == [False, False]


def test_revised_backup_plan_honors_bookings_but_still_misses_the_milestone() -> None:
    revised = solver.revise_plan(get_twin(), PRIMARY, solver.PLAN_BACKUP)
    assert revised.status == "revised" and revised.revisesPlanId == solver.PLAN_BACKUP
    assert revised.projectCompletion == {"A": 9, "B": 3}
    assert not any("Double-books" in v for v in revised.violatedConstraints)
    backup_days = [(s.startDay, s.endDay) for s in revised.schedule if s.personId == "PER-BACKUP"]
    assert (4, 7) in backup_days  # only the days Marcus is actually free


def test_no_plan_ever_schedules_a_person_twice_or_while_unavailable_except_the_rejected_one() -> (
    None
):
    twin = get_twin()
    for preset in twin.presets:
        for plan in solver.all_plans(twin, preset.id):
            state = solver.apply_plan(twin, preset.id, plan.id)
            assert state.conflicts == (), (preset.id, plan.id, state.conflicts)


def test_when_no_plan_can_meet_the_deadline_each_names_the_violated_constraint() -> None:
    plans = _plans(LATE_CONTRACTOR)
    assert all(not p.invoiceEligible for p in plans.values())
    assert plans[solver.PLAN_CONTRACTOR].projectCompletion["A"] == 8
    for plan in plans.values():
        assert any("Project A acceptance" in v for v in plan.violatedConstraints)


def test_finance_report_ties_cost_to_budget_and_invoice() -> None:
    report = solver.finance_report(get_twin(), PRIMARY)
    by_plan = {p.planId: p for p in report.plans}
    assert report.invoiceAmount == 8000 and report.recoveryBudget == 2000
    assert by_plan[solver.PLAN_CONTRACTOR].invoiceAtRisk == 0
    assert by_plan[solver.PLAN_WAIT].invoiceAtRisk == 8000
    assert by_plan[solver.PLAN_CONTRACTOR].budgetFit


def test_resource_report_shows_the_backups_real_free_days() -> None:
    report = solver.resource_report(get_twin(), PRIMARY)
    by_id = {c.personId: c for c in report.candidates}
    assert "PER-QA" not in by_id  # lacks the required skill
    assert by_id["PER-BACKUP"].bookedDays == (2, 3)
    assert by_id["PER-BACKUP"].freeDays == (4, 5, 6, 7, 8, 9, 10)
    assert by_id["PER-DEV1"].freeDays == (6, 7, 8, 9, 10)
    assert by_id["PER-CTR"].freeDays == tuple(range(1, 11))


def test_solver_is_deterministic() -> None:
    twin = get_twin()
    assert solver.candidate_plans(twin, PRIMARY) == solver.candidate_plans(twin, PRIMARY)
    assert solver.impact_report(twin, PRIMARY) == solver.impact_report(twin, PRIMARY)


# ---- apply and outcome (AT-EXEC-002/003) -----------------------------------------------


def test_apply_contractor_plan_updates_state() -> None:
    state = solver.apply_plan(get_twin(), PRIMARY, solver.PLAN_CONTRACTOR)
    assert state.projectCompletion == {"A": 6, "B": 3}
    assert state.invoiceEligible and state.incrementalCost == 1500
    assert state.budgetRemaining == 500
    assert all(m.met for m in state.milestones)
    assert state.conflicts == ()


def test_outcome_matches_for_every_known_plan() -> None:
    twin = get_twin()
    for plan in solver.all_plans(twin, PRIMARY):
        check = solver.verify_outcome(twin, PRIMARY, plan.id)
        assert check.match, (plan.id, check.deltas)
        assert check.deltas == ()


def test_outcome_reports_a_mismatch_when_the_applied_state_drifts() -> None:
    twin = get_twin()
    applied = solver.apply_plan(twin, PRIMARY, solver.PLAN_CONTRACTOR)
    drifted_schedule = tuple(
        s.model_copy(update={"startDay": s.startDay + 3, "endDay": s.endDay + 3})
        if s.taskId == "T-A-QA"
        else s
        for s in applied.schedule
    )
    drifted: AppliedState = applied.model_copy(update={"schedule": drifted_schedule})
    check = solver.verify_outcome(twin, PRIMARY, solver.PLAN_CONTRACTOR, drifted)
    assert not check.match
    fields = {d.field for d in check.deltas}
    assert "projectCompletion.A" in fields
    assert "invoiceEligible" in fields


def test_unknown_plan_or_preset_is_refused() -> None:
    twin = get_twin()
    with pytest.raises(solver.PlanNotFoundError):
        solver.apply_plan(twin, PRIMARY, "plan-made-up")
    with pytest.raises(KeyError):
        solver.candidate_plans(twin, "no-such-preset")


def test_revision_exists_only_for_the_backup_plan() -> None:
    with pytest.raises(ValueError):
        solver.revise_plan(get_twin(), PRIMARY, solver.PLAN_CONTRACTOR)


# ---- boundaries ------------------------------------------------------------------------


def test_solver_has_no_model_or_io_dependencies() -> None:
    tree = ast.parse(Path(solver.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "dataclasses", "twin"}, imported


# ---- golden payloads for the UI track (checkpoint C1) ----------------------------------


def _golden() -> dict[str, object]:
    twin = get_twin()
    out: dict[str, object] = {}
    for preset in twin.presets:
        out[preset.id] = {
            "impact": solver.impact_report(twin, preset.id).model_dump(mode="json"),
            "resources": solver.resource_report(twin, preset.id).model_dump(mode="json"),
            "finance": solver.finance_report(twin, preset.id).model_dump(mode="json"),
            "candidatePlans": [
                p.model_dump(mode="json") for p in solver.candidate_plans(twin, preset.id)
            ],
            "revisedPlan": solver.revise_plan(twin, preset.id, solver.PLAN_BACKUP).model_dump(
                mode="json"
            ),
            "applied": {
                p.id: solver.apply_plan(twin, preset.id, p.id).model_dump(mode="json")
                for p in solver.all_plans(twin, preset.id)
            },
            "outcome": {
                p.id: solver.verify_outcome(twin, preset.id, p.id).model_dump(mode="json")
                for p in solver.all_plans(twin, preset.id)
            },
        }
    return out


def test_golden_payloads_are_current() -> None:
    """tests/fixtures/solver_golden.json is what the UI track diffs its mocks against.
    Regenerate deliberately with: UPDATE_GOLDEN=1 pytest tests/test_solver.py"""
    import os

    path = FIXTURES / "solver_golden.json"
    current = _golden()
    if os.environ.get("UPDATE_GOLDEN") == "1":
        FIXTURES.mkdir(exist_ok=True)
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(current))


# ---- plan_conflicts: the Verifier's independent feasibility re-check -------------------


def test_only_the_naive_backup_plan_has_conflicts_in_every_preset() -> None:
    twin = get_twin()
    for preset in ("dev-out-1-3", "dev-out-1-5", "dev-out-contractor-late"):
        conflicts = {
            p.id: solver.plan_conflicts(twin, preset, p) for p in solver.all_plans(twin, preset)
        }
        assert [pid for pid, found in conflicts.items() if found] == ["plan-backup"], preset
        (message,) = conflicts["plan-backup"]
        assert "Displaces Marcus Lee's existing booking on Billing hotfix" in message
        assert "day(s) 2-3" in message


def test_plan_conflicts_detects_double_booking_and_unavailability() -> None:
    twin = get_twin()
    plan = solver.find_plan(twin, "dev-out-1-5", "plan-contractor")
    segments = list(plan.schedule)
    # Dana is out days 1-5: put her on day 3, and put the contractor on two tasks the same day.
    away = segments[0].model_copy(update={"personId": "PER-DEV1", "startDay": 3, "endDay": 3})
    clash = [
        segments[0].model_copy(update={"taskId": "T-A-INT", "startDay": 1, "endDay": 1}),
        segments[0].model_copy(update={"taskId": "T-A-QA", "startDay": 1, "endDay": 1}),
    ]
    broken = plan.model_copy(update={"schedule": (*segments, away, *clash)})
    text = " | ".join(solver.plan_conflicts(twin, "dev-out-1-5", broken))
    assert "Dana Reyes is scheduled while unavailable on day(s) 3" in text
    assert "scheduled on two tasks on day(s) 1" in text


def test_missing_a_deadline_is_a_trade_off_not_a_conflict() -> None:
    twin = get_twin()
    wait = solver.find_plan(twin, "dev-out-1-5", "plan-wait")
    assert wait.violatedConstraints  # it misses day 6 ...
    assert solver.plan_conflicts(twin, "dev-out-1-5", wait) == ()  # ... but it is feasible

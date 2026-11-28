"""TASK-004/005: seed loads, validates and exposes the dependency chain (AT-TWIN-001-01)."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from twin.model import Twin
from twin.seed import SEED_PATH, SeedValidationError, get_twin, load_seed, parse_seed


def _raw() -> dict[str, Any]:
    return copy.deepcopy(json.loads(SEED_PATH.read_text(encoding="utf-8")))


def test_seed_loads_with_all_required_entity_types() -> None:
    twin = load_seed()
    assert isinstance(twin, Twin)
    assert twin.company.name == "Northstar Systems"
    for collection in (
        twin.projects,
        twin.tasks,
        twin.people,
        twin.milestones,
        twin.commitments,
        twin.invoices,
        twin.customers,
    ):
        assert len(collection) >= 1
    assert twin.budget.recoveryBudget == 2000
    assert twin.contractor.fixedCost == 1500


def test_every_invoice_links_to_a_milestone_and_every_milestone_to_a_task() -> None:
    twin = get_twin()
    milestone_ids = {m.id for m in twin.milestones}
    task_ids = {t.id for t in twin.tasks}
    assert all(i.milestoneId in milestone_ids for i in twin.invoices)
    assert all(m.gatedByTaskIds for m in twin.milestones)
    assert all(set(m.gatedByTaskIds) <= task_ids for m in twin.milestones)


def test_primary_scenario_numbers_match_the_prd() -> None:
    twin = get_twin()
    assert twin.milestone("M-A").dueDay == 6
    assert twin.task("T-A-INT").days == 4
    assert twin.task("T-A-QA").days == 2
    assert twin.invoices[0].amount == 8000
    assert twin.milestone("M-B").dueDay == 4
    backup_booking = next(a for a in twin.assignments if a.personId == "PER-BACKUP")
    assert (backup_booking.startDay, backup_booking.endDay) == (2, 3)
    assert twin.person("PER-CTR").kind == "contractor"


def test_at_least_three_presets_from_two_or_more_systems() -> None:
    twin = get_twin()
    assert len(twin.presets) >= 3
    assert len({p.source.system for p in twin.presets}) >= 2
    primary = twin.preset("dev-out-1-5")
    assert [(u.personId, u.startDay, u.endDay) for u in primary.event.unavailable] == [
        ("PER-DEV1", 1, 5)
    ]


def test_dependency_chain_follows_real_relationships() -> None:
    twin = get_twin()
    chain = twin.dependency_chain("T-A-INT")
    assert [(n.type, n.id) for n in chain] == [
        ("task", "T-A-INT"),
        ("task", "T-A-QA"),
        ("milestone", "M-A"),
        ("commitment", "CM-1"),
        ("invoice", "INV-1"),
    ]
    assert [t.id for t in twin.downstream_tasks("T-A-INT")] == ["T-A-QA"]
    assert twin.downstream_tasks("T-A-QA") == ()


def test_get_twin_is_cached_and_immutable() -> None:
    assert get_twin() is get_twin()
    with pytest.raises(Exception):  # noqa: B017 - pydantic frozen-instance error
        get_twin().budget.recoveryBudget = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda d: d["invoices"][0].update(milestoneId="M-NOPE"),
            "not linked to a known milestone",
        ),
        (lambda d: d["milestones"][0].update(gatedByTaskIds=[]), "gated by no task"),
        (lambda d: d["tasks"][1].update(dependsOn=["T-A-QA"]), "depends on itself"),
        (
            lambda d: d["tasks"][0].update(dependsOn=["T-A-QA"]),
            "dependency cycle",
        ),
        (
            lambda d: d["people"][0]["availability"].append({"startDay": 5, "endDay": 9}),
            "overlapping windows",
        ),
        (
            lambda d: d["people"][0].update(availability=[{"startDay": 9, "endDay": 3}]),
            "after endDay",
        ),
        (lambda d: d["tasks"][0].update(defaultAssigneeId="PER-NOPE"), "unknown default assignee"),
        (lambda d: d["tasks"][0].update(requiredSkill="cooking"), "lacks skill"),
        (
            lambda d: d["assignments"].append(
                {"taskId": "T-A-INT", "personId": "PER-BACKUP", "startDay": 3, "endDay": 4}
            ),
            "double-booked",
        ),
        (lambda d: d["contractor"].update(personId="PER-DEV1"), "not of kind contractor"),
        (
            lambda d: d["presets"][0]["event"]["unavailable"][0].update(personId="PER-NOPE"),
            "unknown person",
        ),
        (lambda d: d["projects"].append(dict(d["projects"][0])), "duplicate id"),
        (lambda d: d["budget"].update(recoveryBudget=-1), "recoveryBudget"),
        (lambda d: d["tasks"][0].update(surprise=1), "surprise"),
        (
            lambda d: d["people"][0].update(source={"system": "erp", "externalId": "X-1"}),
            "source system must be hris",
        ),
        (
            lambda d: d["people"][1].update(source=dict(d["people"][0]["source"])),
            "duplicate source id",
        ),
    ],
)
def test_invalid_seeds_are_rejected_with_a_clear_reason(mutate: Any, expected: str) -> None:
    data = _raw()
    mutate(data)
    with pytest.raises(SeedValidationError) as info:
        parse_seed(data)
    assert expected in str(info.value)
    assert info.value.problems

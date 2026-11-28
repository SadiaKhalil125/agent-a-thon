"""The client-meeting scenario: Business Development logs new client work, the same agents decide.

No new agent: the existing Impact, HR/Resource, Finance, Planner and Verifier work from one CRM
record. The solver stays the only source of numbers; the model is a fake in every test here.
"""

from __future__ import annotations

import asyncio
import copy
import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage

from agents import llm
from app import app
from orchestration.runner import prepare_run, stream_run
from twin import solver
from twin.seed import SEED_PATH, SeedValidationError, get_twin, parse_seed

PRESET = "client-meeting-loyalty"
client = TestClient(app, raise_server_exceptions=False)
Event = tuple[str, dict[str, Any]]


def fake() -> llm.ScriptedChatModel:
    """Role-aware fake model: the Planner first picks the unsafe backup, then the contractor."""
    planner_calls = {"n": 0}

    def respond(messages: list[BaseMessage]) -> str:
        match = re.match(r"You are the (.+?) for Northstar", str(messages[0].content))
        assert match, "unexpected system prompt"
        role = match.group(1)
        if role == "Planner":
            planner_calls["n"] += 1
            chosen = "plan-backup" if planner_calls["n"] == 1 else "plan-contractor"
            return json.dumps({"recommendedPlanId": chosen, "rationale": f"Go with {chosen}."})
        return f"{role}: findings written from the engine facts."

    return llm.ScriptedChatModel(responder=respond)


def run_events(model: llm.ScriptedChatModel, preset: str) -> list[Event]:
    prepared = prepare_run(preset, model=model, max_calls=8)

    async def collect() -> list[Event]:
        return [item async for item in stream_run(prepared)]

    return asyncio.run(collect())


def completed(events: list[Event]) -> list[dict[str, Any]]:
    return [data for name, data in events if name == "node_completed"]


def done_of(events: list[Event]) -> dict[str, Any]:
    return dict(events)["done"]


def _plans() -> dict[str, Any]:
    return {p.id: p for p in solver.all_plans(get_twin(), PRESET)}


def _seed() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return data


def _meeting(data: dict[str, Any]) -> dict[str, Any]:
    preset: dict[str, Any] = next(p for p in data["presets"] if p["id"] == PRESET)
    return preset


# ---- the scenario's numbers (solver only) -----------------------------------------------


def test_the_new_work_is_added_only_inside_this_scenario() -> None:
    twin = get_twin()
    merged = solver.effective_twin(twin, PRESET)
    assert "T-C-LOY" in {t.id for t in merged.tasks} and "T-C-LOY" not in {t.id for t in twin.tasks}
    assert solver.effective_twin(merged, PRESET) is merged  # idempotent
    for other in ("dev-out-1-5", "dev-out-1-3", "dev-out-contractor-late"):
        assert solver.effective_twin(twin, other) is twin  # old scenarios are untouched


def test_the_four_options_and_what_each_does_to_every_commitment() -> None:
    plans = _plans()

    def view(pid: str) -> tuple[dict[str, int | None], int, tuple[str, ...]]:
        p = plans[pid]
        missed = tuple(d.name for d in p.deadlines if not d.met)
        return dict(p.projectCompletion), p.incrementalCost, missed

    # Queued behind Dana: free, but the new work lands one day late.
    assert view("plan-wait") == ({"A": 6, "B": 3, "C": 9}, 0, ("Project C delivery",))
    # Naive reassignment to Marcus: fast, but wrecks the Billing hotfix he is booked on.
    assert view("plan-backup")[0] == {"A": 6, "B": 8, "C": 6}
    assert view("plan-backup")[2] == ("Project B delivery",)
    # Revised: free and on time, but with zero slack (done exactly on day 8).
    assert view("plan-backup-revised") == ({"A": 6, "B": 3, "C": 8}, 0, ())
    # Contractor: 1500 USD buys three days of slack.
    assert view("plan-contractor") == ({"A": 6, "B": 3, "C": 5}, 1500, ())


def test_only_the_naive_backup_is_infeasible_and_the_reason_names_the_victim() -> None:
    twin = get_twin()
    found = {pid: solver.plan_conflicts(twin, PRESET, p) for pid, p in _plans().items()}
    assert [pid for pid, issues in found.items() if issues] == ["plan-backup"]
    (message,) = found["plan-backup"]
    assert "Displaces Marcus Lee's existing booking on Billing hotfix" in message


def test_the_impact_report_carries_the_crm_record_shared_with_other_departments() -> None:
    report = solver.impact_report(get_twin(), PRESET)
    facts = {f.label: f for f in report.facts}
    assert "loyalty API add-on" in facts["Client request"].value
    assert facts["Client request"].tag == "fact"
    assert facts["Quoted value"].value == "6000 USD"
    assert facts["Logged in the CRM by"].value == "Business Development (bd.lead@example.com)"
    assert facts["Shared with"].value == "sales, hr, finance"
    assert facts["Project C delivery finish with no action"].value == "day 9"
    assert [n.id for n in report.chain] == ["T-C-LOY", "M-C", "CM-3", "INV-2"]
    assert report.invoiceAtRisk == 6000  # only the new invoice is at risk when queued


def test_hr_sees_who_is_really_free_after_their_scheduled_work() -> None:
    facts = {f.label: f for f in solver.resource_report(get_twin(), PRESET).facts}
    assert facts["Dana Reyes existing bookings"].value.startswith("days 1-4 on Project A")
    assert facts["Dana Reyes free working days (1-10)"].value == "5-10"
    assert facts["Marcus Lee free working days (1-10)"].value == "4-10"
    assert facts["Priya Nair (contractor) free working days (1-10)"].value == "1-10"
    assert facts["Dana Reyes existing bookings"].tag == "calculated"  # derived, not a seed fact


def test_finance_counts_each_invoice_separately() -> None:
    report = solver.finance_report(get_twin(), PRESET)
    at_risk = {row.planId: row.invoiceAtRisk for row in report.plans}
    assert at_risk == {"plan-wait": 6000, "plan-backup": 0, "plan-contractor": 0}
    assert report.invoiceAmount == 14000
    assert report.facts[0].label == "Invoices gated by milestones"
    assert "INV-1 8000 USD; INV-2 6000 USD" in report.facts[0].value


def test_every_option_applies_cleanly_and_the_outcome_matches() -> None:
    twin = get_twin()
    for pid in _plans():
        assert solver.apply_plan(twin, PRESET, pid).conflicts == (), pid
        assert solver.verify_outcome(twin, PRESET, pid).match, pid


# ---- seed validation of a demand --------------------------------------------------------


def test_a_demand_that_collides_with_an_existing_id_is_refused() -> None:
    data = copy.deepcopy(_seed())
    _meeting(data)["event"]["demand"]["task"]["id"] = "T-A-INT"
    with pytest.raises(SeedValidationError) as err:
        parse_seed(data)
    assert "duplicate id T-A-INT" in str(err.value)


def test_a_demand_must_be_internally_consistent() -> None:
    data = copy.deepcopy(_seed())
    _meeting(data)["event"]["demand"]["invoice"]["milestoneId"] = "M-A"
    with pytest.raises(SeedValidationError) as err:
        parse_seed(data)
    assert "demand invoice is not on the demand milestone" in str(err.value)


def test_a_demand_with_an_unknown_assignee_or_a_late_milestone_is_refused() -> None:
    data = copy.deepcopy(_seed())
    demand = _meeting(data)["event"]["demand"]
    demand["task"]["defaultAssigneeId"] = "PER-NOPE"
    demand["milestone"]["dueDay"] = 99
    with pytest.raises(SeedValidationError) as err:
        parse_seed(data)
    text = str(err.value)
    assert "unknown default assignee PER-NOPE" in text and "dueDay beyond horizon" in text


def test_a_preset_with_neither_absence_nor_demand_is_refused() -> None:
    data = copy.deepcopy(_seed())
    _meeting(data)["event"] = {"unavailable": []}
    with pytest.raises(SeedValidationError) as err:
        parse_seed(data)
    assert "no unavailability and no demand" in str(err.value)


# ---- the full agent run (fake model) -----------------------------------------------------


def test_the_same_five_agents_run_with_no_new_agent_and_the_same_loop() -> None:
    model = fake()
    events = run_events(model, PRESET)
    steps = [(c["node"], c["status"]) for c in completed(events)]
    assert steps[0] == ("impact", "done")
    assert {steps[1][0], steps[2][0]} == {"hr_resource", "finance"}
    assert steps[3:] == [
        ("planner", "done"),
        ("verifier", "rejected"),
        ("planner", "revised"),
        ("verifier", "done"),
    ]
    assert model.call_count == 7
    assert {c["node"] for c in completed(events)} == {
        "impact",
        "hr_resource",
        "finance",
        "planner",
        "verifier",
    }


def test_the_run_streams_the_demand_and_ends_with_four_plans_including_project_c() -> None:
    events = run_events(fake(), PRESET)
    started = dict(events)["run_started"]
    assert started["event"]["demand"]["task"]["id"] == "T-C-LOY"
    done = done_of(events)
    plans = {p["id"]: p for p in done["plans"]}
    assert {pid: p["status"] for pid, p in plans.items()} == {
        "plan-wait": "verified",
        "plan-backup": "rejected",
        "plan-contractor": "verified",
        "plan-backup-revised": "revised",
    }
    assert plans["plan-contractor"]["projectCompletion"] == {"A": 6, "B": 3, "C": 5}
    assert any(d["name"] == "Project C delivery" for d in plans["plan-contractor"]["deadlines"])


def test_old_scenarios_stream_exactly_the_event_they_always_did() -> None:
    started = dict(run_events(fake(), "dev-out-1-5"))["run_started"]  # same stream as before
    assert set(started["event"]) == {"unavailable"}  # no `demand` key appears for them


# ---- the API ----------------------------------------------------------------------------


def test_execute_applies_a_safe_plan_and_refuses_the_unsafe_one() -> None:
    refused = client.post(
        "/api/execute", json={"presetId": PRESET, "approvedPlanId": "plan-backup"}
    )
    assert refused.status_code == 409 and refused.json()["code"] == "PlanRejected"

    ok = client.post("/api/execute", json={"presetId": PRESET, "approvedPlanId": "plan-contractor"})
    assert ok.status_code == 200
    twin = ok.json()["twin"]
    assert twin["projectCompletion"] == {"A": 6, "B": 3, "C": 5}
    assert twin["invoiceEligible"] is True and twin["budgetRemaining"] == 500
    assert {m["milestoneId"] for m in twin["milestones"]} == {"M-A", "M-B", "M-C"}


def test_outcome_accepts_the_new_task_in_the_returned_twin_and_catches_tampering() -> None:
    body = {"presetId": PRESET, "approvedPlanId": "plan-contractor"}
    twin = client.post("/api/execute", json=body).json()["twin"]
    clean = client.post("/api/outcome", json={**body, "twin": twin})
    assert clean.status_code == 200 and clean.json()["match"] is True

    tampered = copy.deepcopy(twin)
    loyalty = next(s for s in tampered["schedule"] if s["taskId"] == "T-C-LOY")
    loyalty["startDay"], loyalty["endDay"] = 6, 10  # pushed past its due day
    bad = client.post("/api/outcome", json={**body, "twin": tampered})
    assert bad.status_code == 200 and bad.json()["match"] is False


def test_the_base_company_state_does_not_contain_the_new_work() -> None:
    state = client.post("/api/reset").json()
    assert "T-C-LOY" not in {t["id"] for t in state["tasks"]}
    assert {p["id"] for p in state["projects"]} == {"P-A", "P-B"}


def test_the_crm_exposes_the_meeting_record_the_departments_share() -> None:
    res = client.get("/mock/crm/meetings")
    assert res.status_code == 200 and res.headers["x-simulated"] == "true"
    (meeting,) = res.json()
    assert meeting["loggedByRole"] == "Business Development"
    assert meeting["sharedWith"] == ["sales", "hr", "finance"]
    assert (meeting["estimateDays"], meeting["requestedDueDay"], meeting["quotedValue"]) == (
        5,
        8,
        6000,
    )
    manifest = client.get("/api/integrations").json()
    crm = next(m for m in manifest if m["id"] == "crm")
    assert "/mock/crm/meetings" in {e["path"] for e in crm["endpoints"]}

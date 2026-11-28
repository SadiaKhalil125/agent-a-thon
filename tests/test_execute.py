"""TASK-014: approval gate, execute, outcome, reset (AT-EXEC-001 to 004)."""

from __future__ import annotations

import socket
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agents import llm
from app import app
from twin import solver
from twin.seed import get_twin

client = TestClient(app, raise_server_exceptions=False)
PRESET = "dev-out-1-5"


def execute(plan_id: str, preset: str = PRESET) -> Any:
    return client.post("/api/execute", json={"presetId": preset, "approvedPlanId": plan_id})


def outcome(plan_id: str, **extra: Any) -> Any:
    return client.post(
        "/api/outcome", json={"presetId": PRESET, "approvedPlanId": plan_id, **extra}
    )


# ---- approval gate (AT-EXEC-001-01) ----------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"presetId": PRESET},
        {"presetId": PRESET, "approvedPlanId": ""},
        {"presetId": PRESET, "approvedPlanId": "plan nope"},
        {"approvedPlanId": "plan-contractor"},
        {"presetId": PRESET, "approvedPlanId": "plan-nope"},
        {"presetId": "nope", "approvedPlanId": "plan-contractor"},
    ],
)
def test_nothing_is_applied_without_an_approved_valid_plan(body: dict[str, str]) -> None:
    before = client.get("/api/state").text
    response = client.post("/api/execute", json=body)
    assert response.status_code == 400
    assert response.json()["code"] == "ValidationError"
    assert "twin" not in response.json() and "applied" not in response.json()
    assert client.get("/api/state").text == before  # no state change


def test_the_verifier_rejected_plan_can_never_be_approved() -> None:
    response = execute("plan-backup")
    assert response.status_code == 409
    assert response.json() == {
        "error": "This plan was rejected by the verifier and cannot be approved.",
        "code": "PlanRejected",
    }
    assert outcome("plan-backup").status_code == 409  # the same gate guards the outcome check


def test_the_gate_is_the_engines_check_not_a_client_claim() -> None:
    twin = get_twin()
    for preset in ("dev-out-1-3", "dev-out-1-5", "dev-out-contractor-late"):
        for plan in solver.all_plans(twin, preset):
            expected = 409 if solver.plan_conflicts(twin, preset, plan) else 200
            assert execute(plan.id, preset).status_code == expected, (preset, plan.id)


# ---- apply (AT-EXEC-002-01) ------------------------------------------------------------


def test_approving_the_contractor_plan_applies_its_schedule() -> None:
    response = execute("plan-contractor")
    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    twin = body["twin"]
    plan = solver.find_plan(get_twin(), PRESET, "plan-contractor").model_dump(mode="json")
    assert twin["schedule"] == plan["schedule"]
    assert twin["projectCompletion"] == {"A": 6, "B": 3}
    assert twin["incrementalCost"] == 1500 and twin["budgetRemaining"] == 500
    assert twin["invoiceEligible"] is True and twin["conflicts"] == []
    assert {m["milestoneId"]: m["met"] for m in twin["milestones"]} == {"M-A": True, "M-B": True}


def test_each_approvable_plan_applies_its_own_numbers() -> None:
    twin = get_twin()
    for plan_id in ("plan-wait", "plan-backup-revised", "plan-contractor"):
        applied = execute(plan_id).json()["twin"]
        plan = solver.find_plan(twin, PRESET, plan_id)
        assert applied["planId"] == plan_id
        assert applied["projectCompletion"] == plan.projectCompletion
        assert applied["incrementalCost"] == plan.incrementalCost


def test_execute_is_repeatable_and_stateless() -> None:
    assert execute("plan-contractor").text == execute("plan-contractor").text
    other = execute("plan-wait").json()["twin"]
    assert other["projectCompletion"] == {"A": 11, "B": 3}  # not polluted by the earlier call


# ---- outcome (AT-EXEC-003-01) ----------------------------------------------------------


def test_outcome_matches_after_execute() -> None:
    applied = execute("plan-contractor").json()["twin"]
    for body in ({}, {"twin": applied}):  # with or without the twin the client holds
        result = outcome("plan-contractor", **body).json()
        assert result["match"] is True and result["deltas"] == []
        assert result["expected"] == result["actual"]
        assert result["actual"]["projectCompletion"] == {"A": 6, "B": 3}


def test_outcome_reports_a_mismatch_when_the_applied_twin_drifted() -> None:
    applied = execute("plan-contractor").json()["twin"]
    for seg in applied["schedule"]:  # QA slips two days in the applied twin
        if seg["taskId"] == "T-A-QA":
            seg["startDay"] += 2
            seg["endDay"] += 2
    result = outcome("plan-contractor", twin=applied).json()
    assert result["match"] is False
    fields = {d["field"] for d in result["deltas"]}
    assert {"projectCompletion.A", "deadline.Project A acceptance", "invoiceEligible"} <= fields
    assert result["expected"]["projectCompletion"]["A"] == 6  # the promise did not change
    assert result["actual"]["projectCompletion"]["A"] == 8


def test_outcome_flags_work_that_runs_before_its_dependency_finishes() -> None:
    applied = execute("plan-contractor").json()["twin"]
    for seg in applied["schedule"]:  # integration slips, QA stays put
        if seg["taskId"] == "T-A-INT":
            seg["startDay"] += 2
            seg["endDay"] += 2
    result = outcome("plan-contractor", twin=applied).json()
    assert result["match"] is False
    reasons = [d["actual"] for d in result["deltas"] if d["field"] == "conflict"]
    assert any(
        "starts on day 5 before Payment gateway integration finishes on day 6" in r for r in reasons
    )


def test_outcome_flags_a_task_with_the_wrong_number_of_days() -> None:
    applied = execute("plan-contractor").json()["twin"]
    for seg in applied["schedule"]:
        if seg["taskId"] == "T-A-INT":
            seg["endDay"] -= 1
    result = outcome("plan-contractor", twin=applied).json()
    assert result["match"] is False
    assert any("3 of 4 required working days" in d["actual"] for d in result["deltas"])


def test_outcome_flags_a_tampered_twin_that_double_books_someone() -> None:
    applied = execute("plan-contractor").json()["twin"]
    first = applied["schedule"][0]
    applied["schedule"].append({**first, "taskId": "T-B-FIX"})  # same person, same days
    result = outcome("plan-contractor", twin=applied).json()
    assert result["match"] is False
    assert any(d["field"] == "conflict" for d in result["deltas"])


@pytest.mark.parametrize(
    "segment",
    [
        {"taskId": "T-NOPE", "personId": "PER-CTR", "startDay": 1, "endDay": 2},
        {"taskId": "T-A-INT", "personId": "PER-NOPE", "startDay": 1, "endDay": 2},
        {"taskId": "T-A-INT", "personId": "PER-CTR", "startDay": 3, "endDay": 2},
        {"taskId": "T-A-INT", "personId": "PER-CTR", "startDay": 1, "endDay": 99},
    ],
)
def test_outcome_refuses_a_twin_that_references_unknown_things(segment: dict[str, Any]) -> None:
    applied = execute("plan-contractor").json()["twin"]
    applied["schedule"] = [segment]
    response = outcome("plan-contractor", twin=applied)
    assert response.status_code == 400
    assert response.json() == {
        "error": "The supplied twin is not valid.",
        "code": "ValidationError",
    }


# ---- reset and no external calls (AT-EXEC-004-01) --------------------------------------


def test_reset_returns_the_seed_state() -> None:
    initial = client.get("/api/state").json()
    execute("plan-contractor")
    reset = client.post("/api/reset")
    assert reset.status_code == 200
    assert reset.json() == initial
    assert client.get("/api/state").json() == initial


def test_execute_outcome_and_reset_make_no_model_call_and_open_no_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("outbound network connection attempted")

    model = llm.ScriptedChatModel()
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    with llm.override_chat_model(model):
        assert execute("plan-contractor").status_code == 200
        assert outcome("plan-contractor").status_code == 200
        assert client.post("/api/reset").status_code == 200
    assert model.call_count == 0


def test_responses_carry_no_secret() -> None:
    blob = execute("plan-contractor").text + outcome("plan-contractor").text
    assert "sk-" not in blob and "api_key" not in blob.lower()


def test_end_to_end_run_then_approve_the_recommendation_then_verify() -> None:
    """Flow A through the API: stream a run, approve what it recommends, apply, verify."""
    import json

    from langchain_core.messages import BaseMessage

    def respond(messages: list[BaseMessage]) -> str:
        system = str(messages[0].content)
        if "You are the Planner" in system:
            return json.dumps({"recommendedPlanId": "plan-contractor", "rationale": "Best fit."})
        return "A short, grounded explanation."

    with llm.override_chat_model(llm.ScriptedChatModel(responder=respond)):
        stream = client.post("/api/run/stream", json={"presetId": PRESET}).text
    frames = [f.split("\n") for f in stream.strip().split("\n\n")]
    done = json.loads(next(f[1][6:] for f in frames if f[0] == "event: done"))
    statuses = {p["id"]: p["status"] for p in done["plans"]}
    approved = done["recommendedPlanId"]
    assert statuses[approved] == "verified" and statuses["plan-backup"] == "rejected"

    applied = execute(approved).json()
    assert applied["applied"] is True
    assert outcome(approved, twin=applied["twin"]).json()["match"] is True
    assert execute("plan-backup").status_code == 409  # the rejected plan still cannot be approved

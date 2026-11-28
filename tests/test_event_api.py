"""The typed-event flow through the real endpoints: state, agent run, approval gate, outcome."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage

from agents import llm
from app import app
from datahub import db

client = TestClient(app, raise_server_exceptions=False)
PRESET = "event-leave"


def leo_event(**overrides: Any) -> dict[str, Any]:
    pid = db.query("SELECT id FROM employees WHERE name = 'Leo Tanaka'")[0]["id"]
    return {"personId": pid, "startDate": "2026-12-01", "workingDays": 5, **overrides}


def fake() -> llm.ScriptedChatModel:
    def respond(messages: list[BaseMessage]) -> str:
        role = re.match(r"You are the (.+?) for Northstar", str(messages[0].content))
        assert role, "unexpected system prompt"
        if role.group(1) == "Planner":
            return json.dumps({"recommendedPlanId": "plan-contractor", "rationale": "Cover it."})
        return f"{role.group(1)} says the situation is understood."

    return llm.ScriptedChatModel(responder=respond)


def sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        out.append((lines[0][7:], json.loads(lines[1][6:])))
    return out


def test_event_state_returns_the_model_built_for_the_event() -> None:
    body = client.post("/api/event/state", json=leo_event()).json()
    assert body["presetId"] == PRESET and body["calendar"][0] == "2026-12-01"
    state = body["state"]
    assert state["people"][0]["name"] == "Leo Tanaka"
    assert state["presets"][0]["id"] == PRESET and state["tasks"] and state["chain"]


def test_a_person_without_delivery_work_is_a_calm_409() -> None:
    sales = db.query("SELECT id FROM employees WHERE name = 'Caleb Zhang'")[0]["id"]
    r = client.post("/api/event/state", json=leo_event(personId=sales))
    assert r.status_code == 409 and r.json()["code"] == "NoImpact"
    assert "no open tickets" in r.json()["error"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        leo_event(workingDays=0),
        leo_event(workingDays=99),
        leo_event(startDate="2026-11-01"),
        leo_event(personId=999999),
        leo_event(startDate="not a date"),
        {**leo_event(), "extra": 1},
    ],
)
def test_bad_events_are_400_with_a_safe_message(body: dict[str, Any]) -> None:
    r = client.post("/api/event/state", json=body)
    assert r.status_code == 400 and r.json()["code"] == "ValidationError"


def test_the_agent_run_streams_on_the_event_model() -> None:
    with llm.override_chat_model(fake()):
        r = client.post("/api/run/stream", json={"presetId": PRESET, "event": leo_event()})
    events = sse(r.text)
    names = [n for n, _ in events]
    assert names[0] == "run_started" and names[-1] == "done"
    assert events[0][1]["event"]["unavailable"][0]["startDay"] == 1
    done = events[-1][1]
    assert {p["id"] for p in done["plans"]} >= {"plan-wait", "plan-backup", "plan-contractor"}
    assert done["verdict"] is not None


def test_an_event_needs_the_event_preset_id() -> None:
    r = client.post("/api/run/stream", json={"presetId": "dev-out-1-5", "event": leo_event()})
    assert r.status_code == 400


def test_the_approval_gate_works_on_the_event_model() -> None:
    naive = client.post(
        "/api/execute",
        json={"presetId": PRESET, "approvedPlanId": "plan-backup", "event": leo_event()},
    )
    assert naive.status_code == 409 and naive.json()["code"] == "PlanRejected"
    ok = client.post(
        "/api/execute",
        json={"presetId": PRESET, "approvedPlanId": "plan-contractor", "event": leo_event()},
    )
    assert ok.status_code == 200 and ok.json()["applied"] is True
    unknown = client.post(
        "/api/execute",
        json={"presetId": PRESET, "approvedPlanId": "plan-nope", "event": leo_event()},
    )
    assert unknown.status_code == 400


def test_the_outcome_matches_the_plan_and_a_tampered_twin_does_not() -> None:
    req = {"presetId": PRESET, "approvedPlanId": "plan-contractor", "event": leo_event()}
    applied = client.post("/api/execute", json=req).json()["twin"]
    assert client.post("/api/outcome", json={**req, "twin": applied}).json()["match"] is True
    tampered = json.loads(json.dumps(applied))
    tampered["schedule"][0]["startDay"] += 1
    assert client.post("/api/outcome", json={**req, "twin": tampered}).json()["match"] is False


def test_the_old_presets_and_state_are_unchanged() -> None:
    assert client.get("/api/state").status_code == 200
    r = client.post(
        "/api/execute", json={"presetId": "dev-out-1-5", "approvedPlanId": "plan-contractor"}
    )
    assert r.status_code == 200

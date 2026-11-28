"""Simulated webhooks: six systems, one signed inbox, the same recovery flow behind it.

No model is used for the inbox. The agent run at the end uses a scripted fake.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage

from agents import llm
from app import app
from datahub import db, event_twin
from integrations import gdocs, webhooks

client = TestClient(app, raise_server_exceptions=False)
SIG = "X-Demo-Signature"


def samples() -> dict[str, dict[str, Any]]:
    return {s["source"]: s for s in client.get("/api/webhooks/samples").json()}


def post(source: str, payload: dict[str, Any], *, sign: bool = True) -> Any:
    body = webhooks.canonical(payload)
    headers = {SIG: webhooks.sign(body.encode())} if sign else {}
    return client.post(f"/api/webhooks/{source}", content=body, headers=headers)


def edited(source: str, *path: str, value: Any) -> dict[str, Any]:
    """A copy of the sample payload with one nested value replaced."""
    payload = json.loads(samples()[source]["body"])
    node = payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return payload


# ---- the samples ---------------------------------------------------------------------------


def test_six_systems_from_six_departments_with_two_kinds_of_event() -> None:
    found = samples()
    assert set(found) == {"hris", "gcal", "slack", "travel", "meet", "crm"}
    assert len({s["department"] for s in found.values()}) == 6
    assert len({s["system"] for s in found.values()}) == 6
    kinds = set()
    for source, sample in found.items():
        r = client.post(
            f"/api/webhooks/{source}", content=sample["body"], headers={SIG: sample["signature"]}
        )
        assert r.status_code == 200, (source, r.text)
        body = r.json()
        assert body["signature"] == "verified (demo)" and body["summary"]
        kinds.add(body["presetId"])
        assert r.headers["x-simulated"] == "true"
    assert kinds == {"event-leave", "event-demand"}


@pytest.mark.parametrize("source", ["hris", "gcal", "slack", "travel", "meet", "crm"])
def test_every_sample_gives_the_engine_something_to_decide(source: str) -> None:
    sample = samples()[source]
    r = client.post(
        f"/api/webhooks/{source}", content=sample["body"], headers={SIG: sample["signature"]}
    )
    state = client.post("/api/event/state", json=r.json()["event"])
    assert state.status_code == 200
    body = state.json()
    assert body["presetId"] == r.json()["presetId"] and body["state"]["chain"]
    assert samples()[source]["body"] == sample["body"]  # samples are stable between calls


def test_the_sample_payloads_use_real_people_a_real_meeting_and_a_real_deal() -> None:
    found = samples()
    for source in ("hris", "slack", "travel"):
        text = found[source]["body"]
        emails = re.findall(r"[\w.]+@example\.com", text)
        assert emails and all(
            db.query("SELECT 1 FROM employees WHERE email = ?", (e,)) for e in emails
        )
    assert db.query(
        "SELECT 1 FROM meetings WHERE id = ? AND status = 'completed'", (webhooks.MEETING_ID,)
    )
    crm = json.loads(found["crm"]["body"])["data"]["payload"]
    opp_id = int(crm["ChangeEventHeader"]["recordIds"][0].removeprefix("OPP-"))
    row = db.query("SELECT amount_usd FROM opportunities WHERE id = ?", (opp_id,))[0]
    assert row["amount_usd"] == crm["Amount"]


# ---- the signature -------------------------------------------------------------------------


def test_a_body_changed_in_transit_is_refused_before_it_is_read() -> None:
    sample = samples()["hris"]
    r = client.post(
        "/api/webhooks/hris", content=sample["tamperedBody"], headers={SIG: sample["signature"]}
    )
    assert r.status_code == 401 and r.json()["code"] == "InvalidSignature"


@pytest.mark.parametrize("header", [None, "", "sha256=abc", "garbage"])
def test_a_missing_or_wrong_signature_is_refused(header: str | None) -> None:
    sample = samples()["gcal"]
    headers = {SIG: header} if header is not None else {}
    r = client.post("/api/webhooks/gcal", content=sample["body"], headers=headers)
    assert r.status_code == 401 and r.json()["code"] == "InvalidSignature"


def test_a_signature_for_one_system_body_does_not_open_another_event() -> None:
    first, second = samples()["hris"], samples()["gcal"]
    r = client.post("/api/webhooks/gcal", content=first["body"], headers={SIG: second["signature"]})
    assert r.status_code == 401


def test_signing_uses_the_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    body = b'{"a":1}'
    default = webhooks.sign(body)
    monkeypatch.setenv("WEBHOOK_DEMO_SECRET", "another-demo-key")
    assert webhooks.sign(body) != default and webhooks.verify(body, webhooks.sign(body))
    assert not webhooks.verify(body, default)


def test_unknown_source_and_non_json_bodies() -> None:
    assert post("nope", {"a": 1}).status_code == 404
    body = b"not json"
    r = client.post("/api/webhooks/hris", content=body, headers={SIG: webhooks.sign(body)})
    assert r.status_code == 400 and r.json()["code"] == "ValidationError"
    arr = b"[1]"
    r = client.post("/api/webhooks/hris", content=arr, headers={SIG: webhooks.sign(arr)})
    assert r.status_code == 400


def test_an_oversized_body_is_refused() -> None:
    r = client.post("/api/webhooks/hris", content="x" * 70_000, headers={SIG: "sha256=0"})
    assert r.status_code == 413


# ---- each system's own payload is read correctly -------------------------------------------


def event_of(source: str) -> dict[str, Any]:
    sample = samples()[source]
    r = client.post(
        f"/api/webhooks/{source}", content=sample["body"], headers={SIG: sample["signature"]}
    )
    return r.json()["event"]


def test_the_calendar_all_day_end_date_is_exclusive() -> None:
    cal = event_twin.working_calendar()
    event = event_of("gcal")
    assert event["startDate"] == cal[2].isoformat()
    assert event["workingDays"] == 5  # Thu 3 Dec to Wed 9 Dec: the end date sent is the 10th


def test_the_slack_status_runs_until_it_clears() -> None:
    cal = event_twin.working_calendar()
    event = event_of("slack")
    assert event["startDate"] == cal[0].isoformat() and event["workingDays"] == 4


def test_the_meeting_minutes_are_fetched_and_the_request_is_read_from_them() -> None:
    sample = samples()["meet"]
    r = client.post(
        "/api/webhooks/meet", content=sample["body"], headers={SIG: sample["signature"]}
    ).json()
    assert r["fetched"][0]["system"] == "Google Docs" and "doc-mtg-422" in r["fetched"][0]["path"]
    event = r["event"]
    account = db.query("SELECT account_id FROM meetings WHERE id = 422")[0]["account_id"]
    assert event["kind"] == "demand" and event["accountId"] == account
    assert (event["days"], event["skill"], event["amount"]) == (4, "security", 7500)
    assert event["dueDate"] == event_twin.working_calendar()[7].isoformat()


def test_the_deal_event_carries_the_sold_scope() -> None:
    event = event_of("crm")
    assert event["kind"] == "demand" and event["days"] == 6 and event["skill"] == "kubernetes"


@pytest.mark.parametrize(
    ("source", "path", "value", "expected"),
    [
        ("hris", ("eventType",), "time_off.requested", "not an approved time-off"),
        ("hris", ("worker", "email"), "nobody@example.com", "not in the company records"),
        ("hris", ("timeOff", "firstDay"), "soon", "not a valid date"),
        ("hris", ("timeOff",), None, "missing"),
        ("gcal", ("changed", "eventType"), "default", "not an out-of-office"),
        ("gcal", ("changed", "status"), "tentative", "not confirmed"),
        (
            "slack",
            ("event", "user", "profile", "status_emoji"),
            ":coffee:",
            "not announce an absence",
        ),
        ("slack", ("event_time",), 4_000_000_000, "no usable expiry"),
        ("slack", ("event", "type"), "message", "not a profile change"),
        ("travel", ("trip", "financeApproved"), False, "not approved by Finance"),
        ("travel", ("event",), "trip.cancelled", "not a booked trip"),
        ("meet", ("transcript", "state"), "STARTED", "not ready"),
        (
            "meet",
            ("transcript", "docsDestination", "document"),
            "documents/doc-mtg-99999",
            "not be found",
        ),
        (
            "meet",
            ("eventType",),
            "google.workspace.meet.recording.fileGenerated",
            "not a finished transcript",
        ),
        ("crm", ("data", "payload", "StageName"), "Negotiation", "not a deal that was just won"),
        ("crm", ("data", "payload", "AccountId"), "ACC-999999", "not in the company records"),
        ("crm", ("data", "payload", "Delivery_Days__c"), 99, "outside the range"),
        ("crm", ("data", "payload", "Amount"), "lots", "not a whole number"),
    ],
)
def test_a_payload_that_does_not_fit_is_refused_with_a_readable_reason(
    source: str, path: tuple[str, ...], value: Any, expected: str
) -> None:
    r = post(source, edited(source, *path, value=value))
    assert r.status_code == 400 and r.json()["code"] == "ValidationError"
    assert expected in r.json()["error"]


def test_minutes_without_a_request_say_what_is_missing_instead_of_guessing() -> None:
    plain = db.query(
        "SELECT id FROM meetings WHERE status = 'completed' AND account_id IS NOT NULL "
        "AND id != 422 LIMIT 1"
    )[0]["id"]
    lines = gdocs.text_lines(gdocs.minutes_document(f"doc-mtg-{plain}"))
    with pytest.raises(event_twin.EventError, match="missing: Client request, Scope"):
        gdocs.request_from_minutes(lines, 1)


def test_the_docs_mock_returns_the_docs_api_shape() -> None:
    r = client.get("/simulated/docs/v1/documents/doc-mtg-422")
    assert r.status_code == 200 and r.headers["x-simulated"] == "true"
    body = r.json()
    assert body["documentId"] == "doc-mtg-422" and body["title"].startswith("Minutes:")
    text = "\n".join(gdocs.text_lines(body))
    assert "Client request: SSO audit-log export" in text and "Quoted value: 7,500 USD" in text
    assert client.get("/simulated/docs/v1/documents/doc-mtg-9999999").status_code == 404
    assert client.get("/simulated/docs/v1/documents/nope").status_code == 404


# ---- the recovery flow behind a webhook event ---------------------------------------------


def fake() -> llm.ScriptedChatModel:
    def respond(messages: list[BaseMessage]) -> str:
        role = re.match(r"You are the (.+?) for Northstar", str(messages[0].content))
        assert role, "unexpected system prompt"
        if role.group(1) == "Planner":
            return json.dumps({"recommendedPlanId": "plan-contractor", "rationale": "Safe."})
        return f"{role.group(1)} says the situation is understood."

    return llm.ScriptedChatModel(responder=respond)


def sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in text.strip().split("\n\n")
    ]


@pytest.mark.parametrize("source", ["meet", "crm", "slack"])
def test_the_agents_run_the_whole_flow_on_a_webhook_event(source: str) -> None:
    sample = samples()[source]
    hook = client.post(
        f"/api/webhooks/{source}", content=sample["body"], headers={SIG: sample["signature"]}
    ).json()
    preset, event = hook["presetId"], hook["event"]
    with llm.override_chat_model(fake()):
        run = client.post("/api/run/stream", json={"presetId": preset, "event": event})
    events = sse(run.text)
    assert events[0][0] == "run_started" and events[-1][0] == "done", [n for n, _ in events]
    ids = {p["id"] for p in events[-1][1]["plans"]}
    assert {"plan-wait", "plan-backup", "plan-contractor"} <= ids

    naive = client.post(
        "/api/execute", json={"presetId": preset, "approvedPlanId": "plan-backup", "event": event}
    )
    assert naive.status_code == 409 and naive.json()["code"] == "PlanRejected"
    req = {"presetId": preset, "approvedPlanId": "plan-contractor", "event": event}
    applied = client.post("/api/execute", json=req)
    assert applied.status_code == 200
    out = client.post("/api/outcome", json={**req, "twin": applied.json()["twin"]})
    assert out.json()["match"] is True


def test_a_demand_event_needs_the_demand_preset_and_a_valid_request() -> None:
    event = event_of("crm")
    assert (
        client.post("/api/run/stream", json={"presetId": "event-leave", "event": event}).status_code
        == 400
    )
    for bad in (
        {**event, "days": 0},
        {**event, "days": 11},
        {**event, "skill": "underwater basket weaving"},
        {**event, "accountId": 999999},
        {**event, "dueDate": "2020-01-01"},
        {**event, "dueDate": "2027-06-01"},
        {**event, "amount": 0},
        {**event, "extra": 1},
    ):
        r = client.post("/api/event/state", json=bad)
        assert r.status_code == 400, (bad, r.text)
    assert client.post("/api/event/state", json=event).status_code == 200


def test_the_passcode_gate_covers_the_inbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSCODE", "letmein")
    sample = samples.__wrapped__ if hasattr(samples, "__wrapped__") else None  # noqa: F841
    assert client.get("/api/webhooks/samples").status_code == 401
    r = client.post("/api/webhooks/hris", content="{}", headers={SIG: "sha256=0"})
    assert r.status_code == 401 and r.json()["code"] == "Unauthorized"

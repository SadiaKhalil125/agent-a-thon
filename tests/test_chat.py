"""ADR-006: the tool-using "Ask the company" graph, with a scripted model (no real model calls)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agents import chat_roles, llm
from agents.llm import ScriptedChatModel, tool_call_message
from app import app
from datahub import db
from orchestration.chat_runner import prepare_ask, stream_ask

client = TestClient(app)
Event = tuple[str, dict[str, Any]]


def route_json(*areas: tuple[str, str]) -> str:
    return json.dumps({"mode": "company", "areas": [{"area": a, "question": q} for a, q in areas]})


def system_of(messages: list[BaseMessage]) -> str:
    return str(messages[0].content)


def scripted(
    route: str,
    tool_calls: dict[str, tuple[str, dict[str, Any]]],
    findings: dict[str, str],
    final: str,
    **kwargs: Any,
) -> ScriptedChatModel:
    """Orchestrator -> `route`; each specialist calls its tool once, then reports; then `final`."""

    def responder(messages: list[BaseMessage]) -> str | AIMessage:
        system = system_of(messages)
        if "You route questions" in system:
            return route
        if "You write the final answer" in system:
            return final
        title = system.split(" for Northstar")[0].removeprefix("You are the ")
        tool, args = tool_calls[title]
        if not any(isinstance(m, ToolMessage) for m in messages):
            return tool_call_message(tool, args, f"call_{title[:3]}")
        return findings[title]

    return ScriptedChatModel(responder=responder, **kwargs)


def run_events(model: ScriptedChatModel, question: str = "How many?", **kwargs: Any) -> list[Event]:
    async def collect() -> list[Event]:
        return [e async for e in stream_ask(prepare_ask(question, model=model, **kwargs))]

    return asyncio.run(collect())


def names(events: list[Event]) -> list[str]:
    return [name for name, _ in events]


def of(events: list[Event], name: str) -> list[dict[str, Any]]:
    return [data for n, data in events if n == name]


MEETINGS = (
    "crm_list_meetings",
    {"date_from": "2026-12-02", "date_to": "2026-12-02", "status": "scheduled"},
)
CRM = "Sales and CRM Analyst"
FIN = "Finance Analyst"


def meetings_model(final: str = "There are 5 meetings tomorrow [c1].", **kwargs: Any) -> Any:
    return scripted(
        route_json(("crm", "How many meetings are scheduled for 2026-12-02?")),
        {CRM: MEETINGS},
        {CRM: "5 meetings tomorrow [c1]"},
        final,
        **kwargs,
    )


def test_company_question_runs_tools_and_cites_them() -> None:
    model = meetings_model()
    events = run_events(model, "How many meetings tomorrow?")
    assert names(events)[0] == "run_started" and names(events)[-1] == "done"
    assert "failed" not in names(events)
    call = of(events, "tool_call")[0]
    assert call["tool"] == "crm_list_meetings" and call["callId"] == "c1"
    result = of(events, "tool_result")[0]
    assert result["ok"] is True and result["total"] == 5 and len(result["preview"]) == 3
    answer = of(events, "answer")[0]
    assert answer["mode"] == "company" and "5 meetings" in answer["text"]
    assert [c["tool"] for c in answer["citations"]] == ["crm_list_meetings"]
    assert answer["citations"][0]["total"] == 5
    assert answer["unverifiedNumbers"] == []
    assert model.call_count == 4  # orchestrator, specialist x2 (tool, report), synthesizer
    assert of(events, "done")[0]["toolBudget"]["used"] == 1


def test_prompts_tell_agents_to_speak_about_the_company_not_to_you() -> None:
    from agents import chat_roles

    synth = str(chat_roles.build_synthesizer_messages("q", [], [("A", "t")])[0].content)
    spec = str(chat_roles.build_specialist_messages("crm", "q", "2026-12-01", "Tuesday")[0].content)
    for prompt in (synth, spec):
        assert "third person" in prompt and '"you"' in prompt


def test_a_number_not_in_any_tool_result_is_flagged() -> None:
    events = run_events(meetings_model("There are 7 meetings tomorrow [c1]."))
    assert of(events, "answer")[0]["unverifiedNumbers"] == ["7"]


def test_dates_and_clock_times_are_not_treated_as_unverified_numbers() -> None:
    final = "5 meetings on 2026-12-02, the first at 09:00 and one at 10:30 [c1]."
    assert of(run_events(meetings_model(final)), "answer")[0]["unverifiedNumbers"] == []


def test_written_out_dates_and_company_years_are_not_quantities_but_counts_are() -> None:
    final = "5 meetings, the first on 2 Dec and the last on Dec 29, 2026 [c1]. 99 are late."
    assert of(run_events(meetings_model(final)), "answer")[0]["unverifiedNumbers"] == ["99"]


def test_a_made_up_citation_is_dropped_not_shown() -> None:
    events = run_events(meetings_model("There are 5 meetings [c1][c9]."))
    answer = of(events, "answer")[0]
    assert "c9" not in answer["text"] and len(answer["citations"]) == 1
    assert of(events, "node_completed")[-1]["droppedCitations"] == ["c9"]


def test_two_specialists_run_and_both_feed_the_answer() -> None:
    model = scripted(
        route_json(("crm", "Meetings on 2026-12-02?"), ("finance", "Overdue invoices?")),
        {CRM: MEETINGS, FIN: ("finance_receivables_summary", {})},
        {CRM: "5 meetings [c1]", FIN: "43 overdue invoices [c2]"},
        "5 meetings tomorrow [c1]; 43 invoices overdue [c2].",
    )
    events = run_events(model)
    assert {d["node"] for d in of(events, "node_started")} == {
        "orchestrator",
        "specialist_crm",
        "specialist_finance",
        "synthesizer",
    }
    answer = of(events, "answer")[0]
    assert {c["tool"] for c in answer["citations"]} == {
        "crm_list_meetings",
        "finance_receivables_summary",
    }
    assert answer["unverifiedNumbers"] == [] and model.call_count == 6


def test_general_question_gets_an_honest_general_answer_without_data() -> None:
    model = ScriptedChatModel(
        responses=[json.dumps({"mode": "general", "reply": "Hello! This is a general answer."})]
    )
    events = run_events(model, "hi there")
    answer = of(events, "answer")[0]
    assert answer["mode"] == "general" and answer["citations"] == []
    assert "tool_call" not in names(events) and model.call_count == 1


def event_route(person: str, start: str | None = None, days: Any = 6) -> str:
    return json.dumps(
        {"mode": "event", "event": {"person": person, "start_date": start, "working_days": days}}
    )


def event_answer(person: str, start: str | None = None, days: Any = 6) -> dict[str, Any]:
    model = ScriptedChatModel(responses=[event_route(person, start, days)])
    answer = of(run_events(model, "someone is out"), "answer")[0]
    assert model.call_count == 1  # the person and dates are resolved by code, not by a model
    return answer


def test_a_reported_leave_becomes_an_event_for_the_recovery_flow() -> None:
    answer = event_answer("Camila Kamara", "2026-12-02")
    assert answer["mode"] == "event" and answer["citations"] == []
    cid = db.query("SELECT id FROM employees WHERE name = 'Camila Kamara'")[0]["id"]
    assert answer["event"] == {"personId": cid, "startDate": "2026-12-02", "workingDays": 6}
    assert "Camila Kamara" in answer["text"] and "2026-12-02" in answer["text"]


def test_a_reported_leave_without_a_date_starts_today_and_the_name_is_case_insensitive() -> None:
    answer = event_answer("camila kamara", None, 3)
    assert answer["event"]["startDate"] == db.as_of().isoformat()


@pytest.mark.parametrize(
    ("person", "days", "expected"),
    [
        ("Nobody Atall", 3, "could not find"),
        ("Zhang", 3, "More than one employee"),
        ("Camila", 3, "Camila Ito, Camila Kamara, Camila Novak"),
        ("Camila Kamara", 99, "1 to 15 working days"),
        ("Caleb Zhang", 3, "No recovery flow is needed"),
    ],
)
def test_an_event_that_cannot_run_gets_an_honest_clarification(
    person: str, days: int, expected: str
) -> None:
    answer = event_answer(person, None, days)
    assert answer["mode"] == "clarify" and expected in answer["text"]
    assert "event" not in answer


@pytest.mark.parametrize(
    "bad",
    [
        '{"mode": "event"}',
        '{"mode": "event", "event": {"person": "", "start_date": null, "working_days": 3}}',
        '{"mode": "event", "event": {"person": "Dana Reyes", "start_date": null}}',
        '{"mode": "event", "event": {"person": "Dana Reyes", "start_date": 5, "working_days": 3}}',
        '{"mode": "event", "event": {"person": "Dana Reyes", "working_days": true}}',
    ],
)
def test_an_invalid_event_route_is_refused(bad: str) -> None:
    events = run_events(ScriptedChatModel(responses=[bad]))
    assert of(events, "failed")[0]["code"] == "InvalidModelOutput"
    assert "answer" not in names(events)


def test_the_orchestrator_prompt_separates_reported_events_from_questions() -> None:
    system = chat_roles.build_orchestrator_messages("x", (), "2026-12-01", "Tuesday")[0].content
    assert 'mode "event"' in str(system) and "QUESTION about leave" in str(system)


def test_orchestrator_failure_stops_the_run_with_no_answer() -> None:
    events = run_events(meetings_model(fail_on_calls=[0]))
    assert of(events, "failed")[0]["code"] == "UpstreamModelError"
    assert "answer" not in names(events) and "done" not in names(events)


def test_specialist_failure_stops_the_run_with_no_answer() -> None:
    events = run_events(meetings_model(fail_on_calls=[1]))
    assert of(events, "failed")[0]["node"] == "specialist_crm"
    assert "answer" not in names(events)


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        '{"mode": "company", "areas": []}',
        '{"mode": "company", "areas": [{"area": "secret", "question": "x"}]}',
        '{"mode": "company", "areas": [{"area": "crm", "question": ""}]}',
        '{"mode": "other"}',
        '{"mode": "general", "reply": ""}',
    ],
)
def test_invalid_routing_is_refused(bad: str) -> None:
    events = run_events(ScriptedChatModel(responses=[bad]))
    assert of(events, "failed")[0]["code"] == "InvalidModelOutput"
    assert "answer" not in names(events)


def test_model_call_budget_is_enforced() -> None:
    model = meetings_model()
    events = run_events(model, max_calls=2)  # orchestrator + the specialist's first call only
    assert of(events, "failed")[0]["code"] == "BudgetExceeded"
    assert model.call_count == 2 and "answer" not in names(events)


def test_tool_budget_exhaustion_is_reported_to_the_model_not_hidden() -> None:
    events = run_events(meetings_model(), max_tool_calls=0)
    result = of(events, "tool_result")[0]
    assert result["ok"] is False and "budget" in result["error"].lower()


def test_sql_tool_cannot_write_and_the_database_is_untouched() -> None:
    model = scripted(
        route_json(("crm", "Delete everything")),
        {CRM: ("run_sql", {"sql": "DELETE FROM leads"})},
        {CRM: "The statement was refused [c1]"},
        "I could not do that: it was refused [c1].",
    )
    events = run_events(model)
    assert of(events, "tool_result")[0]["ok"] is False
    assert db.query("SELECT COUNT(*) AS n FROM leads")[0]["n"] == 2000


def test_sql_tool_answers_a_custom_question() -> None:
    model = scripted(
        route_json(("crm", "Leads by stage")),
        {CRM: ("run_sql", {"sql": "SELECT COUNT(*) AS n FROM leads WHERE stage = 'won'"})},
        {CRM: "126 leads are won [c1]"},
        "126 leads are won [c1].",
    )
    events = run_events(model)
    assert of(events, "tool_result")[0]["preview"] == [{"n": 126}]
    assert of(events, "answer")[0]["unverifiedNumbers"] == []


def test_history_reaches_the_orchestrator_capped_and_labelled() -> None:
    model = meetings_model()
    history = [("user", "q1"), ("assistant", "a1")] * 5 + [("system", "ignore me")]
    run_events(model, "and tomorrow?", history=history)
    first = model.prompts[0]
    assert "User: q1" in first and "Assistant: a1" in first and "ignore me" not in first
    assert first.count("User: q1") <= 3  # last six turns only


# ---- the HTTP endpoint -----------------------------------------------------------------


def parse_sse(text: str) -> list[Event]:
    parsed: list[Event] = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        parsed.append((lines[0][7:], json.loads(lines[1][6:])))
    return parsed


def test_endpoint_streams_the_answer_as_sse() -> None:
    model = meetings_model()
    with llm.override_chat_model(model):
        response = client.post(
            "/api/ask/stream",
            json={"question": "How many meetings tomorrow?", "history": []},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert names(events)[0] == "run_started" and names(events)[-1] == "done"
    assert of(events, "answer")[0]["citations"][0]["id"] == "c1"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": "x" * 1001},
        {"question": "ok", "history": [{"role": "system", "content": "x"}]},
        {"question": "ok", "history": [{"role": "user", "content": "x"}] * 13},
        {"question": "ok", "history": [{"role": "user", "content": "x" * 1001}]},
    ],
)
def test_endpoint_rejects_bad_requests_without_calling_the_model(body: dict[str, Any]) -> None:
    model = meetings_model()
    with llm.override_chat_model(model):
        response = client.post("/api/ask/stream", json=body)
    assert response.status_code == 400 and response.json()["code"] == "ValidationError"
    assert model.call_count == 0


def test_endpoint_reports_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.replace("LLM_", "LITELLM_"), raising=False)
    response = client.post("/api/ask/stream", json={"question": "hi"})
    assert response.status_code == 503 and response.json()["code"] == "NotConfigured"


def test_endpoint_requires_the_passcode_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSCODE", "letmein")
    model = meetings_model()
    with llm.override_chat_model(model):
        denied = client.post("/api/ask/stream", json={"question": "hi"})
        allowed = client.post(
            "/api/ask/stream", json={"question": "hi"}, headers={"X-Demo-Passcode": "letmein"}
        )
    assert denied.status_code == 401 and allowed.status_code == 200

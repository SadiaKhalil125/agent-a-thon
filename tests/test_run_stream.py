"""TASK-009 to 013: the full graph run and `/api/run/stream`.

Covers AT-ORCH-002/003/004/005, AT-IMP-001, AT-PLAN-001/002, AT-VER-003, AT-OPS-001, AT-REL-001.
The model is always a fake (`ScriptedChatModel`), keyed on the role so parallel calls are safe.
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage

from agents import llm
from app import app
from orchestration import graph as graph_module
from orchestration.budget import BudgetExceededError, RunBudget
from orchestration.runner import prepare_run, stream_run
from orchestration.state import RunState
from twin import solver
from twin.seed import get_twin

client = TestClient(app, raise_server_exceptions=False)
ROOT = Path(__file__).resolve().parent.parent
Event = tuple[str, dict[str, Any]]

HR_TEXT = "Marcus Lee is booked on days 2 to 3, so he is only free from day 4."
FINANCE_TEXT = "The contractor costs 1500 USD, within the 2000 USD recovery budget."
VERIFIER_TEXT = "I find every plan fine, approved."  # deliberately ignores the engine result


def role_of(messages: list[BaseMessage]) -> str:
    match = re.match(r"You are the (.+?) for Northstar", str(messages[0].content))
    assert match, "unexpected system prompt"
    return match.group(1)


def fake(
    first: str = "plan-backup",
    second: str = "plan-contractor",
    *,
    raw_planner: dict[int, str] | None = None,
    fail_roles: tuple[str, ...] = (),
) -> llm.ScriptedChatModel:
    """Role-aware fake. `first`/`second` are the Planner's recommendation per pass."""
    planner_calls = {"n": 0}

    def respond(messages: list[BaseMessage]) -> str:
        role = role_of(messages)
        if role in fail_roles:
            raise RuntimeError("simulated failure")
        if role == "Impact Investigator":
            return "Dana Reyes is out, so the integration slips and puts acceptance at risk."
        if role == "HR and Resource Analyst":
            return HR_TEXT
        if role == "Finance Analyst":
            return FINANCE_TEXT
        if role == "Planner":
            planner_calls["n"] += 1
            if raw_planner and planner_calls["n"] in raw_planner:
                return raw_planner[planner_calls["n"]]
            chosen = first if planner_calls["n"] == 1 else second
            return json.dumps({"recommendedPlanId": chosen, "rationale": f"Go with {chosen}."})
        assert role == "Verifier"
        return VERIFIER_TEXT

    return llm.ScriptedChatModel(responder=respond)


def run_events(
    model: llm.ScriptedChatModel, preset: str = "dev-out-1-5", max_calls: int = 8
) -> list[Event]:
    prepared = prepare_run(preset, model=model, max_calls=max_calls)

    async def collect() -> list[Event]:
        return [item async for item in stream_run(prepared)]

    return asyncio.run(collect())


def names(events: list[Event]) -> list[str]:
    return [name for name, _ in events]


def completed(events: list[Event]) -> list[dict[str, Any]]:
    return [data for name, data in events if name == "node_completed"]


def done_of(events: list[Event]) -> dict[str, Any]:
    return dict(events)["done"]


def prompts_of(model: llm.ScriptedChatModel, role: str) -> list[str]:
    return [p for p in model.prompts if p]  # human prompts, in call order (role-agnostic)


# ---- budget ----------------------------------------------------------------------------


def test_budget_allows_up_to_max_then_refuses() -> None:
    budget = RunBudget(max_calls=2)
    budget.consume()
    budget.consume()
    assert budget.snapshot() == {"max": 2, "used": 2}
    with pytest.raises(BudgetExceededError):
        budget.consume()
    assert budget.snapshot() == {"max": 2, "used": 2}  # a refused call is not counted


# ---- the full run (AT-ORCH-002-01, AT-ORCH-003-01, AT-ORCH-004-01, AT-VER-003-01) -------


def test_full_run_visits_every_agent_with_a_rejection_and_a_revision() -> None:
    model = fake()
    events = run_events(model)
    steps = [(c["node"], c["status"]) for c in completed(events)]
    assert steps[0] == ("impact", "done")
    assert set(steps[1:3]) == {("hr_resource", "done"), ("finance", "done")}
    assert steps[3:] == [
        ("planner", "done"),
        ("verifier", "rejected"),
        ("planner", "revised"),
        ("verifier", "done"),
    ]
    assert names(events)[0] == "run_started" and names(events)[-1] == "done"
    assert model.call_count == 7  # one call per node execution, none extra
    assert done_of(events)["budget"] == {"max": 8, "used": 7}


def test_hr_and_finance_start_together_before_either_finishes() -> None:
    events = run_events(fake())
    order = [(name, data.get("node")) for name, data in events]
    started = [
        i
        for i, e in enumerate(order)
        if e in {("node_started", "hr_resource"), ("node_started", "finance")}
    ]
    finished = [
        i
        for i, e in enumerate(order)
        if e in {("node_completed", "hr_resource"), ("node_completed", "finance")}
    ]
    assert len(started) == 2 and max(started) < min(finished)


def test_plans_are_comparable_and_numbers_come_from_the_solver() -> None:
    done = done_of(run_events(fake()))
    plans = {p["id"]: p for p in done["plans"]}
    assert set(plans) == {"plan-wait", "plan-backup", "plan-contractor", "plan-backup-revised"}
    twin = get_twin()
    for plan_id, plan in plans.items():
        truth = solver.find_plan(twin, "dev-out-1-5", plan_id)
        for key in ("projectCompletion", "incrementalCost", "budgetFit", "invoiceEligible"):
            assert plan[key] == truth.model_dump(mode="json")[key], (plan_id, key)
        assert {"deadlines", "violatedConstraints", "schedule", "summary", "name"} <= set(plan)
    assert plans["plan-contractor"]["projectCompletion"] == {"A": 6, "B": 3}
    assert plans["plan-contractor"]["incrementalCost"] == 1500


def test_final_statuses_show_the_rejection_and_the_revision() -> None:
    plans = {p["id"]: p for p in done_of(run_events(fake()))["plans"]}
    assert plans["plan-backup"]["status"] == "rejected"
    assert plans["plan-backup-revised"]["status"] == "revised"
    assert plans["plan-backup-revised"]["revisesPlanId"] == "plan-backup"
    assert plans["plan-wait"]["status"] == plans["plan-contractor"]["status"] == "verified"


def test_verifier_rejection_is_the_engines_decision_not_the_models() -> None:
    events = run_events(fake())
    first, second = [c for c in completed(events) if c["node"] == "verifier"]
    assert first["verdict"]["decision"] == "rejected"
    assert first["verdict"]["planId"] == "plan-backup"
    assert first["verdict"]["reason"] == VERIFIER_TEXT  # the model's words, the engine's verdict
    facts = {f["label"]: f["value"] for f in first["derivedFacts"]}
    assert "Displaces Marcus Lee" in facts["Reassign to Marcus Lee: feasibility"]
    assert second["verdict"] == {
        "planId": "plan-contractor",
        "decision": "approved",
        "reason": VERIFIER_TEXT,
    }
    assert done_of(events)["verdict"] == second["verdict"]


@pytest.mark.parametrize("first", ["plan-backup", "plan-wait", "plan-contractor"])
def test_the_rejectable_candidate_is_always_challenged(first: str) -> None:
    events = run_events(fake(first=first))
    verdicts = [c["verdict"] for c in completed(events) if c["node"] == "verifier"]
    assert [v["decision"] for v in verdicts] == ["rejected", "approved"]


def test_rejection_changes_the_next_planner_output() -> None:
    model = fake()
    events = run_events(model)
    planners = [c for c in completed(events) if c["node"] == "planner"]
    first_ids = [p["id"] for p in planners[0]["plans"]]
    second_ids = [p["id"] for p in planners[1]["plans"]]
    assert "plan-backup-revised" not in first_ids
    assert "plan-backup-revised" in second_ids
    statuses = {p["id"]: p["status"] for p in planners[1]["plans"]}
    assert statuses["plan-backup"] == "rejected" and statuses["plan-backup-revised"] == "revised"
    # the revising Planner was shown the Verifier's objection and may not pick the rejected plan
    revise_prompt = [p for p in model.prompts if "Verifier objection to answer" in p]
    assert len(revise_prompt) == 1 and VERIFIER_TEXT in revise_prompt[0]
    assert "Allowed plan ids: plan-wait, plan-contractor, plan-backup-revised" in revise_prompt[0]
    assert planners[1]["recommendedPlanId"] == "plan-contractor"


def test_downstream_agents_consume_upstream_findings() -> None:
    model = fake()
    run_events(model)
    planner_prompt = next(p for p in model.prompts if "Findings from the other analysts" in p)
    assert HR_TEXT in planner_prompt and FINANCE_TEXT in planner_prompt
    assert "Dana Reyes is out" in planner_prompt
    verifier_prompt = next(p for p in model.prompts if "Plans under review" in p)
    assert "REJECTED: Displaces Marcus Lee" in verifier_prompt
    assert "Go with plan-backup." in verifier_prompt


def test_the_loop_is_capped_at_one_revision() -> None:
    state: RunState = {"verdict": {"decision": "rejected"}, "revisions": 0}
    assert graph_module.after_verifier(state) == "planner"
    state = {"verdict": {"decision": "rejected"}, "revisions": 1}
    assert graph_module.after_verifier(state) == "__end__"
    assert graph_module.after_verifier({"verdict": {"decision": "approved"}}) == "__end__"


def test_a_plan_that_stays_rejected_still_ends_after_one_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(solver, "plan_conflicts", lambda *_: ("always conflicting",))
    # every plan is rejected, so the only plan left to recommend is the revision of the backup
    model = fake(second="plan-backup-revised")
    events = run_events(model)
    assert model.call_count == 7  # never a third planner or verifier pass
    verdicts = [c["verdict"]["decision"] for c in completed(events) if c["node"] == "verifier"]
    assert verdicts == ["rejected", "rejected"]
    assert done_of(events)["verdict"]["decision"] == "rejected"


# ---- grounding and presets (AT-IMP-001-01, AT-PLAN-003-01) -----------------------------


def test_impact_still_covers_the_full_chain_as_evidence() -> None:
    impact = completed(run_events(fake()))[0]
    assert [e["ref"] for e in impact["evidenceUsed"]] == [
        "preset:dev-out-1-5",
        "task:T-A-INT",
        "task:T-A-QA",
        "milestone:M-A",
        "commitment:CM-1",
        "invoice:INV-1",
    ]
    report = solver.impact_report(get_twin(), "dev-out-1-5")
    assert impact["derivedFacts"] == [f.model_dump(mode="json") for f in report.facts]


def test_a_model_number_never_becomes_a_fact() -> None:
    model = llm.ScriptedChatModel(
        responder=lambda m: (
            json.dumps({"recommendedPlanId": "plan-contractor", "rationale": "Costs 999 dollars."})
            if role_of(m) == "Planner"
            else "It costs 999 dollars."
        )
    )
    for node in completed(run_events(model)):
        assert "999" not in json.dumps(node["derivedFacts"]), node["node"]


def test_specialists_cite_their_sources_as_evidence() -> None:
    by_node = {c["node"]: c for c in completed(run_events(fake()))}
    hr_refs = {e["ref"]: e.get("source") for e in by_node["hr_resource"]["evidenceUsed"]}
    assert hr_refs["person:PER-BACKUP"] == "hris"
    finance_refs = [e["ref"] for e in by_node["finance"]["evidenceUsed"]]
    assert "invoice:INV-1" in finance_refs and "budget:recovery" in finance_refs


def test_when_no_plan_meets_every_commitment_the_prompt_and_plans_say_so() -> None:
    model = fake()
    events = run_events(model, "dev-out-contractor-late")
    contractor = next(p for p in done_of(events)["plans"] if p["id"] == "plan-contractor")
    assert contractor["violatedConstraints"]  # honest about what is still missed
    planner_prompt = next(p for p in model.prompts if "Findings from the other analysts" in p)
    assert "MISSED" in planner_prompt


def test_every_preset_runs_to_done() -> None:
    for preset in ("dev-out-1-3", "dev-out-1-5", "dev-out-contractor-late"):
        events = run_events(fake(), preset)
        assert names(events)[-1] == "done", preset
        assert done_of(events)["verdict"]["decision"] == "approved", preset


def test_rerun_is_deterministic_apart_from_the_run_id_and_parallel_order() -> None:
    def normal(events: list[Event]) -> Any:
        body = [e for e in events if e[0] not in {"run_started", "budget", "node_started"}]
        done = body[-1]
        nodes_done = sorted(
            (e for e in body if e[0] == "node_completed"),
            key=lambda e: (e[1]["node"], e[1]["status"]),
        )
        return nodes_done, done

    first, second = run_events(fake()), run_events(fake())
    assert first[0][1]["runId"] != second[0][1]["runId"]
    assert normal(first) == normal(second)


# ---- honest failure and budget (AT-ORCH-005-01, AT-OPS-001-01) -------------------------


def test_impact_failure_stops_the_run_with_no_content() -> None:
    model = fake(fail_roles=("Impact Investigator",))
    events = run_events(model)
    assert names(events) == ["run_started", "node_started", "budget", "failed"]
    assert events[-1][1] == {
        "node": "impact",
        "message": "The model call failed.",
        "code": "UpstreamModelError",
    }
    assert model.call_count == 1


def test_a_failed_specialist_blocks_the_planner_and_sends_no_done() -> None:
    model = fake(fail_roles=("HR and Resource Analyst",))
    events = run_events(model)
    failed = [d for n, d in events if n == "failed"]
    assert [f["node"] for f in failed] == ["hr_resource"]
    assert "done" not in names(events)
    started = [d["node"] for n, d in events if n == "node_started"]
    assert "planner" not in started and "verifier" not in started
    assert model.call_count == 3  # impact, hr (failed), finance; nothing built on the gap


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        '{"recommendedPlanId": "plan-nope", "rationale": "x"}',
        '{"rationale": "x"}',
    ],
)
def test_an_unusable_planner_answer_fails_honestly(raw: str) -> None:
    events = run_events(fake(raw_planner={1: raw}))
    failed = [d for n, d in events if n == "failed"]
    assert failed == [
        {
            "node": "planner",
            "message": "The model's answer could not be used.",
            "code": "InvalidModelOutput",
        }
    ]
    assert "done" not in names(events)
    assert "verifier" not in [d["node"] for n, d in events if n == "node_started"]


def test_the_planner_cannot_pick_the_rejected_plan_when_revising() -> None:
    events = run_events(fake(second="plan-backup"))  # rejected plan is not an allowed id now
    assert [d["code"] for n, d in events if n == "failed"] == ["InvalidModelOutput"]
    assert "done" not in names(events)


def test_planner_json_inside_a_code_fence_is_still_accepted() -> None:
    fenced = '```json\n{"recommendedPlanId": "plan-contractor", "rationale": "Best fit."}\n```'
    events = run_events(fake(raw_planner={1: fenced}))
    assert names(events)[-1] == "done"


def test_a_budget_too_small_for_the_run_stops_honestly() -> None:
    model = fake()
    events = run_events(model, max_calls=3)
    failed = [d for n, d in events if n == "failed"]
    assert [(f["node"], f["code"]) for f in failed] == [("planner", "BudgetExceeded")]
    assert model.call_count == 3  # never exceeds the budget
    assert "done" not in names(events)


def test_zero_budget_refuses_the_first_call() -> None:
    model = fake()
    events = run_events(model, max_calls=0)
    assert names(events) == ["run_started", "node_started", "budget", "failed"]
    assert events[-1][1]["code"] == "BudgetExceeded" and model.call_count == 0


# ---- the HTTP endpoint -----------------------------------------------------------------


def parse_sse(text: str) -> list[Event]:
    parsed: list[Event] = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        assert lines[0].startswith("event: ") and lines[1].startswith("data: ")
        parsed.append((lines[0][7:], json.loads(lines[1][6:])))
    return parsed


def test_endpoint_streams_the_full_run_as_sse() -> None:
    model = fake()
    with llm.override_chat_model(model):
        response = client.post("/api/run/stream", json={"presetId": "dev-out-1-5"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in response.headers["cache-control"]
    events = parse_sse(response.text)
    assert names(events)[0] == "run_started" and names(events)[-1] == "done"
    assert len(completed(events)) == 7 and model.call_count == 7
    assert done_of(events)["verdict"]["decision"] == "approved"


@pytest.mark.parametrize("body", [{"presetId": "nope"}, {}, {"presetId": ""}, {"presetId": "a b"}])
def test_endpoint_rejects_bad_preset_without_calling_the_model(body: dict[str, str]) -> None:
    model = fake()
    with llm.override_chat_model(model):
        response = client.post("/api/run/stream", json=body)
    assert response.status_code == 400
    assert response.json()["code"] == "ValidationError"
    assert model.call_count == 0


def test_endpoint_reports_not_configured_without_leaking(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for name in ("LITELLM_BASE_URL", "LITELLM_API_KEY", "LITELLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    response = client.post("/api/run/stream", json={"presetId": "dev-out-1-5"})
    assert response.status_code == 503
    assert response.json()["code"] == "NotConfigured"


# ---- boundaries (rules section 3) ------------------------------------------------------


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_agents_never_reach_the_solver_or_upper_layers() -> None:
    for path in (ROOT / "agents").glob("*.py"):
        for module in _imports(path):
            assert not module.startswith(("twin.solver", "orchestration", "api")), (path, module)


def test_api_layer_never_calls_the_model_directly() -> None:
    for path in (ROOT / "api").glob("*.py"):
        for module in _imports(path):
            assert not module.startswith(("langchain", "openai", "agents")), (path, module)

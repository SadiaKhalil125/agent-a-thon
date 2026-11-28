"""The LangGraph `StateGraph`: nodes, edges and the per-node execution wrapper (TASK-009 to 013).

Flow: impact -> (hr_resource || finance) -> planner -> verifier -> [planner (revise) -> verifier].
The Verifier -> Planner edge is conditional and capped at one revision.

Agents are graph nodes. Every node goes through `run_node`, which owns what agents must not:
the streamed events, the one-unit budget reservation, and honest failure (a `failed` event and no
fabricated content). Numbers and the approve/reject decision come from `twin.solver`, called here
and handed to the agent; the agent supplies the reasoning text.

Per-node model-call count: impact 1, hr_resource 1, finance 1, planner 1 (+1 revision), verifier
1 (+1 re-review). A full run with a rejection is 7 calls against the default budget of 8.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from agents import llm, nodes, roles
from orchestration.budget import BudgetExceededError
from orchestration.state import MAX_REVISIONS, RunContext, RunState
from twin import solver
from twin.results import Plan

logger = logging.getLogger("companytwin.run")


def emit(event: str, data: dict[str, Any]) -> None:
    """Send one SSE event to the stream (picked up by the runner)."""
    get_stream_writer()({"event": event, "data": data})


def _context(config: RunnableConfig) -> RunContext:
    ctx = config.get("configurable", {}).get("ctx")
    if not isinstance(ctx, RunContext):
        raise RuntimeError("graph invoked without a RunContext")
    return ctx


def jsonable(value: Any) -> Any:
    """Turn plans (pydantic) and containers of them into plain JSON-ready data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def _node_payload(output: nodes.NodeOutput, budget: dict[str, int]) -> dict[str, Any]:
    return {
        "node": output.node,
        "role": output.role,
        "status": output.status,
        "evidenceUsed": [
            {k: v for k, v in (("ref", e.ref), ("label", e.label), ("source", e.source)) if v}
            for e in output.evidence
        ],
        "output": output.output,
        "derivedFacts": [fact.model_dump(mode="json") for fact in output.derived_facts],
        **jsonable(output.extras),
        "budget": budget,
    }


async def run_node(
    ctx: RunContext,
    node_id: str,
    role: str,
    call: Callable[[], Awaitable[nodes.NodeOutput]],
) -> nodes.NodeOutput | None:
    """Run one node: started -> reserve budget -> one model call -> completed, or failed.

    Returns None after emitting `failed` (no content is fabricated).
    """
    started = time.monotonic()
    emit("node_started", {"node": node_id, "role": role})

    def failed(message: str, code: str) -> None:
        emit("failed", {"node": node_id, "message": message, "code": code})

    try:
        ctx.budget.consume()
        emit("budget", ctx.budget.snapshot())
        output = await call()
    except BudgetExceededError:
        emit("budget", ctx.budget.snapshot())
        failed("The run's model-call budget is exhausted.", "BudgetExceeded")
        return None
    except llm.InvalidModelOutputError:
        failed("The model's answer could not be used.", "InvalidModelOutput")
        return None
    except llm.UpstreamModelError:
        failed("The model call failed.", "UpstreamModelError")
        return None
    except Exception as exc:
        logger.error("node %s crashed: %s", node_id, type(exc).__name__)
        failed("The step could not be completed.", "InternalError")
        return None
    budget = ctx.budget.snapshot()
    logger.info(
        "runId=%s node=%s role=%s duration_ms=%.0f call_count=%d budget_remaining=%d",
        ctx.run_id,
        node_id,
        role,
        (time.monotonic() - started) * 1000,
        budget["used"],
        budget["max"] - budget["used"],
    )
    emit("node_completed", _node_payload(output, budget))
    return output


# ---- helpers ---------------------------------------------------------------------------


def _text(state: RunState, node_id: str) -> str:
    return str(state["outputs"][node_id].output)


def _final_statuses(plans: list[Plan], rejected: tuple[str, ...]) -> tuple[Plan, ...]:
    """Final status per plan: rejected, revised (kept as the solver set it) or verified."""
    out: list[Plan] = []
    for plan in plans:
        if plan.id in rejected:
            out.append(plan.model_copy(update={"status": "rejected"}))
        elif plan.status == "revised":
            out.append(plan)
        else:
            out.append(plan.model_copy(update={"status": "verified"}))
    return tuple(out)


def _revisions_of(ctx: RunContext, rejected: tuple[str, ...]) -> list[Plan]:
    revised: list[Plan] = []
    for plan_id in rejected:
        try:
            revised.append(solver.revise_plan(ctx.twin, ctx.preset_id, plan_id))
        except ValueError:
            continue  # this plan has no revision; the Planner simply works without it
    return revised


def _trail_plans(
    candidates: list[Plan], in_play: list[Plan], rejected: tuple[str, ...]
) -> tuple[Plan, ...]:
    """Plans as shown in the Planner event: rejected ones are marked, revisions follow."""
    candidate_ids = {c.id for c in candidates}
    shown = [
        c.model_copy(update={"status": "rejected"}) if c.id in rejected else c for c in candidates
    ]
    shown += [p for p in in_play if p.id not in candidate_ids]
    return tuple(shown)


# ---- nodes -----------------------------------------------------------------------------


async def impact_node(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)

    async def call() -> nodes.NodeOutput:
        report = solver.impact_report(ctx.twin, ctx.preset_id)
        return await nodes.run_impact(report, ctx.twin.preset(ctx.preset_id), ctx.model)

    output = await run_node(ctx, "impact", roles.IMPACT.title, call)
    if output is None:
        return {"failed": True}
    return {"outputs": {"impact": output}}


async def hr_resource_node(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)

    async def call() -> nodes.NodeOutput:
        report = solver.resource_report(ctx.twin, ctx.preset_id)
        return await nodes.run_hr_resource(report, ctx.twin.preset(ctx.preset_id), ctx.model)

    output = await run_node(ctx, "hr_resource", roles.HR_RESOURCE.title, call)
    if output is None:
        return {"failed": True}
    return {"outputs": {"hr_resource": output}}


async def finance_node(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)

    async def call() -> nodes.NodeOutput:
        twin = ctx.twin
        report = solver.finance_report(twin, ctx.preset_id)
        invoices = [(i.id, f"{i.id}: {i.amount} {i.currency}") for i in twin.invoices]
        return await nodes.run_finance(
            report,
            solver.candidate_plans(twin, ctx.preset_id),
            invoices,
            twin.preset(ctx.preset_id),
            twin.budget.currency,
            ctx.model,
        )

    output = await run_node(ctx, "finance", roles.FINANCE.title, call)
    if output is None:
        return {"failed": True}
    return {"outputs": {"finance": output}}


async def planner_node(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)
    if state.get("failed"):
        return {}  # an upstream node failed honestly; do not build on missing findings
    twin = ctx.twin
    objection = state.get("objection")
    revising = objection is not None
    rejected = tuple(state.get("rejectedPlanIds", ()))
    candidates = list(solver.candidate_plans(twin, ctx.preset_id))

    if revising:
        # Rejected plans leave the table; their revisions (if any) take their place.
        in_play = [p for p in candidates if p.id not in rejected] + _revisions_of(ctx, rejected)
    else:
        in_play = candidates
    shown = _trail_plans(candidates, in_play, rejected)
    allowed = [p.id for p in in_play]

    async def call() -> nodes.NodeOutput:
        result = await nodes.run_planner(
            plans=in_play,
            allowed_ids=allowed,
            impact=_text(state, "impact"),
            hr_resource=_text(state, "hr_resource"),
            finance=_text(state, "finance"),
            currency=twin.budget.currency,
            model=ctx.model,
            objection=objection,
        )
        return dataclasses.replace(
            result,
            status="revised" if revising else "done",
            extras={**result.extras, "plans": shown},
        )

    output = await run_node(ctx, "planner", roles.PLANNER.title, call)
    if output is None:
        return {"failed": True}
    return {
        "outputs": {"planner": output},
        "plans": tuple(in_play),
        "recommendedPlanId": output.extras["recommendedPlanId"],
        "revisions": int(state.get("revisions", 0)) + (1 if revising else 0),
    }


async def verifier_node(state: RunState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)
    if state.get("failed"):
        return {}
    twin = ctx.twin
    plans: list[Plan] = list(state["plans"])
    conflicts = {p.id: solver.plan_conflicts(twin, ctx.preset_id, p) for p in plans}
    newly_rejected = tuple(p.id for p in plans if conflicts[p.id])
    decision = "rejected" if newly_rejected else "approved"
    recommended = state.get("recommendedPlanId")
    reviewed = newly_rejected[0] if newly_rejected else recommended

    async def call() -> nodes.NodeOutput:
        result = await nodes.run_verifier(
            plans=plans,
            conflicts=conflicts,
            recommended_id=recommended,
            planner_rationale=_text(state, "planner"),
            currency=twin.budget.currency,
            model=ctx.model,
        )
        verdict = {"planId": reviewed, "decision": decision, "reason": result.output}
        return dataclasses.replace(
            result,
            status="rejected" if decision == "rejected" else "done",
            extras={"verdict": verdict},
        )

    output = await run_node(ctx, "verifier", roles.VERIFIER.title, call)
    if output is None:
        return {"failed": True}

    rejected_all = (*state.get("rejectedPlanIds", ()), *newly_rejected)
    candidates = list(solver.candidate_plans(twin, ctx.preset_id))
    candidate_ids = {c.id for c in candidates}
    revisions = [p for p in plans if p.id not in candidate_ids]
    return {
        "outputs": {"verifier": output},
        "verdict": output.extras["verdict"],
        "rejectedPlanIds": rejected_all,
        "objection": output.output if decision == "rejected" else None,
        "finalPlans": _final_statuses([*candidates, *revisions], rejected_all),
    }


# ---- edges -----------------------------------------------------------------------------


def after_impact(state: RunState) -> list[str] | str:
    return END if state.get("failed") else ["hr_resource", "finance"]


def after_planner(state: RunState) -> str:
    return END if state.get("failed") else "verifier"


def after_verifier(state: RunState) -> str:
    """The one conditional edge: a rejection sends the run back to the Planner, once."""
    if state.get("failed"):
        return END
    verdict = state.get("verdict") or {}
    if verdict.get("decision") == "rejected" and state.get("revisions", 0) < MAX_REVISIONS:
        return "planner"
    return END


def build_graph() -> CompiledStateGraph[RunState, Any, Any, Any]:
    graph: StateGraph[RunState, Any, Any, Any] = StateGraph(RunState)
    graph.add_node("impact", impact_node)
    graph.add_node("hr_resource", hr_resource_node)
    graph.add_node("finance", finance_node)
    graph.add_node("planner", planner_node)
    graph.add_node("verifier", verifier_node)
    graph.add_edge(START, "impact")
    graph.add_conditional_edges("impact", after_impact, ["hr_resource", "finance", END])
    graph.add_edge(["hr_resource", "finance"], "planner")  # waits for both specialists
    graph.add_conditional_edges("planner", after_planner, ["verifier", END])
    graph.add_conditional_edges("verifier", after_verifier, ["planner", END])
    return graph.compile()


@lru_cache(maxsize=1)
def get_graph() -> CompiledStateGraph[RunState, Any, Any, Any]:
    return build_graph()


__all__ = ["build_graph", "emit", "get_graph", "jsonable", "run_node"]

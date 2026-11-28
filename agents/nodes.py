"""Agent functions run by the graph nodes (TASK-010 to 013).

Each function makes exactly ONE model call over solver-derived facts it is handed and returns a
`NodeOutput`. They never compute numbers, never decide feasibility, and know nothing about
streaming or the budget: the graph wrapper (`orchestration/graph.py`) owns events, budget, honest
failure and the approve/reject decision (taken from the solver's re-check).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from agents import llm, roles
from twin.model import Preset
from twin.results import (
    DerivedFact,
    FinanceReport,
    ImpactReport,
    Plan,
    ResourceReport,
)


@dataclass(frozen=True)
class Evidence:
    ref: str  # e.g. "task:T-A-INT"
    label: str
    source: str | None = None


@dataclass(frozen=True)
class NodeOutput:
    node: str
    role: str
    output: str  # the model's narrative
    evidence: tuple[Evidence, ...]
    derived_facts: tuple[DerivedFact, ...]  # solver facts, passed through unchanged
    extras: dict[str, Any] = field(default_factory=dict)  # extra node_completed fields
    status: str = "done"  # node_completed status: done | rejected | revised


async def _narrate(
    role: roles.Role,
    messages: Sequence[BaseMessage],
    model: BaseChatModel,
    evidence: tuple[Evidence, ...],
    facts: tuple[DerivedFact, ...],
    extras: dict[str, Any] | None = None,
    text: str | None = None,
) -> NodeOutput:
    answer = text if text is not None else await llm.ainvoke_model(model, messages)
    return NodeOutput(
        node=role.node,
        role=role.title,
        output=answer,
        evidence=evidence,
        derived_facts=facts,
        extras=extras or {},
    )


# ---- Impact, HR/Resource, Finance ------------------------------------------------------


async def run_impact(report: ImpactReport, preset: Preset, model: BaseChatModel) -> NodeOutput:
    """Impact Investigator: narrate the solver's dependency chain (one model call)."""
    evidence = (
        Evidence(f"preset:{preset.id}", preset.label, preset.source.system),
        *(Evidence(f"{node.type}:{node.id}", node.label, "twin") for node in report.chain),
    )
    return await _narrate(
        roles.IMPACT,
        roles.build_impact_messages(report, preset),
        model,
        evidence,
        report.facts,
    )


async def run_hr_resource(
    report: ResourceReport, preset: Preset, model: BaseChatModel
) -> NodeOutput:
    """HR/Resource Analyst: who can cover, on which free days (one model call)."""
    evidence = (
        Evidence(f"preset:{preset.id}", preset.label, preset.source.system),
        *(Evidence(f"person:{c.personId}", c.name, "hris") for c in report.candidates),
    )
    return await _narrate(
        roles.HR_RESOURCE,
        roles.build_hr_resource_messages(report, preset),
        model,
        evidence,
        report.facts,
    )


async def run_finance(
    report: FinanceReport,
    plans: Sequence[Plan],
    invoices: Sequence[tuple[str, str]],
    preset: Preset,
    currency: str,
    model: BaseChatModel,
) -> NodeOutput:
    """Finance Analyst: invoice exposure and cost against the budget (one model call)."""
    evidence = (
        Evidence("budget:recovery", "Delivery recovery budget", "erp"),
        *(Evidence(f"invoice:{inv_id}", label, "erp") for inv_id, label in invoices),
        *(Evidence(f"plan:{p.id}", p.name, "solver") for p in plans),
    )
    return await _narrate(
        roles.FINANCE,
        roles.build_finance_messages(report, plans, preset, currency),
        model,
        evidence,
        report.facts,
    )


# ---- Planner ---------------------------------------------------------------------------


def plan_facts(plans: Sequence[Plan], currency: str) -> tuple[DerivedFact, ...]:
    """Solver values per plan as labeled facts (formatting only; nothing is computed)."""
    facts: list[DerivedFact] = []
    for plan in plans:
        done = ", ".join(
            f"Project {key} day {day if day is not None else 'not within the horizon'}"
            for key, day in plan.projectCompletion.items()
        )
        facts.append(DerivedFact(label=f"{plan.name}: completion", value=done, tag="calculated"))
        facts.append(
            DerivedFact(
                label=f"{plan.name}: incremental cost",
                value=f"{plan.incrementalCost} {currency}",
                tag="calculated",
            )
        )
        for constraint in plan.violatedConstraints:
            facts.append(
                DerivedFact(label=f"{plan.name}: violated", value=constraint, tag="calculated")
            )
    return tuple(facts)


def parse_recommendation(text: str, allowed_ids: Sequence[str]) -> tuple[str, str]:
    """Extract `{recommendedPlanId, rationale}`; refuse anything outside the allowed ids."""
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if 0 <= start < end else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise llm.InvalidModelOutputError("The model's answer could not be used.")
    plan_id, rationale = data.get("recommendedPlanId"), data.get("rationale")
    if (
        not isinstance(plan_id, str)
        or plan_id not in allowed_ids
        or not isinstance(rationale, str)
        or not rationale.strip()
    ):
        raise llm.InvalidModelOutputError("The model's answer could not be used.")
    return plan_id, rationale.strip()


async def run_planner(
    *,
    plans: Sequence[Plan],
    allowed_ids: Sequence[str],
    impact: str,
    hr_resource: str,
    finance: str,
    currency: str,
    model: BaseChatModel,
    objection: str | None = None,
) -> NodeOutput:
    """Planner: recommend one allowed plan and justify it (one model call)."""
    messages = roles.build_planner_messages(
        impact=impact,
        hr_resource=hr_resource,
        finance=finance,
        plans=plans,
        allowed_ids=allowed_ids,
        currency=currency,
        objection=objection,
    )
    text = await llm.ainvoke_model(model, messages)
    recommended, rationale = parse_recommendation(text, allowed_ids)
    return await _narrate(
        roles.PLANNER,
        messages,
        model,
        tuple(Evidence(f"plan:{p.id}", p.name, "solver") for p in plans),
        plan_facts(plans, currency),
        extras={"recommendedPlanId": recommended},
        text=rationale,
    )


# ---- Verifier --------------------------------------------------------------------------


async def run_verifier(
    *,
    plans: Sequence[Plan],
    conflicts: dict[str, tuple[str, ...]],
    recommended_id: str | None,
    planner_rationale: str,
    currency: str,
    model: BaseChatModel,
) -> NodeOutput:
    """Verifier: explain the engine's feasibility result as an independent challenge.

    The approve/reject decision is the solver's re-check (`conflicts`), taken by the graph. The
    model supplies the reasoning shown to the evaluator.
    """
    facts = tuple(
        DerivedFact(
            label=f"{plan.name}: feasibility",
            value=" | ".join(conflicts[plan.id]) if conflicts.get(plan.id) else "feasible",
            tag="calculated",
        )
        for plan in plans
    )
    return await _narrate(
        roles.VERIFIER,
        roles.build_verifier_messages(
            plans=plans,
            conflicts=conflicts,
            currency=currency,
            recommended_id=recommended_id,
            planner_rationale=planner_rationale,
        ),
        model,
        tuple(Evidence(f"plan:{p.id}", p.name, "solver") for p in plans),
        facts,
    )


__all__ = [
    "Evidence",
    "NodeOutput",
    "parse_recommendation",
    "plan_facts",
    "run_finance",
    "run_hr_resource",
    "run_impact",
    "run_planner",
    "run_verifier",
]

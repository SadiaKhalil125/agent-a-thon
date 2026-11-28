"""Role definitions (system prompt + input builder) for the five reasoning agents.

Impact Investigator, HR/Resource, Finance, Planner and Verifier (TASK-010 to 013). Roles reason and
narrate over solver facts; they NEVER compute numbers. Each builder returns the node's single
prompt. Every system prompt starts "You are the <title>", which the test fake keys on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from twin.model import Preset
from twin.results import DerivedFact, FinanceReport, ImpactReport, Plan, ResourceReport


@dataclass(frozen=True)
class Role:
    node: str  # graph node id (contract)
    title: str  # display role name
    system_prompt: str


_GROUNDING = (
    "All company data is fictional and was computed by a deterministic engine. Use ONLY the facts "
    "you are given. Quote every number, day and amount exactly as written; never calculate, "
    "estimate, round or invent a number, date, person or amount."
)
_PROSE = " Write plain prose: no headings, no bullet lists, no markdown."

IMPACT = Role(
    node="impact",
    title="Impact Investigator",
    system_prompt=(
        "You are the Impact Investigator for Northstar Systems, a fictional company. A business "
        "event is being assessed: either a disruption to the schedule, or a new client "
        "commitment agreed in a meeting. In 3 to 5 sentences, explain how it propagates along the "
        "given chain from the affected or newly requested task, through dependent work, to the "
        "milestone, the customer commitment and the invoice, and what is at risk. Do not "
        "recommend a plan. " + _GROUNDING + _PROSE
    ),
)

HR_RESOURCE = Role(
    node="hr_resource",
    title="HR and Resource Analyst",
    system_prompt=(
        "You are the HR and Resource Analyst for Northstar Systems, a fictional company. Using "
        "the capacity facts, explain in 3 to 5 sentences who could take on the affected or newly "
        "requested work, "
        "on which working days they are actually free, and which existing bookings constrain "
        "them. Flag any conflict with work already committed. Do not recommend a plan. "
        + _GROUNDING
        + _PROSE
    ),
)

FINANCE = Role(
    node="finance",
    title="Finance Analyst",
    system_prompt=(
        "You are the Finance Analyst for Northstar Systems, a fictional company. Using the "
        "finance facts, explain in 3 to 5 sentences what the invoice exposure or quoted value "
        "is, what each option would cost against the recovery budget, and which options keep "
        "the invoices eligible. Do not recommend a plan. " + _GROUNDING + _PROSE
    ),
)

PLANNER = Role(
    node="planner",
    title="Planner",
    system_prompt=(
        "You are the Planner for Northstar Systems, a fictional company. You are given the "
        "findings of the Impact Investigator, the HR and Resource Analyst and the Finance "
        "Analyst, and the candidate plans computed by the engine. Recommend exactly "
        "one plan from the allowed ids and justify it by comparing the trade-offs. If no plan "
        "meets every commitment, say so plainly and name what is missed. If a Verifier "
        "objection is given, say how your recommendation answers it. " + _GROUNDING + " "
        'Reply with ONLY a JSON object, no other text: {"recommendedPlanId": "<allowed id>", '
        '"rationale": "<3 to 5 sentences of plain prose>"}'
    ),
)

VERIFIER = Role(
    node="verifier",
    title="Verifier",
    system_prompt=(
        "You are the Verifier for Northstar Systems, a fictional company. You independently "
        "challenge the Planner's plans. The engine has already re-checked each plan's schedule "
        "and tells you the feasibility result for each; that result is final. In 3 to 5 "
        "sentences: if any plan is rejected, state the objection precisely (who and what is "
        "affected, with the exact days) and what a revised plan must change. If none is "
        "rejected, confirm what you checked and name any remaining trade-off honestly (for "
        "example a deadline a plan still misses). " + _GROUNDING + _PROSE
    ),
)


def _facts(facts: Sequence[DerivedFact]) -> list[str]:
    return [f"- {fact.label}: {fact.value} [{fact.tag}]" for fact in facts]


def _messages(role: Role, lines: list[str]) -> list[BaseMessage]:
    return [SystemMessage(content=role.system_prompt), HumanMessage(content="\n".join(lines))]


def plan_line(plan: Plan, currency: str) -> str:
    """One plan as text for a prompt: solver values only, no arithmetic."""
    done = ", ".join(
        f"Project {key} done day {day if day is not None else 'not within the horizon'}"
        for key, day in plan.projectCompletion.items()
    )
    deadlines = "; ".join(
        f"{d.name} due day {d.dueDay} {'met' if d.met else 'MISSED'}" for d in plan.deadlines
    )
    violated = "; ".join(plan.violatedConstraints) or "none"
    return (
        f"- id={plan.id} | {plan.name} | {done} | {deadlines} | incremental cost "
        f"{plan.incrementalCost} {currency} | within recovery budget: "
        f"{'yes' if plan.budgetFit else 'no'} | invoice eligible on time: "
        f"{'yes' if plan.invoiceEligible else 'no'} | violated constraints: {violated}"
    )


def build_impact_messages(report: ImpactReport, preset: Preset) -> list[BaseMessage]:
    """The Impact node's single prompt: the disruption, the chain and the solver's facts."""
    lines = [
        f"Event: {preset.label} (source system: {preset.source.system}).",
        "",
        "Dependency chain, in order:",
        *(f"{index}. [{node.type}] {node.label}" for index, node in enumerate(report.chain, 1)),
        "",
        "Facts (tag shows where each came from):",
        *_facts(report.facts),
    ]
    return _messages(IMPACT, lines)


def build_hr_resource_messages(report: ResourceReport, preset: Preset) -> list[BaseMessage]:
    lines = [
        f"Event: {preset.label}.",
        f"Skill needed for the affected work: {report.requiredSkill}. "
        f"Planning window: working days 1 to {report.windowEndDay}.",
        "",
        "People who could be involved:",
        *(f"- {c.name} ({c.kind}): {c.note}" for c in report.candidates),
        "",
        "Facts (tag shows where each came from):",
        *_facts(report.facts),
    ]
    return _messages(HR_RESOURCE, lines)


def build_finance_messages(
    report: FinanceReport, plans: Sequence[Plan], preset: Preset, currency: str
) -> list[BaseMessage]:
    names = {plan.id: plan.name for plan in plans}
    lines = [
        f"Event: {preset.label}.",
        "",
        "Options and their finance results:",
        *(
            f"- {names.get(p.planId, p.planId)}: incremental cost {p.incrementalCost} "
            f"{currency}, within recovery budget: {'yes' if p.budgetFit else 'no'}, "
            f"invoice eligible on time: {'yes' if p.invoiceEligible else 'no'}"
            for p in report.plans
        ),
        "",
        "Facts (tag shows where each came from):",
        *_facts(report.facts),
    ]
    return _messages(FINANCE, lines)


def build_planner_messages(
    *,
    impact: str,
    hr_resource: str,
    finance: str,
    plans: Sequence[Plan],
    allowed_ids: Sequence[str],
    currency: str,
    objection: str | None = None,
) -> list[BaseMessage]:
    lines = [
        "Findings from the other analysts:",
        f"Impact Investigator: {impact}",
        f"HR and Resource Analyst: {hr_resource}",
        f"Finance Analyst: {finance}",
        "",
        "Candidate plans (computed by the engine):",
        *(plan_line(plan, currency) for plan in plans),
        "",
        f"Allowed plan ids: {', '.join(allowed_ids)}",
    ]
    if objection:
        lines += ["", f"Verifier objection to answer: {objection}"]
    return _messages(PLANNER, lines)


def build_verifier_messages(
    *,
    plans: Sequence[Plan],
    conflicts: dict[str, tuple[str, ...]],
    currency: str,
    recommended_id: str | None,
    planner_rationale: str,
) -> list[BaseMessage]:
    rejected = [plan for plan in plans if conflicts.get(plan.id)]
    lines = [
        f"Planner's recommendation: {recommended_id or 'none'}. Planner's reasoning: "
        f"{planner_rationale}",
        "",
        "Plans under review:",
        *(plan_line(plan, currency) for plan in plans),
        "",
        "Engine feasibility re-check (final):",
    ]
    for plan in plans:
        found = conflicts.get(plan.id, ())
        lines.append(f"- {plan.id}: {'REJECTED: ' + ' | '.join(found) if found else 'feasible'}")
    overall = "REJECTED (" + ", ".join(p.id for p in rejected) + ")" if rejected else "APPROVED"
    lines += ["", f"Overall result: {overall}"]
    return _messages(VERIFIER, lines)


__all__ = [
    "FINANCE",
    "HR_RESOURCE",
    "IMPACT",
    "PLANNER",
    "VERIFIER",
    "Role",
    "build_finance_messages",
    "build_hr_resource_messages",
    "build_impact_messages",
    "build_planner_messages",
    "build_verifier_messages",
    "plan_line",
]

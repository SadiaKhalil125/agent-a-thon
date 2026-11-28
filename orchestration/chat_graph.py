"""The "Ask the company" LangGraph `StateGraph` (ADR-006): tool-using agents over the company data.

Flow: orchestrator -> specialist x N (parallel, one per department needed) -> synthesizer.
A "general" question stops after the orchestrator with an honest general reply.

Each node runs through `run_chat_node`, which owns the streamed events, the model-call budget and
honest failure (a `failed` event and no fabricated content). A specialist runs a bounded tool loop:
at most `MAX_ROUNDS` model calls, each reserved from the shared budget, with the last round forced
to answer from what it has. Specialists and the synthesizer never compute numbers: values come from
tool results, and the final answer's numbers are checked against them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import operator
import re
import threading
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from agents import chat_roles, chat_tools, llm
from datahub import db, event_twin
from orchestration.budget import BudgetExceededError, RunBudget

logger = logging.getLogger("companytwin.chat")

MAX_ROUNDS = 4  # model calls per specialist (3 tool rounds, the last one must answer)
MAX_TOOLS_PER_ROUND = 4
MAX_AREAS = 3
MAX_ARG_CHARS = 300  # argument values shown in the stream

_CITATION = re.compile(r"\[c(\d+)\]")


# ---- per-question context -----------------------------------------------------------------


@dataclass
class ChatContext:
    run_id: str
    question: str
    history: tuple[tuple[str, str], ...]
    model: BaseChatModel
    budget: RunBudget  # model calls
    tool_budget: RunBudget  # data-tool calls
    today: str
    weekday: str
    calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    result_numbers: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def next_call_id(self) -> str:
        with self._lock:
            call_id = f"c{len(self.calls) + 1}"
            self.calls[call_id] = {"id": call_id}
            return call_id

    def record(
        self, call_id: str, tool: str, args: dict[str, Any], envelope: dict[str, Any]
    ) -> None:
        shown = chat_tools.preview(envelope)
        entry = {
            "id": call_id,
            "tool": tool,
            "arguments": _short_args(args),
            "ok": bool(envelope.get("ok")),
            "rowCount": shown.get("rowCount", 0),
        }
        for key in ("total", "truncated"):
            if key in shown:
                entry[key] = shown[key]
        with self._lock:
            self.calls[call_id] = entry
            self.result_numbers |= chat_tools.numbers_in(
                json.dumps(envelope, default=str, separators=(",", ":"))
            )


def _short_args(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in args.items():
        out[str(key)[:60]] = value[:MAX_ARG_CHARS] if isinstance(value, str) else value
    return out


def _context(config: RunnableConfig) -> ChatContext:
    ctx = config.get("configurable", {}).get("ctx")
    if not isinstance(ctx, ChatContext):
        raise RuntimeError("chat graph invoked without a ChatContext")
    return ctx


def emit(event: str, data: dict[str, Any]) -> None:
    get_stream_writer()({"event": event, "data": data})


# ---- node wrapper -------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatNodeOutput:
    text: str
    extras: dict[str, Any] = field(default_factory=dict)


async def run_chat_node(
    ctx: ChatContext,
    node_id: str,
    role: str,
    call: Callable[[], Awaitable[ChatNodeOutput]],
) -> ChatNodeOutput | None:
    """started -> (the call reserves its own model-call budget) -> completed, or `failed`."""
    started = time.monotonic()
    emit("node_started", {"node": node_id, "role": role})

    def failed(message: str, code: str) -> None:
        emit("failed", {"node": node_id, "message": message, "code": code})

    try:
        output = await call()
    except BudgetExceededError:
        emit("budget", ctx.budget.snapshot())
        failed("The question's model-call budget is exhausted.", "BudgetExceeded")
        return None
    except llm.InvalidModelOutputError:
        failed("The model's answer could not be used.", "InvalidModelOutput")
        return None
    except llm.UpstreamModelError:
        failed("The model call failed.", "UpstreamModelError")
        return None
    except Exception as exc:
        logger.error("chat node %s crashed: %s", node_id, type(exc).__name__)
        failed("The step could not be completed.", "InternalError")
        return None
    budget = ctx.budget.snapshot()
    logger.info(
        "runId=%s node=%s duration_ms=%.0f model_calls=%d tool_calls=%d",
        ctx.run_id,
        node_id,
        (time.monotonic() - started) * 1000,
        budget["used"],
        ctx.tool_budget.snapshot()["used"],
    )
    emit(
        "node_completed",
        {
            "node": node_id,
            "role": role,
            "status": "done",
            "output": output.text,
            **output.extras,
            "budget": budget,
        },
    )
    return output


def _reserve_model_call(ctx: ChatContext) -> None:
    ctx.budget.consume()
    emit("budget", ctx.budget.snapshot())


# ---- orchestrator -------------------------------------------------------------------------


def parse_route(text: str) -> dict[str, Any]:
    """Validate the orchestrator's JSON. Anything outside the contract is refused."""
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if 0 <= start < end else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise llm.InvalidModelOutputError("The model's answer could not be used.")
    mode = data.get("mode")
    if mode == "general":
        reply = data.get("reply")
        if not isinstance(reply, str) or not reply.strip() or len(reply) > 4000:
            raise llm.InvalidModelOutputError("The model's answer could not be used.")
        return {"mode": "general", "reply": reply.strip(), "areas": []}
    if mode == "event":
        event = data.get("event")
        person = event.get("person") if isinstance(event, dict) else None
        when = event.get("start_date") if isinstance(event, dict) else None
        days = event.get("working_days") if isinstance(event, dict) else None
        if (
            not isinstance(person, str)
            or not person.strip()
            or len(person) > 80
            or not (when is None or (isinstance(when, str) and len(when) <= 10))
            or isinstance(days, bool)
            or not isinstance(days, int)
        ):
            raise llm.InvalidModelOutputError("The model's answer could not be used.")
        return {
            "mode": "event",
            "reply": "",
            "areas": [],
            "event": {"person": person.strip(), "start": when, "days": days},
        }
    areas = data.get("areas")
    if mode != "company" or not isinstance(areas, list) or not 1 <= len(areas) <= MAX_AREAS:
        raise llm.InvalidModelOutputError("The model's answer could not be used.")
    parsed: list[dict[str, str]] = []
    for item in areas:
        area = item.get("area") if isinstance(item, dict) else None
        question = item.get("question") if isinstance(item, dict) else None
        if (
            area not in chat_tools.SPECIALIST_AREAS
            or any(p["area"] == area for p in parsed)
            or not isinstance(question, str)
            or not question.strip()
            or len(question) > 600
        ):
            raise llm.InvalidModelOutputError("The model's answer could not be used.")
        parsed.append({"area": area, "question": question.strip()})
    return {"mode": "company", "reply": "", "areas": parsed}


class ChatState(TypedDict, total=False):
    mode: str
    reply: str
    areas: list[dict[str, str]]
    event: dict[str, Any]
    findings: Annotated[list[tuple[str, str]], operator.add]
    failed: Annotated[bool, operator.or_]
    answer: dict[str, Any]


class SpecialistInput(TypedDict):
    area: str
    question: str


async def orchestrator_node(state: ChatState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)

    async def call() -> ChatNodeOutput:
        _reserve_model_call(ctx)
        messages = chat_roles.build_orchestrator_messages(
            ctx.question, ctx.history, ctx.today, ctx.weekday
        )
        route = parse_route(await llm.ainvoke_model(ctx.model, messages))
        if route["mode"] == "general":
            text = "General question: answered without company data."
        else:
            text = "; ".join(
                f"{chat_roles.AREA_TITLES[a['area']]}: {a['question']}" for a in route["areas"]
            )
        return ChatNodeOutput(text, {"route": route})

    out = await run_chat_node(ctx, "orchestrator", chat_roles.ORCHESTRATOR.title, call)
    if out is None:
        return {"failed": True}
    route = out.extras["route"]
    return {
        "mode": route["mode"],
        "reply": route["reply"],
        "areas": route["areas"],
        "event": route.get("event", {}),
    }


def after_orchestrator(state: ChatState) -> list[Send] | str:
    if state.get("failed"):
        return END
    if state.get("mode") == "general":
        return "general"
    if state.get("mode") == "event":
        return "event"
    return [
        Send("specialist", {"area": a["area"], "question": a["question"]}) for a in state["areas"]
    ]


def general_node(state: ChatState) -> dict[str, Any]:
    return {
        "answer": {
            "mode": "general",
            "text": state["reply"],
            "citations": [],
            "unverifiedNumbers": [],
            "areas": [],
        }
    }


# ---- reported events (no model call: the person and dates are resolved by code) ---------------


def _event_answer(mode: str, text: str, event: dict[str, Any] | None = None) -> dict[str, Any]:
    answer: dict[str, Any] = {
        "mode": mode,
        "text": text,
        "citations": [],
        "unverifiedNumbers": [],
        "areas": [],
    }
    if event is not None:
        answer["event"] = event
    return answer


def event_node(state: ChatState) -> dict[str, Any]:
    """Resolve the reported leave to a real employee and check it disrupts work. If it does, the
    answer carries the event so the demo starts the recovery flow; if not, it says why."""
    spec = state.get("event", {})
    start = spec.get("start")
    try:
        event = event_twin.resolve_leave(
            str(spec.get("person", "")),
            None if start in (None, "", "null") else str(start),
            int(spec.get("days", 0)),
        )
        twin = event_twin.build_leave_twin(event)  # raises NoImpactError / EventError
    except event_twin.NoImpactError as exc:
        return {"answer": _event_answer("clarify", f"{exc} No recovery flow is needed.")}
    except event_twin.EventError as exc:
        return {"answer": _event_answer("clarify", str(exc))}
    except ValueError:  # an out-of-range value from the model
        return {"answer": _event_answer("clarify", "I could not read the dates or days.")}
    person = twin.people[0].name
    calendar = event_twin.working_calendar()
    first = event_twin.day_number(calendar, event.startDate) or 1
    last = min(first + event.workingDays - 1, len(calendar))
    text = (
        f"{person} is out for {event.workingDays} working days, from "
        f"{calendar[first - 1].isoformat()} to {calendar[last - 1].isoformat()}. "
        "Starting the recovery flow on the company's real tickets, projects and budget."
    )
    return {
        "answer": _event_answer(
            "event",
            text,
            {
                "personId": event.personId,
                "startDate": event.startDate.isoformat(),
                "workingDays": event.workingDays,
            },
        )
    }


# ---- specialists (bounded tool loop) --------------------------------------------------------


async def _run_tool_call(
    ctx: ChatContext, node_id: str, index: int, call: dict[str, Any]
) -> ToolMessage:
    name = str(call.get("name", ""))
    raw_args = call.get("args")
    args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
    call_id = ctx.next_call_id()
    emit(
        "tool_call",
        {"node": node_id, "callId": call_id, "tool": name, "arguments": _short_args(args)},
    )
    if index >= MAX_TOOLS_PER_ROUND:
        envelope: dict[str, Any] = {"ok": False, "error": "Too many tool calls in one step."}
    else:
        try:
            ctx.tool_budget.consume()
        except BudgetExceededError:
            envelope = {
                "ok": False,
                "error": "Tool-call budget exhausted. Answer with what you have.",
            }
        else:
            envelope = await asyncio.to_thread(chat_tools.execute, name, args)
    ctx.record(call_id, name, args, envelope)
    emit(
        "tool_result",
        {"node": node_id, "callId": call_id, "tool": name, **chat_tools.preview(envelope)},
    )
    content = chat_tools.model_text({**envelope, "callId": call_id})
    return ToolMessage(content=content, tool_call_id=str(call.get("id") or call_id), name=name)


async def run_specialist(ctx: ChatContext, area: str, question: str) -> ChatNodeOutput:
    """Up to `MAX_ROUNDS` model calls; each may request tools. Returns the cited findings."""
    node_id = chat_roles.specialist_role(area).node
    messages: list[BaseMessage] = chat_roles.build_specialist_messages(
        area, question, ctx.today, ctx.weekday
    )
    with_tools = ctx.model.bind_tools(chat_tools.build_tools(area))
    used_tools = 0
    for round_no in range(MAX_ROUNDS):
        _reserve_model_call(ctx)
        if round_no == MAX_ROUNDS - 1:
            messages.append(HumanMessage(content=chat_roles.FINALIZE_NOTE))
            reply = await llm.ainvoke_message(ctx.model, messages)
        else:
            reply = await llm.ainvoke_message(with_tools, messages)
        messages.append(reply)
        if not reply.tool_calls:
            text = llm.text_of(reply)
            if not text:
                raise llm.InvalidModelOutputError("The model's answer could not be used.")
            return ChatNodeOutput(text, {"toolCalls": used_tools, "area": area})
        for index, call in enumerate(reply.tool_calls):
            messages.append(await _run_tool_call(ctx, node_id, index, dict(call)))
            used_tools += 1
    raise llm.InvalidModelOutputError("The model's answer could not be used.")  # unreachable


async def specialist_node(state: SpecialistInput, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)
    area, question = state["area"], state["question"]
    role = chat_roles.specialist_role(area)
    out = await run_chat_node(
        ctx, role.node, role.title, lambda: run_specialist(ctx, area, question)
    )
    if out is None:
        return {"failed": True}
    return {"findings": [(role.title, out.text)]}


# ---- synthesizer and the numeric check --------------------------------------------------------


def check_answer(ctx: ChatContext, text: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Citations used, numbers that match no tool result, and cited ids that do not exist."""
    cited = list(dict.fromkeys(_CITATION.findall(text)))
    known = [
        ctx.calls[f"c{n}"] for n in cited if f"c{n}" in ctx.calls and "tool" in ctx.calls[f"c{n}"]
    ]
    unknown = [
        f"c{n}" for n in cited if f"c{n}" not in ctx.calls or "tool" not in ctx.calls[f"c{n}"]
    ]
    body = _CITATION.sub(" ", text)
    body = re.sub(r"(?m)^\s*(?:\d+[.)]|[-*])\s+", "", body)  # list numbering is not a claim
    allowed = ctx.result_numbers | chat_tools.numbers_in(ctx.question)
    unverified = sorted(chat_tools.numbers_in(body) - allowed)
    return known, unverified, unknown


async def synthesizer_node(state: ChatState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _context(config)
    if state.get("failed"):
        return {}

    async def call() -> ChatNodeOutput:
        _reserve_model_call(ctx)
        messages = chat_roles.build_synthesizer_messages(
            ctx.question, ctx.history, state.get("findings", [])
        )
        text = await llm.ainvoke_model(ctx.model, messages)
        citations, unverified, unknown = check_answer(ctx, text)
        for call_id in unknown:  # a made-up call id is dropped, never shown as evidence
            text = text.replace(f"[{call_id}]", "")
        return ChatNodeOutput(
            text.strip(),
            {"citations": citations, "unverifiedNumbers": unverified, "droppedCitations": unknown},
        )

    out = await run_chat_node(ctx, "synthesizer", chat_roles.SYNTHESIZER.title, call)
    if out is None:
        return {"failed": True}
    return {
        "answer": {
            "mode": "company",
            "text": out.text,
            "citations": out.extras["citations"],
            "unverifiedNumbers": out.extras["unverifiedNumbers"],
            "areas": [a["area"] for a in state.get("areas", [])],
        }
    }


# ---- the graph -----------------------------------------------------------------------------


def build_chat_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    graph: StateGraph[Any, Any, Any, Any] = StateGraph(ChatState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("specialist", specialist_node)
    graph.add_node("general", general_node)
    graph.add_node("event", event_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator", after_orchestrator, ["specialist", "general", "event", END]
    )
    graph.add_edge("specialist", "synthesizer")
    graph.add_edge("general", END)
    graph.add_edge("event", END)
    graph.add_edge("synthesizer", END)
    return graph.compile()


@lru_cache(maxsize=1)
def get_chat_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    return build_chat_graph()


def new_context(
    run_id: str,
    question: str,
    history: Sequence[tuple[str, str]],
    model: BaseChatModel,
    *,
    max_calls: int,
    max_tool_calls: int,
) -> ChatContext:
    return ChatContext(
        run_id=run_id,
        question=question,
        history=tuple(history),
        model=model,
        budget=RunBudget(max_calls=max_calls),
        tool_budget=RunBudget(max_calls=max_tool_calls),
        today=db.as_of().isoformat(),
        weekday=db.meta("weekday") or "",
    )


__all__ = [
    "ChatContext",
    "ChatNodeOutput",
    "ChatState",
    "build_chat_graph",
    "check_answer",
    "get_chat_graph",
    "new_context",
    "parse_route",
    "run_chat_node",
    "run_specialist",
]

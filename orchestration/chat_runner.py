"""Run one "Ask the company" question through the chat graph and yield SSE events (ADR-006).

`prepare_ask` resolves everything that can fail before streaming starts (so the API can return a
clean 4xx/5xx); `stream_ask` then yields `(event, data)` pairs. Stateless: the conversation history
is whatever the client sent with this request, and nothing is kept afterwards.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

import config
from agents import llm
from orchestration import chat_graph

NotConfiguredError = llm.NotConfiguredError

MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 1000
MAX_QUESTION_CHARS = 1000


@dataclass(frozen=True)
class PreparedAsk:
    ctx: chat_graph.ChatContext
    timeout: float


def clean_history(history: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """The last few turns, each capped, labelled for the prompt."""
    labels = {"user": "User", "assistant": "Assistant"}
    return [
        (labels[role], text[:MAX_HISTORY_CHARS])
        for role, text in history[-MAX_HISTORY_MESSAGES:]
        if role in labels
    ]


def prepare_ask(
    question: str,
    history: Sequence[tuple[str, str]] = (),
    *,
    model: BaseChatModel | None = None,
    max_calls: int | None = None,
    max_tool_calls: int | None = None,
    timeout: float | None = None,
) -> PreparedAsk:
    resolved = model if model is not None else llm.get_chat_model()  # NotConfiguredError
    ctx = chat_graph.new_context(
        uuid.uuid4().hex[:12],
        question.strip()[:MAX_QUESTION_CHARS],
        clean_history(history),
        resolved,
        max_calls=config.chat_max_calls() if max_calls is None else max_calls,
        max_tool_calls=config.chat_max_tool_calls() if max_tool_calls is None else max_tool_calls,
    )
    return PreparedAsk(
        ctx=ctx, timeout=config.run_timeout_seconds() if timeout is None else timeout
    )


async def stream_ask(prepared: PreparedAsk) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    ctx = prepared.ctx
    yield (
        "run_started",
        {
            "runId": ctx.run_id,
            "question": ctx.question,
            "today": ctx.today,
            "budget": ctx.budget.snapshot(),
            "toolBudget": ctx.tool_budget.snapshot(),
        },
    )
    final: dict[str, Any] = {}
    stream: AsyncIterator[Any] = chat_graph.get_chat_graph().astream(
        {"findings": []},
        config={"configurable": {"ctx": ctx}},
        stream_mode=["custom", "values"],
    )
    try:
        async with asyncio.timeout(prepared.timeout):
            async for mode, chunk in stream:
                if mode == "custom":
                    yield str(chunk["event"]), dict(chunk["data"])
                else:
                    final = dict(chunk)
    except TimeoutError:
        yield (
            "failed",
            {
                "node": "run",
                "message": "The question took too long and was stopped.",
                "code": "Timeout",
            },
        )
        return
    if final.get("failed"):
        return  # a node already emitted `failed`; there is no verified answer, so no `done`
    answer = final.get("answer")
    if not isinstance(answer, dict):
        yield (
            "failed",
            {"node": "run", "message": "No answer was produced.", "code": "InternalError"},
        )
        return
    yield "answer", answer
    yield "done", {"budget": ctx.budget.snapshot(), "toolBudget": ctx.tool_budget.snapshot()}


__all__ = ["NotConfiguredError", "PreparedAsk", "clean_history", "prepare_ask", "stream_ask"]

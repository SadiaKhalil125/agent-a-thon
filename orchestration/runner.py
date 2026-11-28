"""Run one disruption through the graph and yield SSE events (TASK-010).

`prepare_run` validates and resolves everything that can fail *before* streaming starts (so the API
can return a clean 4xx/5xx); `stream_run` then yields `(event, data)` pairs. The run is
self-contained: no state is kept between requests.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

import config
from agents import llm
from orchestration.budget import RunBudget
from orchestration.graph import get_graph, jsonable
from orchestration.state import RunContext, RunState
from twin import solver
from twin.model import Twin
from twin.seed import get_twin


class UnknownPresetError(LookupError):
    """`presetId` is not one of the seed presets."""


NotConfiguredError = llm.NotConfiguredError


@dataclass(frozen=True)
class PreparedRun:
    ctx: RunContext
    timeout: float  # overall wall-clock limit for the streamed run, in seconds


def prepare_run(
    preset_id: str,
    *,
    twin: Twin | None = None,
    model: BaseChatModel | None = None,
    max_calls: int | None = None,
    timeout: float | None = None,
) -> PreparedRun:
    """Validate the preset and resolve the model and budget. Raises before any event is sent."""
    twin = twin or get_twin()
    if all(p.id != preset_id for p in twin.presets):
        raise UnknownPresetError(preset_id)
    twin = solver.effective_twin(twin, preset_id)  # a client-meeting preset adds the new work
    resolved = model if model is not None else llm.get_chat_model()  # NotConfiguredError
    budget = RunBudget(max_calls=config.max_calls_per_run() if max_calls is None else max_calls)
    ctx = RunContext(
        run_id=uuid.uuid4().hex[:12],
        preset_id=preset_id,
        twin=twin,
        model=resolved,
        budget=budget,
    )
    return PreparedRun(
        ctx=ctx, timeout=config.run_timeout_seconds() if timeout is None else timeout
    )


async def stream_run(prepared: PreparedRun) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    ctx = prepared.ctx
    preset = ctx.twin.preset(ctx.preset_id)
    yield (
        "run_started",
        {
            "runId": ctx.run_id,
            "presetId": ctx.preset_id,
            "event": preset.event.model_dump(mode="json", exclude_none=True),
            "budget": ctx.budget.snapshot(),
        },
    )
    initial: RunState = {"runId": ctx.run_id, "presetId": ctx.preset_id, "outputs": {}}
    final: dict[str, Any] = {}
    stream: AsyncIterator[Any] = get_graph().astream(
        initial, config={"configurable": {"ctx": ctx}}, stream_mode=["custom", "values"]
    )
    try:
        async with asyncio.timeout(prepared.timeout):
            async for item in stream:
                mode, chunk = item  # (stream mode, payload) pairs
                if mode == "custom":
                    yield str(chunk["event"]), dict(chunk["data"])
                else:
                    final = dict(chunk)
    except TimeoutError:
        yield (
            "failed",
            {
                "node": "run",
                "message": "The run took too long and was stopped.",
                "code": "Timeout",
            },
        )
        return
    if final.get("failed"):
        return  # a node already emitted `failed`; no verified result exists, so no `done`
    yield (
        "done",
        {
            "plans": jsonable(final.get("finalPlans", ())),
            "verdict": final.get("verdict"),
            "recommendedPlanId": final.get("recommendedPlanId"),
            "budget": ctx.budget.snapshot(),
        },
    )


__all__ = ["NotConfiguredError", "PreparedRun", "UnknownPresetError", "prepare_run", "stream_run"]

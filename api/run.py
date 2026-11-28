"""POST /api/run/stream: run the LangGraph graph and stream node events as SSE (TASK-010).

Validates the request and shapes the stream. It never calls the model: nodes do, inside the graph.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.errors import ApiError
from api.security import require_passcode
from orchestration.runner import (
    NotConfiguredError,
    UnknownPresetError,
    prepare_run,
    stream_run,
)

router = APIRouter()


class RunRequest(BaseModel):
    presetId: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def _frames(events: AsyncIterator[tuple[str, dict[str, Any]]]) -> AsyncIterator[str]:
    async for event, data in events:
        yield sse(event, data)


@router.post("/api/run/stream", dependencies=[Depends(require_passcode)])
async def run_stream(req: RunRequest) -> StreamingResponse:
    try:
        prepared = prepare_run(req.presetId)
    except UnknownPresetError:
        raise ApiError(400, "ValidationError", "Unknown presetId.") from None
    except NotConfiguredError:
        raise ApiError(
            503,
            "NotConfigured",
            "The AI provider is not configured on the server.",
        ) from None
    return StreamingResponse(
        _frames(stream_run(prepared)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


__all__ = ["router", "sse"]

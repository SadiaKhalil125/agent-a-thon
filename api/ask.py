"""POST /api/ask/stream: ask the company a question in natural language (ADR-006).

Validates the request and shapes the stream. It never calls the model or the data itself: the
chat graph does, through its agents and read-only tools. Stateless: the client sends the recent
conversation with every question.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.errors import ApiError
from api.run import _frames
from api.security import require_passcode
from orchestration.chat_runner import (
    MAX_HISTORY_CHARS,
    MAX_QUESTION_CHARS,
    NotConfiguredError,
    prepare_ask,
    stream_ask,
)

router = APIRouter()


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_HISTORY_CHARS)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)


@router.post("/api/ask/stream", dependencies=[Depends(require_passcode)])
async def ask_stream(req: AskRequest) -> StreamingResponse:
    try:
        prepared = prepare_ask(req.question, [(h.role, h.content) for h in req.history])
    except NotConfiguredError:
        raise ApiError(
            503,
            "NotConfigured",
            "The AI provider is not configured on the server.",
        ) from None
    return StreamingResponse(
        _frames(stream_ask(prepared)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]

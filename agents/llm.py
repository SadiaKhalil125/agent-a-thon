"""ChatOpenAI -> LiteLLM gateway factory (server-side only) and a fake model for tests (TASK-008).

This is the only place the chat model is constructed. It builds
`ChatOpenAI(base_url, api_key, model)` from `config.get_llm_settings()` (provider-neutral: the
endpoint, model and key come from the environment), with a timeout and **one** bounded retry.

Rules enforced here (docs/rules.md section 6):
- no fabricated content: a failed or empty model call raises `UpstreamModelError`, never a
  made-up answer;
- the key and the prompts/responses are never logged or put in an exception message;
- tests inject `ScriptedChatModel` through `override_chat_model`, so CI never spends budget.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from pydantic import Field, PrivateAttr, SecretStr

import config

logger = logging.getLogger("companytwin.llm")

DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_RETRIES = 1  # exactly one bounded retry (protects the budget and the 5-minute ceiling)


class NotConfiguredError(RuntimeError):
    """The LLM provider environment variables are not set (HTTP 503 `NotConfigured`)."""


class UpstreamModelError(RuntimeError):
    """A model call failed or returned nothing. The node must emit `failed` and no content."""


class InvalidModelOutputError(UpstreamModelError):
    """The model answered, but not in the required shape. Still no fabricated content."""


def build_chat_model(
    settings: config.LLMSettings | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> BaseChatModel:
    """Build the chat model for the configured gateway."""
    if settings is None:
        try:
            settings = config.get_llm_settings()
        except RuntimeError as exc:
            raise NotConfiguredError("LLM provider is not configured.") from exc
    return ChatOpenAI(
        model=settings.model,
        base_url=settings.base_url,
        api_key=SecretStr(settings.api_key),
        timeout=timeout,
        max_retries=MAX_RETRIES,
        temperature=0,
    )


# ---- injectable model (tests) ----------------------------------------------------------

_override: BaseChatModel | None = None


def get_chat_model() -> BaseChatModel:
    """The model graph nodes should use: the test override if set, else the configured gateway."""
    return _override if _override is not None else build_chat_model()


@contextmanager
def override_chat_model(model: BaseChatModel) -> Iterator[BaseChatModel]:
    """Temporarily route every node call to `model` (tests only; never used in production)."""
    global _override
    previous = _override
    _override = model
    try:
        yield model
    finally:
        _override = previous


# ---- invocation with honest failure ----------------------------------------------------


def _text_of(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            parts.append(part["text"])
    return "".join(parts).strip()


def _fail(started: float, exc: BaseException | None, reason: str) -> UpstreamModelError:
    # Log only the exception type and duration: never the key, prompt or response.
    logger.warning(
        "model call failed: %s (%s) after %.0f ms",
        reason,
        type(exc).__name__ if exc else "n/a",
        (time.monotonic() - started) * 1000,
    )
    return UpstreamModelError("The model call failed.")


def invoke_model(model: BaseChatModel, messages: Sequence[BaseMessage]) -> str:
    """One model call. Returns the text, or raises `UpstreamModelError` (no fabricated content)."""
    started = time.monotonic()
    try:
        response = model.invoke(list(messages))
    except Exception as exc:
        raise _fail(started, exc, "invoke error") from None
    text = _text_of(response)
    if not text:
        raise _fail(started, None, "empty response")
    return text


async def ainvoke_model(model: BaseChatModel, messages: Sequence[BaseMessage]) -> str:
    """Async twin of `invoke_model` (used by graph nodes so specialists can run in parallel)."""
    started = time.monotonic()
    try:
        response = await model.ainvoke(list(messages))
    except Exception as exc:
        raise _fail(started, exc, "invoke error") from None
    text = _text_of(response)
    if not text:
        raise _fail(started, None, "empty response")
    return text


# ---- fake model for tests --------------------------------------------------------------


class ScriptedChatModel(BaseChatModel):
    """Deterministic stand-in for the gateway.

    Returns `responses` in order (the last one repeats), raises on the zero-based call indexes in
    `fail_on_calls`, and records how many calls happened and the last human prompt of each.
    """

    responses: list[str] = Field(default_factory=lambda: ["ok"])
    fail_on_calls: list[int] = Field(default_factory=list)
    # Optional: choose the reply from the prompt instead of the call index (parallel-safe).
    responder: Callable[[list[BaseMessage]], str] | None = None
    _count: int = PrivateAttr(default=0)
    _prompts: list[str] = PrivateAttr(default_factory=list)

    @property
    def call_count(self) -> int:
        return self._count

    @property
    def prompts(self) -> list[str]:
        return list(self._prompts)

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        index = self._count
        self._count += 1
        self._prompts.append(_text_of(messages[-1]) if messages else "")
        if index in self.fail_on_calls:
            raise RuntimeError("simulated gateway failure")
        if self.responder is not None:
            text = self.responder(messages)
        else:
            text = self.responses[min(index, len(self.responses) - 1)]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, None, **kwargs)


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_RETRIES",
    "InvalidModelOutputError",
    "NotConfiguredError",
    "ScriptedChatModel",
    "UpstreamModelError",
    "ainvoke_model",
    "build_chat_model",
    "get_chat_model",
    "invoke_model",
    "override_chat_model",
]

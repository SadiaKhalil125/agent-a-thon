"""TASK-008: ChatOpenAI -> LiteLLM factory, fake model, honest failure (AT-ORCH-002/005)."""

from __future__ import annotations

import asyncio
import logging

import pytest
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

import config
from agents import llm

SECRET = "sk-test-secret-should-never-leak"
SETTINGS = config.LLMSettings(base_url="http://127.0.0.1:9/v1", api_key=SECRET, model="demo-model")


def _msgs(text: str = "hello") -> list[HumanMessage]:
    return [HumanMessage(content=text)]


# ---- factory ---------------------------------------------------------------------------


def test_factory_builds_chat_openai_with_one_retry_and_hides_the_key() -> None:
    model = llm.build_chat_model(SETTINGS, timeout=5)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "demo-model"
    assert model.openai_api_base == "http://127.0.0.1:9/v1"
    assert model.max_retries == 1
    assert model.request_timeout == 5
    assert SECRET not in repr(model) and SECRET not in str(model)


def test_factory_raises_not_configured_without_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LITELLM_BASE_URL",
        "LITELLM_API_KEY",
        "LITELLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(llm.NotConfiguredError):
        llm.build_chat_model()


def test_factory_reads_the_environment_including_legacy_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://gateway.example.com/v1")
    monkeypatch.setenv("LITELLM_API_KEY", SECRET)
    monkeypatch.setenv("LITELLM_MODEL", "legacy-model")
    model = llm.build_chat_model()
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "legacy-model"


# ---- real model call happens (AT-ORCH-002-01) ------------------------------------------


def test_invoke_returns_text_and_counts_exactly_one_call() -> None:
    fake = llm.ScriptedChatModel(responses=["The chain reaches the invoice."])
    text = llm.invoke_model(fake, _msgs("trace the impact"))
    assert text == "The chain reaches the invoice."
    assert fake.call_count == 1
    assert fake.prompts == ["trace the impact"]


def test_async_invoke_works_and_counts_calls() -> None:
    fake = llm.ScriptedChatModel(responses=["a", "b"])

    async def run() -> list[str]:
        return list(
            await asyncio.gather(
                llm.ainvoke_model(fake, _msgs("one")), llm.ainvoke_model(fake, _msgs("two"))
            )
        )

    results = asyncio.run(run())
    assert sorted(results) == ["a", "b"]
    assert fake.call_count == 2


def test_scripted_model_repeats_its_last_response() -> None:
    fake = llm.ScriptedChatModel(responses=["first", "last"])
    assert [llm.invoke_model(fake, _msgs()) for _ in range(3)] == ["first", "last", "last"]


# ---- honest failure (AT-ORCH-005-01) ---------------------------------------------------


def test_failure_raises_upstream_error_with_no_content_and_no_leak(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = llm.ScriptedChatModel(responses=["never returned"], fail_on_calls=[0])
    prompt = f"confidential prompt with {SECRET}"
    with caplog.at_level(logging.DEBUG), pytest.raises(llm.UpstreamModelError) as info:
        llm.invoke_model(fake, _msgs(prompt))
    assert str(info.value) == "The model call failed."
    assert "never returned" not in str(info.value)
    logged = caplog.text
    assert SECRET not in logged and "confidential prompt" not in logged
    assert "simulated gateway failure" not in logged  # message text may carry payload detail
    assert "RuntimeError" in logged  # the type is enough to diagnose


def test_empty_response_is_a_failure_not_an_answer() -> None:
    fake = llm.ScriptedChatModel(responses=["   "])
    with pytest.raises(llm.UpstreamModelError):
        llm.invoke_model(fake, _msgs())


def test_async_failure_raises_upstream_error() -> None:
    fake = llm.ScriptedChatModel(fail_on_calls=[0])
    with pytest.raises(llm.UpstreamModelError):
        asyncio.run(llm.ainvoke_model(fake, _msgs()))


def test_real_client_against_a_closed_port_fails_honestly_after_one_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The actual ChatOpenAI path (no fake): connection refused becomes UpstreamModelError."""
    model = llm.build_chat_model(SETTINGS, timeout=3)
    with caplog.at_level(logging.DEBUG), pytest.raises(llm.UpstreamModelError):
        llm.invoke_model(model, _msgs("x"))
    assert SECRET not in caplog.text


# ---- injection -------------------------------------------------------------------------


def test_override_routes_get_chat_model_and_restores_afterwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = llm.ScriptedChatModel()
    with llm.override_chat_model(fake):
        assert llm.get_chat_model() is fake
    # No override and no environment: it must not silently fall back to a fake.
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for name in ("LITELLM_BASE_URL", "LITELLM_API_KEY", "LITELLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(llm.NotConfiguredError):
        llm.get_chat_model()

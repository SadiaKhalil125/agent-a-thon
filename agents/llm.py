"""ChatOpenAI -> LiteLLM gateway factory (server-side only).

Filled in TASK-008. Builds `ChatOpenAI(base_url, api_key, model)` from
`config.get_llm_settings()` (provider-neutral; the endpoint/model/key come from
the environment) with timeout + one bounded retry + structured error; never logs
the key or payloads. The only place the chat model is constructed. A fake chat
model lives beside it for tests (no paid calls in CI).
"""

from __future__ import annotations

__all__: list[str] = []

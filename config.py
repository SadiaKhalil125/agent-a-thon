"""Resolve the LLM provider configuration from the environment.

Provider-neutral: the app targets any OpenAI-compatible gateway. The actual
endpoint, model and key come only from the environment — `.env.local` locally
(gitignored), project environment variables when deployed — so the provider is
a matter of configuration, never code or repository content.

Primary variables are `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. The legacy
`LITELLM_*` names are accepted as a fallback, so switching provider is only a
change of values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_BASE_URL_VARS = ("LLM_BASE_URL", "LITELLM_BASE_URL")
_API_KEY_VARS = ("LLM_API_KEY", "LITELLM_API_KEY")
_MODEL_VARS = ("LLM_MODEL", "LITELLM_MODEL")


def _first(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    api_key: str
    model: str


def llm_configured() -> bool:
    """True when base URL, API key and model are all resolvable."""
    return all(_first(group) for group in (_BASE_URL_VARS, _API_KEY_VARS, _MODEL_VARS))


def get_llm_settings() -> LLMSettings:
    """Resolve settings or raise if the provider is not configured.

    Never log or echo the returned api_key.
    """
    base_url = _first(_BASE_URL_VARS)
    api_key = _first(_API_KEY_VARS)
    model = _first(_MODEL_VARS)
    if not (base_url and api_key and model):
        raise RuntimeError(
            "LLM provider is not configured. Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL."
        )
    return LLMSettings(base_url=base_url, api_key=api_key, model=model)

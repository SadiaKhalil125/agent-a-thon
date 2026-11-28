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


DEFAULT_MAX_CALLS_PER_RUN = 8  # impact, hr, finance, planner, verifier, revised planner + headroom


def max_calls_per_run() -> int:
    """Model-call budget for one run (`MAX_CALLS_PER_RUN`, default 8; invalid values fall back)."""
    raw = os.environ.get("MAX_CALLS_PER_RUN")
    if raw is None:
        return DEFAULT_MAX_CALLS_PER_RUN
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_CALLS_PER_RUN
    return value if 0 <= value <= 50 else DEFAULT_MAX_CALLS_PER_RUN


DEFAULT_CHAT_MAX_CALLS = 14  # orchestrator + up to 3 specialists x 4 rounds + synthesizer
DEFAULT_CHAT_MAX_TOOL_CALLS = 24


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if low <= value <= high else default


def chat_max_calls() -> int:
    """Model-call budget for one "Ask the company" question (`CHAT_MAX_CALLS`, 2 to 40)."""
    return _bounded_int("CHAT_MAX_CALLS", DEFAULT_CHAT_MAX_CALLS, 2, 40)


def chat_max_tool_calls() -> int:
    """Data-tool-call budget for one question (`CHAT_MAX_TOOL_CALLS`, 1 to 60)."""
    return _bounded_int("CHAT_MAX_TOOL_CALLS", DEFAULT_CHAT_MAX_TOOL_CALLS, 1, 60)


DEFAULT_RUN_TIMEOUT_SECONDS = 240.0  # under Vercel's ~5-minute ceiling (NFR-PERF-001)


def run_timeout_seconds() -> float:
    """Overall wall-clock limit for one streamed run (`RUN_TIMEOUT_SECONDS`, 1 to 290)."""
    raw = os.environ.get("RUN_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_RUN_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_RUN_TIMEOUT_SECONDS
    return value if 1.0 <= value <= 290.0 else DEFAULT_RUN_TIMEOUT_SECONDS


def demo_passcode() -> str | None:
    """Optional gate for the costly endpoints (`DEMO_PASSCODE`); unset or blank means open."""
    value = os.environ.get("DEMO_PASSCODE", "").strip()
    return value or None


DEMO_WEBHOOK_SECRET = "northstar-simulated-webhook-demo"  # not a credential: it signs fake events


def webhook_secret() -> bytes:
    """Key for the simulated webhook signatures (`WEBHOOK_DEMO_SECRET` overrides the demo key).

    The server both signs the sample events (playing the sending system) and verifies the inbox,
    so this protects nothing real; it shows what a real HMAC check does.
    """
    value = os.environ.get("WEBHOOK_DEMO_SECRET", "").strip()
    return (value or DEMO_WEBHOOK_SECRET).encode()


def dev_console_enabled() -> bool:
    """The `/dev` test console: on locally, off on Vercel unless `DEV_CONSOLE=1`."""
    flag = os.environ.get("DEV_CONSOLE", "").strip()
    if flag:
        return flag == "1"
    return not os.environ.get("VERCEL")


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

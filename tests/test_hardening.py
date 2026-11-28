"""TASK-019/020/021: budget cap, honest failure, deterministic stateless re-run, security.

Covers AT-OPS-001, AT-PERF-001, AT-REL-001, AT-EVENT-002, AT-ORCH-005, AT-SEC-001/002 and
AT-SEC-sec2 (malformed requests are rejected safely).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

import config
from agents import llm
from api.security import MAX_BODY_BYTES
from app import app
from orchestration.graph import get_graph
from orchestration.runner import prepare_run, stream_run
from twin import solver
from twin.seed import get_twin

client = TestClient(app, raise_server_exceptions=False)
ROOT = Path(__file__).resolve().parent.parent
PRESET = "dev-out-1-5"
Event = tuple[str, dict[str, Any]]

ENV_NAMES = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LITELLM_BASE_URL",
    "LITELLM_API_KEY",
    "LITELLM_MODEL",
    "DEMO_PASSCODE",
    "MAX_CALLS_PER_RUN",
    "RUN_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def fake() -> llm.ScriptedChatModel:
    def respond(messages: list[BaseMessage]) -> str:
        if "You are the Planner" in str(messages[0].content):
            return json.dumps({"recommendedPlanId": "plan-contractor", "rationale": "Best fit."})
        return "A short, grounded explanation."

    return llm.ScriptedChatModel(responder=respond)


class SlowModel(llm.ScriptedChatModel):
    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        await asyncio.sleep(5)
        return self._generate(messages, stop, None, **kwargs)


def run_events(model: llm.ScriptedChatModel, **kwargs: Any) -> list[Event]:
    prepared = prepare_run(PRESET, model=model, **kwargs)

    async def collect() -> list[Event]:
        return [item async for item in stream_run(prepared)]

    return asyncio.run(collect())


def names(events: list[Event]) -> list[str]:
    return [name for name, _ in events]


def post_run() -> Any:
    return client.post("/api/run/stream", json={"presetId": PRESET})


# ---- budget cap (TASK-019, AT-OPS-001-01) ----------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 8), ("3", 3), ("0", 0), ("50", 50), ("-1", 8), ("51", 8), ("abc", 8), ("", 8)],
)
def test_call_budget_is_read_from_the_environment_safely(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: int
) -> None:
    if raw is not None:
        monkeypatch.setenv("MAX_CALLS_PER_RUN", raw)
    assert config.max_calls_per_run() == expected


def test_a_run_never_exceeds_the_configured_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_CALLS_PER_RUN", "2")
    model = fake()
    with llm.override_chat_model(model):
        text = post_run().text
    assert model.call_count == 2
    assert '"code":"BudgetExceeded"' in text and "event: done" not in text


def test_the_default_budget_fits_a_full_run_with_a_revision() -> None:
    model = fake()
    events = run_events(model)
    assert names(events)[-1] == "done"
    assert model.call_count == 7 <= config.DEFAULT_MAX_CALLS_PER_RUN


# ---- optional passcode (TASK-019) ------------------------------------------------------


def test_run_is_open_when_no_passcode_is_configured() -> None:
    assert client.get("/api/health").json()["passcodeRequired"] is False
    with llm.override_chat_model(fake()):
        assert post_run().status_code == 200


def test_run_requires_the_passcode_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSCODE", "open-sesame-demo")
    model = fake()
    with llm.override_chat_model(model):
        assert client.get("/api/health").json()["passcodeRequired"] is True
        for headers in ({}, {"X-Demo-Passcode": "wrong"}, {"X-Demo-Passcode": ""}):
            response = client.post("/api/run/stream", json={"presetId": PRESET}, headers=headers)
            assert response.status_code == 401
            assert response.json() == {
                "error": "A valid passcode is required.",
                "code": "Unauthorized",
            }
            assert "open-sesame" not in response.text
        assert model.call_count == 0  # refused before any model spend
        ok = client.post(
            "/api/run/stream",
            json={"presetId": PRESET},
            headers={"X-Demo-Passcode": "open-sesame-demo"},
        )
        assert ok.status_code == 200 and "event: done" in ok.text


def test_passcode_protects_only_the_costly_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSCODE", "open-sesame-demo")
    assert client.get("/api/state").status_code == 200
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401
    assert (
        client.post(
            "/api/execute", json={"presetId": PRESET, "approvedPlanId": "plan-wait"}
        ).status_code
        == 200
    )


# ---- honest failure, timeout, statelessness (TASK-020) ---------------------------------


def test_not_configured_is_visible_and_refuses_politely() -> None:
    assert client.get("/api/health").json() == {
        "ok": True,
        "llm_configured": False,
        "passcodeRequired": False,
    }
    response = post_run()
    assert response.status_code == 503 and response.json()["code"] == "NotConfigured"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 240.0), ("30", 30.0), ("0.5", 240.0), ("999", 240.0), ("abc", 240.0)],
)
def test_run_timeout_is_read_from_the_environment_safely(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: float
) -> None:
    if raw is not None:
        monkeypatch.setenv("RUN_TIMEOUT_SECONDS", raw)
    assert config.run_timeout_seconds() == expected


def test_a_run_that_takes_too_long_is_stopped_honestly() -> None:
    events = run_events(SlowModel(), timeout=0.3)
    assert names(events) == ["run_started", "node_started", "budget", "failed"]
    assert events[-1][1] == {
        "node": "run",
        "message": "The run took too long and was stopped.",
        "code": "Timeout",
    }


def test_the_full_scenario_finishes_well_inside_the_request_limit() -> None:
    import time

    started = time.monotonic()
    assert names(run_events(fake()))[-1] == "done"
    assert time.monotonic() - started < config.DEFAULT_RUN_TIMEOUT_SECONDS


def test_a_run_survives_independent_stateless_invocations() -> None:
    """AT-REL-001-01: drop every in-process cache between runs; the result is identical."""

    def normal(events: list[Event]) -> Any:
        body = [e for e in events if e[0] not in {"run_started", "budget", "node_started"}]
        done = body[-1]
        nodes = sorted(
            (e for e in body if e[0] == "node_completed"),
            key=lambda e: (e[1]["node"], e[1]["status"]),
        )
        return nodes, done

    first = normal(run_events(fake()))
    get_graph.cache_clear()
    get_twin.cache_clear()
    second = normal(run_events(fake()))
    assert first == second


def test_execute_after_a_cold_start_needs_no_prior_run() -> None:
    get_twin.cache_clear()
    response = client.post(
        "/api/execute", json={"presetId": PRESET, "approvedPlanId": "plan-contractor"}
    )
    assert response.status_code == 200


def test_internal_errors_are_generic_and_leak_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("secret-internal-detail /srv/app/path")

    monkeypatch.setattr(solver, "apply_plan", boom)
    response = client.post(
        "/api/execute", json={"presetId": PRESET, "approvedPlanId": "plan-contractor"}
    )
    assert response.status_code == 500
    assert response.json() == {
        "error": "Something went wrong. Please try again.",
        "code": "InternalError",
    }
    assert "secret-internal-detail" not in response.text and "Traceback" not in response.text


# ---- input validation negatives (TASK-021, AT-SEC-sec2) --------------------------------

CANARY = "CANARY-input-must-never-be-echoed"


@pytest.mark.parametrize(
    ("path", "kwargs"),
    [
        ("/api/run/stream", {"content": b"{not json " + CANARY.encode()}),
        ("/api/run/stream", {"json": [CANARY]}),
        ("/api/run/stream", {"json": {"presetId": {"nested": CANARY}}}),
        ("/api/run/stream", {"json": {"presetId": 12345}}),
        ("/api/run/stream", {"json": {"presetId": CANARY + "/../../etc/passwd"}}),
        ("/api/run/stream", {"json": {"presetId": "x" * 10_000}}),
        ("/api/run/stream", {"json": {"presetId": "a\u0000b"}}),
        ("/api/run/stream", {"content": CANARY, "headers": {"Content-Type": "text/plain"}}),
        ("/api/execute", {"json": {"presetId": PRESET, "approvedPlanId": CANARY + " x"}}),
        ("/api/execute", {"json": {"presetId": PRESET, "approvedPlanId": ["plan-wait"]}}),
        (
            "/api/outcome",
            {"json": {"presetId": PRESET, "approvedPlanId": "plan-wait", "twin": CANARY}},
        ),
        ("/api/chat", {"json": {"message": CANARY * 100}}),
    ],
)
def test_malformed_requests_are_rejected_safely(path: str, kwargs: dict[str, Any]) -> None:
    model = fake()
    with llm.override_chat_model(model):
        response = client.post(path, **kwargs)
    assert response.status_code == 400, (path, response.status_code)
    assert response.json()["code"] == "ValidationError"
    assert CANARY not in response.text and "Traceback" not in response.text
    assert model.call_count == 0


def test_wrong_methods_are_refused() -> None:
    for path in ("/api/run/stream", "/api/execute", "/api/outcome", "/api/reset"):
        assert client.get(path).status_code == 405, path
    assert client.post("/api/state").status_code == 405


def test_an_oversized_body_is_refused_before_it_is_read() -> None:
    big = b'{"presetId": "' + b"a" * (MAX_BODY_BYTES + 10) + b'"}'
    response = client.post(
        "/api/run/stream", content=big, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json() == {"error": "The request is too large.", "code": "ValidationError"}
    assert response.headers["x-content-type-options"] == "nosniff"


def test_an_outcome_twin_with_too_many_segments_is_refused() -> None:
    twin = client.post(
        "/api/execute", json={"presetId": PRESET, "approvedPlanId": "plan-contractor"}
    ).json()["twin"]
    twin["schedule"] = twin["schedule"] * 40
    response = client.post(
        "/api/outcome", json={"presetId": PRESET, "approvedPlanId": "plan-contractor", "twin": twin}
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/mock/tracker/issues/..%2F..%2Fapp.py",
        "/mock/crm/accounts/%2e%2e%2fapp.py",
        "/mock/crm/accounts/%00",
        "/static/../app.py",
        "/static/%2e%2e/app.py",
        "/static/..%2fapp.py",
    ],
)
def test_path_traversal_never_reaches_files(path: str) -> None:
    response = client.get(path)
    assert response.status_code in {400, 404}
    assert "FastAPI(" not in response.text and "import " not in response.text


def test_responses_carry_conservative_security_headers() -> None:
    with llm.override_chat_model(fake()):
        responses = [client.get("/api/state"), client.get("/nope"), post_run()]
    for response in responses:
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"


# ---- no key leakage (AT-SEC-001-01) ----------------------------------------------------

KEY = "sk-canary-0123456789abcdefghijklmnop"  # fake; never a real credential


def test_the_key_never_appears_in_any_response_or_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")  # closed port: a real failure path
    monkeypatch.setenv("LLM_MODEL", "demo-model")
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "30")
    seen: list[str] = []
    with caplog.at_level(logging.DEBUG):
        for response in (
            client.get("/api/health"),
            client.get("/api/state"),
            client.get("/api/integrations"),
            client.get("/mock/hris/employees"),
            client.get("/openapi.json"),
            client.get("/"),
            post_run(),  # reaches the real client, fails honestly
            client.post("/api/execute", json={"presetId": PRESET, "approvedPlanId": "plan-backup"}),
            client.post("/api/run/stream", json={"presetId": KEY}),
        ):
            seen.append(response.text + str(dict(response.headers)))
    blob = "\n".join(seen)
    assert KEY not in blob and KEY not in caplog.text
    assert "event: failed" in seen[6] and "UpstreamModelError" in seen[6]  # it did fail honestly
    assert client.get("/api/health").json()["llm_configured"] is True


# ---- repository scans: no key, no real data (AT-SEC-001-01, AT-SEC-002-01) -------------

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cursor",
}


def _repo_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        candidates = [ROOT / name for name in out]
    except (OSError, subprocess.CalledProcessError):
        candidates = [
            p
            for p in ROOT.rglob("*")
            if p.is_file() and not SKIP_DIRS & set(p.relative_to(ROOT).parts)
        ]
    files = []
    for path in candidates:
        if path.is_file() and path.name != ".env.local" and path.stat().st_size < 2_000_000:
            files.append(path)
    return files


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def test_the_repo_contains_no_api_key_shaped_secret() -> None:
    pattern = re.compile(r"sk-(?!test-|canary-)[A-Za-z0-9]{20,}")
    hits = [
        str(p.relative_to(ROOT)) for p in _repo_files() if (t := _text(p)) and pattern.search(t)
    ]
    assert hits == []


def test_the_configured_key_value_appears_in_no_other_file() -> None:
    env = ROOT / ".env.local"
    if not env.exists():
        pytest.skip("no local .env.local to compare against")
    secrets = [v for k, v in dotenv_values(env).items() if v and len(v) >= 8 and "KEY" in k.upper()]
    for path in _repo_files():
        text = _text(path)
        if text:
            for secret in secrets:
                assert secret not in text, str(path.relative_to(ROOT))


def test_env_local_is_git_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env*.local" in ignore or ".env.local" in ignore
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", ".env.local"], cwd=ROOT, capture_output=True, check=False
        )
    except OSError:
        return
    assert result.returncode == 0


def test_the_browser_bundle_holds_no_provider_secrets_or_urls() -> None:
    forbidden = re.compile(
        r"LLM_API_KEY|LITELLM|api\.deepseek|api\.openai|Bearer\s|sk-[A-Za-z0-9]{10,}"
    )
    for folder in ("static", "templates"):
        for path in (ROOT / folder).rglob("*"):
            text = _text(path) if path.is_file() else None
            if text:
                assert not forbidden.search(text), str(path.relative_to(ROOT))


def test_only_fabricated_email_domains_exist_in_data_and_docs() -> None:
    allowed = {"example.com", "example.org", "example.net"}
    email = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
    offenders: dict[str, set[str]] = {}
    for path in _repo_files():
        rel = path.relative_to(ROOT)
        if rel.parts[0] not in {"data", "docs", "integrations", "static", "templates", "tests"}:
            continue
        for domain in email.findall(_text(path) or ""):
            if domain.lower() not in allowed:
                offenders.setdefault(str(rel), set()).add(domain)
    assert offenders == {}

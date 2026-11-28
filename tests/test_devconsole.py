"""The /dev test console is a local tool: served locally, hidden on Vercel, holds no secret."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import config
from app import app

client = TestClient(app)


def test_console_is_served_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("DEV_CONSOLE", raising=False)
    res = client.get("/dev")
    assert res.status_code == 200
    assert "CompanyTwin engine test console" in res.text


def test_console_is_hidden_on_vercel_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DEV_CONSOLE", raising=False)
    res = client.get("/dev")
    assert res.status_code == 404
    assert res.json()["code"] == "ValidationError"


def test_console_can_be_forced_on_or_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DEV_CONSOLE", "1")
    assert config.dev_console_enabled() is True
    monkeypatch.delenv("VERCEL")
    monkeypatch.setenv("DEV_CONSOLE", "0")
    assert config.dev_console_enabled() is False
    assert client.get("/dev").status_code == 404


def test_home_page_is_the_console_even_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Temporary: `/` serves the console so it opens on Vercel (where /dev is hidden)."""
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DEV_CONSOLE", raising=False)
    res = client.get("/")
    assert res.status_code == 200
    assert "CompanyTwin engine test console" in res.text
    assert "sk-" not in res.text


def test_console_page_holds_no_secret_and_only_calls_this_server() -> None:
    html = client.get("/dev").text
    assert "sk-" not in html
    assert "http://" not in html.replace("http://www.w3.org", "")
    assert "https://" not in html

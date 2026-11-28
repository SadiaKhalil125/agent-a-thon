"""/api/data/*: read-only company data over the same repository functions the agents use."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app
from datahub import registry

client = TestClient(app)


def test_tools_listing_covers_every_registered_tool() -> None:
    body = client.get("/api/data/tools").json()
    assert len(body["tools"]) == len(registry.TOOLS) == 22
    assert {t["area"] for t in body["tools"]} == set(registry.AREAS)


def test_meetings_tomorrow_endpoint() -> None:
    r = client.get(
        "/api/data/crm/list_meetings",
        params={"date_from": "2026-12-02", "date_to": "2026-12-02", "status": "scheduled"},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 5


def test_string_arguments_are_coerced_to_their_types() -> None:
    r = client.get("/api/data/engineering/workload", params={"overloaded_only": "true"})
    assert r.status_code == 200 and r.json()["total"] >= 5
    r = client.get("/api/data/engineering/search_tickets", params={"overdue": "true", "limit": "3"})
    assert len(r.json()["rows"]) == 3


@pytest.mark.parametrize(
    "path,params",
    [
        ("/api/data/crm/count_leads", {"group_by": "stage; DROP TABLE leads"}),
        ("/api/data/crm/count_leads", {"nonsense": "1"}),
        ("/api/data/finance/invoices", {"status": "paid' OR '1'='1"}),
        ("/api/data/engineering/search_tickets", {"limit": "abc"}),
        ("/api/data/hr/find_employees", {"name": "x" * 500}),
        ("/api/data/engineering/project_detail", {}),
    ],
)
def test_bad_arguments_are_400_with_no_detail(path: str, params: dict[str, str]) -> None:
    r = client.get(path, params=params)
    assert r.status_code == 400
    assert r.json()["code"] == "ValidationError"
    assert "DROP" not in r.text and "Traceback" not in r.text


def test_unknown_endpoint_is_404() -> None:
    assert client.get("/api/data/crm/nope").status_code == 404
    assert client.get("/api/data/nope/count_leads").status_code == 404


def test_schema_endpoint() -> None:
    body = client.get("/api/data/schema", params={"table": "leads"}).json()
    assert "CREATE TABLE leads" in body["schema"] and len(body["tables"]) == 29


def test_writes_are_not_allowed() -> None:
    assert client.post("/api/data/crm/count_leads").status_code == 405
    assert client.delete("/api/data/crm/count_leads").status_code == 405


def test_passcode_is_enforced_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSCODE", "letmein")
    assert client.get("/api/data/crm/count_leads").status_code == 401
    ok = client.get("/api/data/crm/count_leads", headers={"X-Demo-Passcode": "letmein"})
    assert ok.status_code == 200

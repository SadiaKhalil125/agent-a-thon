"""TASK-024: simulated connectors core (AT-INT-001, AT-INT-006, AT-INT-sec-01)."""

from __future__ import annotations

import ast
import json
import re
import socket
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import app
from integrations.registry import build_registry
from twin.seed import get_twin

client = TestClient(app, raise_server_exceptions=False)
ROOT = Path(__file__).resolve().parent.parent

READ_URLS = [
    "/api/integrations",
    "/api/integrations/hris/sample",
    "/api/integrations/tracker/sample",
    "/api/integrations/erp/sample",
    "/api/integrations/crm/sample",
    "/api/integrations/calendar/sample",
    "/mock/hris/employees",
    "/mock/hris/leave-requests",
    "/mock/tracker/issues",
    "/mock/tracker/issues/NS-142",
    "/mock/tracker/sprints/current",
    "/mock/erp/invoices",
    "/mock/erp/budgets/recovery",
    "/mock/erp/purchase-orders",
    "/mock/crm/accounts/ACC-1001",
    "/mock/crm/commitments",
    "/mock/calendar/freebusy?person=PER-BACKUP",
    "/mock/calendar/events",
]


def get(url: str) -> Any:
    response = client.get(url)
    assert response.status_code == 200, (url, response.text)
    return response.json()


# ---- manifests (AT-INT-001-01, AT-INT-006-01) ------------------------------------------


def test_manifest_lists_the_five_tier_one_systems_as_simulated() -> None:
    manifests = get("/api/integrations")
    assert [m["id"] for m in manifests] == ["hris", "tracker", "erp", "crm", "calendar"]
    for manifest in manifests:
        assert manifest["mode"] == "simulated"
        assert manifest["status"] == "connected"
        assert manifest["tier"] == 1
        assert manifest["capabilities"] == ["read"]
        assert manifest["auth"]["mode"] in {"oauth2", "api_key", "webhook_hmac"}
        assert manifest["auth"]["scopes"] and manifest["auth"]["rateLimit"]
        assert manifest["recordCount"] > 0
        assert manifest["lastSync"]
        assert all(e["path"].startswith("/mock/") for e in manifest["endpoints"])


def test_every_declared_endpoint_is_served() -> None:
    def norm(path: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", path)

    declared = {norm(e["path"]) for m in get("/api/integrations") for e in m["endpoints"]}
    served = {norm(p) for p in app.openapi()["paths"] if p.startswith("/mock")}
    assert declared == served


def test_every_response_is_labelled_simulated() -> None:
    for url in READ_URLS:
        assert client.get(url).headers["x-simulated"] == "true", url


def test_mock_endpoints_are_tagged_in_openapi() -> None:
    paths = app.openapi()["paths"]
    assert paths["/mock/hris/employees"]["get"]["tags"] == ["Simulated connectors"]
    assert paths["/api/integrations"]["get"]["tags"] == ["Simulated connectors"]


def test_each_connector_has_a_sample_and_unknown_ids_are_rejected() -> None:
    for connector_id in build_registry(get_twin()):
        assert get(f"/api/integrations/{connector_id}/sample")
    response = client.get("/api/integrations/payroll/sample")
    assert response.status_code == 404
    assert response.json() == {"error": "Unknown integration.", "code": "ValidationError"}


# ---- native-looking data, grounded in the seed -----------------------------------------


def test_hris_matches_the_seed_people_and_the_leave_event() -> None:
    employees = {e["employeeId"]: e for e in get("/mock/hris/employees")}
    assert employees["HR-1001"]["displayName"] == "Dana Reyes"
    assert employees["HR-1001"]["employmentType"] == "FTE"
    assert employees["HR-1004"]["employmentType"] == "CONTRACTOR"
    (leave,) = get("/mock/hris/leave-requests")
    assert (leave["employeeId"], leave["startDay"], leave["endDay"]) == ("HR-1001", 1, 5)
    window = get_twin().preset("dev-out-1-5").event.unavailable[0]
    assert (window.startDay, window.endDay) == (leave["startDay"], leave["endDay"])


def test_tracker_issues_carry_dependencies_and_assignees() -> None:
    issue = get("/mock/tracker/issues/NS-142")
    assert issue["summary"] == "Payment gateway integration"
    assert issue["assignee"] == {"accountId": "HR-1001", "displayName": "Dana Reyes"}
    assert issue["estimateDays"] == 4
    assert get("/mock/tracker/issues/NS-143")["dependsOn"] == ["NS-142"]
    assert get("/mock/tracker/issues/T-A-INT")["key"] == "NS-142"  # seed ids resolve too
    sprint = get("/mock/tracker/sprints/current")
    assert sprint["issues"] == ["NS-142", "NS-143", "NS-150"]
    assert sprint["endDay"] == 6


def test_erp_exposes_invoice_budget_and_contractor_po() -> None:
    (invoice,) = get("/mock/erp/invoices")
    assert (invoice["invoiceNumber"], invoice["amount"], invoice["currency"]) == (
        "ERP-INV-90001",
        8000,
        "USD",
    )
    assert invoice["milestone"]["dueDay"] == 6
    assert get("/mock/erp/budgets/recovery")["amount"] == 2000
    (po,) = get("/mock/erp/purchase-orders")
    assert po["amount"] == 1500 and po["status"] == "not_issued"


def test_crm_account_lists_its_commitments() -> None:
    account = get("/mock/crm/accounts/ACC-1001")
    assert account["name"].startswith("Orbit Retail")
    assert [c["commitmentId"] for c in account["commitments"]] == ["COM-5001"]
    assert [c["dueDay"] for c in get("/mock/crm/commitments")] == [6, 4]


def test_calendar_freebusy_shows_bookings_and_optionally_the_disruption() -> None:
    marcus = get("/mock/calendar/freebusy?person=PER-BACKUP")
    assert marcus["busy"] == [{"startDay": 2, "endDay": 3, "reason": "Booked: Billing hotfix"}]
    assert get("/mock/calendar/freebusy?person=HR-1002") == marcus  # hris id resolves too
    dana = get("/mock/calendar/freebusy?person=PER-DEV1&preset=dev-out-1-5")
    assert dana["busy"] == [{"startDay": 1, "endDay": 5, "reason": "Out of office"}]
    events = get("/mock/calendar/events")
    assert {e["kind"] for e in events} == {"out_of_office", "booking"}


def test_unknown_records_and_bad_parameters_are_clean_errors() -> None:
    for url in (
        "/mock/tracker/issues/NS-999",
        "/mock/crm/accounts/NOPE",
        "/mock/calendar/freebusy?person=PER-NOPE",
        "/mock/calendar/freebusy?person=PER-DEV1&preset=nope",
    ):
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.json() == {"error": "Record not found.", "code": "ValidationError"}
    bad = client.get("/mock/calendar/freebusy?person=a%20b")
    assert bad.status_code == 400 and bad.json()["code"] == "ValidationError"
    assert client.get("/mock/calendar/freebusy").status_code == 400


def test_responses_are_deterministic() -> None:
    for url in READ_URLS:
        assert client.get(url).text == client.get(url).text, url


def test_only_fabricated_example_addresses_appear() -> None:
    blob = " ".join(client.get(url).text for url in READ_URLS)
    domains = set(re.findall(r"@([A-Za-z0-9.-]+)", blob))
    assert domains == {"example.com"}


# ---- no outbound network (AT-INT-sec-01) -----------------------------------------------

BANNED_PREFIXES = (
    "httpx",
    "requests",
    "urllib",
    "http.client",
    "socket",
    "aiohttp",
    "openai",
    "langchain",
    "langgraph",
    "agents",
    "orchestration",
)


def test_integrations_import_no_network_or_model_code() -> None:
    for path in (ROOT / "integrations").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            for module in modules:
                assert not module.startswith(BANNED_PREFIXES), (path.name, module)


def test_serving_every_endpoint_opens_no_socket_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("outbound network connection attempted")

    # (socket.connect cannot be patched: Windows asyncio uses it for its own socketpair.)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    for url in READ_URLS:
        assert client.get(url).status_code == 200, url


def test_nothing_secret_or_real_in_connector_payloads() -> None:
    blob = " ".join(client.get(url).text for url in READ_URLS)
    assert "sk-" not in blob
    assert json.loads(client.get("/api/integrations").text)  # still valid JSON

"""A3: GET /api/state matches docs/contracts.md and exposes no secrets."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import ApiError, register_error_handlers
from app import app

client = TestClient(app, raise_server_exceptions=False)

CONTRACT_KEYS = {
    "company",
    "projects",
    "tasks",
    "people",
    "milestones",
    "commitments",
    "invoices",
    "budget",
    "contractor",
    "chain",
    "presets",
}


def test_state_has_every_contract_key() -> None:
    response = client.get("/api/state")
    assert response.status_code == 200
    assert CONTRACT_KEYS <= set(response.json())


def test_state_entities_match_the_seed_scenario() -> None:
    data = client.get("/api/state").json()
    assert data["company"]["name"] == "Northstar Systems"
    assert {t["id"] for t in data["tasks"]} >= {"T-A-INT", "T-A-QA", "T-B-FIX"}
    task = next(t for t in data["tasks"] if t["id"] == "T-A-QA")
    assert set(task) >= {"id", "projectId", "type", "days", "dependsOn"}
    assert task["dependsOn"] == ["T-A-INT"]
    backup = next(p for p in data["people"] if p["id"] == "PER-BACKUP")
    assert backup["assignments"] == [{"taskId": "T-B-FIX", "startDay": 2, "endDay": 3}]
    assert set(backup) >= {"id", "name", "skills", "availability", "assignments"}
    assert data["budget"]["recoveryBudget"] == 2000
    assert data["contractor"]["fixedCost"] == 1500
    assert data["invoices"][0]["amount"] == 8000


def test_state_chain_is_the_primary_impact_chain() -> None:
    chain = client.get("/api/state").json()["chain"]
    assert [(n["type"], n["id"]) for n in chain] == [
        ("task", "T-A-INT"),
        ("task", "T-A-QA"),
        ("milestone", "M-A"),
        ("commitment", "CM-1"),
        ("invoice", "INV-1"),
    ]
    assert all(set(n) == {"id", "type", "label"} for n in chain)


def test_state_has_presets_from_two_or_more_systems() -> None:
    presets = client.get("/api/state").json()["presets"]
    assert len(presets) >= 4
    assert len({p["source"]["system"] for p in presets}) >= 2
    for preset in presets:
        assert set(preset) >= {"id", "label", "description", "source"}
        # Every scenario is either someone being out or new client work (or both).
        assert preset["event"]["unavailable"] or preset["event"]["demand"]


def test_the_client_meeting_preset_exposes_the_request_but_not_the_company_change() -> None:
    body = client.get("/api/state").json()
    meeting = next(p for p in body["presets"] if p["id"] == "client-meeting-loyalty")
    assert meeting["source"]["system"] == "crm"
    assert meeting["event"]["unavailable"] == []
    demand = meeting["event"]["demand"]
    assert demand["taskName"] == "Loyalty API add-on"
    assert (demand["days"], demand["dueDay"], demand["invoiceAmount"]) == (5, 8, 6000)
    # The new work only exists inside that scenario: the base company is unchanged.
    assert "T-C-LOY" not in {t["id"] for t in body["tasks"]}
    assert all(p["event"]["demand"] is None for p in body["presets"] if p is not meeting)


def test_state_is_read_only_and_identical_across_calls() -> None:
    assert client.get("/api/state").json() == client.get("/api/state").json()
    assert client.post("/api/state").status_code == 405


def test_error_handlers_return_the_safe_shape_without_echoing_input() -> None:
    probe = FastAPI()
    register_error_handlers(probe)

    @probe.get("/typed")
    def typed(n: int) -> dict[str, int]:
        return {"n": n}

    @probe.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    @probe.get("/gate")
    def gate() -> None:
        raise ApiError(403, "ValidationError", "Plan not approved.")

    probe_client = TestClient(probe, raise_server_exceptions=False)
    bad = probe_client.get("/typed", params={"n": "abc-SECRET"})
    assert bad.status_code == 400
    assert bad.json() == {"error": "The request was not valid.", "code": "ValidationError"}
    assert "SECRET" not in bad.text
    crash = probe_client.get("/boom")
    assert crash.status_code == 500
    assert crash.json()["code"] == "InternalError"
    assert "secret internal detail" not in crash.text
    gated = probe_client.get("/gate")
    assert gated.status_code == 403 and gated.json() == {
        "error": "Plan not approved.",
        "code": "ValidationError",
    }


def test_state_never_contains_secrets() -> None:
    body = client.get("/api/state").text.lower()
    for needle in ("api_key", "sk-", "llm_api_key", "bearer"):
        assert needle not in body

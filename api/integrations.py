"""Simulated connector endpoints: `/api/integrations` and the dummy `/mock/*` systems (TASK-024).

All data is fabricated and read from the seed in-process; every response carries
`X-Simulated: true` and every manifest says `mode: "simulated"` (FR-INT-006).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from api.errors import ApiError
from integrations.base import RecordNotFoundError
from integrations.calendar import CalendarConnector
from integrations.crm import CrmConnector
from integrations.erp import ErpConnector
from integrations.hris import HrisConnector
from integrations.manifest import Manifest
from integrations.registry import build_registry, list_manifests
from integrations.tracker import TrackerConnector
from twin.seed import get_twin

TAG = "Simulated connectors"


def _mark_simulated(response: Response) -> None:
    response.headers["X-Simulated"] = "true"


router = APIRouter(tags=[TAG], dependencies=[Depends(_mark_simulated)])

_Ref = Annotated[str, Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.@-]+$")]


def _not_found(_: RecordNotFoundError) -> ApiError:
    return ApiError(404, "ValidationError", "Record not found.")


@router.get("/api/integrations", response_model=list[Manifest])
def integrations() -> list[Manifest]:
    return list_manifests(get_twin())


@router.get("/api/integrations/{integration_id}/sample")
def integration_sample(integration_id: str) -> dict[str, Any]:
    connector = build_registry(get_twin()).get(integration_id)
    if connector is None:
        raise ApiError(404, "ValidationError", "Unknown integration.")
    return connector.sample()


# ---- hris ------------------------------------------------------------------------------


@router.get("/mock/hris/employees")
def hris_employees() -> list[dict[str, Any]]:
    return HrisConnector(get_twin()).employees()


@router.get("/mock/hris/leave-requests")
def hris_leave_requests() -> list[dict[str, Any]]:
    return HrisConnector(get_twin()).leave_requests()


# ---- tracker ---------------------------------------------------------------------------


@router.get("/mock/tracker/issues")
def tracker_issues() -> list[dict[str, Any]]:
    return TrackerConnector(get_twin()).issues()


@router.get("/mock/tracker/issues/{key}")
def tracker_issue(key: str) -> dict[str, Any]:
    try:
        return TrackerConnector(get_twin()).issue(key)
    except RecordNotFoundError as exc:
        raise _not_found(exc) from None


@router.get("/mock/tracker/sprints/current")
def tracker_sprint() -> dict[str, Any]:
    return TrackerConnector(get_twin()).current_sprint()


# ---- erp -------------------------------------------------------------------------------


@router.get("/mock/erp/invoices")
def erp_invoices() -> list[dict[str, Any]]:
    return ErpConnector(get_twin()).invoices()


@router.get("/mock/erp/budgets/recovery")
def erp_recovery_budget() -> dict[str, Any]:
    return ErpConnector(get_twin()).recovery_budget()


@router.get("/mock/erp/purchase-orders")
def erp_purchase_orders() -> list[dict[str, Any]]:
    return ErpConnector(get_twin()).purchase_orders()


# ---- crm -------------------------------------------------------------------------------


@router.get("/mock/crm/accounts/{account_id}")
def crm_account(account_id: str) -> dict[str, Any]:
    try:
        return CrmConnector(get_twin()).account(account_id)
    except RecordNotFoundError as exc:
        raise _not_found(exc) from None


@router.get("/mock/crm/commitments")
def crm_commitments() -> list[dict[str, Any]]:
    return CrmConnector(get_twin()).commitments()


@router.get("/mock/crm/meetings")
def crm_meetings() -> list[dict[str, Any]]:
    return CrmConnector(get_twin()).meetings()


# ---- calendar --------------------------------------------------------------------------


@router.get("/mock/calendar/freebusy")
def calendar_freebusy(person: _Ref, preset: _Ref | None = None) -> dict[str, Any]:
    try:
        return CalendarConnector(get_twin()).freebusy(person, preset)
    except RecordNotFoundError as exc:
        raise _not_found(exc) from None


@router.get("/mock/calendar/events")
def calendar_events() -> list[dict[str, Any]]:
    return CalendarConnector(get_twin()).events()


__all__ = ["router"]

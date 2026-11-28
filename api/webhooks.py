"""Simulated inbound webhooks (docs/contracts.md 3b): one signed inbox for six systems.

`GET /api/webhooks/samples` plays the sending systems (signs a realistic payload for each);
`POST /api/webhooks/{source}` plays the receiving side: verify the signature over the exact body,
read the system's native payload with that system's adapter, and answer with the event the
recovery flow will run on. Everything is fabricated, in-process and stateless; no model is called.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response

from api.errors import ApiError
from api.event import twin_for
from api.security import MAX_BODY_BYTES, require_passcode
from datahub import event_twin
from datahub.db import DatabaseMissingError
from datahub.event_twin import EventError
from integrations import gdocs, webhooks
from integrations.webhooks import BY_SOURCE, WebhookError

TAG = "Simulated webhooks"


def _mark_simulated(response: Response) -> None:
    response.headers["X-Simulated"] = "true"


router = APIRouter(tags=[TAG], dependencies=[Depends(_mark_simulated)])


@router.get("/api/webhooks/samples", dependencies=[Depends(require_passcode)])
def samples() -> list[dict[str, Any]]:
    try:
        return [webhooks.sample_envelope(a) for a in webhooks.ADAPTERS]
    except (DatabaseMissingError, LookupError):
        raise ApiError(503, "DataUnavailable", "The company data is not available.") from None


@router.post("/api/webhooks/{source}", dependencies=[Depends(require_passcode)])
async def receive(
    source: str,
    request: Request,
    x_demo_signature: Annotated[str | None, Header(max_length=100)] = None,
) -> dict[str, Any]:
    adapter = BY_SOURCE.get(source)
    if adapter is None:
        raise ApiError(404, "NotFound", "Unknown webhook source.")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise ApiError(400, "ValidationError", "The request is too large.")
    if not webhooks.verify(body, x_demo_signature):  # before anything is read from the body
        raise ApiError(401, "InvalidSignature", "The webhook signature does not match the body.")
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        raise ApiError(400, "ValidationError", "The webhook body is not a JSON object.")
    try:
        result = adapter.normalize(payload)
    except (WebhookError, EventError) as exc:
        raise ApiError(400, "ValidationError", str(exc)) from None
    except DatabaseMissingError:
        raise ApiError(503, "DataUnavailable", "The company data is not available.") from None
    preset_id = event_twin.preset_id_for(result.event)
    twin_for(preset_id, result.event)  # a 409 NoImpact now, not after the run has started
    return {
        "source": adapter.source,
        "system": adapter.system,
        "department": adapter.department,
        "eventType": adapter.event_type,
        "signature": "verified (demo)",
        "summary": result.summary,
        "fetched": list(result.fetched),
        "presetId": preset_id,
        "event": result.event.model_dump(mode="json"),
    }


@router.get("/simulated/docs/v1/documents/{document_id}")
def docs_document(document_id: str) -> dict[str, Any]:
    """Simulated Google Docs API `documents.get` for a meeting's minutes."""
    try:
        return gdocs.minutes_document(document_id)
    except LookupError:
        raise ApiError(404, "ValidationError", "Record not found.") from None


__all__ = ["router"]

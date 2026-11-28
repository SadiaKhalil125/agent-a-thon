"""POST /api/event/state: the company model for a typed or webhook event (ADR-006, event flow).

An event ("Camila is on leave for 6 working days", or a client asking for new work) is turned
into the same company model the recovery agents already use, built from the company database by
code (no model call). The other endpoints (`/api/run/stream`, `/api/execute`, `/api/outcome`)
accept the same `event` object and rebuild the identical model, so nothing is stored on the
server between requests.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.errors import ApiError
from api.security import require_passcode
from api.state import build_state
from datahub import event_twin
from datahub.db import DatabaseMissingError
from datahub.event_twin import ClientRequest, EventError, LeaveEvent, NoImpactError
from twin.model import Twin
from twin.seed import get_twin

router = APIRouter()

AnyEvent = LeaveEvent | ClientRequest


def twin_for(preset_id: str, event: AnyEvent | None) -> Twin:
    """The company for a request: the seed, or the model built for the event."""
    if event is None:
        return get_twin()
    if preset_id != event_twin.preset_id_for(event):
        raise ApiError(400, "ValidationError", "Unknown presetId.")
    try:
        return event_twin.build_twin(event)
    except NoImpactError as exc:
        raise ApiError(409, "NoImpact", str(exc)) from None
    except EventError as exc:
        raise ApiError(400, "ValidationError", str(exc)) from None
    except DatabaseMissingError:
        raise ApiError(503, "DataUnavailable", "The company data is not available.") from None


@router.post("/api/event/state", dependencies=[Depends(require_passcode)])
def event_state(req: AnyEvent) -> dict[str, Any]:
    preset_id = event_twin.preset_id_for(req)
    twin = twin_for(preset_id, req)
    return {
        "presetId": preset_id,
        "state": build_state(twin).model_dump(mode="json"),
        "calendar": event_twin.calendar_dates(),
    }


__all__ = ["AnyEvent", "router", "twin_for"]
